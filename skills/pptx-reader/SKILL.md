---
name: pptx-reader
description: "Extract the text content of a PowerPoint (.pptx) file. Optionally scope to specific slides (e.g. 1-5, 7). Use whenever the user asks to read / show / summarize / quote a .pptx deck."
compatibility: "Claude Code, Roo Code, Cline"
---

# PPTX Reader

## Overview

`pptx-reader` extracts plain text from a PowerPoint deck, preserving slide boundaries (`--- Slide N ---`) so an agent can reason about *which* slide said what. Optional slide-range selection (`--slides 1-5,7`) lets you read only the slides you need.

One of the four readers in the **`document-readers`** plugin. Companion to the [`document-search`](../document-search/) skill: use document-search to find *which* deck mentions your keyword, then pptx-reader to actually read it.

## When to use

Fire this skill when the user asks, in any phrasing:

- **"What's in this deck?"** / **"Read `presentation.pptx`."**
- **"Show me slides 1-5 of the pitch deck."**
- **"Summarize this PowerPoint."**
- **"Quote the 'Roadmap' slide from `q4-strategy.pptx`."**
- Any question that requires the **text content of a specific `.pptx` file**.

## When NOT to use

- The user wants to search a *folder* of decks (plus other formats) — use [`document-search`](../document-search/).
- The file is a `.pdf` / `.docx` / `.xlsx` — use the corresponding reader.
- You need layout, colors, or slide images — this skill only returns plain text.
- You need to *edit* the deck — this skill is read-only.

## Usage

Read the whole deck:

```bash
python3 scripts/pptx_reader.py ./deck.pptx
```

Read slides 1-5:

```bash
python3 scripts/pptx_reader.py ./deck.pptx --slides 1-5
```

Read slide 3 and slides 7-10:

```bash
python3 scripts/pptx_reader.py ./deck.pptx --slides 3,7-10
```

Describe the deck (slide count, size) without dumping content:

```bash
python3 scripts/pptx_reader.py ./deck.pptx --metadata-only
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.pptx` file |
| `--slides N` | all | Slide range (`1-5`, `3`, `1,3-4,7`) |
| `--max-bytes N` | `200000` | Max bytes of rendered content returned |
| `--metadata-only` | off | Return metadata only, no content |
| `--format` | `text` | `text` or `json` |

**Exit code:** `0` on success, `2` on missing file / read error / missing `python-pptx`.

## Output format

### Text mode (default)

```text
# pptx-reader
path:      /home/alice/pitch.pptx
size:      2104832 bytes
metadata:
  total_slides: 24
  slides_returned: [1, 2, 3, 4, 5]

## Content
--- Slide 1 ---
Q4 Strategy
Acme Corp — October 2025
--- Slide 2 ---
Agenda
• Market landscape
• Product roadmap
...
```

### JSON mode

```json
{
  "path": "/home/alice/pitch.pptx",
  "extension": ".pptx",
  "kind": "pptx",
  "size": 2104832,
  "content": "--- Slide 1 ---\n...",
  "truncated": false,
  "metadata": {
    "total_slides": 24,
    "slides_returned": [1, 2, 3, 4, 5]
  },
  "error": null,
  "missing_imports": [],
  "install_guide": null
}
```

## Requirements

- Python 3.8+
- `python-pptx` — lazy-loaded; the skill prints a bilingual install guide and exits with code 2 if missing

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.
