#!/usr/bin/env python3
"""
pdf-inspector — structural inspection of a PDF file.

Unlike pdf-reader, which returns *text*, this skill returns *structure* —
the deterministic facts an LLM cannot reliably infer from extracted
text:

  * /Info dictionary metadata (title, author, dates, creator, producer)
  * Structural facts from the document catalog (page count, encryption,
    first-page size, PDF version)
  * AcroForm field inventory (field names, types, values, required /
    read-only flags, best-effort page numbers)

Sibling skills in the `document-inspector` plugin handle other formats
(docx-inspector for .docx, xlsx-inspector for .xlsx). This skill is
PDF-only by design.

Usage:
    pdf_inspector.py <file> --feature metadata|forms|all
                            [--format text|json]

Run with --help for the full option list.
"""
from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field, asdict
from datetime import datetime
from pathlib import Path
from typing import Any, Optional

# Self-contained install-guide helper (copied from template/_preflight.py).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _preflight  # noqa: E402


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class FormField:
    name: str
    field_type: str          # /Tx, /Btn, /Ch, /Sig, or "unknown"
    field_type_label: str    # human label: "text", "button", "choice", "signature"
    value: Optional[str] = None
    required: bool = False
    read_only: bool = False
    page: Optional[int] = None


@dataclass
class AnalyzeResult:
    path: str
    extension: str
    kind: str
    feature: str             # "metadata", "forms", or "all"
    size: int = 0
    metadata: dict = field(default_factory=dict)
    forms: dict = field(default_factory=dict)  # {"has_form": bool, "field_count": N, "fields": [...]}
    error: Optional[str] = None
    missing_imports: list[str] = field(default_factory=list)
    install_guide: Optional[str] = None


class MissingDependency(RuntimeError):
    def __init__(self, import_name: str, feature: str):
        self.import_name = import_name
        self.feature = feature
        super().__init__(f"missing optional package '{import_name}' for {feature}")


# ---------------------------------------------------------------------------
# PDF feature: metadata
# ---------------------------------------------------------------------------

# Fields in /Info we recognise. Any other field is still surfaced under
# "extra" so nothing from the document is silently dropped.
PDF_INFO_FIELDS = (
    "/Title", "/Author", "/Subject", "/Keywords",
    "/Creator", "/Producer",
    "/CreationDate", "/ModDate",
    "/Trapped",
)


def _pdf_date_to_iso(raw: str) -> str:
    """
    Convert a PDF date string (e.g. 'D:20251231140530+00'00'') into an
    ISO-8601-ish string. Best-effort: if parsing fails, return the
    original string so no information is lost.
    """
    if not isinstance(raw, str):
        return str(raw)
    s = raw
    if s.startswith("D:"):
        s = s[2:]
    try:
        year = int(s[0:4])
        month = int(s[4:6]) if len(s) >= 6 else 1
        day = int(s[6:8]) if len(s) >= 8 else 1
        hour = int(s[8:10]) if len(s) >= 10 else 0
        minute = int(s[10:12]) if len(s) >= 12 else 0
        second = int(s[12:14]) if len(s) >= 14 else 0
        dt = datetime(year, month, day, hour, minute, second)
        return dt.isoformat()
    except (ValueError, IndexError):
        return raw


def _pdf_metadata(reader: Any) -> dict:
    """
    Extract document metadata from the /Info dictionary and the document
    catalog. Always returns the same shape — missing values become None
    rather than being omitted, so the agent can reason about "empty"
    distinctly from "absent".
    """
    info = getattr(reader, "metadata", None) or {}

    out: dict[str, Any] = {}
    for key in PDF_INFO_FIELDS:
        value = None
        try:
            value = info.get(key) if hasattr(info, "get") else info[key]  # type: ignore[index]
        except (KeyError, TypeError):
            value = None
        if value is None:
            out[key.lstrip("/").lower()] = None
            continue
        s = str(value)
        if "date" in key.lower():
            out[key.lstrip("/").lower()] = _pdf_date_to_iso(s)
        else:
            out[key.lstrip("/").lower()] = s

    # Extra /Info keys we didn't name above — keep them for completeness.
    try:
        if hasattr(info, "keys"):
            extra: dict[str, Any] = {}
            for key in info.keys():  # type: ignore[attr-defined]
                if key in PDF_INFO_FIELDS:
                    continue
                try:
                    extra[str(key).lstrip("/")] = str(info[key])  # type: ignore[index]
                except Exception:  # noqa: BLE001
                    continue
            if extra:
                out["extra"] = extra
    except Exception:  # noqa: BLE001
        pass

    # Page count + basic structural facts.
    try:
        out["total_pages"] = len(reader.pages)
    except Exception:  # noqa: BLE001
        out["total_pages"] = None

    # Encryption / permissions.
    try:
        out["encrypted"] = bool(getattr(reader, "is_encrypted", False))
    except Exception:  # noqa: BLE001
        out["encrypted"] = None

    # Page size of first page, in PDF user-space units (72 units ≈ 1 inch).
    try:
        if len(reader.pages) > 0:
            first = reader.pages[0]
            mediabox = getattr(first, "mediabox", None)
            if mediabox is not None:
                out["first_page_size"] = {
                    "width": float(mediabox.width),
                    "height": float(mediabox.height),
                    "unit": "points",
                }
    except Exception:  # noqa: BLE001
        pass

    # PDF version (on the document catalog).
    try:
        version = getattr(reader, "pdf_header", None)
        if version:
            out["pdf_version"] = str(version).strip()
    except Exception:  # noqa: BLE001
        pass

    return out


# ---------------------------------------------------------------------------
# PDF feature: forms
# ---------------------------------------------------------------------------

_FT_LABELS = {
    "/Tx": "text",
    "/Btn": "button",  # checkbox / radio / pushbutton — refined via /Ff flags below if needed
    "/Ch": "choice",
    "/Sig": "signature",
}


def _pdf_forms(reader: Any) -> dict:
    """
    Walk the AcroForm (if any) and return an inventory of form fields:
    name, type, current value, required/read-only flags, and the page
    the field lives on (best effort).

    Returns:
      {
        "has_form": bool,
        "field_count": N,
        "fields": [FormField, ...],
        "signatures": N,
      }
    """
    result: dict[str, Any] = {
        "has_form": False,
        "field_count": 0,
        "fields": [],
        "signatures": 0,
    }

    # pypdf exposes form fields via reader.get_fields() — returns a dict
    # of name -> {"/FT": type, "/V": value, "/Ff": flags, ...} or None
    # if there is no form.
    try:
        raw_fields = reader.get_fields()
    except Exception:  # noqa: BLE001
        raw_fields = None

    if not raw_fields:
        return result

    result["has_form"] = True
    result["field_count"] = len(raw_fields)

    # Build a page lookup: widget annotation -> page index.
    widget_page: dict[int, int] = {}
    try:
        for idx, page in enumerate(reader.pages):
            annots = page.get("/Annots")
            if not annots:
                continue
            # /Annots may be a reference; resolve to a list.
            try:
                annots = annots.get_object() if hasattr(annots, "get_object") else annots
            except Exception:  # noqa: BLE001
                pass
            for annot in annots or []:
                try:
                    obj = annot.get_object() if hasattr(annot, "get_object") else annot
                except Exception:  # noqa: BLE001
                    continue
                try:
                    widget_page[id(obj)] = idx + 1  # 1-based page numbers
                except Exception:  # noqa: BLE001
                    continue
    except Exception:  # noqa: BLE001
        pass

    fields_out: list[FormField] = []
    signature_count = 0
    for name, data in raw_fields.items():
        if not isinstance(data, dict):
            fields_out.append(FormField(
                name=str(name),
                field_type="unknown",
                field_type_label="unknown",
            ))
            continue

        ft = None
        for key in ("/FT", "FT"):
            if key in data:
                ft = str(data[key])
                break
        ft = ft or "unknown"
        label = _FT_LABELS.get(ft, "unknown")
        if ft == "/Sig":
            signature_count += 1

        value = None
        for key in ("/V", "V", "value"):
            if key in data:
                raw = data[key]
                if raw is None:
                    value = None
                else:
                    try:
                        value = str(raw)
                    except Exception:  # noqa: BLE001
                        value = repr(raw)
                break

        flags = 0
        for key in ("/Ff", "Ff"):
            if key in data:
                try:
                    flags = int(data[key])
                except (TypeError, ValueError):
                    flags = 0
                break
        # PDF field flag bits: 1 (read-only), 2 (required), 4 (no-export).
        read_only = bool(flags & 1)
        required = bool(flags & 2)

        page_number: Optional[int] = None
        # Best-effort: if the field has a /Kids list of widgets, look them up.
        try:
            kids = data.get("/Kids") or data.get("Kids")
            if kids:
                for kid in kids:
                    try:
                        obj = kid.get_object() if hasattr(kid, "get_object") else kid
                    except Exception:  # noqa: BLE001
                        continue
                    pg = widget_page.get(id(obj))
                    if pg is not None:
                        page_number = pg
                        break
        except Exception:  # noqa: BLE001
            pass

        fields_out.append(FormField(
            name=str(name),
            field_type=ft,
            field_type_label=label,
            value=value,
            required=required,
            read_only=read_only,
            page=page_number,
        ))

    result["fields"] = [asdict(f) for f in fields_out]
    result["signatures"] = signature_count
    return result


# ---------------------------------------------------------------------------
# Feature dispatch
# ---------------------------------------------------------------------------

FEATURES = ("metadata", "forms", "all")


def _open_pdf(path: Path):
    try:
        import pypdf  # type: ignore
    except ImportError as e:
        raise MissingDependency("pypdf", "PDF analysis") from e
    return pypdf.PdfReader(str(path))


def analyze(path: Path, feature: str) -> AnalyzeResult:
    result = AnalyzeResult(
        path=str(path),
        extension=path.suffix.lower(),
        kind="pdf" if path.suffix.lower() == ".pdf" else "unknown",
        feature=feature,
        size=path.stat().st_size,
    )

    if result.extension != ".pdf":
        result.error = (
            f"pdf-inspector only accepts .pdf files "
            f"(got {result.extension or '(none)'}) — use docx-inspector "
            f"or xlsx-inspector for other formats"
        )
        return result

    try:
        reader = _open_pdf(path)
    except MissingDependency as e:
        result.error = str(e)
        result.missing_imports = [e.import_name]
        result.install_guide = _preflight.format_install_guide(
            [e.import_name],
            feature="inspecting .pdf files (metadata, forms)",
            skill_name="pdf-inspector",
        )
        return result
    except Exception as e:  # noqa: BLE001
        result.error = f"failed to open PDF: {e}"
        return result

    try:
        if feature in ("metadata", "all"):
            result.metadata = _pdf_metadata(reader)
        if feature in ("forms", "all"):
            result.forms = _pdf_forms(reader)
    except Exception as e:  # noqa: BLE001
        result.error = f"analysis failed: {e}"
        return result

    return result


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def render_text(r: AnalyzeResult) -> str:
    out: list[str] = []
    out.append("# pdf-inspector")
    out.append(f"path:      {r.path}")
    out.append(f"size:      {r.size} bytes")
    out.append(f"kind:      {r.kind}")
    out.append(f"feature:   {r.feature}")
    out.append("")

    if r.error:
        out.append(f"error: {r.error}")
        if r.install_guide:
            out.append("")
            out.append("## Install guide")
            out.append(r.install_guide)
        return "\n".join(out)

    if r.feature in ("metadata", "all") and r.metadata:
        out.append("## Metadata")
        ordered_keys = (
            "title", "author", "subject", "keywords",
            "creator", "producer",
            "creationdate", "moddate",
            "trapped",
            "pdf_version",
            "total_pages", "encrypted",
            "first_page_size",
        )
        for key in ordered_keys:
            if key in r.metadata:
                value = r.metadata[key]
                if isinstance(value, dict):
                    out.append(f"  {key}:")
                    for k, v in value.items():
                        out.append(f"    {k}: {v}")
                else:
                    out.append(f"  {key}: {value if value is not None else '(none)'}")
        extra = r.metadata.get("extra")
        if extra:
            out.append("  extra:")
            for k, v in extra.items():
                out.append(f"    {k}: {v}")
        out.append("")

    if r.feature in ("forms", "all") and r.forms:
        out.append("## Forms")
        if not r.forms.get("has_form"):
            out.append("  (no AcroForm found)")
            return "\n".join(out).rstrip() + "\n"
        out.append(f"  field_count: {r.forms.get('field_count', 0)}")
        out.append(f"  signatures:  {r.forms.get('signatures', 0)}")
        fields = r.forms.get("fields") or []
        if fields:
            out.append("")
            out.append("  fields:")
            for fld in fields[:100]:
                flags: list[str] = []
                if fld.get("required"):
                    flags.append("required")
                if fld.get("read_only"):
                    flags.append("read-only")
                flag_str = f" [{', '.join(flags)}]" if flags else ""
                page_str = f" (page {fld['page']})" if fld.get("page") is not None else ""
                label = fld.get("field_type_label", "unknown")
                name = fld.get("name", "")
                value = fld.get("value")
                if value is None:
                    value_str = ""
                else:
                    # Truncate very long values so the terminal doesn't blow up.
                    short = value if len(value) <= 60 else value[:57] + "..."
                    value_str = f" = {short!r}"
                out.append(f"    [{label}] {name}{page_str}{flag_str}{value_str}")
            if len(fields) > 100:
                out.append(f"    ... ({len(fields) - 100} more fields)")
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def render_json(r: AnalyzeResult) -> str:
    return json.dumps(asdict(r), ensure_ascii=False, indent=2)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="pdf_inspector.py",
        description="Structural inspection of a single PDF file — "
                    "metadata (title/author/dates/encryption/page size) "
                    "and form-field inventory. Returns the deterministic "
                    "facts an LLM cannot derive from extracted text.",
    )
    p.add_argument("file", help="Path to the .pdf file to inspect.")
    p.add_argument("--feature", choices=FEATURES, default="all",
                   help="Which inspection to run (default: all).")
    p.add_argument("--format", choices=("text", "json"), default="text",
                   help="Output format (default: text).")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)
    path = Path(args.file)
    if not path.exists():
        print(f"error: file does not exist: {path}", file=sys.stderr)
        return 2
    if not path.is_file():
        print(f"error: not a regular file: {path}", file=sys.stderr)
        return 2

    result = analyze(path, feature=args.feature)

    if args.format == "json":
        print(render_json(result))
    else:
        print(render_text(result))
    return 0 if result.error is None else 2


if __name__ == "__main__":
    sys.exit(main())
