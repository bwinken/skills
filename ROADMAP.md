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

### 1. `document-analyzer` — structured analysis of a single document

**Status:** planned • **Plugin target:** new, `document-tools` (or fold into `document-readers`)

**Why not just use `*-reader`?** Readers return *text*. Analyzers return *structure* — things an LLM cannot reliably infer by eyeballing extracted text. The whole point of this skill is to do the deterministic, mechanical work that LLMs do badly, so the LLM can focus on interpretation.

**Candidate sub-features** (pick one or more to MVP, not all at once):

| Feature | Format | Why it's hard for the LLM |
|---|---|---|
| Track changes / revision history extraction | `.docx` | `python-docx` exposes a raw XML tree; an LLM reading the rendered text has no way to see who changed what |
| Cross-sheet formula dependency graph | `.xlsx` | Requires walking every cell's formula AST, resolving `Sheet1!A1` references across sheets |
| PDF metadata + form-field inventory | `.pdf` | Author, creation date, encryption flags, fillable fields — all buried in the document catalog, invisible to text extraction |
| Two-document diff (structured) | `.docx` / `.pdf` | Compare two versions of a contract; return a structured list of added/removed/modified clauses, not a character-level diff |
| Structure validation | `.docx` | Check heading hierarchy (no H3 before H2), list indentation consistency, table schema |

**When to use (trigger phrases):**
- "What changed between v1 and v2 of this contract?"
- "List all the tracked changes in `spec.docx`."
- "Show me the formula dependencies in this Excel workbook."
- "What forms does this PDF have, and what fields are fillable?"

**Proposed scope for MVP:**
- Pick **one** sub-feature to start. **Recommendation: PDF metadata + form-field inventory** — it's the most format-contained, no cross-file logic, and `pypdf` exposes everything needed.
- CLI: `document_analyzer.py <file> --feature metadata|forms|diff|...`
- Dispatch by feature flag, not by file extension — this skill *is* cross-format by design.

**Known challenges:**
- **Scope creep**: "analyzer" is seductive. Resist doing general-purpose LLM-ready summarization — that's just a reader + LLM. Every feature must produce something the LLM *can't trivially derive from reader output*.
- **Dependency sprawl**: each sub-feature may need its own optional lib. Keep them lazy.
- **Format-specific analyzers may want their own skills eventually** (`pdf-analyzer`, `docx-analyzer`, ...). Start as one skill; split later if the CLI flag matrix gets unwieldy.

**Future split risk:** **high**. If MVP grows to 4+ feature flags × 4 formats, the "read vs search split rule" suggests splitting per format (since analyzing *a single file* is what this does). Keep an eye on the CLI complexity.

---

### 2. `project-structure` — map a codebase's architecture (with AST)

**Status:** planned • **Plugin target:** new, `code-tools`

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
- Ship **layer 1** only. Pure stdlib, no optional deps. Output: JSON + human text.
- Defer AST layers to a v2 — they're higher value but much more complex.
- CLI: `project_structure.py <path> [--languages] [--entry-points] [--tree] [--format json|text]`

**Known challenges:**
- **`tree-sitter-languages` has prebuilt wheels** for most platforms, but corporate proxies can block PyPI. Keep it behind `_preflight.require()` and make layer 1 (stdlib) always work.
- **Static call graphs are unreliable** in dynamic languages (Python's monkey-patching, JS's runtime dispatch). Mark any call-graph output as "best effort" in the schema.
- **Large monorepos** will produce huge outputs. Mandatory `--max-files` and per-directory summaries.
- **gitignore parsing** is surprisingly annoying stdlib-only. We can shell out to `git ls-files` when a `.git/` is present, fall back to a hard-coded ignore list otherwise.

**Future split risk:** **medium**. If the AST layer gets big it may want to be its own `code-ast` skill (single-file analysis), leaving `project-structure` as the folder-level skill. This fits the read-vs-search split rule cleanly: `project-structure` operates on a folder, `code-ast` operates on a single file.

---

### 3. `code-review` — prepare structured review context for the LLM

**Status:** planned • **Plugin target:** new, `code-tools` (same as `project-structure`)

**Why it exists:** "AI code review" is usually just the agent reading the diff and commenting. That's slow and token-expensive. This skill does the **mechanical prep work** so the LLM can focus on semantic review:

- Extract the diff (`git diff main...HEAD` or `git diff --staged`)
- Identify which files / functions / classes changed (via AST; reuse `project-structure`'s AST logic — **duplicate the code**, don't import it; see self-contained rule)
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

Applying these criteria to what's left on the roadmap, the **easiest remaining wins** are:

1. **`project-structure` layer 1** — stdlib-only, read-only, one file of logic
2. **`document-analyzer` (PDF metadata feature)** — single sub-feature, one optional dep, no mutations

Do these two in either order. `code-review` is the biggest remaining item because of the subprocess orchestration for linters/tests.

The document-organization cluster is already shipped as `document-organizer` — see §4 for the retrospective on why it ended up as one skill instead of four.
