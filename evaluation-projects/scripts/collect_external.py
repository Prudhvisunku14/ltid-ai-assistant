"""Collects REAL evidence for the three uploaded projects (appointment booking, expense system, support tickets).

    .venv\\Scripts\\python.exe evaluation-projects/scripts/collect_external.py [project-id ...]

For each project it:
  1. runs the project's own pytest suite with -v and parses every test result (reports/test-results.json);
  2. compiles every Python file in the project;
  3. starts the app on its dedicated port with a temporary database, waits until it answers, captures a screenshot of
     the home page with Microsoft Edge (Playwright), then stops the app (reports/screenshots/, reports/live-check.json);
  4. records git state (these uploads are not git repositories, so that is recorded as such);
  5. writes reports/timeline.json from the evidence above.

analysis.json (requirements, tools, limitations) is written by hand from each project's own README and kept in the
project's reports folder; this script never edits it.
Nothing is typed in: every number comes from the runs.
"""
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys
import tempfile
import time
import urllib.request

EVAL = pathlib.Path(__file__).resolve().parents[1]
PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")  # noqa: E731

PROJECTS = {
    "appointment-booking": {
        "outer": EVAL / "appointment-booking", "root": EVAL / "appointment-booking" / "appointment-booking",
        "port": 8004, "title": "Appointment booking — Kaizen Consulting",
        "start": lambda db: ([PY, "run.py"], {"HOST": "127.0.0.1", "PORT": "8004", "BOOKING_DB": db}),
        "db_env": "BOOKING_DB", "db_name": "appointments.db",
    },
    "expense-system": {
        "outer": EVAL / "expense-system", "root": EVAL / "expense-system" / "expense-system",
        "port": 8005, "title": "Expense management & approval — Northstar Services",
        "start": lambda db: ([PY, "run.py"], {"HOST": "127.0.0.1", "PORT": "8005", "EXPENSE_DB": db, "SEED_DEMO": "1"}),
        "db_env": "EXPENSE_DB", "db_name": "expenses.db",
    },
    "support-ticket-system": {
        "outer": EVAL / "support-ticket-system", "root": EVAL / "support-ticket-system" / "support-ticket-system",
        "port": 8006, "title": "AI-supported support ticket system",
        "start": lambda db: ([PY, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", "8006"], {"DATABASE_PATH": db}),
        "db_env": "DATABASE_PATH", "db_name": "tickets.db",
    },
    "prompt-c-rag": {
        "outer": EVAL / "ltid-ai-competition-rag-final", "root": EVAL / "ltid-ai-competition-rag-final",
        "port": 8008, "title": "LTID AI Competition - RAG", "runner": "unittest-multi",
        "suites": [("project-tests", "RAG project tests (rag_app)", EVAL / "ltid-ai-competition-rag-final" / "prompt-c-rag"),
                   ("web-tests", "Web interface tests (web_demo)", EVAL / "ltid-ai-competition-rag-final" / "web_demo")],
        "start_cwd": EVAL / "ltid-ai-competition-rag-final" / "web_demo",
        "git_repo": EVAL / "ltid-ai-competition-rag-final" / "prompt-c-rag",
        "ui_check": EVAL / "ltid-ai-competition-rag-final" / "web_demo" / "ui_check.py",
        "start": lambda db: ([PY, "server.py"], {"HOST": "127.0.0.1", "PORT": "8008"}),
        "db_env": "none", "db_name": "unused.db",
    },
    "github-dev-automation": {
        "outer": EVAL / "GitHub Development Automation System", "root": EVAL / "GitHub Development Automation System",
        "port": 8009, "title": "devbot - GitHub Development Automation System", "runner": "unittest-multi",
        "suites": [("project-tests", "devbot project tests", EVAL / "GitHub Development Automation System" / "GitHub Development Automation System"),
                   ("web-tests", "Web interface tests (web_demo)", EVAL / "GitHub Development Automation System" / "web_demo")],
        "start_cwd": EVAL / "GitHub Development Automation System" / "web_demo",
        "ui_check": EVAL / "GitHub Development Automation System" / "web_demo" / "ui_check.py",
        "start": lambda db: ([PY, "server.py"], {"HOST": "127.0.0.1", "PORT": "8009"}),
        "db_env": "none", "db_name": "unused.db",
    },
    "docchange": {
        "outer": EVAL / "docchange", "root": EVAL / "docchange" / "docchange",
        "port": 8007, "title": "Document change monitoring system", "runner": "unittest",
        "start": lambda db: ([PY, "run.py"], {"HOST": "127.0.0.1", "PORT": "8007", "HISTORY_DB": db}),
        "db_env": "HISTORY_DB", "db_name": "history.db",
    },
}


def run(cmd, cwd, timeout=600):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def pytest_suite(root):
    t0 = now()
    code, out = run([PY, "-m", "pytest", "-v", "-p", "no:cacheprovider"], root)
    cases = []
    # node ids may contain spaces inside [...] parameters, so match up to the status word that ends the line's id
    for m in re.finditer(r"^(\S+?\.py::.+?) (PASSED|FAILED|ERROR|SKIPPED|XFAIL|XPASS)(?= )", out, re.M):
        nodeid, res = m.groups()
        cases.append({"name": nodeid.split("::", 1)[1], "class": nodeid.split("::")[0], "status": {"PASSED": "passed", "SKIPPED": "skipped"}.get(res, "failed")})
    summary = re.search(r"=+ (.*?) in [\d.]+s", out)
    summary_line = summary.group(1) if summary else ""
    # every collected test must appear in the parsed list; a mismatch is recorded, never hidden
    counted = sum(int(n) for n in re.findall(r"(\d+) (?:passed|failed|error|errors|skipped|xfailed|xpassed)", summary_line))
    return {"id": "pytest", "title": "Automated test suite (pytest)", "command": "python -m pytest -v", "ran_at": t0,
            "exit_code": code, "cases": cases, "output_tail": out.strip().splitlines()[-3:],
            "summary_line": summary_line, "parsed_count": len(cases), "reported_count": counted,
            "parse_complete": len(cases) == counted}


def unittest_suite(root, sid="unittest", title="Automated test suite (unittest)"):
    """Runs the project's unittest suite (standard library) and parses every result line."""
    t0 = now()
    code, out = run([PY, "-m", "unittest", "discover", "-s", "tests", "-v"], root)
    cases = []
    # a test with a docstring prints "name (id)" and then "<docstring first line> ... ok" on the NEXT line
    for m in re.finditer(r"^(test\S*) \(([\w.]+)\)(?:\n(?!test)[^\n]*?)? \.\.\. (ok|FAIL|ERROR|skipped.*)$", out, re.M):
        name, ident, res = m.groups()
        cases.append({"name": name, "class": ident, "status": "passed" if res == "ok" else "skipped" if res.startswith("skipped") else "failed"})
    ran = re.search(r"Ran (\d+) tests?", out)
    reported = int(ran.group(1)) if ran else 0
    summary_line = (out.strip().splitlines() or [""])[-1]
    return {"id": sid, "title": title, "command": "python -m unittest discover -s tests -v", "ran_at": t0,
            "exit_code": code, "cases": cases, "output_tail": out.strip().splitlines()[-3:],
            "summary_line": (f"{reported} tests ran; " + ("OK" if code == 0 else "FAILED")),
            "parsed_count": len(cases), "reported_count": reported, "parse_complete": len(cases) == reported}


def nested_git(repo):
    """Real git state of a project that carries its own repository (read-only git commands)."""
    def g(*a):
        return subprocess.run(["git", *a], cwd=repo, capture_output=True, text=True, encoding="utf-8", errors="replace").stdout.strip()
    commits = [dict(zip(("hash", "author", "date", "subject"), l.split(""))) for l in g("log", "--format=%h%an%aI%s").splitlines()]
    remotes = g("remote")
    return {"exported_at": now(), "repository_url": g("remote", "get-url", "origin") or None, "base_branch": None, "base_branch_verified": False,
            "base_branch_evidence": "no remote configured; the repository exists only on this machine" if not remotes else "remote configured",
            "import_kind": "Project folder with its own local git repository (1 commit, no starter baseline commit and no remote)" if len(commits) == 1 else "Project folder with its own local git repository",
            "dev_branch": g("rev-parse", "--abbrev-ref", "HEAD"), "baseline_commit": {}, "commits": commits,
            "uncommitted_changes": g("status", "--short").splitlines(),
            "push": {"status": "not_pushed", "reason": "No remote is configured in the project's repository, so nothing has been pushed."},
            "draft_pr": {"status": "not_created", "url": None, "reason": "Requires a pushed branch."}}


def compile_check(root):
    """Compiles every project .py file IN MEMORY (no .pyc files are written into the project)."""
    t0 = now()
    checker = "\n".join([
        "import pathlib, sys",
        "bad = []; n = 0",
        "for p in pathlib.Path('.').rglob('*.py'):",
        "    if '__pycache__' in p.parts: continue",
        "    n += 1",
        "    try: compile(p.read_bytes(), str(p), 'exec')",
        "    except SyntaxError as e: bad.append(f'{p}: {e}')",
        "print(f'compiled {n} files OK' if not bad else 'ERRORS: ' + '; '.join(bad))",
        "sys.exit(1 if bad else 0)",
    ])
    code, out = run([PY, "-c", checker], root)
    return {"status": "passed" if code == 0 else "failed", "command": "compile() every .py file in the project, in memory",
            "ran_at": t0, "output": out.strip()[-200:]}


def live_check_and_screenshot(name, cfg, shots_dir):
    tmpdir = tempfile.mkdtemp(prefix=f"{name}-")
    db = str(pathlib.Path(tmpdir) / cfg["db_name"])
    cmd, extra = cfg["start"](db)
    proc = subprocess.Popen(cmd, cwd=cfg.get("start_cwd", cfg["root"]), env={**ENV, **extra}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{cfg['port']}/"
    result = {"url": url, "started_at": now(), "reachable": False, "http_status": None, "screenshot": None, "error": None}
    try:
        for _ in range(60):
            try:
                with urllib.request.urlopen(url, timeout=2) as r:
                    result["http_status"] = r.status; result["reachable"] = True; break
            except Exception as exc:
                result["error"] = str(exc)[:120]; time.sleep(0.5)
        if result["reachable"]:
            from playwright.sync_api import sync_playwright
            with sync_playwright() as p:
                try:
                    b = p.chromium.launch(channel="msedge")
                except Exception:
                    b = p.chromium.launch()
                pg = b.new_page(viewport={"width": 1280, "height": 860})
                pg.goto(url, wait_until="networkidle"); pg.wait_for_timeout(500)
                shot = shots_dir / f"{name}-home.png"
                pg.screenshot(path=str(shot), full_page=True)
                result["screenshot"] = f"screenshots/{shot.name}"
                result["page_title"] = pg.title()
                b.close()
    except Exception as exc:
        result["error"] = f"{type(exc).__name__}: {exc}"[:200]
    finally:
        proc.terminate()
        try: proc.wait(timeout=5)
        except subprocess.TimeoutExpired: proc.kill()
    result["stopped_at"] = now()
    return result


def main(names):
    for name in names:
        cfg = PROJECTS[name]
        reports = cfg["outer"] / "reports"; shots = reports / "screenshots"
        reports.mkdir(exist_ok=True); shots.mkdir(exist_ok=True)
        print(f"== {name}", flush=True)
        if cfg.get("runner") == "unittest-multi":
            suites = [unittest_suite(path, sid, title) for sid, title, path in cfg["suites"]]
        elif cfg.get("runner") == "unittest":
            suites = [unittest_suite(cfg["root"])]
        else:
            suites = [pytest_suite(cfg["root"])]
        if cfg.get("ui_check"):                       # real-browser checks of the web interface (Playwright + Edge)
            t_ui = now()
            ui_code, ui_out = run([PY, str(cfg["ui_check"])], cfg["root"], timeout=900)
            try:
                ui_cases = json.loads(ui_out.strip().splitlines()[-1])["cases"]
            except Exception:
                ui_cases = [{"name": "ui_check_could_not_run", "class": "BrowserUI", "status": "failed", "detail": ui_out[-200:]}]
            ui_passed = sum(c["status"] == "passed" for c in ui_cases)
            suites.append({"id": "browser-ui", "title": "Browser UI checks (Playwright + Microsoft Edge)", "command": "python web_demo/ui_check.py",
                           "ran_at": t_ui, "exit_code": ui_code, "cases": [{k: v for k, v in c.items() if k != "detail"} for c in ui_cases],
                           "output_tail": [f"{c['status']}: {c['name']}" + (f" - {c['detail']}" if c.get("detail") else "") for c in ui_cases if c["status"] != "passed"][:6] or ["all checks passed"],
                           "summary_line": f"{ui_passed} of {len(ui_cases)} checks passed", "parsed_count": len(ui_cases), "reported_count": len(ui_cases), "parse_complete": True})
        suite = suites[0]
        suites_ok = all(s["exit_code"] == 0 and s.get("parse_complete", True) for s in suites)
        build = compile_check(cfg["root"])
        totals = {"passed": sum(c["status"] == "passed" for s in suites for c in s["cases"]), "failed": sum(c["status"] == "failed" for s in suites for c in s["cases"])}
        (reports / "test-results.json").write_text(json.dumps({"generated_at": now(), "build": build, "suites": suites, "totals": totals}, indent=2), encoding="utf-8")
        live = live_check_and_screenshot(name, cfg, shots)
        (reports / "live-check.json").write_text(json.dumps(live, indent=2), encoding="utf-8")
        # git: these are uploads, not repositories
        top = subprocess.run(["git", "rev-parse", "--show-toplevel"], cwd=cfg["root"], capture_output=True, text=True).stdout.strip()
        is_git = bool(top) and pathlib.Path(top).resolve() == pathlib.Path(cfg["root"]).resolve()      # the project's OWN repository, not the platform repo around it
        git = {"exported_at": now(), "repository_url": None, "base_branch": None, "base_branch_verified": False,
               "base_branch_evidence": "not a git repository (uploaded folder)" if not is_git else "git repository detected",
               "import_kind": "Uploaded folder (no version-control history and no baseline snapshot available)",
               "dev_branch": None, "baseline_commit": {}, "commits": [], "uncommitted_changes": [],
               "push": {"status": "not_pushed", "reason": "Not a git repository and no remote; nothing to push."},
               "draft_pr": {"status": "not_created", "url": None, "reason": "Requires a pushed branch."}}
        if cfg.get("git_repo"):
            git = nested_git(cfg["git_repo"])
        (reports / "git.json").write_text(json.dumps(git, indent=2), encoding="utf-8")
        # timeline from the evidence just collected
        tl = [
            {"n": 1, "title": "Project uploaded and inspected", "status": "completed", "timestamp": None,
             "description": "Folder structure, README, requirements and source files read.", "output": "", "evidence": "analysis.json"},
            {"n": 2, "title": "Automated test suite executed", "status": "completed" if suites_ok else "blocked",
             "timestamp": suite["ran_at"], "description": "The project's own test suite(s) run in this environment.",
             "output": "; ".join(f"{x['id']}: {x['summary_line']}" for x in suites), "evidence": "test-results.json"},
            {"n": 3, "title": "Source compiled", "status": build["status"] == "passed" and "completed" or "blocked", "timestamp": build["ran_at"],
             "description": "Every Python file byte-compiled.", "output": build["output"], "evidence": "test-results.json -> build"},
            {"n": 4, "title": "Application started and reachable", "status": "completed" if live["reachable"] else "blocked", "timestamp": live["started_at"],
             "description": f"Started the app on port {cfg['port']} with a temporary database and waited for HTTP.", "output": f"HTTP {live['http_status']}" if live["reachable"] else (live["error"] or ""), "evidence": "live-check.json"},
            {"n": 5, "title": "Live screenshot captured", "status": "completed" if live.get("screenshot") else "blocked", "timestamp": live.get("stopped_at"),
             "description": "Home page captured in Microsoft Edge at 1280px.", "output": live.get("screenshot") or "", "evidence": "reports/screenshots"},
            {"n": 6, "title": "Source-control baseline", "status": "partial", "timestamp": None,
             "description": "No original snapshot was supplied (any local git history is in git.json), so code changes cannot be compared with a baseline.", "output": git["import_kind"], "evidence": "git.json"},
            {"n": 7, "title": "Integrated into LTID Assistant", "status": "pending", "timestamp": None,
             "description": "Gallery card, workspace, Source Explorer, tests, report and live preview in the dashboard. Set to completed only by the dashboard check.", "output": "", "evidence": "dashboard"},
        ]
        (reports / "timeline.json").write_text(json.dumps(tl, indent=2), encoding="utf-8")
        print(f"   tests {totals['passed']} passed, {totals['failed']} failed (exit codes {[x['exit_code'] for x in suites]}); build {build['status']}; live {'yes' if live['reachable'] else 'NO'}; screenshot {live.get('screenshot')}", flush=True)
    return 0


if __name__ == "__main__":
    targets = sys.argv[1:] or list(PROJECTS)
    sys.exit(main(targets))
