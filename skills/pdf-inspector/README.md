# pdf-inspector

> Structural inspection of a single PDF — metadata and form-field inventory. Returns the deterministic facts an LLM cannot derive from extracted text.

[`pdf-reader`](../pdf-reader/) returns the *text* of a PDF. This skill returns its *structure*: the things an LLM cannot reliably see from extracted text — `/Info` dictionary metadata (author, dates, creator, producer), document-catalog facts (page count, encryption, page dimensions, PDF version), and the full AcroForm field inventory (types, values, required/read-only flags, best-effort page numbers for each field).

One of three sibling skills in the **`document-inspector`** plugin:

- `pdf-inspector` — `.pdf` files (this skill)
- [`docx-inspector`](../docx-inspector/) — `.docx` files
- [`xlsx-inspector`](../xlsx-inspector/) — `.xlsx` files

---

## Requirements

- **Python 3.8+**
- **`pypdf`** — lazy-loaded. Skill prints a bilingual install guide on first use if missing.

Install:

```bash
pip install pypdf
```

---

## Installation

### Claude Code — plugin marketplace

```text
/plugin marketplace add bwinken/skills
/plugin install document-inspector@skills
```

The `document-inspector` plugin bundles `pdf-inspector` with `docx-inspector` and `xlsx-inspector`. Install the plugin once and get all three.

### Other agents — install.py wizard

```bash
python install.py install pdf-inspector --agent claude   # or roo, cline
```

### Manual install

Copy this folder into the right directory for your agent:

- **Claude Code**: `~/.claude/skills/pdf-inspector/` (global) or `./.claude/skills/pdf-inspector/` (workspace)
- **Roo Code**: `~/.roo/skills/pdf-inspector/` or `./.roo/skills/pdf-inspector/`
- **Cline**: `~/.cline/skills/pdf-inspector/` or `./.cline/skills/pdf-inspector/`

---

## Usage

### Basic — full inspection

```bash
python3 scripts/pdf_inspector.py ./report.pdf
```

Reports metadata and form inventory.

### Metadata only

```bash
python3 scripts/pdf_inspector.py ./report.pdf --feature metadata
```

### Form inventory only

```bash
python3 scripts/pdf_inspector.py ./form.pdf --feature forms
```

### JSON output

```bash
python3 scripts/pdf_inspector.py ./report.pdf --format json | jq '.metadata'
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.pdf` file |
| `--feature` | `all` | `metadata`, `forms`, or `all` |
| `--format` | `text` | `text` or `json` |

---

## Output format

### Text — metadata

```text
# pdf-inspector
path:      /home/alice/report.pdf
size:      284571 bytes
kind:      pdf
feature:   metadata

## Metadata
  title: Q4 2025 Revenue Report
  author: Alice Chen
  creationdate: 2026-01-05T14:22:10
  total_pages: 42
  encrypted: False
  pdf_version: %PDF-1.7
  first_page_size:
    width: 612.0
    height: 792.0
    unit: points
```

### Text — forms

```text
## Forms
  field_count: 8
  signatures:  1

  fields:
    [text] full_name (page 1) [required] = 'Bob Smith'
    [button] agree_tos (page 1) [required]
    [signature] signer_1 (page 2) [required]
```

### JSON mode

```json
{
  "path": "/home/alice/report.pdf",
  "kind": "pdf",
  "feature": "all",
  "metadata": {
    "title": "Q4 2025 Revenue Report",
    "author": "Alice Chen",
    "total_pages": 42,
    "encrypted": false
  },
  "forms": {
    "has_form": true,
    "field_count": 8,
    "signatures": 1,
    "fields": [
      {"name": "full_name", "field_type_label": "text", "required": true, "page": 1}
    ]
  }
}
```

---

## Field type reference

| PDF type | Label | Meaning |
|----------|-------|---------|
| `/Tx`  | `text`      | Free-text input |
| `/Btn` | `button`    | Checkbox / radio / pushbutton |
| `/Ch`  | `choice`    | Combo box / list box |
| `/Sig` | `signature` | Digital signature field |

Field flag bits surfaced by the skill:

- `required` — bit 2 (field is required on submit)
- `read_only` — bit 1 (field cannot be edited)

---

## Examples

### Example 1 — who authored this PDF and when?

```bash
python3 scripts/pdf_inspector.py contract.pdf --feature metadata
```

Returns the `/Info` dictionary: title, author, subject, keywords, creator, producer, creation/modification dates (parsed to ISO-8601).

### Example 2 — is this a fillable form?

```bash
python3 scripts/pdf_inspector.py onboarding.pdf --feature forms
```

Returns `has_form`, a field count, a signature count, and a full inventory with type labels, current values, required/read-only flags, and (best-effort) page numbers.

### Example 3 — machine-readable report

```bash
python3 scripts/pdf_inspector.py contract.pdf --format json > report.json
```

Emit the full result as JSON so a downstream tool (or the agent) can reason about it programmatically.

---

## How it works

1. Open the PDF with [`pypdf`](https://pypdf.readthedocs.io/).
2. **Metadata**: pull the `/Info` dictionary (title, author, dates, creator, producer, trapped), plus structural facts from the document catalog (page count, encryption, first page MediaBox, PDF version). PDF date strings like `D:20251231140530+00'00'` are parsed to ISO-8601 best-effort; unparseable values are passed through unchanged so nothing is silently dropped.
3. **Forms**: call `reader.get_fields()` to walk the AcroForm. Each field is reported with its PDF type (`/Tx` / `/Btn` / `/Ch` / `/Sig`), a human-readable label, current value, the `required` / `read_only` flag bits, and a best-effort page number derived from the widget annotations on each page.

All work is read-only. Errors (missing file, broken PDF, missing package, wrong extension) produce a structured error record and exit code 2, never a stack trace in the user's face.

---

## See also

- [SKILL.md](SKILL.md) — agent-facing definition
- [pdf-reader](../pdf-reader/) — when you want the *text* of a PDF
- [docx-inspector](../docx-inspector/) — the .docx sibling
- [xlsx-inspector](../xlsx-inspector/) — the .xlsx sibling
- [ROADMAP.md](../../ROADMAP.md) — design notes for the document-inspector plugin
