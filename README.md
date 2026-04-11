# skills 🛠️

> A curated collection of skills for AI coding agents, shipped as a **Claude Code plugin marketplace**.

`skills` is a growing library of self-contained **skills** that you can drop into any of the three major AI coding agents with native skill support — **Claude Code**, **Roo Code**, and **Cline**. All three use the same `SKILL.md` + YAML-frontmatter format (`name`, `description`), and all three auto-discover skills from well-known folders, so a single skill folder works everywhere without any glue code.

Installing is a one-liner. **Claude Code** users can use the built-in plugin marketplace (`/plugin marketplace add bwinken/skills`). Everyone else (and Claude Code users who prefer a single-file flow) can drop [`install.py`](install.py) into any folder and run `python install.py` — it launches an interactive wizard that picks the agent, global-vs-workspace scope, and which skills to install, downloading them directly from GitHub if you haven't cloned the repo.

> 📖 Documentation is written in English, but skills may include bilingual (English / 中文) usage notes where helpful.

---

## What is a skill?

A **skill** is a self-contained folder under `skills/` that bundles:

1. **`SKILL.md`** — A machine- and human-readable definition. It declares the skill's name, description, trigger conditions, usage instructions, and examples. Agents read this file to decide *when* and *how* to use the skill.
2. **`scripts/`** — The actual implementation (Python, shell, Node, etc.) that performs the work.
3. **`README.md`** — A GitHub-facing page so humans browsing the repo can understand the skill at a glance.

Every skill folder is **fully self-contained**: it never imports from or depends on another skill, so you can copy a single folder into your own project and it will just work.

---

## Supported agents

All three supported agents natively auto-discover skills from well-known directories. No config files, no manual registration — just drop the skill folder in the right place (or let [`install.py`](install.py) do it for you) and the agent picks it up on next launch.

| Agent | Global (user-wide) | Workspace (project-local) | Docs |
|-------|--------------------|---------------------------|------|
| **Claude Code** (Anthropic) | `~/.claude/skills/<name>/` | `./.claude/skills/<name>/` | [docs](https://docs.claude.com/en/docs/claude-code/skills) |
| **Roo Code** | `~/.roo/skills/<name>/` | `./.roo/skills/<name>/` | [docs](https://docs.roocode.com/features/skills) |
| **Cline** | `~/.cline/skills/<name>/` | `./.cline/skills/<name>/` | [docs](https://docs.cline.bot/customization/skills) |

All three agents share the same skill format — a folder containing a `SKILL.md` with YAML frontmatter (`name`, `description`). A skill authored for one agent works in all three.

---

## Skills

Every skill lives flat under [`skills/`](skills/). Plugin grouping is declared in [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json) — the same convention the official [`anthropics/skills`](https://github.com/anthropics/skills) repo uses — so a single plugin can bundle several related skills without forcing them into nested folders.

The current skills cover the **文書工作 (office workflow)** core loop: **find** the relevant file, then **read** its content. Together they let an agent answer questions like *"which report in this folder mentions Q4 revenue, and what does that report say?"* even when the folder is full of `.docx` / `.pdf` files.

| Skill | Plugin | Description | Dependency |
|-------|--------|-------------|------------|
| [document-search](skills/document-search/) | `document-search` | Search a folder for a term across mixed formats — **`.docx`, `.pptx`, `.xlsx`, `.pdf`** and 60+ text / code types — in one pass, returning a ranked file list | *(none for text; optional for Office/PDF)* |
| [pdf-reader](skills/pdf-reader/) | `document-readers` | Read a PDF file, with optional page range (`--pages 1-5`) | `pypdf` |
| [docx-reader](skills/docx-reader/) | `document-readers` | Read a Word document — paragraphs and tables | `python-docx` |
| [xlsx-reader](skills/xlsx-reader/) | `document-readers` | Read an Excel file as GitHub-flavored markdown tables, one per sheet | `openpyxl` |
| [pptx-reader](skills/pptx-reader/) | `document-readers` | Read a PowerPoint deck, with optional slide range (`--slides 1-5`) | `python-pptx` |
| [llm-wiki](skills/llm-wiki/) | `knowledge-tools` | Maintain a personal, LLM-curated knowledge base: four workflows (init / ingest / query / lint), a Karpathy-inspired schema, and three stdlib helper scripts. Agent-orchestration style skill — heavy on docs, light on code. | *(none — stdlib only)* |

The `document-readers` plugin bundles all four readers together — install once, get support for PDF / Word / Excel / PowerPoint. Install them individually if you only need one format. The `knowledge-tools` plugin currently hosts `llm-wiki` and will grow as more knowledge-management skills come online.

More skills are planned — see [ROADMAP.md](ROADMAP.md) for the design notes on upcoming skills (`document-analyzer`, `project-structure`, `code-review`, and a cluster of document-organization skills). Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

## Related marketplaces

Looking for something specific while this library is still small? These marketplaces are worth a look:

- **[`anthropics/skills`](https://github.com/anthropics/skills)** — Anthropic's own example skills (PDF / Word / Excel / PowerPoint processing, frontend design, MCP builder, and more). Install from inside Claude Code with:
  ```text
  /plugin marketplace add anthropics/skills
  /plugin install document-skills@anthropic-agent-skills
  ```
  Note: Anthropic's skills ship under Anthropic's own license — see [their LICENSE.txt](https://github.com/anthropics/skills/blob/main/skills/pdf/LICENSE.txt) before redistributing or creating derivative works.

---

## Installation

### Claude Code — one-liner via the plugin marketplace ⭐

This repo **is** a Claude Code plugin marketplace. Inside Claude Code, run:

```text
/plugin marketplace add bwinken/skills
/plugin install <skill-name>@skills
```

That's it — no `git clone`, no copy-paste, no `pip install`. Claude Code fetches the plugin, registers its skill, and auto-discovers it on your next prompt. Replace `<skill-name>` with any plugin listed in this marketplace (see the Skills section above). See [`discover plugins`](https://docs.claude.com/en/docs/claude-code/plugins) in the Claude Code docs for `/plugin` commands (update, remove, list, etc.).

### Any agent — `install.py` wizard (one file, no clone)

Works for **Claude Code**, **Roo Code**, and **Cline** — Windows, Linux, macOS. The only requirement is Python 3.8+. No `pip install`, no clone step, no config to edit afterwards.

**The one-liner (no clone, no setup):**

```bash
# macOS / Linux
curl -fsSLO https://raw.githubusercontent.com/bwinken/skills/main/install.py
python install.py

# Windows (PowerShell)
iwr https://raw.githubusercontent.com/bwinken/skills/main/install.py -OutFile install.py
python install.py
```

That drops a single file (`install.py`) into your current folder and launches an interactive wizard:

```
Step 1/3 — Which coding agent are you using?
  1) Claude Code
  2) Roo Code
  3) Cline

Step 2/3 — Install globally or only for the current workspace?
  1) Global     (e.g. ~/.claude/skills/)
  2) Workspace  (e.g. ./.claude/skills/)

Step 3/3 — Which skills do you want to install?  (multi-select)
  [x] 1) <skill-name> — <description from frontmatter>
```

The installer fetches the selected skill(s) directly from GitHub (via the public Contents API) and drops them into the right folder for your agent. No config to edit — all three agents auto-discover skills from those paths on next launch. If you already cloned the repo, `install.py` uses the local copy instead of hitting GitHub.

**Non-interactive mode (for scripts / CI):**

```bash
python install.py list                                           # see what's available
python install.py install <skill> --agent claude                 # global (default scope)
python install.py install <skill> --agent roo --scope workspace
python install.py install <skill> --agent cline --dry-run        # preview first
python install.py where --agent claude --scope workspace         # show the target path
python install.py uninstall <skill> --agent roo --scope workspace
```

Supported `--agent` values: `claude`, `roo`, `cline`. Supported `--scope` values: `global` (default), `workspace`. The installer walks the flat `skills/<skill>/` layout — the same layout Claude Code's marketplace reads through `.claude-plugin/marketplace.json` — so both install paths stay in sync from a single source of truth.

### Manual install (if you'd rather not use `install.py`)

Every skill folder under `skills/` is **fully self-contained** — just copy the folder into the right directory for your agent and it will be auto-discovered:

- **Claude Code**: `~/.claude/skills/<name>/` (global) or `./.claude/skills/<name>/` (workspace)
- **Roo Code**: `~/.roo/skills/<name>/` or `./.roo/skills/<name>/`
- **Cline**: `~/.cline/skills/<name>/` or `./.cline/skills/<name>/`

### Optional packages & corporate proxies

Skills are expected to run on the Python standard library alone by default. When a feature needs a third-party package (e.g. `pypdf` for PDF reading), skills should **never crash on a missing package** — they should detect it at runtime and print a bilingual install guide that includes:

- the exact `pip install` command with the correct Python interpreter,
- instructions for setting `HTTPS_PROXY` if you're behind a corporate firewall (PowerShell / cmd / bash / zsh / fish),
- the affected files so the agent can retry them once you install.

[`template/_preflight.py`](template/_preflight.py) ships a zero-dependency helper that does exactly this — drop it into any new skill's `scripts/` folder and call `_preflight.require([...])` lazily.

---

## Repository layout

This repo mirrors the [`anthropics/skills`](https://github.com/anthropics/skills) layout: every skill is a flat folder under `skills/`, and plugin grouping is declared in `.claude-plugin/marketplace.json`.

```
skills/                               # repo root
├── README.md                         # You are here
├── LICENSE                           # MIT
├── CONTRIBUTING.md                   # How to add a new skill
├── install.py                        # Single-file installer with interactive wizard
├── .gitignore
├── .claude-plugin/
│   └── marketplace.json              # Claude Code marketplace manifest (plugin grouping)
├── skills/                           # The actual skills — one flat folder each
│   ├── README.md
│   └── <skill-name>/                 # (none published yet)
│       ├── SKILL.md                  # Agent-facing definition
│       ├── README.md                 # Human-facing page
│       └── scripts/
│           ├── <entry>.py
│           └── _preflight.py         # local install-guide helper (stdlib only)
└── template/                         # Copy these when creating a new skill
    ├── SKILL.md                      # Skill template
    ├── README.md                     # Readme template
    └── _preflight.py                 # Drop into your skill's scripts/ folder
```

---

## License

[MIT](LICENSE) © bwinken
