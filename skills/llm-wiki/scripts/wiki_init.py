#!/usr/bin/env python3
"""
wiki_init.py — scaffold a new LLM wiki folder.

Creates the directory layout described in the skill's schema.md,
copies the schema to the new wiki as SCHEMA.md (the personalized
copy), seeds index.md and log.md with minimal starter content, and
optionally initializes a git repo.

Usage:
    wiki_init.py <path> [--git] [--force] [--format text|json]

The default schema is copied from `../schema.md` (sibling of the
scripts/ folder). If you want a different schema, edit schema.md in
the skill folder before running this script, or edit the resulting
SCHEMA.md in the target wiki folder afterwards.
"""
from __future__ import annotations

import argparse
import datetime as dt
import json
import shutil
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


HERE = Path(__file__).resolve().parent
SKILL_ROOT = HERE.parent
DEFAULT_SCHEMA = SKILL_ROOT / "schema.md"


# Directory layout defined by schema.md §1. Keep in sync.
DIRECTORIES = [
    "raw",
    "raw/assets",
    "wiki",
    "wiki/entities",
    "wiki/concepts",
    "wiki/sources",
    "wiki/synthesis",
]


GITIGNORE = """\
# macOS / editors
.DS_Store
Thumbs.db
*.swp
*.swo
*~
.idea/
.vscode/

# Trashed pages (from lint moves)
.trash/
"""


@dataclass
class InitResult:
    path: str
    created_directories: list[str] = field(default_factory=list)
    created_files: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    git_initialized: bool = False
    error: Optional[str] = None


def today() -> str:
    return dt.date.today().isoformat()


def init_wiki(target: Path, *, do_git: bool, force: bool) -> InitResult:
    result = InitResult(path=str(target))

    # --- Pre-flight checks ---
    if target.exists() and any(target.iterdir()) and not force:
        claude_md = target / "SCHEMA.md"
        if claude_md.exists():
            result.error = (
                f"target already contains a wiki (SCHEMA.md exists at {claude_md}). "
                "Pass --force to overwrite (careful: this will replace SCHEMA.md)."
            )
            return result
        # Non-empty folder without SCHEMA.md — abort unless --force.
        result.error = (
            f"target folder {target} is not empty. Pass --force if you really want "
            "to scaffold a wiki on top of existing files."
        )
        return result

    if not DEFAULT_SCHEMA.exists():
        result.error = (
            f"default schema not found at {DEFAULT_SCHEMA}. Did you copy the skill "
            "folder correctly? schema.md is a required sibling of scripts/."
        )
        return result

    # --- Create directories ---
    try:
        target.mkdir(parents=True, exist_ok=True)
        for rel in DIRECTORIES:
            d = target / rel
            if d.exists():
                result.skipped.append(str(d))
                continue
            d.mkdir(parents=True, exist_ok=False)
            result.created_directories.append(str(d))
    except OSError as e:
        result.error = f"failed to create directories: {e}"
        return result

    # --- Copy schema.md to SCHEMA.md ---
    try:
        claude_md = target / "SCHEMA.md"
        if claude_md.exists() and not force:
            result.skipped.append(str(claude_md))
        else:
            shutil.copy2(DEFAULT_SCHEMA, claude_md)
            result.created_files.append(str(claude_md))
    except OSError as e:
        result.error = f"failed to copy schema to SCHEMA.md: {e}"
        return result

    # --- Seed index.md ---
    index_md = target / "index.md"
    if index_md.exists() and not force:
        result.skipped.append(str(index_md))
    else:
        try:
            index_md.write_text(
                f"# Wiki index\n\nLast updated: {today()}\n\n"
                "## By kind\n"
                "- **Entities**: _(none yet)_\n"
                "- **Concepts**: _(none yet)_\n"
                "- **Syntheses**: _(none yet)_\n"
                "- **Recent sources**: see `log.md`\n\n"
                "## By topic\n"
                "_(topics will appear here as you ingest sources)_\n",
                encoding="utf-8",
            )
            result.created_files.append(str(index_md))
        except OSError as e:
            result.error = f"failed to write index.md: {e}"
            return result

    # --- Seed log.md ---
    log_md = target / "log.md"
    if log_md.exists() and not force:
        result.skipped.append(str(log_md))
    else:
        try:
            log_md.write_text(
                "# Log\n\n"
                f"## [{today()}] Init: wiki created with default schema\n"
                "- **Schema source**: `llm-wiki` skill, default `schema.md`\n"
                "- **Directories created**: "
                f"{', '.join('`' + d + '`' for d in DIRECTORIES)}\n"
                "- **Next step**: drop a source into `raw/` and ask an agent to ingest it\n",
                encoding="utf-8",
            )
            result.created_files.append(str(log_md))
        except OSError as e:
            result.error = f"failed to write log.md: {e}"
            return result

    # --- Optionally init git ---
    if do_git:
        gitignore = target / ".gitignore"
        if not gitignore.exists():
            try:
                gitignore.write_text(GITIGNORE, encoding="utf-8")
                result.created_files.append(str(gitignore))
            except OSError as e:
                result.error = f"failed to write .gitignore: {e}"
                return result
        # Run git init if there's no .git already.
        if not (target / ".git").exists():
            try:
                subprocess.run(
                    ["git", "init", "--quiet"],
                    cwd=target,
                    check=True,
                    capture_output=True,
                )
                result.git_initialized = True
            except (subprocess.CalledProcessError, FileNotFoundError) as e:
                result.error = (
                    f"failed to initialize git (is git installed?): {e}. "
                    "The wiki scaffold itself is fine; just skip --git next time "
                    "or initialize the repo manually."
                )
                return result

    return result


def render_text(r: InitResult) -> str:
    out: list[str] = []
    if r.error:
        out.append(f"error: {r.error}")
        return "\n".join(out)

    out.append(f"# wiki_init — wiki created at {r.path}")
    out.append("")
    out.append(f"Directories created: {len(r.created_directories)}")
    for d in r.created_directories:
        out.append(f"  + {d}")
    out.append("")
    out.append(f"Files created: {len(r.created_files)}")
    for f in r.created_files:
        out.append(f"  + {f}")
    if r.skipped:
        out.append("")
        out.append(f"Skipped (already existed): {len(r.skipped)}")
        for s in r.skipped:
            out.append(f"  ~ {s}")
    if r.git_initialized:
        out.append("")
        out.append("git: initialized (no commits yet)")
    out.append("")
    out.append("Next steps:")
    out.append(f"  1. Review {r.path}/SCHEMA.md — this is your wiki's schema. Edit it if you")
    out.append("     want to deviate from the default Karpathy-inspired layout.")
    out.append(f"  2. Drop a source file into {r.path}/raw/ (a PDF, markdown, or saved article).")
    out.append("  3. Ask your agent: 'add this to my wiki' and point at the source.")
    return "\n".join(out)


def render_json(r: InitResult) -> str:
    return json.dumps(asdict(r), ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wiki_init.py",
        description="Scaffold a new LLM wiki folder with the default schema.",
    )
    p.add_argument("path", help="Target directory for the new wiki.")
    p.add_argument("--git", action="store_true",
                   help="Initialize a git repo and write a sensible .gitignore.")
    p.add_argument("--force", action="store_true",
                   help="Overwrite an existing wiki at this path. Use with care.")
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
    target = Path(args.path).expanduser().resolve()

    result = init_wiki(target, do_git=args.git, force=args.force)

    if args.format == "json":
        print(render_json(result))
    else:
        print(render_text(result))

    return 0 if result.error is None else 2


if __name__ == "__main__":
    sys.exit(main())
