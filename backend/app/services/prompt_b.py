"""Reads REAL data for the Prompt B (weather forecasting) evaluation project from disk. Nothing here is invented:
the file tree, diffs, test results, evaluation numbers, git state and report are derived from the repository snapshot
and from JSON files written by scripts/run_evidence.py and scripts/export_git.py after real executions.
The backend never runs project code; it only reads files."""
import ast, json, sys
from datetime import datetime, timezone
from fastapi import HTTPException
from ..config import PROMPT_B, PROMPT_B_PREVIEW_URL
from .project_fs import ProjectFS

SRC = PROMPT_B / "source"
ORIG = PROMPT_B / "original"
REPORTS = PROMPT_B / "reports"
SHOT_DIR = REPORTS / "screenshots"

def category(rel: str) -> str:
    if rel.startswith("tests/"): return "test"
    if rel.startswith("weather_app/web/"): return "frontend"
    if rel.endswith(".py"): return "backend"
    if rel.startswith("data/"): return "data"
    if rel.endswith((".md", ".txt")) or rel.startswith("."): return "config"
    return "other"

_fs = ProjectFS(SRC, ORIG, category)
change_map, tree, file_content, raw_file, diffs = _fs.change_map, _fs.tree, _fs.file_content, _fs.raw_file, _fs.diffs

def _json(name: str):
    p = REPORTS / name
    if not p.exists():
        raise HTTPException(404, f"{name} not found; run evaluation-projects/prompt-b-weather/scripts/run_evidence.py")
    return json.loads(p.read_text(encoding="utf-8"))

def tests() -> dict: return _json("test-results.json")
def timeline() -> list: return _json("timeline.json")
def analysis() -> dict: return _json("analysis.json")
def git() -> dict: return _json("git.json")
def evaluation() -> dict: return _json("evaluation.json")

def preview() -> dict:
    return {"url": PROMPT_B_PREVIEW_URL, "title": "Prompt B weather demo",
            "start_hint": "python -m weather_app --serve --port 8002 inside evaluation-projects/prompt-b-weather/source, or docker compose up --build"}

def screenshots() -> list[dict]:
    labels = {"desktop-1280-fold": "Desktop 1280px — forecast above the fold", "desktop-1280-full": "Desktop 1280px — forecast, full page",
              "desktop-1280-evaluation": "Desktop 1280px — MAE evaluation tab", "desktop-1280-demo": "Desktop 1280px — six demonstrations",
              "mobile-375-fold": "Mobile 375px — above the fold", "mobile-375-full": "Mobile 375px — forecast, full page",
              "mobile-375-evaluation": "Mobile 375px — MAE evaluation tab"}
    if not SHOT_DIR.exists(): return []
    return [{"name": s.stem, "label": labels.get(s.stem, s.stem), "path": f"screenshots/{s.name}",
             "viewport": "375" if "mobile" in s.stem else "1280"} for s in sorted(SHOT_DIR.glob("*.png"))]

# ------------------------------------------------------------------------------------------------------------ stack
def detect_stack() -> list[str]:
    """Technology stack detected from the real source files (imports and file types), not a hard-coded list."""
    std = set(sys.stdlib_module_names)
    third, mods = set(), set()
    for p in SRC.rglob("*.py"):
        if set(p.relative_to(SRC).parts) & {".git", "__pycache__"}: continue
        try: tree_ = ast.parse(p.read_text(encoding="utf-8"))
        except (SyntaxError, UnicodeDecodeError): continue
        for n in ast.walk(tree_):
            names = [a.name for a in n.names] if isinstance(n, ast.Import) else ([n.module or ""] if isinstance(n, ast.ImportFrom) and n.level == 0 else [])
            for full in names:
                top = full.split(".")[0]; mods.add(full)
                if top and top not in std and top != "weather_app": third.add(top)
    exts = {p.suffix for p in SRC.rglob("*") if p.is_file() and ".git" not in p.parts}
    try: py = analysis()["environment"]["python"].replace("Python ", "")
    except Exception: py = ""
    stack = [f"Python {py}".strip()]
    stack.append("stdlib only" if not third else "Python: " + ", ".join(sorted(third)))
    if "unittest" in mods: stack.append("unittest")
    if "http.server" in mods: stack.append("http.server JSON API")
    if {".html", ".js", ".css"} <= exts: stack.append("HTML/CSS/vanilla JS (SVG charts)")
    if "csv" in mods and ".csv" in exts: stack.append("CSV dataset")
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
    t = tests(); cm = change_map(); g = git(); ev = evaluation()
    return {"tests_passed": t["totals"]["passed"], "tests_failed": t["totals"]["failed"],
            "files_added": sum(v == "added" for v in cm.values()), "files_modified": sum(v == "modified" for v in cm.values()),
            "files_deleted": sum(v == "deleted" for v in cm.values()), "commits": len(g["commits"]),
            "pushed": g["push"]["status"] == "pushed", "draft_pr_created": g["draft_pr"]["status"] == "created",
            "cities": len(ev["overview"]["cities"]), "overall_mae": ev["evaluation"]["overall"]["mae"],
            "heldout_forecasts": ev["evaluation"]["overall"]["n"]}

# ------------------------------------------------------------------------------------------------------------ report
def _t(headers, rows) -> list[str]:
    cell = lambda x: str(x).replace("|", "/").replace("\n", " ")
    # leading blank line: a pipe table must be separated from the preceding paragraph to render as a table
    return ["", "| " + " | ".join(headers) + " |", "|" + "|".join("---" for _ in headers) + "|"] + ["| " + " | ".join(cell(c) for c in r) + " |" for r in rows]

REQUIRED_TESTS = [
    ("1. Valid city selection", "test_01_valid_city_selection"), ("2. Invalid city", "test_02_invalid_city_is_rejected_with_a_clear_message"),
    ("3. Valid 1-day horizon", "test_03_valid_1_day_horizon"), ("4. Valid 2-day horizon", "test_04_valid_2_day_horizon"),
    ("5. Valid 3-day horizon", "test_05_valid_3_day_horizon"), ("6. Invalid horizon", "test_06_invalid_horizon_is_rejected"),
    ("7. Missing observations", "test_07_missing_observations_are_excluded_not_imputed"),
    ("8. Malformed observations", "test_08_malformed_observations_fixture_exact_counts"),
    ("9. Time-ordered split", "test_09_time_ordered_split_trains_on_earlier_data_only"), ("10. MAE calculation", "test_10_mae_hand_computed"),
    ("10b. Independent evaluation calculation", "test_11_independent_recomputation_of_heldout_mae"),
    ("11. Forecast output format", "test_forecast_output_format"), ("12. Synthetic-data disclaimer", "test_12_synthetic_disclaimer_is_exact_and_always_present"),
]

def report_markdown() -> str:
    a, ev, t, g, cm = analysis(), evaluation(), tests(), git(), change_map()
    tl = timeline(); d = a["dataset"]; r = a["repository"]; ov = ev["overview"]; evl = ev["evaluation"]
    unit = next(s for s in t["suites"] if s["id"] == "weather-unittest"); status = {c["name"]: c["status"] for c in unit["cases"]}
    first = evl["cities"][0]
    L = ["# Evaluation Report — Prompt B: Weather Forecasting Demo", "",
         f"_Generated {datetime.now(timezone.utc).isoformat(timespec='seconds')} from real evidence files._", "",
         f"**{ev['disclaimer']}**", "",
         "## 1. Original evaluation task",
         f"Fictional client: **Eastbay City Lab**. Requirements: {a['requirements_source']['document']} — {a['requirements_source']['access']}", ""]
    L += [f"- **{x['id']} {x['area']}** — {x['text']}" for x in a["requirements"]]
    L += ["", "## 2. Repository analysis",
          f"- Repository: {r['url']}", f"- Import status: **{r['import_method']}**",
          f"- Base branch: `{r['base_branch']}` — {r['base_branch_note']}", f"- Framework: {r['framework']}", f"- Backend: {r['backend']}",
          f"- Entry points: {r['routes']}", f"- Original files: {', '.join(r['original_files'])}", "", "### Issues found in the starter (observed by running it)"]
    L += _t(["ID", "Area", "Finding", "Observed behaviour"], [(e["id"], e["area"], e["finding"], e["observed"]) for e in a["existing_issues"]])
    L += ["", "### Requirement coverage (starter vs result)"] + _t(["ID", "Area", "Starter", "Result", "Evidence"], [(x["id"], x["area"], x["original"], x["result"], x["evidence"]) for x in a["requirements"]])
    L += ["", "## 3. Dataset analysis",
          f"- File: `{d['file']}` — {d['observations']} observations, date range {d['date_range'][0]} to {d['date_range'][1]}",
          f"- Missing values: {d['missing_values']}; malformed observations: {d['malformed_observations']}; duplicates: {d['duplicate_observations']}; rows excluded by validation: {d['excluded_rows']}",
          f"- Temperature column: {', '.join(d['temperature_columns'])}; context columns (loaded, unused by the method): {', '.join(d['context_columns'])}", ""]
    L += _t(["City", "Observations", "First date", "Last date", "Missing days", "Temp range (°C)"], [(c["city"], c["observations"], c["first_date"], c["last_date"], c["missing_calendar_days"], f"{c['temp_min_c']} to {c['temp_max_c']}") for c in d["cities"]])
    L += [""] + _t(["Column", "Type", "Missing", "Example"], [(c["column"], c["type"], c["missing"], c["example"]) for c in d["columns"]])
    L += ["", "## 4. Synthetic-data explanation", f"- {ov['data_note']}", f"- {d['synthetic_evidence']}",
          "- Consequence: every forecast is labelled “Educational demonstration using synthetic observations – not a real weather forecast”, and a very low MAE reflects the regular pattern in the synthetic data, not real skill.", "",
          "## 5. Available tools and reasons"]
    L += [f"- **{x['name']}** — _{x['decision']}_: {x['reason']}" for x in a["tools"]]
    env = a.get("environment", {})
    L += ["", "Detected on the build machine: " + "; ".join(f"{k}: {v if v else 'not installed'}" for k, v in env.items()) + ". Only tools marked Selected were used.", "",
          "## 6. Selected forecasting method", f"- **{a['method']['name']}**", f"- Why: {a['method']['why']}", f"- How: {a['method']['how']}",
          f"- Limitations: {a['method']['limitations']}", f"- Why not machine learning: {a['method']['why_not_ml']}", "",
          f"Candidates for {first['city']} (training-backtest MAE was used to select; held-out MAE shown for transparency):"]
    L += _t(["Method", "Cycle", "Training backtest MAE °C", "Held-out MAE °C", "Selected"], [(c["label"], c["period"] or "-", f"{c['train_backtest_mae']:.3f}", f"{c['heldout_mae']:.3f}", "yes" if c["selected"] else "") for c in first["comparison"]])
    L += ["", "## 7. Architecture", "```"] + [f"{'→ ' if i else ''}{s['step']}  [{s['module']}]" for i, s in enumerate(a["architecture"])] + ["```", ""]
    L += ["## 8. Preprocessing policy",
          "- Excluded, never imputed: blank or non-numeric temperature, implausible temperature (outside -90..60 °C), invalid or non-ISO date, blank city, extra fields in a row.",
          "- Duplicates: identical copies dropped; for conflicting values the last row wins.", "- Unknown cities and horizons outside 1–3 are rejected with clear messages; empty or unreadable datasets raise a clear data error.",
          "- Every row is accounted for: total rows = valid rows + excluded rows.", "", "## 9. Time-ordered split",
          f"- {ev['evaluation']['split_config']['description']}. Data are sorted by date and never shuffled; training dates are verified to precede evaluation dates."]
    L += _t(["City", "Train obs", "Eval obs", "Training dates", "Evaluation dates", "No leakage"], [(c["city"], c["split"]["train_count"], c["split"]["evaluation_count"], f"{c['split']['train_start']} to {c['split']['train_end']}", f"{c['split']['evaluation_start']} to {c['split']['evaluation_end']}", "verified" if c["split"]["no_leakage"] else "VIOLATED") for c in evl["cities"]])
    L += ["", "## 10. MAE formula and actual calculations", f"`{evl['formula']}`", "",
          "Held-out MAE by city and horizon (walk-forward: a forecast for day t at horizon h uses only observations dated up to t−h):"]
    L += _t(["City", "Method", "1-day MAE", "2-day MAE", "3-day MAE", "Pooled MAE", "n", "Stricter train-only MAE", "Starter baseline MAE"],
            [(c["city"], c["selection"]["label"] + (f" ({c['selection']['period']}d)" if c["selection"]["period"] else ""), *[f"{h['mae']:.3f}" for h in c["metrics"]["by_horizon"]], f"{c['metrics']['pooled']['mae']:.3f}", c["metrics"]["pooled"]["n"], f"{c['metrics']['train_only_fixed_origin']['mae']:.3f}", f"{c['baseline_recent_average_mae']:.3f}") for c in evl["cities"]])
    L += ["", f"All cities pooled: **MAE = {evl['overall']['mae']:.3f} °C** over {evl['overall']['n']} held-out forecasts.", "", f"Worked example — {first['city']}, 1-day-ahead forecasts on the held-out days:"]
    rows1 = first["evaluation_rows"][0]["rows"]; tot = sum(x["abs_error"] for x in rows1)
    L += _t(["Date", "Actual °C", "Predicted °C", "Absolute error °C"], [(x["date"], f"{x['actual']:.1f}", f"{x['predicted']:.1f}", f"{x['abs_error']:.1f}") for x in rows1])
    L += ["", f"MAE = {tot:.1f} / {len(rows1)} = **{tot / len(rows1):.3f} °C**", f"{first['explanation']}", "", f"Independent check ({ev['independent_check']['description']}): " + "; ".join(f"{c['city']} reported {c['mae_reported']:.6f} vs recomputed {c['mae_independent']:.6f} ({'match' if c['match'] else 'MISMATCH'})" for c in ev["independent_check"]["cities"]) + ".", "",
          "## 11. Two-city, three-horizon demonstrations", ev["demonstrations"]["note"]]
    L += _t(["Case", "Method", "Day 1", "Day 2", "Day 3", "Held-out MAE (per forecast day)"], [(c["case"], c["method"] + (f" ({c['period_days']}d)" if c["period_days"] else ""), *[f"{p['predicted_temp_c']:.1f} °C ({p['date']})" if i < len(c["predictions"]) else "-" for i, p in enumerate(c["predictions"])], *["-"] * (3 - len(c["predictions"])), ", ".join(f"{m['mae']:.3f}" for m in c["heldout_mae_by_forecast_day"])) for c in ev["demonstrations"]["cases"]])
    L += ["", f"_{ev['disclaimer']}_", "", "## 12. Unit test results"]
    for s in t["suites"]:
        p = sum(c["status"] == "passed" for c in s["cases"])
        L.append(f"- **{s['title']}** (`{s['command']}`, run {s['ran_at']}): {p}/{len(s['cases'])} passed, exit code {s['exit_code']}")
    L += [f"- Total: **{t['totals']['passed']} passed, {t['totals']['failed']} failed**", "", "Requirement-to-test mapping (status from the recorded run):"]
    L += _t(["Required area", "Test", "Status"], [(lbl, f"`{nm}`", status.get(nm, "not found")) for lbl, nm in REQUIRED_TESTS])
    chk = ev["robustness_checks"]
    L += ["", "## 13. Error handling", f"{sum(c['passed'] for c in chk)} of {len(chk)} executed robustness checks behaved as documented (no unhandled exceptions):"]
    L += _t(["Group", "Check", "Input", "Outcome", "Pass"], [(c["group"], c["name"], c["input"], c["outcome"], "yes" if c["passed"] else "NO") for c in chk])
    diffs_ = diffs(); ch = lambda st: [x for x in diffs_ if x["status"] == st]   # noqa: E731
    L += ["", "## 14. Modified files", f"{len(ch('modified'))} modified, {len(ch('added'))} added, {len(ch('deleted'))} deleted (source vs original ZIP snapshot):"]
    L += _t(["File", "Status", "+", "−"], [(x["path"], x["status"], x["additions"], x["deletions"]) for x in diffs_])
    L += ["", "## 15. GitHub branch and PR status", f"- Repository: {g['repository_url']}", f"- Base branch: `{g['base_branch']}` (verified: {g['base_branch_verified']}) — `{g['baseline_commit']['hash']}` {g['baseline_commit']['subject']}",
          f"- Development branch: `{g['dev_branch']}` (local)", "- Local commits:"] + [f"  - `{c['hash']}` {c['subject']}" for c in g["commits"]]
    L += [f"- Push: **{g['push']['status']}** — {g['push']['reason']}", f"- Draft PR: **{g['draft_pr']['status']}** — {g['draft_pr']['reason']}", "- A local `git bundle` of the branch is in `reports/prompt-b-source.bundle`.", "",
          "## 16. Limitations"] + [f"- {x}" for x in ev["known_limitations"]]
    done = sum(s["status"] == "completed" for s in tl)
    L += ["", "## 17. Final completion status", f"{done}/{len(tl)} timeline steps completed; not fully completed: " + (", ".join(f"#{s['n']} {s['title']} ({s['status']})" for s in tl if s["status"] != "completed") or "none") + ".",
          "Overall: forecasting application implemented, tested and verified locally; GitHub publication **pending** (" + g["push"]["status"].replace("_", " ") + ")."]
    return "\n".join(L)
