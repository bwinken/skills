---
name: document-organizer
description: "Safely organize a folder of files — classify by content, group by metadata, find duplicates, or rename en masse. Four modes, one skill, with a scan → plan → execute → undo workflow that never mutates anything without dry-run review. Use whenever the user asks to 'organize my Downloads', 'sort these files', 'find duplicates', 'rename these scans', 'group by month', or any folder cleanup request."
compatibility: "Claude Code, Roo Code, Cline"
---

# Document Organizer

## Overview

`document-organizer` turns messy folders (a chaotic `~/Downloads`, a pile of scanned PDFs, years of receipts) into organized, navigable structures. **Four modes**, unified by the same safe execution pipeline:

| Mode | What it does | LLM involved? |
|---|---|---|
| `classify` | Sort files into subfolders by content (`invoice/`, `contract/`, ...) | ✅ LLM decides each file's category |
| `by-metadata` | Group by mtime (year/month/day), extension, or size | ❌ Fully deterministic |
| `dedup` | Find duplicate files (by hash or by name), move copies to `_duplicates/` | ❌ Fully deterministic |
| `rename` | Rename files using an agent-provided mapping | ✅ LLM designs new names |

All four modes share the same **four-phase workflow**:

```
  scan   →   plan   →   execute   →   (optional) undo
  ↓          ↓          ↓              ↓
 metadata   dry-run   real moves     reverse
 for LLM    preview   + undo log     from log
```

**Never destructive by default.** `execute` is a dry-run unless `--execute` is passed. Every real execute writes an undo log so you can always roll back.

## When to use

Fire this skill when the user's request is about **reorganizing a folder of files**:

- **Classify by content**: "Organize my Downloads", "Sort my receipts by type", "File these PDFs into categories"
- **Group by metadata**: "Archive files by month", "Separate PDFs from Word docs", "Group these by year", "Sort by file type"
- **Find duplicates**: "Find duplicate PDFs", "Are there any copies of this file?", "Deduplicate my screenshots folder"
- **Rename**: "Give these scans readable names", "Rename these files based on their content", "Batch-rename these invoices"

Pick the mode based on the verb the user uses: *organize/classify/sort* → `classify` or `by-metadata`; *duplicate/copies* → `dedup`; *rename* → `rename`.

## When NOT to use

- The user wants to **delete** files. This skill never deletes. Dedup moves duplicates to `_duplicates/` but never `rm`'s anything.
- The user has **one** file to move or rename. Use the agent's built-in file tools — this skill is for batches.
- The target folder is a **git repo / project root** — by default the skill refuses (soft warning). Explicit `--force-dangerous` can override but think twice.
- The user wants to **edit file contents**, not move them. This is a filesystem skill, not a content editor.
- The user wants **smart semantic search** inside files before organizing — use [`document-search`](../document-search/) first, then pipe the results into this skill.

## The four-phase workflow

**Always** follow this sequence. Never skip phases, never guess.

### Phase 1 — Scan

The agent runs `scan` to discover what's in the folder. Different modes return different data:

```bash
# Classify mode — files + content preview (text files only)
python /path/to/scripts/document_organizer.py scan <folder> \
    --mode classify --content-preview 500 --format json

# By-metadata mode — files + computed mapping (already deterministic)
python /path/to/scripts/document_organizer.py scan <folder> \
    --mode by-metadata --group-by mtime-month --format json

# Dedup mode — files + hash-grouped duplicate sets
python /path/to/scripts/document_organizer.py scan <folder> \
    --mode dedup --match hash --format json

# Rename mode — files + content preview
python /path/to/scripts/document_organizer.py scan <folder> \
    --mode rename --content-preview 500 --format json
```

The scan reads any `.document-organizer-rules.json` state file in the folder and uses its preferences (categories, group_by, match, template) unless you override with a CLI flag.

### Phase 2 — The agent decides

For `classify` and `rename`, the LLM looks at the scan output and produces a **mapping** — a JSON object:

```json
{
  "Scan_0042.pdf": "invoice",
  "Contract_signed.pdf": "contract",
  "IMG_1234.jpg": "misc"
}
```

For `by-metadata` and `dedup`, the mapping is already computed by the scan itself — the agent just reads it from the scan output.

**Always show the mapping to the user before moving on to plan.** They need to confirm the categories / destinations before anything touches disk.

### Phase 3 — Plan

`plan` takes the mapping and produces a dry-run preview of every move:

```bash
python /path/to/scripts/document_organizer.py plan <folder> \
    --mode classify --mapping <inline-json-or-file> \
    [--target /other/folder] \
    --format json
```

The plan lists every `source_path → target_path` pair. It handles:

- **Validation**: rejects bad category names (contains `/`, `..`, starts with `.`, Windows reserved names)
- **Collisions**: if two files would end up at the same target, auto-appends ` (2)`, ` (3)`, ...
- **Missing sources**: reports any mapping keys that don't exist on disk

If `plan` has errors, stop and tell the user — don't try to `execute`.

### Phase 4 — Execute

```bash
python /path/to/scripts/document_organizer.py execute <folder> \
    --mode classify --mapping <inline-json-or-file> \
    [--target /other/folder] \
    --execute \
    --format json
```

**Important:** Without `--execute`, this is still a **dry run**. You must pass `--execute` explicitly to perform real moves. This is the main safety mechanism of the skill.

On success, `execute` writes an undo log to `<folder>/.document-organizer-undo/undo-<mode>-<timestamp>.json`. The log path is printed in the output; show it to the user in case they want to reverse.

### Phase 5 — Undo (if needed)

```bash
python /path/to/scripts/document_organizer.py undo \
    --log /path/to/undo-log.json --execute --format json
```

Same `--execute` safety — default is dry-run. Restores every file to its original location.

## State management

Each folder can have its own `.document-organizer-rules.json` storing per-folder preferences:

```json
{
  "version": 1,
  "created": "2026-04-11",
  "updated": "2026-04-11",
  "classify": {
    "categories": ["invoice", "contract", "datasheet", "misc"]
  },
  "by_metadata": {
    "group_by": "mtime-month"
  },
  "dedup": {
    "match": "hash"
  },
  "rename": {
    "template": "{original}"
  },
  "notes": "Engineering downloads folder"
}
```

**State is only written by the `init-rules` subcommand.** Regular `scan`/`plan`/`execute` runs are read-only — they never modify the state file. This keeps occasional tweaks from permanently changing the folder's preferences.

### When to offer rules to the user

On the **first** classify/rename scan of a new folder, propose creating a rules file. Typical dialogue:

> "I see this folder mostly has datasheets and technical papers. The default categories don't fit well. Want me to create a rules file here with `datasheet, paper, spec, contract, misc`? Next time you run organize on this folder I'll use those automatically."

On subsequent scans of a folder with existing rules, just use them silently — don't keep re-asking.

```bash
# Write a rules file
python /path/to/scripts/document_organizer.py init-rules <folder> \
    --categories invoice,contract,datasheet,misc \
    --notes "My downloads folder"

# Inspect the current rules
python /path/to/scripts/document_organizer.py show-rules <folder>
```

## Safety — what the skill refuses to do

### Hard-rejected (no escape hatch)

These paths are **never** acceptable as the target folder:

- Filesystem root: `/`, `C:\`, `D:\`, ...
- Your home folder itself (not subfolders): `~`, `$HOME`, `C:\Users\<you>`
- Unix system folders: `/etc`, `/usr`, `/var`, `/bin`, `/sbin`, `/boot`, `/dev`, `/proc`, `/sys`, `/lib`, `/lib64`, `/tmp`
- Windows system folders: `C:\Windows`, `C:\Program Files`, `C:\Program Files (x86)`, `C:\ProgramData`

### Soft-rejected (override with `--force-dangerous`)

- Folders that look like a git / project root (contain `.git/`, `pyproject.toml`, `package.json`, `Cargo.toml`, `go.mod`)

### Always enforced

- **Dry-run by default** — `execute` does nothing without `--execute`
- **Undo log** — every real execute writes a reversal log
- **No cross-device moves** — refuses if source and target are on different drives/mount points
- **Category name validation** — rejects `..`, `/`, `\`, leading `.`, Windows reserved names (`con`, `prn`, `nul`, etc.)
- **Collision resolution** — never overwrites an existing file, auto-appends ` (2)`
- **Never deletes** — dedup moves duplicates to `_duplicates/` for the user to review

## Critical rules

1. **Never call `execute` without `--execute`** when the user has confirmed — the flag is explicit on purpose.
2. **Never skip the `plan` phase** — always show a dry-run preview before executing.
3. **Never guess the mapping** for `classify`/`rename` — always present it to the user for approval first.
4. **Never use `--force-dangerous` on a git repo root** without asking the user twice. Really.
5. **Always show the undo log path** after execute — the user may want it.
6. **Never delete anything** — not even dedup. Duplicates go to `_duplicates/`.

## Helper-script layout

```
skills/document-organizer/
├── SKILL.md
├── README.md
└── scripts/
    ├── document_organizer.py    # Single main script, six subcommands
    └── _preflight.py             # Bilingual install guide helper (unused by this skill — stdlib only)
```

Subcommands:

| Subcommand | Phase | Purpose |
|---|---|---|
| `scan <folder> --mode <mode>` | 1 | Return file metadata for the LLM |
| `plan <folder> --mode <mode> --mapping <json>` | 3 | Validate and dry-run-preview the moves |
| `execute <folder> --mode <mode> --mapping <json> --execute` | 4 | Actually perform the moves |
| `undo --log <path> --execute` | 5 | Reverse a previous execute |
| `init-rules <folder> [--categories ...]` | — | Write per-folder state file |
| `show-rules <folder>` | — | Inspect per-folder state file |

All subcommands accept `--format text|json`. Prefer JSON when the agent is reading the output programmatically.

## Requirements

- Python 3.8+ — standard library only
- No optional dependencies

## Installation

See the [root README](../../README.md#installation) — covers the one-file installer, Claude Code plugin marketplace, and manual install paths for Claude Code / Roo Code / Cline.
