#!/usr/bin/env python3
"""
install.py — cross-platform, zero-dependency Skills installer.

Two ways to run it:

  1. Interactive wizard (easiest):
         python install.py
     Walks you through: pick agent → global or workspace → pick skills.

  2. One-shot CLI (for scripts / CI):
         python install.py list
         python install.py install <skill> --agent claude --scope global
         python install.py uninstall <skill> --agent claude --scope workspace
         python install.py where --agent claude --scope global

Two ways to *source* skills:

  * **Local mode** — if this file lives next to a `skills/` folder
    (the cloned repo), it installs from that folder.
  * **Remote mode** — if `skills/` isn't next to it, it transparently
    downloads the requested skill from github.com/bwinken/skills via
    the public GitHub Contents API. That means you can drop this
    single file into any folder and just run `python install.py`.

Zero dependencies: pure Python 3.8+ standard library. Works on
Windows, Linux, and macOS.
"""
from __future__ import annotations

import argparse
import json
import os
import platform
import shutil
import ssl
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Optional


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

REPO_OWNER = "bwinken"
REPO_NAME = "skills"
REPO_BRANCH = "main"
GITHUB_API = "https://api.github.com"

HERE = Path(__file__).resolve().parent
LOCAL_SKILLS_DIR = HERE / "skills"


def is_local_mode() -> bool:
    """True if this script lives next to a populated skills/ folder."""
    return LOCAL_SKILLS_DIR.is_dir() and any(LOCAL_SKILLS_DIR.iterdir())


# ---------------------------------------------------------------------------
# Agent registry
# ---------------------------------------------------------------------------

def _home() -> Path:
    return Path(os.path.expanduser("~"))


def _cwd() -> Path:
    return Path.cwd()


@dataclass(frozen=True)
class Agent:
    key: str
    label: str
    # Base dir where skill folders live, per scope.
    global_dir: Callable[[], Path]
    workspace_dir: Callable[[], Path]
    # Short description of the agent, shown in the wizard.
    note: str


AGENTS: dict[str, Agent] = {
    "claude": Agent(
        key="claude",
        label="Claude Code",
        global_dir=lambda: _home() / ".claude" / "skills",
        workspace_dir=lambda: _cwd() / ".claude" / "skills",
        note="auto-discovers skills from ~/.claude/skills/ and <project>/.claude/skills/",
    ),
    "roo": Agent(
        key="roo",
        label="Roo Code",
        global_dir=lambda: _home() / ".roo" / "skills",
        workspace_dir=lambda: _cwd() / ".roo" / "skills",
        note="auto-discovers skills from ~/.roo/skills/ and <project>/.roo/skills/",
    ),
    "cline": Agent(
        key="cline",
        label="Cline",
        global_dir=lambda: _home() / ".cline" / "skills",
        workspace_dir=lambda: _cwd() / ".cline" / "skills",
        note="auto-discovers skills from ~/.cline/skills/ and <project>/.cline/skills/",
    ),
}


def resolve_target(agent_key: str, scope: str) -> Path:
    agent = AGENTS.get(agent_key)
    if agent is None:
        raise SystemExit(
            f"error: unknown agent '{agent_key}'. "
            f"Choose one of: {', '.join(AGENTS)}"
        )
    if scope == "global":
        return agent.global_dir()
    if scope == "workspace":
        return agent.workspace_dir()
    raise SystemExit(f"error: unknown scope '{scope}' (use global or workspace).")


# ---------------------------------------------------------------------------
# Platform helper
# ---------------------------------------------------------------------------

def platform_label() -> str:
    sysname = platform.system()
    if sysname == "Darwin":
        return "macOS"
    return sysname or "Unknown"


# ---------------------------------------------------------------------------
# Skill source: local or remote
# ---------------------------------------------------------------------------

@dataclass
class SkillInfo:
    name: str
    description: str


# --- local source ----------------------------------------------------------

def _local_list_skills(root: Optional[Path] = None) -> list[SkillInfo]:
    root = root if root is not None else LOCAL_SKILLS_DIR
    if not root.is_dir():
        return []
    out: list[SkillInfo] = []
    for p in sorted(root.iterdir()):
        if not p.is_dir() or p.name.startswith("_"):
            continue
        if not (p / "SKILL.md").exists():
            continue
        out.append(SkillInfo(name=p.name, description=_parse_description(p / "SKILL.md")))
    return out


def _parse_description(skill_md: Path) -> str:
    try:
        text = skill_md.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return ""
    return _extract_description(text)


def _extract_description(text: str) -> str:
    """Return the `description:` value from a SKILL.md YAML frontmatter."""
    if not text.startswith("---"):
        return ""
    end = text.find("\n---", 3)
    if end == -1:
        return ""
    frontmatter = text[3:end]
    for line in frontmatter.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        if key.strip() == "description":
            return value.strip().strip('"').strip("'")
    return ""


# --- remote source (GitHub Contents API) -----------------------------------

# Retry transient failures (5xx, 408, 429, network errors) with exponential
# backoff: 2s, 4s, 8s, 16s — matching the install.py network-retry policy.
_RETRY_DELAYS = (2, 4, 8, 16)
_RETRYABLE_STATUSES = frozenset({408, 429, 500, 502, 503, 504})

# --insecure / SKILLS_INSTALLER_INSECURE=1 disables TLS verification for
# corporate environments that intercept HTTPS with a self-signed CA. It's the
# moral equivalent of pip's `--trusted-host` flag. Off by default.
_INSECURE_TLS: bool = os.environ.get("SKILLS_INSTALLER_INSECURE", "") not in ("", "0")


def _ssl_context() -> Optional[ssl.SSLContext]:
    if not _INSECURE_TLS:
        return None
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx


def _gh_get(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{REPO_OWNER}-skills-installer",
        },
    )
    attempts = len(_RETRY_DELAYS) + 1
    ctx = _ssl_context()
    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(req, timeout=30, context=ctx) as r:
                return r.read()
        except urllib.error.HTTPError as e:
            if e.code == 403:
                raise SystemExit(
                    "error: GitHub rate-limited this installer (HTTP 403). "
                    "Wait a few minutes and retry, or clone the repo and run "
                    "install.py from there."
                )
            if e.code in _RETRYABLE_STATUSES and attempt < attempts:
                delay = _RETRY_DELAYS[attempt - 1]
                print(
                    f"  github returned HTTP {e.code}; retrying in {delay}s "
                    f"(attempt {attempt}/{attempts - 1})...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            if e.code in _RETRYABLE_STATUSES:
                raise SystemExit(
                    f"error: GitHub request failed after {attempts} attempts "
                    f"(HTTP {e.code} {e.reason}) — {url}. "
                    "GitHub may be experiencing an outage; try again later, "
                    "or clone the repo and run install.py from there."
                )
            raise SystemExit(f"error: GitHub request failed: {e} — {url}")
        except urllib.error.URLError as e:
            if attempt < attempts:
                delay = _RETRY_DELAYS[attempt - 1]
                print(
                    f"  network error ({e.reason}); retrying in {delay}s "
                    f"(attempt {attempt}/{attempts - 1})...",
                    file=sys.stderr,
                )
                time.sleep(delay)
                continue
            raise SystemExit(
                f"error: could not reach github.com ({e.reason}) after "
                f"{attempts} attempts. Check your network / HTTPS_PROXY "
                "and retry."
            )
    # Unreachable: loop always returns or raises.
    raise SystemExit("error: unreachable in _gh_get retry loop")


def _gh_list_dir(path: str) -> list[dict]:
    """GET /repos/{owner}/{repo}/contents/{path}?ref={branch}."""
    url = (
        f"{GITHUB_API}/repos/{REPO_OWNER}/{REPO_NAME}/contents/{path}"
        f"?ref={REPO_BRANCH}"
    )
    raw = _gh_get(url)
    data = json.loads(raw.decode("utf-8"))
    if isinstance(data, dict):
        # A single-file response (shouldn't happen for a directory).
        return [data]
    return data


def _gh_get_text(download_url: str) -> str:
    return _gh_get(download_url).decode("utf-8", errors="replace")


def _remote_list_skills() -> list[SkillInfo]:
    try:
        entries = _gh_list_dir("skills")
    except SystemExit:
        raise
    out: list[SkillInfo] = []
    for e in entries:
        if e.get("type") != "dir":
            continue
        name = e["name"]
        if name.startswith("_"):
            continue
        skill_md_url = (
            f"https://raw.githubusercontent.com/"
            f"{REPO_OWNER}/{REPO_NAME}/{REPO_BRANCH}/skills/{name}/SKILL.md"
        )
        try:
            text = _gh_get_text(skill_md_url)
        except SystemExit:
            continue
        out.append(SkillInfo(name=name, description=_extract_description(text)))
    return sorted(out, key=lambda s: s.name)


# --- tarball source (codeload.github.com) ----------------------------------
#
# The per-file GitHub Contents API is rate-limited and flaky: a single
# 503 on /repos/.../contents breaks the wizard mid-step. codeload.github.com
# serves the full repo as a tarball in one request and runs on separate
# infrastructure — so we prefer it, and fall back to the Contents API only
# if the tarball download fails.

_REMOTE_TARBALL_CACHE: Optional[Path] = None
_REMOTE_TARBALL_ATTEMPTED = False


def _ensure_tarball() -> Optional[Path]:
    """Download + extract the repo tarball once. Returns the skills/ dir or None."""
    global _REMOTE_TARBALL_CACHE, _REMOTE_TARBALL_ATTEMPTED
    if _REMOTE_TARBALL_ATTEMPTED:
        return _REMOTE_TARBALL_CACHE
    _REMOTE_TARBALL_ATTEMPTED = True
    _REMOTE_TARBALL_CACHE = _try_fetch_tarball()
    return _REMOTE_TARBALL_CACHE


def _try_fetch_tarball() -> Optional[Path]:
    import io
    import tarfile
    import tempfile

    url = (
        f"https://codeload.github.com/{REPO_OWNER}/{REPO_NAME}"
        f"/tar.gz/refs/heads/{REPO_BRANCH}"
    )
    print(
        f"  downloading repo tarball from codeload.github.com "
        f"({REPO_BRANCH})...",
        file=sys.stderr,
    )
    try:
        data = _gh_get(url)
    except SystemExit as e:
        print(f"  tarball download failed: {e}", file=sys.stderr)
        return None

    tmpdir = Path(tempfile.mkdtemp(prefix="skills-installer-"))
    try:
        with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
            safe: list = []
            for m in tf.getmembers():
                # Reject absolute paths and parent-traversal entries.
                if m.name.startswith("/") or ".." in Path(m.name).parts:
                    print(
                        f"  unsafe tarball entry rejected: {m.name}",
                        file=sys.stderr,
                    )
                    return None
                # Skip symlinks, hardlinks, devices; keep regular files + dirs.
                if not (m.isfile() or m.isdir()):
                    continue
                safe.append(m)
            tf.extractall(tmpdir, members=safe)
    except (OSError, tarfile.TarError) as e:
        print(f"  tarball extraction failed: {e}", file=sys.stderr)
        return None

    # Tarball top-level is "<repo>-<branch>/"; find it and return its skills/.
    for child in tmpdir.iterdir():
        if child.is_dir():
            skills_dir = child / "skills"
            if skills_dir.is_dir():
                return skills_dir
    print(
        "  tarball did not contain a skills/ directory",
        file=sys.stderr,
    )
    return None


def list_skills() -> list[SkillInfo]:
    if is_local_mode():
        return _local_list_skills()
    tarball_dir = _ensure_tarball()
    if tarball_dir is not None:
        return _local_list_skills(tarball_dir)
    return _remote_list_skills()


def skill_exists(name: str) -> bool:
    return any(s.name == name for s in list_skills())


def _scan_installed(target_root: Path) -> set[str]:
    """Return names of skills currently installed under `target_root`.

    A directory counts as an installed skill if it contains SKILL.md and
    its name doesn't start with '_' (matching the same rules as the
    local/tarball listers).
    """
    if not target_root.is_dir():
        return set()
    out: set[str] = set()
    for p in target_root.iterdir():
        if not p.is_dir() or p.name.startswith("_"):
            continue
        if (p / "SKILL.md").exists():
            out.add(p.name)
    return out


# ---------------------------------------------------------------------------
# Install / uninstall
# ---------------------------------------------------------------------------

def _copytree_overwrite(src: Path, dst: Path) -> None:
    if dst.exists():
        shutil.rmtree(dst)
    shutil.copytree(src, dst)


def _remote_download_tree(repo_path: str, dst: Path) -> None:
    """Recursively download a directory from the GitHub repo to `dst`."""
    dst.mkdir(parents=True, exist_ok=True)
    entries = _gh_list_dir(repo_path)
    for e in entries:
        name = e["name"]
        etype = e.get("type")
        if etype == "dir":
            _remote_download_tree(f"{repo_path}/{name}", dst / name)
        elif etype == "file":
            download_url = e.get("download_url")
            if not download_url:
                continue
            data = _gh_get(download_url)
            (dst / name).write_bytes(data)
            print(f"    ↓ {name}")


def install_skill(skill_name: str, target: Path, *, dry_run: bool) -> None:
    """Copy (local / tarball) or download (Contents API) the skill into `target`."""
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)

    # Source 1: cloned repo next to install.py
    if is_local_mode():
        src = LOCAL_SKILLS_DIR / skill_name
        if not src.is_dir() or not (src / "SKILL.md").exists():
            raise SystemExit(f"error: local skill not found: {src}")
        shutil.copytree(src, target)
        return

    # Source 2: tarball fetched once from codeload.github.com
    tarball_dir = _ensure_tarball()
    if tarball_dir is not None:
        src = tarball_dir / skill_name
        if not src.is_dir() or not (src / "SKILL.md").exists():
            raise SystemExit(
                f"error: skill not found in tarball: {skill_name}"
            )
        shutil.copytree(src, target)
        return

    # Source 3: fall back to the GitHub Contents API (per-file downloads)
    print(f"  fetching from github.com/{REPO_OWNER}/{REPO_NAME}...")
    _remote_download_tree(f"skills/{skill_name}", target)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_list(_args: argparse.Namespace) -> int:
    mode = "local" if is_local_mode() else "remote"
    source = (
        f"local ({LOCAL_SKILLS_DIR})"
        if mode == "local"
        else f"remote (github.com/{REPO_OWNER}/{REPO_NAME})"
    )
    print(f"source: {source}")
    print()
    skills = list_skills()
    if not skills:
        print("(no skills found)")
        return 0
    print(f"Skills — {len(skills)} skill(s) available:")
    print()
    for s in skills:
        desc = s.description
        if len(desc) > 80:
            desc = desc[:77] + "..."
        print(f"  {s.name:<20}  {desc}")
    print()
    print("Run:  python install.py                       (interactive wizard)")
    print("      python install.py install <skill> --agent <agent>")
    print("      python install.py install <skill> --agent <agent> --scope workspace")
    print()
    print("Claude Code users can also install via the plugin marketplace:")
    print(f"  /plugin marketplace add {REPO_OWNER}/{REPO_NAME}")
    print("  /plugin install <skill>@skills")
    return 0


def cmd_where(args: argparse.Namespace) -> int:
    target = resolve_target(args.agent, args.scope)
    print(f"platform: {platform_label()}")
    print(f"agent:    {args.agent}")
    print(f"scope:    {args.scope}")
    print(f"target:   {target}")
    print(f"exists:   {target.exists()}")
    return 0


def cmd_install(args: argparse.Namespace) -> int:
    skill_name = args.skill
    if not skill_exists(skill_name):
        print(f"error: skill not found: {skill_name}", file=sys.stderr)
        print("       run 'python install.py list' to see available skills.",
              file=sys.stderr)
        return 2

    target_root = resolve_target(args.agent, args.scope)
    dst = target_root / skill_name

    print(f"platform: {platform_label()}")
    print(f"agent:    {args.agent}")
    print(f"scope:    {args.scope}")
    print(f"target:   {dst}")
    print(f"source:   {'local' if is_local_mode() else 'remote (github)'}")

    if args.dry_run:
        print("(dry run — no files copied)")
        _print_post_install_hint(args.agent, args.scope, dst, skill_name)
        return 0

    try:
        install_skill(skill_name, dst, dry_run=False)
    except OSError as e:
        print(f"error: failed to install: {e}", file=sys.stderr)
        return 1

    print("installed.")
    _print_post_install_hint(args.agent, args.scope, dst, skill_name)
    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    target_root = resolve_target(args.agent, args.scope)
    dst = target_root / args.skill
    if not dst.exists():
        print(f"not installed at {dst} — nothing to do.")
        return 0
    if args.dry_run:
        print(f"(dry run) would remove: {dst}")
        return 0
    try:
        shutil.rmtree(dst)
    except OSError as e:
        print(f"error: failed to remove: {e}", file=sys.stderr)
        return 1
    print(f"removed: {dst}")
    return 0


# ---------------------------------------------------------------------------
# Interactive wizard
# ---------------------------------------------------------------------------

def _prompt(msg: str) -> str:
    try:
        return input(msg).strip()
    except (EOFError, KeyboardInterrupt):
        print()
        raise SystemExit(130)


def _pick_numbered(title: str, options: list[tuple[str, str]]) -> int:
    """
    Ask the user to pick one option by number.
    `options` is a list of (label, hint) tuples. Returns the zero-based index.
    """
    print(title)
    for i, (label, hint) in enumerate(options, start=1):
        if hint:
            print(f"  {i}) {label}")
            print(f"     {hint}")
        else:
            print(f"  {i}) {label}")
    while True:
        raw = _prompt("> ")
        if not raw.isdigit():
            print("please enter a number from the list.")
            continue
        idx = int(raw)
        if 1 <= idx <= len(options):
            return idx - 1
        print(f"please enter a number between 1 and {len(options)}.")


def _pick_multi(
    title: str,
    skills: list[SkillInfo],
    *,
    initial_selected: Optional[set[int]] = None,
) -> list[str]:
    """
    Let the user toggle a multi-select list.
    Input: space-separated numbers (e.g. '1 3'), 'a' = all, '' (enter) = confirm.
    Returns selected skill names, in the original order.
    """
    if initial_selected is None:
        selected: set[int] = set(range(len(skills)))  # default: all selected
    else:
        selected = set(initial_selected)

    while True:
        print(title)
        for i, s in enumerate(skills, start=1):
            mark = "x" if (i - 1) in selected else " "
            desc = s.description
            if len(desc) > 65:
                desc = desc[:62] + "..."
            print(f"  [{mark}] {i}) {s.name} — {desc}")
        print("     (numbers = toggle  /  a = all  /  n = none  /  enter = confirm)")
        raw = _prompt("> ")
        if raw == "":
            if not selected:
                print("please select at least one skill.")
                continue
            return [skills[i].name for i in sorted(selected)]
        if raw.lower() == "a":
            selected = set(range(len(skills)))
            continue
        if raw.lower() == "n":
            selected = set()
            continue
        ok = True
        toggled: set[int] = set()
        for tok in raw.split():
            if not tok.isdigit():
                ok = False
                break
            idx = int(tok)
            if not (1 <= idx <= len(skills)):
                ok = False
                break
            toggled.add(idx - 1)
        if not ok:
            print("invalid input. enter numbers separated by spaces, or a / n / enter.")
            continue
        for t in toggled:
            if t in selected:
                selected.remove(t)
            else:
                selected.add(t)


# ---------------------------------------------------------------------------
# TUI primitives: arrow-key menus, zero dependencies
# ---------------------------------------------------------------------------
#
# Cross-platform raw key reading using only the stdlib:
#   - Windows:   msvcrt.getwch()           (stdlib, always available on Windows)
#   - Unix/mac:  termios + tty.setraw()    (stdlib, always available on POSIX)
#
# If we can't get a real TTY (piped stdin, CI, etc.), we transparently fall
# back to the legacy number-picker so every non-interactive workflow still
# works exactly as before.

def _is_tty() -> bool:
    try:
        return bool(sys.stdin.isatty() and sys.stdout.isatty())
    except (AttributeError, ValueError):
        return False


def _enable_vt_windows() -> bool:
    """Turn on ANSI escape processing in the Windows console. No-op elsewhere."""
    if os.name != "nt":
        return True
    try:
        import ctypes
        kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined]
        handle = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
        mode = ctypes.c_uint32()
        if not kernel32.GetConsoleMode(handle, ctypes.byref(mode)):
            return False
        ENABLE_VIRTUAL_TERMINAL_PROCESSING = 0x0004
        return bool(kernel32.SetConsoleMode(
            handle, mode.value | ENABLE_VIRTUAL_TERMINAL_PROCESSING
        ))
    except Exception:
        return False


def _supports_arrow_menus() -> bool:
    if not _is_tty():
        return False
    if os.name == "nt":
        return _enable_vt_windows()
    return True


def _read_key() -> str:
    """Read one keypress and return a normalized name.

    Returns one of: 'up', 'down', 'left', 'right', 'enter', 'space',
    'esc', 'home', 'end', 'pageup', 'pagedown', a lowercase character,
    or 'other' for anything we don't recognize.
    """
    if os.name == "nt":
        import msvcrt
        ch = msvcrt.getwch()
        if ch in ("\x00", "\xe0"):
            ch2 = msvcrt.getwch()
            return {
                "H": "up", "P": "down", "K": "left", "M": "right",
                "G": "home", "O": "end", "I": "pageup", "Q": "pagedown",
            }.get(ch2, "other")
        if ch == "\r":
            return "enter"
        if ch == "\x1b":
            return "esc"
        if ch == " ":
            return "space"
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch.lower()

    import select
    import termios
    import tty
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    try:
        tty.setraw(fd)
        ch = sys.stdin.read(1)
        if ch == "\x1b":
            # Could be a bare ESC or the start of a CSI sequence (arrow keys).
            if select.select([sys.stdin], [], [], 0.01)[0]:
                ch2 = sys.stdin.read(1)
                if ch2 == "[":
                    ch3 = sys.stdin.read(1)
                    return {
                        "A": "up", "B": "down",
                        "C": "right", "D": "left",
                        "H": "home", "F": "end",
                    }.get(ch3, "other")
            return "esc"
        if ch in ("\r", "\n"):
            return "enter"
        if ch == " ":
            return "space"
        if ch == "\x03":
            raise KeyboardInterrupt
        return ch.lower()
    finally:
        termios.tcsetattr(fd, termios.TCSADRAIN, old)


# ANSI escape helpers. `_CLR_DOWN` erases from the cursor to the end of
# the screen; combined with cursor-up it lets us re-render the same menu
# in place without flicker.
_CSI = "\x1b["
_REVERSE = _CSI + "7m"
_DIM = _CSI + "2m"
_RESET = _CSI + "0m"


def _truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    if width <= 3:
        return s[:width]
    return s[: width - 3] + "..."


def _render_single(
    title: str,
    options: list[tuple[str, str]],
    cursor: int,
) -> int:
    """Render a single-select menu. Returns the number of lines printed."""
    lines = 0
    print(title)
    lines += 1
    for i, (label, hint) in enumerate(options):
        pointer = "›" if i == cursor else " "
        row = f" {pointer} {label}"
        if i == cursor:
            print(f"{_REVERSE}{row}{_RESET}")
        else:
            print(row)
        lines += 1
        if hint:
            print(f"     {_DIM}{_truncate(hint, 100)}{_RESET}")
            lines += 1
    print(f"  {_DIM}(↑/↓ move · enter = confirm · q = cancel){_RESET}")
    lines += 1
    sys.stdout.flush()
    return lines


def _menu_single(title: str, options: list[tuple[str, str]]) -> int:
    if not _supports_arrow_menus():
        return _pick_numbered(title, options)
    cursor = 0
    lines = _render_single(title, options, cursor)
    try:
        while True:
            key = _read_key()
            if key == "up":
                cursor = (cursor - 1) % len(options)
            elif key == "down":
                cursor = (cursor + 1) % len(options)
            elif key in ("home", "pageup"):
                cursor = 0
            elif key in ("end", "pagedown"):
                cursor = len(options) - 1
            elif key == "enter":
                return cursor
            elif key in ("q", "esc"):
                print()
                raise SystemExit(130)
            else:
                continue
            sys.stdout.write(f"{_CSI}{lines}A{_CSI}J")
            sys.stdout.flush()
            lines = _render_single(title, options, cursor)
    except KeyboardInterrupt:
        print()
        raise SystemExit(130)


def _render_multi(
    title: str,
    items: list[SkillInfo],
    cursor: int,
    selected: set[int],
) -> int:
    lines = 0
    print(title)
    lines += 1
    for i, s in enumerate(items):
        mark = "x" if i in selected else " "
        pointer = "›" if i == cursor else " "
        desc = _truncate(s.description, 55)
        head = f" {pointer} [{mark}] {s.name}"
        row = f"{head}  {_DIM}— {desc}{_RESET}" if desc else head
        if i == cursor:
            # Reverse video only on the non-dim part so highlight is readable.
            print(f"{_REVERSE}{head}{_RESET}  {_DIM}— {desc}{_RESET}"
                  if desc else f"{_REVERSE}{head}{_RESET}")
        else:
            print(row)
        lines += 1
    print(
        f"  {_DIM}(↑/↓ move · space = toggle · a = all · n = none · "
        f"enter = confirm · q = cancel){_RESET}"
    )
    lines += 1
    sys.stdout.flush()
    return lines


def _menu_multi(
    title: str,
    items: list[SkillInfo],
    *,
    initial_selected: Optional[set[int]] = None,
) -> list[str]:
    if not _supports_arrow_menus():
        return _pick_multi(title, items, initial_selected=initial_selected)
    cursor = 0
    if initial_selected is None:
        selected: set[int] = set(range(len(items)))  # default: all selected
    else:
        selected = set(initial_selected)
    lines = _render_multi(title, items, cursor, selected)
    try:
        while True:
            key = _read_key()
            if key == "up":
                cursor = (cursor - 1) % len(items)
            elif key == "down":
                cursor = (cursor + 1) % len(items)
            elif key in ("home", "pageup"):
                cursor = 0
            elif key in ("end", "pagedown"):
                cursor = len(items) - 1
            elif key == "space":
                if cursor in selected:
                    selected.remove(cursor)
                else:
                    selected.add(cursor)
            elif key == "a":
                selected = set(range(len(items)))
            elif key == "n":
                selected = set()
            elif key == "enter":
                if not selected:
                    # Empty selection: audible beep, keep going.
                    sys.stdout.write("\a")
                    sys.stdout.flush()
                    continue
                return [items[i].name for i in sorted(selected)]
            elif key in ("q", "esc"):
                print()
                raise SystemExit(130)
            else:
                continue
            sys.stdout.write(f"{_CSI}{lines}A{_CSI}J")
            sys.stdout.flush()
            lines = _render_multi(title, items, cursor, selected)
    except KeyboardInterrupt:
        print()
        raise SystemExit(130)


def cmd_wizard(_args: Optional[argparse.Namespace] = None) -> int:
    print()
    print(f"skills installer — github.com/{REPO_OWNER}/{REPO_NAME}")
    print("=" * 60)
    source = "local repo" if is_local_mode() else f"remote (github.com/{REPO_OWNER}/{REPO_NAME})"
    print(f"source: {source}")
    print(f"platform: {platform_label()}")
    print()

    # Step 1: agent
    agent_order = ["claude", "roo", "cline"]
    agent_idx = _menu_single(
        "Step 1/3 — Which coding agent are you using?",
        [(AGENTS[k].label, AGENTS[k].note) for k in agent_order],
    )
    agent_key = agent_order[agent_idx]
    agent = AGENTS[agent_key]
    print()

    # Step 2: scope
    scope_options = [
        ("Global  (user-wide, every project)", f"{agent.global_dir()}"),
        ("Workspace  (this folder only)", f"{agent.workspace_dir()}"),
    ]
    scope_idx = _menu_single(
        "Step 2/3 — Install globally or only for the current workspace?",
        scope_options,
    )
    scope = "global" if scope_idx == 0 else "workspace"
    print()

    # Step 3: list available skills, detect what's already installed, and
    # let the user toggle in one unified multi-select.
    #
    # The selection drives three kinds of actions on confirm:
    #   - checked & not installed           -> install
    #   - checked & already installed       -> update (reinstall from source)
    #   - unchecked & was installed         -> uninstall
    target_root = resolve_target(agent_key, scope)
    installed = _scan_installed(target_root)

    print("fetching available skills...")
    try:
        available = list_skills()
    except SystemExit as e:
        print(f"{e}", file=sys.stderr)
        # Even if the fetch fails, we may still have installed skills to
        # manage (uninstall). Only give up if nothing's around.
        if not installed:
            return 1
        available = []

    avail_map: dict[str, SkillInfo] = {s.name: s for s in available}
    all_names = sorted(set(avail_map.keys()) | installed)
    if not all_names:
        print("no skills available and none installed — nothing to do.")
        return 0

    # Build menu entries: each row gets a status badge so the user can see
    # what's installed, what's new, and what's an orphan (installed but the
    # upstream source is gone).
    entries: list[SkillInfo] = []
    initial_selected: set[int] = set()
    for i, name in enumerate(all_names):
        info = avail_map.get(name)
        desc = info.description if info else ""
        if name in installed and info is not None:
            badge = "[installed]"
            initial_selected.add(i)
        elif name in installed:
            badge = "[installed · no source]"
            initial_selected.add(i)
        else:
            badge = "[new]"
        label_desc = f"{badge} {desc}".strip()
        entries.append(SkillInfo(name=name, description=label_desc))

    print(
        f"found {len(avail_map)} available skill(s), "
        f"{len(installed)} already installed at {target_root}"
    )
    print()

    chosen = _menu_multi(
        "Step 3/3 — Toggle skills to install / update / remove:",
        entries,
        initial_selected=initial_selected,
    )
    chosen_set = set(chosen)
    print()

    # Classify the diff.
    to_install = sorted(chosen_set - installed)
    to_uninstall = sorted(installed - chosen_set)
    kept = chosen_set & installed
    to_update = sorted(n for n in kept if n in avail_map)
    kept_orphans = sorted(n for n in kept if n not in avail_map)

    if not (to_install or to_update or to_uninstall):
        print("no changes requested — nothing to do.")
        return 0

    # Summary + confirmation
    print("About to apply:")
    if to_install:
        print(f"  + install   ({len(to_install)}):")
        for n in to_install:
            print(f"      {n}  →  {target_root / n}")
    if to_update:
        print(f"  ↻ update    ({len(to_update)}):")
        for n in to_update:
            print(f"      {n}  →  {target_root / n}")
    if to_uninstall:
        print(f"  - uninstall ({len(to_uninstall)}):")
        for n in to_uninstall:
            print(f"      {n}  →  {target_root / n}")
    if kept_orphans:
        print(f"  = keep as-is (no upstream source) ({len(kept_orphans)}):")
        for n in kept_orphans:
            print(f"      {n}")
    print()
    confirm = _prompt("Proceed? [Y/n] ").lower()
    if confirm not in ("", "y", "yes"):
        print("aborted.")
        return 1
    print()

    # Execute: remove first (frees any locked paths), then install+update.
    failures: list[str] = []

    for name in to_uninstall:
        dst = target_root / name
        print(f"uninstalling {name} → {dst}")
        try:
            if dst.exists():
                shutil.rmtree(dst)
            print("  ✓ removed")
        except OSError as e:
            print(f"  ✗ failed: {e}", file=sys.stderr)
            failures.append(name)

    # install_skill overwrites existing dirs, so update = reinstall.
    for name in sorted(to_install + to_update):
        dst = target_root / name
        action = "updating" if name in installed else "installing"
        print(f"{action} {name} → {dst}")
        try:
            install_skill(name, dst, dry_run=False)
            print("  ✓ done")
        except (OSError, SystemExit) as e:
            print(f"  ✗ failed: {e}", file=sys.stderr)
            failures.append(name)

    # Post-install hint (pick any installed/updated skill as the sample)
    sample_name = next(iter(to_install + to_update), None)
    if sample_name is not None and sample_name not in failures:
        print()
        _print_post_install_hint(
            agent_key, scope, target_root / sample_name, sample_name
        )

    if failures:
        print()
        print(f"completed with errors: {', '.join(failures)}", file=sys.stderr)
        return 1
    return 0


# ---------------------------------------------------------------------------
# Post-install guidance
# ---------------------------------------------------------------------------

def _print_post_install_hint(
    agent_key: str,
    scope: str,
    dst: Path,
    skill_name: str,
) -> None:
    agent = AGENTS[agent_key]
    print()
    print("--- next steps ---")
    if scope == "global":
        print(f"{agent.label} will auto-discover this skill on its next launch.")
    else:
        print(f"{agent.label} will auto-discover this skill when you open this folder.")
    print(f"location: {dst}")
    print(f"SKILL.md (full docs): {dst / 'SKILL.md'}")


# ---------------------------------------------------------------------------
# Argparse
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    agent_choices = sorted(AGENTS)
    scope_choices = ("global", "workspace")

    p = argparse.ArgumentParser(
        prog="install.py",
        description="Skills cross-platform installer (zero dependencies). "
                    "Run with no arguments for the interactive wizard.",
    )
    # Top-level flag so it works in wizard mode AND with every subcommand.
    p.add_argument(
        "--insecure",
        action="store_true",
        help="Skip TLS certificate verification (for corporate proxies "
             "with TLS interception). Equivalent to pip's --trusted-host. "
             "You can also set SKILLS_INSTALLER_INSECURE=1.",
    )
    sub = p.add_subparsers(dest="command")

    sub.add_parser("list", help="List skills available in this repo / remote.")

    p_install = sub.add_parser("install", help="Install a skill for an agent.")
    p_install.add_argument("skill", help="Skill name (e.g. 'deep-grep').")
    p_install.add_argument("--agent", default="claude", choices=agent_choices,
                           help="Target agent (default: claude).")
    p_install.add_argument("--scope", default="global", choices=scope_choices,
                           help="'global' (user-wide) or 'workspace' (cwd). "
                                "Default: global.")
    p_install.add_argument("--dry-run", action="store_true",
                           help="Show what would happen without writing files.")

    p_uninstall = sub.add_parser("uninstall", help="Uninstall a skill.")
    p_uninstall.add_argument("skill")
    p_uninstall.add_argument("--agent", default="claude", choices=agent_choices)
    p_uninstall.add_argument("--scope", default="global", choices=scope_choices)
    p_uninstall.add_argument("--dry-run", action="store_true")

    p_where = sub.add_parser("where", help="Print the install target for an agent.")
    p_where.add_argument("--agent", default="claude", choices=agent_choices)
    p_where.add_argument("--scope", default="global", choices=scope_choices)

    return p


def main(argv: Optional[list[str]] = None) -> int:
    # Force UTF-8 so unicode (→, ↓, ✓, 中文 etc.) survives Windows consoles.
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    # Enable ANSI escape processing on Windows so the arrow-key menus can
    # repaint with cursor-up / clear-to-end. No-op on macOS/Linux.
    _enable_vt_windows()

    args = build_parser().parse_args(argv)

    # Apply --insecure (or SKILLS_INSTALLER_INSECURE=1) globally so every
    # HTTPS call — tarball, Contents API, raw files — uses the same context.
    global _INSECURE_TLS
    if args.insecure:
        _INSECURE_TLS = True
    if _INSECURE_TLS:
        print(
            "warning: TLS verification disabled (--insecure). "
            "Only use on trusted corporate networks.",
            file=sys.stderr,
        )

    proxy = os.environ.get("HTTPS_PROXY") or os.environ.get("HTTP_PROXY")
    if proxy:
        print(f"using proxy: {proxy}", file=sys.stderr)

    if args.command is None:
        return cmd_wizard(args)

    handlers = {
        "list":      cmd_list,
        "install":   cmd_install,
        "uninstall": cmd_uninstall,
        "where":     cmd_where,
    }
    return handlers[args.command](args)


if __name__ == "__main__":
    sys.exit(main())
