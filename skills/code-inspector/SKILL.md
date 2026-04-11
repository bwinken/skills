---
name: code-inspector
description: "Structural inspection of a codebase — two feature tiers: (1) overview = language/LOC breakdown, detected entry points, detected frameworks (Django/FastAPI/React/Next.js/...), detected test layout; (2) ast = per-file Python AST analysis (classes, top-level functions, imports with relative-depth, statement count, max nesting depth, has `__main__` check) plus aggregate totals and a top-10 most-complex-files ranking. Stdlib only, read-only, gitignore-aware walk. Use whenever the user asks to explore/understand/map an unfamiliar codebase, find the largest classes, see the import structure, or list entry points and frameworks — before writing any code in the project."
compatibility: "Claude Code, Roo Code, Cline"
---

# Code Inspector

## Overview

`code-inspector` is the codebase-side analog of the `document-inspector` plugin: it returns **structural facts** about a project folder that an LLM would otherwise waste tokens discovering through repeated `ls` / `cat` / grep calls. Two feature tiers:

- **`overview`** — the layer-1 facts every agent wants when joining a new repo: language + LOC breakdown, entry points (`pyproject.toml` / `package.json` / `Cargo.toml` / ...), detected frameworks (Django / FastAPI / React / Next.js / pytest / Jest / ...), and test layout. Stdlib-only, seconds to run.
- **`ast`** — per-file Python AST analysis via the stdlib `ast` module: classes (with bases, methods, length), top-level functions (args, async, return annotation, length), imports (with relative-import depth), statement count, max nesting depth, `if __name__ == "__main__":` detection. Aggregate totals across parsed files plus a **top-10 most-complex-files** ranking. Non-Python files are counted in `overview` but ignored by `ast`.

Directory tree (`--tree`) is an orthogonal output toggle — it can be added on top of any feature selection (or run alone via `--feature overview --tree` / similar).

The skill walks the project with `git ls-files` when a `.git/` is present (honoring `.gitignore` natively) or a hard-coded ignore list as fallback (`node_modules`, `venv`, `build`, `dist`, `__pycache__`, `.mypy_cache`, etc.).

One skill per plugin is intentional here: unlike document-inspector (which splits per file format), code-inspector operates on a **folder**, so the "single file → split per format" rule doesn't apply. Layer 3 (non-Python AST via `tree-sitter-languages`) is a planned add-on, not a separate skill.

## When to use

Fire this skill when the user asks, in any phrasing:

- **"Give me an overview of this project."** / **"What's the structure of this codebase?"**
- **"What language / framework is this project in?"**
- **"Where are the entry points?"** / **"Where do I start reading?"**
- **"Where are the tests in this repo?"**
- **"List all the classes in this project."** / **"How many functions are there?"**
- **"Which files are the most complex?"** / **"Show me the biggest classes."**
- **"What does this file import?"** / **"What are the top-level dependencies?"**
- **"Does this project have a main entry point?"** / **"Which modules can be run standalone?"**
- **"Show me the directory tree (but skip `node_modules`)."**
- Any first-pass question about an **unfamiliar project folder** — especially before starting to write or modify code in it.

## When NOT to use

- You want **the content** of a specific file — use the agent's built-in `Read` tool.
- You want to **search file contents** — use [`document-search`](../document-search/) (works on code folders too).
- You want **non-Python AST** (JS / TS / Go / Rust class listings) — not yet supported; layer 3 is planned via `tree-sitter-languages`. For now, `overview` gives you cross-language facts and `ast` gives you Python depth.
- You want a **call graph** or **dependency resolution** — the skill is deliberately static and file-level. A real call graph needs a CFG and this is out of scope.
- You want to **diff two branches** or **review a PR** — that's the planned `code-review` skill, not this one.

## Usage

Full inspection (overview + AST — default):

```bash
python3 scripts/code_inspector.py ./path/to/repo
```

Just the overview (layer 1, fast, no AST parsing):

```bash
python3 scripts/code_inspector.py ./path/to/repo --feature overview
```

Just the AST layer (Python files only):

```bash
python3 scripts/code_inspector.py ./path/to/repo --feature ast
```

Add a directory tree on top of any feature:

```bash
python3 scripts/code_inspector.py ./path/to/repo --tree --tree-depth 3
python3 scripts/code_inspector.py ./path/to/repo --feature ast --tree
```

JSON output for pipelines:

```bash
python3 scripts/code_inspector.py ./path/to/repo --format json | jq '.ast.most_complex_files'
```

Cap the scan on a big monorepo:

```bash
python3 scripts/code_inspector.py ./path/to/repo \
    --max-files 2000 --max-depth 5 --max-ast-files 300
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `path` (**required**) | — | Directory to inspect |
| `--feature` | `all` | `overview`, `ast`, or `all` |
| `--tree` | off | Add an ASCII directory tree to the output |
| `--tree-depth N` | `3` | Max tree depth when `--tree` is set |
| `--max-files N` | `5000` | Cap on total files scanned during the walk |
| `--max-depth N` | unlimited | Cap on directory depth walked |
| `--max-ast-files N` | `500` | Cap on `.py` files parsed by the AST feature |
| `--format` | `text` | `text` or `json` |

**Exit code:** `0` on success, `2` on missing / unreadable path.

## Output format

### Text mode — overview

```text
# code-inspector
root:            /home/alice/myproj
feature:         overview
scanned files:   487
scanned dirs:    62
note:            git-tracked file list in use (487 files)

## Languages
ext           files       lines  language
--------------------------------------------------------
.py             240       18432  Python
.md              35        2100  Markdown
.yml              8         320  YAML

## Entry points
  [python] pyproject.toml
  [python] src/myproj/__main__.py
  [docker] Dockerfile

## Frameworks / libraries
  FastAPI   — pyproject.toml/requirements.txt
  Pydantic  — pyproject.toml/requirements.txt
  pytest    — pyproject.toml/requirements.txt

## Tests
  directories:
    tests/
  file patterns:
    test_*.py
  runner configs:
    pytest.ini
```

### Text mode — AST

```text
# code-inspector
root:            /home/alice/myproj
feature:         ast

## Python AST
  python_file_count: 240
  parsed:            240
  totals: classes=48, functions=612, imports=318, modules_with_main=3

  most_complex_files (top 10 by score):
      487  src/myproj/core/pipeline.py  (classes=6, functions=22, max_nesting=6)
      342  src/myproj/io/loader.py      (classes=3, functions=18, max_nesting=5)
      ...

  files:
    src/myproj/core/pipeline.py  [812 lines, 487 stmts, max_nesting=6, has __main__]
      class Pipeline(BaseRunner)  line 24, methods=14, lines=212
      class Stage  line 236, methods=6, lines=48
      def build_pipeline(...)  line 310, args=3 → T, lines=28
      async def run_step(...)  line 340, args=2 → T, lines=15
      imports (12): dataclasses; logging; typing; from .stage import Stage; ...
    ...
```

### JSON mode

```json
{
  "root": "/home/alice/myproj",
  "feature": "all",
  "scanned_files": 487,
  "overview": {
    "languages": [{"extension": ".py", "files": 240, "lines": 18432}],
    "entry_points": [{"path": "pyproject.toml", "kind": "python"}],
    "frameworks": [{"name": "FastAPI", "evidence": "pyproject.toml/requirements.txt"}],
    "tests": {"directories": ["tests"], "file_patterns": ["test_*.py"], "runner_configs": ["pytest.ini"]}
  },
  "ast": {
    "python_file_count": 240,
    "parsed_file_count": 240,
    "skipped": [],
    "totals": {"classes": 48, "functions": 612, "imports": 318, "modules_with_main": 3},
    "most_complex_files": [
      {"path": "src/myproj/core/pipeline.py", "score": 487, "classes": 6, "functions": 22, "max_nesting_depth": 6}
    ],
    "files": [
      {
        "path": "src/myproj/core/pipeline.py",
        "total_lines": 812,
        "total_statements": 487,
        "max_nesting_depth": 6,
        "has_main": true,
        "classes": [
          {"name": "Pipeline", "line": 24, "bases": ["BaseRunner"], "method_count": 14, "methods": ["__init__", "run", "..."], "length": 212}
        ],
        "functions": [
          {"name": "build_pipeline", "line": 310, "arg_count": 3, "is_async": false, "has_return_annotation": true, "length": 28}
        ],
        "imports": [
          {"kind": "from_import", "module": "stage", "names": ["Stage"], "level": 1, "line": 5}
        ]
      }
    ],
    "truncated": false
  }
}
```

## Detection notes

### Overview feature

- **Languages**: ~50 extensions mapped to human-readable names; unknown extensions still counted by file count but not by lines.
- **Entry points**: well-known project-config filenames (`pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`, `pom.xml`, `Dockerfile`, `Makefile`, ...) plus program-entry filenames (`main.py`, `__main__.py`, `index.ts`, `main.rs`, `Main.java`, `Program.cs`) at project root or under `src/` / `app/` / `lib/` / `cmd/`.
- **Frameworks**: parsed from `package.json` dependencies, `pyproject.toml` / `requirements.txt` substring match, and sentinel files (`manage.py` → Django, `go.mod` → Go modules, `Cargo.toml` → Rust).
- **Tests**: well-known test directory names, test file globs, and runner config files.

### AST feature (Python only for now)

- **Classes**: extracted via `ast.ClassDef`. `bases` are rendered via `ast.unparse()` when available (Python 3.9+), falling back to a Name/Attribute walker on 3.8.
- **Functions**: only **top-level** `FunctionDef` / `AsyncFunctionDef` nodes (methods are listed under their class, not double-counted here).
- **Imports**: only **module-level** imports. Imports nested inside classes or functions are intentionally skipped — layer 2 is about the public shape of each module, not every import anywhere. Relative imports (`from .foo import bar`) surface their dot depth in the `level` field.
- **Statement count**: every `ast.stmt` node in the file, anywhere in the tree (includes nested statements). Useful as a rough "how much is happening in this file" signal.
- **Max nesting depth**: tracked by an `ast.NodeVisitor` that counts `If` / `For` / `While` / `Try` / `With` / `AsyncFor` / `AsyncWith` blocks. Helps spot deeply-nested control flow.
- **`has_main`**: true if the file contains a top-level `if __name__ == "__main__":` (handles both orderings).
- **`most_complex_files`**: top-10 ranking by a rough score `3 * classes + 2 * functions + 4 * max_nesting + stmts // 10`. This is **not** a real cyclomatic complexity — it's a cheap proxy for "which files have the most surface area", useful for directing attention, not for quality gates.
- **Caps**: AST feature is capped at `--max-ast-files` (default 500). Files with syntax errors are recorded in `skipped` with their reason and do **not** count against the parsed total.

## Requirements

- Python 3.8+ (3.9+ recommended for richer `ast.unparse()`-based base-class rendering)
- **Standard library only** — no `pip install` anything
- Optional: `git` on PATH (for gitignore-aware walking). Falls back to a hard-coded ignore list when git is missing or the path isn't a git repo.

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.
