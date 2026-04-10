# <skill-name>

> <One-line description of what this skill does.>

<A short paragraph (2–4 sentences) introducing the skill. What problem does it solve? Who is it for? What makes it different from a naive approach?>

---

## Requirements

- **Python 3.8+** (or Node, or whichever runtime your skill needs)
- **Standard library only** for core functionality
- **Optional dependencies** for extended features:
  - `<package-a>` — <what it adds>
  - `<package-b>` — <what it adds>

Install optional dependencies with:

```bash
pip install <package-a> <package-b>
```

---

## Installation

Clone the parent repo and use this skill directly:

```bash
git clone https://github.com/bwinken/skills-library.git
cd skills-library/skills/<skill-name>
```

Or copy just this folder into your own project / agent configuration:

```bash
cp -r skills/<skill-name> /destination/
```

---

## Usage

### Basic

```bash
python3 scripts/<entry>.py <required-arg>
```

### With options

```bash
python3 scripts/<entry>.py <required-arg> --flag value
```

### Options

| Flag | Default | Description |
|------|---------|-------------|
| `--example` | `value` | <What this flag controls.> |
| `--format` | `text` | Output format (`text` or `json`). |

Run `python3 scripts/<entry>.py --help` for the full list.

---

## Output format

### Text mode

```text
<sample text output>
```

### JSON mode

```json
{
  "example": "value",
  "items": []
}
```

---

## Examples

### Example 1 — <short title>

```bash
python3 scripts/<entry>.py ./examples/input
```

<What this does, and what the user should see.>

### Example 2 — <short title>

```bash
python3 scripts/<entry>.py ./examples/input --format json
```

<What this does.>

---

## How it works

<Optional: a brief explanation of the implementation strategy, so users understand the skill's guarantees and limits.>

---

## See also

- [SKILL.md](SKILL.md) — agent-facing definition
- [Root README](../../README.md)
- [CONTRIBUTING](../../CONTRIBUTING.md)
