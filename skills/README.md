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

Together these five skills cover the **文書工作 (office workflow)** core loop: **find** the right file with `document-search`, then **read** it with the appropriate reader. The LLM itself handles the analysis step on top of the extracted text.

### `knowledge-tools` plugin

Longer-lived knowledge management — turning sources into a structured, maintained wiki.

| Skill | Description | Dependency |
|-------|-------------|------------|
| [llm-wiki](llm-wiki/) | Turn the agent into the maintainer of a personal wiki. Ships a schema, four workflows (init / ingest / query / lint), and three stdlib helper scripts. Inspired by [Andrej Karpathy's LLM wiki method](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). | *(none — stdlib only)* |

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
