# SkillForge 🛠️

> A curated collection of skills for AI coding agents.

SkillForge is a growing library of self-contained **skills** that you can drop into any AI coding agent — Claude Code, Roo Code, Aider, Cursor, Cline, or any agent that supports MCP servers, custom tools, or shell execution. Each skill is a small, focused capability (a file scanner, a doc summarizer, a test runner, etc.) packaged in a way that an LLM agent can discover, understand, and invoke on demand.

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

SkillForge skills are designed to be agent-agnostic. They have been verified to work with, or are easy to wire into:

- **Claude Code** (Anthropic) — drop `SKILL.md` under `~/.claude/skills/<skill-name>/`.
- **Roo Code** — register the skill as a custom tool or mode prompt.
- **Aider** — invoke the script directly via shell; point Aider to the skill's usage docs.
- **Cursor** — add the script as a custom command or via an MCP wrapper.
- **Cline** — expose the script as a tool in Cline's configuration.
- **Any MCP-capable agent** — wrap the script in an MCP server and register it.
- **Any agent that can run shell commands** — just call the script directly.

---

## Skills

| Skill | Description | File Types |
|-------|-------------|------------|
| [deep-grep](skills/deep-grep/) | Grep for a term across a workspace and return a ranked list of files that contain it — **including inside `.docx`, `.pptx`, `.xlsx`, and `.pdf`** where ordinary grep/rg are blind | `.py`, `.md`, `.docx`, `.pdf`, `.pptx`, `.xlsx`, 60+ types |

More skills coming soon. Contributions welcome — see [CONTRIBUTING.md](CONTRIBUTING.md).

---

## Installation

Clone the repo anywhere on your machine:

```bash
git clone https://github.com/bwinken/skills-library.git
cd skills-library
```

### Using a skill with Claude Code

```bash
mkdir -p ~/.claude/skills
cp -r skills/deep-grep ~/.claude/skills/
```

Claude Code will auto-discover the skill on next launch.

### Using a skill with Roo Code / Cursor / Cline

Point the agent at the skill's script directly, or register the script as a custom tool. For example, Roo Code:

```jsonc
// .roo/config.json
{
  "customTools": [
    {
      "name": "deep-grep",
      "command": "python3 /absolute/path/to/skills-library/skills/deep-grep/scripts/deep_grep.py",
      "description": "Grep for a term across a workspace, including .docx/.pptx/.xlsx/.pdf. Returns a ranked list of files that contain the term."
    }
  ]
}
```

### Using a skill with Aider or any shell-capable agent

Just invoke the script:

```bash
python3 skills-library/skills/deep-grep/scripts/deep_grep.py "TODO" ./my-project
```

---

## Quick Start

Find every file in the current directory that mentions `DATABASE_URL`:

```bash
python3 skills/deep-grep/scripts/deep_grep.py "DATABASE_URL" .
```

Search a docs folder (including Word and PDF documents) for "quarterly revenue", case-insensitive:

```bash
pip install python-docx pypdf
python3 skills/deep-grep/scripts/deep_grep.py "quarterly revenue" ./docs \
  --ext .md,.docx,.pdf -i
```

TODO / FIXME hunt across a Python + TypeScript codebase with line-level context:

```bash
python3 skills/deep-grep/scripts/deep_grep.py "TODO|FIXME" ./src \
  --ext .py,.ts --context 2
```

See each skill's own `README.md` and `SKILL.md` for the full option list.

---

## Repository layout

```
skills-library/
├── README.md              # You are here
├── LICENSE                # MIT
├── CONTRIBUTING.md        # How to add a new skill
├── .gitignore
├── skills/                # The actual skills
│   ├── README.md
│   └── deep-grep/
│       ├── SKILL.md
│       ├── README.md
│       └── scripts/
│           └── deep_grep.py
└── templates/             # Copy these when creating a new skill
    ├── SKILL_TEMPLATE.md
    └── README_TEMPLATE.md
```

---

## License

[MIT](LICENSE) © bwinken
