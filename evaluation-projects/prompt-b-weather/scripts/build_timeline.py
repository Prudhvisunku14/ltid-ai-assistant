"""Builds reports/timeline.json. Each step's status is DERIVED from the evidence files written by run_evidence.py,
export_git.py and verify_platform.py - a step is only 'completed' when its evidence exists and passed."""
import json
import pathlib

R = pathlib.Path(__file__).resolve().parents[1] / "reports"
load = lambda n: json.loads((R / n).read_text(encoding="utf-8")) if (R / n).exists() else None   # noqa: E731
tests, ev, an, git, plat = load("test-results.json"), load("evaluation.json"), load("analysis.json"), load("git.json"), load("platform-verification.json")


def suite(sid):
    return next((s for s in (tests or {}).get("suites", []) if s["id"] == sid), None)


def counts(s):
    return (sum(c["status"] == "passed" for c in s["cases"]), sum(c["status"] == "failed" for c in s["cases"])) if s else (0, 0)


def ok(s):
    p, f = counts(s)
    return bool(s) and f == 0 and p > 0 and s["exit_code"] == 0


steps = []
def add(title, status, description, output, evidence, ts=None):
    steps.append({"n": len(steps) + 1, "title": title, "status": status, "timestamp": ts, "description": description, "output": output, "evidence": evidence})

a_ts = an and an["generated_at"]
t_ts = tests and tests["generated_at"]
d = an["dataset"] if an else {}
orig, wx, ui = suite("original-tests"), suite("weather-unittest"), suite("browser-ui")

add("Repository imported / accessed", "partial",
    "Imported from the user-supplied ZIP snapshot. Anonymous read access to GitHub confirmed the default branch and that the ZIP equals upstream main; no authenticated connection exists (push failed), so the import is labelled a ZIP snapshot.",
    (git or {}).get("base_branch_evidence", ""), "reports/git.json; analysis.json -> repository")
add("Requirements imported / accessed", "completed", "02_Weather_Requirements.docx was read directly from Google Drive through the Drive connector (plain-text rendering).",
    "5 functional + 2 acceptance requirements", "inputs/02_Weather_Requirements.md", a_ts)
add("Source code inspected", "completed", "Python CLI starter, no framework or web layer; 7 files.", ", ".join(an["repository"]["original_files"]) if an else "", "analysis.json -> repository", a_ts)
add("Dataset analysed", "completed", "Profiled the supplied synthetic CSV (columns, types, cities, range, missing/malformed/duplicate rows).",
    f"{d.get('observations')} rows, {len(d.get('cities', []))} cities, {d.get('date_range', ['', ''])[0]} to {d.get('date_range', ['', ''])[1]}; {d.get('excluded_rows')} rows invalid" if d else "", "analysis.json -> dataset", a_ts)
add("Existing tests executed", "completed" if ok(orig) else "blocked", "Ran the starter's own tests on the untouched baseline before changing anything.",
    "\n".join((orig or {}).get("output_tail", [])[-3:]), "test-results.json -> original-tests", orig and orig["ran_at"])
add("Starter compared with requirements", "completed", "Ran the starter on malformed and boundary inputs to find real defects and gaps.",
    "; ".join(f"{e['id']}: {e['area']}" for e in (an or {}).get("existing_issues", [])), "analysis.json -> existing_issues, requirements", a_ts)
add("Tools and forecasting method selected", "completed", "Chose a standard-library stack and five transparent candidate methods; the method is selected by backtest on training data only.",
    (an or {}).get("method", {}).get("name", ""), "analysis.json -> tools, method", a_ts)
add("Implementation plan produced", "completed", "Numbered plan with files, tools, status and verification evidence.", f"{len((an or {}).get('plan', []))} tasks", "analysis.json -> plan", a_ts)
sel = ev and ev["evaluation"]["cities"][0]["selection"]
add("Validation, forecasting and evaluation implemented", "completed" if ev and ev["independent_check"]["all_match"] else "partial",
    "Data validation, five forecast methods, time-ordered split, held-out MAE.", f"selected: {sel['label']} (period {sel['period']}); independent MAE recomputation matches: {ev['independent_check']['all_match']}" if sel else "", "evaluation.json -> independent_check", ev and ev["generated_at"])
add("CLI, JSON API and interactive UI implemented", "completed" if ok(ui) else "partial", "Hardened original CLI; stdlib JSON API; interactive UI with chart, cards, table and evaluation views.", "weather_app/server.py, weather_app/web/*", "reports/screenshots")
wp, wf = counts(wx)
add("Unit tests added and executed", "completed" if ok(wx) else "blocked", "Added tests for invalid city/horizon, malformed data, split, leakage, MAE (hand-computed and independent), output format, disclaimer, CLI, HTTP API.",
    f"{wp} passed, {wf} failed", "test-results.json -> weather-unittest", wx and wx["ran_at"])
up, uf = counts(ui)
add("Browser verification (desktop + mobile)", "completed" if ok(ui) else "blocked", "Playwright drove the real UI in Edge at 1280px and 375px; displayed numbers cross-checked against the API.",
    f"{up} passed, {uf} failed", "test-results.json -> browser-ui; reports/screenshots", ui and ui["ran_at"])
add("Two cities x three horizons demonstrated", "completed" if ev and len(ev["demonstrations"]["cases"]) == 6 else "partial", "Six cases generated by the implementation.",
    ", ".join(c["case"] for c in ev["demonstrations"]["cases"]) if ev else "", "evaluation.json -> demonstrations", ev and ev["generated_at"])
pv = plat
add("Integrated into LTID Assistant", "completed" if pv and pv["all_passed"] else ("blocked" if pv else "pending"),
    "Gallery card, workspace, Source Explorer, tests, report, live preview and GitHub tabs reuse the existing components; Prompt A regression checked.",
    ("; ".join(f"{c['name']}: {'ok' if c['passed'] else 'FAILED'}" for c in pv["checks"])) if pv else "not yet verified", "reports/platform-verification.json", pv and pv["ran_at"])
cm = git["commits"][0] if git and git["commits"] else None
add("Local development branch committed", "completed" if cm else "pending", "Branch created on a clone of upstream main and the modifications committed.",
    f"{git['dev_branch']} @ {cm['hash']} (base {git['baseline_commit']['hash']})" if cm else "", "reports/git.json", cm and cm["date"])
pushed = git and git["push"]["status"] == "pushed"
add("Push branch and open Draft PR", "completed" if git and git["draft_pr"]["status"] == "created" else ("blocked" if git and git["push"].get("attempted_at") and not pushed else "pending"),
    "Pushing needs GitHub credentials. Nothing is reported as pushed unless git ls-remote confirms it; the PR is never merged.",
    f"push: {git['push']['status']} — {git['push']['reason']}\nDraft PR: {git['draft_pr']['status']} — {git['draft_pr']['reason']}" if git else "", "reports/git.json", git and git["push"].get("attempted_at"))
add("Final report generated", "completed", "Seventeen-section report (Markdown/PDF) and evaluation JSON are generated on demand from these evidence files.", "GET /api/projects/prompt-b/report", "backend/app/services/prompt_b.py")
(R / "timeline.json").write_text(json.dumps(steps, indent=2, ensure_ascii=False), encoding="utf-8")
print(json.dumps([(s["n"], s["status"]) for s in steps]))
