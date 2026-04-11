---
name: document-search
description: "Search a folder for a term and return a ranked list of files that contain it — including inside .docx, .pptx, .xlsx, and .pdf documents where ordinary grep/rg are blind. Use whenever the user asks 'which files mention X?', 'where is Y used?', or needs to search a folder containing Word / Excel / PowerPoint / PDF files."
compatibility: "Claude Code, Roo Code, Cline"
---

# Document Search

## Overview

`document-search` 是一個「能看懂 Office 和 PDF 的 grep」。給它一個關鍵字和一個目錄，它會地毯式掃描目錄下所有支援的檔案（60+ 種程式碼 / 文字格式 + `.docx` / `.pptx` / `.xlsx` / `.pdf`），回傳一份依命中次數排序的**檔案清單**，讓 agent 直接告訴使用者「這個詞出現在哪些檔案裡」。

The key differentiator: ordinary `grep` / `ripgrep` cannot see inside binary document formats. `document-search` extracts their text first (via optional `python-docx`, `python-pptx`, `openpyxl`, `pypdf`), then searches it — so a user asking "which of my spec docs mentions `auth token`?" gets an accurate answer even when half the folder is `.docx` and `.pdf`.

## When to use

Fire this skill when the user asks, in any phrasing, one of:

- **"Which files mention / contain / reference `<term>`?"**
- **"Where is `<function_name>` / `<class>` / `<config key>` used in this project?"**
- **"Find all TODO / FIXME / XXX in the codebase."**
- **"Search my docs folder for `<keyword>` — there are Word files and PDFs in there."**
- **"Is `<string>` mentioned anywhere in this workspace?"**
- Any question that boils down to *"locate a term across many files of mixed formats"*.

## When NOT to use

- You already know the file — just use the agent's built-in `Read` / `cat` tool, or one of the companion reader skills (`pdf-reader`, `docx-reader`, `xlsx-reader`, `pptx-reader`) for Office / PDF.
- You need fuzzy / semantic search (e.g. "find files about authentication" without a specific term) — use an embedding-based skill instead.
- You need to *modify* matched content — `document-search` is read-only. Pipe its file list into another tool.

## Usage

Basic — find every occurrence of a term under the current directory:

```bash
python3 scripts/document_search.py "auth token"
```

Literal (non-regex) match, case-insensitive, scoped to `./docs`:

```bash
python3 scripts/document_search.py "Auth Token" ./docs -F -i
```

Restrict to code files and show the matched lines with 1 line of context:

```bash
python3 scripts/document_search.py "TODO|FIXME" ./src --ext .py,.ts,.go --show-matches --context 1
```

Search Office + PDF documents (install optional libs first):

```bash
pip install python-docx python-pptx openpyxl pypdf
python3 scripts/document_search.py "quarterly revenue" ./reports --ext .docx,.xlsx,.pdf
```

Machine-readable output for agent-to-agent pipelines:

```bash
python3 scripts/document_search.py "deprecated" . --format json
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `pattern` (positional, **required**) | — | Regex to search for (or literal with `-F`). |
| `path` (positional) | `.` | Root directory to scan. |
| `--ext` | 60+ built-in types | Comma-separated extensions, e.g. `.py,.md,.docx`. |
| `-F`, `--fixed-string` | off | Treat `pattern` as a literal string, not a regex. |
| `-i`, `--ignore-case` | off | Case-insensitive match. |
| `--show-matches` | off | Include the matched lines (with line numbers) in the output. |
| `--context N` | `0` | Lines of context around each match (implies `--show-matches`). |
| `--content` | off | Also include the full extracted file content (JSON only, rare). |
| `--max-bytes N` | `200000` | Max bytes read per file — protects the agent's context window. |
| `--max-files N` | `0` | Stop after N files (0 = no limit). |
| `--ignore DIRS` | *(see below)* | Extra directory names to skip. |
| `--include-hidden` | off | Include dotfiles and dot-directories. |
| `--format` | `text` | `text` (human) or `json` (machine). |

**Exit code:** `0` if anything matched, `1` if nothing matched, `2` on a usage / path / regex error — same convention as `grep`.

### Directories skipped by default

`.git`, `.hg`, `.svn`, `node_modules`, `bower_components`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `venv`, `.venv`, `env`, `.env`, `dist`, `build`, `target`, `out`, `.idea`, `.vscode`, `.next`, `.nuxt`, `.svelte-kit`, `.gradle`, `.tox`.

### Supported file types

**Text & code (direct read, no extra deps):** `.py .pyi .pyx .js .jsx .ts .tsx .mjs .cjs .java .kt .kts .scala .groovy .c .h .cc .cpp .cxx .hpp .hh .cs .fs .vb .go .rs .swift .m .mm .rb .php .pl .pm .lua .r .jl .dart .ex .exs .erl .hrl .clj .cljs .cljc .edn .hs .lhs .ml .mli .nim .zig .sh .bash .zsh .fish .ps1 .psm1 .bat .cmd .md .markdown .mdx .rst .txt .adoc .asciidoc .tex .org .json .jsonc .json5 .yaml .yml .toml .ini .cfg .conf .properties .env .xml .html .htm .xhtml .svg .css .scss .sass .less .csv .tsv .dockerfile .tf .tfvars .hcl .nix .gradle .sbt .mk .cmake .sql .log .patch .diff`

**Office / PDF (optional libraries required):**

| Extension | Library | Install |
|-----------|---------|---------|
| `.docx` | `python-docx` | `pip install python-docx` |
| `.pptx` | `python-pptx` | `pip install python-pptx` |
| `.xlsx` | `openpyxl` | `pip install openpyxl` |
| `.pdf`  | `pypdf`       | `pip install pypdf` |

If a library is missing, the scan continues and the affected files are reported under `skipped_missing_deps` so the agent knows exactly what to `pip install`. A bilingual (English / 中文) install guide with `pip` command + `HTTPS_PROXY` instructions is printed at the end.

**Extension-less files** like `Dockerfile`, `Makefile`, `Rakefile`, `Gemfile`, `Procfile`, `Jenkinsfile`, `Vagrantfile`, `CMakeLists.txt`, `README`, `LICENSE`, `CHANGELOG`, `NOTICE`, `AUTHORS` are also picked up whenever any text extension is requested.

## Output format

### Text mode (default)

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

Add `--show-matches` (or `--context N`) to also get a `## Match details` section with line numbers and surrounding context.

### JSON mode (`--format json`)

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

Results are always sorted by `match_count` descending so the most relevant files come first.

## Requirements

- Python 3.8+ — standard library only for text / code files
- Optional for Office / PDF: `python-docx`, `python-pptx`, `openpyxl`, `pypdf`. Lazy-loaded; the skill skips affected files and prints a bilingual install guide if any are missing.

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.

## Example with expected output

The `## Usage` section above lists common invocations. Here is one end-to-end example so the agent knows what to expect back from the script:

```bash
python3 scripts/document_search.py "DATABASE_URL" .
```

```text
# document-search results
pattern: 'DATABASE_URL'
root:    /home/alice/project
files matched: 3 / 214 scanned (7 total matches)

## Matched files
  config/settings.py       4 matches
  .env.example             2 matches
  README.md                1 match
```
