# xlsx-reader

> Extract Excel (`.xlsx`) content as GitHub-flavored markdown tables.

`xlsx-reader` is one of four readers in the [`document-readers`](../../.claude-plugin/marketplace.json) plugin. Give it an `.xlsx` file and it renders every sheet (or just the one you pick with `--sheet`) as a `| col1 | col2 |` markdown table, so the LLM can reason about rows, columns, and totals directly.

Pair it with [`document-search`](../document-search/) for the full **文書工作 (office workflow)** loop: search first, then read.

---

## Requirements

- **Python 3.8+**
- **`openpyxl`** — `pip install openpyxl`

If `openpyxl` is missing, the skill doesn't crash — it prints a bilingual install guide with the exact `pip` command and `HTTPS_PROXY` instructions, then exits with code 2.

---

## Installation

### Easiest — one-file installer

```bash
# macOS / Linux
curl -fsSLO https://raw.githubusercontent.com/bwinken/skills/main/install.py
python install.py            # interactive wizard

# Windows (PowerShell)
iwr https://raw.githubusercontent.com/bwinken/skills/main/install.py -OutFile install.py
python install.py
```

Non-interactive:

```bash
python install.py install xlsx-reader --agent claude
```

### Claude Code — plugin marketplace

Install the whole `document-readers` suite:

```text
/plugin marketplace add bwinken/skills
/plugin install document-readers@skills
```

Or just this one:

```text
/plugin install xlsx-reader@skills
```

### Manual install

| Agent | Global | Workspace |
|-------|--------|-----------|
| Claude Code | `~/.claude/skills/xlsx-reader/` | `./.claude/skills/xlsx-reader/` |
| Roo Code | `~/.roo/skills/xlsx-reader/` | `./.roo/skills/xlsx-reader/` |
| Cline | `~/.cline/skills/xlsx-reader/` | `./.cline/skills/xlsx-reader/` |

---

## Usage

### Quick examples

Read every sheet:

```bash
python3 scripts/xlsx_reader.py ./budget.xlsx
```

Read just one sheet:

```bash
python3 scripts/xlsx_reader.py ./budget.xlsx --sheet "Q4 Summary"
```

Describe the workbook:

```bash
python3 scripts/xlsx_reader.py ./budget.xlsx --metadata-only
```

### Full option list

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.xlsx` file |
| `--sheet NAME` | all | Sheet name to extract |
| `--max-bytes N` | `200000` | Max bytes of rendered content returned |
| `--metadata-only` | off | Metadata only, no content |
| `--format` | `text` | `text` or `json` |

---

## Output format

### Text mode

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

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | File read successfully |
| `2` | File not found, read error, or missing `openpyxl` |

---

## Notes

- **Formulas**: xlsx-reader reads **cached values** (what Excel last saved). If you need to recompute a model you'll need a separate tool.
- **Empty columns**: trailing fully-empty columns are trimmed so the rendered table doesn't get ridiculous widths.
- **Read-only**: the workbook is opened with `read_only=True` so huge files stream efficiently.

---

## See also

- [SKILL.md](SKILL.md) — agent-facing skill definition
- [document-search](../document-search/) — find which spreadsheet mentions a keyword
- Sibling readers: [pdf-reader](../pdf-reader/), [docx-reader](../docx-reader/), [pptx-reader](../pptx-reader/)
- [Root README](../../README.md)
