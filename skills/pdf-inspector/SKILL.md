---
name: pdf-inspector
description: "Structural inspection of a single PDF file — returns metadata (title/author/dates/encryption/page size/PDF version) and AcroForm field inventory (names, types, values, required/read-only flags, signature fields). Use whenever the user asks about who authored a PDF, when it was created, whether it is encrypted, what form fields it has, or whether it contains signature fields — not its rendered text. One of three sibling skills in the `document-inspector` plugin (pdf-inspector / docx-inspector / xlsx-inspector)."
compatibility: "Claude Code, Roo Code, Cline"
---

# PDF Inspector

## Overview

`pdf-inspector` returns **structure**, not **text**. [`pdf-reader`](../pdf-reader/) extracts the content an LLM can then summarize; this skill extracts the things an LLM *cannot* reliably see from extracted text: PDF metadata buried in the document catalog, the list of fillable form fields, encryption flags, page dimensions, PDF version.

One of three sibling skills in the **`document-inspector`** plugin:

- `pdf-inspector` — `.pdf` files (this skill)
- [`docx-inspector`](../docx-inspector/) — `.docx` files (metadata, tracked changes, heading structure)
- [`xlsx-inspector`](../xlsx-inspector/) — `.xlsx` files (metadata, formula dependency graph, named ranges)

Every inspector follows the ROADMAP's "LLM thinks, skill mechanics" rule: each feature produces something an LLM *cannot* trivially derive from the corresponding reader's output.

## When to use

Fire this skill when the user asks, in any phrasing:

- **"What's the metadata of this PDF?"** / **"Who authored this PDF?"**
- **"When was this PDF created / last modified?"**
- **"Is this PDF encrypted?"** / **"What's the page size?"**
- **"What forms does this PDF have?"** / **"List the fillable fields."**
- **"Is this a fillable form? What fields need to be filled?"**
- **"Are there any signature fields in this PDF?"**
- **"What are the required form fields in this PDF?"**
- Any question about a PDF's **document properties, structure, or form layout** (not its rendered text).

## When NOT to use

- The user wants the **text content** of a PDF — use [`pdf-reader`](../pdf-reader/) instead.
- The user wants to **search a folder** of PDFs — use [`document-search`](../document-search/).
- The file is `.docx` — use [`docx-inspector`](../docx-inspector/) for metadata, tracked changes, and heading structure.
- The file is `.xlsx` — use [`xlsx-inspector`](../xlsx-inspector/) for metadata, formula dependencies, and named ranges.
- The file is `.pptx` — use [`pptx-reader`](../pptx-reader/) and have the LLM summarize; there is no dedicated PowerPoint inspector.
- You need to **modify** the PDF — this skill is strictly read-only.

## Usage

Full inspection (default: both metadata and forms):

```bash
python3 scripts/pdf_inspector.py ./report.pdf
```

Metadata only:

```bash
python3 scripts/pdf_inspector.py ./report.pdf --feature metadata
```

Form inventory only:

```bash
python3 scripts/pdf_inspector.py ./form.pdf --feature forms
```

JSON output for pipelines:

```bash
python3 scripts/pdf_inspector.py ./report.pdf --format json | jq '.metadata'
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.pdf` file |
| `--feature` | `all` | `metadata`, `forms`, or `all` |
| `--format` | `text` | Output format (`text` or `json`) |

**Exit code:** `0` on success, `2` on missing file / read error / missing `pypdf` / wrong extension.

## Output format

### Text mode — metadata

```text
# pdf-inspector
path:      /home/alice/report.pdf
size:      284571 bytes
kind:      pdf
feature:   metadata

## Metadata
  title: Q4 2025 Revenue Report
  author: Alice Chen
  subject: Internal
  keywords: revenue, q4, 2025
  creator: Microsoft Word
  producer: Acrobat Distiller 11.0
  creationdate: 2026-01-05T14:22:10
  moddate: 2026-01-06T09:11:44
  trapped: (none)
  pdf_version: %PDF-1.7
  total_pages: 42
  encrypted: False
  first_page_size:
    width: 612.0
    height: 792.0
    unit: points
```

### Text mode — forms

```text
## Forms
  field_count: 8
  signatures:  1

  fields:
    [text] full_name (page 1) [required] = 'Bob Smith'
    [text] email (page 1) [required]
    [button] agree_tos (page 1) [required]
    [choice] country (page 1)
    [signature] signer_1 (page 2) [required]
```

### JSON mode

```json
{
  "path": "/home/alice/report.pdf",
  "extension": ".pdf",
  "kind": "pdf",
  "feature": "all",
  "size": 284571,
  "metadata": {
    "title": "Q4 2025 Revenue Report",
    "author": "Alice Chen",
    "creationdate": "2026-01-05T14:22:10",
    "total_pages": 42,
    "encrypted": false,
    "first_page_size": {"width": 612.0, "height": 792.0, "unit": "points"},
    "pdf_version": "%PDF-1.7"
  },
  "forms": {
    "has_form": true,
    "field_count": 8,
    "signatures": 1,
    "fields": [
      {
        "name": "full_name",
        "field_type": "/Tx",
        "field_type_label": "text",
        "value": "Bob Smith",
        "required": true,
        "read_only": false,
        "page": 1
      }
    ]
  },
  "error": null,
  "missing_imports": [],
  "install_guide": null
}
```

## Field type reference

| PDF type | Label | Meaning |
|----------|-------|---------|
| `/Tx`  | `text`      | Free-text input |
| `/Btn` | `button`    | Checkbox / radio button / pushbutton |
| `/Ch`  | `choice`    | Combo box / list box |
| `/Sig` | `signature` | Digital signature field |

Field flag bits surfaced by the skill:

- `required` — bit 2 (field is required on form submit)
- `read_only` — bit 1 (field cannot be edited)

## Requirements

- Python 3.8+
- `pypdf` — lazy-loaded; the skill prints a bilingual install guide and exits with code 2 if missing

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.
