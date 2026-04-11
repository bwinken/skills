# docx-inspector

> Structural inspection of a single Word document — core properties, tracked changes, and heading-hierarchy outline. Returns the deterministic facts an LLM cannot derive from extracted text.

[`docx-reader`](../docx-reader/) returns the *text* of a `.docx` file. This skill returns its *structure*: who authored it, when it was modified, every tracked change in the revision history (walked straight from `w:ins` / `w:del` XML nodes — python-docx doesn't expose these through its high-level API), and the document's heading hierarchy with automatic skipped-level detection.

One of three sibling skills in the **`document-inspector`** plugin:

- [`pdf-inspector`](../pdf-inspector/) — `.pdf` files
- `docx-inspector` — `.docx` files (this skill)
- [`xlsx-inspector`](../xlsx-inspector/) — `.xlsx` files

---

## Requirements

- **Python 3.8+**
- **`python-docx`** (import name `docx`) — lazy-loaded. Skill prints a bilingual install guide on first use if missing.

Install:

```bash
pip install python-docx
```

---

## Installation

### Claude Code — plugin marketplace

```text
/plugin marketplace add bwinken/skills
/plugin install document-inspector@skills
```

The `document-inspector` plugin bundles `docx-inspector` with `pdf-inspector` and `xlsx-inspector`. Install the plugin once and get all three.

### Other agents — install.py wizard

```bash
python install.py install docx-inspector --agent claude   # or roo, cline
```

### Manual install

Copy this folder into the right directory for your agent:

- **Claude Code**: `~/.claude/skills/docx-inspector/` (global) or `./.claude/skills/docx-inspector/` (workspace)
- **Roo Code**: `~/.roo/skills/docx-inspector/` or `./.roo/skills/docx-inspector/`
- **Cline**: `~/.cline/skills/docx-inspector/` or `./.cline/skills/docx-inspector/`

---

## Usage

### Basic — full inspection

```bash
python3 scripts/docx_inspector.py ./contract.docx
```

Reports metadata, tracked changes, and structure.

### Metadata only

```bash
python3 scripts/docx_inspector.py ./contract.docx --feature metadata
```

### Tracked changes only

```bash
python3 scripts/docx_inspector.py ./contract.docx --feature changes
```

### Heading structure only

```bash
python3 scripts/docx_inspector.py ./contract.docx --feature structure
```

### JSON output

```bash
python3 scripts/docx_inspector.py ./contract.docx --format json | jq '.changes'
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.docx` file |
| `--feature` | `all` | `metadata`, `changes`, `structure`, or `all` |
| `--format` | `text` | `text` or `json` |

---

## Output format

### Text — metadata

```text
# docx-inspector
path:      /home/alice/contract.docx
size:      28412 bytes
kind:      docx
feature:   metadata

## Metadata
  title: Master Service Agreement
  author: Alice Chen
  created: 2026-01-12T09:22:00+00:00
  modified: 2026-03-04T14:08:00+00:00
  last_modified_by: Bob Smith
  revision: 17
  paragraph_count: 142
  word_count: 6284
  table_count: 4
  section_count: 3
```

### Text — tracked changes

```text
## Tracked changes
  insertion_count: 12
  deletion_count:  8
  authors: Alice Chen, Bob Smith, Carol Lee

  changes:
    [insert] Bob Smith @ 2026-03-04T10:15:00Z: 'must be delivered within 30 days of'
    [delete] Bob Smith @ 2026-03-04T10:15:00Z: 'upon signing'
```

### Text — structure

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
            H3: Indemnification Terms
```

### JSON mode

```json
{
  "path": "/home/alice/contract.docx",
  "kind": "docx",
  "feature": "all",
  "metadata": {"title": "Master Service Agreement", "word_count": 6284},
  "changes": {
    "has_tracked_changes": true,
    "insertion_count": 12,
    "deletion_count": 8,
    "authors": ["Alice Chen", "Bob Smith"],
    "changes": [
      {"type": "insert", "author": "Bob Smith", "date": "2026-03-04T10:15:00Z", "text": "...", "id": "42"}
    ]
  },
  "structure": {
    "heading_count": 18,
    "hierarchy_issues": [{"level": 3, "previous_level": 1, "issue": "skipped from H1 to H3 (missing H2)"}]
  }
}
```

---

## Examples

### Example 1 — who edited this contract and what did they change?

```bash
python3 scripts/docx_inspector.py contract.docx --feature changes
```

Returns every tracked insertion and deletion with author, timestamp, and the actual text. Useful for reviewing a contract that came back from legal with track changes on.

### Example 2 — is this document's heading structure consistent?

```bash
python3 scripts/docx_inspector.py report.docx --feature structure
```

Returns the full outline plus any hierarchy issues (H1 → H3 jumps, first heading not H1, etc.). Useful before publishing a document that needs a clean table of contents.

### Example 3 — document properties for an audit

```bash
python3 scripts/docx_inspector.py report.docx --feature metadata --format json
```

Machine-readable core properties (title, author, dates, revision number, word count) — good for audit logs or compliance reports.

---

## How it works

1. Open the `.docx` with [`python-docx`](https://python-docx.readthedocs.io/).
2. **Metadata**: read `doc.core_properties` for the standard OOXML properties (title, author, dates, revision, last-modified-by, etc.) and compute counts from `doc.paragraphs`, `doc.tables`, `doc.sections`.
3. **Tracked changes**: walk `doc.element` (the raw lxml tree) for `w:ins` and `w:del` elements. The `w:author` / `w:date` / `w:id` attributes give you the revision metadata; inserted text lives in `w:t` descendants and deleted text lives in `w:delText` descendants. python-docx's high-level API doesn't expose tracked changes at all — this direct XML walk is the only path.
4. **Structure**: iterate `doc.paragraphs`, detect any paragraph whose style name starts with `"Heading "`, parse the level number, and walk the sequence flagging hierarchy issues (skipped levels downward, first heading not H1).

All work is read-only. Errors (missing file, broken DOCX, missing package, wrong extension) produce a structured error record and exit code 2, never a stack trace in the user's face.

### Caps

- Tracked changes capped at 200 entries (`truncated` flag signals overflow)
- Each change's text capped at 200 characters with an ellipsis
- Outline capped at 200 headings

---

## See also

- [SKILL.md](SKILL.md) — agent-facing definition
- [docx-reader](../docx-reader/) — when you want the *text* of a `.docx` file
- [pdf-inspector](../pdf-inspector/) — the `.pdf` sibling
- [xlsx-inspector](../xlsx-inspector/) — the `.xlsx` sibling
- [ROADMAP.md §1](../../ROADMAP.md) — design notes for the document-inspector plugin
