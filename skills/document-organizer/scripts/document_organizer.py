#!/usr/bin/env python3
"""
document-organizer — a safe, four-mode folder organizer.

One skill, four modes, shared safety infrastructure:

  * classify    — group files into content-driven folders. The LLM supplies
                  the per-file category; the skill validates and executes.
  * by-metadata — group files by mtime / extension / filename pattern.
                  Fully deterministic, no LLM required.
  * dedup       — find duplicate files by hash (and optionally by name).
                  Moves duplicates to a `_duplicates/` subfolder, never deletes.
  * rename      — rename files using an agent-provided mapping. Same safety
                  guarantees as move.

Unified four-phase workflow for every mode:

      scan  →  plan  →  execute  →  (optional) undo

`scan` returns file metadata the agent needs to make decisions. The agent
(or the user) produces a `mapping.json` — a `{source_file: target}` dict.
`plan` validates the mapping and prints a dry-run summary. `execute`
performs the actual moves and writes an undo log. `undo` reverses a
previous execute by reading the log back.

Non-destructive guarantees (see safety module):
  * Refuses to operate on `/`, `C:\\`, `$HOME`, `/etc`, `C:\\Windows`, ...
  * Requires `--force-dangerous` to operate on a git repo root.
  * Never deletes files. Dedup moves duplicates to `_duplicates/`.
  * Refuses cross-device moves.
  * Auto-appends `(2)`, `(3)`, ... on filename collisions.
  * `execute` is a no-op unless `--execute` is passed (dry-run by default).
  * Every `execute` writes an undo log under `<source>/.document-organizer-undo/`.

State file: `<source>/.document-organizer-rules.json` stores per-folder
preferences (category list for `classify`, template for `rename`, etc.).
Only written when the user runs `init-rules`; `execute` does not auto-write.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

STATE_FILENAME = ".document-organizer-rules.json"
STATE_VERSION = 1
UNDO_LOG_DIR = ".document-organizer-undo"

# Default category list used by the `classify` mode when no state file
# exists. Users can override via `init-rules --categories a,b,c` or
# the `--categories` flag on `scan`.
DEFAULT_CATEGORIES = [
    "invoice",
    "receipt",
    "contract",
    "report",
    "tax",
    "manual",
    "article",
    "personal",
    "misc",
]

# Default subfolder name where dedup mode parks duplicates.
DEDUP_SUBFOLDER = "_duplicates"

# Default group-by strategy for by-metadata mode.
DEFAULT_METADATA_GROUP = "mtime-month"
VALID_METADATA_GROUPS = {
    "mtime-year",
    "mtime-month",
    "mtime-day",
    "extension",
    "size-bucket",
}

# Which file extensions count as "text-readable" for --content-preview.
TEXT_PREVIEW_EXTENSIONS = {
    ".txt", ".md", ".markdown", ".rst", ".log", ".csv", ".tsv",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".xml", ".html", ".htm", ".svg",
    ".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rs",
    ".c", ".cpp", ".h", ".hpp", ".cs", ".rb", ".php", ".sh", ".bash",
}

# Binary-wrapped formats we know about but won't read for preview — agents
# should use the document-readers skills to extract content from these.
BINARY_FORMATS = {".pdf", ".docx", ".pptx", ".xlsx"}


# ---------------------------------------------------------------------------
# Safety module
# ---------------------------------------------------------------------------

class UnsafePathError(RuntimeError):
    """Raised when a path would be unsafe to operate on."""


def _home() -> Path:
    return Path(os.path.expanduser("~")).resolve()


def _normalize(path: Path) -> Path:
    """Resolve to absolute, follow symlinks, normalize separators."""
    return path.expanduser().resolve()


def _is_filesystem_root(path: Path) -> bool:
    """True if path is a filesystem root like `/` or `C:\\`."""
    return path == path.parent


# Hard-rejected paths: no `--force-dangerous` escape hatch for these.
_HARD_BANNED_UNIX = {
    Path("/"),
    Path("/etc"),
    Path("/usr"),
    Path("/var"),
    Path("/bin"),
    Path("/sbin"),
    Path("/boot"),
    Path("/dev"),
    Path("/proc"),
    Path("/sys"),
    Path("/lib"),
    Path("/lib64"),
    Path("/tmp"),    # safer to refuse; /tmp contents may be live session data
}
_HARD_BANNED_WINDOWS_NAMES = {
    "windows", "program files", "program files (x86)",
    "programdata", "system volume information", "$recycle.bin",
}


def _check_hard_banned(target: Path) -> Optional[str]:
    """Return a rejection reason if `target` is a hard-banned root, else None."""
    resolved = _normalize(target)

    # Filesystem root (e.g. /, C:\, D:\)
    if _is_filesystem_root(resolved):
        return f"refusing to operate on filesystem root: {resolved}"

    # User home folder itself (not subfolders)
    if resolved == _home():
        return (
            f"refusing to operate on your home folder itself: {resolved}. "
            "Pick a specific subfolder like ~/Downloads or ~/Documents."
        )

    # Unix hard-banned paths
    if sys.platform != "win32":
        if resolved in _HARD_BANNED_UNIX:
            return f"refusing to operate on system folder: {resolved}"

    # Windows hard-banned paths — check drive root + banned top-level names
    else:
        parts = resolved.parts
        if len(parts) >= 2:
            # parts[0] is like 'C:\\', parts[1] is the top-level folder name
            top_level = parts[1].lower()
            if top_level in _HARD_BANNED_WINDOWS_NAMES:
                return f"refusing to operate on Windows system folder: {resolved}"

    return None


def _looks_like_git_repo_root(target: Path) -> bool:
    """Heuristic: does this folder look like the root of a git repo?"""
    markers = [".git", ".hg", ".svn", "pyproject.toml", "package.json", "Cargo.toml", "go.mod"]
    return any((target / m).exists() for m in markers)


def check_safety(target: Path, *, force_dangerous: bool = False) -> None:
    """
    Verify it's safe to operate on `target`. Raises UnsafePathError on violation.

    Hard-banned roots (filesystem root, $HOME itself, system folders) are
    always rejected. Repo-like folders trigger a soft warning that can be
    overridden with `--force-dangerous`.
    """
    target = _normalize(target)

    if not target.exists():
        raise UnsafePathError(f"target does not exist: {target}")
    if not target.is_dir():
        raise UnsafePathError(f"target is not a directory: {target}")

    # Hard-banned list
    reason = _check_hard_banned(target)
    if reason:
        raise UnsafePathError(reason)

    # Soft check: repo root
    if _looks_like_git_repo_root(target) and not force_dangerous:
        raise UnsafePathError(
            f"{target} looks like a version-controlled project root "
            "(contains .git/, pyproject.toml, or similar). Refusing by default. "
            "Pass --force-dangerous if you really meant this."
        )


def check_same_device(source: Path, target: Path) -> None:
    """Refuse cross-device moves. On Windows, compares drive letters."""
    source = _normalize(source)
    target = _normalize(target)

    if sys.platform == "win32":
        # Compare drive letters
        if source.drive.lower() != target.drive.lower():
            raise UnsafePathError(
                f"cross-drive move: {source.drive} → {target.drive}. "
                "Refusing for safety; move manually or use --target on the same drive."
            )
    else:
        # Compare Unix device ids
        try:
            s_dev = source.stat().st_dev
            # For the target we check the parent (target may not exist yet)
            t_dev = target.parent.stat().st_dev if target.exists() or target.parent.exists() else s_dev
            if s_dev != t_dev:
                raise UnsafePathError(
                    f"cross-device move detected (different st_dev). "
                    "Refusing for safety."
                )
        except OSError:
            pass  # Best-effort; if stat fails, let the move itself fail later


def validate_category_name(name: str) -> None:
    """Reject dangerous characters in category / target folder names."""
    if not name:
        raise UnsafePathError("empty category name")
    if name in (".", ".."):
        raise UnsafePathError(f"reserved category name: {name!r}")
    if "/" in name or "\\" in name:
        raise UnsafePathError(f"category name must not contain path separators: {name!r}")
    if name.startswith(".") and name not in (".trash",):
        # Allow specific dotfolders, reject others to avoid hidden file tricks
        raise UnsafePathError(f"category name must not start with '.': {name!r}")
    # Reserved Windows names
    reserved = {"con", "prn", "aux", "nul",
                "com1", "com2", "com3", "com4", "com5", "com6", "com7", "com8", "com9",
                "lpt1", "lpt2", "lpt3", "lpt4", "lpt5", "lpt6", "lpt7", "lpt8", "lpt9"}
    if name.lower() in reserved:
        raise UnsafePathError(f"reserved Windows name: {name!r}")


# ---------------------------------------------------------------------------
# State module — .document-organizer-rules.json
# ---------------------------------------------------------------------------

@dataclass
class Rules:
    version: int = STATE_VERSION
    created: str = ""
    updated: str = ""
    classify: dict = field(default_factory=lambda: {"categories": list(DEFAULT_CATEGORIES)})
    by_metadata: dict = field(default_factory=lambda: {"group_by": DEFAULT_METADATA_GROUP})
    dedup: dict = field(default_factory=lambda: {"match": "hash"})
    rename: dict = field(default_factory=lambda: {"template": "{original}"})
    notes: str = ""

    @classmethod
    def default(cls) -> "Rules":
        today = dt.date.today().isoformat()
        return cls(created=today, updated=today)


def rules_path(folder: Path) -> Path:
    return folder / STATE_FILENAME


def load_rules(folder: Path) -> Rules:
    """Load rules from <folder>/.document-organizer-rules.json, or return defaults."""
    path = rules_path(folder)
    if not path.exists():
        return Rules.default()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as e:
        raise UnsafePathError(f"cannot read rules file {path}: {e}")

    if not isinstance(data, dict):
        raise UnsafePathError(f"rules file is not a JSON object: {path}")

    version = data.get("version", 1)
    if version != STATE_VERSION:
        raise UnsafePathError(
            f"rules file version {version} is incompatible with this script "
            f"(expected {STATE_VERSION}). Upgrade the skill or delete the rules file."
        )

    rules = Rules.default()
    if "created" in data:
        rules.created = data["created"]
    if "updated" in data:
        rules.updated = data["updated"]
    if isinstance(data.get("classify"), dict):
        rules.classify.update(data["classify"])
    if isinstance(data.get("by_metadata"), dict):
        rules.by_metadata.update(data["by_metadata"])
    if isinstance(data.get("dedup"), dict):
        rules.dedup.update(data["dedup"])
    if isinstance(data.get("rename"), dict):
        rules.rename.update(data["rename"])
    if "notes" in data:
        rules.notes = data["notes"]
    return rules


def save_rules(folder: Path, rules: Rules) -> None:
    """Write rules back to disk. Bumps `updated` to today."""
    rules.updated = dt.date.today().isoformat()
    path = rules_path(folder)
    path.write_text(
        json.dumps(asdict(rules), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Undo log module
# ---------------------------------------------------------------------------

@dataclass
class UndoEntry:
    source: str     # absolute path before the move
    target: str     # absolute path after the move
    timestamp: str  # ISO datetime


@dataclass
class UndoLog:
    version: int = 1
    created: str = ""
    mode: str = ""
    source_folder: str = ""
    target_folder: str = ""
    entries: list[UndoEntry] = field(default_factory=list)


def undo_log_dir(folder: Path) -> Path:
    return folder / UNDO_LOG_DIR


def new_undo_log_path(folder: Path, mode: str) -> Path:
    """Generate a fresh undo log filename under the folder's .undo dir."""
    stamp = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    return undo_log_dir(folder) / f"undo-{mode}-{stamp}.json"


def write_undo_log(path: Path, log: UndoLog) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "version": log.version,
                "created": log.created,
                "mode": log.mode,
                "source_folder": log.source_folder,
                "target_folder": log.target_folder,
                "entries": [asdict(e) for e in log.entries],
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def read_undo_log(path: Path) -> UndoLog:
    data = json.loads(path.read_text(encoding="utf-8"))
    if data.get("version") != 1:
        raise UnsafePathError(f"unknown undo log version: {data.get('version')}")
    log = UndoLog(
        version=data["version"],
        created=data.get("created", ""),
        mode=data.get("mode", ""),
        source_folder=data.get("source_folder", ""),
        target_folder=data.get("target_folder", ""),
    )
    for e in data.get("entries", []):
        log.entries.append(UndoEntry(
            source=e["source"],
            target=e["target"],
            timestamp=e.get("timestamp", ""),
        ))
    return log


# ---------------------------------------------------------------------------
# File metadata extraction
# ---------------------------------------------------------------------------

@dataclass
class FileMeta:
    path: str               # absolute path
    rel_path: str           # relative to the scanned folder
    name: str               # basename
    extension: str          # lowercase, includes the dot (.pdf), or "" if none
    size: int               # bytes
    mtime: str              # ISO date
    content_preview: Optional[str] = None
    hash: Optional[str] = None


def _hash_file(path: Path, algo: str = "sha256", chunk: int = 65536) -> str:
    h = hashlib.new(algo)
    try:
        with path.open("rb") as f:
            while True:
                data = f.read(chunk)
                if not data:
                    break
                h.update(data)
    except OSError:
        return ""
    return h.hexdigest()


def _read_preview(path: Path, max_bytes: int) -> Optional[str]:
    """Read the first `max_bytes` of a text-looking file. Returns None if binary / unreadable."""
    ext = path.suffix.lower()
    if ext not in TEXT_PREVIEW_EXTENSIONS:
        return None
    try:
        with path.open("rb") as f:
            raw = f.read(max_bytes)
        return raw.decode("utf-8", errors="replace")
    except OSError:
        return None


def scan_files(
    folder: Path,
    *,
    include_hidden: bool,
    max_files: int,
    content_preview_bytes: int,
    compute_hash: bool,
    recursive: bool,
) -> list[FileMeta]:
    """Walk `folder`, return metadata for each regular file."""
    results: list[FileMeta] = []
    count = 0

    iterator = folder.rglob("*") if recursive else folder.iterdir()
    for p in sorted(iterator):
        if max_files and count >= max_files:
            break
        if not p.is_file():
            continue
        name = p.name
        if not include_hidden and name.startswith("."):
            continue
        # Also skip the state file and undo log folder
        if name == STATE_FILENAME:
            continue
        if UNDO_LOG_DIR in p.parts:
            continue

        try:
            st = p.stat()
        except OSError:
            continue

        rel = p.relative_to(folder).as_posix()
        mtime = dt.datetime.fromtimestamp(st.st_mtime).date().isoformat()
        meta = FileMeta(
            path=str(p),
            rel_path=rel,
            name=name,
            extension=p.suffix.lower(),
            size=st.st_size,
            mtime=mtime,
        )
        if content_preview_bytes > 0:
            meta.content_preview = _read_preview(p, content_preview_bytes)
        if compute_hash:
            meta.hash = _hash_file(p)
        results.append(meta)
        count += 1

    return results


# ---------------------------------------------------------------------------
# Mode: classify
# ---------------------------------------------------------------------------

@dataclass
class ClassifyScanResult:
    mode: str
    source_folder: str
    categories: list[str]
    files: list[FileMeta]


def scan_classify(
    folder: Path,
    rules: Rules,
    *,
    categories_override: Optional[list[str]],
    content_preview_bytes: int,
    include_hidden: bool,
    max_files: int,
) -> ClassifyScanResult:
    categories = categories_override or list(rules.classify.get("categories") or DEFAULT_CATEGORIES)
    for c in categories:
        validate_category_name(c)
    files = scan_files(
        folder,
        include_hidden=include_hidden,
        max_files=max_files,
        content_preview_bytes=content_preview_bytes,
        compute_hash=False,
        recursive=False,
    )
    return ClassifyScanResult(
        mode="classify",
        source_folder=str(folder),
        categories=categories,
        files=files,
    )


# ---------------------------------------------------------------------------
# Mode: by-metadata
# ---------------------------------------------------------------------------

@dataclass
class ByMetadataScanResult:
    mode: str
    source_folder: str
    group_by: str
    mapping: dict[str, str]  # source rel path -> target subfolder
    files: list[FileMeta]


def _size_bucket(size: int) -> str:
    """Return a coarse size bucket label for a file size in bytes."""
    kb = size / 1024
    if kb < 100:
        return "small (<100KB)"
    if kb < 1024:
        return "medium (100KB-1MB)"
    mb = kb / 1024
    if mb < 10:
        return "large (1-10MB)"
    if mb < 100:
        return "xlarge (10-100MB)"
    return "huge (>100MB)"


def _metadata_group_label(meta: FileMeta, group_by: str) -> str:
    """Return the target subfolder name for a file under the given group-by rule."""
    if group_by == "mtime-year":
        return meta.mtime[:4]  # YYYY
    if group_by == "mtime-month":
        return meta.mtime[:7]  # YYYY-MM
    if group_by == "mtime-day":
        return meta.mtime      # YYYY-MM-DD
    if group_by == "extension":
        return meta.extension.lstrip(".") or "no-extension"
    if group_by == "size-bucket":
        return _size_bucket(meta.size)
    raise UnsafePathError(f"unknown group_by: {group_by}")


def scan_by_metadata(
    folder: Path,
    rules: Rules,
    *,
    group_by_override: Optional[str],
    include_hidden: bool,
    max_files: int,
) -> ByMetadataScanResult:
    group_by = group_by_override or rules.by_metadata.get("group_by") or DEFAULT_METADATA_GROUP
    if group_by not in VALID_METADATA_GROUPS:
        raise UnsafePathError(
            f"unknown group_by: {group_by!r}. "
            f"Valid: {sorted(VALID_METADATA_GROUPS)}"
        )
    files = scan_files(
        folder,
        include_hidden=include_hidden,
        max_files=max_files,
        content_preview_bytes=0,
        compute_hash=False,
        recursive=False,
    )
    # By-metadata is fully deterministic — we compute the mapping here,
    # no LLM needed.
    mapping: dict[str, str] = {}
    for f in files:
        label = _metadata_group_label(f, group_by)
        validate_category_name(label)
        mapping[f.rel_path] = label
    return ByMetadataScanResult(
        mode="by-metadata",
        source_folder=str(folder),
        group_by=group_by,
        mapping=mapping,
        files=files,
    )


# ---------------------------------------------------------------------------
# Mode: dedup
# ---------------------------------------------------------------------------

@dataclass
class DedupScanResult:
    mode: str
    source_folder: str
    match: str
    groups: list[list[str]]  # groups of duplicate rel paths
    mapping: dict[str, str]  # rel path -> target subfolder (DEDUP_SUBFOLDER)
    files: list[FileMeta]


def scan_dedup(
    folder: Path,
    rules: Rules,
    *,
    match_override: Optional[str],
    include_hidden: bool,
    max_files: int,
) -> DedupScanResult:
    match = match_override or rules.dedup.get("match") or "hash"
    if match not in ("hash", "name"):
        raise UnsafePathError(f"unknown dedup match mode: {match!r}. Valid: hash, name")

    compute_hash = (match == "hash")
    files = scan_files(
        folder,
        include_hidden=include_hidden,
        max_files=max_files,
        content_preview_bytes=0,
        compute_hash=compute_hash,
        recursive=True,  # dedup is recursive — duplicates can live in subfolders
    )

    # Group by hash or name
    if match == "hash":
        buckets: dict[str, list[FileMeta]] = {}
        for f in files:
            if f.hash:
                buckets.setdefault(f.hash, []).append(f)
    else:
        buckets = {}
        for f in files:
            buckets.setdefault(f.name.lower(), []).append(f)

    # A "duplicate group" is any bucket with >= 2 files
    groups: list[list[str]] = []
    mapping: dict[str, str] = {}
    for key, group in buckets.items():
        if len(group) < 2:
            continue
        # Sort by rel_path so the "kept" file is deterministic (first alphabetically)
        group_sorted = sorted(group, key=lambda f: f.rel_path)
        groups.append([f.rel_path for f in group_sorted])
        # The first file is kept in place; the rest go to _duplicates/
        for f in group_sorted[1:]:
            mapping[f.rel_path] = DEDUP_SUBFOLDER

    return DedupScanResult(
        mode="dedup",
        source_folder=str(folder),
        match=match,
        groups=groups,
        mapping=mapping,
        files=files,
    )


# ---------------------------------------------------------------------------
# Mode: rename
# ---------------------------------------------------------------------------

@dataclass
class RenameScanResult:
    mode: str
    source_folder: str
    template: str
    files: list[FileMeta]


def scan_rename(
    folder: Path,
    rules: Rules,
    *,
    template_override: Optional[str],
    content_preview_bytes: int,
    include_hidden: bool,
    max_files: int,
) -> RenameScanResult:
    template = template_override or rules.rename.get("template") or "{original}"
    files = scan_files(
        folder,
        include_hidden=include_hidden,
        max_files=max_files,
        content_preview_bytes=content_preview_bytes,
        compute_hash=False,
        recursive=False,
    )
    return RenameScanResult(
        mode="rename",
        source_folder=str(folder),
        template=template,
        files=files,
    )


# ---------------------------------------------------------------------------
# Plan subcommand
# ---------------------------------------------------------------------------

@dataclass
class PlannedMove:
    source_path: str   # absolute
    target_path: str   # absolute
    reason: str        # "classify:invoice" or "dedup:hash-match" etc.
    conflict_resolved: bool = False  # true if we appended (2)/(3)/...


@dataclass
class Plan:
    mode: str
    source_folder: str
    target_folder: str
    moves: list[PlannedMove] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def _resolve_collision(target: Path, planned_targets: set[str]) -> Path:
    """
    If `target` already exists or is already in `planned_targets`, append
    ` (2)`, ` (3)`, ... before the extension until we find a free name.
    """
    if str(target) not in planned_targets and not target.exists():
        return target
    stem = target.stem
    suffix = target.suffix
    parent = target.parent
    counter = 2
    while True:
        candidate = parent / f"{stem} ({counter}){suffix}"
        if str(candidate) not in planned_targets and not candidate.exists():
            return candidate
        counter += 1
        if counter > 1000:
            raise UnsafePathError(f"too many collisions for {target}")


def plan_moves(
    source_folder: Path,
    target_folder: Path,
    mapping: dict[str, str],
    *,
    mode: str,
    new_names: Optional[dict[str, str]] = None,
) -> Plan:
    """
    Given a mapping of `rel_path → target_subfolder` (for classify / by-metadata
    / dedup) or `rel_path → new_filename` (for rename), produce a Plan of
    absolute source→target moves. Handles filename collisions.
    """
    source_folder = _normalize(source_folder)
    target_folder = _normalize(target_folder)
    plan = Plan(
        mode=mode,
        source_folder=str(source_folder),
        target_folder=str(target_folder),
    )
    planned_targets: set[str] = set()

    if mode == "rename":
        # Rename mode: mapping is {rel_path: new_filename}. Files stay in place.
        for rel, new_name in mapping.items():
            src = source_folder / rel
            if not src.exists() or not src.is_file():
                plan.errors.append(f"source file not found: {rel}")
                continue
            try:
                validate_category_name(new_name)
            except UnsafePathError as e:
                plan.errors.append(f"invalid rename target for {rel}: {e}")
                continue
            if "/" in new_name or "\\" in new_name:
                plan.errors.append(f"rename target must not contain path separators: {new_name}")
                continue
            dst = src.parent / new_name
            if str(dst) == str(src):
                continue  # no-op
            original_dst = dst
            dst = _resolve_collision(dst, planned_targets)
            planned_targets.add(str(dst))
            plan.moves.append(PlannedMove(
                source_path=str(src),
                target_path=str(dst),
                reason=f"rename:{new_name}",
                conflict_resolved=(str(dst) != str(original_dst)),
            ))
        return plan

    # classify / by-metadata / dedup: mapping is {rel_path: target_subfolder}
    for rel, subfolder in mapping.items():
        src = source_folder / rel
        if not src.exists() or not src.is_file():
            plan.errors.append(f"source file not found: {rel}")
            continue
        try:
            validate_category_name(subfolder)
        except UnsafePathError as e:
            plan.errors.append(f"invalid subfolder for {rel}: {e}")
            continue

        dst_dir = target_folder / subfolder
        dst = dst_dir / src.name
        original_dst = dst
        dst = _resolve_collision(dst, planned_targets)
        planned_targets.add(str(dst))
        plan.moves.append(PlannedMove(
            source_path=str(src),
            target_path=str(dst),
            reason=f"{mode}:{subfolder}",
            conflict_resolved=(str(dst) != str(original_dst)),
        ))

    return plan


# ---------------------------------------------------------------------------
# Execute subcommand
# ---------------------------------------------------------------------------

@dataclass
class ExecuteResult:
    moved: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)
    undo_log_path: Optional[str] = None


def execute_plan(
    plan: Plan,
    source_folder: Path,
    *,
    dry_run: bool,
) -> ExecuteResult:
    result = ExecuteResult()
    if plan.errors:
        result.errors.extend(plan.errors)
        return result

    if dry_run:
        # Dry-run: don't touch anything, don't write an undo log.
        result.moved = len(plan.moves)
        return result

    # Prepare the undo log
    log = UndoLog(
        version=1,
        created=dt.datetime.now().isoformat(timespec="seconds"),
        mode=plan.mode,
        source_folder=plan.source_folder,
        target_folder=plan.target_folder,
    )

    for move in plan.moves:
        src = Path(move.source_path)
        dst = Path(move.target_path)

        try:
            check_same_device(src, dst)
        except UnsafePathError as e:
            result.errors.append(f"{move.source_path}: {e}")
            result.skipped += 1
            continue

        try:
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(src), str(dst))
        except OSError as e:
            result.errors.append(f"{move.source_path}: failed to move: {e}")
            result.skipped += 1
            continue

        log.entries.append(UndoEntry(
            source=move.source_path,
            target=move.target_path,
            timestamp=dt.datetime.now().isoformat(timespec="seconds"),
        ))
        result.moved += 1

    if log.entries:
        log_path = new_undo_log_path(source_folder, plan.mode)
        write_undo_log(log_path, log)
        result.undo_log_path = str(log_path)

    return result


# ---------------------------------------------------------------------------
# Undo subcommand
# ---------------------------------------------------------------------------

@dataclass
class UndoResult:
    restored: int = 0
    skipped: int = 0
    errors: list[str] = field(default_factory=list)


def undo_from_log(log_path: Path, *, dry_run: bool) -> UndoResult:
    result = UndoResult()
    log = read_undo_log(log_path)

    # Process in reverse so nested moves unwind correctly
    for entry in reversed(log.entries):
        moved_to = Path(entry.target)
        original = Path(entry.source)

        if not moved_to.exists():
            result.errors.append(f"missing (target already gone): {entry.target}")
            result.skipped += 1
            continue
        if original.exists():
            result.errors.append(
                f"cannot restore {entry.target} → {entry.source}: original path is occupied"
            )
            result.skipped += 1
            continue

        if dry_run:
            result.restored += 1
            continue

        try:
            original.parent.mkdir(parents=True, exist_ok=True)
            shutil.move(str(moved_to), str(original))
            result.restored += 1
        except OSError as e:
            result.errors.append(f"{entry.target}: failed to restore: {e}")
            result.skipped += 1

    return result


# ---------------------------------------------------------------------------
# Rendering
# ---------------------------------------------------------------------------

def _scan_result_to_dict(r) -> dict:
    """Convert any *ScanResult dataclass to a JSON-friendly dict."""
    d = asdict(r)
    return d


def render_scan_text(r) -> str:
    out: list[str] = []
    out.append(f"# document-organizer — scan ({r.mode})")
    out.append(f"source: {r.source_folder}")
    out.append(f"files:  {len(r.files)}")
    if hasattr(r, "categories"):
        out.append(f"categories: {', '.join(r.categories)}")
    if hasattr(r, "group_by"):
        out.append(f"group_by: {r.group_by}")
    if hasattr(r, "match"):
        out.append(f"match: {r.match}")
    if hasattr(r, "template"):
        out.append(f"template: {r.template}")
    out.append("")

    if not r.files:
        out.append("(no files to scan)")
        return "\n".join(out)

    if r.mode == "by-metadata":
        out.append("## Proposed mapping (deterministic)")
        grouped: dict[str, list[str]] = {}
        for src, sub in r.mapping.items():
            grouped.setdefault(sub, []).append(src)
        for sub in sorted(grouped):
            out.append(f"  {sub}/")
            for f in sorted(grouped[sub]):
                out.append(f"    {f}")
        return "\n".join(out)

    if r.mode == "dedup":
        out.append(f"## Duplicate groups: {len(r.groups)}")
        for i, group in enumerate(r.groups, start=1):
            out.append(f"  Group {i} ({len(group)} files):")
            for f in group:
                marker = "keep" if f == group[0] else "→ _duplicates/"
                out.append(f"    [{marker}] {f}")
        return "\n".join(out)

    # classify / rename: show each file with whatever preview/metadata is relevant
    out.append("## Files to organize")
    for f in r.files:
        size_kb = f.size / 1024
        out.append(f"  {f.rel_path}  ({size_kb:.1f} KB, mtime {f.mtime})")
        if f.content_preview:
            preview = f.content_preview.replace("\n", " ")[:120]
            out.append(f"    preview: {preview}")
    return "\n".join(out)


def render_plan_text(plan: Plan) -> str:
    out: list[str] = []
    out.append(f"# document-organizer — plan ({plan.mode})")
    out.append(f"source: {plan.source_folder}")
    out.append(f"target: {plan.target_folder}")
    out.append(f"moves:  {len(plan.moves)}")
    if plan.errors:
        out.append(f"errors: {len(plan.errors)}")
    out.append("")

    if plan.errors:
        out.append("## Errors")
        for e in plan.errors:
            out.append(f"  ✗ {e}")
        out.append("")

    if plan.moves:
        out.append("## Planned moves")
        for m in plan.moves:
            marker = "(collision)" if m.conflict_resolved else ""
            out.append(f"  {m.source_path}")
            out.append(f"    → {m.target_path}  [{m.reason}] {marker}".rstrip())
    else:
        out.append("(no moves planned)")

    return "\n".join(out)


def render_execute_text(result: ExecuteResult, *, dry_run: bool) -> str:
    out: list[str] = []
    out.append("# document-organizer — execute" + (" (dry run)" if dry_run else ""))
    out.append(f"moved:   {result.moved}")
    out.append(f"skipped: {result.skipped}")
    if result.errors:
        out.append(f"errors:  {len(result.errors)}")
        out.append("")
        out.append("## Errors")
        for e in result.errors:
            out.append(f"  ✗ {e}")
    if result.undo_log_path:
        out.append("")
        out.append(f"Undo log: {result.undo_log_path}")
        out.append(f"To reverse: python document_organizer.py undo --log {result.undo_log_path} --execute")
    return "\n".join(out)


def render_undo_text(result: UndoResult, *, dry_run: bool) -> str:
    out: list[str] = []
    out.append("# document-organizer — undo" + (" (dry run)" if dry_run else ""))
    out.append(f"restored: {result.restored}")
    out.append(f"skipped:  {result.skipped}")
    if result.errors:
        out.append(f"errors:   {len(result.errors)}")
        out.append("")
        out.append("## Errors")
        for e in result.errors:
            out.append(f"  ✗ {e}")
    return "\n".join(out)


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------

def cmd_scan(args: argparse.Namespace) -> int:
    folder = _normalize(Path(args.folder))
    try:
        check_safety(folder, force_dangerous=args.force_dangerous)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        rules = load_rules(folder)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    try:
        if args.mode == "classify":
            result = scan_classify(
                folder, rules,
                categories_override=(args.categories.split(",") if args.categories else None),
                content_preview_bytes=args.content_preview,
                include_hidden=args.include_hidden,
                max_files=args.max_files,
            )
        elif args.mode == "by-metadata":
            result = scan_by_metadata(
                folder, rules,
                group_by_override=args.group_by,
                include_hidden=args.include_hidden,
                max_files=args.max_files,
            )
        elif args.mode == "dedup":
            result = scan_dedup(
                folder, rules,
                match_override=args.match,
                include_hidden=args.include_hidden,
                max_files=args.max_files,
            )
        elif args.mode == "rename":
            result = scan_rename(
                folder, rules,
                template_override=args.template,
                content_preview_bytes=args.content_preview,
                include_hidden=args.include_hidden,
                max_files=args.max_files,
            )
        else:
            print(f"error: unknown mode: {args.mode}", file=sys.stderr)
            return 2
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps(_scan_result_to_dict(result), ensure_ascii=False, indent=2))
    else:
        print(render_scan_text(result))
    return 0


def _parse_mapping_arg(arg: str) -> dict[str, str]:
    """Parse a mapping from either a JSON file path or inline JSON."""
    p = Path(arg)
    if p.exists():
        text = p.read_text(encoding="utf-8")
    else:
        text = arg
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise UnsafePathError(f"invalid mapping JSON: {e}")
    if not isinstance(data, dict):
        raise UnsafePathError("mapping must be a JSON object")
    for k, v in data.items():
        if not isinstance(k, str) or not isinstance(v, str):
            raise UnsafePathError("mapping keys and values must be strings")
    return data


def cmd_plan(args: argparse.Namespace) -> int:
    folder = _normalize(Path(args.folder))
    try:
        check_safety(folder, force_dangerous=args.force_dangerous)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    target_folder = _normalize(Path(args.target)) if args.target else folder
    try:
        mapping = _parse_mapping_arg(args.mapping)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    plan = plan_moves(folder, target_folder, mapping, mode=args.mode)

    if args.format == "json":
        print(json.dumps(asdict(plan), ensure_ascii=False, indent=2))
    else:
        print(render_plan_text(plan))
    return 0 if not plan.errors else 1


def cmd_execute(args: argparse.Namespace) -> int:
    folder = _normalize(Path(args.folder))
    try:
        check_safety(folder, force_dangerous=args.force_dangerous)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    target_folder = _normalize(Path(args.target)) if args.target else folder
    try:
        mapping = _parse_mapping_arg(args.mapping)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    plan = plan_moves(folder, target_folder, mapping, mode=args.mode)
    result = execute_plan(plan, folder, dry_run=not args.execute)

    if args.format == "json":
        payload = asdict(result)
        payload["dry_run"] = not args.execute
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_execute_text(result, dry_run=not args.execute))
    return 0 if not result.errors else 1


def cmd_undo(args: argparse.Namespace) -> int:
    log_path = Path(args.log).expanduser().resolve()
    if not log_path.exists():
        print(f"error: undo log not found: {log_path}", file=sys.stderr)
        return 2
    try:
        result = undo_from_log(log_path, dry_run=not args.execute)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.format == "json":
        payload = asdict(result)
        payload["dry_run"] = not args.execute
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_undo_text(result, dry_run=not args.execute))
    return 0 if not result.errors else 1


def cmd_init_rules(args: argparse.Namespace) -> int:
    folder = _normalize(Path(args.folder))
    try:
        check_safety(folder, force_dangerous=args.force_dangerous)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    path = rules_path(folder)
    if path.exists() and not args.force:
        print(f"error: rules file already exists at {path}. Pass --force to overwrite.",
              file=sys.stderr)
        return 2

    rules = Rules.default()
    if args.categories:
        cats = [c.strip() for c in args.categories.split(",") if c.strip()]
        for c in cats:
            try:
                validate_category_name(c)
            except UnsafePathError as e:
                print(f"error: {e}", file=sys.stderr)
                return 2
        rules.classify["categories"] = cats
    if args.group_by:
        if args.group_by not in VALID_METADATA_GROUPS:
            print(f"error: unknown group_by: {args.group_by!r}", file=sys.stderr)
            return 2
        rules.by_metadata["group_by"] = args.group_by
    if args.dedup_match:
        if args.dedup_match not in ("hash", "name"):
            print(f"error: unknown dedup match: {args.dedup_match!r}", file=sys.stderr)
            return 2
        rules.dedup["match"] = args.dedup_match
    if args.rename_template:
        rules.rename["template"] = args.rename_template
    if args.notes:
        rules.notes = args.notes

    save_rules(folder, rules)

    if args.format == "json":
        print(json.dumps({
            "created": str(path),
            "rules": asdict(rules),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"✓ rules file written: {path}")
        print(f"  categories:  {rules.classify.get('categories')}")
        print(f"  group_by:    {rules.by_metadata.get('group_by')}")
        print(f"  dedup match: {rules.dedup.get('match')}")
        print(f"  rename tpl:  {rules.rename.get('template')}")
        if rules.notes:
            print(f"  notes:       {rules.notes}")
    return 0


def cmd_show_rules(args: argparse.Namespace) -> int:
    folder = _normalize(Path(args.folder))
    if not folder.exists() or not folder.is_dir():
        print(f"error: folder not found: {folder}", file=sys.stderr)
        return 2

    path = rules_path(folder)
    if not path.exists():
        if args.format == "json":
            print(json.dumps({
                "rules_file": str(path),
                "exists": False,
                "using_defaults": True,
                "defaults": asdict(Rules.default()),
            }, ensure_ascii=False, indent=2))
        else:
            print(f"no rules file at {path}")
            print(f"using defaults: categories={DEFAULT_CATEGORIES}, "
                  f"group_by={DEFAULT_METADATA_GROUP}")
        return 0

    try:
        rules = load_rules(folder)
    except UnsafePathError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.format == "json":
        print(json.dumps({
            "rules_file": str(path),
            "exists": True,
            "rules": asdict(rules),
        }, ensure_ascii=False, indent=2))
    else:
        print(f"rules file: {path}")
        print(f"  version:     {rules.version}")
        print(f"  created:     {rules.created}")
        print(f"  updated:     {rules.updated}")
        print(f"  categories:  {rules.classify.get('categories')}")
        print(f"  group_by:    {rules.by_metadata.get('group_by')}")
        print(f"  dedup match: {rules.dedup.get('match')}")
        print(f"  rename tpl:  {rules.rename.get('template')}")
        if rules.notes:
            print(f"  notes:       {rules.notes}")
    return 0


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="document_organizer.py",
        description="Safe, four-mode folder organizer. "
                    "Modes: classify, by-metadata, dedup, rename. "
                    "Phases: scan → plan → execute → undo.",
    )
    sub = p.add_subparsers(dest="command", required=True)

    # ---- scan ----
    p_scan = sub.add_parser("scan", help="Inspect a folder and return metadata for its files.")
    p_scan.add_argument("folder", help="Folder to scan.")
    p_scan.add_argument("--mode", default="classify",
                        choices=("classify", "by-metadata", "dedup", "rename"),
                        help="Operating mode (default: classify).")
    p_scan.add_argument("--categories", default=None,
                        help="[classify] Comma-separated category list override.")
    p_scan.add_argument("--group-by", default=None,
                        choices=tuple(VALID_METADATA_GROUPS),
                        help="[by-metadata] How to group files.")
    p_scan.add_argument("--match", default=None, choices=("hash", "name"),
                        help="[dedup] How to identify duplicates.")
    p_scan.add_argument("--template", default=None,
                        help="[rename] Rename template (agent-provided).")
    p_scan.add_argument("--content-preview", type=int, default=0,
                        help="Read the first N bytes of each text file as a preview "
                             "(default: 0 = no preview).")
    p_scan.add_argument("--max-files", type=int, default=1000,
                        help="Stop after N files (default: 1000).")
    p_scan.add_argument("--include-hidden", action="store_true",
                        help="Include dotfiles.")
    p_scan.add_argument("--force-dangerous", action="store_true",
                        help="Operate on a git repo root anyway.")
    p_scan.add_argument("--format", choices=("text", "json"), default="text")

    # ---- plan ----
    p_plan = sub.add_parser("plan", help="Validate a mapping and show planned moves as a dry-run.")
    p_plan.add_argument("folder", help="Source folder.")
    p_plan.add_argument("--mode", required=True,
                        choices=("classify", "by-metadata", "dedup", "rename"))
    p_plan.add_argument("--mapping", required=True,
                        help="JSON file path, or inline JSON string, of the mapping "
                             "{rel_path: target_subfolder_or_new_filename}.")
    p_plan.add_argument("--target", default=None,
                        help="Move destination (default: same as source).")
    p_plan.add_argument("--force-dangerous", action="store_true")
    p_plan.add_argument("--format", choices=("text", "json"), default="text")

    # ---- execute ----
    p_exec = sub.add_parser("execute", help="Perform moves. Defaults to dry-run.")
    p_exec.add_argument("folder", help="Source folder.")
    p_exec.add_argument("--mode", required=True,
                        choices=("classify", "by-metadata", "dedup", "rename"))
    p_exec.add_argument("--mapping", required=True,
                        help="JSON file path or inline JSON string.")
    p_exec.add_argument("--target", default=None)
    p_exec.add_argument("--execute", action="store_true",
                        help="Actually perform the moves. WITHOUT THIS FLAG, execute is a dry run.")
    p_exec.add_argument("--force-dangerous", action="store_true")
    p_exec.add_argument("--format", choices=("text", "json"), default="text")

    # ---- undo ----
    p_undo = sub.add_parser("undo", help="Reverse a previous execute using its undo log.")
    p_undo.add_argument("--log", required=True, help="Path to the undo log JSON.")
    p_undo.add_argument("--execute", action="store_true",
                        help="Actually perform the restore. Without this flag, undo is a dry run.")
    p_undo.add_argument("--format", choices=("text", "json"), default="text")

    # ---- init-rules ----
    p_init = sub.add_parser("init-rules", help="Write a per-folder rules file.")
    p_init.add_argument("folder", help="Folder the rules apply to.")
    p_init.add_argument("--categories", default=None,
                        help="Comma-separated list for the classify mode.")
    p_init.add_argument("--group-by", default=None, choices=tuple(VALID_METADATA_GROUPS),
                        help="Default grouping for the by-metadata mode.")
    p_init.add_argument("--dedup-match", default=None, choices=("hash", "name"),
                        help="Default matching mode for dedup.")
    p_init.add_argument("--rename-template", default=None,
                        help="Default rename template.")
    p_init.add_argument("--notes", default=None,
                        help="Optional free-text note stored in the rules file.")
    p_init.add_argument("--force", action="store_true",
                        help="Overwrite an existing rules file.")
    p_init.add_argument("--force-dangerous", action="store_true")
    p_init.add_argument("--format", choices=("text", "json"), default="text")

    # ---- show-rules ----
    p_show = sub.add_parser("show-rules", help="Print the current rules for a folder.")
    p_show.add_argument("folder", help="Folder to inspect.")
    p_show.add_argument("--format", choices=("text", "json"), default="text")

    return p


def main(argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)

    handlers = {
        "scan": cmd_scan,
        "plan": cmd_plan,
        "execute": cmd_execute,
        "undo": cmd_undo,
        "init-rules": cmd_init_rules,
        "show-rules": cmd_show_rules,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
