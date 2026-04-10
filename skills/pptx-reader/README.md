# pptx-reader

> Extract the text content of a PowerPoint (`.pptx`) deck, with optional slide-range selection.

`pptx-reader` is one of four readers in the [`document-readers`](../../.claude-plugin/marketplace.json) plugin. Give it a `.pptx` file and it extracts each slide's text in order, marking boundaries with `--- Slide N ---` so the LLM can reason about slide positions.

Pair it with [`document-search`](../document-search/) for the full **文書工作 (office workflow)** loop: search first, then read.

---

## Requirements

- **Python 3.8+**
- **`python-pptx`** — `pip install python-pptx`

If `python-pptx` is missing, the skill doesn't crash — it prints a bilingual install guide with the exact `pip` command and `HTTPS_PROXY` instructions, then exits with code 2.

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
python install.py install pptx-reader --agent claude
```

### Claude Code — plugin marketplace

Install the whole `document-readers` suite:

```text
/plugin marketplace add bwinken/skills
/plugin install document-readers@skills
```

Or just this one:

```text
/plugin install pptx-reader@skills
```

### Manual install

| Agent | Global | Workspace |
|-------|--------|-----------|
| Claude Code | `~/.claude/skills/pptx-reader/` | `./.claude/skills/pptx-reader/` |
| Roo Code | `~/.roo/skills/pptx-reader/` | `./.roo/skills/pptx-reader/` |
| Cline | `~/.cline/skills/pptx-reader/` | `./.cline/skills/pptx-reader/` |

---

## Usage

### Quick examples

Read the whole deck:

```bash
python3 scripts/pptx_reader.py ./deck.pptx
```

Slides 1-5 only:

```bash
python3 scripts/pptx_reader.py ./deck.pptx --slides 1-5
```

Slide 3 and slides 7-10:

```bash
python3 scripts/pptx_reader.py ./deck.pptx --slides 3,7-10
```

Describe the deck:

```bash
python3 scripts/pptx_reader.py ./deck.pptx --metadata-only
```

### Full option list

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.pptx` file |
| `--slides N` | all | Slide range (`1-5`, `3`, `1,3-4,7`) |
| `--max-bytes N` | `200000` | Max bytes of rendered content returned |
| `--metadata-only` | off | Metadata only, no content |
| `--format` | `text` | `text` or `json` |

---

## Output format

### Text mode

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
...
```

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | File read successfully |
| `2` | File not found, read error, or missing `python-pptx` |

---

## See also

- [SKILL.md](SKILL.md) — agent-facing skill definition
- [document-search](../document-search/) — find which deck mentions a keyword
- Sibling readers: [pdf-reader](../pdf-reader/), [docx-reader](../docx-reader/), [xlsx-reader](../xlsx-reader/)
- [Root README](../../README.md)
