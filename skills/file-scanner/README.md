# file-scanner

> Recursively scan a workspace and extract text from 60+ file types — code, Markdown, Word, PowerPoint, Excel, and PDF.

`file-scanner` is the "give an agent eyes on the filesystem" skill. Point it at a folder and it walks the tree, skips junk directories, reads every supported file up to a configurable byte cap, optionally runs a regex grep, and emits either a human-readable report or a JSON document you can pipe to another tool.

It's the first skill in the [SkillForge](../../README.md) library and a good reference for how skills in this repo are structured.

---

## Features

- **60+ built-in file types** — every common programming language, shell, markup, config, and data format.
- **Office + PDF support** — `.docx`, `.pptx`, `.xlsx`, `.pdf` via optional libraries; the scan degrades gracefully when they're not installed.
- **Regex grep with context** — find patterns across a whole workspace in one call.
- **Context-window safe** — per-file `--max-bytes` and total `--max-files` caps so you never blow up an LLM's context.
- **Smart defaults** — skips `.git`, `node_modules`, `__pycache__`, build output, venvs, and other noise out of the box.
- **Two output modes** — `text` for humans, `json` for agent-to-agent pipelines.
- **Pure Python 3.8+ standard library** for core functionality.

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

If a library is missing, the scan still completes — the affected files are reported in a `skipped_missing_deps` summary so the calling agent knows exactly what to `pip install`.

---

## Installation

### As part of SkillForge

```bash
git clone https://github.com/bwinken/skills-library.git
cd skills-library
python3 skills/file-scanner/scripts/scan.py --help
```

### Standalone (copy just this folder)

```bash
cp -r skills/file-scanner ~/my-project/tools/
python3 ~/my-project/tools/file-scanner/scripts/scan.py --help
```

### Claude Code

```bash
mkdir -p ~/.claude/skills
cp -r skills/file-scanner ~/.claude/skills/
```

See [SKILL.md](SKILL.md) for Roo Code, Cursor, Cline, and Aider integration snippets.

---

## Usage

### Quick examples

Scan the current directory with all default extensions:

```bash
python3 scripts/scan.py .
```

Find every TODO or FIXME in a Python project with 1 line of context:

```bash
python3 scripts/scan.py ./my-project --ext .py --grep "TODO|FIXME" --context 1
```

Pull text out of a folder of Office and PDF documents:

```bash
python3 scripts/scan.py ./docs --ext .docx,.pdf,.pptx --max-bytes 100000
```

List every Markdown file as JSON without reading content:

```bash
python3 scripts/scan.py ./site --ext .md --list-only --format json
```

### Full option list

| Flag | Default | Description |
|------|---------|-------------|
| `path` (positional) | `.` | Root directory to scan |
| `--ext` | 60+ types | Comma-separated extensions (`.py,.md,.docx`) |
| `--grep PATTERN` | *(none)* | Regex to search for; only matching files are returned |
| `--ignore-case` | off | Case-insensitive grep |
| `--context N` | `0` | Lines of context around each grep match |
| `--max-bytes N` | `200000` | Maximum bytes read per file |
| `--max-files N` | `0` | Stop after N files (0 = unlimited) |
| `--ignore DIRS` | *(see below)* | Extra directory names to skip |
| `--include-hidden` | off | Include dotfiles and dot-directories |
| `--list-only` | off | Do not emit file contents |
| `--format` | `text` | `text` or `json` |

Run `python3 scripts/scan.py --help` for the live version.

### Default ignored directories

`.git`, `.hg`, `.svn`, `node_modules`, `bower_components`, `__pycache__`, `.pytest_cache`, `.mypy_cache`, `.ruff_cache`, `venv`, `.venv`, `env`, `.env`, `dist`, `build`, `target`, `out`, `.idea`, `.vscode`, `.next`, `.nuxt`, `.svelte-kit`, `.gradle`, `.tox`

---

## Output format

### Text mode

```text
# file-scanner results
root: /home/alice/project
files scanned: 12
files matched: 3
bytes read:    45210

=== /home/alice/project/src/main.py [text, 3421 bytes] ===
  14: # TODO: refactor this
  42: # TODO: handle edge case

=== /home/alice/project/README.md [text, 1204 bytes] ===
  ...
```

### JSON mode

```json
{
  "root": "/home/alice/project",
  "files_scanned": 12,
  "files_matched": 3,
  "bytes_read": 45210,
  "skipped_missing_deps": { ".pdf": 2 },
  "results": [
    {
      "path": "/home/alice/project/src/main.py",
      "size": 3421,
      "extension": ".py",
      "kind": "text",
      "truncated": false,
      "content": "...",
      "matches": [
        {
          "line": 14,
          "text": "# TODO: refactor this",
          "before": [],
          "after": []
        }
      ],
      "error": null
    }
  ]
}
```

---

## How it works

1. **Walk** — `os.walk()` with in-place pruning of the ignore list (avoids descending into `node_modules` etc.).
2. **Filter** — each file is matched against the requested extension set; extension-less files like `Dockerfile` and `Makefile` are picked up when any text extension is requested.
3. **Read** — text and code files go through a size-capped UTF-8 decode with lenient error handling. Office / PDF files are routed to optional library adapters (`python-docx`, `python-pptx`, `openpyxl`, `pypdf`).
4. **Grep** (optional) — line-by-line regex match with configurable leading/trailing context.
5. **Render** — `text` mode produces a human-readable report; `json` mode produces a dataclass-backed document suitable for piping into another tool.

Files that are too large to read in full are truncated at `--max-bytes`, marked `"truncated": true`, and still returned so the agent can see what was cut.

---

## See also

- [SKILL.md](SKILL.md) — agent-facing skill definition
- [Root README](../../README.md) — the full SkillForge library
- [CONTRIBUTING](../../CONTRIBUTING.md) — how to add your own skill
