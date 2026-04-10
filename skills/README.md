# Skills

This directory holds every skill in SkillForge. Each subfolder is a self-contained skill that can be dropped into any AI coding agent.

## Index

| Skill | Description |
|-------|-------------|
| [file-scanner](file-scanner/) | Recursively scan a workspace and extract text content from 60+ file types (code, markdown, Word, PDF, PowerPoint, Excel, and more). Supports extension filtering, grep, size limits, and JSON output. |

## Adding a new skill

See the top-level [CONTRIBUTING.md](../CONTRIBUTING.md) for the full contribution guide, or the quick version:

```bash
mkdir -p skills/<skill-name>/scripts
cp templates/SKILL_TEMPLATE.md skills/<skill-name>/SKILL.md
cp templates/README_TEMPLATE.md skills/<skill-name>/README.md
# ... implement scripts/, fill in SKILL.md + README.md, add a row above ...
```

## Layout of a skill folder

```
skills/<skill-name>/
├── SKILL.md       # Agent-facing definition (frontmatter + usage + options)
├── README.md      # Human-facing GitHub page
└── scripts/       # Implementation (Python, shell, Node, ...)
    └── <entry>.py
```
