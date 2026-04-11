# code-inspector

> Structural inspection of a codebase — language/LOC breakdown, entry points, frameworks, test layout, **plus** Python AST analysis (classes, functions, imports, complexity, most-complex-files ranking). Stdlib only; read-only; gitignore-aware.

Codebase-side analog of the `document-inspector` plugin. When an agent joins a new repository it usually wastes tokens doing `ls` and `cat` to figure out the shape of the project, then wastes even more tokens reading file after file trying to find "the important ones". This skill produces a single structured, agent-ready report in one call — and, for Python code, walks the stdlib `ast` module to list every class, every top-level function, every import, and rank the most complex files.

Two feature tiers:

- **`overview`** — layer 1: stdlib-only, seconds to run. Language + LOC breakdown, entry points, frameworks, test layout.
- **`ast`** — layer 2: Python-only AST analysis. Classes (with bases, methods, length), top-level functions (args, async, return annotation, length), imports (with relative-import depth), statement count, max nesting depth, `__main__` detection, most-complex-files ranking.

`all` runs both. Directory tree (`--tree`) is an orthogonal toggle you can add on top of any feature.

---

## Requirements

- **Python 3.8+** (3.9+ recommended for richer base-class rendering via `ast.unparse`)
- **Standard library only** — no `pip install` anything
- Optional: `git` on PATH for gitignore-aware walking (falls back to a hard-coded ignore list otherwise)

---

## Installation

### Claude Code — plugin marketplace

```text
/plugin marketplace add bwinken/skills
/plugin install code-inspector@skills
```

### Other agents — install.py wizard

```bash
python install.py install code-inspector --agent claude   # or roo, cline
```

### Manual install

Copy this folder into the right directory for your agent:

- **Claude Code**: `~/.claude/skills/code-inspector/` (global) or `./.claude/skills/code-inspector/` (workspace)
- **Roo Code**: `~/.roo/skills/code-inspector/` or `./.roo/skills/code-inspector/`
- **Cline**: `~/.cline/skills/code-inspector/` or `./.cline/skills/code-inspector/`

---

## Usage

### Basic — full inspection (overview + AST)

```bash
python3 scripts/code_inspector.py ./path/to/repo
```

### Only overview (fast, no AST parsing)

```bash
python3 scripts/code_inspector.py ./path/to/repo --feature overview
```

### Only AST (Python files only)

```bash
python3 scripts/code_inspector.py ./path/to/repo --feature ast
```

### With a directory tree

```bash
python3 scripts/code_inspector.py ./path/to/repo --tree --tree-depth 3
```

### JSON output for pipelines

```bash
python3 scripts/code_inspector.py ./path/to/repo --format json | jq '.ast.most_complex_files'
```

### Bounded scan for monorepos

```bash
python3 scripts/code_inspector.py ./path/to/repo \
    --max-files 2000 --max-depth 5 --max-ast-files 300
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `path` (**required**) | — | Directory to inspect |
| `--feature` | `all` | `overview`, `ast`, or `all` |
| `--tree` | off | Add an ASCII directory tree to the output |
| `--tree-depth N` | `3` | Max tree depth when `--tree` is set |
| `--max-files N` | `5000` | Cap on total files scanned during the walk |
| `--max-depth N` | unlimited | Cap on directory depth walked |
| `--max-ast-files N` | `500` | Cap on `.py` files parsed for the AST feature |
| `--format` | `text` | `text` or `json` |

---

## Output format

### Text — overview

```text
# code-inspector
root:            /home/alice/myproj
feature:         overview
scanned files:   487
note:            git-tracked file list in use (487 files)

## Languages
ext           files       lines  language
.py             240       18432  Python
.md              35        2100  Markdown

## Entry points
  [python] pyproject.toml
  [docker] Dockerfile

## Frameworks / libraries
  FastAPI   — pyproject.toml/requirements.txt
  pytest    — pyproject.toml/requirements.txt

## Tests
  directories:
    tests/
  file patterns:
    test_*.py
  runner configs:
    pytest.ini
```

### Text — AST

```text
## Python AST
  python_file_count: 240
  parsed:            240
  totals: classes=48, functions=612, imports=318, modules_with_main=3

  most_complex_files (top 10 by score):
      487  src/myproj/core/pipeline.py  (classes=6, functions=22, max_nesting=6)
      342  src/myproj/io/loader.py      (classes=3, functions=18, max_nesting=5)

  files:
    src/myproj/core/pipeline.py  [812 lines, 487 stmts, max_nesting=6, has __main__]
      class Pipeline(BaseRunner)  line 24, methods=14, lines=212
      class Stage  line 236, methods=6, lines=48
      def build_pipeline(...)  line 310, args=3 → T, lines=28
      async def run_step(...)  line 340, args=2 → T, lines=15
      imports (12): dataclasses; logging; typing; from .stage import Stage; ...
```

### JSON mode

```json
{
  "root": "/home/alice/myproj",
  "feature": "all",
  "overview": {
    "languages": [{"extension": ".py", "files": 240, "lines": 18432}],
    "entry_points": [{"path": "pyproject.toml", "kind": "python"}],
    "frameworks": [{"name": "FastAPI", "evidence": "pyproject.toml/requirements.txt"}],
    "tests": {"directories": ["tests"], "file_patterns": ["test_*.py"]}
  },
  "ast": {
    "python_file_count": 240,
    "parsed_file_count": 240,
    "totals": {"classes": 48, "functions": 612, "imports": 318, "modules_with_main": 3},
    "most_complex_files": [
      {"path": "src/myproj/core/pipeline.py", "score": 487, "classes": 6, "functions": 22, "max_nesting_depth": 6}
    ],
    "files": [
      {
        "path": "src/myproj/core/pipeline.py",
        "total_lines": 812,
        "max_nesting_depth": 6,
        "has_main": true,
        "classes": [
          {"name": "Pipeline", "bases": ["BaseRunner"], "method_count": 14, "length": 212}
        ]
      }
    ]
  }
}
```

---

## Examples

### Example 1 — first-pass exploration of an unfamiliar repo

```bash
python3 scripts/code_inspector.py ~/src/some-cloned-repo
```

You get the language breakdown, detected frameworks, test layout, **and** a full Python AST map (classes, functions, most-complex files) in one call — enough context to decide which files to read first without blindly wandering through the codebase.

### Example 2 — find the biggest files in a Python project

```bash
python3 scripts/code_inspector.py . --feature ast --format json \
  | jq '.ast.most_complex_files'
```

Top-10 ranking by a rough complexity score: more classes, more functions, deeper nesting, more statements → higher score.

### Example 3 — list all the classes in this project

```bash
python3 scripts/code_inspector.py . --feature ast --format json \
  | jq '[.ast.files[] | {path, classes: [.classes[].name]}]'
```

Dump every class name keyed by the file it lives in.

### Example 4 — framework detection only

```bash
python3 scripts/code_inspector.py . --feature overview --format json \
  | jq '.overview.frameworks'
```

### Example 5 — tree of a monorepo with tight bounds

```bash
python3 scripts/code_inspector.py ./monorepo --tree --tree-depth 2 --feature overview
```

---

## How it works

1. **Walk** — when a `.git/` is present, shell out to `git ls-files` to honor `.gitignore`. Otherwise fall back to a conservative hard-coded ignore list (`node_modules`, `venv`, `build`, `dist`, `__pycache__`, `.mypy_cache`, ...). The walk is capped by `--max-files` and `--max-depth`.
2. **Overview** — for every tracked file: bucket by extension, count lines for known source extensions, detect entry-point filenames, parse `package.json` / `pyproject.toml` / `requirements.txt` for framework signals, match test directory names / file globs / runner configs.
3. **AST** — for every `.py` file (up to `--max-ast-files`): read the source, `ast.parse()` it, walk the tree:
   - Top-level `ClassDef` / `FunctionDef` / `AsyncFunctionDef` → per-class and per-function records with bases, methods, args, return annotation, and length
   - Top-level `Import` / `ImportFrom` → imports with relative-depth
   - `ast.walk()` → statement count
   - `NodeVisitor` over block statements → max nesting depth
   - `if __name__ == "__main__":` → main-module detection
   - Files with syntax errors are recorded in `skipped` with their reason, never crash the run
4. **Most-complex ranking** — files ranked by a rough proxy score (`3*classes + 2*functions + 4*max_nesting + stmts//10`), top 10.

AST analysis is deliberately **module-level, file-level, and Python-only**:

- No call graph (unreliable in dynamic languages)
- No type inference or cross-file resolution
- No docstring extraction (that's a reader's job)
- No non-Python AST (planned: layer 3 via `tree-sitter-languages`)

---

## See also

- [SKILL.md](SKILL.md) — agent-facing definition
- [document-search](../document-search/) — when you need to search file *contents*, not map structure
- [pdf-inspector](../pdf-inspector/) / [docx-inspector](../docx-inspector/) / [xlsx-inspector](../xlsx-inspector/) — the document-side analogs (single files)
- [ROADMAP.md](../../ROADMAP.md) — design notes, including layer 3 (non-Python AST) and the planned `code-review` skill
