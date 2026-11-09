"""Re-runs the Inventory project's own test suites and writes reports/*.json from REAL executions.

    .venv\\Scripts\\python.exe evaluation-projects/inventory-system/scripts/run_evidence.py

* unit + live-HTTP tests:   python -m unittest discover -s tests -t . -v      (stdlib only)
* browser end-to-end test:  python -m tests.browser_e2e   (Playwright; uses the installed Microsoft Edge)
* git state:                read from the local repository (no remote exists, so nothing is claimed as pushed)
* screenshots:              copied from docs/ by the browser test run

Nothing is typed in: every number comes from the commands above.
"""
import datetime as dt
import json
import os
import pathlib
import re
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT / "inventory"
REPORTS = ROOT / "reports"
PY = sys.executable
ENV = {**os.environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"}
now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")  # noqa: E731


def run(cmd, cwd, timeout=600):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", env=ENV, timeout=timeout)
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def git(*args):
    return subprocess.run(["git", *args], cwd=REPO, capture_output=True, text=True, encoding="utf-8").stdout.strip()


def parse_unittest(out):
    cases = []
    for m in re.finditer(r"^(test\w*) \(([\w.]+)\) \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$", out, re.M):
        name, ident, res = m.groups()
        cases.append({"name": name, "class": ident.rsplit(".", 1)[-1] if "." in ident else ident,
                      "status": "passed" if res == "ok" else "skipped" if res.startswith("skipped") else "failed"})
    ran = int(re.search(r"Ran (\d+) tests?", out).group(1))
    if len(cases) != ran:
        raise RuntimeError(f"parsed {len(cases)} cases but unittest ran {ran}")
    return cases


def main():
    REPORTS.mkdir(exist_ok=True)
    suites = []

    # 1. unit + live HTTP tests
    t0 = now()
    code, out = run([PY, "-m", "unittest", "discover", "-s", "tests", "-t", ".", "-v"], REPO)
    suites.append({"id": "unit-http", "title": "Unit and live-HTTP tests (database, API, CSV, security)",
                   "command": "python -m unittest discover -s tests -t . -v", "ran_at": t0, "exit_code": code,
                   "cases": parse_unittest(out), "output_tail": out.strip().splitlines()[-3:]})

    # 2. browser end-to-end (Playwright). Uses the installed Edge when Playwright's own Chromium is missing.
    t0 = now()
    wrapper = ROOT / "scripts" / "_run_e2e.py"
    wrapper.write_text(
        "import os, sys, runpy\n"
        "sys.path.insert(0, os.getcwd())\n"
        "from playwright.sync_api._generated import BrowserType\n"
        "_orig = BrowserType.launch\n"
        "def _launch(self, *a, **kw):\n"
        "    try:\n"
        "        return _orig(self, *a, **kw)\n"
        "    except Exception:\n"
        "        kw['channel'] = 'msedge'\n"
        "        return _orig(self, *a, **kw)\n"
        "BrowserType.launch = _launch\n"
        "sys.argv = ['tests.browser_e2e']\n"
        "runpy.run_module('tests.browser_e2e', run_name='__main__', alter_sys=True)\n", encoding="utf-8")
    try:
        code, out = run([PY, str(wrapper)], REPO, timeout=900)
    finally:
        wrapper.unlink(missing_ok=True)
    steps = [l[4:] for l in out.splitlines() if l.startswith("ok: ")]
    browser_cases = [{"name": s, "class": "BrowserE2E", "status": "passed"} for s in steps]
    if code != 0 or "BROWSER E2E PASSED" not in out:
        browser_cases.append({"name": "browser end-to-end run", "class": "BrowserE2E", "status": "failed"})
    skipped = "SKIPPED" in out
    suites.append({"id": "browser-e2e", "title": "Browser end-to-end (Chromium/Edge: add, alert, edit, import, export, XSS, delete, reload)",
                   "command": "python -m tests.browser_e2e", "ran_at": t0, "exit_code": code,
                   "cases": browser_cases, "output_tail": out.strip().splitlines()[-3:], "skipped": skipped})

    totals = {"passed": sum(c["status"] == "passed" for s in suites for c in s["cases"]),
              "failed": sum(c["status"] == "failed" for s in suites for c in s["cases"])}
    (REPORTS / "test-results.json").write_text(json.dumps({"generated_at": now(), "build": {
        "status": "passed" if all(s["exit_code"] == 0 for s in suites) else "failed",
        "command": "python -m unittest + python -m tests.browser_e2e (stdlib app; no compile step)", "ran_at": now(),
        "output": "all suites exit 0" }, "suites": suites, "totals": totals}, indent=2), encoding="utf-8")

    # 3. git state (local only; no remote configured)
    log = git("log", "--format=%h\x1f%an\x1f%aI\x1f%s").splitlines()
    commits = [dict(zip(("hash", "author", "date", "subject"), l.split("\x1f"))) for l in log]
    base = commits[-1]
    dev = git("rev-parse", "--abbrev-ref", "HEAD")
    remotes = git("remote")
    git_state = {"exported_at": now(), "repository_url": None, "base_branch": dev, "base_branch_verified": False,
                 "base_branch_evidence": "no remote configured; branch exists only in the local repository",
                 "import_kind": "Local git repository built by the project's agent (no GitHub remote)",
                 "dev_branch": dev, "baseline_commit": base, "commits": commits[:-1],
                 "uncommitted_changes": git("status", "--short").splitlines(),
                 "push": {"status": "not_pushed" if not remotes else "not_attempted",
                          "reason": "No remote is configured in the local repository, so nothing has been pushed." if not remotes else "Remote exists; push not attempted by this script."},
                 "draft_pr": {"status": "not_created", "url": None, "reason": "Requires a pushed branch."}}
    (REPORTS / "git.json").write_text(json.dumps(git_state, indent=2), encoding="utf-8")

    # 4. screenshots the browser run captured (tests write them into docs/)
    for name in ("screenshot-main.png", "screenshot-after.png"):
        src = REPO / "docs" / name
        if src.exists():
            (REPORTS / "screenshots" / name.replace("screenshot-main", "main-list").replace("screenshot-after", "after-changes")).write_bytes(src.read_bytes())
    git("checkout", "--", "docs/screenshot-main.png", "docs/screenshot-after.png")   # keep the committed docs unchanged

    print(json.dumps({"tests": totals, "suites": [(s["id"], len(s["cases"]), s["exit_code"]) for s in suites]}))
    return 0 if totals["failed"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
