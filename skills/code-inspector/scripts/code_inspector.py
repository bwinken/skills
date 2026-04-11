#!/usr/bin/env python3
"""
code-inspector — structural inspection of a codebase.

Returns deterministic, agent-ready facts about a project folder so an
LLM can skip the usual `ls` / `cat` / grep exploration. Two feature
tiers dispatched via `--feature`:

  overview
    * Language + LOC breakdown (file extension → files + lines)
    * Detected entry points (pyproject.toml, package.json, Cargo.toml,
      Dockerfile, main.py, index.ts, ...)
    * Detected frameworks (Django, FastAPI, React, Next.js, pytest,
      Jest, ...)
    * Detected test layout (tests/, __tests__/, test_*.py, jest.config,
      ...)

  ast  (Python only for now — stdlib ast module)
    * Per-file classes (name, line, bases, methods, length)
    * Per-file top-level functions (name, line, args, async, return
      annotation, length)
    * Per-file imports (import X / from X import Y, with relative-
      import depth)
    * Per-file complexity indicators (statement count, max nesting
      depth, has `if __name__ == "__main__":`)
    * Aggregate totals + top-N most-complex files

Directory tree (`--tree`) is an orthogonal output toggle, not a
feature — it can be added on top of any feature selection.

Sibling skill of the `document-inspector` plugin's per-format
inspectors. This skill operates on a *folder*, not a single file,
which is why it stays a single skill with internal feature dispatch
rather than splitting per language.

Usage:
    code_inspector.py <path> [--feature overview|ast|all]
                             [--tree] [--tree-depth N]
                             [--max-files N] [--max-depth N]
                             [--max-ast-files N]
                             [--format text|json]

Run with --help for the full option list.
"""
from __future__ import annotations

import argparse
import ast
import fnmatch
import json
import os
import subprocess
import sys
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Optional

# Keep the skill folder copy-and-go. _preflight is imported for parity
# with other skills — code-inspector itself needs nothing beyond the
# standard library (including the `ast` module, also stdlib).
sys.path.insert(0, str(Path(__file__).resolve().parent))
import _preflight  # noqa: E402,F401


# ===========================================================================
# Data model
# ===========================================================================

@dataclass
class LanguageStat:
    extension: str
    files: int = 0
    lines: int = 0


@dataclass
class EntryPoint:
    path: str
    kind: str  # "python", "node", "rust", "go", "java", "dotnet", "make", ...


@dataclass
class Framework:
    name: str
    evidence: str  # path or short explanation of why we think it's there


@dataclass
class TestLayout:
    directories: list[str] = field(default_factory=list)
    file_patterns: list[str] = field(default_factory=list)
    runner_configs: list[str] = field(default_factory=list)


@dataclass
class OverviewSection:
    languages: list[LanguageStat] = field(default_factory=list)
    entry_points: list[EntryPoint] = field(default_factory=list)
    frameworks: list[Framework] = field(default_factory=list)
    tests: TestLayout = field(default_factory=TestLayout)


# --- AST layer --------------------------------------------------------------

@dataclass
class ClassInfo:
    name: str
    line: int
    bases: list[str]
    method_count: int
    methods: list[str]
    length: int          # end_lineno - lineno + 1


@dataclass
class FunctionInfo:
    name: str
    line: int
    arg_count: int
    is_async: bool
    has_return_annotation: bool
    length: int


@dataclass
class ImportInfo:
    kind: str            # "import" or "from_import"
    module: Optional[str]
    names: list[str]
    level: int           # 0 = absolute, 1+ = relative dots ("from .foo import bar" → 1)
    line: int


@dataclass
class FileAST:
    path: str            # relative path from project root
    total_lines: int = 0
    total_statements: int = 0
    max_nesting_depth: int = 0
    has_main: bool = False
    classes: list[ClassInfo] = field(default_factory=list)
    functions: list[FunctionInfo] = field(default_factory=list)
    imports: list[ImportInfo] = field(default_factory=list)
    parse_error: Optional[str] = None


@dataclass
class ASTTotals:
    classes: int = 0
    functions: int = 0
    imports: int = 0
    modules_with_main: int = 0


@dataclass
class MostComplexFile:
    path: str
    score: int
    classes: int
    functions: int
    max_nesting_depth: int


@dataclass
class ASTSection:
    python_file_count: int = 0
    parsed_file_count: int = 0
    skipped: list[dict] = field(default_factory=list)  # [{path, reason}]
    totals: ASTTotals = field(default_factory=ASTTotals)
    most_complex_files: list[MostComplexFile] = field(default_factory=list)
    files: list[FileAST] = field(default_factory=list)
    truncated: bool = False
    limit_reached: Optional[str] = None


@dataclass
class InspectReport:
    root: str
    feature: str = "all"
    scanned_files: int = 0
    scanned_directories: int = 0
    walk_truncated: bool = False
    walk_limit_reached: Optional[str] = None
    notes: list[str] = field(default_factory=list)
    overview: Optional[OverviewSection] = None
    ast: Optional[ASTSection] = None
    tree: Optional[str] = None


# ===========================================================================
# Ignore handling
# ===========================================================================

DEFAULT_IGNORED_DIRS = frozenset({
    ".git", ".hg", ".svn",
    "node_modules", "bower_components",
    ".venv", "venv", "env", ".env",
    "__pycache__", ".mypy_cache", ".pytest_cache", ".ruff_cache", ".tox",
    ".idea", ".vscode",
    "dist", "build", "target", "out", "bin", "obj",
    ".next", ".nuxt", ".svelte-kit",
    "coverage", ".coverage", ".nyc_output",
    ".DS_Store",
})

DEFAULT_IGNORED_FILE_SUFFIXES = frozenset({
    ".pyc", ".pyo", ".class", ".o", ".obj", ".so", ".dll", ".dylib",
    ".exe", ".out",
    ".min.js", ".min.css", ".map",
    ".log", ".tmp", ".swp",
})


def _git_tracked_files(root: Path) -> Optional[set[Path]]:
    """Git-aware file list (honors .gitignore). None if not a repo."""
    if not (root / ".git").exists():
        return None
    try:
        proc = subprocess.run(
            ["git", "-C", str(root), "ls-files", "-z"],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            check=False,
            timeout=15,
        )
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None
    if proc.returncode != 0:
        return None
    raw = proc.stdout.decode("utf-8", errors="replace")
    files: set[Path] = set()
    for name in raw.split("\0"):
        if not name:
            continue
        files.add((root / name).resolve())
    return files


# ===========================================================================
# Language detection
# ===========================================================================

EXTENSION_LANGUAGES: dict[str, str] = {
    ".py": "Python", ".pyi": "Python",
    ".ipynb": "Jupyter Notebook",
    ".js": "JavaScript", ".mjs": "JavaScript", ".cjs": "JavaScript",
    ".jsx": "JavaScript (JSX)",
    ".ts": "TypeScript", ".tsx": "TypeScript (TSX)",
    ".go": "Go",
    ".rs": "Rust",
    ".java": "Java",
    ".kt": "Kotlin", ".kts": "Kotlin",
    ".c": "C", ".h": "C header",
    ".cc": "C++", ".cpp": "C++", ".hpp": "C++ header", ".hh": "C++ header",
    ".cs": "C#",
    ".rb": "Ruby",
    ".php": "PHP",
    ".swift": "Swift",
    ".m": "Objective-C",
    ".sh": "Shell", ".bash": "Shell", ".zsh": "Shell",
    ".ps1": "PowerShell",
    ".sql": "SQL",
    ".html": "HTML", ".htm": "HTML",
    ".css": "CSS", ".scss": "SCSS", ".sass": "Sass", ".less": "Less",
    ".vue": "Vue", ".svelte": "Svelte",
    ".md": "Markdown", ".mdx": "MDX", ".rst": "reStructuredText",
    ".json": "JSON", ".yaml": "YAML", ".yml": "YAML", ".toml": "TOML",
    ".xml": "XML",
    ".r": "R", ".R": "R",
    ".lua": "Lua",
    ".ex": "Elixir", ".exs": "Elixir",
    ".erl": "Erlang",
    ".hs": "Haskell",
    ".dart": "Dart",
    ".zig": "Zig",
}


def _count_lines(path: Path) -> int:
    try:
        with path.open("rb") as f:
            return sum(1 for _ in f)
    except OSError:
        return 0


# ===========================================================================
# Entry-point detection
# ===========================================================================

ENTRY_POINT_FILES: dict[str, str] = {
    "pyproject.toml": "python",
    "setup.py": "python",
    "setup.cfg": "python",
    "requirements.txt": "python",
    "Pipfile": "python",
    "poetry.lock": "python",
    "manage.py": "python",
    "package.json": "node",
    "pnpm-lock.yaml": "node",
    "yarn.lock": "node",
    "deno.json": "node",
    "bun.lockb": "node",
    "Cargo.toml": "rust",
    "go.mod": "go",
    "go.sum": "go",
    "pom.xml": "java",
    "build.gradle": "java",
    "build.gradle.kts": "java",
    "settings.gradle": "java",
    "mix.exs": "elixir",
    "Gemfile": "ruby",
    "composer.json": "php",
    "Makefile": "make",
    "Rakefile": "ruby",
    "CMakeLists.txt": "cmake",
    "Dockerfile": "docker",
    "docker-compose.yml": "docker",
    "docker-compose.yaml": "docker",
}

PROGRAM_ENTRY_NAMES: dict[str, str] = {
    "main.py": "python",
    "__main__.py": "python",
    "app.py": "python",
    "index.js": "node",
    "index.ts": "node",
    "index.mjs": "node",
    "main.go": "go",
    "main.rs": "rust",
    "Main.java": "java",
    "Program.cs": "dotnet",
}


# ===========================================================================
# Framework detection
# ===========================================================================

def _detect_frameworks(
    files_rel: list[str],
    package_json_text: Optional[str],
    pyproject_text: Optional[str],
    requirements_text: Optional[str],
) -> list[Framework]:
    frameworks: list[Framework] = []
    rel_set = set(files_rel)

    py_text = " ".join(filter(None, [pyproject_text, requirements_text])).lower()
    py_checks = [
        ("Django", "django", "pyproject.toml/requirements.txt"),
        ("FastAPI", "fastapi", "pyproject.toml/requirements.txt"),
        ("Flask", "flask", "pyproject.toml/requirements.txt"),
        ("Starlette", "starlette", "pyproject.toml/requirements.txt"),
        ("aiohttp", "aiohttp", "pyproject.toml/requirements.txt"),
        ("Tornado", "tornado", "pyproject.toml/requirements.txt"),
        ("Pyramid", "pyramid", "pyproject.toml/requirements.txt"),
        ("pytest", "pytest", "pyproject.toml/requirements.txt"),
        ("SQLAlchemy", "sqlalchemy", "pyproject.toml/requirements.txt"),
        ("Pydantic", "pydantic", "pyproject.toml/requirements.txt"),
        ("Celery", "celery", "pyproject.toml/requirements.txt"),
    ]
    for label, needle, evidence in py_checks:
        if needle in py_text:
            frameworks.append(Framework(name=label, evidence=evidence))

    if "manage.py" in rel_set and not any(f.name == "Django" for f in frameworks):
        frameworks.append(Framework(name="Django", evidence="manage.py"))

    if package_json_text:
        try:
            pkg = json.loads(package_json_text)
        except json.JSONDecodeError:
            pkg = {}
        deps: dict = {}
        for key in ("dependencies", "devDependencies", "peerDependencies"):
            d = pkg.get(key) or {}
            if isinstance(d, dict):
                deps.update(d)
        node_checks = [
            ("React", "react"),
            ("Next.js", "next"),
            ("Nuxt", "nuxt"),
            ("Vue", "vue"),
            ("Svelte", "svelte"),
            ("SvelteKit", "@sveltejs/kit"),
            ("Angular", "@angular/core"),
            ("Express", "express"),
            ("Fastify", "fastify"),
            ("NestJS", "@nestjs/core"),
            ("Remix", "@remix-run/react"),
            ("Astro", "astro"),
            ("Vite", "vite"),
            ("Webpack", "webpack"),
            ("TypeScript", "typescript"),
            ("Jest", "jest"),
            ("Vitest", "vitest"),
            ("Playwright", "@playwright/test"),
        ]
        for label, dep in node_checks:
            if dep in deps:
                frameworks.append(Framework(name=label, evidence=f"package.json[{dep}]"))

    if "go.mod" in rel_set:
        frameworks.append(Framework(name="Go modules", evidence="go.mod"))
    if "Cargo.toml" in rel_set:
        frameworks.append(Framework(name="Cargo (Rust)", evidence="Cargo.toml"))

    seen: set[str] = set()
    unique: list[Framework] = []
    for f in frameworks:
        if f.name in seen:
            continue
        seen.add(f.name)
        unique.append(f)
    return unique


# ===========================================================================
# Test layout detection
# ===========================================================================

TEST_DIR_NAMES = frozenset({"tests", "test", "__tests__", "spec", "specs"})
TEST_FILE_GLOBS = (
    "*_test.py", "test_*.py",
    "*.test.js", "*.test.ts", "*.spec.js", "*.spec.ts",
    "*_test.go",
    "*Test.java",
    "*_spec.rb",
)
TEST_RUNNER_CONFIGS = (
    "pytest.ini", "tox.ini",
    "jest.config.js", "jest.config.ts", "jest.config.mjs", "jest.config.cjs",
    "vitest.config.js", "vitest.config.ts",
    "playwright.config.js", "playwright.config.ts",
    "karma.conf.js", "mocharc.json", ".mocharc.json",
    "phpunit.xml",
)


def _detect_tests(rel_files: list[str]) -> TestLayout:
    test_dirs_found: list[str] = []
    test_file_patterns_found: list[str] = []
    runner_configs_found: list[str] = []
    for rel in rel_files:
        parts = rel.split("/")
        for part in parts[:-1]:
            if part in TEST_DIR_NAMES:
                idx = parts.index(part)
                test_dirs_found.append("/".join(parts[: idx + 1]))
                break
        name = parts[-1]
        if name in TEST_RUNNER_CONFIGS:
            runner_configs_found.append(rel)
        for glob_pat in TEST_FILE_GLOBS:
            if fnmatch.fnmatch(name, glob_pat):
                test_file_patterns_found.append(glob_pat)
                break
    return TestLayout(
        directories=sorted(set(test_dirs_found)),
        file_patterns=sorted(set(test_file_patterns_found)),
        runner_configs=sorted(set(runner_configs_found)),
    )


# ===========================================================================
# Directory walker
# ===========================================================================

@dataclass
class _WalkResult:
    files: list[Path]
    directories: list[Path]
    truncated: bool
    limit_reason: Optional[str]


def _walk_project(
    root: Path,
    *,
    max_files: int,
    max_depth: Optional[int],
    tracked: Optional[set[Path]],
) -> _WalkResult:
    files: list[Path] = []
    dirs: list[Path] = []
    truncated = False
    limit_reason: Optional[str] = None

    root_abs = root.resolve()

    for dirpath, dirnames, filenames in os.walk(root_abs, followlinks=False):
        here = Path(dirpath)

        if max_depth is not None:
            try:
                rel_depth = len(here.relative_to(root_abs).parts)
            except ValueError:
                rel_depth = 0
            if rel_depth > max_depth:
                dirnames[:] = []
                continue

        dirnames[:] = [d for d in dirnames if d not in DEFAULT_IGNORED_DIRS]
        dirs.append(here)

        for name in filenames:
            fp = here / name
            lower = name.lower()
            if any(lower.endswith(s) for s in DEFAULT_IGNORED_FILE_SUFFIXES):
                continue
            if tracked is not None:
                try:
                    if fp.resolve() not in tracked:
                        continue
                except OSError:
                    continue
            files.append(fp)
            if len(files) >= max_files:
                truncated = True
                limit_reason = f"max_files={max_files} reached"
                return _WalkResult(
                    files=files, directories=dirs,
                    truncated=truncated, limit_reason=limit_reason,
                )

    return _WalkResult(
        files=files, directories=dirs,
        truncated=truncated, limit_reason=limit_reason,
    )


# ===========================================================================
# AST layer — Python-only (stdlib ast module)
# ===========================================================================

_NESTING_NODE_TYPES: tuple = (
    ast.If, ast.For, ast.While, ast.Try, ast.With,
    ast.AsyncFor, ast.AsyncWith,
)


def _unparse_base(node) -> str:
    """
    Render an ast expression node as a short string (best effort).
    Uses ast.unparse() when available (Python 3.9+), otherwise falls
    back to Name.id / Attribute chains.
    """
    if hasattr(ast, "unparse"):
        try:
            return ast.unparse(node)
        except Exception:  # noqa: BLE001
            pass
    # Manual fallback for 3.8: just handle Name and simple Attribute.
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        parts: list[str] = []
        cur = node
        while isinstance(cur, ast.Attribute):
            parts.append(cur.attr)
            cur = cur.value
        if isinstance(cur, ast.Name):
            parts.append(cur.id)
        return ".".join(reversed(parts))
    return type(node).__name__


def _node_length(node) -> int:
    start = getattr(node, "lineno", None) or 0
    end = getattr(node, "end_lineno", None) or start
    if end < start:
        return 1
    return max(1, end - start + 1)


def _extract_class(node: ast.ClassDef) -> ClassInfo:
    bases = [_unparse_base(b) for b in node.bases]
    methods = [
        child.name
        for child in node.body
        if isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]
    return ClassInfo(
        name=node.name,
        line=node.lineno,
        bases=bases,
        method_count=len(methods),
        methods=methods,
        length=_node_length(node),
    )


def _extract_function(node) -> FunctionInfo:
    args = node.args
    arg_count = len(args.args) + len(getattr(args, "kwonlyargs", []))
    if getattr(args, "vararg", None):
        arg_count += 1
    if getattr(args, "kwarg", None):
        arg_count += 1
    return FunctionInfo(
        name=node.name,
        line=node.lineno,
        arg_count=arg_count,
        is_async=isinstance(node, ast.AsyncFunctionDef),
        has_return_annotation=node.returns is not None,
        length=_node_length(node),
    )


def _extract_imports(node) -> list[ImportInfo]:
    out: list[ImportInfo] = []
    if isinstance(node, ast.Import):
        for alias in node.names:
            out.append(ImportInfo(
                kind="import",
                module=alias.name,
                names=[alias.asname or alias.name],
                level=0,
                line=node.lineno,
            ))
    elif isinstance(node, ast.ImportFrom):
        out.append(ImportInfo(
            kind="from_import",
            module=node.module,
            names=[(a.asname or a.name) for a in node.names],
            level=node.level or 0,
            line=node.lineno,
        ))
    return out


def _is_main_check(node) -> bool:
    """
    True if `node` is `if __name__ == "__main__":`. Handles both
    Name / Constant comparisons in either order.
    """
    if not isinstance(node, ast.If):
        return False
    test = node.test
    if not isinstance(test, ast.Compare):
        return False
    if len(test.ops) != 1 or not isinstance(test.ops[0], ast.Eq):
        return False
    left, right = test.left, test.comparators[0]

    def _is_name_dunder(n) -> bool:
        return isinstance(n, ast.Name) and n.id == "__name__"

    def _is_main_literal(n) -> bool:
        if isinstance(n, ast.Constant) and n.value == "__main__":
            return True
        # Py 3.7 legacy: ast.Str
        if getattr(ast, "Str", None) is not None and isinstance(n, getattr(ast, "Str")):
            return getattr(n, "s", None) == "__main__"
        return False

    return (
        (_is_name_dunder(left) and _is_main_literal(right))
        or (_is_name_dunder(right) and _is_main_literal(left))
    )


class _NestingDepthVisitor(ast.NodeVisitor):
    """Tracks the maximum block-statement nesting depth."""
    def __init__(self) -> None:
        self.depth = 0
        self.max_depth = 0

    def generic_visit(self, node):  # type: ignore[override]
        bump = isinstance(node, _NESTING_NODE_TYPES)
        if bump:
            self.depth += 1
            if self.depth > self.max_depth:
                self.max_depth = self.depth
        super().generic_visit(node)
        if bump:
            self.depth -= 1


def _analyze_python_file(source: str, rel_path: str) -> FileAST:
    """Parse a single .py file into a FileAST. Never raises."""
    fa = FileAST(path=rel_path)
    fa.total_lines = source.count("\n") + (0 if source.endswith("\n") else 1)

    try:
        tree = ast.parse(source, filename=rel_path)
    except SyntaxError as e:
        fa.parse_error = f"SyntaxError: {e.msg} at line {e.lineno}"
        return fa
    except Exception as e:  # noqa: BLE001
        fa.parse_error = f"parse error: {e}"
        return fa

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            fa.classes.append(_extract_class(node))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            fa.functions.append(_extract_function(node))
        elif isinstance(node, (ast.Import, ast.ImportFrom)):
            fa.imports.extend(_extract_imports(node))
        elif _is_main_check(node):
            fa.has_main = True

    # Imports inside classes or functions are missed by the top-level
    # scan above. For the common case (module-level) this is what you
    # want anyway. If we ever need inner imports we can add a second
    # pass with ast.walk.

    # Total statements = every ast.stmt node anywhere in the tree.
    fa.total_statements = sum(1 for n in ast.walk(tree) if isinstance(n, ast.stmt))

    visitor = _NestingDepthVisitor()
    visitor.visit(tree)
    fa.max_nesting_depth = visitor.max_depth

    return fa


def _complexity_score(fa: FileAST) -> int:
    """
    Rough complexity proxy used only for ranking most-complex files.
    Not a real cyclomatic complexity — we're deliberately avoiding a
    full CFG analysis for layer 2.
    """
    return (
        len(fa.classes) * 3
        + len(fa.functions) * 2
        + fa.max_nesting_depth * 4
        + fa.total_statements // 10
    )


def _build_ast_section(
    py_files: list[Path],
    root_abs: Path,
    *,
    max_ast_files: int,
) -> ASTSection:
    section = ASTSection()
    section.python_file_count = len(py_files)

    to_parse = py_files[:max_ast_files]
    if len(py_files) > max_ast_files:
        section.truncated = True
        section.limit_reached = f"max_ast_files={max_ast_files} reached"

    parsed_files: list[FileAST] = []
    for fp in to_parse:
        try:
            rel = fp.resolve().relative_to(root_abs)
        except ValueError:
            rel = Path(fp.name)
        rel_str = str(rel).replace("\\", "/")

        try:
            source = fp.read_text(encoding="utf-8", errors="replace")
        except OSError as e:
            section.skipped.append({"path": rel_str, "reason": f"read failed: {e}"})
            continue

        fa = _analyze_python_file(source, rel_str)
        if fa.parse_error:
            section.skipped.append({"path": rel_str, "reason": fa.parse_error})
            continue
        parsed_files.append(fa)

    section.parsed_file_count = len(parsed_files)
    section.files = parsed_files

    # Aggregate totals.
    totals = ASTTotals()
    for fa in parsed_files:
        totals.classes += len(fa.classes)
        totals.functions += len(fa.functions)
        totals.imports += len(fa.imports)
        if fa.has_main:
            totals.modules_with_main += 1
    section.totals = totals

    # Top-N most complex.
    ranked = sorted(
        parsed_files,
        key=_complexity_score,
        reverse=True,
    )[:10]
    section.most_complex_files = [
        MostComplexFile(
            path=fa.path,
            score=_complexity_score(fa),
            classes=len(fa.classes),
            functions=len(fa.functions),
            max_nesting_depth=fa.max_nesting_depth,
        )
        for fa in ranked
    ]

    return section


# ===========================================================================
# Tree
# ===========================================================================

def _render_tree(root: Path, max_depth: int) -> str:
    lines: list[str] = [str(root.name or root)]

    def _walk(path: Path, prefix: str, depth: int) -> None:
        if depth > max_depth:
            return
        try:
            entries = sorted(
                [e for e in path.iterdir() if e.name not in DEFAULT_IGNORED_DIRS],
                key=lambda p: (not p.is_dir(), p.name.lower()),
            )
        except OSError:
            return
        count = len(entries)
        for i, entry in enumerate(entries):
            connector = "└── " if i == count - 1 else "├── "
            suffix = "/" if entry.is_dir() else ""
            lines.append(prefix + connector + entry.name + suffix)
            if entry.is_dir() and depth < max_depth:
                extension = "    " if i == count - 1 else "│   "
                _walk(entry, prefix + extension, depth + 1)

    _walk(root, "", 1)
    return "\n".join(lines)


# ===========================================================================
# Main analysis
# ===========================================================================

FEATURES = ("overview", "ast", "all")


def inspect(
    root: Path,
    *,
    feature: str,
    max_files: int,
    max_depth: Optional[int],
    max_ast_files: int,
    include_tree: bool,
    tree_depth: int,
) -> InspectReport:
    report = InspectReport(root=str(root.resolve()), feature=feature)

    tracked = _git_tracked_files(root)
    if tracked is None:
        report.notes.append(
            "no .git/ detected or git ls-files failed — falling back to "
            "hard-coded ignore list"
        )
    else:
        report.notes.append(
            f"git-tracked file list in use ({len(tracked)} files)"
        )

    walk = _walk_project(
        root,
        max_files=max_files,
        max_depth=max_depth,
        tracked=tracked,
    )
    report.scanned_files = len(walk.files)
    report.scanned_directories = len(walk.directories)
    report.walk_truncated = walk.truncated
    report.walk_limit_reached = walk.limit_reason

    root_abs = root.resolve()
    rel_files: list[str] = []
    for fp in walk.files:
        try:
            rel = fp.resolve().relative_to(root_abs)
        except ValueError:
            continue
        rel_files.append(str(rel).replace("\\", "/"))

    # --- overview section -------------------------------------------------
    if feature in ("overview", "all"):
        overview = OverviewSection()

        lang_files: dict[str, int] = {}
        lang_lines: dict[str, int] = {}
        for fp in walk.files:
            ext = fp.suffix
            lang_files[ext] = lang_files.get(ext, 0) + 1
            if ext in EXTENSION_LANGUAGES:
                lang_lines[ext] = lang_lines.get(ext, 0) + _count_lines(fp)
        overview.languages = sorted(
            [
                LanguageStat(extension=ext, files=lang_files[ext],
                             lines=lang_lines.get(ext, 0))
                for ext in lang_files
            ],
            key=lambda s: (-s.files, s.extension),
        )

        seen_ep: set[str] = set()
        for rel in rel_files:
            name = rel.rsplit("/", 1)[-1]
            if name in ENTRY_POINT_FILES:
                if rel in seen_ep:
                    continue
                seen_ep.add(rel)
                overview.entry_points.append(
                    EntryPoint(path=rel, kind=ENTRY_POINT_FILES[name])
                )
            elif name in PROGRAM_ENTRY_NAMES:
                parts = rel.split("/")
                if len(parts) <= 2 or parts[0] in ("src", "app", "lib", "cmd"):
                    if rel in seen_ep:
                        continue
                    seen_ep.add(rel)
                    overview.entry_points.append(
                        EntryPoint(path=rel, kind=PROGRAM_ENTRY_NAMES[name])
                    )

        def _read_text(rel: str) -> Optional[str]:
            fp = root_abs / rel
            try:
                return fp.read_text(encoding="utf-8", errors="replace")
            except OSError:
                return None

        overview.frameworks = _detect_frameworks(
            files_rel=rel_files,
            package_json_text=_read_text("package.json") if "package.json" in rel_files else None,
            pyproject_text=_read_text("pyproject.toml") if "pyproject.toml" in rel_files else None,
            requirements_text=_read_text("requirements.txt") if "requirements.txt" in rel_files else None,
        )

        overview.tests = _detect_tests(rel_files)
        report.overview = overview

    # --- ast section ------------------------------------------------------
    if feature in ("ast", "all"):
        py_files = [fp for fp in walk.files if fp.suffix == ".py"]
        report.ast = _build_ast_section(
            py_files,
            root_abs,
            max_ast_files=max_ast_files,
        )

    # --- tree (orthogonal) ------------------------------------------------
    if include_tree:
        report.tree = _render_tree(root_abs, tree_depth)

    return report


# ===========================================================================
# Rendering
# ===========================================================================

def render_text(r: InspectReport) -> str:
    out: list[str] = []
    out.append("# code-inspector")
    out.append(f"root:            {r.root}")
    out.append(f"feature:         {r.feature}")
    out.append(f"scanned files:   {r.scanned_files}")
    out.append(f"scanned dirs:    {r.scanned_directories}")
    if r.walk_truncated:
        out.append(f"walk truncated:  yes ({r.walk_limit_reached})")
    for note in r.notes:
        out.append(f"note:            {note}")
    out.append("")

    # Overview
    if r.overview is not None:
        ov = r.overview

        if ov.languages:
            out.append("## Languages")
            out.append(f"{'ext':<12}{'files':>8}{'lines':>12}  language")
            out.append("-" * 56)
            for stat in ov.languages[:40]:
                lang = EXTENSION_LANGUAGES.get(stat.extension, "")
                ext = stat.extension or "(none)"
                out.append(f"{ext:<12}{stat.files:>8}{stat.lines:>12}  {lang}")
            if len(ov.languages) > 40:
                out.append(f"... ({len(ov.languages) - 40} more extensions)")
            out.append("")

        if ov.entry_points:
            out.append("## Entry points")
            for ep in ov.entry_points:
                out.append(f"  [{ep.kind}] {ep.path}")
            out.append("")

        if ov.frameworks:
            out.append("## Frameworks / libraries")
            for fw in ov.frameworks:
                out.append(f"  {fw.name}  — {fw.evidence}")
            out.append("")

        if ov.tests.directories or ov.tests.file_patterns or ov.tests.runner_configs:
            out.append("## Tests")
            if ov.tests.directories:
                out.append("  directories:")
                for d in ov.tests.directories[:20]:
                    out.append(f"    {d}/")
                if len(ov.tests.directories) > 20:
                    out.append(f"    ... ({len(ov.tests.directories) - 20} more)")
            if ov.tests.file_patterns:
                out.append("  file patterns:")
                for p in ov.tests.file_patterns:
                    out.append(f"    {p}")
            if ov.tests.runner_configs:
                out.append("  runner configs:")
                for c in ov.tests.runner_configs:
                    out.append(f"    {c}")
            out.append("")

    # AST
    if r.ast is not None:
        a = r.ast
        out.append("## Python AST")
        out.append(f"  python_file_count: {a.python_file_count}")
        out.append(f"  parsed:            {a.parsed_file_count}")
        if a.skipped:
            out.append(f"  skipped:           {len(a.skipped)}")
            for item in a.skipped[:10]:
                out.append(f"    - {item.get('path')}: {item.get('reason')}")
            if len(a.skipped) > 10:
                out.append(f"    ... ({len(a.skipped) - 10} more)")
        if a.truncated:
            out.append(f"  ast truncated:     yes ({a.limit_reached})")
        t = a.totals
        out.append(f"  totals: classes={t.classes}, functions={t.functions}, "
                   f"imports={t.imports}, modules_with_main={t.modules_with_main}")

        if a.most_complex_files:
            out.append("")
            out.append("  most_complex_files (top 10 by score):")
            for mcf in a.most_complex_files:
                out.append(
                    f"    {mcf.score:>5}  {mcf.path}  "
                    f"(classes={mcf.classes}, functions={mcf.functions}, "
                    f"max_nesting={mcf.max_nesting_depth})"
                )

        if a.files:
            out.append("")
            out.append("  files:")
            for fa in a.files[:40]:
                head = f"    {fa.path}  [{fa.total_lines} lines, "
                head += f"{fa.total_statements} stmts, max_nesting={fa.max_nesting_depth}"
                if fa.has_main:
                    head += ", has __main__"
                head += "]"
                out.append(head)
                if fa.classes:
                    for c in fa.classes[:10]:
                        base_str = f"({', '.join(c.bases)})" if c.bases else ""
                        out.append(
                            f"      class {c.name}{base_str}  "
                            f"line {c.line}, methods={c.method_count}, "
                            f"lines={c.length}"
                        )
                    if len(fa.classes) > 10:
                        out.append(f"      ... ({len(fa.classes) - 10} more classes)")
                if fa.functions:
                    for fn in fa.functions[:10]:
                        async_str = "async " if fn.is_async else ""
                        ret_str = " → T" if fn.has_return_annotation else ""
                        out.append(
                            f"      {async_str}def {fn.name}(...)  "
                            f"line {fn.line}, args={fn.arg_count}{ret_str}, "
                            f"lines={fn.length}"
                        )
                    if len(fa.functions) > 10:
                        out.append(f"      ... ({len(fa.functions) - 10} more functions)")
                if fa.imports:
                    imp_count = len(fa.imports)
                    first_few = []
                    for imp in fa.imports[:5]:
                        if imp.kind == "import":
                            first_few.append(imp.module or "?")
                        else:
                            dots = "." * imp.level
                            mod = imp.module or ""
                            first_few.append(f"from {dots}{mod} import "
                                             f"{', '.join(imp.names)}")
                    out.append(f"      imports ({imp_count}): {'; '.join(first_few)}"
                               + (" ..." if imp_count > 5 else ""))
            if len(a.files) > 40:
                out.append(f"    ... ({len(a.files) - 40} more files)")
        out.append("")

    if r.tree:
        out.append("## Tree")
        out.append(r.tree)
        out.append("")

    return "\n".join(out).rstrip() + "\n"


def render_json(r: InspectReport) -> str:
    return json.dumps(asdict(r), ensure_ascii=False, indent=2)


# ===========================================================================
# CLI
# ===========================================================================

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="code_inspector.py",
        description="Structural inspection of a codebase — language/LOC "
                    "breakdown, entry points, frameworks, test layout "
                    "(overview feature), plus Python AST analysis "
                    "(classes, functions, imports, complexity) via the "
                    "stdlib ast module. Gitignore-aware, read-only.",
    )
    p.add_argument("path", help="Path to the project root directory.")
    p.add_argument("--feature", choices=FEATURES, default="all",
                   help="Which inspection tier to run (default: all).")
    p.add_argument("--tree", action="store_true",
                   help="Also include an ASCII directory tree in the output.")
    p.add_argument("--tree-depth", type=int, default=3,
                   help="Max tree depth when --tree is set (default: 3).")
    p.add_argument("--max-files", type=int, default=5000,
                   help="Cap on total files scanned during the walk "
                        "(default: 5000).")
    p.add_argument("--max-depth", type=int, default=None,
                   help="Max directory depth to walk (default: unlimited).")
    p.add_argument("--max-ast-files", type=int, default=500,
                   help="Cap on number of .py files parsed for the AST "
                        "feature (default: 500). Larger monorepos should "
                        "raise this explicitly.")
    p.add_argument("--format", choices=("text", "json"), default="text",
                   help="Output format (default: text).")
    return p


def main(argv: Optional[list[str]] = None) -> int:
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
        except (AttributeError, ValueError):
            pass

    args = build_parser().parse_args(argv)
    root = Path(args.path)
    if not root.exists():
        print(f"error: path does not exist: {root}", file=sys.stderr)
        return 2
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    report = inspect(
        root,
        feature=args.feature,
        max_files=args.max_files,
        max_depth=args.max_depth,
        max_ast_files=args.max_ast_files,
        include_tree=args.tree,
        tree_depth=args.tree_depth,
    )

    if args.format == "json":
        print(render_json(report))
    else:
        print(render_text(report))
    return 0


if __name__ == "__main__":
    sys.exit(main())
