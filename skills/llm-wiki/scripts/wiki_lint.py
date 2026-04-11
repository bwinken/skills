#!/usr/bin/env python3
"""
wiki_lint.py — deterministic health checks for an LLM wiki.

Runs the five mechanical checks described in schema.md §9 and the
lint workflow. Never modifies the wiki — it only reports findings
(in text or JSON) so the calling agent can decide what to do.

Checks:
  * broken-links     — markdown links like [text](path.md) whose relative
                       path (resolved against the containing file) does
                       not point to an existing file
  * orphans          — pages in wiki/ that no other file links to
  * frontmatter      — missing required YAML frontmatter fields
  * stale            — pages whose `updated:` date is older than N days
  * unref-sources    — source pages that no entity/concept/synthesis cites

Usage:
    wiki_lint.py <wiki-path> [--mode all|broken-links|orphans|frontmatter|stale|unref-sources]
                             [--stale-days 180]
                             [--format text|json]

The script is purely read-only. Nothing in the wiki is modified. If
you want to auto-fix the trivially-fixable findings, that's the
agent's job (it should follow workflows/lint.md).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


REQUIRED_FRONTMATTER_FIELDS = {"title", "kind", "created", "updated"}
VALID_KINDS = {"entity", "concept", "source", "synthesis"}
# Markdown link regex: [display](target.md) or [display](target.md#anchor).
# We capture the target path only. The path may include ../ segments and
# subdirectories. Excludes absolute URLs (http://, https://, etc.).
MARKDOWN_LINK_RE = re.compile(
    r"\[[^\]]*\]\(((?!https?://|mailto:|#)[^)\s#]+?\.md)(?:#[^)]*)?\)"
)
FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)


# ---------------------------------------------------------------------------
# Data model
# ---------------------------------------------------------------------------

@dataclass
class PageInfo:
    path: str                    # absolute path
    rel_path: str                # relative to wiki root, forward slashes
    kind_folder: str             # "entities" / "concepts" / "sources" / "synthesis"
    frontmatter: dict = field(default_factory=dict)
    body: str = ""
    # Raw link targets as they appear in the markdown (e.g. "../entities/foo.md")
    raw_link_targets: list[str] = field(default_factory=list)
    # Parallel list: for each raw target, the resolved absolute path (if it
    # points at an existing file inside the wiki), or None if broken.
    resolved_links: list[Optional[str]] = field(default_factory=list)
    has_frontmatter: bool = False


@dataclass
class Finding:
    category: str                # "broken-links" | "orphans" | ...
    severity: str                # "error" | "warning" | "info"
    page: Optional[str]          # relative path of the affected page (if any)
    message: str
    details: dict = field(default_factory=dict)


@dataclass
class LintReport:
    wiki_path: str
    pages_scanned: int
    findings: list[Finding] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    error: Optional[str] = None


# ---------------------------------------------------------------------------
# Parsing helpers
# ---------------------------------------------------------------------------

def _parse_frontmatter(text: str) -> tuple[dict, str]:
    """Return (frontmatter_dict, body). Handles simple YAML only — no nesting."""
    m = FRONTMATTER_RE.match(text)
    if not m:
        return {}, text
    raw = m.group(1)
    body = text[m.end():]
    fm: dict = {}
    for line in raw.splitlines():
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        key = key.strip()
        value = value.strip()
        # Strip quotes and brackets for list-like fields (best effort).
        if value.startswith("[") and value.endswith("]"):
            inner = value[1:-1].strip()
            fm[key] = [v.strip().strip('"').strip("'") for v in inner.split(",") if v.strip()]
        else:
            fm[key] = value.strip('"').strip("'")
    return fm, body


def _collect_markdown_links(body: str) -> list[str]:
    """Extract markdown link targets (relative .md paths) from a page body."""
    targets: list[str] = []
    for m in MARKDOWN_LINK_RE.finditer(body):
        target = m.group(1).strip()
        targets.append(target)
    return targets


def _resolve_link(link_target: str, source_file: Path, wiki_root: Path) -> Optional[Path]:
    """
    Resolve a relative markdown link against its source file's directory.
    Returns the absolute path of the target file if it exists inside the
    wiki_root (or is a raw/ file), None otherwise.

    `source_file` is the file containing the link; `wiki_root` is the wiki's
    top-level folder. The target is resolved relative to `source_file`'s
    parent directory — standard markdown link semantics.
    """
    try:
        base = source_file.parent
        candidate = (base / link_target).resolve()
    except (OSError, ValueError):
        return None

    # Must stay inside the wiki root (no escaping).
    try:
        candidate.relative_to(wiki_root.resolve())
    except ValueError:
        return None

    return candidate if candidate.exists() else None


def _load_pages(wiki_root: Path) -> list[PageInfo]:
    """Scan wiki/ folder for markdown files and resolve their links."""
    wiki_dir = wiki_root / "wiki"
    pages: list[PageInfo] = []
    if not wiki_dir.is_dir():
        return pages

    for md_path in sorted(wiki_dir.rglob("*.md")):
        try:
            text = md_path.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        fm, body = _parse_frontmatter(text)
        rel = md_path.relative_to(wiki_root).as_posix()
        kind_folder = md_path.relative_to(wiki_dir).parts[0] if md_path.relative_to(wiki_dir).parts else ""
        raw_targets = _collect_markdown_links(body)
        resolved = [
            str(r) if (r := _resolve_link(t, md_path, wiki_root)) else None
            for t in raw_targets
        ]
        pages.append(PageInfo(
            path=str(md_path),
            rel_path=rel,
            kind_folder=kind_folder,
            frontmatter=fm,
            body=body,
            raw_link_targets=raw_targets,
            resolved_links=resolved,
            has_frontmatter=bool(fm),
        ))
    return pages


def _collect_all_linked_pages(wiki_root: Path, pages: list[PageInfo]) -> set[str]:
    """
    Return the set of absolute path strings that are targets of any link
    in the wiki (both from pages under wiki/ and from top-level index.md).
    Used for orphan detection.
    """
    linked: set[str] = set()
    for p in pages:
        for r in p.resolved_links:
            if r is not None:
                linked.add(r)

    # Also include links from index.md (it's the curated map of the wiki)
    index = wiki_root / "index.md"
    if index.exists():
        try:
            body = index.read_text(encoding="utf-8", errors="replace")
            for target in _collect_markdown_links(body):
                resolved = _resolve_link(target, index, wiki_root)
                if resolved is not None:
                    linked.add(str(resolved))
        except OSError:
            pass
    return linked


# ---------------------------------------------------------------------------
# Checks
# ---------------------------------------------------------------------------

def check_broken_links(pages: list[PageInfo]) -> list[Finding]:
    findings: list[Finding] = []
    for p in pages:
        for raw, resolved in zip(p.raw_link_targets, p.resolved_links):
            if resolved is not None:
                continue
            findings.append(Finding(
                category="broken-links",
                severity="error",
                page=p.rel_path,
                message=f"broken link: ({raw})",
                details={"target": raw},
            ))
    return findings


def check_orphans(pages: list[PageInfo], linked: set[str]) -> list[Finding]:
    findings: list[Finding] = []
    for p in pages:
        if p.path in linked:
            continue
        findings.append(Finding(
            category="orphans",
            severity="warning",
            page=p.rel_path,
            message="orphan page: nothing links to this file",
        ))
    return findings


def check_frontmatter(pages: list[PageInfo]) -> list[Finding]:
    findings: list[Finding] = []
    for p in pages:
        if not p.has_frontmatter:
            findings.append(Finding(
                category="frontmatter",
                severity="error",
                page=p.rel_path,
                message="no YAML frontmatter",
            ))
            continue
        missing = REQUIRED_FRONTMATTER_FIELDS - set(p.frontmatter.keys())
        if missing:
            findings.append(Finding(
                category="frontmatter",
                severity="warning",
                page=p.rel_path,
                message=f"missing required fields: {sorted(missing)}",
                details={"missing": sorted(missing)},
            ))
        kind = p.frontmatter.get("kind")
        if kind and kind not in VALID_KINDS:
            findings.append(Finding(
                category="frontmatter",
                severity="warning",
                page=p.rel_path,
                message=f"invalid kind: {kind!r} (expected one of {sorted(VALID_KINDS)})",
                details={"kind": kind},
            ))
        # kind should match folder (entities/ -> entity, etc.)
        if kind and p.kind_folder:
            expected_kind = p.kind_folder.rstrip("s")  # entities -> entitie (bad)
            # Map folder names to kinds
            folder_to_kind = {
                "entities": "entity",
                "concepts": "concept",
                "sources": "source",
                "synthesis": "synthesis",
            }
            expected = folder_to_kind.get(p.kind_folder)
            if expected and kind != expected:
                findings.append(Finding(
                    category="frontmatter",
                    severity="warning",
                    page=p.rel_path,
                    message=f"kind mismatch: page says {kind!r} but folder is {p.kind_folder!r} (expected kind {expected!r})",
                ))
    return findings


def check_stale(pages: list[PageInfo], stale_days: int) -> list[Finding]:
    findings: list[Finding] = []
    threshold = dt.date.today() - dt.timedelta(days=stale_days)
    for p in pages:
        updated = p.frontmatter.get("updated")
        if not updated:
            continue
        try:
            u = dt.date.fromisoformat(updated)
        except (ValueError, TypeError):
            continue
        if u < threshold:
            findings.append(Finding(
                category="stale",
                severity="info",
                page=p.rel_path,
                message=f"page has not been updated in {(dt.date.today() - u).days} days (threshold: {stale_days})",
                details={"updated": updated, "days_old": (dt.date.today() - u).days},
            ))
    return findings


def check_unref_sources(pages: list[PageInfo]) -> list[Finding]:
    findings: list[Finding] = []
    # Sources are in wiki/sources/
    source_pages = [p for p in pages if p.kind_folder == "sources"]
    # Collect every resolved link from non-source pages (absolute paths)
    non_source_citations: set[str] = set()
    for p in pages:
        if p.kind_folder == "sources":
            continue
        for r in p.resolved_links:
            if r is not None:
                non_source_citations.add(r)

    for sp in source_pages:
        if sp.path in non_source_citations:
            continue
        findings.append(Finding(
            category="unref-sources",
            severity="warning",
            page=sp.rel_path,
            message="source page is not cited by any entity, concept, or synthesis page",
        ))
    return findings


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

def run_lint(wiki_path: Path, *, mode: str, stale_days: int) -> LintReport:
    report = LintReport(wiki_path=str(wiki_path), pages_scanned=0)
    if not wiki_path.exists() or not wiki_path.is_dir():
        report.error = f"wiki path does not exist or is not a directory: {wiki_path}"
        return report
    if not (wiki_path / "SCHEMA.md").exists():
        report.error = (
            f"no SCHEMA.md at {wiki_path}. This doesn't look like a wiki. "
            "Run wiki_init.py first."
        )
        return report

    pages = _load_pages(wiki_path)
    report.pages_scanned = len(pages)

    linked_pages = _collect_all_linked_pages(wiki_path, pages)

    modes = {mode} if mode != "all" else {
        "broken-links", "orphans", "frontmatter", "stale", "unref-sources",
    }

    if "broken-links" in modes:
        report.findings.extend(check_broken_links(pages))
    if "orphans" in modes:
        report.findings.extend(check_orphans(pages, linked_pages))
    if "frontmatter" in modes:
        report.findings.extend(check_frontmatter(pages))
    if "stale" in modes:
        report.findings.extend(check_stale(pages, stale_days))
    if "unref-sources" in modes:
        report.findings.extend(check_unref_sources(pages))

    # Build summary counts per category
    for f in report.findings:
        report.summary[f.category] = report.summary.get(f.category, 0) + 1

    return report


def render_text(report: LintReport) -> str:
    out: list[str] = []
    if report.error:
        return f"error: {report.error}"

    out.append(f"# wiki_lint — {report.wiki_path}")
    out.append(f"pages scanned: {report.pages_scanned}")
    out.append(f"total findings: {len(report.findings)}")
    if report.summary:
        out.append("by category:")
        for cat, n in sorted(report.summary.items()):
            out.append(f"  {cat}: {n}")
    out.append("")

    if not report.findings:
        out.append("✓ no findings — wiki is clean.")
        return "\n".join(out)

    # Group findings by category for readable output
    by_cat: dict[str, list[Finding]] = {}
    for f in report.findings:
        by_cat.setdefault(f.category, []).append(f)

    for cat in sorted(by_cat):
        out.append(f"## {cat} ({len(by_cat[cat])})")
        for f in by_cat[cat]:
            prefix = f"[{f.severity}]"
            if f.page:
                out.append(f"  {prefix} {f.page}: {f.message}")
            else:
                out.append(f"  {prefix} {f.message}")
        out.append("")

    return "\n".join(out).rstrip()


def render_json(report: LintReport) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wiki_lint.py",
        description="Deterministic health checks for an LLM wiki "
                    "(orphans, broken links, frontmatter, stale pages, unreferenced sources).",
    )
    p.add_argument("wiki_path", help="Path to the wiki folder.")
    p.add_argument(
        "--mode",
        default="all",
        choices=("all", "broken-links", "orphans", "frontmatter", "stale", "unref-sources"),
        help="Which check to run (default: all).",
    )
    p.add_argument("--stale-days", type=int, default=180,
                   help="A page is stale if its updated: date is older than this many days (default: 180).")
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
    wiki_path = Path(args.wiki_path).expanduser().resolve()

    report = run_lint(wiki_path, mode=args.mode, stale_days=args.stale_days)

    if args.format == "json":
        print(render_json(report))
    else:
        print(render_text(report))

    # Exit code: 0 if clean or info-only, 1 if warnings found, 2 on error
    if report.error:
        return 2
    severities = {f.severity for f in report.findings}
    if "error" in severities or "warning" in severities:
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
