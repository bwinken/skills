# Skills

This directory holds every skill in the repo. Each subfolder is a self-contained skill that can be dropped into Claude Code, Roo Code, or Cline.

## Index

### `document-search` plugin

| Skill | Description |
|-------|-------------|
| [document-search](document-search/) | Search a folder for a term and return a ranked list of files that contain it — **including inside `.docx`, `.pptx`, `.xlsx`, and `.pdf`** where ordinary grep/rg are blind. Handles mixed-format folders in one pass. |

### `document-readers` plugin

One skill per format — install them individually or all at once via the `document-readers` plugin.

| Skill | Description | Dependency |
|-------|-------------|------------|
| [pdf-reader](pdf-reader/) | Extract text from a PDF file, with optional page-range selection (`--pages 1-5`). | `pypdf` |
| [docx-reader](docx-reader/) | Extract text from a Word document — paragraphs and tables. | `python-docx` |
| [xlsx-reader](xlsx-reader/) | Extract Excel content as GitHub-flavored markdown tables, one per sheet. | `openpyxl` |
| [pptx-reader](pptx-reader/) | Extract text from a PowerPoint deck, with optional slide-range selection (`--slides 1-5`). | `python-pptx` |

Together with `document-search` these five skills cover the **文書工作 (office workflow)** core loop: **find** the right file, then **read** it with the matching reader. Pair them with the `document-inspector` plugin (below) when you also need structural facts — metadata, tracked changes, form fields, formula dependencies.

### `knowledge-tools` plugin

Longer-lived knowledge management — turning sources into a structured, maintained wiki.

| Skill | Description | Dependency |
|-------|-------------|------------|
| [llm-wiki](llm-wiki/) | Turn the agent into the maintainer of a personal wiki. Ships a schema, four workflows (init / ingest / query / lint), and three stdlib helper scripts. Inspired by [Andrej Karpathy's LLM wiki method](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). | *(none — stdlib only)* |

### `document-organizer` plugin

Safe, destructive-aware folder organization.

| Skill | Description | Dependency |
|-------|-------------|------------|
| [document-organizer](document-organizer/) | Four modes in one skill: **classify** by content, **by-metadata** (group by mtime/extension), **dedup** (find duplicates by hash), **rename** (batch-rename from content). Unified scan → plan → execute → undo pipeline, dry-run by default, per-folder state file, undo log on every real execute. | *(none — stdlib only)* |

### `document-inspector` plugin

Structural counterpart to `document-readers`: returns the deterministic facts an LLM can't derive from rendered text. One skill per format, bundled together.

| Skill | Description | Dependency |
|-------|-------------|------------|
| [pdf-inspector](pdf-inspector/) | Inspect a PDF — metadata (title / author / dates / encryption / page size / PDF version) and AcroForm field inventory (names, types, values, required/read-only flags, signature fields). | `pypdf` |
| [docx-inspector](docx-inspector/) | Inspect a Word document — core properties, **tracked changes** (every `w:ins` / `w:del` with author, timestamp, text), and heading-hierarchy outline with skipped-level detection. | `python-docx` |
| [xlsx-inspector](xlsx-inspector/) | Inspect an Excel workbook — properties, per-sheet dimensions, **formula dependency graph** (cross-sheet references, formula density per sheet), and named-range inventory with scope. | `openpyxl` |

The readers answer *"what does this document say?"*; the inspectors answer *"what are the facts about this document that the text itself can't tell you?"* — who wrote it, what forms it has, who tracked-changed what, which formulas flow across sheets, which named ranges exist. Install both plugins together to cover the full read-plus-inspect loop.

### `code-tools` plugin

Understanding codebases — the code-side equivalent of the document plugins.

| Skill | Description | Dependency |
|-------|-------------|------------|
| [code-inspector](code-inspector/) | Map a codebase — **overview** tier (language + LOC breakdown, entry points, framework detection, test layout) **plus Python AST** tier (per-file classes with bases/methods/length, top-level functions with args and return annotations, imports with relative-depth, statement count, max nesting depth, `__main__` detection, aggregate totals, top-10 most-complex-files ranking). Gitignore-aware walk. Stdlib only; read-only. | *(none — stdlib only)* |

Plans for a `code-review` skill (diff + linter orchestration) and non-Python AST via `tree-sitter-languages` live in [ROADMAP.md](../ROADMAP.md).

Want to contribute one? See [CONTRIBUTING.md](../CONTRIBUTING.md).

## Adding a new skill

See the top-level [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution guide, or the quick version:

```bash
mkdir -p skills/<skill-name>/scripts
cp template/SKILL.md     skills/<skill-name>/SKILL.md
cp template/README.md    skills/<skill-name>/README.md
cp template/_preflight.py skills/<skill-name>/scripts/_preflight.py
# ... implement scripts/, fill in SKILL.md + README.md,
# then register the plugin in .claude-plugin/marketplace.json ...
```

## Layout of a skill folder

```
skills/<skill-name>/
├── SKILL.md       # Agent-facing definition (frontmatter + usage + options)
├── README.md      # Human-facing GitHub page
└── scripts/       # Implementation (Python, shell, Node, ...)
    ├── <entry>.py
    └── _preflight.py  # optional: bilingual install guide for missing deps
```
