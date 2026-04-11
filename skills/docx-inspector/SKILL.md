---
name: docx-inspector
description: "Structural inspection of a single Word (.docx) file — returns core document properties (title/author/dates/revision/word count), tracked changes (every w:ins / w:del with author, timestamp, and text), and heading-hierarchy outline with skipped-level detection. Use whenever the user asks about a .docx file's author, creation date, tracked changes, revision history, who changed what, heading structure, or document outline — not its rendered text. One of three sibling skills in the `document-inspector` plugin (pdf-inspector / docx-inspector / xlsx-inspector)."
compatibility: "Claude Code, Roo Code, Cline"
---

# DOCX Inspector

## Overview

`docx-inspector` returns **structure**, not **text**. [`docx-reader`](../docx-reader/) extracts the content an LLM can then summarize; this skill extracts the things an LLM *cannot* see from rendered text:

- **Core properties** — title, author, dates, revision number, last-modified-by, plus computed counts (paragraphs, words, tables, sections)
- **Tracked changes** — every `w:ins` / `w:del` XML element walked directly from the lxml tree (python-docx doesn't expose these through its high-level API), with author, timestamp, change ID, and the actual inserted/deleted text
- **Heading hierarchy** — document outline from `Heading N` styles, with automatic detection of skipped levels (e.g. H1 → H3 with no H2 between) and documents that don't start at H1

One of three sibling skills in the **`document-inspector`** plugin:

- [`pdf-inspector`](../pdf-inspector/) — `.pdf` files (metadata + AcroForm fields)
- `docx-inspector` — `.docx` files (this skill)
- [`xlsx-inspector`](../xlsx-inspector/) — `.xlsx` files (metadata + formula graph + named ranges)

## When to use

Fire this skill when the user asks, in any phrasing:

- **"Who authored this document? When was it last modified?"**
- **"How many words / paragraphs / tables does this document have?"**
- **"List the tracked changes in this document."** / **"Who edited this and what did they change?"**
- **"Show me the revision history."** / **"Are there any unaccepted changes?"**
- **"What's the heading structure of this document?"** / **"Give me the outline."**
- **"Is the heading hierarchy consistent?"** / **"Does this doc skip heading levels?"**
- Any question about a Word document's **properties, edit history, or outline structure** (not its rendered body text).

## When NOT to use

- The user wants the **text content** of the document — use [`docx-reader`](../docx-reader/) instead.
- The user wants to **search a folder** of documents — use [`document-search`](../document-search/).
- The file is `.pdf` — use [`pdf-inspector`](../pdf-inspector/).
- The file is `.xlsx` — use [`xlsx-inspector`](../xlsx-inspector/).
- The file is legacy `.doc` (binary format, not OOXML) — python-docx does not support it and neither does this skill.
- You need to **modify** the document — this skill is strictly read-only.

## Usage

Full inspection (default: metadata + changes + structure):

```bash
python3 scripts/docx_inspector.py ./contract.docx
```

Metadata only:

```bash
python3 scripts/docx_inspector.py ./contract.docx --feature metadata
```

Tracked changes only:

```bash
python3 scripts/docx_inspector.py ./contract.docx --feature changes
```

Heading hierarchy only:

```bash
python3 scripts/docx_inspector.py ./contract.docx --feature structure
```

JSON output for pipelines:

```bash
python3 scripts/docx_inspector.py ./contract.docx --format json | jq '.changes'
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.docx` file |
| `--feature` | `all` | `metadata`, `changes`, `structure`, or `all` |
| `--format` | `text` | Output format (`text` or `json`) |

**Exit code:** `0` on success, `2` on missing file / read error / missing `python-docx` / wrong extension.

## Output format

### Text mode — metadata

```text
# docx-inspector
path:      /home/alice/contract.docx
size:      28412 bytes
kind:      docx
feature:   metadata

## Metadata
  title: Master Service Agreement
  author: Alice Chen
  subject: Legal / procurement
  keywords: msa, vendor, 2026
  category: contracts
  created: 2026-01-12T09:22:00+00:00
  modified: 2026-03-04T14:08:00+00:00
  last_modified_by: Bob Smith
  revision: 17
  paragraph_count: 142
  word_count: 6284
  table_count: 4
  section_count: 3
```

### Text mode — tracked changes

```text
## Tracked changes
  insertion_count: 12
  deletion_count:  8
  authors: Alice Chen, Bob Smith, Carol Lee

  changes:
    [insert] Bob Smith @ 2026-03-04T10:15:00Z: 'must be delivered within 30 days of'
    [delete] Bob Smith @ 2026-03-04T10:15:00Z: 'upon signing'
    [insert] Carol Lee @ 2026-03-04T11:02:00Z: ', excluding weekends and holidays'
```

### Text mode — structure

```text
## Structure
  heading_count: 18
  max_depth:     3
  hierarchy_issues: 1
    - index 32: skipped from H1 to H3 (missing H2)
      text: 'Indemnification Terms'

  outline:
      H1: Preamble
        H2: Definitions
        H2: Scope of Work
          H3: Deliverables
      H1: Indemnification
            H3: Indemnification Terms    ← flagged
```

### JSON mode

```json
{
  "path": "/home/alice/contract.docx",
  "kind": "docx",
  "feature": "all",
  "metadata": {
    "title": "Master Service Agreement",
    "author": "Alice Chen",
    "revision": "17",
    "word_count": 6284
  },
  "changes": {
    "has_tracked_changes": true,
    "insertion_count": 12,
    "deletion_count": 8,
    "authors": ["Alice Chen", "Bob Smith", "Carol Lee"],
    "changes": [
      {
        "type": "insert",
        "author": "Bob Smith",
        "date": "2026-03-04T10:15:00Z",
        "text": "must be delivered within 30 days of",
        "id": "42"
      }
    ],
    "truncated": false
  },
  "structure": {
    "heading_count": 18,
    "max_depth": 3,
    "outline": [
      {"level": 1, "text": "Preamble", "index": 0}
    ],
    "hierarchy_issues": [
      {
        "index": 32,
        "text": "Indemnification Terms",
        "level": 3,
        "previous_level": 1,
        "issue": "skipped from H1 to H3 (missing H2)"
      }
    ]
  }
}
```

## How it works

- **Metadata** uses python-docx's `doc.core_properties` for the core fields, plus computed counts from `doc.paragraphs`, `doc.tables`, and `doc.sections`.
- **Tracked changes** walks the raw lxml tree (`doc.element`) with the `w:` namespace and collects every `w:ins` (insertion) and `w:del` (deletion) element. Inserted text lives in `w:t` descendants; deleted text lives in `w:delText` descendants. Author, date, and change ID come from the `w:author` / `w:date` / `w:id` attributes. python-docx does **not** expose tracked changes through its high-level API — this raw-XML walk is the only way.
- **Structure** scans `doc.paragraphs` for any paragraph whose style name starts with `"Heading "`, extracts the level number, and walks the list to flag hierarchy issues (skipped levels downward, first heading not H1).

## Caps and truncation

- Tracked changes are capped at **200 entries** (the `truncated` field signals when more existed).
- Each change's text is capped at **200 characters** with an ellipsis.
- The outline is capped at **200 headings**.
- All caps are visible in the JSON output so the agent can request another pass with a different feature focus if needed.

## Requirements

- Python 3.8+
- `python-docx` (import name `docx`) — lazy-loaded; the skill prints a bilingual install guide and exits with code 2 if missing.

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.
