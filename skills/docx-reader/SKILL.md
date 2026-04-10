---
name: docx-reader
description: "Extract the text content of a Word (.docx) file, including paragraphs and tables. Use whenever the user asks to read / show / summarize / quote a .docx document."
compatibility: "Claude Code, Roo Code, Cline"
---

# DOCX Reader

## Overview

`docx-reader` extracts plain text from a Microsoft Word (`.docx`) file — all paragraphs **and** all table cells (rendered inline as `cell | cell | cell`), so an agent can read specs, contracts, meeting notes, or any other Word document as easily as a `.txt` file.

One of the four readers in the **`document-readers`** plugin. Companion to the [`document-search`](../document-search/) skill: use document-search to find *which* Word doc mentions your keyword, then docx-reader to actually read it.

## When to use

Fire this skill when the user asks, in any phrasing:

- **"What's in this Word doc?"** / **"Read this `.docx`."**
- **"Show me the contract at `contract.docx`."**
- **"Summarize the spec in `design.docx`."**
- **"Quote the 'acceptance criteria' section from the spec doc."**
- Any question that requires the **text content of a specific `.docx` file**.

## When NOT to use

- The user wants to search a *folder* of Word docs (plus other formats) — use [`document-search`](../document-search/) instead.
- The file is a `.pdf` / `.xlsx` / `.pptx` — use the corresponding reader.
- You need to *edit* the document — this skill is read-only.
- You need layout fidelity (fonts, colors, styles) — this skill only returns plain text.

## Usage

Read the whole document:

```bash
python3 scripts/docx_reader.py ./spec.docx
```

Describe the file (paragraph + table counts) without dumping content:

```bash
python3 scripts/docx_reader.py ./spec.docx --metadata-only
```

JSON for pipelines:

```bash
python3 scripts/docx_reader.py ./spec.docx --format json
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.docx` file |
| `--max-bytes N` | `200000` | Max bytes of rendered content returned |
| `--metadata-only` | off | Return metadata only, no content |
| `--format` | `text` | `text` or `json` |

**Exit code:** `0` on success, `2` on missing file / read error / missing `python-docx`.

## Output format

### Text mode (default)

```text
# docx-reader
path:      /home/alice/spec.docx
size:      45128 bytes
metadata:
  paragraphs: 87
  tables: 3

## Content
Project Kickoff — Q4 2025
This document describes the scope, milestones, and acceptance criteria ...
...
Role | Owner | Deadline
Lead | Alice | 2026-01-15
QA   | Bob   | 2026-02-01
```

Tables are flattened to `cell | cell | cell` rows so the LLM can still read them without needing a table renderer.

### JSON mode

```json
{
  "path": "/home/alice/spec.docx",
  "extension": ".docx",
  "kind": "docx",
  "size": 45128,
  "content": "Project Kickoff — Q4 2025\n...",
  "truncated": false,
  "metadata": {
    "paragraphs": 87,
    "tables": 3
  },
  "error": null,
  "missing_imports": [],
  "install_guide": null
}
```

## Requirements

- Python **3.8+**
- **`python-docx`** — `pip install python-docx`. If missing, the skill prints a bilingual (English / 中文) install guide with `HTTPS_PROXY` instructions and exits with code 2.

## Integration

All three supported agents (Claude Code, Roo Code, Cline) natively auto-discover this skill from their standard folders.

### One-file installer

```bash
curl -fsSLO https://raw.githubusercontent.com/bwinken/skills/main/install.py
python install.py                                    # interactive wizard
python install.py install docx-reader --agent claude
```

### Claude Code — plugin marketplace

Install the whole `document-readers` suite:

```text
/plugin marketplace add bwinken/skills
/plugin install document-readers@skills
```

Or just this one:

```text
/plugin install docx-reader@skills
```

### Manual install

| Agent | Global | Workspace |
|-------|--------|-----------|
| Claude Code | `~/.claude/skills/docx-reader/` | `./.claude/skills/docx-reader/` |
| Roo Code | `~/.roo/skills/docx-reader/` | `./.roo/skills/docx-reader/` |
| Cline | `~/.cline/skills/docx-reader/` | `./.cline/skills/docx-reader/` |
