# Roadmap

Skills that are **planned** but not yet implemented. This file captures the design intent behind each one so that when someone (you, future-me, or a contributor) picks one up, the scope and tradeoffs are already written down.

The current published skills cover the "find → read" half of document workflows. The next wave rounds that out into "find → read → **analyze / organize**" and extends the same toolkit into code workflows.

For skills that are already shipping, see the [Skills table in the root README](README.md#skills).

---

## Design principles (reminder)

When adding anything from this roadmap, follow the rules we've committed to:

1. **Three agents only** — Claude Code, Roo Code, Cline. All three auto-discover skills from their standard folders.
2. **Self-contained** — a skill folder must be copy-and-go. No imports from other skills, no reliance on repo-level shared libs. Duplicate small helpers across skills if you must.
3. **Flat layout** — one folder per skill under `skills/<name>/`. Plugin grouping lives in `.claude-plugin/marketplace.json`, not on the filesystem.
4. **"Read vs search" split rule**:
   - *Operate on a single file* → split one skill per format (e.g. `pdf-reader`, `docx-reader`).
   - *Operate on a folder / multiple files* → one skill, internal format dispatch (e.g. `document-search`).
5. **Stdlib first, optional packages second** — lazy imports wrapped by `_preflight.require()`. Never crash on a missing package; print a bilingual install guide.
6. **LLM does the thinking, skill does the mechanics** — skills are deterministic data-producers. If a skill's implementation boils down to "read content and let the LLM summarize," it's probably a reader skill, not an analyzer.

---

## Planned skills

### 1. ~~`document-analyzer`~~ → `document-inspector` plugin — shipped as **three sibling skills**

**Status:** ✅ **shipped** as the `document-inspector` plugin, bundling three single-format skills:

| Skill | Features | Dependency |
|---|---|---|
| [`pdf-inspector`](skills/pdf-inspector/) | `metadata` (title/author/dates/encryption/page size/PDF version), `forms` (AcroForm field inventory with types, values, required/read-only flags, signature fields) | `pypdf` |
| [`docx-inspector`](skills/docx-inspector/) | `metadata` (core properties, word/paragraph/table counts), `changes` (tracked changes — who changed what, when, via raw `w:ins`/`w:del` XML walk), `structure` (heading-hierarchy outline with skipped-level detection) | `python-docx` |
| [`xlsx-inspector`](skills/xlsx-inspector/) | `metadata` (properties + per-sheet dimensions/cell counts/merged ranges), `formulas` (regex-based dependency graph — cross-sheet references, per-sheet formula counts, sample formulas), `named-ranges` (full inventory with scope) | `openpyxl` |

**Retrospective — why the design changed from one-skill-five-features to three-skills-per-format:**

The original MVP shipped as a single `document-analyzer` skill with a `--feature` flag that was supposed to grow sideways into DOCX / XLSX / etc. features over time. Two problems emerged:

1. **The name over-promised.** "Analyzer" reads as *semantic* analysis — finding totals, summarising content, answering questions about what's inside. The skill only ever did *structural* extraction (metadata, form fields). Users hit the name and expected the former; the skill delivered the latter. The fix is a more honest name: **inspector**, matching Word's "Document Inspector" vocabulary — "checking" not "understanding".
2. **The single-skill-with-cross-format-features design violated this repo's own split rule.** The rule is *"operate on a single file → split one skill per format"*. PDF metadata extraction and XLSX formula parsing share roughly 5% of their code (argparse + `_preflight` + the renderer shell), so merging them into one skill only served the *name* — not any actual code reuse. Splitting into `pdf-inspector` / `docx-inspector` / `xlsx-inspector` makes each skill's SKILL.md, CLI, and test story dramatically simpler, and each skill's dependency (`pypdf` / `python-docx` / `openpyxl`) is loaded only when that skill runs.

**Why the plugin name is `document-inspector` (not `office-inspector` or similar):** the three skills share a concept — "get the structural facts around a document, not the content" — and that's what the plugin groups. `pptx-inspector` could be added later if someone needs slide-level metadata or speaker-notes inventory; nothing in the plugin shape prevents it.

**Still open (for a later round):**

- **Two-document structured diff** — compare v1 vs v2 of a contract and return a structured list of added/removed/modified clauses (not a character diff). The ROADMAP's split rule suggests this becomes its own `document-diff` skill, since it operates on multiple files.
- **DOCX structure validation (deeper)** — current `structure` feature only checks heading hierarchy; the original plan also mentioned list indentation and table schema validation. Adding those is a good follow-up inside `docx-inspector`.
- **PDF outline / bookmarks + annotations inventory** — `pypdf` exposes both via `reader.outline` and `page['/Annots']`. Natural additions inside `pdf-inspector` as `--feature outline` and `--feature annotations`.
- **XLSX data-validation rules** — `openpyxl` exposes `ws.data_validations`, which is another thing rendered tables hide.

**Retrospective lesson for future "umbrella" skill names:** the "analyzer" trap applies to any name whose scope is broader than the actual implementation. When the description paragraph starts with *"this skill does X"* and reality is *"this skill does X for PDF metadata"*, the name is wrong — either narrow it or broaden the implementation. In this case we narrowed it, because broadening (five features in one skill) violated the split rule.

---

### 2. ~~`project-structure`~~ → `code-inspector` — map a codebase's architecture (with AST)

**Status:** ✅ **layer 1 + layer 2 shipped** as [`code-inspector`](skills/code-inspector/) in the `code-tools` plugin (renamed from `project-structure` when layer 2 landed, to match the `inspector` vocabulary used by the `document-inspector` plugin's per-format skills — "inspector" = structural checking, not semantic understanding). CLI uses `--feature overview|ast|all` dispatch, mirroring document-inspector's pattern. `--tree` stays as an orthogonal toggle.

**What ships in layer 1 (`--feature overview`):** gitignore-aware walk, language + LOC breakdown (≈50 extensions mapped), entry points (`pyproject.toml`, `package.json`, `Cargo.toml`, `Dockerfile`, `main.py`, `index.ts`, ...), framework detection (Django / FastAPI / Flask / React / Next.js / Vue / Svelte / Angular / Express / NestJS / pytest / Jest / Vitest / Playwright / ...), test layout (directories, file globs, runner configs).

**What ships in layer 2 (`--feature ast`, Python only):** per-file Python AST analysis via stdlib `ast` — classes (with bases rendered via `ast.unparse`, methods, length), top-level functions (arg count, async flag, return annotation, length), module-level imports (with relative-import depth), statement count, max nesting depth (walks `If`/`For`/`While`/`Try`/`With` blocks), `if __name__ == "__main__":` detection, aggregate totals, top-10 most-complex-files ranking by a rough proxy score. Files with syntax errors are recorded in `skipped` with their reason and never crash the run. Capped at `--max-ast-files` (default 500).

**Layer 3 (non-Python AST via `tree-sitter-languages`)** is still open. The plan is to emit the same output shape for `.js` / `.ts` / `.go` / `.rs` / ... using prebuilt tree-sitter parsers (no C compiler needed). Lazy-loaded so layer 1 + layer 2 still work when the optional package is absent.

**Why it exists:** When an agent joins a new codebase it wastes tokens doing `ls` / `cat` / grep to understand the shape. This skill produces a **structured, agent-ready map** of the project in one call: languages, entry points, module graph, classes/functions, import relationships.

**Proposed layers (MVP to max):**

1. **File-level (stdlib only):**
   - Directory tree with gitignore-aware pruning
   - Language breakdown (count files + LOC by extension)
   - Detected entry points (`main.py`, `index.ts`, `Cargo.toml`, `package.json`, `pyproject.toml`, ...)
   - Detected frameworks (Django `manage.py`, FastAPI, React `package.json` + `"react"`, Next.js, ...)
   - Test directories (`tests/`, `__tests__/`, `*_test.py`, `*.test.ts`)
2. **AST-level for Python (stdlib `ast`):**
   - Per-file class / function definitions with signatures
   - Import graph (who imports whom)
   - Call graph (best-effort; static analysis only)
   - Complexity indicators (nesting depth, number of methods per class)
3. **AST-level for other languages (optional `tree-sitter-languages`):**
   - Same output shape as the Python layer, for `.js` / `.ts` / `.go` / `.rs` / ...
   - `tree-sitter-languages` ships prebuilt parsers so no C compiler needed.

**When to use (trigger phrases):**
- "Give me an overview of this project."
- "What's the structure of this codebase?"
- "List all the classes in `src/`."
- "Show me the import graph of this Python project."
- "Which files define `UserService`?"

**Proposed scope for MVP:**
- ~~Ship **layer 1** only. Pure stdlib, no optional deps.~~ ✅ done in the first round.
- ~~Defer AST layers to a v2.~~ ✅ layer 2 (Python AST) shipped in the rename round. Still deferred: layer 3 (non-Python AST).
- Final CLI: `code_inspector.py <path> [--feature overview|ast|all] [--tree] [--tree-depth N] [--max-files N] [--max-ast-files N] [--format text|json]`

**Known challenges (remaining):**
- **`tree-sitter-languages` has prebuilt wheels** for most platforms, but corporate proxies can block PyPI. Keep it behind `_preflight.require()` so layer 1 + layer 2 stay usable when the optional package is absent.
- **Static call graphs are unreliable** in dynamic languages (Python's monkey-patching, JS's runtime dispatch). The layer 2 implementation deliberately does NOT try to build a call graph for this reason — only per-file shape is extracted. If layer 3 ever wants cross-file resolution, mark it as "best effort" in the schema and expect false positives.
- **Large monorepos** — handled via `--max-files`, `--max-depth`, and `--max-ast-files` caps.
- **gitignore parsing** — handled via `git ls-files` when a `.git/` is present, hard-coded ignore fallback otherwise.

**Split rule retrospective:** the original plan floated splitting an eventual AST layer into its own `code-ast` skill. Layer 2 ended up inside `code-inspector` via `--feature ast` dispatch instead, because the AST output shares the walk infrastructure (gitignore handling, file enumeration, caps) with the overview tier. Splitting would have meant copy-pasting the walker, so the `--feature` approach is cleaner and matches the document-inspector pattern.

---

### 3. `code-review` — prepare structured review context for the LLM

**Status:** planned • **Plugin target:** `code-tools` (same plugin as `code-inspector`)

**Why it exists:** "AI code review" is usually just the agent reading the diff and commenting. That's slow and token-expensive. This skill does the **mechanical prep work** so the LLM can focus on semantic review:

- Extract the diff (`git diff main...HEAD` or `git diff --staged`)
- Identify which files / functions / classes changed (via AST; reuse `code-inspector`'s AST logic — **duplicate the code**, don't import it; see self-contained rule)
- Run linters on changed files: `ruff check --output-format json`, `pyright`, `eslint --format json`, `golangci-lint run --out-format json`, ...
- Run tests if a test runner is detected and `--run-tests` is passed
- Check coverage delta if coverage data exists
- Organize everything into a structured JSON report the LLM can reason about

**When to use (trigger phrases):**
- "Review my changes before I push."
- "Run a code review on this branch."
- "What's wrong with my PR?"
- "Check this diff for issues."

**Proposed scope for MVP:**
- CLI: `code_review.py [--base main] [--linters ruff,eslint] [--run-tests] [--format json|text]`
- Output: JSON structured report with sections: `summary`, `files_changed`, `lint_findings`, `test_results`, `coverage_delta`
- Ship with Python-first support (`ruff` + `pyright`). JS/TS/Go/Rust are stretch goals.

**Known challenges:**
- **Linter availability varies wildly** — `ruff` may be installed globally, in a venv, or not at all. `_preflight` helps but linters are CLI tools, not pip packages, so the check is different. We'd need to invoke `shutil.which("ruff")` and fall back gracefully if missing.
- **Running tests is dangerous** — `pytest` on an unknown project could run anything. Make `--run-tests` off by default and add a big warning.
- **Subprocess orchestration** — lots of shell-out logic, lots of timeout / stderr handling. Keep each linter adapter in its own function, well-tested.
- **Overlap with agent's built-in review**: the agent will still do the semantic part. This skill's job is strictly "collect and structure the evidence." That line must be drawn clearly in `SKILL.md` or the skill will compete with the LLM instead of helping it.

**Future split risk:** **low-medium**. Could split per language (`python-review`, `js-review`) if the adapter matrix gets messy. Probably fine as one skill for the first year.

---

### 4. ~~Document organization skills (4-skill cluster)~~ — **shipped** as a single skill

**Status:** ✅ **shipped as [`document-organizer`](skills/document-organizer/)** (single skill, four modes) in the `document-organizer` plugin.

**What happened:** The original plan was to ship four independent skills — `document-classifier`, `document-metadata-organizer`, `document-deduplicator`, `document-renamer`. During implementation the design collapsed into a **single skill with four modes** (`classify` / `by-metadata` / `dedup` / `rename`) because they all share the same safety infrastructure: scan → plan → execute → undo, dry-run by default, hard-banned paths, collision resolution, per-folder state file. Shipping as four skills would have meant copy-pasting that infrastructure four times under the `self-contained` rule, and making the agent pick between four nearly-identical SKILL.md files.

**The unified skill ended up with:**

- **Four modes** (`--mode classify|by-metadata|dedup|rename`) dispatched by the same scan/plan/execute/undo subcommands
- **Per-folder state file** `.document-organizer-rules.json` remembers category lists, group-by strategy, dedup match mode, rename template — written only by explicit `init-rules`, never auto-written
- **Undo log** on every real execute, written to `<folder>/.document-organizer-undo/undo-<mode>-<timestamp>.json`
- **Dry-run by default** — `execute` is a no-op unless `--execute` is passed explicitly
- **Hard-banned paths** (filesystem root, `~`, `/etc`, `C:\Windows`, ...) plus soft-banned git repo roots (override with `--force-dangerous`)
- **Collision resolution** via auto-appending ` (2)`, ` (3)`, ...
- **Cross-device-move refused** for safety
- **Never deletes** — dedup moves duplicates to `_duplicates/`, not the trash, not `rm`
- **Pure stdlib** — no `pip install` anything

**Retrospective lesson for future skill clusters:** when a cluster of skills shares ≥60% of its infrastructure (safety, validation, state, undo), prefer a **single skill with modes** over N copy-pasted self-contained skills. The "one skill per filesystem action" split rule still stands — but `classify` / `by-metadata` / `dedup` / `rename` are all the same action (move-files-with-rules), just with different decision layers, so they belong together.

---

## Also on the radar (lower priority)

These are half-formed ideas that didn't make the numbered list, but are worth remembering:

- **`dependency-inspector`** — read `requirements.txt` / `package.json` / `Cargo.toml` / `go.mod` and produce a structured report: outdated versions, security advisories (via `pip-audit` / `npm audit`), unused deps.
- **`env-inspector`** — find every `.env` / config file in a project, list all variables, cross-reference which are actually read by the code. Useful for "what env vars does this project need?"
- **`changelog-generator`** — walk `git log` between two tags and produce a structured changelog by parsing commit messages. Complements code-review.
- **`test-runner-detector`** — given a project folder, figure out how to run its tests (`pytest`, `npm test`, `cargo test`, `go test ./...`) by inspecting config files. Returns the exact command so the agent knows how to invoke tests.

---

## How to pick one to work on

When you come back to this file and want to start something, these criteria help:

1. **Does it follow the "LLM thinks, skill mechanics" split?** If the implementation is "read → pass to LLM → done," it's probably a reader, not a new skill.
2. **Does it need dangerous operations?** Destructive skills (delete, overwrite, rename en masse) need more guards and testing. Start with read-only skills first.
3. **Does the MVP fit in one script file?** If a skill needs multiple scripts to even get started, that's a sign the scope is too broad. Cut it down.
4. **Can you test it without external state?** Skills that need a git repo, a network connection, or a large test corpus are harder to iterate on. Prefer skills that work against a single file or a small sample folder.

Applying these criteria, the shipped inspectors cover the easiest remaining wins:

1. ~~`project-structure` layer 1~~ — ✅ shipped, then renamed to `code-inspector`
2. ~~`document-analyzer` (PDF metadata feature)~~ — ✅ shipped as `pdf-inspector`
3. ~~`document-analyzer` DOCX track-changes~~ — ✅ shipped as `docx-inspector`
4. ~~`document-analyzer` XLSX formula graph~~ — ✅ shipped as `xlsx-inspector`
5. ~~`code-inspector` layer 2 (Python AST)~~ — ✅ shipped

The remaining items are:

- `code-review` (biggest; subprocess orchestration for linters/tests)
- `code-inspector` layer 3 — non-Python AST via `tree-sitter-languages` (JavaScript / TypeScript / Go / Rust / ...)
- Two-document structured diff (likely a new `document-diff` skill rather than a feature on any existing inspector)
- PDF `outline` / `annotations` features for `pdf-inspector`
- Deeper `docx-inspector` structure validation (list indentation, table schema)
- `xlsx-inspector` data-validation rule inventory

The document-organization cluster is already shipped as `document-organizer` — see §4 for the retrospective on why it ended up as one skill instead of four.
