# LLM Wiki — Schema

> The design book for an LLM-maintained personal knowledge base. This is the schema the agent reads *before* every wiki operation so that the wiki stays consistent across months and hundreds of conversations.
>
> **Credit:** this schema is directly inspired by Andrej Karpathy's gist ["How I create my own LLM wiki"](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f). The directory layout, the `log.md` append-only idea, and the "wiki as a maintained artifact" framing are all his. This file adapts the idea into a concrete, agent-readable spec.
>
> **Status:** this is the **default** schema shipped with the `llm-wiki` skill. When a user first runs `init`, this file is copied to `<wiki>/SCHEMA.md` (or `<wiki>/AGENTS.md`) — the user's personal copy. **Edit the user's copy, not this one.** If you (the agent) want to change something while maintaining a wiki, edit `<wiki>/SCHEMA.md` after confirming with the user.

---

## 1. Directory layout

A wiki is a single folder the user owns (e.g. `~/my-wiki/`, `~/Documents/wiki/`). Everything lives under it; nothing is stored in the skill folder itself. The user is expected to version-control this folder with git.

```
<wiki>/
├── SCHEMA.md           # This schema, personalized. The agent reads it before every operation.
├── index.md            # Content-oriented catalog — see §5. Keep it curated.
├── log.md              # Append-only chronological record — see §6. Never edit past entries.
├── raw/                # Immutable sources dropped by the user. Never modify.
│   └── assets/         # Images, data files, PDFs attached to sources
├── wiki/               # LLM-generated markdown. This is where the synthesis lives.
│   ├── entities/       # Concrete things: people, companies, products, repos, places
│   ├── concepts/       # Abstract things: techniques, patterns, theories, mental models
│   ├── sources/        # One page per ingested source (summary + takeaways + link back to raw/)
│   └── synthesis/      # Multi-source pages: comparisons, overviews, "state of X in 2026"
```

### Rules

- **`raw/` is immutable.** The agent must never modify or delete files in `raw/`. If a source needs updating, ingest the new version as a separate file and add a cross-reference.
- **`wiki/` is all LLM-maintained.** Every file here was either created by the agent or edited by the user. Files can be moved between subfolders (e.g. a `concept/` that turns out to be about a specific product → move to `entities/`).
- **`index.md` and `log.md` live at the top level**, not under `wiki/`, because they describe the whole repo.
- **`assets/` is the only sub-folder of `raw/`.** Images/PDFs/binary attachments go there. If there are enough of them, the agent can create topical sub-folders (`raw/assets/screenshots/`, `raw/assets/diagrams/`) but keep the depth shallow.

---

## 2. Page naming

All wiki pages use **lowercase, kebab-case** with a `{category}-{name}` prefix when the category helps disambiguate.

| Kind | Filename pattern | Examples |
|---|---|---|
| Entity | `entities/<category>-<name>.md` | `entities/tech-bigquery.md`, `entities/person-alice-chen.md`, `entities/company-anthropic.md` |
| Concept | `concepts/<name>.md` | `concepts/retrieval-augmented-generation.md`, `concepts/linear-attention.md` |
| Source | `sources/<date>-<slug>.md` | `sources/2026-04-11-karpathy-llm-wiki-gist.md` |
| Synthesis | `synthesis/<name>.md` | `synthesis/rag-landscape-2026.md`, `synthesis/post-attention-architectures.md` |

### Categories for entities (not exhaustive; add new ones as needed, then tell the user)

`person-`, `company-`, `tech-` (technology / library / product), `project-`, `place-`, `event-`, `team-`, `repo-`.

### Rules

- **No spaces, no underscores, no CamelCase.** Use hyphens.
- **No `.md.md`, no `index.md` inside subfolders** — that path is reserved for the top-level `index.md`.
- **When renaming a page, update all inbound links.** Use `wiki_lint.py --mode broken-links` to find them.

---

## 3. Page frontmatter (required)

Every markdown file in `wiki/` **must** start with YAML frontmatter:

```yaml
---
title: "BigQuery"
kind: entity              # entity | concept | source | synthesis
category: tech            # optional; only for entities that use a category prefix
tags: [data-warehouse, google-cloud, sql]
created: 2026-04-11
updated: 2026-04-11
sources: 3                # how many source pages contribute to this page
aliases: [BQ, BigQuery SQL]
---
```

### Required fields

| Field | Type | Notes |
|---|---|---|
| `title` | string | Human-readable display name. Quoted string, no hyphens required. |
| `kind` | enum | One of `entity`, `concept`, `source`, `synthesis`. Must match the folder. |
| `created` | date | `YYYY-MM-DD`. Set once, never changed. |
| `updated` | date | `YYYY-MM-DD`. Bumped every time the agent edits the page (except for pure link-fixup edits from `lint`). |

### Optional fields

| Field | Type | When to include |
|---|---|---|
| `category` | string | Only for entity pages that use a category prefix (e.g. `category: tech` for `tech-bigquery.md`). |
| `tags` | list | A short list of searchable tags. Lowercase, kebab-case. |
| `sources` | int | How many source pages the claims on this page came from. Only for `kind: entity`, `concept`, or `synthesis`. Helps the lint pass detect stale pages. |
| `aliases` | list | Alternative names the user or agent might use to search for this page. |
| `status` | enum | `draft` / `stable` / `stale`. Only set `stable` after a lint pass confirms the page is well-supported. |

### Frontmatter rules

- **Never delete fields**, only add. If a field is no longer relevant, set it to an empty value (`aliases: []`) rather than removing it. This keeps the schema stable.
- **Dates use `YYYY-MM-DD`**, not slashes, not localized. The log parser depends on this.
- **`updated` bumps:** every real edit (content change, new section, reworded paragraph) bumps `updated`. Pure link fixups from a lint pass do *not* bump it — add a `## Maintenance` note at the bottom of the page instead.

---

## 4. Page structure (body)

Inside the body, each kind has a recommended structure. These are **strong defaults** — deviate only when the content really demands it, and when you do, tell the user.

### 4a. Entity page (`wiki/entities/*.md`)

```markdown
# <Title>

<1-2 sentence summary — what is this thing? why does it matter to the user?>

## Key facts
- <bulleted facts the user cares about>
- <each fact should be a standalone claim, not a narrative paragraph>

## Relationships
- **Related to**: [concept-xyz](../concepts/concept-xyz.md), [tech-foo](tech-foo.md)
- **Part of**: [company-acme](company-acme.md)
- **Used for**: [concept-retrieval](../concepts/concept-retrieval.md)

## Notes
<Narrative prose. Longer observations, user's opinions, "things to remember">

## Sources
- [Karpathy LLM wiki gist](../sources/2026-04-11-karpathy-llm-wiki-gist.md)
- [BigQuery docs](../sources/2025-12-03-bigquery-docs.md)
```

### 4b. Concept page (`wiki/concepts/*.md`)

```markdown
# <Title>

<1-2 sentence definition>

## Why it matters
<Why the user cares about this concept — often a reference to a project they're working on>

## How it works
<The actual mechanism. Keep it tight; link out to entities rather than redefining them.>

## Variations / alternatives
- [concept-alternative-a](concept-alternative-a.md)
- [concept-alternative-b](concept-alternative-b.md)

## Sources
- [source title](../sources/YYYY-MM-DD-slug.md)
```

### 4c. Source page (`wiki/sources/*.md`)

**These are the anchor pages.** Every claim elsewhere in the wiki should trace back to at least one source page.

```markdown
---
title: "Karpathy — How I create my own LLM wiki"
kind: source
created: 2026-04-11
updated: 2026-04-11
source_type: gist         # article | paper | gist | video | doc | book | conversation
source_url: "https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f"
raw_file: "raw/2026-04-11-karpathy-llm-wiki.md"
author: "Andrej Karpathy"
published: 2026-04-10
---

# Karpathy — How I create my own LLM wiki

## Summary
<1 paragraph — what is this source about? Why did the user save it?>

## Key takeaways
1. <First concrete takeaway>
2. <Second>
3. ...

## Quotes
> <Direct quote from the source the user wants to remember>

## Links out
- Covers: [personal-knowledge-base](../concepts/personal-knowledge-base.md), [tech-obsidian](../entities/tech-obsidian.md), [Karpathy](../entities/person-karpathy.md)
- Disagrees with: [source title](YYYY-MM-DD-other-slug.md)  (optional)
- Extends: [source title](YYYY-MM-DD-other-slug.md)  (optional)
```

### 4d. Synthesis page (`wiki/synthesis/*.md`)

```markdown
# <Title>

<1 paragraph — what question does this synthesis answer?>

## TL;DR
<A direct answer, 3-5 bullets>

## Landscape
<Breakdown by category / axis. Use tables when comparing multiple things.>

## Open questions
- <Things the user has noticed but not resolved>

## Sources
- [source title](../sources/YYYY-MM-DD-slug.md)
- [another source](../sources/YYYY-MM-DD-other-slug.md)  (at least 2 — if only 1, this should be a source summary instead)
```

---

## 5. `index.md` — the curated catalog

This is the **hand-maintained** (well, agent-maintained) top-level map of the wiki. It is **not** an automatic listing of every file.

```markdown
# Wiki index

Last updated: 2026-04-11

## By kind
- **Entities**: [BigQuery](wiki/entities/tech-bigquery.md), [Karpathy](wiki/entities/person-karpathy.md), ...
- **Concepts**: [personal-knowledge-base](wiki/concepts/personal-knowledge-base.md), ...
- **Syntheses**: [rag-landscape-2026](wiki/synthesis/rag-landscape-2026.md), ...
- **Recent sources**: see `log.md`

## By topic
### AI / ML
- [retrieval-augmented-generation](wiki/concepts/retrieval-augmented-generation.md) — the pattern
- [linear-attention](wiki/concepts/linear-attention.md) — alternative to quadratic attention
- [post-attention-architectures](wiki/synthesis/post-attention-architectures.md) — overview

### Data infra
- [BigQuery](wiki/entities/tech-bigquery.md)
- [columnar-storage](wiki/concepts/columnar-storage.md)

### <your topic>
- ...
```

### Rules

- **Topical groupings are flexible.** The agent should propose topic headings that match the user's current interests, not impose a taxonomy.
- **Updated on every ingest**, at least the "Last updated" date and the affected topic section.
- **Deleted pages must be removed from the index in the same operation.** This is a frequent source of broken links.
- **One-line summary per link** when there's room. The index should read like a table of contents, not a raw file listing.

---

## 6. `log.md` — append-only chronological record

This is the **wiki's commit log at the prose level**. Every operation (ingest, query, lint) appends an entry. **Never edit past entries.**

```markdown
# Log

## [2026-04-11] Ingest: Karpathy LLM wiki gist
- **Source**: [Karpathy LLM wiki gist](wiki/sources/2026-04-11-karpathy-llm-wiki-gist.md)
- **New pages**: `wiki/concepts/personal-knowledge-base.md`, `wiki/entities/person-karpathy.md`
- **Updated pages**: `index.md` (added "Knowledge management" topic)
- **Notes**: First wiki source. Triggered the creation of the `concepts/` folder.

## [2026-04-11] Query: "What does Karpathy say about wiki ingestion?"
- **Pages consulted**: `sources/2026-04-11-karpathy-llm-wiki-gist`
- **Answer synthesis**: Quoted takeaways #1 and #3, cited back to the source.
- **New pages filed**: none

## [2026-04-12] Lint pass
- **Orphan pages**: 0
- **Broken links**: 1 fixed (`concepts/rag` was renamed to `concepts/retrieval-augmented-generation`)
- **Stale pages flagged**: 0
```

### Rules

- **Every log entry starts with `## [YYYY-MM-DD] <operation>: <short description>`.** The `wiki_log.py` helper grep's for this exact pattern.
- **Operations are one of:** `Ingest`, `Query`, `Lint`, `Edit`, `Rename`, `Delete`, `Init`.
- **New entries go at the bottom** (append-only). Never sort chronologically from the top down.
- **Log entries should be short** (3–6 bullets). This is a trail for future debugging, not a narrative.
- **Log never deletes.** If a page is deleted, log the deletion with a reason.

---

## 7. Links

All links — internal and external — use **standard markdown link syntax**: `[display text](path/to/file.md)`. This maximizes tool compatibility:

- ✅ GitHub / GitLab renders them as clickable links when browsing the repo
- ✅ VSCode markdown preview renders them
- ✅ mkdocs and other static-site generators pick them up without any extra plugin
- ✅ Obsidian also renders them (with slightly weaker backlink detection than wikilinks, but it still works)
- ✅ Pandoc, Hugo, Jekyll, and every other markdown tool support them

**Do not use** `[[wikilinks]]`. They're an Obsidian-specific extension that most tools ignore.

### Internal links — use relative paths

The path is **relative to the file that contains the link**, not to the wiki root. Examples:

| Link is written in… | Linking to `wiki/entities/tech-bigquery.md` | Example |
|---|---|---|
| `wiki/entities/tech-snowflake.md` (same folder) | `tech-bigquery.md` | `See also [BigQuery](tech-bigquery.md).` |
| `wiki/concepts/columnar-storage.md` | `../entities/tech-bigquery.md` | `An example is [BigQuery](../entities/tech-bigquery.md).` |
| `wiki/sources/2026-04-11-foo.md` | `../entities/tech-bigquery.md` | `Covers: [BigQuery](../entities/tech-bigquery.md)` |
| `index.md` (wiki root) | `wiki/entities/tech-bigquery.md` | `- [BigQuery](wiki/entities/tech-bigquery.md)` |
| `log.md` (wiki root) | `wiki/entities/tech-bigquery.md` | Same as index.md |

**Rule of thumb:** count how many folders you need to go up (`../`) to get to the common ancestor, then descend into the target's path.

### Display text

Prefer the human-readable title for the display text (what the reader sees), not the filename. Examples:

- ✅ `[BigQuery](../entities/tech-bigquery.md)` — reader sees "BigQuery"
- ⚠️ `[tech-bigquery](../entities/tech-bigquery.md)` — works, but the dash-case filename is ugly
- ❌ `[../entities/tech-bigquery.md](../entities/tech-bigquery.md)` — redundant

For aliases and alternate names, rely on the `aliases:` field in the target page's frontmatter — don't bake them into the link text.

### External links

Same markdown syntax, with the URL instead of a relative path:

```markdown
Read [Karpathy's original gist](https://gist.github.com/karpathy/442a6bf555914893e9891c11519de94f) for the design philosophy.
```

### Links to `raw/`

Raw sources are outside the `wiki/` subtree, so they need a `../../raw/...` style path from inside a wiki page. A source page typically stores the raw-file path in frontmatter (`raw_file:`) so you don't need inline links.

### Linting

`wiki_lint.py --mode broken-links` parses `](path.md)` patterns and resolves each relative path against the containing file. Any unresolved target is reported as a broken link.

---

## 8. Tagging conventions

Tags live in frontmatter. Use them sparingly — the directory structure already categorizes, so tags should add a *second* dimension.

Good tags:
- **Topic area**: `ai`, `data`, `infra`, `personal-finance`, `health`
- **Status signal**: `work-in-progress`, `confidence-high`, `confidence-low`
- **Source quality**: `primary-source`, `secondary-source`, `opinion`

Bad tags (don't use):
- Anything already captured by the folder (`entity`, `concept`) — that's what `kind:` is for
- Anything already captured by the filename prefix (`tech` for `tech-*.md`)

---

## 9. What the agent must *never* do

These are hard rules. The agent should refuse or ask for explicit confirmation if a user request would violate them:

1. **Never modify files in `raw/`.** Sources are immutable.
2. **Never delete entries from `log.md`.** Append-only.
3. **Never rename a file without updating all inbound links.** Use `wiki_lint.py --mode broken-links` afterwards.
4. **Never overwrite `<wiki>/SCHEMA.md` with the skill's default schema** without confirming with the user. Their schema may have drifted from the default.
5. **Never commit to git automatically** unless the user explicitly asks. The user owns the wiki; the agent is a maintainer, not an author.
6. **Never write to a wiki location that doesn't contain a `SCHEMA.md`.** If the target folder has no schema, abort and ask the user to run `wiki_init.py` first.

---

## 10. When this schema is ambiguous

If the agent encounters a situation this schema doesn't cover (new source type, new page kind, unusual frontmatter need):

1. **Propose** the extension to the user in conversation.
2. **Wait** for confirmation.
3. **Edit** `<wiki>/SCHEMA.md` to document the new rule.
4. **Log** the schema change as a `## [YYYY-MM-DD] Schema: <what changed>` entry.

The schema is a living document. This default is the starting point, not the final word.
