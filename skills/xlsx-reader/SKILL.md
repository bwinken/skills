---
name: xlsx-reader
description: "Extract the content of an Excel (.xlsx) file, rendered as GitHub-flavored markdown tables (one per sheet). Optionally scope to a single sheet by name. Use whenever the user asks to read / show / summarize / query an .xlsx spreadsheet."
compatibility: "Claude Code, Roo Code, Cline"
---

# XLSX Reader

## Overview

`xlsx-reader` turns an Excel workbook into markdown tables the LLM can actually reason about. Each sheet is rendered as a GitHub-flavored `| col1 | col2 |` table, so the agent can read the header row, spot totals, compare rows, or quote a specific cell — without needing a spreadsheet-aware tool.

One of the four readers in the **`document-readers`** plugin. Companion to the [`document-search`](../document-search/) skill: use document-search to find *which* spreadsheet mentions your keyword, then xlsx-reader to actually read it.

## When to use

Fire this skill when the user asks, in any phrasing:

- **"What's in this Excel file?"** / **"Read `budget.xlsx`."**
- **"Show me the Q4 Summary sheet of this workbook."**
- **"What are the totals in the revenue spreadsheet?"**
- **"List the rows in the 'Customers' sheet."**
- Any question that requires the **content of a specific `.xlsx` file**.

## When NOT to use

- The user wants to search a *folder* of spreadsheets (plus other formats) — use [`document-search`](../document-search/).
- The file is a `.pdf` / `.docx` / `.pptx` — use the corresponding reader.
- You need to **compute** a formula-driven result precisely (e.g. "recompute the model and tell me the new total") — this skill reads cached values, not live formulas. For pure value extraction on a saved file it's fine.
- You need to **write** to the spreadsheet — this skill is read-only.

## Usage

> **How to invoke this skill** — read this **before running any example below**.
>
> 1. **Use the absolute path.** Your working directory is the user's
>    workspace, not the skill folder. `python scripts/...` (relative) will
>    fail — the scripts live inside this skill's own folder. Substitute the
>    real install location wherever you see `~/.claude/skills/xlsx-reader/`:
>
>    | Agent       | Global                          | Workspace                                |
>    |-------------|---------------------------------|------------------------------------------|
>    | Claude Code | `~/.claude/skills/xlsx-reader/`      | `<cwd>/.claude/skills/xlsx-reader/`           |
>    | Roo Code    | `~/.roo/skills/xlsx-reader/`         | `<cwd>/.roo/skills/xlsx-reader/`              |
>    | Cline       | `~/.cline/skills/xlsx-reader/`       | `<cwd>/.cline/skills/xlsx-reader/`            |
>
>    The real path is wherever **this SKILL.md** is loaded from.
>
> 2. **Pick the right Python command.** The examples below use `python` —
>    which is what Windows installs. On macOS / Linux where only `python3`
>    exists, substitute `python3`. On Windows you can also use `py -3`.

Read the whole workbook (every sheet):

```bash
python ~/.claude/skills/xlsx-reader/scripts/xlsx_reader.py ./budget.xlsx
```

Read just one sheet:

```bash
python ~/.claude/skills/xlsx-reader/scripts/xlsx_reader.py ./budget.xlsx --sheet "Q4 Summary"
```

Describe the workbook (sheet names, size) without dumping content:

```bash
python ~/.claude/skills/xlsx-reader/scripts/xlsx_reader.py ./budget.xlsx --metadata-only
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.xlsx` file |
| `--sheet NAME` | all | Sheet name to extract (default: all sheets) |
| `--max-bytes N` | `200000` | Max bytes of rendered content returned |
| `--metadata-only` | off | Return metadata (sheet names) only, no content |
| `--format` | `text` | `text` or `json` |

**Exit code:** `0` on success, `2` on missing file / read error / missing `openpyxl`.

## Output format

### Text mode (default)

```text
# xlsx-reader
path:      /home/alice/budget.xlsx
size:      18432 bytes
metadata:
  sheets: ['Q3 Summary', 'Q4 Summary', 'Annual']
  sheets_returned: ['Q4 Summary']

## Content
--- Sheet: Q4 Summary ---
| Month | Revenue | Expenses | Profit |
| --- | --- | --- | --- |
| Oct | 12000 | 8000 | 4000 |
| Nov | 14500 | 8500 | 6000 |
| Dec | 18000 | 9200 | 8800 |
```

### JSON mode

```json
{
  "path": "/home/alice/budget.xlsx",
  "extension": ".xlsx",
  "kind": "xlsx",
  "size": 18432,
  "content": "--- Sheet: Q4 Summary ---\n| Month | ...",
  "truncated": false,
  "metadata": {
    "sheets": ["Q3 Summary", "Q4 Summary", "Annual"],
    "sheets_returned": ["Q4 Summary"]
  },
  "error": null,
  "missing_imports": [],
  "install_guide": null
}
```

## Requirements

- Python 3.8+
- `openpyxl` — lazy-loaded; the skill prints a bilingual install guide and exits with code 2 if missing

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.
