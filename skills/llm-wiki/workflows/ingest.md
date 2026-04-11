# Workflow: ingest — add a new source to the wiki

**When to run this:** the user wants to file something into their wiki. The trigger is usually one of:

- "Add this PDF to my wiki"
- "Ingest this article: `<path or URL>`"
- "File this under my wiki"
- "Save this to my notes" (when a wiki exists)
- "Remember this for later" (with a source attached)

**Prerequisite state:** a wiki exists at a known path, and its `SCHEMA.md` has been read by the agent in this conversation. If the user hasn't told you where their wiki is, ask. If they don't have one, run `workflows/init.md` first.

---

## Step 0 — Read the wiki's schema

**Always** read `<wiki>/SCHEMA.md` before doing any ingest. The user may have customized it since the last time you looked. This is cheap (a single file read) and prevents schema drift.

---

## Step 1 — Identify and stage the raw source

The source can be:

- A **local file** (PDF, Word doc, markdown, text file, image)
- A **URL** (article, gist, paper, YouTube video, etc.)
- **Inline content** the user pasted into the conversation

### If it's a local file

Copy (don't move) the file into `<wiki>/raw/` with a date-prefixed filename: `raw/YYYY-MM-DD-<slug>.<ext>`. Example:

```
~/Downloads/karpathy_wiki.pdf  →  ~/my-wiki/raw/2026-04-11-karpathy-wiki.pdf
```

Use `shutil.copy2` (or the agent's built-in file-copy) — **do not move** the original. The user's source remains where it was.

If the file is a PDF / docx / xlsx / pptx and the user has the corresponding reader skill (`pdf-reader` / `docx-reader` / etc.) installed, **use it** to extract the text content for the summary. If those skills aren't installed, fall back to the agent's built-in file-reading tool.

### If it's a URL

Ideally, save a clean-text snapshot of the URL into `raw/` as well (using the agent's web-fetch tool, or a tool like [Obsidian Web Clipper](https://obsidian.md/clipper) if the user has it set up). The raw snapshot protects against link rot.

Save as: `raw/YYYY-MM-DD-<domain>-<slug>.md`. Example:

```
raw/2026-04-11-gist-github-karpathy-llm-wiki.md
```

### If it's inline content

Save the pasted content verbatim to `raw/YYYY-MM-DD-<user-supplied-name>.md` with a note at the top indicating it was pasted inline.

### Confirm with the user

Before moving on, tell the user where the raw file landed:

> "I've saved the source as `raw/2026-04-11-karpathy-llm-wiki.md`. That copy is now immutable — I'll synthesize from it into the wiki next."

---

## Step 2 — Read the source and discuss it

Actually read the staged raw file (or the extracted text if it was a PDF/docx). Form 3–5 key takeaways.

**Discuss with the user first**, don't immediately write the summary:

> "I've read it. The main takeaways look like:
> 1. <takeaway 1>
> 2. <takeaway 2>
> 3. <takeaway 3>
>
> Is there anything you specifically want me to capture that I didn't list? Any angle I should emphasize?"

This step matters — the user often has a specific reason for saving something, and the agent's default summary may miss it. Wait for the user's feedback before writing the source page.

---

## Step 3 — Create the source page

Following the `source` page template in `schema.md`, create `<wiki>/wiki/sources/YYYY-MM-DD-<slug>.md`:

```markdown
---
title: "<human-readable title>"
kind: source
created: YYYY-MM-DD
updated: YYYY-MM-DD
source_type: <article | paper | gist | video | doc | book | conversation>
source_url: "<URL if applicable>"
raw_file: "raw/YYYY-MM-DD-<slug>.<ext>"
author: "<author name>"
published: YYYY-MM-DD
---

# <title>

## Summary
<1 paragraph — written after discussion with the user>

## Key takeaways
1. <takeaway 1>
2. <takeaway 2>
...

## Quotes
> <direct quotes worth preserving — use sparingly>

## Links out
- Covers: [entity name](../entities/entity-slug.md), [concept name](../concepts/concept-slug.md)
```

**Leave the `Links out` section initially empty** — you'll fill it after Step 4 decides which entities/concepts to create or link to.

**Link paths are relative to the source page's location.** Since source pages live in `wiki/sources/`, links to entities live at `../entities/<name>.md`, links to other source pages live at `./<name>.md` (same folder), and so on. See `schema.md` §7 for the full path-writing rules.

---

## Step 4 — Find related existing pages (layer 1: suggest, don't auto-update)

This is the key design decision in this workflow. **Do not automatically update existing wiki pages.** Instead:

### 4a. Search the existing wiki for related terms

Extract the 5–15 key terms from the takeaways (entities, technologies, people, concepts, projects). Then search the existing wiki for each one. Prefer this approach in order:

1. **If the `document-search` skill is installed**, use it:
   ```bash
   python /path/to/skills/document-search/scripts/document_search.py "<term>" <wiki-path>/wiki --format json
   ```
   This gives you a ranked list of files already mentioning each term.

2. **Otherwise**, use the agent's built-in Grep tool on `<wiki-path>/wiki/`.

3. **Also search `index.md`** for the term — the index often lists canonical pages.

### 4b. Build a proposal list

Classify each term into one of four buckets:

| Bucket | Meaning | Action |
|---|---|---|
| **Already exists, high-relevance** | Term matches an existing page's title or primary content | Propose: add a "Sources" link from that page to the new source page. Optionally propose a small content update. |
| **Already exists, tangential** | Term appears in an existing page but only in passing | Propose: nothing (don't clutter the page just because the word appeared). Add to source page's "Links out". |
| **Doesn't exist, important to the source** | Term is central to the new source and deserves its own page | Propose: create a new entity or concept page stub. |
| **Doesn't exist, tangential** | Term is mentioned but not worth its own page | Propose: nothing. The source page is enough. |

### 4c. Present the proposal to the user

Show it clearly and wait for approval. **Never execute updates automatically.**

> "Here's what I'd like to do — tell me yes/no for each:
>
> **Updates to existing pages:**
> - `wiki/entities/tech-bigquery.md` — add a new "Sources" entry linking to this new source, and add a one-sentence note about the new insight. **[update / skip]**
> - `wiki/concepts/retrieval-augmented-generation.md` — add to its Sources list. **[update / skip]**
>
> **New pages I'd create:**
> - `wiki/entities/person-karpathy.md` — a new entity page, since the source is authored by Karpathy and he's not in the wiki yet. **[create / skip]**
> - `wiki/concepts/personal-knowledge-base.md` — a new concept page for this idea. **[create / skip]**
>
> **Tangential mentions I'll link from the source page but not touch elsewhere:**
> - `tech-obsidian` (not in wiki, but only mentioned once)
> - `concept-flashcards` (not in wiki)
>
> How does this look? Reply 'all yes' to accept everything, or pick and choose."

### 4d. Wait for user feedback, then execute

Only after the user confirms, execute the approved actions one by one:
- For each "update existing page" — edit the page, bumping its `updated:` field.
- For each "create new page" — create a stub page with frontmatter + minimal structure (1 paragraph).
- Never create more than **5 new stub pages per ingest** without checking in again. If the source is so dense it warrants more, tell the user: "This source would generate 8 new pages — want me to create all 8, or should I start with the 3 most important?"

---

## Step 5 — Update `index.md`

Add the new source page to `index.md`, and if any new entities / concepts / synthesis pages were created, add them too.

Update the "Last updated" line. Don't rewrite the whole file — just append to the relevant sections.

If a new topic category emerges (the user is starting to accumulate pages in a new area), propose a new topic heading in `index.md`:

> "You now have 3 pages about personal knowledge management (karpathy's wiki method, obsidian, and the wiki concept). I'd like to add a new 'Knowledge management' section to `index.md` to group them. OK?"

---

## Step 6 — Append to `log.md`

Log the ingest as an entry at the bottom of `<wiki>/log.md`:

```markdown
## [YYYY-MM-DD] Ingest: <short description of the source>
- **Source**: [short title](wiki/sources/YYYY-MM-DD-<slug>.md)
- **New pages**: `<list any new entities/concepts/synthesis pages created>`
- **Updated pages**: `<list any existing pages modified>`
- **Raw file**: `raw/YYYY-MM-DD-<slug>.<ext>`
- **Notes**: <optional; anything notable about this ingest>
```

**Never edit past log entries.** Always append.

---

## Step 7 — Summarize to the user

Tell the user exactly what happened:

> "Done. Here's the summary:
>
> - **Raw source**: `raw/2026-04-11-karpathy-llm-wiki.md`
> - **New source page**: `wiki/sources/2026-04-11-karpathy-llm-wiki-gist.md`
> - **New pages created**: `wiki/entities/person-karpathy.md`, `wiki/concepts/personal-knowledge-base.md`
> - **Existing pages updated**: `wiki/entities/tech-obsidian.md` (added to Sources)
> - **Index updated**: added 'Knowledge management' section
> - **Logged at**: `log.md`
>
> The wiki now has <N> source pages and <M> total pages. Ask me anything about it, or drop another source in when you're ready."

---

## Failure modes and recovery

### The user doesn't remember their wiki path

Ask. Keep a mental note for the rest of the conversation. Do not guess.

### The source file is huge (e.g. a 200-page PDF)

- If a reader skill is available, use page-range selection (`--pages 1-20`) to read just the first section, then ask the user if you should continue.
- Ask the user upfront: "This is a long source. Should I read the whole thing, or focus on specific pages/chapters?"
- If the summary ends up very long, keep the source page's "Key takeaways" section to the top 10 items and put the rest in a collapsed "More takeaways" section.

### The proposal list is huge (20+ affected pages)

Don't dump all 20 on the user at once. Group by category and show the top 5 in each group, with a count of the remainder:

> "This source touches a lot of existing pages. Here are the top 5 by relevance, plus summaries of the rest:
> ..."

Let the user approve in batches.

### The user wants layer-2 behavior (auto-update without asking)

If the user says "don't ask, just do it", you can switch to a **less conservative mode within this conversation only** — but:

1. Confirm the scope: "For this ingest, I'll skip the approval step and update all the pages I find relevant. Confirm?"
2. Still log every update in the log entry so the user can review what happened.
3. Never persist this preference across conversations. Every new conversation defaults back to layer 1 (ask first).
