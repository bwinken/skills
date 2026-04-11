# Workflow: init — set up a new wiki

**When to run this:** the user wants to start a personal wiki for the first time, or create a second independent wiki (e.g. one for work, one for personal). The trigger is usually one of:

- "Set up a wiki for me"
- "I want to start taking notes with Claude"
- "Create a knowledge base at `<path>`"
- "Initialize a wiki in this folder"

**Prerequisite state:** the target folder either doesn't exist yet, or exists but is empty / doesn't already contain a `SCHEMA.md` from a previous wiki. If the folder already has a wiki, **abort and tell the user** — don't overwrite someone else's wiki.

---

## Step 1 — Ask the user where the wiki should live

Don't guess. Default suggestion is `~/my-wiki/`, but the user may want `~/Documents/wiki/`, `~/work/wiki/`, or any other path. Ask:

> "Where would you like your wiki to live? I suggest `~/my-wiki/`, but any folder works. It'll be a regular directory you can version-control with git."

Also ask:
> "Do you want me to initialize a git repo inside it as well? (recommended — wikis are much safer under version control)"

Remember the answers.

---

## Step 2 — Show the user the default schema and ask for changes

**This is the most important step.** The default schema is Karpathy's structure (see `schema.md` in the skill folder). Show the user the key decisions and ask if any should change:

> "I'll use the following structure by default — this is adapted from Andrej Karpathy's [LLM wiki method](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). Tell me if any of these don't fit your workflow:
>
> **Directories:**
> - `raw/` — where you drop immutable source files (articles, PDFs, notes)
> - `wiki/entities/` — people, companies, products, technologies
> - `wiki/concepts/` — abstract ideas, patterns, theories
> - `wiki/sources/` — one page per source you ingest (summary + takeaways)
> - `wiki/synthesis/` — multi-source comparisons, 'state of X' pages
>
> **Top-level files:**
> - `index.md` — curated table of contents
> - `log.md` — append-only chronological record of every ingest / query / lint
> - `SCHEMA.md` — this schema, copied here so you can edit it
>
> **Page naming:** lowercase, kebab-case, with a `{category}-{name}` prefix for entities (e.g. `tech-bigquery.md`, `person-alice.md`)
>
> **Linking:** standard markdown links (`[text](../concepts/foo.md)`) for everything — works in GitHub, mkdocs, VSCode, and Obsidian alike. No wikilinks.
>
> Does this look right, or would you like to change anything before I create it?"

**Common customizations the user might want:**

- **Rename directories** (e.g. `wiki/people/` + `wiki/orgs/` + `wiki/tech/` instead of one `wiki/entities/` with prefixes). If the user prefers this, the agent must edit their `SCHEMA.md` **before** proceeding so the rest of the workflows read the new structure.
- **Drop or add a top-level category** (e.g. add `wiki/projects/` if they're primarily tracking personal projects).
- **Use a different date format** (Karpathy's is `YYYY-MM-DD` — don't change this lightly, the log parser depends on it).
- **Different page naming convention** (e.g. no category prefix for entity files).

**When the user requests a change**, do **not** silently apply it. Confirm explicitly:

> "OK — so you'd like `wiki/people/` and `wiki/orgs/` instead of one `wiki/entities/` folder with prefixes. I'll update the schema to reflect this before creating the wiki. Confirm?"

Wait for explicit yes before creating anything.

---

## Step 3 — Create the wiki scaffold

Only after the user has confirmed the schema, run:

```bash
python /path/to/skills/llm-wiki/scripts/wiki_init.py <wiki-path> [--git]
```

This script:
1. Creates the target directory and all sub-directories
2. Copies `schema.md` from the skill folder to `<wiki>/SCHEMA.md`
3. If the user asked for custom directory names, the agent should edit `<wiki>/SCHEMA.md` *after* the script runs to reflect the user's choices
4. Creates a stub `index.md` with just `# Wiki index\n\nLast updated: YYYY-MM-DD\n`
5. Creates a stub `log.md` with the init entry: `## [YYYY-MM-DD] Init: wiki created with default schema`
6. If `--git` was passed, runs `git init` and adds a sensible `.gitignore` (ignoring `.DS_Store`, editor swap files, etc.)

The script does **not** commit anything to git — that's the user's decision.

---

## Step 4 — Show the user what was created

After the script succeeds, show the user the resulting tree (e.g. via `ls -R` or a textual listing) and confirm:

> "Done. Your wiki is at `<wiki-path>`. Here's what I created:
>
> ```
> <paste the directory tree>
> ```
>
> The schema is in `<wiki-path>/SCHEMA.md` — that's where future edits to the conventions go. The skill will always read this file before making changes.
>
> Next step: drop a source file into `raw/` (a PDF, an article URL saved as markdown, a note) and ask me to ingest it. Try 'add this to my wiki' with any file.
>
> **Optional:** if you ever want to browse this wiki as a local website (with search, dark mode, nice sidebar, etc.), just ask me to 'set up mkdocs for my wiki' — I'll drop in a pre-configured `mkdocs.yml` and tell you how to `mkdocs serve`. It's completely optional and needs a one-time `pip install mkdocs mkdocs-material`."

---

## Step 5 — Log the init

The script creates the first log entry automatically. No extra action needed here. But confirm to the user that the log is active:

> "I'll keep track of every ingest, query, and cleanup in `log.md`. You can always ask 'what did I add this week?' and I'll scan the log for you."

---

## Common failures

### The target folder already has a `SCHEMA.md`

Abort immediately. Tell the user:

> "The folder `<path>` already contains a `SCHEMA.md` — looks like a wiki is already there. I don't want to overwrite it. Would you like me to:
>
> 1. Pick a different path
> 2. Show you the existing wiki (I'll read the existing `SCHEMA.md`)
> 3. Delete the existing wiki and start fresh (confirm this *very* carefully)"

### The target folder exists and has other files in it

If the folder has random files but no `SCHEMA.md`, the user might be trying to "wiki-ify" an existing notes folder. Ask:

> "This folder already has some files. Do you want to:
>
> 1. Pick an empty folder instead
> 2. Create the wiki structure alongside the existing files (they'll be ignored by the wiki until you manually move them into `raw/` or `wiki/`)
> 3. Import all existing markdown files into `raw/` as 'legacy notes' (I'll ingest them one by one afterwards)"

### The user wants a schema that's very different from the default

If the user wants to dramatically deviate (e.g. "I don't want `concepts/`, just one flat `notes/` folder"), **warn them** that future workflows will assume the standard structure and they may need to re-explain their layout to the agent in every conversation. Then, if they still want to proceed, edit `<wiki>/SCHEMA.md` comprehensively before running any other workflow.

Record the schema changes in the init log entry:

```markdown
## [YYYY-MM-DD] Init: wiki created with custom schema
- **Custom directories**: `notes/` only (no entities/concepts/sources/synthesis split)
- **Rationale**: user prefers a flat structure for personal notes
- **Schema file**: `SCHEMA.md` updated to describe the custom layout
```
