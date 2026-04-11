# document-organizer

> Safely organize a folder of files — four modes, one skill, with a scan → plan → execute → undo pipeline that never mutates anything without your review.

`document-organizer` is the first skill in the `document-organizer` plugin and covers the whole document-organization cluster originally planned in the roadmap (classifier / metadata-organizer / deduplicator / renamer) as four modes of a single tool. It's designed to be the go-to skill when the user says "clean up my Downloads", "sort these files", "find duplicates", or "rename these scans".

The most important design decision is **safety**. This skill moves files on the user's disk — destructive operations deserve serious guardrails. Every mode:

- Refuses to touch filesystem roots, home, or system folders
- Warns before operating on git repos
- Is **dry-run by default** — you pass `--execute` explicitly to make real changes
- Writes an **undo log** on every real execute so you can always roll back
- Never deletes (dedup moves duplicates aside, it doesn't `rm` them)

---

## The four modes

| Mode | Purpose | Example trigger |
|---|---|---|
| **classify** | Sort files into content-labeled subfolders (`invoice/`, `contract/`, ...) | "Organize my Downloads by type" |
| **by-metadata** | Group files by mtime (year/month/day), extension, or size bucket | "Archive these by month" |
| **dedup** | Find duplicate files by hash or name, move copies to `_duplicates/` | "Find duplicate PDFs" |
| **rename** | Batch-rename files using a mapping the LLM generates from content | "Give these scans readable names" |

`classify` and `rename` use the LLM to make per-file decisions. `by-metadata` and `dedup` are fully deterministic — no LLM needed.

All four modes share the same **four-phase workflow**:

```
scan   →   plan   →   execute   →   undo
```

See [SKILL.md](SKILL.md) for the agent-facing description of how each phase works.

---

## Features

- **Non-destructive** — dry-run by default, always writes an undo log, never deletes
- **Hard-rejects dangerous targets** — `/`, `~`, `C:\Windows`, `/etc`, etc.
- **Soft-rejects git repo roots** — requires `--force-dangerous` to override
- **Collision-safe** — auto-appends ` (2)`, ` (3)`, ... if a target filename already exists
- **Cross-device safe** — refuses to move between drives / mount points
- **Per-folder state file** — `.document-organizer-rules.json` remembers your preferences (categories, group-by strategy, dedup match mode, rename template)
- **Pure stdlib** — no third-party dependencies, Python 3.8+

---

## Requirements

- **Python 3.8+** (standard library only)
- That's it. No optional packages, no network calls, no pip install.

---

## Install

```bash
# Interactive wizard (recommended — picks agent + scope)
python install.py

# Or directly
python install.py install document-organizer --agent claude
```

See the [root README](../../README.md#installation) for the full story: one-file installer without `git clone`, Claude Code plugin marketplace (`document-organizer` plugin), Roo Code and Cline setup, workspace vs global scope, and manual install paths.

---

## Usage

The full API surface is six subcommands on `document_organizer.py`:

| Subcommand | When to use |
|---|---|
| `scan <folder> --mode <mode>` | Phase 1: discover what's in the folder |
| `plan <folder> --mode <mode> --mapping <json>` | Phase 3: preview the moves as a dry-run |
| `execute <folder> --mode <mode> --mapping <json> --execute` | Phase 4: actually perform moves + write undo log |
| `undo --log <path> --execute` | Phase 5: reverse a previous execute |
| `init-rules <folder> [...]` | One-time: write per-folder preferences |
| `show-rules <folder>` | Inspect per-folder preferences |

All subcommands accept `--format text|json`.

### Example 1 — classify mode: organize `~/Downloads` by content

**Step 1: scan with content preview**

```bash
python3 scripts/document_organizer.py scan ~/Downloads --mode classify \
    --content-preview 500 --format json > /tmp/scan.json
```

The agent reads `/tmp/scan.json`, sees filenames and content previews for each text file, and decides a category for each.

**Step 2: plan the moves**

```bash
python3 scripts/document_organizer.py plan ~/Downloads --mode classify \
    --mapping '{"invoice_acme.pdf":"invoice","contract.pdf":"contract","Scan_0042.pdf":"misc"}'
```

Output:

```text
# document-organizer — plan (classify)
source: /home/alice/Downloads
target: /home/alice/Downloads
moves:  3

## Planned moves
  /home/alice/Downloads/invoice_acme.pdf
    → /home/alice/Downloads/invoice/invoice_acme.pdf  [classify:invoice]
  /home/alice/Downloads/contract.pdf
    → /home/alice/Downloads/contract/contract.pdf  [classify:contract]
  /home/alice/Downloads/Scan_0042.pdf
    → /home/alice/Downloads/misc/Scan_0042.pdf  [classify:misc]
```

**Step 3: execute (pass `--execute` explicitly)**

```bash
python3 scripts/document_organizer.py execute ~/Downloads --mode classify \
    --mapping '{"invoice_acme.pdf":"invoice","contract.pdf":"contract","Scan_0042.pdf":"misc"}' \
    --execute
```

Output:

```text
# document-organizer — execute
moved:   3
skipped: 0

Undo log: /home/alice/Downloads/.document-organizer-undo/undo-classify-20260411-143022.json
To reverse: python document_organizer.py undo --log ... --execute
```

**Step 4: undo if needed**

```bash
python3 scripts/document_organizer.py undo \
    --log /home/alice/Downloads/.document-organizer-undo/undo-classify-20260411-143022.json \
    --execute
```

### Example 2 — by-metadata mode: archive by month

By-metadata is fully deterministic. The scan already computes the mapping.

```bash
python3 scripts/document_organizer.py scan ~/Archive/2026 \
    --mode by-metadata --group-by mtime-month
```

```text
# document-organizer — scan (by-metadata)
source: /home/alice/Archive/2026
files:  47
group_by: mtime-month

## Proposed mapping (deterministic)
  2026-01/
    invoice_jan_01.pdf
    invoice_jan_15.pdf
    ...
  2026-02/
    ...
```

Then pass the mapping into `execute`. For `by-metadata`, the mapping comes from the scan's own output:

```bash
python3 scripts/document_organizer.py scan ~/Archive/2026 \
    --mode by-metadata --group-by mtime-month --format json > /tmp/scan.json

# Agent extracts the .mapping field from scan.json and passes it to execute
```

### Example 3 — dedup mode: find duplicate photos

```bash
python3 scripts/document_organizer.py scan ~/Pictures --mode dedup --match hash
```

```text
# document-organizer — scan (dedup)
source: /home/alice/Pictures
files:  2348
match: hash

## Duplicate groups: 17
  Group 1 (3 files):
    [keep] 2024/IMG_1234.jpg
    [→ _duplicates/] 2025/backup/IMG_1234.jpg
    [→ _duplicates/] Desktop/IMG_1234_copy.jpg
  Group 2 (2 files):
    ...
```

Then execute to move the duplicates aside (never deletes):

```bash
python3 scripts/document_organizer.py execute ~/Pictures --mode dedup \
    --mapping '<the mapping field from scan output>' \
    --execute
```

### Example 4 — rename mode: meaningful names for scans

```bash
python3 scripts/document_organizer.py scan ~/Scans --mode rename --content-preview 500
```

The agent reads the previews, figures out what each scan is about, and generates new names:

```bash
python3 scripts/document_organizer.py execute ~/Scans --mode rename \
    --mapping '{"Scan_0042.pdf":"2026-03-15-invoice-acme.pdf","Scan_0043.pdf":"2026-03-15-contract-signed.pdf"}' \
    --execute
```

### Example 5 — init-rules: remember per-folder preferences

```bash
python3 scripts/document_organizer.py init-rules ~/Downloads \
    --categories invoice,contract,datasheet,paper,misc \
    --notes "Engineering downloads folder"
```

Output:

```text
✓ rules file written: /home/alice/Downloads/.document-organizer-rules.json
  categories:  ['invoice', 'contract', 'datasheet', 'paper', 'misc']
  group_by:    mtime-month
  dedup match: hash
  rename tpl:  {original}
  notes:       Engineering downloads folder
```

Next time you run `scan ~/Downloads --mode classify`, the skill automatically picks up these 5 categories instead of the 9 defaults.

---

## Full option list

### `scan`

| Flag | Default | Description |
|------|---------|-------------|
| `folder` (**required**) | — | Folder to scan |
| `--mode` | `classify` | `classify` / `by-metadata` / `dedup` / `rename` |
| `--categories a,b,c` | *(from rules or defaults)* | [classify] Override category list |
| `--group-by KEY` | *(from rules or `mtime-month`)* | [by-metadata] `mtime-year` / `mtime-month` / `mtime-day` / `extension` / `size-bucket` |
| `--match` | *(from rules or `hash`)* | [dedup] `hash` or `name` |
| `--template STR` | *(from rules or `{original}`)* | [rename] Rename template |
| `--content-preview N` | `0` | Read first N bytes of text files for LLM preview |
| `--max-files N` | `1000` | Stop after N files |
| `--include-hidden` | off | Include dotfiles |
| `--force-dangerous` | off | Operate on a git repo root anyway |
| `--format` | `text` | `text` or `json` |

### `plan`

| Flag | Default | Description |
|------|---------|-------------|
| `folder` (**required**) | — | Source folder |
| `--mode` (**required**) | — | Mode |
| `--mapping` (**required**) | — | JSON file path *or* inline JSON string |
| `--target` | same as source | Move destination |
| `--force-dangerous` | off | |
| `--format` | `text` | |

### `execute`

Same as `plan` plus:

| Flag | Default | Description |
|------|---------|-------------|
| `--execute` | off | **Required to perform real moves.** Without it, execute is a dry run. |

### `undo`

| Flag | Default | Description |
|------|---------|-------------|
| `--log` (**required**) | — | Path to a previously-written undo log |
| `--execute` | off | Required to perform the restore |
| `--format` | `text` | |

### `init-rules`

| Flag | Default | Description |
|------|---------|-------------|
| `folder` (**required**) | — | Folder to write the rules file in |
| `--categories a,b,c` | — | [classify] Category list |
| `--group-by KEY` | — | [by-metadata] Default strategy |
| `--dedup-match` | — | [dedup] `hash` / `name` |
| `--rename-template` | — | [rename] Default template |
| `--notes` | — | Free-text notes |
| `--force` | off | Overwrite existing rules |
| `--force-dangerous` | off | |
| `--format` | `text` | |

### `show-rules`

| Flag | Default | Description |
|------|---------|-------------|
| `folder` (**required**) | — | Folder to inspect |
| `--format` | `text` | |

---

## State file schema

`.document-organizer-rules.json` in any organized folder:

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

The file is only created when you explicitly run `init-rules`. `scan`/`plan`/`execute` never modify it — they just read it for preferences.

---

## Safety recap

| Layer | What it prevents |
|---|---|
| **Hard-banned paths** | Operating on `/`, `~`, `C:\Windows`, `/etc`, etc. No override. |
| **Soft-banned paths** | Operating on git repos without `--force-dangerous`. |
| **Dry-run default** | `execute` does nothing unless `--execute` is passed. |
| **Undo log** | Every real execute writes a reversal log. |
| **Collision resolution** | Never overwrites an existing file; auto-appends ` (2)`. |
| **Category validation** | Rejects `..`, `/`, `\`, leading `.`, Windows reserved names. |
| **Cross-device refused** | Won't move files across drives / mount points. |
| **Never deletes** | Dedup moves duplicates to `_duplicates/` for user review. |

---

## See also

- [SKILL.md](SKILL.md) — agent-facing skill definition with the full four-phase workflow
- [Root README](../../README.md) — the full skills library
- [ROADMAP](../../ROADMAP.md) — this skill replaces the four-item organizer cluster (classifier / metadata-organizer / deduplicator / renamer) with a single unified skill
- [CONTRIBUTING](../../CONTRIBUTING.md) — how to add your own skill
