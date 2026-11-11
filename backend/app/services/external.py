"""Shared reader for the uploaded evaluation projects (appointment booking, expense system, support tickets).

Each project has:
  * its code folder (the project root, read-only for the dashboard), and
  * an evidence folder  <project>/reports/  written by evaluation-projects/scripts/collect_external.py after real runs
    (test-results.json, live-check.json, timeline.json, git.json, analysis.json, screenshots/).

Nothing is invented: a missing evidence file is reported as 404, and the code is only read, never executed.
There is no baseline snapshot for these uploads, so every file is shown as unchanged and there are no diffs.
"""
import ast, json, sys
from datetime import datetime, timezone
from pathlib import Path
from fastapi import HTTPException
from ..config import EVAL_ROOT
from .project_fs import ProjectFS


def category(rel: str) -> str:
    if rel.startswith("tests/") or "/tests/" in rel or rel.startswith("test_"): return "test"
    if rel.endswith((".html", ".css", ".js")) or "/static/" in rel: return "frontend"
    if rel.endswith(".py"): return "backend"
    if rel.endswith((".db", ".sqlite")): return "data"
    return "config" if rel.startswith(".") or rel.endswith((".md", ".txt", ".ini", ".toml", ".yml", ".yaml", ".example")) or rel in ("Dockerfile", "requirements.txt") else "other"


# Per-project configuration. Ports are fixed so each live app has its own address next to the other projects.
PROJECTS = {
    "appointment-booking": {
        "outer": EVAL_ROOT / "appointment-booking", "root": EVAL_ROOT / "appointment-booking" / "appointment-booking",
        "name": "Appointment Booking System", "client": "Kaizen Consulting", "category": "Business Application / Scheduling",
        "description": "Customers book, view, modify and cancel 30-minute appointments (Mon–Fri, 09:00–17:00 JST). Admins get a weekly calendar. Double bookings are prevented by the database.",
        "port": 8004, "preview_env": "APPOINTMENT_PREVIEW_URL", "launch": "Launch Booking App", "repo": None,
        "start_hint": "cd evaluation-projects/appointment-booking/appointment-booking && PORT=8004 python run.py",
    },
    "expense-system": {
        "outer": EVAL_ROOT / "expense-system", "root": EVAL_ROOT / "expense-system" / "expense-system",
        "name": "Expense Management & Approval System", "client": "Northstar Services (fictional)", "category": "Business Application / Finance",
        "description": "Employees register expenses; managers and finance approve or reject, every decision is kept in a history, and monthly totals can be exported to CSV under the company expense policy.",
        "port": 8005, "preview_env": "EXPENSE_PREVIEW_URL", "launch": "Launch Expense App", "repo": None,
        "start_hint": "cd evaluation-projects/expense-system/expense-system && PORT=8005 python run.py",
    },
    "support-ticket-system": {
        "outer": EVAL_ROOT / "support-ticket-system", "root": EVAL_ROOT / "support-ticket-system" / "support-ticket-system",
        "name": "AI-Supported Support Ticket System", "client": None, "category": "Business Application / Customer Support",
        "description": "Users submit tickets; a classifier (GPT when an API key is set, otherwise a free rule-based fallback) suggests category and priority with reasoning. Staff can correct everything and move tickets through a workflow.",
        "port": 8006, "preview_env": "SUPPORT_PREVIEW_URL", "launch": "Launch Ticket App", "repo": None,
        "start_hint": "cd evaluation-projects/support-ticket-system/support-ticket-system && uvicorn app.main:app --port 8006",
    },
    "prompt-c-rag": {
        "outer": EVAL_ROOT / "ltid-ai-competition-rag-final", "root": EVAL_ROOT / "ltid-ai-competition-rag-final",
        "name": "LTID AI Competition – RAG", "client": "Northstar Services (fictional)", "category": "AI / Retrieval-Augmented Generation",
        "description": "Answers questions about company policy documents using only what the documents say. It finds passages with BM25 keyword retrieval, quotes them with file and line citations, prefers the current version of a policy over a superseded one, and says so when the documents do not support an answer. Includes a web interface with document upload; an optional LLM can rephrase from the retrieved evidence. No embeddings or vector database.",
        "port": 8008, "preview_env": "RAG_PREVIEW_URL", "launch": "Launch RAG App", "repo": None,
        "import_note": "Supplied project folder with its own local git repository (1 commit, no remote). The web interface in web_demo/ was added next to it by this integration. Tests and the live app were run here; LLM rephrasing was never run against a live model",
        "start_hint": "cd evaluation-projects/ltid-ai-competition-rag-final/web_demo && PORT=8008 python server.py",
    },
    "docchange": {
        "outer": EVAL_ROOT / "docchange", "root": EVAL_ROOT / "docchange" / "docchange",
        "name": "Document Change Monitoring System", "client": None, "category": "Requirements Management / Document Control",
        "description": "Compares two versions of a document and lists what changed (verified by exact text comparison), flags changes that may affect requirements (labelled as unverified rule-based interpretation), and keeps a reviewable history.",
        "port": 8007, "preview_env": "DOCCHANGE_PREVIEW_URL", "launch": "Launch Monitor", "repo": None,
        "start_hint": "cd evaluation-projects/docchange/docchange && PORT=8007 python run.py",
    },
}

PKG_LABEL = {"flask": "Flask", "fastapi": "FastAPI", "uvicorn": "Uvicorn", "openai": "OpenAI SDK (optional)",
             "python-dotenv": "python-dotenv", "tzdata": "tzdata", "pytest": "pytest", "httpx": "httpx", "pydantic": "Pydantic"}


class ExternalProject:
    def __init__(self, key: str, cfg: dict):
        self.key, self.cfg = key, cfg
        self.outer, self.root = cfg["outer"], cfg["root"]
        self.REPORTS = self.outer / "reports"
        self.SHOT_DIR = self.REPORTS / "screenshots"
        # no baseline snapshot exists for these uploads: the code is compared with itself (no changes shown)
        self._fs = ProjectFS(self.root, self.root, category)
        self.change_map = self._fs.change_map
        self.tree = self._fs.tree
        self.file_content = self._fs.file_content
        self.raw_file = self._fs.raw_file
        self.diffs = self._fs.diffs

    # ----------------------------------------------------------------- evidence files
    def _json(self, name: str):
        p = self.REPORTS / name
        if not p.exists():
            raise HTTPException(404, f"{name} not found; run evaluation-projects/scripts/collect_external.py {self.key}")
        return json.loads(p.read_text(encoding="utf-8"))

    def tests(self) -> dict: return self._json("test-results.json")
    def timeline(self) -> list: return self._json("timeline.json")
    def analysis(self) -> dict: return self._json("analysis.json")
    def git(self) -> dict: return self._json("git.json")
    def live_check(self) -> dict: return self._json("live-check.json")

    # ----------------------------------------------------------------- dashboard views
    def preview(self) -> dict:
        import os
        url = os.getenv(self.cfg["preview_env"], f"http://localhost:{self.cfg['port']}")
        return {"url": url, "title": self.cfg["name"], "start_hint": self.cfg["start_hint"]}

    def screenshots(self) -> list[dict]:
        if not self.SHOT_DIR.exists(): return []
        return [{"name": s.stem, "label": s.stem.replace("-", " ").capitalize(), "path": f"screenshots/{s.name}", "viewport": "1280"}
                for s in sorted(self.SHOT_DIR.glob("*.png"))]

    def build_status(self) -> str:
        try: b = self.tests().get("build")
        except HTTPException: return "unknown"
        return "passing" if b and b.get("status") == "passed" else "failing" if b else "unknown"

    def test_status(self) -> str:
        try: t = self.tests()["totals"]
        except HTTPException: return "no results"
        return f"{t['passed']} passed, {t['failed']} failed"

    def last_updated(self) -> str | None:
        try: return self.tests()["generated_at"]
        except HTTPException: return None

    def detect_stack(self) -> list[str]:
        """Stack from the project's requirements.txt and its Python imports (not a hard-coded list)."""
        stack = ["Python 3.12"]
        req = self.root / "requirements.txt"
        if req.exists():
            for line in req.read_text(encoding="utf-8").splitlines():
                name = line.split("#")[0].strip().split(">")[0].split("=")[0].split("[")[0].strip().lower()
                if name in PKG_LABEL: stack.append(PKG_LABEL[name])
        std = set(sys.stdlib_module_names); mods = set()
        for p in self.root.rglob("*.py"):
            if "__pycache__" in p.parts: continue
            try: t = ast.parse(p.read_text(encoding="utf-8"))
            except (SyntaxError, UnicodeDecodeError): continue
            for n in ast.walk(t):
                if isinstance(n, ast.Import): mods.update(a.name.split(".")[0] for a in n.names)
                elif isinstance(n, ast.ImportFrom) and n.level == 0 and n.module: mods.add(n.module.split(".")[0])
        if "sqlite3" in mods: stack.append("SQLite")
        if any(self.root.glob("static")) or any(self.root.glob("*/static")) or any(self.root.glob("*/*/static")): stack.append("HTML/CSS/vanilla JS")
        if "pytest" in mods: stack.append("pytest")
        elif "unittest" in mods: stack.append("unittest")
        if any("bm25" in p.read_text(encoding="utf-8", errors="ignore").lower() for p in self.root.rglob("*.py") if "__pycache__" not in p.parts): stack.append("BM25 retrieval")
        seen = []
        for s in stack:
            if s not in seen: seen.append(s)
        return seen

    def summary(self) -> dict:
        t = self.tests()["totals"]
        return {"tests_passed": t["passed"], "tests_failed": t["failed"], "files_added": 0, "files_modified": 0, "files_deleted": 0,
                "commits": 0, "pushed": False, "draft_pr_created": False}

    def report_markdown(self) -> str:
        a, t, tl = self.analysis(), self.tests(), self.timeline()
        L = [f"# Evaluation Report — {self.cfg['name']}", "",
             f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} from the evidence files in `{self.outer.name}/reports/`._", "",
             f"Client: {self.cfg['client'] or 'not stated'}", "",
             "## 1. Original task", f"Source: {a['requirements_source']['document']} — {a['requirements_source']['access']}", ""]
        L += [f"- **{x['id']} {x['area']}** — {x['text']}" for x in a["requirements"]]
        r = a["repository"]
        L += ["", "## 2. Repository analysis", f"- Location: {r['slug']}", f"- Import: {r['import_method']}",
              f"- Framework: {r['framework']}", f"- Backend: {r['backend']}", f"- Routes: {r['routes']}"]
        L += ["", "## 3. Tools and reasons"] + [f"- **{x['name']}** — _{x['decision']}_: {x['reason']}" for x in a["tools"]]
        L += ["", "## 4. Implementation plan"] + [f"{p['n']}. **{p['task']}** — {p['status']}. Evidence: {p['evidence'] or '—'}" for p in a["plan"]]
        L += ["", "## 5. Test results", f"Total: **{t['totals']['passed']} passed, {t['totals']['failed']} failed**."]
        for s in t["suites"]:
            L.append(f"- **{s['title']}** (`{s['command']}`, run {s['ran_at']}): {s['summary_line'] or '—'}; exit code {s['exit_code']}; parsed {s.get('parsed_count', '?')} of {s.get('reported_count', '?')} tests")
        L += ["", f"Compile check: {t.get('build', {}).get('status', 'unknown')} — {t.get('build', {}).get('output', '')}"]
        try:
            lc = self.live_check()
            L += ["", "## 6. Live application", f"- {lc['url']} — reachable: **{lc['reachable']}**, HTTP {lc.get('http_status')}, screenshot `{lc.get('screenshot')}`"]
        except HTTPException:
            pass
        L += ["", "## 7. Source control", f"- {self.git().get('base_branch_evidence', 'not recorded')}", f"- {self.git()['push']['reason']}"]
        L += ["", "## 8. Limitations"] + [f"- {x}" for x in a["limitations"]]
        done = sum(s["status"] == "completed" for s in tl)
        L += ["", "## 9. Completion status", f"{done}/{len(tl)} timeline steps completed; not completed: " +
              (", ".join(f"#{s['n']} {s['title']} ({s['status']})" for s in tl if s["status"] != "completed") or "none") + "."]
        return "\n".join(L)


_instances = {k: ExternalProject(k, cfg) for k, cfg in PROJECTS.items()}
