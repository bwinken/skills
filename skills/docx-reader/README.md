# docx-reader

> Extract the text content of a Word (`.docx`) file — paragraphs and tables.

`docx-reader` is one of four readers in the [`document-readers`](../../.claude-plugin/marketplace.json) plugin. Give it a `.docx` file and it returns the plain text of every paragraph, plus each table flattened to `cell | cell | cell` rows so the LLM can still read table data without a full table renderer.

Pair it with [`document-search`](../document-search/) for the full **文書工作 (office workflow)** loop: search first, then read.

---

## Requirements

- **Python 3.8+**
- **`python-docx`** — `pip install python-docx`

If `python-docx` is missing, the skill doesn't crash — it prints a bilingual install guide with the exact `pip` command and `HTTPS_PROXY` instructions, then exits with code 2.

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

---

## Usage

### Quick examples

Read a whole document:

```bash
python3 scripts/docx_reader.py ./spec.docx
```

Just describe it:

```bash
python3 scripts/docx_reader.py ./spec.docx --metadata-only
```

JSON pipeline:

```bash
python3 scripts/docx_reader.py ./spec.docx --format json
```

### Full option list

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.docx` file |
| `--max-bytes N` | `200000` | Max bytes of rendered content returned |
| `--metadata-only` | off | Metadata only, no content |
| `--format` | `text` | `text` or `json` |

---

## Output format

### Text mode

```text
# docx-reader
path:      /home/alice/spec.docx
size:      45128 bytes
metadata:
  paragraphs: 87
  tables: 3

## Content
Project Kickoff — Q4 2025
...
Role | Owner | Deadline
Lead | Alice | 2026-01-15
```

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

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | File read successfully |
| `2` | File not found, read error, or missing `python-docx` |

---

## See also

- [SKILL.md](SKILL.md) — agent-facing skill definition
- [document-search](../document-search/) — find which Word doc mentions a keyword
- Sibling readers: [pdf-reader](../pdf-reader/), [xlsx-reader](../xlsx-reader/), [pptx-reader](../pptx-reader/)
- [Root README](../../README.md)
