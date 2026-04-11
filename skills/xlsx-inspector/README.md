# xlsx-inspector

> Structural inspection of a single Excel workbook — properties, per-sheet dimensions, formula dependency graph, and named-range inventory. Returns the deterministic facts an LLM cannot derive from a rendered table view.

[`xlsx-reader`](../xlsx-reader/) renders each sheet as a Markdown table — great for reading cell values, useless for understanding how the workbook is *wired*. This skill returns the wiring: which cells contain formulas, which ranges those formulas reference, which references cross sheet boundaries, which named ranges exist, and all the standard workbook properties and per-sheet dimensions that rendered tables hide.

One of three sibling skills in the **`document-inspector`** plugin:

- [`pdf-inspector`](../pdf-inspector/) — `.pdf` files
- [`docx-inspector`](../docx-inspector/) — `.docx` files
- `xlsx-inspector` — `.xlsx` files (this skill)

---

## Requirements

- **Python 3.8+**
- **`openpyxl`** — lazy-loaded. Skill prints a bilingual install guide on first use if missing.

Install:

```bash
pip install openpyxl
```

---

## Installation

### Claude Code — plugin marketplace

```text
/plugin marketplace add bwinken/skills
/plugin install document-inspector@skills
```

The `document-inspector` plugin bundles `xlsx-inspector` with `pdf-inspector` and `docx-inspector`. Install the plugin once and get all three.

### Other agents — install.py wizard

```bash
python install.py install xlsx-inspector --agent claude   # or roo, cline
```

### Manual install

Copy this folder into the right directory for your agent:

- **Claude Code**: `~/.claude/skills/xlsx-inspector/` (global) or `./.claude/skills/xlsx-inspector/` (workspace)
- **Roo Code**: `~/.roo/skills/xlsx-inspector/` or `./.roo/skills/xlsx-inspector/`
- **Cline**: `~/.cline/skills/xlsx-inspector/` or `./.cline/skills/xlsx-inspector/`

---

## Usage

### Basic — full inspection

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx
```

Reports metadata, formula graph, and named ranges.

### Metadata only

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx --feature metadata
```

### Formula graph only

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx --feature formulas
```

### Named ranges only

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx --feature named-ranges
```

### JSON output

```bash
python3 scripts/xlsx_inspector.py ./budget.xlsx --format json | jq '.formulas.dependents_by_sheet'
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.xlsx` file |
| `--feature` | `all` | `metadata`, `formulas`, `named-ranges`, or `all` |
| `--format` | `text` | `text` or `json` |

---

## Output format

### Text — metadata

```text
# xlsx-inspector
path:      /home/alice/budget.xlsx
size:      18420 bytes
kind:      xlsx
feature:   metadata

## Metadata
  title: 2026 Budget
  creator: Alice Chen
  created: 2026-01-02T09:00:00
  modified: 2026-04-01T14:22:00
  sheet_count: 4

  sheets:
    - Data: dim=A1:F100, rows=100, cols=6, cells=582, merged=0
    - Summary: dim=A1:D20, rows=20, cols=4, cells=68, merged=2
```

### Text — formulas

```text
## Formulas
  formula_cell_count:          34
  cross_sheet_reference_count: 18
  unique_referenced_sheets:    Assumptions, Data
  dependents_by_sheet:
    Data: 0
    Summary: 28

  sample_formulas:
    Summary!B2: =SUM(Data!A2:A101)
      refs: Data!A2:A101
    Summary!C2: =B2*Assumptions!B1
      refs: Assumptions!B1, B2
```

### Text — named ranges

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
    "sheet_count": 4,
    "sheets": [
      {"name": "Data", "dimensions": "A1:F100", "data_cell_count": 582}
    ]
  },
  "formulas": {
    "formula_cell_count": 34,
    "cross_sheet_reference_count": 18,
    "dependents_by_sheet": {"Data": 0, "Summary": 28},
    "sample_formulas": [
      {
        "cell": "Summary!B2",
        "formula": "=SUM(Data!A2:A101)",
        "references": [{"sheet": "Data", "range": "A2:A101"}],
        "cross_sheet": true
      }
    ]
  },
  "named_ranges": [
    {"name": "grand_total", "value": "Summary!$D$20", "scope": "workbook"}
  ]
}
```

---

## Examples

### Example 1 — how does this workbook flow data?

```bash
python3 scripts/xlsx_inspector.py budget.xlsx --feature formulas
```

Returns `dependents_by_sheet` so you can see at a glance which sheets contain formulas (the "downstream" sheets) and `unique_referenced_sheets` so you can see which ones are data sources. If `Summary` has 28 formulas and `Data` has 0, you know `Data` is the input and `Summary` is computed from it.

### Example 2 — what does `Summary!B2` depend on?

```bash
python3 scripts/xlsx_inspector.py budget.xlsx --feature formulas --format json \
  | jq '.formulas.sample_formulas[] | select(.cell == "Summary!B2")'
```

Returns the formula string, its extracted references, and the `cross_sheet` flag.

### Example 3 — are there any named ranges I missed?

```bash
python3 scripts/xlsx_inspector.py budget.xlsx --feature named-ranges
```

Returns every defined name with its reference and scope (workbook-wide vs local to a specific sheet).

---

## How it works

1. Load the workbook with [`openpyxl`](https://openpyxl.readthedocs.io/) using `data_only=False` (preserves formula strings), `read_only=False` (full `defined_names` access), and `keep_links=False` (skips external workbook links).
2. **Metadata**: pull `wb.properties` for the standard OOXML properties, then iterate `wb.sheetnames` to collect per-sheet dimensions, cell counts, and merged-range counts.
3. **Formulas**: walk every cell in every sheet, filter for `cell.data_type == "f"`, and extract references with a **best-effort regex** (not a full parser):
   - Cross-sheet refs (`'Sheet Name'!A1:B5`, `Data!A1`) are matched first
   - After stripping those, local refs (`A1`, `$B$2`, `A1:C10`) are matched with word boundaries to avoid colliding with function names
   - Each formula cell is recorded with its references and a `cross_sheet` flag
4. **Named ranges**: iterate `wb.defined_names` (with a fallback for older openpyxl versions that expose `defined_names.definedName` instead). Each name's `localSheetId` resolves to a scope — `workbook` if None, sheet name otherwise.

### Tradeoffs of the regex formula parser

The regex approach:

- **Handles well**: simple cell refs, ranges, quoted/unquoted sheet prefixes, mixed local and cross-sheet refs, quoted string literals (stripped first)
- **Is best-effort for**: `INDIRECT()`, `OFFSET()`, structured references, whole-column refs (`A:A`), 3D refs
- **Doesn't do**: computed values, name resolution, dependency chain walking, cycle detection

For use cases that need any of those, use a proper Excel evaluator like [`formulas`](https://pypi.org/project/formulas/). This skill is a cheap structural view, not a full dependency engine.

### Caps

- Sample formulas capped at 50 (`truncated` flag signals overflow; the total count is always accurate)
- Named ranges capped at 100 in text output (JSON has all)

---

## See also

- [SKILL.md](SKILL.md) — agent-facing definition
- [xlsx-reader](../xlsx-reader/) — when you want the *values* in a workbook
- [pdf-inspector](../pdf-inspector/) — the `.pdf` sibling
- [docx-inspector](../docx-inspector/) — the `.docx` sibling
- [ROADMAP.md §1](../../ROADMAP.md) — design notes for the document-inspector plugin
