"""Step 2-3: read repository structure, detect languages/frameworks/tools, explain key files."""
from __future__ import annotations
import ast
import importlib.util
import json
import os
import re
import sys
from collections import Counter
from dataclasses import dataclass, field, asdict
from pathlib import Path

from .git_ops import Git

LANGS = {".py": "Python", ".js": "JavaScript", ".jsx": "JavaScript", ".ts": "TypeScript", ".tsx": "TypeScript",
         ".java": "Java", ".go": "Go", ".rs": "Rust", ".rb": "Ruby", ".php": "PHP", ".c": "C", ".h": "C",
         ".cpp": "C++", ".cs": "C#", ".kt": "Kotlin", ".swift": "Swift", ".sh": "Shell",
         ".html": "HTML", ".css": "CSS", ".sql": "SQL"}
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build", ".mypy_cache", ".pytest_cache"}

FRAMEWORK_HINTS = {  # keyword in a dependency manifest -> framework label
    "flask": "Flask", "django": "Django", "fastapi": "FastAPI", "pytest": "pytest", "numpy": "NumPy",
    "pandas": "pandas", "torch": "PyTorch", "tensorflow": "TensorFlow", "sqlalchemy": "SQLAlchemy",
    "express": "Express.js", "react": "React", "next": "Next.js", "vue": "Vue", "jest": "Jest",
    "spring-boot": "Spring Boot", "junit": "JUnit", "gin-gonic": "Gin", "actix": "Actix", "rocket": "Rocket",
}
CONFIG_TOOLS = {  # filename -> (tool, purpose)
    "pytest.ini": ("pytest", "Python test runner"), "tox.ini": ("tox", "multi-env test automation"),
    ".flake8": ("flake8", "Python linter"), ".pre-commit-config.yaml": ("pre-commit", "git hook runner"),
    "Makefile": ("make", "task runner"), "Dockerfile": ("Docker", "container build"),
    "docker-compose.yml": ("Docker Compose", "multi-container dev setup"),
    ".eslintrc": ("ESLint", "JS/TS linter"), ".eslintrc.json": ("ESLint", "JS/TS linter"),
    ".prettierrc": ("Prettier", "code formatter"), "jest.config.js": ("Jest", "JS test runner"),
    "tsconfig.json": ("TypeScript", "type checker/compiler"), "ruff.toml": ("Ruff", "Python linter/formatter"),
    "mypy.ini": ("mypy", "Python type checker"),
}
FILE_PURPOSES = {
    "README.md": "Project overview and usage instructions.", "LICENSE": "Open-source license terms.",
    "requirements.txt": "Python dependency list.", "pyproject.toml": "Python project metadata / tool config.",
    "setup.py": "Python packaging script.", "package.json": "Node.js manifest: dependencies and scripts.",
    "go.mod": "Go module definition.", "Cargo.toml": "Rust crate manifest.", "pom.xml": "Maven build definition.",
    "Makefile": "Shortcut commands for build/test/lint.", "Dockerfile": "Instructions to build the container image.",
    ".gitignore": "Files git should not track.", "CONTRIBUTING.md": "Contribution rules.",
}


@dataclass
class RepoReport:
    root: str
    files: list[str]
    languages: dict[str, int]
    frameworks: list[str]
    package_managers: list[str]
    dev_tools: list[dict]
    key_files: list[dict]
    test_command: list[str]
    tree: str = ""
    overview: str = ""

    def to_dict(self) -> dict:
        d = asdict(self)
        d["files"] = self.files[:200]
        return d


def list_files(root: Path) -> list[str]:
    git = Git(root)
    if git.is_repo():
        out = git.run("ls-files")
        return sorted(f for f in out.splitlines() if f)
    found = []
    for dp, dn, fn in os.walk(root):
        dn[:] = [d for d in dn if d not in SKIP_DIRS]
        for f in fn:
            found.append(os.path.relpath(os.path.join(dp, f), root).replace(os.sep, "/"))
    return sorted(found)


def render_tree(files: list[str], max_depth: int = 3) -> str:
    seen, lines = set(), []
    for f in files:
        parts = f.split("/")
        for i in range(min(len(parts), max_depth)):
            key = "/".join(parts[: i + 1])
            if key in seen:
                continue
            seen.add(key)
            is_dir = i < len(parts) - 1
            lines.append("  " * i + parts[i] + ("/" if is_dir else ""))
    return "\n".join(lines)


def _read(root: Path, rel: str, limit: int = 20000) -> str:
    try:
        return (root / rel).read_text(encoding="utf-8", errors="ignore")[:limit]
    except OSError:
        return ""


def _py_docstring(text: str) -> str:
    try:
        return (ast.get_docstring(ast.parse(text)) or "").strip().splitlines()[0] if text else ""
    except (SyntaxError, IndexError):
        return ""


def detect_test_command(root: Path, files: list[str], manifest_text: str) -> list[str]:
    pkg = _read(root, "package.json")
    if pkg:
        try:
            t = json.loads(pkg).get("scripts", {}).get("test", "")
            if t and "no test specified" not in t:
                return ["npm", "test", "--silent"]
        except json.JSONDecodeError:
            pass
    if "go.mod" in files:
        return ["go", "test", "./..."]
    if "Cargo.toml" in files:
        return ["cargo", "test"]
    if "pom.xml" in files:
        return ["mvn", "-q", "test"]
    if any(f.endswith(".py") for f in files):
        has_pytest = "pytest" in manifest_text.lower() or "pytest.ini" in files
        if has_pytest and importlib.util.find_spec("pytest"):
            return [sys.executable, "-m", "pytest", "-q"]
        if any(f.startswith("tests/") for f in files):
            return [sys.executable, "-m", "unittest", "discover", "-s", "tests", "-t", "."]
        return [sys.executable, "-m", "unittest", "discover"]
    return []


def analyze(root: Path) -> RepoReport:
    root = Path(root)
    files = list_files(root)
    langs = Counter(LANGS[Path(f).suffix] for f in files if Path(f).suffix in LANGS)

    manifests = [f for f in files if Path(f).name in
                 ("requirements.txt", "pyproject.toml", "package.json", "go.mod", "Cargo.toml", "pom.xml", "setup.py")]
    manifest_text = "\n".join(_read(root, m) for m in manifests)
    low = manifest_text.lower()
    frameworks = sorted({label for key, label in FRAMEWORK_HINTS.items() if re.search(rf"\b{re.escape(key)}\b", low)})

    pm = []
    for name, label in (("requirements.txt", "pip"), ("pyproject.toml", "pip/pyproject"), ("package.json", "npm"),
                        ("go.mod", "go modules"), ("Cargo.toml", "cargo"), ("pom.xml", "maven")):
        if name in files:
            pm.append(label)

    tools = []
    for f in files:
        base = Path(f).name
        if base in CONFIG_TOOLS:
            t, p = CONFIG_TOOLS[base]
            tools.append({"tool": t, "purpose": p, "evidence": f})
        if f.startswith(".github/workflows/"):
            tools.append({"tool": "GitHub Actions", "purpose": "CI pipeline", "evidence": f})
    for tool, kw in (("Ruff", "[tool.ruff"), ("Black", "[tool.black"), ("mypy", "[tool.mypy"), ("pytest", "[tool.pytest")):
        if kw in manifest_text:
            tools.append({"tool": tool, "purpose": "configured in pyproject.toml", "evidence": "pyproject.toml"})
    if any(f.startswith("tests/") or f.startswith("test_") for f in files) and not any(t["tool"] == "pytest" for t in tools):
        runner = "pytest" if "pytest" in low else "unittest (stdlib)"
        tools.append({"tool": runner, "purpose": "automated tests", "evidence": "tests/"})

    key_files = []
    for f in files:
        base = Path(f).name
        if base in FILE_PURPOSES and "/" not in f:
            key_files.append({"path": f, "purpose": FILE_PURPOSES[base]})
        elif f.endswith(".py") and not base.startswith("__"):
            doc = _py_docstring(_read(root, f))
            kind = "Test module" if (f.startswith("tests/") or base.startswith("test_")) else "Source module"
            key_files.append({"path": f, "purpose": f"{kind}. {doc}".strip()})
        elif f.startswith(".github/workflows/"):
            key_files.append({"path": f, "purpose": "CI workflow (devbot never edits these)."})
    return RepoReport(
        root=str(root), files=files, languages=dict(langs.most_common()), frameworks=frameworks,
        package_managers=pm, dev_tools=tools, key_files=key_files[:60],
        test_command=detect_test_command(root, files, manifest_text), tree=render_tree(files))


def read_source_context(root: Path, files: list[str], budget: int = 60000) -> dict[str, str]:
    """Collect text of source/test/config files for the LLM prompt, within a character budget."""
    out, used = {}, 0
    ordered = sorted(files, key=lambda f: (not f.endswith(tuple(LANGS)), len(f)))
    for f in ordered:
        if Path(f).suffix not in LANGS and Path(f).name not in FILE_PURPOSES:
            continue
        text = _read(root, f, 20000)
        if used + len(text) > budget:
            continue
        out[f] = text
        used += len(text)
    return out
