# Contributing to skills

Thanks for your interest in contributing! This repo is a library of small, composable skills for AI coding agents, and the value of the library grows every time someone adds a new one. This document explains how to add a skill, what makes a good skill, and the review process.

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
cp template/SKILL.md    skills/<skill-name>/SKILL.md
cp template/README.md   skills/<skill-name>/README.md
cp template/_preflight.py skills/<skill-name>/scripts/_preflight.py
```

Then add your implementation under `skills/<skill-name>/scripts/`.

Skills are laid out flat — one folder per skill directly under `skills/` — to match the official [`anthropics/skills`](https://github.com/anthropics/skills) convention. Plugin grouping lives in `.claude-plugin/marketplace.json`, not in the filesystem. See Step 6.

### Step 3 — Fill in `SKILL.md`

Every `SKILL.md` **must** contain:

1. **YAML frontmatter** with at minimum `name` and `description`. Include `compatibility` if you've verified the skill against specific agents.

   ```yaml
   ---
   name: my-skill
   description: "One sentence that tells an agent exactly when to fire this skill."
   compatibility: "Claude Code, Roo Code, Cline"
   ---
   ```

2. **An `## Overview` section** — a short paragraph describing the skill's purpose.
3. **A `## When to use` section** — concrete trigger scenarios written for an LLM agent to recognize.
4. **A `## Usage` section** — copy-pasteable command examples.
5. **An `## Options` table** — every CLI flag, its default, and what it does.
6. **An `## Output format` section** — describe (or show an example of) exactly what the skill returns.
7. **An `## Integration` section** — a short note confirming the skill works with Claude Code / Roo Code / Cline (all three auto-discover skills from their standard folders, so usually just `install.py` is enough).

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
- Python scripts should start with `#!/usr/bin/env python3` and run under Python 3.8+.
- Shell scripts should start with `#!/usr/bin/env bash` and set `set -euo pipefail`.

This self-contained rule is what lets users copy a single folder into their own project and have it just work.

### Step 5.1 — Stdlib first, optional packages second

Users run on a huge variety of environments (Windows, Linux, macOS, locked-down corporate machines). To keep the barrier to entry low, follow these rules:

- **Prefer the Python standard library.** If a task can reasonably be done with `os`, `pathlib`, `re`, `json`, `csv`, `html.parser`, `xml.etree`, etc., don't add a third-party dependency for it.
- **If you need a third-party package, make it optional.** Import it *lazily*, only in the code path that actually needs it — never at module load time. That way users who don't need the exotic feature never need the exotic package.
- **Never crash on a missing package.** Instead, copy `template/_preflight.py` into your skill's `scripts/` folder and call `_preflight.require([...])` right before the code that needs the package. It will print a bilingual (English / 中文) install guide to stderr, including the exact `pip install` command *and* how to set `HTTPS_PROXY` for users behind corporate firewalls, then exit with code 2.

  ```python
  # scripts/my_skill.py
  import sys
  from pathlib import Path
  sys.path.insert(0, str(Path(__file__).resolve().parent))
  import _preflight

  def extract_pdf(path):
      _preflight.require(["pypdf"], feature="PDF reading", skill_name="my-skill")
      import pypdf
      ...
  ```

  If you'd rather continue with reduced functionality, use `_preflight.check([...])` instead — it returns `(present, missing)` without exiting, so you can emit a warning and skip the affected files.
- **Document every optional package** in your skill's `README.md` and in the `## Requirements` section of `SKILL.md`.

### Step 5.2 — Work on Windows

Test your skill on Windows (or at least don't rely on Unix-only conventions):

- Use `pathlib.Path` and `os.path` rather than hardcoded `/` separators in Python code.
- Don't shell out to `cp`, `mkdir -p`, `rm -rf`, `cat`, `grep`, `which`, etc. Use `shutil`, `Path.mkdir(parents=True, exist_ok=True)`, and Python-side logic instead.
- If your script prints non-ASCII text (e.g. the install guide contains 中文), reconfigure stdout/stderr to UTF-8 at the start of `main()` — Windows consoles default to cp1252 and will crash otherwise:

  ```python
  for stream in (sys.stdout, sys.stderr):
      try:
          stream.reconfigure(encoding="utf-8", errors="replace")
      except (AttributeError, ValueError):
          pass
  ```

### Step 6 — Register your skill

Add a row for your skill to the **Skills table** in both:

- [`README.md`](README.md) (root)
- [`skills/README.md`](skills/README.md)

Then register your skill with a Claude Code plugin in [`.claude-plugin/marketplace.json`](.claude-plugin/marketplace.json). You have two options:

1. **New plugin (one skill)** — add a new entry to the `plugins` array:

   ```json
   {
     "name": "<skill-name>",
     "description": "<one-line description>",
     "source": "./",
     "strict": false,
     "skills": ["./skills/<skill-name>"]
   }
   ```

2. **Add to an existing plugin** — if your skill is part of an existing themed group (e.g. a `document-skills` plugin), append `"./skills/<skill-name>"` to that plugin's `skills` array. This is exactly how the official `anthropics/skills` repo bundles `xlsx`, `docx`, `pptx`, and `pdf` into a single `document-skills` plugin.

Plugin grouping is a pure marketplace-level concept — nothing changes on disk, and the same skill folder can even be referenced by multiple plugins if it makes sense.

---

## 3. Code quality checklist

Before opening a PR, please confirm:

- [ ] Folder is named in `lower-kebab-case`
- [ ] `SKILL.md` contains valid YAML frontmatter with `name` and `description`
- [ ] All required `SKILL.md` sections are present
- [ ] `README.md` exists and documents requirements + usage
- [ ] Script runs on a clean machine with **only Python stdlib** for the default code path
- [ ] Every third-party import is lazy (inside the function that needs it) and wrapped by `_preflight.require()` or `_preflight.check()`
- [ ] The script runs on Windows (paths, no `cp`/`rm -rf`, UTF-8 stdout)
- [ ] Optional dependencies are listed in `SKILL.md` and `README.md`
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
