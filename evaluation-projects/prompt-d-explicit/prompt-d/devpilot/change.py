"""D5 - Unseen change request: analyse -> plan -> implement -> test -> repair -> evidence (rollback on failure).
Works on ANY small Python project given an LLM. There is no prompt-specific logic in this file."""
import ast, difflib, json, shutil, sys, tempfile, datetime as dt
from pathlib import Path
from .common import run_cmd, extract_json
from .llm import LLMUnavailable

SKIP = {".git", "__pycache__", "evidence", ".pytest_cache", "node_modules"}
SYS_PLAN = ("You are a careful software engineer. Reply with JSON only: "
            '{"approach": str, "files_to_change": [str], "tests_to_add": [str], "risks": [str]}')
SYS_IMPL = ("You implement the approved plan. Reply with JSON only: "
            '{"files": [{"path": "relative/path.py", "content": "FULL new file content"}]}. '
            "Include tests for the new behaviour. Never modify paths outside the project.")


def project_files(root):
    root = Path(root)
    return sorted(p for p in root.rglob("*") if p.is_file() and not (set(p.relative_to(root).parts) & SKIP))


def analyse(root):
    root = Path(root); tree, symbols = [], {}
    for p in project_files(root):
        rel = str(p.relative_to(root)); tree.append(rel)
        if p.suffix == ".py":
            try:
                t = ast.parse(p.read_text())
                symbols[rel] = [f"{type(n).__name__}:{n.name}" for n in ast.walk(t)
                                if isinstance(n, (ast.FunctionDef, ast.ClassDef))]
            except SyntaxError as e:
                symbols[rel] = [f"SyntaxError line {e.lineno}"]
    return {"tree": tree, "symbols": symbols}


def run_tests(root, run=run_cmd):
    rc, o, e = run([sys.executable, "-m", "pytest", "-q", "-x"], timeout=300, cwd=str(root))
    if "No module named pytest" in e:
        rc, o, e = run([sys.executable, "-m", "unittest", "discover", "-v"], timeout=300, cwd=str(root))
        runner = "unittest"
    else:
        runner = "pytest"
    return {"runner": runner, "passed": rc == 0, "returncode": rc, "output": (o + e)[-3000:]}


def _safe(root, rel):
    p = (Path(root) / rel).resolve()
    if Path(root).resolve() not in p.parents or SKIP & set(p.relative_to(Path(root).resolve()).parts):
        raise ValueError(f"refusing path outside project or protected: {rel}")
    return p


def apply_edits(root, files):
    changed = []
    for f in files:
        p = _safe(root, f["path"]); p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(f["content"]); changed.append(f["path"])
    return changed


def snapshot(root):
    return {str(p.relative_to(root)): p.read_text(errors="replace") for p in project_files(root)}


def rollback(root, snap):
    for p in project_files(root):
        if str(p.relative_to(root)) not in snap: p.unlink()
    for rel, txt in snap.items():
        (Path(root) / rel).write_text(txt)


def diff(before, after):
    out = []
    for rel in sorted(set(before) | set(after)):
        a, b = before.get(rel, ""), after.get(rel, "")
        if a != b:
            out += list(difflib.unified_diff(a.splitlines(True), b.splitlines(True), f"a/{rel}", f"b/{rel}"))
    return "".join(out)


def run_change(root, request, llm, max_repairs=3, evidence_root=None, run=run_cmd):
    root = Path(root).resolve(); ts = dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    ev = Path(evidence_root or root.parent / "evidence") / ts; ev.mkdir(parents=True, exist_ok=True)
    rep = {"request": request, "root": str(root), "status": None, "attempts": []}
    snap = snapshot(root)
    rep["analysis"] = analyse(root)
    rep["baseline"] = run_tests(root, run)
    try:
        rep["plan"] = extract_json(llm.complete(SYS_PLAN, json.dumps({"request": request, **rep["analysis"],
                      "files": {k: v for k, v in snap.items() if k.endswith((".py", ".js", ".html", ".md"))}})))
        reply = llm.complete(SYS_IMPL, json.dumps({"request": request, "plan": rep["plan"], "files": snap}))
        for attempt in range(1, max_repairs + 2):
            files = extract_json(reply)["files"]
            changed = apply_edits(root, files)
            res = run_tests(root, run)
            rep["attempts"].append({"n": attempt, "changed": changed, "tests": res})
            if res["passed"]:
                rep["status"] = "success" if rep["baseline"]["passed"] else "success (baseline was already failing)"
                break
            if attempt > max_repairs:
                break
            reply = llm.complete(SYS_IMPL, json.dumps({"request": request, "plan": rep["plan"],
                                 "failure": "Tests failed. Fix the code (or the new tests if they are wrong).",
                                 "test_output": res["output"], "files": snapshot(root)}))
        if rep["status"] is None:
            rollback(root, snap); rep["status"] = "FAILED after repairs; project rolled back to original"
    except LLMUnavailable as e:
        rollback(root, snap); rep["status"] = f"NOT ATTEMPTED: {e}. No files were changed."
    except (ValueError, KeyError, json.JSONDecodeError) as e:
        rollback(root, snap); rep["status"] = f"FAILED: bad model output or unsafe edit ({e}); rolled back"
    after = snapshot(root); rep["diff"] = diff(snap, after) if not rep["status"].startswith(("FAILED", "NOT")) else ""
    (ev / "report.json").write_text(json.dumps(rep, indent=2)); (ev / "change.diff").write_text(rep["diff"])
    (ev / "report.md").write_text(render(rep)); rep["evidence_dir"] = str(ev)
    return rep


def render(r):
    L = ["# D5 Change request evidence", "", f"**Request:** {r['request']}", f"**Status:** {r['status']}", "",
         "## Analysis", f"Files: {', '.join(r['analysis']['tree'])}", "",
         f"Baseline tests ({r['baseline']['runner']}): {'PASS' if r['baseline']['passed'] else 'FAIL'}", ""]
    if "plan" in r:
        L += ["## Plan", f"Approach: {r['plan'].get('approach')}", f"Files to change: {r['plan'].get('files_to_change')}",
              f"Tests to add: {r['plan'].get('tests_to_add')}", f"Risks: {r['plan'].get('risks')}", ""]
    for a in r["attempts"]:
        L += [f"## Attempt {a['n']}: {'PASS' if a['tests']['passed'] else 'FAIL'} (changed {a['changed']})",
              "```", a["tests"]["output"][-800:], "```"]
    L += ["", "## Diff", "```diff", r.get("diff", ""), "```"]
    return "\n".join(L)
