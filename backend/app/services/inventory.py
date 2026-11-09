"""Reads the Inventory project (evaluation-projects/inventory-system) from disk. Nothing is invented: the file tree, diffs,
test results, git state and timeline come from the repository and from JSON files written by
evaluation-projects/inventory-system/scripts after real executions. The backend never runs project code."""
import ast, json, sys
from datetime import datetime, timezone
from fastapi import HTTPException
from ..config import INVENTORY, INVENTORY_PREVIEW_URL
from .project_fs import ProjectFS

SRC = INVENTORY / "inventory"           # the git repository (working tree)
ORIG = INVENTORY / "original"           # snapshot of the initial skeleton commit 65e4e4c
REPORTS = INVENTORY / "reports"
SHOT_DIR = REPORTS / "screenshots"


def category(rel: str) -> str:
    if rel.startswith("tests/"): return "test"
    if rel.startswith("static/"): return "frontend"
    if rel.startswith("app/"): return "backend"
    if rel.startswith("docs/"): return "docs"
    if rel.startswith(".github/"): return "config"
    return "config" if rel.startswith(".") or rel.endswith(".md") else "other"


_fs = ProjectFS(SRC, ORIG, category)
change_map, tree, file_content, raw_file, diffs = _fs.change_map, _fs.tree, _fs.file_content, _fs.raw_file, _fs.diffs


def _json(name: str):
    p = REPORTS / name
    if not p.exists():
        raise HTTPException(404, f"{name} not found; run evaluation-projects/inventory-system/scripts/run_evidence.py")
    return json.loads(p.read_text(encoding="utf-8"))


def tests() -> dict: return _json("test-results.json")
def timeline() -> list: return _json("timeline.json")
def analysis() -> dict: return _json("analysis.json")
def git() -> dict: return _json("git.json")


def preview() -> dict:
    return {"url": INVENTORY_PREVIEW_URL, "title": "Inventory Manager",
            "start_hint": "INVENTORY_PORT=8003 python -m app   (run inside evaluation-projects/inventory-system/inventory)"}


def screenshots() -> list[dict]:
    labels = {"main-list": "Inventory list with low-stock banner", "after-changes": "After edits, delete and import"}
    if not SHOT_DIR.exists(): return []
    return [{"name": s.stem, "label": labels.get(s.stem, s.stem), "path": f"screenshots/{s.name}", "viewport": "1100"}
            for s in sorted(SHOT_DIR.glob("*.png"))]


def detect_stack() -> list[str]:
    """Technology stack from the real imports in the project's Python code (not a hard-coded list)."""
    std = set(sys.stdlib_module_names)
    third, mods = set(), set()
    for p in (SRC / "app").rglob("*.py"):          # the application only; tests may use Playwright without it being part of the stack
        if set(p.relative_to(SRC).parts) & {".git", "__pycache__"}: continue
        try: t = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError): continue
        for n in ast.walk(t):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else ([n.module or ""] if isinstance(n, ast.ImportFrom) and n.level == 0 else [])
            for full in names:
                top = full.split(".")[0]; mods.add(full)
                if top and top not in std and top not in ("app", "tests"): third.add(top)
    exts = {p.suffix for p in SRC.rglob("*") if p.is_file() and ".git" not in p.parts}
    stack = [f"Python {sys.version_info.major}.{sys.version_info.minor}", "stdlib only" if not third else "Python: " + ", ".join(sorted(third))]
    if "sqlite3" in mods: stack.append("SQLite")
    if "http.server" in mods: stack.append("http.server JSON API")
    if {".html", ".js", ".css"} <= exts: stack.append("HTML/CSS/vanilla JS")
    if "unittest" in mods: stack.append("unittest")
    return stack


def build_status() -> str:
    try: b = tests().get("build")
    except HTTPException: return "unknown"
    return "passing" if b and b.get("status") == "passed" else "failing" if b else "unknown"


def test_status() -> str:
    try: t = tests()["totals"]
    except HTTPException: return "no results"
    return f"{t['passed']} passed, {t['failed']} failed"


def last_updated() -> str | None:
    try: return git()["commits"][0]["date"]
    except Exception: return None


def summary() -> dict:
    t = tests(); cm = change_map(); g = git()
    return {"tests_passed": t["totals"]["passed"], "tests_failed": t["totals"]["failed"],
            "files_added": sum(v == "added" for v in cm.values()), "files_modified": sum(v == "modified" for v in cm.values()),
            "files_deleted": sum(v == "deleted" for v in cm.values()), "commits": len(g["commits"]) + 1,
            "pushed": g["push"]["status"] == "pushed", "draft_pr_created": g["draft_pr"]["status"] == "created"}


def _t(headers, rows) -> list[str]:
    cell = lambda x: str(x).replace("|", "/").replace("\n", " ")   # noqa: E731
    return ["", "| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"] + \
           ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]


def report_markdown() -> str:
    a, t, g, cm = analysis(), tests(), git(), change_map()
    r = a["repository"]; tl = timeline()
    L = ["# Evaluation Report — Inventory Management System", "",
         f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} from real evidence files._", "",
         "## 1. Original evaluation task",
         f"Source: {a['requirements_source']['document']} — {a['requirements_source']['access']}", ""]
    L += [f"- **{x['id']} {x['area']}** — {x['text']}" for x in a["requirements"]]
    L += ["", "## 2. Repository analysis", f"- Repository: {r['slug']}", f"- Import: {r['import_method']}",
          f"- Base branch: `{r['base_branch']}` — {r['base_branch_note']}", f"- Framework: {r['framework']}", f"- Backend: {r['backend']}", f"- Routes: {r['routes']}", "",
          "### Existing issues observed"]
    L += _t(["ID", "Area", "Finding", "Observed"], [(e["id"], e["area"], e["finding"], e["observed"]) for e in a.get("existing_issues", [])])
    L += ["", "### Requirement coverage"] + _t(["ID", "Area", "Result", "Evidence"], [(x["id"], x["area"], x["result"], x["evidence"]) for x in a["requirements"]])
    L += ["", "## 3. Tools and reasons"] + [f"- **{x['name']}** — _{x['decision']}_: {x['reason']}" for x in a["tools"]]
    env = a.get("environment")
    if env: L += ["", "Detected on the build machine: " + "; ".join(f"{k}: {v if v else 'not installed'}" for k, v in env.items()) + "."]
    L += ["", "## 4. Implementation plan"] + [f"{p['n']}. **{p['task']}** — {p['status']}. Files: {p['files']}. Evidence: {p['evidence'] or '—'}" for p in a["plan"]]
    L += ["", "## 5. Test results", f"Total: **{t['totals']['passed']} passed, {t['totals']['failed']} failed**.", ""]
    for s in t["suites"]:
        p = sum(c["status"] == "passed" for c in s["cases"])
        L.append(f"- **{s['title']}** (`{s['command']}`, run {s['ran_at']}): {p}/{len(s['cases'])} passed, exit code {s['exit_code']}")
    L += ["", "## 6. Modified files"]
    L += _t(["File", "Status"], [(k, v) for k, v in sorted(cm.items()) if v != "unchanged"])
    L += ["", "## 7. GitHub / repository status", f"- Development branch: `{g['dev_branch']}` (local repository)",
          f"- Push: **{g['push']['status']}** — {g['push']['reason']}", f"- Draft PR: **{g['draft_pr']['status']}** — {g['draft_pr']['reason']}",
          f"- Uncommitted changes at export: {', '.join(g.get('uncommitted_changes', [])) or 'none'}", "- Local commits:"] + \
         [f"  - `{c['hash']}` {c['subject']}" for c in g["commits"]]
    L += ["", "## 8. Limitations"] + [f"- {x}" for x in a["limitations"]]
    done = sum(s["status"] == "completed" for s in tl)
    L += ["", "## 9. Final completion status", f"{done}/{len(tl)} timeline steps completed; not completed: " +
          (", ".join(f"#{s['n']} {s['title']} ({s['status']})" for s in tl if s["status"] != "completed") or "none") + ".",
          "Overall: the application is implemented and tested locally; GitHub publication is **pending** (no remote configured)."]
    return "\n".join(L)
