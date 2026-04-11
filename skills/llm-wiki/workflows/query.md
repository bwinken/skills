# Workflow: query — ask questions against the wiki

**When to run this:** the user wants to retrieve knowledge from their wiki. The trigger is usually one of:

- "What do I know about X?"
- "What have I saved about Y?"
- "Check my wiki for Z"
- "Remind me what I wrote about <topic>"
- "What does my wiki say about <person / product / concept>?"
- "Find everything in my wiki related to <topic>"

**Prerequisite state:** a wiki exists at a known path, and `SCHEMA.md` has been read by the agent in this conversation.

---

## Step 0 — Read the wiki's schema

Always start by reading `<wiki>/SCHEMA.md`. You need to know the directory layout, naming conventions, and whether the user has customized anything.

---

## Step 1 — Understand the query

Before searching, parse what the user is actually asking. There are three common patterns:

### Pattern A: "What do I know about X?"

A **recall** query. The user wants a consolidated answer based on what's in the wiki. The answer should:
- Synthesize from multiple pages if possible
- Cite the source pages explicitly as markdown links (`[title](../sources/...md)`)
- Distinguish between "what the wiki says" and "what I (the agent) know in general"

### Pattern B: "Find me the page about X"

A **navigation** query. The user wants a specific page, not a synthesis. The answer should:
- Return a list of matching page paths
- Prefer exact title matches over content matches
- If only one page matches, offer to open it / read it

### Pattern C: "What sources do I have on X?"

An **inventory** query. The user wants a list of the raw sources they've filed, not a synthesis. The answer should:
- List source pages (not entity / concept pages)
- Include publication dates and source types if available
- Order by relevance then date

**Ask the user for clarification** only if the query is genuinely ambiguous. Most of the time the pattern is obvious from the phrasing.

---

## Step 2 — Search the wiki

Use a multi-pass search strategy. Don't just grep once.

### 2a. Start with `index.md`

Read `<wiki>/index.md`. The index is the curated map — if the query matches a topic heading or a listed page, you've probably found the canonical answer already.

### 2b. Search page titles and aliases

Parse frontmatter across `wiki/**/*.md` for any page whose `title` or `aliases` match the query. Title matches are **strong** signals.

This can be done with the `document-search` skill if available:

```bash
python /path/to/skills/document-search/scripts/document_search.py "<term>" <wiki-path>/wiki --show-matches
```

Or with the agent's built-in Grep tool on `<wiki-path>/wiki/`.

### 2c. Search page bodies

Full-text search across `wiki/**/*.md` for the query term. Use `document-search` if available.

### 2d. Search the source pages separately

`wiki/sources/*.md` is where the original material lives. If the query is about "what does X think about Y", the answer is often in a source page written by X, not in a concept page.

### 2e. Check `log.md`

If the user is asking a **temporal** question ("what did I add last week?", "when did I first save something about X?"), skip the wiki search and use `wiki_log.py` instead — see `workflows/lint.md` and the script's `--help`.

---

## Step 3 — Rank and filter results

You'll likely have a few candidate pages. Rank them by:

1. **Direct title / alias match** (highest)
2. **Frontmatter tag match**
3. **Multiple content matches in the same page** (body density)
4. **Single content match** (lowest)

**Filter out** pages with `status: stale` from the primary answer — but mention them at the end as "also marked as stale, may be out of date".

### Source-page priority

For Pattern A (recall) queries, **always** prefer pulling quotes from source pages over entity/concept pages. Source pages are primary, entity pages are syntheses.

---

## Step 4 — Synthesize the answer

Write the answer in a way that makes the wiki's contribution explicit. The user wants to see **what's in their wiki**, not "here's what I know from training."

### Template for Pattern A (recall)

```markdown
Based on your wiki:

<1-paragraph synthesis of the key claims from the wiki pages>

**Sources in your wiki:**
- [Karpathy — LLM wiki gist](wiki/sources/2026-04-11-karpathy-llm-wiki-gist.md) — "key quote or takeaway"
- [BigQuery docs](wiki/sources/2025-12-03-bigquery-docs.md) — "another key claim"

**Related pages:**
- [BigQuery](wiki/entities/tech-bigquery.md)
- [retrieval-augmented-generation](wiki/concepts/retrieval-augmented-generation.md)

<Optional: 1 sentence of general knowledge the agent can add, clearly labeled as "outside the wiki">
```

### Template for Pattern B (navigation)

```markdown
I found these pages matching "<query>":

1. **[BigQuery](wiki/entities/tech-bigquery.md)** — a columnar data warehouse. (primary match)
2. **[columnar-storage](wiki/concepts/columnar-storage.md)** — mentions BigQuery as an example
3. **[BigQuery docs](wiki/sources/2025-12-03-bigquery-docs.md)** — original source

Which one would you like me to read?
```

### Template for Pattern C (inventory)

```markdown
You have <N> source pages about "<query>" in your wiki:

| Date | Title | Type |
|------|-------|------|
| 2026-04-11 | [Karpathy — LLM wiki gist](wiki/sources/2026-04-11-karpathy-llm-wiki-gist.md) | gist |
| 2025-12-03 | [BigQuery docs](wiki/sources/2025-12-03-bigquery-docs.md) | doc |
| 2025-09-15 | [Paper title](wiki/sources/2025-09-15-paper-name.md) | paper |
```

---

## Step 5 — Cite, cite, cite

Every factual claim in the answer must trace back to a specific wiki page. Use standard markdown links with relative paths (`[title](wiki/sources/...md)`) so the user can click through in any markdown viewer.

**Never fabricate citations.** If the wiki doesn't mention something, say so:

> "Your wiki doesn't mention <specific claim>. If you'd like me to add it, drop a source in `raw/` and I'll ingest it."

---

## Step 6 — Offer to file the answer

If the synthesis you just produced is valuable and not already captured as a `synthesis/` page, offer to file it:

> "This synthesis doesn't exist in your wiki yet. Want me to save it as `wiki/synthesis/<name>.md`? It would cite all the sources I just pulled."

**Never auto-file without asking.** The user may want a throwaway answer, not a new wiki entry.

---

## Step 7 — Log the query

Append to `<wiki>/log.md`:

```markdown
## [YYYY-MM-DD] Query: "<the user's question>"
- **Pattern**: <recall | navigation | inventory>
- **Pages consulted**: <list the pages the agent actually read>
- **New pages filed**: <if the user accepted a synthesis offer; otherwise "none">
- **Notes**: <optional; anything the agent wants future-self to remember>
```

This matters — it creates a history of what the user asked and when. Future lint passes can use this to identify "pages that keep getting cited but are never updated" (candidates for review) or "topics that keep getting asked but have no source in the wiki" (gaps to fill).

---

## Common failures

### The wiki returns nothing

Tell the user honestly:

> "Your wiki doesn't have anything on '<query>'. Would you like to:
>
> 1. Add a source now (I can search the web or ingest a file you have)
> 2. Rephrase the query — sometimes content is filed under a different term
> 3. Ask me from general knowledge instead (I'll tell you clearly it's not from your wiki)"

### The wiki has too many hits

If more than ~15 pages match, don't dump them all. Show the top 5 and count the rest:

> "I found 23 pages about '<topic>'. Here are the 5 most relevant:
> ...
> Plus 18 more — want me to narrow the search? For example, by date range or specific sub-topic?"

### The wiki's answer contradicts the agent's training

Be explicit. Trust the wiki as primary:

> "Your wiki says X (from [source title](wiki/sources/...md)). From training data I'd say Y. The wiki is more recent — I'll go with X, but flag that you may want to double-check."

### The user wants a *semantic* search (embeddings)

This skill does not ship with an embedding-based search. If the user's query is too fuzzy for string search (e.g. "find me sources that discuss similar ideas to RAG but use different terminology"), tell them:

> "Text search isn't going to catch that — it's a semantic question. Your options:
>
> 1. Try a few related terms and I'll search for each
> 2. Let me read the top candidate pages myself and do the comparison
> 3. If you use a tool like `qmd` or another vector search, point me at it and I can pull from there"
