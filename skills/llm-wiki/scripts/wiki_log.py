#!/usr/bin/env python3
"""
wiki_log.py — read an LLM wiki's append-only log.md.

The wiki's log.md is a chronological record of every ingest, query,
and lint operation. Each entry starts with:

    ## [YYYY-MM-DD] <Operation>: <short description>

This script parses that format and offers a few common slices:
latest N entries, entries by operation type, entries by date range.

Usage:
    wiki_log.py <wiki-path> [--tail N] [--op ingest|query|lint|...]
                            [--since YYYY-MM-DD] [--until YYYY-MM-DD]
                            [--format text|json]

The log.md format is defined by the skill's schema.md §6. If the user
has customized their log format, this script will still find entries
that match the `## [DATE] Operation:` pattern; entries that don't
match are silently ignored.
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


# Matches: ## [2026-04-11] Ingest: Karpathy LLM wiki gist
# Capture groups: 1=date, 2=operation, 3=rest-of-line
HEADER_RE = re.compile(
    r"^##\s+\[(\d{4}-\d{2}-\d{2})\]\s+([A-Za-z]+)\s*:\s*(.*?)\s*$"
)


@dataclass
class LogEntry:
    date: str
    operation: str
    title: str
    body: str = ""


@dataclass
class LogReport:
    wiki_path: str
    log_file: str
    total_entries: int
    returned_entries: int
    entries: list[LogEntry] = field(default_factory=list)
    error: Optional[str] = None


def parse_log(text: str) -> list[LogEntry]:
    """Parse log.md into a list of entries."""
    entries: list[LogEntry] = []
    current: Optional[LogEntry] = None
    body_lines: list[str] = []

    for line in text.splitlines():
        m = HEADER_RE.match(line)
        if m:
            if current is not None:
                current.body = "\n".join(body_lines).strip()
                entries.append(current)
            current = LogEntry(
                date=m.group(1),
                operation=m.group(2),
                title=m.group(3),
            )
            body_lines = []
        elif current is not None:
            body_lines.append(line)
    if current is not None:
        current.body = "\n".join(body_lines).strip()
        entries.append(current)

    return entries


def _parse_iso_date(raw: str) -> Optional[dt.date]:
    try:
        return dt.date.fromisoformat(raw)
    except ValueError:
        return None


def filter_entries(
    entries: list[LogEntry],
    *,
    op: Optional[str],
    since: Optional[str],
    until: Optional[str],
    tail: Optional[int],
) -> list[LogEntry]:
    out = list(entries)

    if op:
        op_lower = op.lower()
        out = [e for e in out if e.operation.lower() == op_lower]

    if since:
        since_d = _parse_iso_date(since)
        if since_d is not None:
            out = [e for e in out if _parse_iso_date(e.date) and _parse_iso_date(e.date) >= since_d]  # type: ignore[operator]

    if until:
        until_d = _parse_iso_date(until)
        if until_d is not None:
            out = [e for e in out if _parse_iso_date(e.date) and _parse_iso_date(e.date) <= until_d]  # type: ignore[operator]

    if tail is not None and tail > 0:
        out = out[-tail:]

    return out


def read_log(wiki_path: Path, **filters) -> LogReport:
    log_file = wiki_path / "log.md"
    report = LogReport(
        wiki_path=str(wiki_path),
        log_file=str(log_file),
        total_entries=0,
        returned_entries=0,
    )
    if not wiki_path.exists() or not wiki_path.is_dir():
        report.error = f"wiki path does not exist or is not a directory: {wiki_path}"
        return report
    if not log_file.exists():
        report.error = (
            f"no log.md found at {log_file}. Is this a wiki? "
            "Run wiki_init.py to create one."
        )
        return report

    try:
        text = log_file.read_text(encoding="utf-8", errors="replace")
    except OSError as e:
        report.error = f"failed to read log.md: {e}"
        return report

    all_entries = parse_log(text)
    report.total_entries = len(all_entries)

    filtered = filter_entries(all_entries, **filters)
    report.entries = filtered
    report.returned_entries = len(filtered)
    return report


def render_text(report: LogReport) -> str:
    out: list[str] = []
    if report.error:
        return f"error: {report.error}"

    out.append(f"# wiki_log — {report.log_file}")
    out.append(
        f"{report.returned_entries} of {report.total_entries} entries shown"
    )
    out.append("")

    if not report.entries:
        out.append("(no entries match these filters)")
        return "\n".join(out)

    for e in report.entries:
        out.append(f"## [{e.date}] {e.operation}: {e.title}")
        if e.body:
            out.append(e.body)
        out.append("")
    return "\n".join(out).rstrip()


def render_json(report: LogReport) -> str:
    return json.dumps(asdict(report), ensure_ascii=False, indent=2)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="wiki_log.py",
        description="Read and filter an LLM wiki's append-only log.md.",
    )
    p.add_argument("wiki_path", help="Path to the wiki folder (contains log.md).")
    p.add_argument("--tail", type=int, default=None,
                   help="Show only the last N entries (after other filters).")
    p.add_argument("--op", default=None,
                   help="Filter by operation (e.g. 'ingest', 'query', 'lint', 'init').")
    p.add_argument("--since", default=None,
                   help="Only entries on or after this date (YYYY-MM-DD).")
    p.add_argument("--until", default=None,
                   help="Only entries on or before this date (YYYY-MM-DD).")
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

    report = read_log(
        wiki_path,
        op=args.op,
        since=args.since,
        until=args.until,
        tail=args.tail,
    )

    if args.format == "json":
        print(render_json(report))
    else:
        print(render_text(report))

    return 0 if report.error is None else 2


if __name__ == "__main__":
    sys.exit(main())
