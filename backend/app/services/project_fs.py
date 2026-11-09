"""Read-only view of a project's `source/` vs `original/` folders: file tree, file contents, change map and unified
diffs. Shared by every evaluation project (Prompt A, Prompt B ...). Nothing here executes project code."""
import difflib
from pathlib import Path
from typing import Callable
from fastapi import HTTPException

SKIP_DIRS = {".git", "node_modules", "__pycache__", ".pytest_cache", ".venv"}
LANG = {".html": "xml", ".css": "css", ".js": "javascript", ".py": "python", ".md": "markdown",
        ".json": "json", ".svg": "xml", ".txt": "plaintext", ".yml": "yaml", ".yaml": "yaml", ".csv": "plaintext"}
BINARY_EXT = {".png", ".jpg", ".jpeg", ".gif", ".ico", ".webp", ".pyc", ".bundle"}


class ProjectFS:
    def __init__(self, src: Path, orig: Path, category: Callable[[str], str]):
        self.src, self.orig, self.category = src, orig, category

    # ---------------------------------------------------------------- helpers
    @staticmethod
    def files(base: Path) -> dict[str, Path]:
        out = {}
        if not base.exists(): return out
        for p in sorted(base.rglob("*")):
            if p.is_file() and not (set(p.relative_to(base).parts) & SKIP_DIRS) and p.suffix != ".pyc":
                out[p.relative_to(base).as_posix()] = p
        return out

    @staticmethod
    def read(p: Path) -> str | None:
        if p.suffix.lower() in BINARY_EXT: return None
        try: return p.read_text(encoding="utf-8")
        except UnicodeDecodeError: return None

    @staticmethod
    def safe(base: Path, rel: str) -> Path:
        p = (base / rel).resolve()
        if base.resolve() not in p.parents and p != base.resolve():
            raise HTTPException(400, "invalid path")
        return p

    @staticmethod
    def _same(a: Path, b: Path) -> bool:
        # compare ignoring line endings so a CRLF/LF difference alone is not reported as a modification
        return a.read_bytes().replace(b"\r\n", b"\n") == b.read_bytes().replace(b"\r\n", b"\n")

    # ---------------------------------------------------------------- views
    def change_map(self) -> dict[str, str]:
        a, b = self.files(self.orig), self.files(self.src)
        m = {}
        for r in b: m[r] = "unchanged" if r in a and self._same(a[r], b[r]) else ("modified" if r in a else "added")
        for r in a:
            if r not in b: m[r] = "deleted"
        return m

    def tree(self) -> dict:
        cm = self.change_map(); root = {"name": "source", "path": "", "type": "dir", "children": []}
        for rel in sorted(k for k in cm if cm[k] != "deleted"):
            node = root; parts = rel.split("/")
            for i, part in enumerate(parts):
                path = "/".join(parts[: i + 1])
                if i == len(parts) - 1:
                    node["children"].append({"name": part, "path": rel, "type": "file", "category": self.category(rel), "change": cm[rel], "children": []})
                else:
                    nxt = next((c for c in node["children"] if c["type"] == "dir" and c["name"] == part), None)
                    if not nxt:
                        nxt = {"name": part, "path": path, "type": "dir", "children": []}; node["children"].append(nxt)
                    node = nxt
        def sort(n):
            n["children"].sort(key=lambda c: (c["type"] != "dir", c["name"].lower()))
            for c in n["children"]: sort(c)
        sort(root); return root

    def file_content(self, rel: str) -> dict:
        p = self.safe(self.src, rel)
        if not p.is_file(): raise HTTPException(404, "file not found")
        cm = self.change_map().get(rel, "unchanged"); text = self.read(p)
        op = self.safe(self.orig, rel); orig = self.read(op) if op.is_file() else None
        return {"path": rel, "language": LANG.get(p.suffix.lower(), "plaintext"), "content": text or "",
                "original": orig, "binary": text is None, "change": cm}

    def raw_file(self, rel: str) -> Path:
        p = self.safe(self.src, rel)
        if not p.is_file(): raise HTTPException(404, "file not found")
        return p

    def diffs(self) -> list[dict]:
        out = []
        for rel, st in sorted(self.change_map().items()):
            if st == "unchanged": continue
            a = self.read(self.orig / rel) if (self.orig / rel).is_file() else ""
            b = self.read(self.src / rel) if (self.src / rel).is_file() else ""
            if a is None or b is None:
                out.append({"path": rel, "status": st, "additions": 0, "deletions": 0, "diff": "Binary file"}); continue
            a, b = a.replace("\r\n", "\n"), b.replace("\r\n", "\n")
            d = list(difflib.unified_diff(a.splitlines(), b.splitlines(), f"a/{rel}", f"b/{rel}", lineterm="", n=3))
            out.append({"path": rel, "status": st, "additions": sum(1 for l in d if l.startswith("+") and not l.startswith("+++")),
                        "deletions": sum(1 for l in d if l.startswith("-") and not l.startswith("---")), "diff": "\n".join(d)})
        return out
