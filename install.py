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
import sys
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

def _local_list_skills() -> list[SkillInfo]:
    if not LOCAL_SKILLS_DIR.is_dir():
        return []
    out: list[SkillInfo] = []
    for p in sorted(LOCAL_SKILLS_DIR.iterdir()):
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

def _gh_get(url: str) -> bytes:
    req = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"{REPO_OWNER}-skills-installer",
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            return r.read()
    except urllib.error.HTTPError as e:
        if e.code == 403:
            raise SystemExit(
                "error: GitHub rate-limited this installer (HTTP 403). "
                "Wait a few minutes and retry, or clone the repo and run "
                "install.py from there."
            )
        raise SystemExit(f"error: GitHub request failed: {e} — {url}")
    except urllib.error.URLError as e:
        raise SystemExit(
            f"error: could not reach github.com ({e.reason}). "
            "Check your network / HTTPS_PROXY and retry."
        )


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


def list_skills() -> list[SkillInfo]:
    if is_local_mode():
        return _local_list_skills()
    return _remote_list_skills()


def skill_exists(name: str) -> bool:
    return any(s.name == name for s in list_skills())


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
    """Copy (local) or download (remote) the skill into `target`."""
    if dry_run:
        return
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        shutil.rmtree(target)
    if is_local_mode():
        src = LOCAL_SKILLS_DIR / skill_name
        if not src.is_dir() or not (src / "SKILL.md").exists():
            raise SystemExit(f"error: local skill not found: {src}")
        shutil.copytree(src, target)
    else:
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


def _pick_multi(title: str, skills: list[SkillInfo]) -> list[str]:
    """
    Let the user toggle a multi-select list.
    Input: space-separated numbers (e.g. '1 3'), 'a' = all, '' (enter) = confirm.
    Returns selected skill names, in the original order.
    """
    selected: set[int] = set(range(len(skills)))  # default: all selected

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
    agent_idx = _pick_numbered(
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
    scope_idx = _pick_numbered(
        "Step 2/3 — Install globally or only for the current workspace?",
        scope_options,
    )
    scope = "global" if scope_idx == 0 else "workspace"
    print()

    # Step 3: skills
    print("fetching available skills...")
    try:
        skills = list_skills()
    except SystemExit as e:
        print(f"{e}", file=sys.stderr)
        return 1
    if not skills:
        print("no skills found — nothing to install.")
        return 1
    print(f"found {len(skills)} skill(s).")
    print()

    chosen = _pick_multi(
        "Step 3/3 — Which skills do you want to install?",
        skills,
    )
    print()

    # Summary + confirmation
    target_root = resolve_target(agent_key, scope)
    print("About to install:")
    for name in chosen:
        print(f"  • {name}  →  {target_root / name}")
    print()
    confirm = _prompt("Proceed? [Y/n] ").lower()
    if confirm not in ("", "y", "yes"):
        print("aborted.")
        return 1
    print()

    # Install each skill
    failures: list[str] = []
    for name in chosen:
        dst = target_root / name
        print(f"installing {name} → {dst}")
        try:
            install_skill(name, dst, dry_run=False)
        except (OSError, SystemExit) as e:
            print(f"  ✗ failed: {e}", file=sys.stderr)
            failures.append(name)
            continue
        print("  ✓ done")

    # Post-install hints (once, based on the agent/scope the user picked)
    if chosen and not failures:
        print()
        _print_post_install_hint(agent_key, scope, target_root / chosen[0], chosen[0])

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

    args = build_parser().parse_args(argv)

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
