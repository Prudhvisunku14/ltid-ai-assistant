"""Reads REAL data for the Prompt A evaluation project from disk. Nothing here is invented:
files, diffs, tests, git history and the timeline all come from files produced by actual runs."""
import json
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from ..config import PROMPT_A, PREVIEW_URL
from .project_fs import ProjectFS

SRC = PROMPT_A / "source"
ORIG = PROMPT_A / "original"
REPORTS = PROMPT_A / "reports"
def category(rel: str) -> str:
    if rel.startswith("tests/"): return "test"
    if rel.endswith((".html", ".css", ".js", ".svg")) and not rel.startswith("tests"): return "frontend"
    if rel.endswith(".png"): return "evidence"
    return "config" if rel.startswith(".") or rel.endswith(".md") else "other"

# File browsing is shared with the other evaluation projects (see project_fs.py).
_fs = ProjectFS(SRC, ORIG, category)
_files, _read, _safe = _fs.files, _fs.read, _fs.safe
change_map, tree, file_content, raw_file, diffs = _fs.change_map, _fs.tree, _fs.file_content, _fs.raw_file, _fs.diffs

def _json(name: str):
    p = REPORTS / name
    if not p.exists():
        raise HTTPException(404, f"{name} not found; run scripts/run_evidence.py / export_git.py")
    return json.loads(p.read_text(encoding="utf-8"))

def tests() -> dict: return _json("test-results.json")
def timeline() -> list: return _json("timeline.json")
def analysis() -> dict: return _json("analysis.json")
def git() -> dict: return _json("git.json")

def screenshots() -> list[dict]:
    d = SRC / "screenshots"
    labels = {"desktop-1280-full": "Desktop 1280px — full page", "desktop-1280-fold": "Desktop 1280px — above the fold",
              "mobile-375-full": "Mobile 375px — full page", "mobile-375-fold": "Mobile 375px — above the fold",
              "mobile-375-menu-open": "Mobile 375px — menu open"}
    return [{"name": s.stem, "label": labels.get(s.stem, s.stem), "path": f"screenshots/{s.name}",
             "viewport": "375" if "mobile" in s.stem else "1280"} for s in sorted(d.glob("*.png"))] if d.exists() else []

def summary() -> dict:
    t = tests(); cm = change_map(); g = git()
    return {"tests_passed": t["totals"]["passed"], "tests_failed": t["totals"]["failed"],
            "files_added": sum(v == "added" for v in cm.values()), "files_modified": sum(v == "modified" for v in cm.values()),
            "files_deleted": sum(v == "deleted" for v in cm.values()), "commits": len(g["commits"]),
            "pushed": g["push"]["status"] == "pushed", "draft_pr_created": g["draft_pr"]["status"] == "created"}

def report_markdown() -> str:
    a, t, g, cm = analysis(), tests(), git(), change_map(); tl = timeline()
    L = ["# Evaluation Report — Prompt A: Website Development", "",
         f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} from real evidence files._", "",
         "## 1. Original requirements", f"Source: {a['requirements_source']['document']} — {a['requirements_source']['access']}", ""]
    L += [f"- **{r['area']}** — {r['text']}" for r in a["requirements"]]
    r = a["repository"]
    L += ["", "## 2. Existing repository analysis", f"- Repository: {r['url']}", f"- Import: {r['import_method']}", f"- Framework: {r['framework']}", f"- Backend: {r['backend']}", f"- Routes: {r['routes']}", "",
          "## 3. Missing functionality (in the starter)"]
    L += [f"- **{x['id']} {x['area']}**: {x['original']}" for x in a["requirements"]]
    L += ["", "## 4. Selected development tools and reasoning"] + [f"- **{x['name']}** — _{x['decision']}_: {x['reason']}" for x in a["tools"]]
    L += ["", "## 5. Implementation plan"] + [f"{i}. {s}" for i, s in enumerate(a["plan"], 1)]
    L += ["", "## 6. Files modified"] + [f"- {k}" for k, v in sorted(cm.items()) if v == "modified"]
    L += ["", "## 7. Files created"] + [f"- {k}" for k, v in sorted(cm.items()) if v == "added"]
    L += ["", "## 8. Tests executed and results"]
    for s in t["suites"]:
        p = sum(c["status"] == "passed" for c in s["cases"])
        L.append(f"- **{s['title']}** (`{s['command']}`, run {s['ran_at']}): {p}/{len(s['cases'])} passed, exit code {s['exit_code']}")
    L += [f"- Total: **{t['totals']['passed']} passed, {t['totals']['failed']} failed**", "",
          "## 9. Desktop verification", "Headless Chromium 1280px: portfolio renders ≥3 cards, nav visible, toggle hidden, no horizontal overflow, form validation flow. Screenshot evidence in Live Preview.", "",
          "## 10. Mobile verification", "Headless Chromium 375px: toggle visible and keyboard operable (Enter opens, Esc closes and returns focus), no horizontal overflow. Real devices not tested.", "",
          "## 11. Known limitations"] + [f"- {x}" for x in a["limitations"]]
    L += ["", "## 12. GitHub branch and PR details", f"- Repository: {g['repository_url']}", f"- Base branch: {g['base_branch']} (verified: {g['base_branch_verified']})",
          f"- Development branch: `{g['dev_branch']}` (local only)", f"- Push: **{g['push']['status']}** — {g['push']['reason']}",
          f"- Draft PR: **{g['draft_pr']['status']}** — {g['draft_pr']['reason']}", "- Local commits:"] + [f"  - `{c['hash']}` {c['subject']}" for c in g["commits"]]
    done = sum(s["status"] == "completed" for s in tl)
    L += ["", "## 13. Final completion status", f"{done}/{len(tl)} timeline steps fully completed; steps with status partial/blocked: " +
          ", ".join(f"#{s['n']} {s['title']} ({s['status']})" for s in tl if s["status"] != "completed") + ".",
          "Overall: website implementation and verification complete; GitHub publication **pending**."]
    return "\n".join(L)


SHOT_DIR = SRC / "screenshots"

def preview() -> dict:
    return {"url": PREVIEW_URL, "title": "Prompt A live preview",
            "start_hint": "docker compose up --build, or python -m http.server 8000 inside evaluation-projects/prompt-a-website/source"}
