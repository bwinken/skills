---
name: <skill-name>
description: "<One sentence that tells an agent exactly when to use this skill and what it does.>"
compatibility: "Claude Code, Roo Code, Cline"
---

# <Skill Name>

## Overview

<One short paragraph explaining what the skill does, why it exists, and who it is for. Write this for an LLM agent that will read it to decide whether to invoke the skill.>

## When to use

- <Concrete trigger scenario 1 — e.g. "The user asks to find all TODO comments in a project.">
- <Concrete trigger scenario 2 — e.g. "The user needs to extract text from a folder of Word documents.">
- <Concrete trigger scenario 3>

## When NOT to use

- <Optional: cases where another skill or a built-in tool is a better fit.>

## Usage

Basic invocation:

```bash
python3 scripts/<entry>.py <required-arg>
```

With common options:

```bash
python3 scripts/<entry>.py <required-arg> --flag value --other-flag
```

## Options

| Flag | Default | Description |
|------|---------|-------------|
| `--example` | `value` | <What this flag controls.> |
| `--format` | `text` | Output format (`text` or `json`). |

## Output format

<Describe or show an example of the exact output the skill produces. If JSON, include a sample object. If plain text, include a short sample.>

```text
<sample output>
```

## Requirements

- Python 3.8+
- Optional: `<package-name>` — for `<extra feature>`

## Integration

All three supported agents (Claude Code, Roo Code, Cline) natively auto-discover skills from their standard folders — no manual registration needed.

### One-file installer (recommended)

```bash
curl -fsSLO https://raw.githubusercontent.com/bwinken/skills/main/install.py
python install.py                                          # interactive wizard
python install.py install <skill-name> --agent claude      # or roo, cline
```

### Claude Code — plugin marketplace (alternative)

```text
/plugin marketplace add bwinken/skills
/plugin install <skill-name>@skills
```

### Manual install

Copy this skill folder into the agent's skills directory:

| Agent | Global | Workspace |
|-------|--------|-----------|
| Claude Code | `~/.claude/skills/<skill-name>/` | `./.claude/skills/<skill-name>/` |
| Roo Code | `~/.roo/skills/<skill-name>/` | `./.roo/skills/<skill-name>/` |
| Cline | `~/.cline/skills/<skill-name>/` | `./.cline/skills/<skill-name>/` |

## Examples

### Example 1 — <short title>

```bash
python3 scripts/<entry>.py ./example-input
```

Expected output:

```text
<what the user should see>
```
