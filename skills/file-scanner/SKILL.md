---
name: file-scanner
description: "Recursively scan a workspace and extract text from 60+ file types (code, Markdown, Word, PDF, PowerPoint, Excel). Use when the agent needs to ground context in actual file content, find TODOs across a codebase, or summarize a folder of documents."
compatibility: "Claude Code, Roo Code, Aider, Cursor, Cline, any MCP-capable or shell-capable agent"
---

# File Scanner

## Overview

`file-scanner` 遞迴掃描指定目錄，從超過 60 種檔案類型中擷取文字內容 — 包含程式碼、設定檔、Markdown、以及（若安裝對應的選用套件）Word、PowerPoint、Excel、PDF 等 Office 文件。它的設計目的是讓 AI coding agent 可以在回答問題前，先把工作空間裡「實際的檔案內容」讀進 context，而不是憑空猜測。

It supports extension filtering, regex grep with context lines, byte/file caps so you never blow up your context window, and both human-readable (`text`) and machine-readable (`json`) output.

## When to use

Trigger this skill when:

- The user asks to **find something across their codebase** — "find all TODOs", "where is `foo_bar` called?", "list files mentioning `deprecated`".
- The user asks to **summarize a folder** — "what's in this docs directory?", "summarize the specs in `/specs`".
- The user drops a project folder and the agent needs to **understand the layout and content** before making changes.
- The user has **Office documents or PDFs** in their workspace and wants them read into context.
- The user wants a **machine-readable inventory** of a folder (`--format json`) to feed into another tool.

## When NOT to use

- For a single known file, use the agent's built-in `Read`/`cat` tool — it's faster and simpler.
- For semantic / embedding search, use a dedicated vector-search skill.
- For huge binary blobs (video, images, archives), this skill will just skip them.

## Usage

Basic — scan the current directory with default extensions:

```bash
python3 scripts/scan.py .
```

Scan only Python and Markdown, look for `TODO` with 2 lines of context:

```bash
python3 scripts/scan.py ./project --ext .py,.md --grep TODO --context 2
```

List every `.docx` and `.pdf` in `./docs` as JSON without reading content:

```bash
python3 scripts/scan.py ./docs --ext .docx,.pdf --list-only --format json
```

Cap memory usage when scanning a large monorepo:

```bash
python3 scripts/scan.py . --max-bytes 50000 --max-files 500
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `path` (positional) | `.` | Root directory to scan. |
| `--ext` | 60+ built-in types | Comma-separated extensions to include, e.g. `.py,.md,.docx`. |
| `--grep PATTERN` | *(none)* | Regex to search for. Only files with matches are returned. |
| `--ignore-case` | off | Make `--grep` case-insensitive. |
| `--context N` | `0` | Lines of context around each grep match. |
| `--max-bytes N` | `200000` | Maximum bytes read per file (prevents context blow-up). |
| `--max-files N` | `0` (no limit) | Stop after scanning this many files. |
| `--ignore DIRS` | *(see below)* | Extra comma-separated directory names to skip. |
| `--include-hidden` | off | Include dotfiles and dot-directories. |
| `--list-only` | off | Only list matching files — do not emit content. |
| `--format` | `text` | `text` (human) or `json` (machine). |

### Directories skipped by default

`.git`, `.hg`, `.svn`, `node_modules`, `bower_components`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `venv`, `.venv`, `env`, `.env`, `dist`, `build`, `target`, `out`, `.idea`, `.vscode`, `.next`, `.nuxt`, `.svelte-kit`, `.gradle`, `.tox`.

### Supported file types

**Text & code (direct read):** `.py .pyi .pyx .js .jsx .ts .tsx .mjs .cjs .java .kt .kts .scala .groovy .c .h .cc .cpp .cxx .hpp .hh .cs .fs .vb .go .rs .swift .m .mm .rb .php .pl .pm .lua .r .jl .dart .ex .exs .erl .hrl .clj .cljs .cljc .edn .hs .lhs .ml .mli .nim .zig .sh .bash .zsh .fish .ps1 .psm1 .bat .cmd .md .markdown .mdx .rst .txt .adoc .asciidoc .tex .org .json .jsonc .json5 .yaml .yml .toml .ini .cfg .conf .properties .env .xml .html .htm .xhtml .svg .css .scss .sass .less .csv .tsv .dockerfile .tf .tfvars .hcl .nix .gradle .sbt .mk .cmake .sql .log .patch .diff`

**Office / PDF (optional libraries required):**

| Extension | Library | Install |
|-----------|---------|---------|
| `.docx` | `python-docx` | `pip install python-docx` |
| `.pptx` | `python-pptx` | `pip install python-pptx` |
| `.xlsx` | `openpyxl` | `pip install openpyxl` |
| `.pdf`  | `pypdf`       | `pip install pypdf` |

Missing an optional library? The scan continues and the file is reported in `skipped_missing_deps` so the agent knows what to install.

**Extension-less files** like `Dockerfile`, `Makefile`, `Rakefile`, `Gemfile`, `Procfile`, `Jenkinsfile`, `Vagrantfile`, `CMakeLists.txt`, `README`, `LICENSE`, `CHANGELOG`, `NOTICE`, `AUTHORS` are also picked up whenever any text extension is requested.

## Output format

### Text mode (default)

```text
# file-scanner results
root: /abs/path/to/project
files scanned: 12
files matched: 3
bytes read:    45210

=== /abs/path/to/project/src/main.py [text, 3421 bytes] ===
  14: # TODO: refactor this
  42: # TODO: handle edge case

=== /abs/path/to/project/README.md [text, 1204 bytes] ===
  ...
```

### JSON mode (`--format json`)

```json
{
  "root": "/abs/path/to/project",
  "files_scanned": 12,
  "files_matched": 3,
  "bytes_read": 45210,
  "skipped_missing_deps": { ".pdf": 2 },
  "results": [
    {
      "path": "/abs/path/to/project/src/main.py",
      "size": 3421,
      "extension": ".py",
      "kind": "text",
      "truncated": false,
      "content": "...",
      "matches": [
        { "line": 14, "text": "# TODO: refactor this", "before": [], "after": [] }
      ],
      "error": null
    }
  ]
}
```

## Requirements

- Python **3.8+**
- Standard library only for text / code files
- Optional: `python-docx`, `python-pptx`, `openpyxl`, `pypdf` for Office / PDF

## Integration

### Claude Code

```bash
mkdir -p ~/.claude/skills
cp -r skills/file-scanner ~/.claude/skills/
```

Once copied, Claude Code auto-discovers the skill via its frontmatter. The agent will decide when to call `scan.py` based on the `description` field above.

### Roo Code / Cursor / Cline

Register the script as a custom tool:

```jsonc
{
  "name": "file-scanner",
  "command": "python3 /absolute/path/to/skills-library/skills/file-scanner/scripts/scan.py",
  "description": "Recursively scan a workspace and extract text content from 60+ file types. Use for TODO hunts, codebase surveys, and Office/PDF reading."
}
```

### Aider or any shell-capable agent

Just invoke the script directly:

```bash
python3 /path/to/skills-library/skills/file-scanner/scripts/scan.py ./project --grep TODO
```

## Examples

### Example 1 — find every TODO in a Python project

```bash
python3 scripts/scan.py ./my-project --ext .py --grep "TODO|FIXME|XXX" --context 1
```

### Example 2 — summarize a docs folder with Office files

```bash
pip install python-docx python-pptx pypdf
python3 scripts/scan.py ./docs --ext .md,.docx,.pptx,.pdf --max-bytes 100000
```

### Example 3 — machine-readable inventory for another agent

```bash
python3 scripts/scan.py . --list-only --format json > inventory.json
```
