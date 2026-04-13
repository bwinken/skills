---
name: pdf-reader
description: "Extract the text content of a PDF file. Optionally scope to specific pages (e.g. 1-5, 7, 9-10). Use whenever the user asks to read / show / summarize / quote / search inside a .pdf document."
compatibility: "Claude Code, Roo Code, Cline"
---

# PDF Reader

## Overview

`pdf-reader` extracts plain text from a PDF file, preserving page boundaries (`--- Page N ---`) so an agent can reason about *where* something was said in the document. Optional page-range selection (`--pages 1-5,7`) lets you read just the parts you need instead of dumping a 200-page report into the context window.

One of the four readers in the **`document-readers`** plugin. Companion to the [`document-search`](../document-search/) skill: use document-search to find *which* PDF mentions your keyword, then pdf-reader to actually read it.

## When to use

Fire this skill when the user asks, in any phrasing:

- **"What's in this PDF?"** / **"Read this PDF."**
- **"Show me pages 1-5 of `report.pdf`."**
- **"Summarize the attached PDF."**
- **"Quote the section about Q4 revenue from `quarterly.pdf`."**
- **"What does the PDF say on page 42?"**
- Any question that requires the **text content of a specific `.pdf` file**.

## When NOT to use

- The user wants to search a *folder* of PDFs (plus other formats) — use [`document-search`](../document-search/) instead; it handles mixed-format folders in one pass.
- The file is a `.docx` / `.xlsx` / `.pptx` — use the corresponding reader (`docx-reader`, `xlsx-reader`, `pptx-reader`).
- The file is plain text / code — use the agent's built-in `Read` tool (it's cheaper and faster).
- You need to *modify* the PDF — this skill is read-only.

## Usage

> **How to invoke this skill** — read this **before running any example below**.
>
> 1. **Use the absolute path.** Your working directory is the user's
>    workspace, not the skill folder. `python scripts/...` (relative) will
>    fail — the scripts live inside this skill's own folder. Substitute the
>    real install location wherever you see `~/.claude/skills/pdf-reader/`:
>
>    | Agent       | Global                          | Workspace                                |
>    |-------------|---------------------------------|------------------------------------------|
>    | Claude Code | `~/.claude/skills/pdf-reader/`      | `<cwd>/.claude/skills/pdf-reader/`           |
>    | Roo Code    | `~/.roo/skills/pdf-reader/`         | `<cwd>/.roo/skills/pdf-reader/`              |
>    | Cline       | `~/.cline/skills/pdf-reader/`       | `<cwd>/.cline/skills/pdf-reader/`            |
>
>    The real path is wherever **this SKILL.md** is loaded from.
>
> 2. **Pick the right Python command.** The examples below use `python` —
>    which is what Windows installs. On macOS / Linux where only `python3`
>    exists, substitute `python3`. On Windows you can also use `py -3`.

Read an entire PDF:

```bash
python ~/.claude/skills/pdf-reader/scripts/pdf_reader.py ./report.pdf
```

Read only pages 1–5:

```bash
python ~/.claude/skills/pdf-reader/scripts/pdf_reader.py ./report.pdf --pages 1-5
```

Read pages 3, 5, 7 and 10–12:

```bash
python ~/.claude/skills/pdf-reader/scripts/pdf_reader.py ./report.pdf --pages 3,5,7,10-12
```

Just describe the file (page count, size) without dumping the content:

```bash
python ~/.claude/skills/pdf-reader/scripts/pdf_reader.py ./report.pdf --metadata-only
```

JSON output for pipelines:

```bash
python ~/.claude/skills/pdf-reader/scripts/pdf_reader.py ./report.pdf --format json | jq '.metadata'
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.pdf` file |
| `--pages N` | all | Page range (e.g. `1-5`, `3`, `1,3-4,7`) |
| `--max-bytes N` | `200000` | Max bytes of rendered content returned |
| `--metadata-only` | off | Return metadata only, no content |
| `--format` | `text` | `text` or `json` |

**Exit code:** `0` on success, `2` on missing file / read error / missing `pypdf`.

## Output format

### Text mode (default)

```text
# pdf-reader
path:      /home/alice/report.pdf
size:      2845712 bytes
metadata:
  total_pages: 42
  pages_returned: [1, 2, 3, 4, 5]

## Content
--- Page 1 ---
Quarterly revenue report — Q4 2025
...
--- Page 2 ---
...
```

### JSON mode (`--format json`)

```json
{
  "path": "/home/alice/report.pdf",
  "extension": ".pdf",
  "kind": "pdf",
  "size": 2845712,
  "content": "--- Page 1 ---\n...",
  "truncated": false,
  "metadata": {
    "total_pages": 42,
    "pages_returned": [1, 2, 3, 4, 5]
  },
  "error": null,
  "missing_imports": [],
  "install_guide": null
}
```

## Requirements

- Python 3.8+
- `pypdf` — lazy-loaded; the skill prints a bilingual install guide and exits with code 2 if missing

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.
