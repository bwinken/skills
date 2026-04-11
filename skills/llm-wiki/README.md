# llm-wiki

> Turn your AI coding agent into the maintainer of a long-lived, structured personal knowledge base.

`llm-wiki` is the first skill in the `knowledge-tools` plugin. It's a **workflow orchestration** skill rather than a single-tool script — it ships a design schema, four step-by-step workflows (init / ingest / query / lint), and three stdlib-only helper scripts that let Claude Code, Roo Code, or Cline maintain a personal wiki consistently across months and conversations.

> **Inspired by Andrej Karpathy's gist *["How I create my own LLM wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)*.** The directory layout (`raw/` + `wiki/entities|concepts|sources|synthesis/` + `index.md` + `log.md`), the append-only log, and the "LLM as wiki curator" framing are all his. This skill packages those ideas as a concrete, reusable, agent-executable spec. Highly recommended reading before using this skill — the gist explains the *why*; this skill implements the *how*.

---

## What is a "wiki" here?

A folder on your disk — typically version-controlled with git — that holds your accumulated knowledge on whatever topics matter to you. Not a SaaS product, not an Obsidian vault (though you can absolutely use it with Obsidian), not a database. Just markdown files in a structured layout:

```
~/my-wiki/
├── SCHEMA.md           # Your personalized schema — the agent reads this first
├── index.md            # Curated table of contents
├── log.md              # Append-only chronological record of every operation
├── raw/                # Immutable source files (articles, PDFs, clippings)
│   └── assets/
└── wiki/
    ├── entities/       # People, companies, products, technologies
    ├── concepts/       # Abstract ideas, patterns, theories
    ├── sources/        # One page per ingested source — summary + takeaways
    └── synthesis/      # Multi-source comparisons and overviews
```

The **agent** is the curator. The **user** drops sources into `raw/` and asks questions. The **schema** (`SCHEMA.md`) keeps the agent consistent across conversations so your wiki doesn't turn into inconsistent garbage after a few months.

---

## What this skill does

Four workflows, each a step-by-step runbook the agent follows:

| Workflow | Triggered by | What happens |
|---|---|---|
| **init** | "Set up a wiki for me" | Agent asks where to put it, shows you the default Karpathy-inspired schema, lets you customize, then scaffolds directories / `SCHEMA.md` / `index.md` / `log.md` / (optional) git repo |
| **ingest** | "Add this to my wiki" | Agent reads the source, proposes a summary, finds related existing pages, proposes updates and new pages, waits for your approval, executes confirmed actions, logs the ingest |
| **query** | "What do I know about X?" | Agent reads `index.md` + searches page titles / bodies / source pages, synthesizes an answer with explicit citations back to wiki pages, optionally files the synthesis as a new `synthesis/` page |
| **lint** | "Clean up my wiki" | Agent runs deterministic checks (broken links, orphan pages, missing frontmatter, stale pages, uncited sources), proposes auto-fixes for mechanical issues, reports judgment-call findings for your review |

The **key design decision**: at every step where the agent might change existing content, it **proposes first and waits for confirmation**. No silent auto-updates. This keeps you in control of your own knowledge base.

---

## Repository layout of the skill

```
skills/llm-wiki/
├── SKILL.md                 # Agent entry point (what triggers the skill)
├── README.md                # This file (human-facing)
├── schema.md                # The default wiki design: dirs, frontmatter, naming, templates
├── workflows/
│   ├── init.md              # Step-by-step: set up a new wiki
│   ├── ingest.md            # Step-by-step: add a source
│   ├── query.md              # Step-by-step: answer a question from the wiki
│   └── lint.md              # Step-by-step: periodic cleanup
└── scripts/
    ├── wiki_init.py         # Scaffold a new wiki folder
    ├── wiki_log.py          # Parse / filter log.md
    ├── wiki_lint.py         # Deterministic health checks (read-only)
    └── _preflight.py        # Missing-dependency install guide helper
```

Nothing here depends on third-party Python packages — everything is stdlib. The workflows optionally use companion skills (`document-search` and the `document-readers` suite) for richer file handling, but they degrade gracefully if those aren't installed.

---

## Requirements

- **Python 3.8+** (standard library only)
- **One of**: Claude Code, Roo Code, or Cline (any agent that auto-discovers skills from a standard folder)
- **Optional but recommended**:
  - `git` — so you can version-control your wiki
  - `document-search` skill — for finding existing wiki pages during ingest / query
  - `pdf-reader` / `docx-reader` / `xlsx-reader` / `pptx-reader` skills — for reading Office/PDF sources

---

## Install

```bash
# Interactive wizard (recommended — picks agent + scope)
python install.py

# Or directly
python install.py install llm-wiki --agent claude
```

See the [root README](../../README.md#installation) for the full story: one-file installer without `git clone`, Claude Code plugin marketplace (`knowledge-tools` bundle), Roo Code and Cline setup, workspace vs global scope, and manual install paths.

---

## Usage

### First-time setup

In your agent, say:

> "Set up a personal wiki for me at `~/my-wiki`."

The agent will:
1. Read `skills/llm-wiki/workflows/init.md`
2. Ask you to confirm the path and the default schema
3. Run `wiki_init.py` to scaffold the folders
4. Show you what was created and suggest a first ingest

### Add a source

```
> I saved an interesting article at ~/Downloads/karpathy_llm_wiki.md.
> Add it to my wiki.
```

The agent will:
1. Read your `~/my-wiki/SCHEMA.md` (the schema)
2. Copy the source to `~/my-wiki/raw/2026-04-11-karpathy-llm-wiki.md`
3. Read the content and propose a summary
4. Search your existing wiki for related pages and propose updates
5. Wait for your approval on each proposed change
6. Create the source page and any new entity/concept pages
7. Update `index.md` and append to `log.md`
8. Tell you exactly what happened

### Query your wiki

```
> What do I know about retrieval-augmented generation?
```

The agent will:
1. Read your `SCHEMA.md`
2. Search `index.md`, page titles, and page bodies
3. Synthesize an answer citing specific wiki pages as markdown links (`[title](wiki/sources/...md)`)
4. Optionally offer to file the synthesis as a new `wiki/synthesis/` page

### Clean up periodically

```
> Run a lint pass on my wiki.
```

The agent will:
1. Run `wiki_lint.py` to find broken links, orphan pages, stale pages, etc.
2. Auto-fix trivial mechanical issues (with your approval)
3. Report judgment-call findings for you to review
4. Log the lint pass to `log.md`

---

## Helper scripts (direct invocation)

You can also run the helper scripts directly — useful for scripting, cron jobs, or debugging. Each supports `--help`.

### `wiki_init.py` — scaffold a new wiki

```bash
python ~/.claude/skills/llm-wiki/scripts/wiki_init.py ~/my-wiki --git
```

Creates the directory layout, copies `schema.md` to `~/my-wiki/SCHEMA.md`, seeds `index.md` and `log.md`, optionally initializes a git repo.

### `wiki_log.py` — read the append-only log

```bash
# All entries
python ~/.claude/skills/llm-wiki/scripts/wiki_log.py ~/my-wiki

# Last 5 ingests
python ~/.claude/skills/llm-wiki/scripts/wiki_log.py ~/my-wiki --op ingest --tail 5

# Everything in the last month
python ~/.claude/skills/llm-wiki/scripts/wiki_log.py ~/my-wiki --since 2026-03-11

# JSON for piping
python ~/.claude/skills/llm-wiki/scripts/wiki_log.py ~/my-wiki --format json | jq '.entries[].title'
```

### `wiki_lint.py` — deterministic health checks

```bash
# Run all checks
python ~/.claude/skills/llm-wiki/scripts/wiki_lint.py ~/my-wiki

# Just broken links
python ~/.claude/skills/llm-wiki/scripts/wiki_lint.py ~/my-wiki --mode broken-links

# Use a stricter staleness threshold (90 days instead of 180)
python ~/.claude/skills/llm-wiki/scripts/wiki_lint.py ~/my-wiki --mode stale --stale-days 90

# JSON for pipelines
python ~/.claude/skills/llm-wiki/scripts/wiki_lint.py ~/my-wiki --format json
```

Exit codes: `0` clean / info only, `1` warnings or errors found, `2` script error (e.g. no wiki at path).

### `wiki_mkdocs_setup.py` — optional, browse the wiki as a website

```bash
# Drop a mkdocs.yml into the wiki so it can be built as a static site
python ~/.claude/skills/llm-wiki/scripts/wiki_mkdocs_setup.py ~/my-wiki
```

See the **Browse your wiki as a website (optional)** section below for the full story.

---

## Browse your wiki as a website (optional)

The wiki is plain markdown on purpose — you can read and edit it with any editor. But if you want search, dark mode, a nice sidebar, or the ability to publish it as a website, you can turn it into a **mkdocs** site in one command. This is completely optional and the default `init` workflow does **not** set it up.

**When you want it**, just ask the agent:

```
> Set up mkdocs for my wiki.
```

The agent will follow [`workflows/mkdocs.md`](workflows/mkdocs.md) which:

1. Confirms what will happen (writes a `mkdocs.yml` into your wiki; doesn't touch the markdown)
2. Runs `wiki_mkdocs_setup.py` to copy the bundled `mkdocs.yml` template
3. Checks whether `mkdocs` and `mkdocs-material` are already installed
4. Prints next-step commands for you
5. Appends a log entry

You then install the two Python packages once:

```bash
pip install mkdocs mkdocs-material
```

And either **preview live** or **build a static site**:

```bash
cd ~/my-wiki

# Live preview at http://127.0.0.1:8000 (auto-reloads when you edit)
mkdocs serve

# Build a static site into ./site/
mkdocs build
```

The `site/` folder is self-contained HTML — deploy it to GitHub Pages, Netlify, Cloudflare Pages, or any static host. Or just open `site/index.html` in a browser to read locally.

### What gets included in the site?

The bundled `mkdocs.yml` configures mkdocs to read the **entire wiki folder** with `docs_dir: .`, so all your `wiki/entities/`, `wiki/concepts/`, `wiki/sources/`, `wiki/synthesis/`, and top-level `index.md` get turned into pages. Files that **don't** show up in the site:

- `raw/` — immutable source files (PDFs, clippings). These stay in the repo but aren't rendered.
- `SCHEMA.md` — the agent's reference, not meant for readers.
- `mkdocs.yml` itself, `.git/`, `.gitignore`, `site/` (the build output), `.trash/` (lint move target)

You can edit `mkdocs.yml` freely — it's your config, not the skill's. Common customizations:

- **Change `site_name`** from "My Wiki" to whatever you want
- **Change the theme palette** (primary color, dark mode default)
- **Add plugins** like `mkdocs-glightbox` for image lightboxes, `mkdocs-git-revision-date-localized-plugin` to show "last updated" dates

### Why the default `init` doesn't set this up

Two reasons:

1. **mkdocs is a Python package the user has to install.** We don't want to assume anyone who wants a wiki also wants mkdocs, or has `pip install` permission.
2. **Not everyone needs a website.** For many users, browsing markdown files in VSCode or Obsidian is enough. mkdocs is for when you want search, publish, or share with others.

So we leave it off by default, and the agent only sets it up when you explicitly ask.

### Why does this work with our markdown link style?

Because our default link style is **standard markdown links with relative paths** (`[text](path.md)`), not Obsidian-style `[[wikilinks]]`. mkdocs natively understands relative markdown links and converts them into correct HTML anchors during `build`. No plugins needed. This is exactly why we chose markdown links in [`schema.md` §7](schema.md).

---

## Customizing the schema

The default schema lives in `schema.md` in this skill folder. **Never edit that directly for a specific wiki** — instead, the first-time `init` workflow copies it to `<wiki>/SCHEMA.md`, and that's your personal copy to edit.

Common customizations:

- **Rename directories** — e.g. `wiki/people/` + `wiki/orgs/` instead of one `wiki/entities/` with prefixes
- **Drop categories** — maybe you don't need `synthesis/` and prefer to keep everything in `concepts/`
- **Add categories** — a `wiki/projects/` folder for personal projects, or `wiki/decisions/` for ADRs
- **Change frontmatter fields** — add a `confidence:` or `priority:` field to every page
- **Different linking style** — the default is already standard markdown links, but you could opt into wikilinks if you're 100% Obsidian (not recommended)

Any customization lives in `<wiki>/SCHEMA.md`. The skill's own `schema.md` is a starting template; the user's `SCHEMA.md` is the source of truth from day two onwards.

---

## Why this skill is different from the other ones in the repo

The other skills in this repo (`document-search`, `pdf-reader`, etc.) are **tools** — deterministic scripts the agent invokes to produce structured data. They're mostly script, a little documentation.

`llm-wiki` is mostly **documentation**. The three helper scripts do the mechanical work (scaffold, parse log, run health checks), but 80% of the skill's value is in `schema.md` and the four `workflows/*.md` files — those are what the agent reads to behave consistently. Without them, the scripts are just a file-creation tool and a markdown parser.

This is a deliberate design choice. Karpathy's gist has almost no code either — the intelligence is in the method. This skill bets that the method, written as clear runbooks, is what makes the difference between "a folder of markdown files" and "a wiki that stays coherent for years".

---

## Credit

Andrej Karpathy, *["How I create my own LLM wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)*. If this skill is useful to you, his gist is the source material — read it. Much of what this skill does is a direct adaptation of his approach.

---

## See also

- [SKILL.md](SKILL.md) — agent-facing skill definition (workflow dispatch)
- [schema.md](schema.md) — the full default wiki design (directories, frontmatter, naming, templates)
- [workflows/init.md](workflows/init.md), [workflows/ingest.md](workflows/ingest.md), [workflows/query.md](workflows/query.md), [workflows/lint.md](workflows/lint.md) — step-by-step runbooks
- Companion skills: [document-search](../document-search/), [pdf-reader](../pdf-reader/), [docx-reader](../docx-reader/), [xlsx-reader](../xlsx-reader/), [pptx-reader](../pptx-reader/)
- [Root README](../../README.md)
- [CONTRIBUTING](../../CONTRIBUTING.md) — how to add your own skill
