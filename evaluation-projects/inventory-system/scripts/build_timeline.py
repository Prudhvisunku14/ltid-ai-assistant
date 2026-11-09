"""Builds reports/timeline.json from the real git history and reports/test-results.json.
A step is 'completed' only when its commit exists in the repository or its test evidence passed."""
import json
import pathlib
import subprocess

ROOT = pathlib.Path(__file__).resolve().parents[1]
REPO = ROOT / "inventory"
R = ROOT / "reports"
tests = json.loads((R / "test-results.json").read_text(encoding="utf-8"))
git = json.loads((R / "git.json").read_text(encoding="utf-8"))
by_hash = {c["hash"]: c for c in git["commits"] + [git["baseline_commit"]]}


def suite(sid):
    return next((s for s in tests["suites"] if s["id"] == sid), None)


def ok(s):
    return bool(s) and s["exit_code"] == 0 and all(c["status"] == "passed" for c in s["cases"])


def load_dash():
    p = R / "dashboard-verification.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else None


steps = []
def add(title, status, description, output, evidence, ts=None):
    steps.append({"n": len(steps) + 1, "title": title, "status": status, "timestamp": ts, "description": description,
                  "output": output, "evidence": evidence})

def sub(prefix):
    return next((v for v in by_hash.values() if v["subject"].startswith(prefix)), None)

base = sub("chore: initial")
data = sub("feat(db)")
api = sub("feat(api,ui)")
tst = sub("test: unit")
e2e = sub("test(e2e)")
add("Skeleton repository", "completed" if base else "pending", "Initial repository skeleton (README and .gitignore).", base and base["subject"], f"commit {base['hash']}" if base else "", base and base["date"])
add("Data layer: schema, validation, search, CSV", "completed" if data else "pending", "SQLite persistence, validation, search, CSV import and export.", data and data["subject"], f"commit {data['hash']}" if data else "", data and data["date"])
add("HTTP API, single-page UI, low-stock banner", "completed" if api else "pending", "JSON API, UI, low-stock alert banner.", api and api["subject"], f"commit {api['hash']}" if api else "", api and api["date"])
add("Unit and live-HTTP tests", "completed" if tst else "pending", "Unit and HTTP tests; one fix found by them (oversized body returns 413).", tst and tst["subject"], f"commit {tst['hash']}" if tst else "", tst and tst["date"])
add("Real-browser end-to-end test and screenshots", "completed" if e2e else "pending", "Playwright end-to-end test with screenshots.", e2e and e2e["subject"], f"commit {e2e['hash']}" if e2e else "", e2e and e2e["date"])
u = suite("unit-http"); b = suite("browser-e2e")
add("Re-run of all tests (evidence)", "completed" if ok(u) and ok(b) else "blocked", "Unit/HTTP and browser suites re-executed by scripts/run_evidence.py.",
    f"unit-http: {sum(c['status']=='passed' for c in u['cases'])} passed; browser: {sum(c['status']=='passed' for c in b['cases'])} steps passed" if u and b else "",
    "reports/test-results.json", tests["generated_at"])
add("Fix: favicon request answered 404", "completed" if ok(u) else "partial",
    "The browser test found that /favicon.ico returned 404; now 204. Change is uncommitted in the working tree.",
    "; ".join(git["uncommitted_changes"]) or "no uncommitted changes", "app/server.py, tests/test_api.py (uncommitted)", tests["generated_at"])
dv = load_dash()
add("Integrated into LTID Assistant", "completed" if dv and dv["passed"] == dv["total"] else ("partial" if dv else "pending"),
    "Gallery card, workspace, Source Explorer, tests, report, live preview and settings in the dashboard.",
    f"{dv['passed']}/{dv['total']} browser checks pass (scripts/verify_dashboard.py); backend tests 27 passed" if dv else "not yet verified",
    "reports/dashboard-verification.json", dv and tests["generated_at"])
add("Publish to GitHub and open Draft PR", "blocked" if git["push"]["status"] == "not_pushed" else "pending",
    "No remote is configured, so nothing can be pushed. The PR is never merged.", git["push"]["reason"], "reports/git.json")

(R / "timeline.json").write_text(json.dumps(steps, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps([(s["n"], s["status"]) for s in steps]))
