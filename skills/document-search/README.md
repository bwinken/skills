# document-search

> Search a folder for a term and get back a ranked list of files that contain it — including inside `.docx`, `.pptx`, `.xlsx`, and `.pdf`.

`document-search` is a grep that doesn't go blind on Office and PDF files. Point it at a folder, give it a search term, and it walks the tree, extracts text from 60+ text/code formats **and** Microsoft Office / PDF documents, counts matches per file, and emits a compact list sorted by match count.

It's the first half of the **文書工作 (office workflow)** suite in this repo — pair it with the `document-readers` plugin ([`pdf-reader`](../pdf-reader/), [`docx-reader`](../docx-reader/), [`xlsx-reader`](../xlsx-reader/), [`pptx-reader`](../pptx-reader/)) when you want to search first, then read the matching file's content.

---

## Why not just use `grep` / `ripgrep`?

Ordinary `grep`, `rg`, `ag`, and every IDE "Find in Files" feature treat `.docx`, `.pptx`, `.xlsx`, and `.pdf` as binary noise and skip them. That's fine until your user has a `/docs` folder full of Word specs and PDF reports and asks *"which of these mentions the quarterly revenue target?"* — suddenly none of the standard tools help.

`document-search` plugs that gap. For text / code files it behaves like any normal grep (and is dependency-free). For Office / PDF it first extracts text via optional libraries (`python-docx`, `python-pptx`, `openpyxl`, `pypdf`) and then searches that. You get one ranked list that covers the whole workspace.

---

## Features

- **Ranked file list by default** — exactly what an agent needs to answer "which files mention X?"
- **60+ text / code file types** plus **`.docx` / `.pptx` / `.xlsx` / `.pdf`**
- **Regex or literal search** (`-F`), **case-insensitive** (`-i`)
- **Optional line-level output** (`--show-matches` / `--context N`)
- **Context-window safe** — `--max-bytes` and `--max-files` caps so nothing blows up the agent
- **Graceful degradation** — missing an optional library? The scan still runs; affected files are reported under `skipped_missing_deps` and a bilingual install guide is printed at the end
- **Grep-style exit codes** — `0` if anything matched, `1` if nothing did
- **`text` and `json` output modes**
- **Python 3.8+ standard library** for the core

---

## Requirements

- **Python 3.8 or newer**
- **No required third-party dependencies** for text / code files.

### Optional dependencies

Install only the ones whose file types you actually care about:

| File type | Package | Install |
|-----------|---------|---------|
| `.docx` (Word) | `python-docx` | `pip install python-docx` |
| `.pptx` (PowerPoint) | `python-pptx` | `pip install python-pptx` |
| `.xlsx` (Excel) | `openpyxl` | `pip install openpyxl` |
| `.pdf` | `pypdf` | `pip install pypdf` |

Install everything at once:

```bash
pip install python-docx python-pptx openpyxl pypdf
```

---

## Installation

Works with **Claude Code**, **Roo Code**, and **Cline** — all three natively auto-discover this skill from their standard folders.

### Easiest — one-file installer

```bash
# macOS / Linux
curl -fsSLO https://raw.githubusercontent.com/bwinken/skills/main/install.py
python install.py            # interactive wizard

# Windows (PowerShell)
iwr https://raw.githubusercontent.com/bwinken/skills/main/install.py -OutFile install.py
python install.py
```

Non-interactive variant:

```bash
python install.py install document-search --agent claude               # global
python install.py install document-search --agent roo --scope workspace
python install.py install document-search --agent cline
```

### Claude Code — plugin marketplace

```text
/plugin marketplace add bwinken/skills
/plugin install document-search@skills
```

### Manual install

| Agent | Global | Workspace |
|-------|--------|-----------|
| Claude Code | `~/.claude/skills/document-search/` | `./.claude/skills/document-search/` |
| Roo Code | `~/.roo/skills/document-search/` | `./.roo/skills/document-search/` |
| Cline | `~/.cline/skills/document-search/` | `./.cline/skills/document-search/` |

---

## Usage

### Quick examples

Find a term across the whole workspace:

```bash
python3 scripts/document_search.py "DATABASE_URL" .
```

Literal string, case-insensitive, only in docs:

```bash
python3 scripts/document_search.py "Q4 roadmap" ./docs -F -i
```

TODO hunt in source code with 2 lines of context:

```bash
python3 scripts/document_search.py "TODO|FIXME" ./src --ext .py,.ts --context 2
```

Office + PDF search:

```bash
pip install python-docx pypdf
python3 scripts/document_search.py "auth token" ./docs --ext .docx,.pdf
```

JSON for piping into `jq` or another tool:

```bash
python3 scripts/document_search.py "deprecated" . --format json | jq '.results[] | {path, match_count}'
```

### Full option list

| Flag | Default | Description |
|------|---------|-------------|
| `pattern` (**required**) | — | Regex to search for (or literal with `-F`) |
| `path` (positional) | `.` | Root directory to scan |
| `--ext` | 60+ types | Comma-separated extensions (`.py,.md,.docx`) |
| `-F`, `--fixed-string` | off | Treat `pattern` as a literal string |
| `-i`, `--ignore-case` | off | Case-insensitive match |
| `--show-matches` | off | Include matched lines with line numbers |
| `--context N` | `0` | Lines of context around each match (implies `--show-matches`) |
| `--content` | off | Also include full extracted content (JSON only) |
| `--max-bytes N` | `200000` | Max bytes read per file |
| `--max-files N` | `0` | Stop after N files (0 = unlimited) |
| `--ignore DIRS` | *(see below)* | Extra directory names to skip |
| `--include-hidden` | off | Include dotfiles |
| `--format` | `text` | `text` or `json` |

Run `python3 scripts/document_search.py --help` for the live version.

### Default ignored directories

`.git`, `.hg`, `.svn`, `node_modules`, `bower_components`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `venv`, `.venv`, `env`, `.env`, `dist`, `build`, `target`, `out`, `.idea`, `.vscode`, `.next`, `.nuxt`, `.svelte-kit`, `.gradle`, `.tox`

---

## Output format

### Text mode (default — ranked file list)

```text
# document-search results
pattern: 'auth token'
root:    /home/alice/project
files matched: 3 / 128 scanned (17 total matches)

## Matched files
  src/auth/session.py          9 matches
  docs/architecture.docx       5 matches [docx]
  docs/security-review.pdf     3 matches [pdf]
```

Add `--show-matches` or `--context N` for a `## Match details` section:

```text
## Match details
=== src/auth/session.py (9) ===
     14- def create_session(user):
     15:     token = issue_auth_token(user)
     16-     return token
```

### JSON mode

```json
{
  "pattern": "auth token",
  "root": "/home/alice/project",
  "files_scanned": 128,
  "files_matched": 3,
  "total_matches": 17,
  "skipped_missing_deps": {},
  "results": [
    {
      "path": "/home/alice/project/src/auth/session.py",
      "extension": ".py",
      "kind": "text",
      "size": 4821,
      "match_count": 9,
      "truncated": false,
      "matches": [],
      "content": null,
      "error": null
    }
  ]
}
```

Results are always sorted by `match_count` descending.

### Exit codes

| Code | Meaning |
|------|---------|
| `0` | At least one file matched |
| `1` | No matches |
| `2` | Usage error, invalid regex, or bad path |

---

## How it works

1. **Walk** — `os.walk()` with in-place pruning of the ignore list, so it never descends into `node_modules` / `.git` / `venv` / etc.
2. **Filter** — each file is matched against the requested extension set; extension-less files like `Dockerfile` and `Makefile` are picked up when any text extension is requested.
3. **Extract** — text / code files get a size-capped UTF-8 decode. Office / PDF files are routed to optional adapters (`python-docx`, `python-pptx`, `openpyxl`, `pypdf`). Missing libraries are reported gracefully.
4. **Count** — a single `findall` per file (fast, no line split) unless `--show-matches` is set, in which case it does a line-by-line scan so it can also return line numbers and context.
5. **Rank & render** — results are sorted by `match_count` descending and rendered as either a compact text list or a JSON document.

Files larger than `--max-bytes` are truncated and marked `"truncated": true` so the agent knows the count might be a lower bound.

---

## See also

- [SKILL.md](SKILL.md) — agent-facing skill definition
- Companion readers: [pdf-reader](../pdf-reader/), [docx-reader](../docx-reader/), [xlsx-reader](../xlsx-reader/), [pptx-reader](../pptx-reader/) — extract content from a single document
- [Root README](../../README.md) — the full skills library
- [CONTRIBUTING](../../CONTRIBUTING.md) — how to add your own skill
