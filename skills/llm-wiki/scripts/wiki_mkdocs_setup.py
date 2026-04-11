#!/usr/bin/env python3
"""
wiki_mkdocs_setup.py — add a mkdocs configuration to an existing wiki.

Reads the mkdocs.yml template from the skill folder and writes it to
<wiki-path>/mkdocs.yml, so the user can run `mkdocs serve` or
`mkdocs build` to browse their wiki as a local website.

This script does **not** install mkdocs itself — it only writes the
config file and prints instructions. mkdocs and mkdocs-material are
optional Python packages the user installs separately with pip.

Usage:
    wiki_mkdocs_setup.py <wiki-path> [--force] [--format text|json]

The wiki must already exist (it needs a SCHEMA.md at its root — run
wiki_init.py first if it doesn't).
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

sys.path.insert(0, str(Path(__file__).resolve().parent))
import _preflight  # noqa: E402


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
TEMPLATE_PATH = SKILL_ROOT / "templates" / "mkdocs.yml"


@dataclass
class SetupResult:
    wiki_path: str
    mkdocs_file: str
    created: bool = False
    skipped_existing: bool = False
    mkdocs_installed: bool = False
    mkdocs_material_installed: bool = False
    error: Optional[str] = None
    log_entry_appended: bool = False


def today() -> str:
    return dt.date.today().isoformat()


def _append_log_entry(wiki_path: Path) -> bool:
    """Append a '## [DATE] Mkdocs: ...' entry to log.md. Best-effort."""
    log_file = wiki_path / "log.md"
    if not log_file.exists():
        return False
    try:
        with log_file.open("a", encoding="utf-8") as f:
            f.write(
                f"\n## [{today()}] Mkdocs: setup completed\n"
                "- **Config file**: `mkdocs.yml` (from the llm-wiki skill template)\n"
                "- **Theme**: Material for MkDocs\n"
                "- **Next**: run `pip install mkdocs mkdocs-material` then `mkdocs serve`\n"
            )
        return True
    except OSError:
        return False


def setup_mkdocs(wiki_path: Path, *, force: bool) -> SetupResult:
    result = SetupResult(
        wiki_path=str(wiki_path),
        mkdocs_file=str(wiki_path / "mkdocs.yml"),
    )

    # --- Pre-flight checks ---
    if not wiki_path.exists() or not wiki_path.is_dir():
        result.error = f"wiki path does not exist or is not a directory: {wiki_path}"
        return result

    if not (wiki_path / "SCHEMA.md").exists():
        result.error = (
            f"no SCHEMA.md at {wiki_path}. This doesn't look like a wiki. "
            "Run wiki_init.py first to scaffold a wiki."
        )
        return result

    if not TEMPLATE_PATH.exists():
        result.error = (
            f"mkdocs template not found at {TEMPLATE_PATH}. Did you copy the skill "
            "folder correctly? The template is a required sibling of scripts/."
        )
        return result

    target = wiki_path / "mkdocs.yml"

    # --- Don't clobber existing config ---
    if target.exists() and not force:
        result.skipped_existing = True
        result.error = (
            f"mkdocs.yml already exists at {target}. Pass --force to overwrite."
        )
        return result

    # --- Copy the template ---
    try:
        shutil.copy2(TEMPLATE_PATH, target)
        result.created = True
    except OSError as e:
        result.error = f"failed to copy template: {e}"
        return result

    # --- Check if mkdocs and mkdocs-material are installed ---
    present, _ = _preflight.check(["mkdocs"])
    result.mkdocs_installed = "mkdocs" in present
    material_present, _ = _preflight.check(["material"])
    result.mkdocs_material_installed = "material" in material_present

    # --- Append to log.md ---
    result.log_entry_appended = _append_log_entry(wiki_path)

    return result


def render_text(r: SetupResult) -> str:
    out: list[str] = []
    if r.error and not r.created:
        out.append(f"error: {r.error}")
        return "\n".join(out)

    out.append(f"# wiki_mkdocs_setup — {r.wiki_path}")
    out.append("")

    if r.created:
        out.append(f"✓ mkdocs.yml created at {r.mkdocs_file}")
    if r.log_entry_appended:
        out.append("✓ log entry appended to log.md")

    out.append("")
    out.append("Installed Python packages:")
    out.append(
        f"  mkdocs:          {'✓ installed' if r.mkdocs_installed else '✗ missing'}"
    )
    out.append(
        f"  mkdocs-material: {'✓ installed' if r.mkdocs_material_installed else '✗ missing'}"
    )
    out.append("")

    if not (r.mkdocs_installed and r.mkdocs_material_installed):
        out.append("Install the missing packages with:")
        out.append(f'  "{sys.executable}" -m pip install --user mkdocs mkdocs-material')
        out.append("")

    out.append("Next steps:")
    out.append(f"  1. cd {r.wiki_path}")
    out.append("  2. mkdocs serve       # preview at http://127.0.0.1:8000")
    out.append("  3. mkdocs build       # build a static site into ./site/")
    out.append("")
    out.append(f"Config file: {r.mkdocs_file}")
    out.append("Customize freely — this is your wiki's config, not the skill's.")
    return "\n".join(out)


def render_json(r: SetupResult) -> str:
    return json.dumps(asdict(r), ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wiki_mkdocs_setup.py",
        description="Add a mkdocs configuration to an existing LLM wiki "
                    "so it can be browsed as a local website.",
    )
    p.add_argument("wiki_path", help="Path to the existing wiki folder.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing mkdocs.yml. Use with care.")
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

    result = setup_mkdocs(wiki_path, force=args.force)

    if args.format == "json":
        print(render_json(result))
    else:
        print(render_text(result))

    return 0 if result.created else 2


if __name__ == "__main__":
    sys.exit(main())
