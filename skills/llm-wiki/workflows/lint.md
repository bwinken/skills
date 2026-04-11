# Workflow: lint — periodic wiki cleanup

**When to run this:** the user wants to clean up their wiki. This should be run periodically (once a month for active wikis, whenever the user asks). The trigger is usually one of:

- "Clean up my wiki"
- "Run a lint pass on the wiki"
- "Find broken links in my wiki"
- "What pages are stale / orphaned?"
- "Wiki health check"

**Prerequisite state:** a wiki exists at a known path, and `SCHEMA.md` has been read.

---

## Step 0 — Read the wiki's schema

Read `<wiki>/SCHEMA.md` first. Lint behavior depends on the user's customizations (e.g. if they renamed directories, the broken-link detector needs to know the new names).

---

## Step 1 — Run the lint script

```bash
python /path/to/skills/llm-wiki/scripts/wiki_lint.py <wiki-path> --format json
```

The script performs the **deterministic** checks that don't need an LLM:

1. **Orphan pages** — pages in `wiki/` that are not linked from anywhere (including `index.md`)
2. **Broken links** — markdown links `](some/path.md)` that don't resolve to an existing file (relative paths are resolved against the containing file)
3. **Missing frontmatter** — pages without the required frontmatter fields (`title`, `kind`, `created`, `updated`)
4. **Frontmatter schema violations** — wrong `kind` for the folder, invalid date formats, etc.
5. **Stale pages** — pages whose `updated:` date is older than a threshold (default: 180 days)
6. **Unreferenced sources** — source pages in `wiki/sources/` that no other page cites

The script outputs JSON. Parse it and use the findings for the next steps.

---

## Step 2 — Triage the findings

For each category of finding, decide whether it needs **LLM attention** (semantic judgment) or can be **auto-fixed** (deterministic).

### 2a. Broken links (usually auto-fixable)

Broken links are almost always caused by a file rename. The fix pattern:
1. Take the broken target (e.g. `(../concepts/rag.md)`)
2. Search for a file whose frontmatter `aliases:` contains "rag" or whose filename is close (`concepts/retrieval-augmented-generation.md`)
3. If a clear match exists, fix the link automatically — remember to recompute the relative path for the file doing the linking
4. If no clear match, report it to the user for a decision

### 2b. Missing frontmatter (usually auto-fixable)

If a page has a partially-filled frontmatter (e.g. missing `updated:`), fill in sensible defaults:
- `updated:` → today's date
- `kind:` → derive from folder (`wiki/entities/...` → `entity`)
- `created:` → if git is available, use the file's first commit date; otherwise today
- `title:` → derive from the first `#` heading in the body

If a page has **no** frontmatter at all, treat it as more suspicious — it may be a legacy note the user dragged in manually. Report it, don't auto-fix.

### 2c. Orphan pages (needs LLM judgment)

An orphan page isn't automatically wrong. It might be:
- **A draft** the user is still working on
- **A leaf page** that has no natural linker (e.g. a one-off synthesis)
- **Actually abandoned** and should be either linked from `index.md` or deleted

Report orphans to the user with context:

> "Found 3 orphan pages (not linked from anywhere):
>
> 1. `wiki/concepts/quantum-fourier-transform.md` — created 2025-08-02, updated 2025-08-02, 847 bytes. Looks like an abandoned stub (no content beyond the template).
> 2. `wiki/synthesis/rag-vs-long-context.md` — created 2026-03-15, updated 2026-04-01, 3.2KB. Looks active — maybe just needs to be linked from `index.md`.
> 3. `wiki/entities/person-someone.md` — created 2025-01-01, updated 2025-01-01, 200 bytes. Very stale stub.
>
> For each, tell me: link / delete / ignore."

Wait for the user's decision. **Never delete a page without explicit confirmation.**

### 2d. Stale pages (needs LLM judgment)

A page with `updated:` > 180 days old isn't necessarily wrong — some things don't change. Report them **grouped**, not individually:

> "Found 8 pages with no updates in > 180 days. Most are likely fine (entities that are stable), but worth a quick scan:
>
> **Probably fine (stable reference):**
> - `wiki/entities/tech-bigquery.md` — last updated 2025-09-12
> - `wiki/entities/company-google.md` — last updated 2025-06-03
>
> **Worth checking (recent activity in related pages):**
> - `wiki/concepts/retrieval-augmented-generation.md` — last updated 2025-10-01, but 3 new source pages on RAG were ingested since then. Might need an update.
>
> Want me to open any of these?"

### 2e. Unreferenced sources (needs LLM judgment)

A source page that no other wiki page cites is a **red flag** — it means the ingest didn't fully propagate. Two likely causes:
1. The ingest was aborted partway through
2. The source is about a topic that didn't deserve any entity/concept pages

Report them:

> "Found 2 source pages that aren't cited by any entity or concept page:
>
> 1. `sources/2026-03-20-random-article.md` — ingested 2026-03-20. Might have been an aborted ingest. Want me to re-process it, or delete it?
> 2. `sources/2025-11-15-one-off-read.md` — ingested 2025-11-15. No entities were extracted at the time. Might be fine."

---

## Step 3 — Apply safe fixes

For each category the user approved as "auto-fixable":

1. **Edit the affected pages** one at a time
2. **Do NOT bump the `updated:` field** on pages that only had mechanical fixes (broken link repair, frontmatter fill-in). Instead, add a small note at the bottom:

   ```markdown

   ---

   <!-- Lint 2026-04-11: fixed broken link to concepts/rag → concepts/retrieval-augmented-generation -->
   ```

   This preserves the semantic meaning of `updated:` (it's "when did the content change", not "when did the file get touched").

3. **Keep a running list** of every fix applied. You'll need it for the log entry in Step 5.

---

## Step 4 — Propose structural improvements (optional, requires LLM judgment)

After the mechanical fixes, the agent can optionally **propose** higher-level improvements. These are always suggestions, never auto-applied:

- **Missing index entries**: pages that exist but aren't in `index.md`
- **Topic clustering**: pages that are in the same topic area but aren't cross-linked
- **Missing syntheses**: topics where the user has 3+ source pages but no synthesis page
- **Inconsistent naming**: e.g. some pages use `tech-` prefix, others don't

Example:

> "Structural observations (not errors — just ideas):
>
> 1. You have 5 source pages about RAG but no synthesis page. Want me to draft one? It would cite all 5 sources.
> 2. `wiki/entities/tech-bigquery.md` and `wiki/entities/tech-snowflake.md` aren't cross-linked, even though they're both data warehouses. Should I add a 'Related to' entry on each?
> 3. Your `wiki/entities/` folder mixes `tech-*` and un-prefixed files. If you want to standardize, I can rename the un-prefixed ones and fix all inbound links.
>
> Tell me yes/no for each, or say 'skip' to leave structure as-is."

Wait for the user. **Never apply structural changes without explicit confirmation.**

---

## Step 5 — Log the lint pass

Append to `<wiki>/log.md`:

```markdown
## [YYYY-MM-DD] Lint pass
- **Orphan pages**: <count> (action: <fixed N / reported M>)
- **Broken links**: <count> (fixed: <N>)
- **Missing frontmatter**: <count> (filled: <N>, reported: <M>)
- **Stale pages flagged**: <count>
- **Unreferenced sources**: <count>
- **Structural suggestions**: <count> (accepted: <N>, skipped: <M>)
- **Notes**: <any particular observations worth remembering>
```

---

## Step 6 — Summarize to the user

Give the user a before/after view:

> "Lint complete. Summary:
>
> **Auto-fixed (no content changes):**
> - 3 broken links → pointed at renamed files
> - 1 missing frontmatter field filled in
>
> **Reported for your review:**
> - 2 orphan pages (see above)
> - 5 stale pages (all look fine, just old)
> - 1 unreferenced source (possibly aborted ingest)
>
> **Structural ideas:**
> - Proposed a new `synthesis/rag-landscape.md` (you said yes — I'll draft it in a follow-up)
>
> Your wiki now has <N> pages total, with <M> source pages, <K> entities, <L> concepts, and <J> synthesis pages.
>
> Logged to `log.md`. I'd recommend running a lint pass again in about a month."

---

## Common failures

### The script finds a huge number of broken links (say, 50+)

This usually means a large rename happened and the user ran lint much later. Don't try to fix all 50 at once. Group by target filename:

> "Most of the broken links (42 of 50) point at `concepts/rag` — looks like this was renamed to `concepts/retrieval-augmented-generation`. Should I fix all 42 at once, or do you want to review each?"

### The script finds suspicious deletions

If a page is orphaned AND has a very short body AND was created long ago AND never updated, suggest deletion — but **always** with a confirmation prompt and **always** offer to move to a `.trash/` subfolder instead of deleting outright:

> "I'd recommend moving these 3 pages to `.trash/` (not deleted — just out of the way):
>
> - `wiki/entities/person-someone.md` (200 bytes, 15 months old, never updated)
>
> Proceed?"

### The user wants to run lint automatically

Lint is intentionally manual. If the user wants automation, tell them:

> "Lint is intentionally opt-in because it can make structural changes I want you to review. But you can set up a scheduled trigger in Claude Code (`/schedule`) to remind yourself to run it monthly, or alias it to a short command in your shell."

Don't try to auto-schedule anything from inside this workflow.
