# pdf-reader

> Extract the text content of a PDF file, with optional page-range selection.

`pdf-reader` is one of four readers in the [`document-readers`](../../.claude-plugin/marketplace.json) plugin. Give it a `.pdf` file and it extracts the text page-by-page, marking each page with `--- Page N ---` so the LLM can reason about where content was said. Supports page ranges like `1-5,7,9-10` so you only pay for the pages you actually need.

Pair it with [`document-search`](../document-search/) for the full **文書工作 (office workflow)** loop: search first, then read.

---

## Requirements

- **Python 3.8+**
- **`pypdf`** — `pip install pypdf`

If `pypdf` is missing, the skill doesn't crash — it prints a bilingual install guide with the exact `pip` command and `HTTPS_PROXY` instructions for corporate networks, then exits with code 2.

---

## Install

```bash
# Interactive wizard (recommended — picks agent + scope)
python install.py

# Or directly
python install.py install pdf-reader --agent claude
```

See the [root README](../../README.md#installation) for the full story: one-file installer without `git clone`, Claude Code plugin marketplace (`document-readers` bundle), Roo Code and Cline setup, workspace vs global scope, and manual install paths.

---

## Usage

### Quick examples

Read everything:

```bash
python3 scripts/pdf_reader.py ./report.pdf
```

Pages 1-5 only:

```bash
python3 scripts/pdf_reader.py ./report.pdf --pages 1-5
```

Page 3, 5, 7 and 10-12:

```bash
python3 scripts/pdf_reader.py ./report.pdf --pages 3,5,7,10-12
```

Just describe it:

```bash
python3 scripts/pdf_reader.py ./report.pdf --metadata-only
```

JSON pipeline:

```bash
python3 scripts/pdf_reader.py ./report.pdf --format json | jq '.metadata'
```

### Full option list

| Flag | Default | Description |
|------|---------|-------------|
| `file` (**required**) | — | Path to the `.pdf` file |
| `--pages N` | all | Page range (`1-5`, `3`, `1,3-4,7`) |
| `--max-bytes N` | `200000` | Max bytes of rendered content returned |
| `--metadata-only` | off | Metadata only, no content |
| `--format` | `text` | `text` or `json` |

Run `python3 scripts/pdf_reader.py --help` for the live version.

---

## Output format

### Text mode

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

### JSON mode

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

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | File read successfully |
| `2` | File not found, read error, or missing `pypdf` |

---

## See also

- [SKILL.md](SKILL.md) — agent-facing skill definition
- [document-search](../document-search/) — find which PDF mentions a keyword
- Sibling readers: [docx-reader](../docx-reader/), [xlsx-reader](../xlsx-reader/), [pptx-reader](../pptx-reader/)
- [Root README](../../README.md)
