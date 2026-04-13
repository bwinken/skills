---
name: llm-wiki
description: "Maintain a personal, LLM-curated knowledge base (wiki) for the user. Use when the user wants to set up, add to, query, or clean up a long-lived personal wiki — a place where they drop sources and you turn them into a structured, cross-linked collection of entity/concept/synthesis pages. Triggers: 'set up a wiki', 'add this to my wiki', 'what do I know about X', 'clean up my wiki', 'what did I save this week'. Inspired by Andrej Karpathy's LLM wiki method."
compatibility: "Claude Code, Roo Code, Cline"
---

# LLM Wiki

## Overview

This skill turns the agent into a **wiki maintainer** — a long-lived curator of a structured knowledge base that the user owns. The wiki is a regular folder on disk (typically version-controlled) containing:

- **`raw/`** — immutable source files the user drops in (articles, PDFs, notes, clips)
- **`wiki/`** — agent-maintained markdown pages: entities, concepts, sources, syntheses
- **`index.md`** — the curated catalog
- **`log.md`** — append-only chronological record of every ingest / query / lint
- **`SCHEMA.md`** — the user's personalized copy of the schema, which the agent reads before every operation

The value of this skill is **consistency across months and conversations**. A plain "read this PDF and summarize" is a one-shot job. Maintaining a wiki means making the same decisions the same way every time: same directory structure, same frontmatter fields, same naming conventions, same linking patterns. That's what the schema is for, and that's what this skill enforces.

> **Credit:** the directory layout, the append-only log, the "wiki as maintained artifact" framing, and the overall workflow are directly inspired by Andrej Karpathy's gist *["How I create my own LLM wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f)*. This skill packages that method into a schema + workflows + helper scripts an agent can execute consistently.

## When to use

Fire this skill when the user's request is about **maintaining a long-lived, structured knowledge base**:

- **Setup**: "Set up a wiki for me", "Start a knowledge base at `<path>`", "Initialize a wiki"
- **Ingest**: "Add this to my wiki", "Ingest this PDF", "Save this to my notes" (when a wiki exists), "Remember this"
- **Query**: "What do I know about X?", "What have I saved about Y?", "Check my wiki for Z", "Remind me what I wrote about..."
- **Maintenance**: "Clean up my wiki", "Find broken links in my wiki", "What pages are stale?", "Wiki health check"
- **Log inspection**: "What did I add this week?", "Show me my ingest history"

## When NOT to use

- **One-shot summarization** — "summarize this PDF for me, I don't need to save it": use a reader skill (e.g. `pdf-reader`) and let the LLM summarize directly. No wiki needed.
- **Searching a folder of files that isn't a wiki** — use `document-search` instead.
- **Reading a single file** — use the appropriate `*-reader` skill.
- **The user doesn't know what a wiki is and doesn't want one** — don't impose this structure. Ask first.

## The operating model

Before doing **anything** wiki-related, the agent must:

1. **Know the wiki path**. If the user hasn't said where it is, ask. Don't guess.
2. **Read `<wiki>/SCHEMA.md`** once per conversation. This is the personalized schema — the user may have customized directories, naming, frontmatter fields, etc. Always read it before the first operation in a conversation.
3. **Pick a workflow** based on the user's request and follow the corresponding file in `workflows/`:

   | User's intent | Workflow file | Prereq |
   |---|---|---|
   | First-time setup or new wiki | [`workflows/init.md`](workflows/init.md) | None |
   | Add a source (file / URL / paste) | [`workflows/ingest.md`](workflows/ingest.md) | Wiki exists, `SCHEMA.md` read |
   | Answer a question from wiki content | [`workflows/query.md`](workflows/query.md) | Wiki exists, `SCHEMA.md` read |
   | Periodic cleanup | [`workflows/lint.md`](workflows/lint.md) | Wiki exists, `SCHEMA.md` read |
   | Set up mkdocs to browse as a website | [`workflows/mkdocs.md`](workflows/mkdocs.md) | Wiki exists. **Opt-in only** — never set up mkdocs unless the user asks. |

Each workflow file is a step-by-step runbook. Read the whole file before executing, because the workflows are careful about things like "ask before updating", "never delete without confirmation", and "always append to the log".

## Default schema reference

The default schema shipped with this skill is in [`schema.md`](schema.md). It describes:

- §1 Directory layout
- §2 Page naming
- §3 Required frontmatter fields
- §4 Page body templates (entity / concept / source / synthesis)
- §5 `index.md` structure
- §6 `log.md` format (including the `## [YYYY-MM-DD] <Op>: <title>` header pattern used by `wiki_log.py`)
- §7 Wikilinks vs markdown links
- §8 Tagging conventions
- §9 What the agent must never do
- §10 How to extend the schema when ambiguous

When the user runs `init` for the first time, `schema.md` is copied to `<wiki>/SCHEMA.md` — **that's** the file you (the agent) read in future conversations. The user may customize it; respect their version over the default.

## Helper scripts

This skill ships four stdlib-only Python scripts under `scripts/`:

| Script | Purpose | When to call |
|---|---|---|
| `wiki_init.py <path> [--git]` | Scaffold a new wiki (creates directories, copies `schema.md` to `SCHEMA.md`, seeds `index.md` / `log.md`) | Once, during the init workflow |
| `wiki_log.py <path> [--tail N] [--op ingest\|query\|lint] [--since DATE] [--until DATE]` | Parse `log.md` and return filtered entries as text or JSON | Whenever the user asks a temporal question, or the lint workflow wants ingest history |
| `wiki_lint.py <path> [--mode all\|broken-links\|orphans\|frontmatter\|stale\|unref-sources] [--stale-days 180]` | Deterministic health checks; returns findings but never modifies the wiki | The lint workflow. Also useful as a sanity check after any large rename. |
| `wiki_mkdocs_setup.py <path> [--force]` | Copy the bundled `mkdocs.yml` template to the wiki root so the user can run `mkdocs serve` / `mkdocs build`. Checks whether `mkdocs` / `mkdocs-material` are installed. | **Only when the user asks** — part of the opt-in mkdocs workflow. |

All three scripts accept `--format text|json`. For agent-to-agent pipelines prefer JSON.

> **How to invoke these scripts** — read this **before running**.
>
> 1. **Use the absolute path.** Your working directory is the user's
>    workspace, not the skill folder. Bare `wiki_init.py ...` or
>    `python scripts/wiki_init.py ...` will fail. The real path is
>    wherever **this SKILL.md** is loaded from. Substitute the install
>    location that matches the user's agent / scope:
>
>    | Agent       | Global                     | Workspace                            |
>    |-------------|----------------------------|--------------------------------------|
>    | Claude Code | `~/.claude/skills/llm-wiki/` | `<cwd>/.claude/skills/llm-wiki/`   |
>    | Roo Code    | `~/.roo/skills/llm-wiki/`    | `<cwd>/.roo/skills/llm-wiki/`      |
>    | Cline       | `~/.cline/skills/llm-wiki/`  | `<cwd>/.cline/skills/llm-wiki/`    |
>
> 2. **Pick the right Python command.** Use `python` on Windows, `python3`
>    on macOS / Linux. On Windows you can also use `py -3`.
>
> Concrete example — scaffold a new wiki:
>
> ```bash
> python ~/.claude/skills/llm-wiki/scripts/wiki_init.py ~/my-wiki --git
> ```

## Recommended companion skills

This skill works best when paired with the following, but doesn't require any of them:

- **`document-search`** — for Step 4 of `workflows/ingest.md` (finding existing wiki pages related to a new source) and for `workflows/query.md`. Without it, fall back to the agent's built-in Grep.
- **`pdf-reader` / `docx-reader` / `xlsx-reader` / `pptx-reader`** — for Step 1 of `workflows/ingest.md` when the source is an Office or PDF file. Without them, the agent's built-in file-reading may still handle plain text and markdown; Office/PDF ingest will need either these skills or an external extraction step.

If a companion isn't installed, gracefully degrade — don't pretend it's there.

## Wiki location

The wiki lives **outside** the skill folder. Typical locations:

- `~/my-wiki/` (Karpathy's default)
- `~/Documents/wiki/`
- `~/work/wiki/` and `~/personal/wiki/` (two wikis for different contexts)

The skill itself is stateless — all user data lives in the user's wiki folder. This means the skill can be uninstalled and reinstalled without touching the wiki. It also means multiple wikis can coexist; the agent just needs to know which one the user is asking about.

## Critical rules (from schema.md §9, restated)

Never do these without explicit user confirmation:

1. Modify or delete anything in `raw/`
2. Edit past entries in `log.md` (append-only)
3. Rename a file without updating all inbound markdown links
4. Overwrite `<wiki>/SCHEMA.md` with the skill's default schema
5. Commit to git automatically
6. Write to a wiki location that doesn't contain a `SCHEMA.md` — abort and ask the user to run `wiki_init.py` first

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace (bundle with the other `knowledge-tools` skills), and manual install paths for Claude Code / Roo Code / Cline.

## Quick-start narrative for the agent

The first time a user asks you to "set up a wiki":

1. Read `workflows/init.md`. Follow it step by step.
2. Ask the user where the wiki should live and whether to use git.
3. Show them the default schema (summarize `schema.md` — don't paste the whole thing).
4. Wait for their confirmation or customization request.
5. Run `wiki_init.py` with the confirmed path.
6. Tell them what was created and suggest a first action.

The next time the user mentions "my wiki" or "add this":

1. Read `<wiki>/SCHEMA.md` (their schema).
2. Pick the right workflow file based on the verb.
3. Follow it.

Treat every new conversation as a fresh one — always re-read `SCHEMA.md`.
