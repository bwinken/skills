"""
_preflight.py — zero-dependency package checker & install guide.

Drop this file into your skill's `scripts/` folder so the skill folder
stays fully self-contained. Then, inside your entry script, call
`require(...)` **only when you actually need the optional package** —
never at import time. That way a skill that can do most of its work
with the standard library keeps working even if the optional packages
are missing.

Design rules:
  * Pure Python standard library (works on Python 3.8+).
  * Never raises on missing packages. Instead it prints a structured,
    bilingual (English / 中文) install guide to stderr and exits with
    a well-defined code (default: 2). AI agents reading the output can
    parse the guide and help the user fix it.
  * Honors HTTPS_PROXY / HTTP_PROXY environment variables — essential
    for users behind corporate firewalls.
  * Cross-platform: detects Windows / Linux / macOS and prints the
    right shell syntax for setting the proxy env var.

Usage inside a skill:

    from _preflight import require

    def read_pdf(path):
        require(["pypdf"], feature="PDF reading")
        import pypdf
        ...
"""
from __future__ import annotations

import importlib.util
import os
import platform
import sys
from typing import Iterable, Optional, Sequence


# Map the *import name* (what `import X` uses) to the *pip package name*.
# Most packages use the same name for both, but a handful differ
# (e.g. you `import docx` but `pip install python-docx`).
_PIP_NAME_OVERRIDES = {
    "docx": "python-docx",
    "pptx": "python-pptx",
    "PIL": "Pillow",
    "cv2": "opencv-python",
    "yaml": "PyYAML",
    "bs4": "beautifulsoup4",
    "sklearn": "scikit-learn",
    "Crypto": "pycryptodome",
}


def _pip_name(import_name: str) -> str:
    return _PIP_NAME_OVERRIDES.get(import_name, import_name)


def missing_packages(import_names: Iterable[str]) -> list[str]:
    """Return the subset of `import_names` that are NOT importable."""
    missing: list[str] = []
    for name in import_names:
        if importlib.util.find_spec(name) is None:
            missing.append(name)
    return missing


def _proxy_hint() -> Optional[str]:
    """Return whichever proxy env var is already set, or None."""
    for var in ("HTTPS_PROXY", "https_proxy", "HTTP_PROXY", "http_proxy"):
        val = os.environ.get(var)
        if val:
            return f"{var}={val}"
    return None


def _platform_name() -> str:
    sysname = platform.system()
    if sysname == "Darwin":
        return "macOS"
    return sysname or "Unknown"


def _pip_install_cmd(pip_names: Sequence[str]) -> str:
    pkgs = " ".join(pip_names)
    return f'"{sys.executable}" -m pip install --user {pkgs}'


def _proxy_set_snippets() -> list[tuple[str, str]]:
    """
    Return a list of (shell label, command) pairs showing how to set
    HTTPS_PROXY on the current platform. We show both the current
    platform's native shell *and* a cross-platform option so users
    who are SSH'd in or using a different shell still get help.
    """
    snippets: list[tuple[str, str]] = []
    sysname = platform.system()
    example = "http://proxy.example.com:8080"

    if sysname == "Windows":
        snippets.append(("PowerShell", f'$env:HTTPS_PROXY = "{example}"'))
        snippets.append(("cmd.exe",     f'set HTTPS_PROXY={example}'))
    else:
        snippets.append(("bash / zsh",  f'export HTTPS_PROXY={example}'))
        snippets.append(("fish",        f'set -x HTTPS_PROXY {example}'))
    return snippets


def format_install_guide(
    missing: Sequence[str],
    *,
    feature: Optional[str] = None,
    skill_name: Optional[str] = None,
) -> str:
    """
    Build a human- and agent-readable install guide for the given
    missing import names. Written in English + 中文 so both the user
    and an LLM agent reading stderr can act on it.
    """
    pip_names = [_pip_name(m) for m in missing]
    proxy_already = _proxy_hint()
    lines: list[str] = []

    header = "missing optional package(s)"
    if skill_name:
        header = f"[{skill_name}] {header}"
    lines.append(f"error: {header}: {', '.join(missing)}")
    if feature:
        lines.append(f"needed for: {feature}")
    lines.append(f"platform:   {_platform_name()} (Python {platform.python_version()})")
    lines.append("")

    lines.append("--- How to fix / 如何修復 ---")
    lines.append("")
    lines.append("1) Install with pip / 用 pip 安裝:")
    lines.append(f"   {_pip_install_cmd(pip_names)}")
    lines.append("")

    if proxy_already:
        lines.append(f"   (proxy detected / 偵測到 proxy: {proxy_already})")
        lines.append("")
    else:
        lines.append("2) Behind a corporate firewall? Set HTTPS_PROXY first,")
        lines.append("   then re-run the install command.")
        lines.append("   若在企業防火牆後，請先設定 HTTPS_PROXY 再重新執行安裝:")
        lines.append("")
        for shell, cmd in _proxy_set_snippets():
            lines.append(f"   [{shell}]  {cmd}")
        lines.append("")
        lines.append("   Replace proxy.example.com:8080 with your actual proxy.")
        lines.append("   請把 proxy.example.com:8080 換成你實際的 proxy 位址。")
        lines.append("")

    lines.append("3) After installing, re-run the original command.")
    lines.append("   安裝完成後，重新執行原本的指令即可。")
    return "\n".join(lines)


def require(
    import_names: Sequence[str],
    *,
    feature: Optional[str] = None,
    skill_name: Optional[str] = None,
    exit_code: int = 2,
) -> None:
    """
    Ensure every name in `import_names` is importable. If not, print a
    bilingual install guide to stderr and exit with `exit_code`.

    Call this LAZILY — right before the code path that actually needs
    the package. That keeps stdlib-only code paths working even when
    the optional packages are missing.
    """
    missing = missing_packages(import_names)
    if not missing:
        return
    print(
        format_install_guide(missing, feature=feature, skill_name=skill_name),
        file=sys.stderr,
    )
    sys.exit(exit_code)


def check(import_names: Sequence[str]) -> tuple[list[str], list[str]]:
    """
    Non-fatal variant of `require`. Returns (present, missing) lists so
    the caller can decide whether to skip a feature, emit a warning,
    or continue with reduced functionality.
    """
    missing = missing_packages(import_names)
    present = [n for n in import_names if n not in missing]
    return present, missing
