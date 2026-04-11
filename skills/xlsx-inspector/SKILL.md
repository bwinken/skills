---
name: xlsx-inspector
description: "Structural inspection of a single Excel (.xlsx) workbook — returns workbook properties (title/creator/dates), per-sheet dimensions and cell counts, formula dependency graph (which cells reference which, including cross-sheet references), and named-range inventory with scope. Use whenever the user asks about a workbook's author, how many sheets, which formulas cross sheets, what named ranges exist, or how one sheet depends on another — not its rendered cell values. One of three sibling skills in the `document-inspector` plugin (pdf-inspector / docx-inspector / xlsx-inspector)."
compatibility: "Claude Code, Roo Code, Cline"
---

# XLSX Inspector

## Overview

`xlsx-inspector` returns **structure**, not **rendered tables**. [`xlsx-reader`](../xlsx-reader/) dumps sheet contents as GitHub-flavored Markdown tables; this skill extracts the things an LLM *cannot* see from that table view:

- **Workbook properties** — title, creator, subject, dates, revision, last-modified-by
- **Per-sheet facts** — dimensions (`A1:F20`), row/column counts, data-cell counts, merged-range counts
- **Formula dependency graph** — every formula cell in the workbook, the references it contains (with sheet names for cross-sheet refs), per-sheet formula density, and the full list of referenced sheets
- **Named ranges** — inventory of all defined names, each with its reference string and scope (workbook-wide vs sheet-local)

One of three sibling skills in the **`document-inspector`** plugin:

- [`pdf-inspector`](../pdf-inspector/) — `.pdf` files
- [`docx-inspector`](../docx-inspector/) — `.docx` files
- `xlsx-inspector` — `.xlsx` files (this skill)

## When to use

Fire this skill when the user asks, in any phrasing:

- **"Who authored this workbook? When was it last modified?"**
- **"How many sheets does this workbook have?"** / **"What are the sheet dimensions?"**
- **"Which formulas in this workbook cross sheets?"** / **"What does Summary.B1 depend on?"**
- **"How many formulas are on each sheet?"**
- **"What named ranges exist in this workbook?"** / **"Which sheet is `grand_total` scoped to?"**
- **"This workbook has a bug — something downstream of `Data!A1:A5` is wrong. What formulas reference that range?"**
- Any question about a workbook's **properties, sheet layout, or formula topology** (not the cell values themselves).

## When NOT to use

- The user wants the **cell values** of the workbook — use [`xlsx-reader`](../xlsx-reader/) instead.
- The user wants to **search a folder** of workbooks — use [`document-search`](../document-search/).
- The file is `.pdf` — use [`pdf-inspector`](../pdf-inspector/).
- The file is `.docx` — use [`docx-inspector`](../docx-inspector/).
- The file is legacy `.xls` (binary format) — `openpyxl` doesn't support it and neither does this skill.
- You need the **computed value** of a formula — this skill loads with `data_only=False` to preserve the formula strings, so it sees `=SUM(Data!A1:A5)`, not the result. For computed values, use xlsx-reader.
- You need a **provably complete** formula parser — the formula graph is built with a regex-based reference extractor, not a full Excel expression parser. See "How it works" below for the tradeoffs.

## Usage

Full inspection (default: metadata + formulas + named-ranges):

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx
```

Metadata only:

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx --feature metadata
```

Formula graph only:

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx --feature formulas
```

Named ranges only:

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx --feature named-ranges
```

JSON output for pipelines:

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx --format json | jq '.formulas'
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.xlsx` file |
| `--feature` | `all` | `metadata`, `formulas`, `named-ranges`, or `all` |
| `--format` | `text` | Output format (`text` or `json`) |

**Exit code:** `0` on success, `2` on missing file / read error / missing `openpyxl` / wrong extension.

## Output format

### Text mode — metadata

```text
# xlsx-inspector
path:      /home/alice/budget.xlsx
size:      18420 bytes
kind:      xlsx
feature:   metadata

## Metadata
  title: 2026 Budget
  creator: Alice Chen
  subject: Finance
  created: 2026-01-02T09:00:00
  modified: 2026-04-01T14:22:00
  last_modified_by: Bob Smith
  revision: 12
  sheet_count: 4
  active_sheet_index: 0

  sheets:
    - Data: dim=A1:F100, rows=100, cols=6, cells=582, merged=0
    - Summary: dim=A1:D20, rows=20, cols=4, cells=68, merged=2
    - Charts: dim=A1:A1, rows=1, cols=1, cells=0, merged=0
    - Assumptions: dim=A1:B12, rows=12, cols=2, cells=24, merged=0
```

### Text mode — formulas

```text
## Formulas
  formula_cell_count:          34
  cross_sheet_reference_count: 18
  unique_referenced_sheets:    Assumptions, Data
  dependents_by_sheet:
    Data: 0
    Summary: 28
    Charts: 0
    Assumptions: 6

  sample_formulas:
    Summary!B2: =SUM(Data!A2:A101)
      refs: Data!A2:A101
    Summary!B3: =AVERAGE(Data!A2:A101)
      refs: Data!A2:A101
    Summary!C2: =B2*Assumptions!B1
      refs: Assumptions!B1, B2
```

### Text mode — named ranges

```text
## Named ranges
  [workbook] grand_total = Summary!$D$20
  [Summary] growth_rate = Assumptions!$B$1
```

### JSON mode

```json
{
  "path": "/home/alice/budget.xlsx",
  "kind": "xlsx",
  "feature": "all",
  "metadata": {
    "title": "2026 Budget",
    "creator": "Alice Chen",
    "sheet_count": 4,
    "sheets": [
      {"name": "Data", "max_row": 100, "max_column": 6, "dimensions": "A1:F100", "merged_cells_count": 0, "data_cell_count": 582}
    ]
  },
  "formulas": {
    "formula_cell_count": 34,
    "cross_sheet_reference_count": 18,
    "dependents_by_sheet": {"Data": 0, "Summary": 28, "Charts": 0, "Assumptions": 6},
    "unique_referenced_sheets": ["Assumptions", "Data"],
    "sample_formulas": [
      {
        "cell": "Summary!B2",
        "formula": "=SUM(Data!A2:A101)",
        "references": [{"sheet": "Data", "range": "A2:A101"}],
        "cross_sheet": true
      }
    ],
    "truncated": false
  },
  "named_ranges": [
    {"name": "grand_total", "value": "Summary!$D$20", "scope": "workbook"}
  ]
}
```

## How it works

1. Open the workbook with [`openpyxl`](https://openpyxl.readthedocs.io/) using `data_only=False` (keeps formulas as strings), `read_only=False` (gives full access to `defined_names`), and `keep_links=False` (skips resolving external workbook links).
2. **Metadata**: read `wb.properties` for the standard OOXML properties, plus iterate `wb.sheetnames` to collect per-sheet dimensions, cell counts, and merged-range counts via `ws.max_row` / `ws.dimensions` / `ws.merged_cells.ranges`.
3. **Formulas**: walk every cell in every sheet (`ws.iter_rows()`), filter for `cell.data_type == "f"`, and extract cell references from the formula string using a **best-effort regex** (not a full parser):
   - Cross-sheet refs like `'Sheet Name'!A1:B5` or `Data!A1` are matched first
   - After stripping those, local refs like `A1` / `$B$2` / `A1:C10` are matched with word boundaries to avoid colliding with function names (`SUM`, `IF`, etc.)
   - Each formula cell is recorded with its references, a `cross_sheet` flag, and its sheet/coordinate
   - Aggregate counters: `formula_cell_count`, `cross_sheet_reference_count`, `dependents_by_sheet`, `unique_referenced_sheets`
4. **Named ranges**: iterate `wb.defined_names` (tolerant of openpyxl version differences — falls back to `defined_names.definedName` on older versions), resolving each name's `localSheetId` to a scope (`workbook` if None, sheet name otherwise).

### Tradeoffs of the regex formula parser

A full Excel expression parser is a large dependency (e.g. `formulas`, `pycel`) and would violate this repo's stdlib-first principle. The regex approach:

- **Handles well**: simple cell refs (`A1`, `$A$1`), ranges (`A1:B5`), quoted and unquoted sheet prefixes, mixed local and cross-sheet refs in one formula, literal strings (stripped before matching).
- **Is best-effort for**: `INDIRECT()`, `OFFSET()`, structured references (table columns like `Table1[Column]`), whole-column refs (`A:A`), 3D refs (`Sheet1:Sheet3!A1`).
- **Doesn't**: compute values, resolve names through named ranges, follow chains of dependencies, or detect cycles.

For use cases that need any of those, the right tool is a proper evaluator like [`formulas`](https://pypi.org/project/formulas/), not this skill.

## Caps and truncation

- **Sample formulas** capped at 50 entries (the `truncated` field signals when more existed). `formula_cell_count` is always the true total; samples are just a preview.
- **Named ranges** capped at 100 in text output (JSON always includes all).

## Requirements

- Python 3.8+
- `openpyxl` — lazy-loaded; the skill prints a bilingual install guide and exits with code 2 if missing.

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.
