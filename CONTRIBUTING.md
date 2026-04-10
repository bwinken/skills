# Contributing to SkillForge

Thanks for your interest in contributing! SkillForge is a library of small, composable skills for AI coding agents, and the value of the library grows every time someone adds a new one. This document explains how to add a skill, what makes a good skill, and the review process.

---

## 1. Before you start

- **One PR, one skill.** Keep pull requests focused on a single skill (or a single change to an existing skill) so reviews stay fast.
- **Search existing skills first.** Browse [`skills/`](skills/) to make sure what you're adding isn't already covered.
- **Open an issue for discussion** if you're proposing a large new skill or an architectural change. A short design note avoids wasted work.

---

## 2. How to add a new skill

### Step 1 — Pick a name

Skill names must be:

- **lowercase**
- **kebab-case** (hyphen-separated)
- **descriptive and concrete**

Good: `deep-grep`, `doc-summarizer`, `pytest-runner`, `dependency-graph`
Bad: `DeepGrep`, `scanner`, `utils`, `my_tool`

### Step 2 — Copy the templates

```bash
mkdir -p skills/<skill-name>/scripts
cp templates/SKILL_TEMPLATE.md skills/<skill-name>/SKILL.md
cp templates/README_TEMPLATE.md skills/<skill-name>/README.md
```

Then add your implementation under `skills/<skill-name>/scripts/`.

### Step 3 — Fill in `SKILL.md`

Every `SKILL.md` **must** contain:

1. **YAML frontmatter** with at minimum `name` and `description`. Include `compatibility` if you've verified the skill against specific agents.

   ```yaml
   ---
   name: my-skill
   description: "One sentence that tells an agent exactly when to fire this skill."
   compatibility: "Claude Code, Roo Code, Aider, Cursor, Cline"
   ---
   ```

2. **An `## Overview` section** — a short paragraph describing the skill's purpose.
3. **A `## When to use` section** — concrete trigger scenarios written for an LLM agent to recognize.
4. **A `## Usage` section** — copy-pasteable command examples.
5. **An `## Options` table** — every CLI flag, its default, and what it does.
6. **An `## Output format` section** — describe (or show an example of) exactly what the skill returns.
7. **An `## Integration` section** — a short note on wiring the skill into Claude Code / Roo Code / Aider / Cursor / Cline or any other agent you've tested.

The `description` field in frontmatter is the single most important piece of text in your skill: it's what an agent reads to decide whether to invoke the skill. Make it precise.

### Step 4 — Fill in `README.md`

The skill-level `README.md` is for humans browsing GitHub. It should include:

- Name and one-line description
- Requirements (Python version, optional libraries, system dependencies)
- Installation / setup
- Usage examples with expected output
- Output format examples
- Links back to the root repo and `SKILL.md`

### Step 5 — Self-contained implementation

Every skill folder **must be fully self-contained**:

- Do not import from other skills.
- Do not assume files exist outside the skill's own folder.
- Prefer the standard library; if you need third-party packages, make them **optional** wherever reasonable and document them clearly in `README.md`.
- Python scripts should start with `#!/usr/bin/env python3` and run under Python 3.8+.
- Shell scripts should start with `#!/usr/bin/env bash` and set `set -euo pipefail`.

This self-contained rule is what lets users copy a single folder into their own project and have it just work.

### Step 6 — Register your skill

Add a row for your skill to the **Skills table** in both:

- [`README.md`](README.md) (root)
- [`skills/README.md`](skills/README.md)

---

## 3. Code quality checklist

Before opening a PR, please confirm:

- [ ] Folder is named in `lower-kebab-case`
- [ ] `SKILL.md` contains valid YAML frontmatter with `name` and `description`
- [ ] All required `SKILL.md` sections are present
- [ ] `README.md` exists and documents requirements + usage
- [ ] Script runs on a clean machine with no hidden dependencies
- [ ] Optional dependencies are clearly listed and the script degrades gracefully when they're missing
- [ ] No files from your local environment leaked in (check against `.gitignore`)
- [ ] Skills table in root `README.md` and `skills/README.md` is updated

---

## 4. Pull request process

1. **Fork** the repo and create a branch: `git checkout -b skill/<skill-name>`
2. **Commit** with a clear message: `feat(skills): add <skill-name>`
3. **Push** the branch and open a PR against `main`
4. In the PR description, include:
   - What the skill does
   - Which agent(s) you tested it with
   - A sample invocation and its output
5. Respond to review feedback. Once approved, a maintainer will merge.

---

## 5. Reporting issues

Found a bug in an existing skill? Open an issue with:

- The skill name
- The exact command you ran
- The full error output
- Your OS, Python/Node version, and agent (if relevant)

---

## 6. License

By contributing you agree that your work is released under the repository's [MIT License](LICENSE).
