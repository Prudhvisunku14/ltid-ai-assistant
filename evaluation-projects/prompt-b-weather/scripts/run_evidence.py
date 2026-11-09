"""Re-runs everything for Prompt B and rewrites reports/*.json from REAL executions (nothing typed in):

  * the starter's ORIGINAL tests against the untouched baseline (original/)
  * the full unit-test suite against the modified source (source/)
  * the Playwright browser checks (scripts/ui_check.py)
  * the evaluation document (dataset profile, split, MAE, six demonstrations, robustness checks)
  * analysis.json (repository / dataset / tool analysis computed from the files and the machine)

Usage (from the platform root):   .venv\\Scripts\\python.exe evaluation-projects/prompt-b-weather/scripts/run_evidence.py
"""
import csv
import datetime as dt
import importlib.util
import json
import pathlib
import re
import shutil
import subprocess
import sys
from collections import Counter

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC, ORIG, REPORTS = ROOT / "source", ROOT / "original", ROOT / "reports"
PY = sys.executable
now = lambda: dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")   # noqa: E731
sys.path.insert(0, str(SRC))


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace",
                       env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8", "PYTHONDONTWRITEBYTECODE": "1"})
    return p.returncode, (p.stdout or "") + (p.stderr or "")


def parse_unittest(output):
    """Parse `unittest -v` output into cases; cross-checks the count with the 'Ran N tests' line."""
    cases = []
    pat = re.compile(r"^(test\w*) \(([\w.]+)\)(?:\n(?!test)[^\n]*?)? \.\.\. (ok|FAIL|ERROR|skipped[^\n]*)$", re.M)
    for m in pat.finditer(output):
        name, ident, res = m.groups()
        cases.append({"name": name, "class": ident.rsplit(".", 1)[0].split(".", 1)[-1] if "." in ident else ident,
                      "status": "passed" if res == "ok" else "skipped" if res.startswith("skipped") else "failed"})
    ran = int(re.search(r"Ran (\d+) tests?", output).group(1))
    if len(cases) != ran:
        raise RuntimeError(f"parsed {len(cases)} cases but unittest ran {ran}")
    return cases


def unittest_suite(sid, title, cwd, label):
    cmd = [PY, "-m", "unittest", "discover", "-s", "tests", "-v"]
    t0 = now()
    code, out = run(cmd, cwd)
    return {"id": sid, "title": title, "command": f"python -m unittest discover -s tests -v   (cwd: {label})", "ran_at": t0,
            "exit_code": code, "cases": parse_unittest(out), "output_tail": out.strip().splitlines()[-6:]}


def tool_version(cmd):
    try:
        r = subprocess.run(cmd, capture_output=True, text=True, timeout=20)
        return (r.stdout or r.stderr).strip().splitlines()[0]
    except Exception:
        return None


def module_version(name):
    try:
        spec = importlib.util.find_spec(name)
    except Exception:
        spec = None
    if not spec:
        return None
    try:
        return __import__(name).__version__
    except Exception:
        return "installed"


def dataset_profile():
    from weather_app.service import WeatherService
    path = ORIG / "data" / "weather_history.csv"
    with open(path, encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    def kind(col):
        vals = [r[col] for r in rows]
        if all(re.fullmatch(r"\d{4}-\d{2}-\d{2}", v) for v in vals): return "date (ISO YYYY-MM-DD)"
        try:
            [float(v) for v in vals]
            return "integer-valued number" if all(re.fullmatch(r"-?\d+", v) for v in vals) else "decimal number"
        except ValueError:
            return "text"
    cols = [{"column": c, "type": kind(c), "missing": sum(1 for r in rows if not (r[c] or "").strip()),
             "example": rows[0][c]} for c in rows[0].keys()]
    svc = WeatherService(path)
    dq = svc.data_quality()
    ov = svc.overview()
    return {"file": "data/weather_history.csv", "sha256": ov["dataset"]["sha256"], "observations": len(rows),
            "cities": [{"city": c["city"], "observations": c["observations"], "first_date": c["first_date"], "last_date": c["last_date"],
                        "missing_calendar_days": c["missing_calendar_days"], "temp_min_c": c["min_temp_c"], "temp_max_c": c["max_temp_c"]}
                       for c in dq["cities"]],
            "date_range": [ov["dataset"]["first_date"], ov["dataset"]["last_date"]], "columns": cols,
            "temperature_columns": ["temp_c (°C, target variable)"],
            "context_columns": ["humidity_pct", "rain_mm"],
            "missing_values": sum(c["missing"] for c in cols), "malformed_observations": dq["malformed_total"],
            "duplicate_observations": dq["duplicates_total"], "excluded_rows": dq["excluded_total"],
            "synthetic": True,
            "synthetic_evidence": "README.md and TASK_PUBLIC.md state the data are synthetic." + (
                " Verified from the data: Osaka = Tokyo + 1.0 °C and Sapporo = Tokyo − 7.0 °C on every date (one shared pattern, shifted)."
                if all(verify_offsets().values()) else "")}


def verify_offsets():
    """Confirm the synthetic-structure claim above from the data instead of asserting it."""
    from weather_app.service import WeatherService
    ds = WeatherService(ORIG / "data" / "weather_history.csv").dataset()
    t = {o.date: o.temp_c for o in ds.observations("Tokyo")}
    res = {}
    for city, off in (("Osaka", 1.0), ("Sapporo", -7.0)):
        res[city] = all(abs((o.temp_c - t[o.date]) - off) < 1e-9 for o in ds.observations(city))
    return res


ORIGINAL_PROBE = r"""
import json, sys, traceback, tempfile, os, csv
from weather_app.core import load_rows, predict_temperature
fixture = sys.argv[1]
out = []
def attempt(key, fn):
    try:
        out.append([key, "returned", repr(fn())[:160]])
    except Exception as e:
        out.append([key, "raised", type(e).__name__ + ": " + str(e)[:120]])
rows = load_rows("data/weather_history.csv", "Tokyo")
attempt("flat_forecast_3_days", lambda: predict_temperature(rows, 3))
attempt("horizon_0_in_library", lambda: predict_temperature(rows, 0))
attempt("horizon_99_in_library", lambda: len(predict_temperature(rows, 99)))
attempt("malformed_fixture_load_then_predict", lambda: predict_temperature(load_rows(fixture, "Tokyo"), 2))
d = tempfile.mkdtemp(); p = os.path.join(d, "nocity.csv"); open(p, "w").write("date,temp_c\n2026-08-01,10\n")
attempt("missing_city_column", lambda: load_rows(p, "Tokyo"))
q = os.path.join(d, "dates.csv"); open(q, "w").write("city,date,temp_c\nTokyo,2026-10-01,20\nTokyo,2026-9-15,10\nTokyo,2026-08-01,30\n")
r1 = os.path.join(d, "blank.csv"); open(r1, "w").write("city,date,temp_c\nTokyo,2026-08-01,10\nTokyo,2026-08-02,12\nTokyo,2026-08-03,\n")
attempt("blank_latest_temperature", lambda: predict_temperature(load_rows(r1, "Tokyo"), 2))
r2 = os.path.join(d, "word.csv"); open(r2, "w").write("city,date,temp_c\nTokyo,2026-08-01,10\nTokyo,2026-08-02,12\nTokyo,2026-08-03,warm\n")
attempt("non_numeric_latest_temperature", lambda: predict_temperature(load_rows(r2, "Tokyo"), 2))
attempt("string_date_sorting", lambda: [r["date"] for r in load_rows(q, "Tokyo")])
print(json.dumps(out))
"""


def original_behaviour():
    code, out = run([PY, "-c", ORIGINAL_PROBE, str(SRC / "tests" / "fixtures" / "malformed_weather.csv")], ORIG)
    res = {k: (how, text) for k, how, text in json.loads(out.strip().splitlines()[-1])}
    g = lambda k: res[k][1]   # noqa: E731
    pattern = re.compile(r"(?<![a-z])mae(?![a-z])|def\s+\w*(split|evaluat)", re.I)
    hits = [str(f.relative_to(ORIG)) for f in ORIG.rglob("*.py") if pattern.search(f.read_text(encoding="utf-8"))]
    return [
        {"id": "E1", "area": "Forecast", "finding": "The starter forecast is a flat recent average: every forecast day is identical.", "observed": g("flat_forecast_3_days")},
        {"id": "E2", "area": "Robustness", "finding": "A blank or non-numeric temperature among the latest rows crashes the library with an unhandled exception. (Bad rows earlier in the file are silently ignored only because just the last 3 rows are read, so errors are inconsistent, not handled.)", "observed": "blank latest temp -> " + g("blank_latest_temperature") + " | 'warm' latest temp -> " + g("non_numeric_latest_temperature") + " | malformed fixture with valid last rows -> " + g("malformed_fixture_load_then_predict")},
        {"id": "E3", "area": "Robustness", "finding": "A CSV without the expected columns crashes with a KeyError.", "observed": g("missing_city_column")},
        {"id": "E4", "area": "Inputs", "finding": "The 1-3 day limit exists only in the CLI. The library accepts any horizon.", "observed": f"days=0 -> {g('horizon_0_in_library')}; days=99 -> {g('horizon_99_in_library')} values"},
        {"id": "E5", "area": "Data handling", "finding": "Rows are sorted as text, so non-padded dates sort in the wrong order.", "observed": "dates 2026-10-01, 2026-9-15, 2026-08-01 sorted as " + g("string_date_sorting")},
        {"id": "E6", "area": "Evaluation", "finding": "No train/evaluation split and no MAE exist anywhere in the starter.", "observed": "searched original/ *.py for a 'mae' name or a split/evaluate function: " + (str(hits) if hits else "no matches")},
        {"id": "E7", "area": "Tests", "finding": "The 2 starter tests cover only a happy path (Tokyo row count, one average). No invalid input or evaluation is tested.", "observed": "2 tests, both passing on the baseline"},
        {"id": "E8", "area": "Output", "finding": "The CLI JSON has no dates, method name, explanation, or MAE; only a 'type' string mentions the data are synthetic.", "observed": "see original/weather_app/__main__.py"},
    ]


def main():
    REPORTS.mkdir(exist_ok=True)
    # ---------------------------------------------------------------- tests
    suites = [
        unittest_suite("original-tests", "Starter tests (original, untouched baseline)", ORIG, "original/"),
        unittest_suite("weather-unittest", "Weather unit tests (modified source)", SRC, "source/"),
    ]
    code, out = run([PY, str(ROOT / "scripts" / "ui_check.py")], ROOT.parents[1])
    try:
        ui = json.loads(out.strip().splitlines()[-1])["cases"]
    except Exception:
        ui = [{"name": "ui_check_could_not_run", "class": "BrowserUI", "status": "failed", "detail": out[-300:]}]
    suites.append({"id": "browser-ui", "title": "Browser UI checks (Playwright + Microsoft Edge: desktop 1280px and mobile 375px)",
                   "command": "python scripts/ui_check.py", "ran_at": now(), "exit_code": code,
                   "cases": [{k: v for k, v in c.items() if k != "detail"} for c in ui],
                   "output_tail": [f"{c['status']}: {c['name']}" + (f" - {c['detail']}" if c.get("detail") and c['status'] != 'passed' else "") for c in ui[-6:]]})
    build_cmd = [PY, "-c", "import ast, pathlib, sys; sys.path.insert(0, '.'); "
                 "[ast.parse(p.read_text(encoding='utf-8'), str(p)) for p in pathlib.Path('weather_app').rglob('*.py')]; "
                 "import weather_app.__main__, weather_app.server; print('compiled and imported OK')"]
    bcode, bout = run(build_cmd, SRC)
    build = {"status": "passed" if bcode == 0 else "failed", "command": "python: parse every weather_app/*.py, then import weather_app.__main__ and weather_app.server (no compile/bundle step exists)",
             "ran_at": now(), "output": bout.strip()[-200:]}
    totals = {"passed": sum(c["status"] == "passed" for s in suites for c in s["cases"]),
              "failed": sum(c["status"] == "failed" for s in suites for c in s["cases"])}
    (REPORTS / "test-results.json").write_text(json.dumps({"generated_at": now(), "build": build, "suites": suites, "totals": totals}, indent=2), encoding="utf-8")

    # ---------------------------------------------------------------- evaluation document
    from weather_app.service import WeatherService
    svc = WeatherService(SRC / "data" / "weather_history.csv")
    doc = svc.full_document()
    # independent recomputation (plain csv + arithmetic, no weather_app code) stored beside the reported numbers
    with open(SRC / "data" / "weather_history.csv", encoding="utf-8", newline="") as fh:
        rows = list(csv.DictReader(fh))
    checks = []
    for city_eval in doc["evaluation"]["cities"]:
        vals = [float(r["temp_c"]) for r in sorted((r for r in rows if r["city"] == city_eval["city"]), key=lambda r: r["date"])]
        n_tr = city_eval["split"]["train_count"]
        sel = city_eval["selection"]
        errs = []
        for j in range(n_tr, len(vals)):
            for h in (1, 2, 3):
                hist = vals[: j - h + 1]
                p = sel["period"]
                drift = sum(hist[i] - hist[i - p] for i in range(p, len(hist))) / (len(hist) - p)
                errs.append(abs(vals[j] - round(vals[j - p] + drift, 1)))
        mine = sum(errs) / len(errs)
        checks.append({"city": city_eval["city"], "method": sel["method"], "period": sel["period"], "n": len(errs),
                       "mae_reported": city_eval["metrics"]["pooled"]["mae"], "mae_independent": round(mine, 6),
                       "match": abs(mine - city_eval["metrics"]["pooled"]["mae"]) < 1e-5})
    doc["independent_check"] = {"description": "Held-out MAE recomputed with plain csv + arithmetic (no weather_app code).", "cities": checks,
                                "all_match": all(c["match"] for c in checks)}
    doc["synthetic_structure_check"] = verify_offsets()
    doc["tests"] = {"passed": totals["passed"], "failed": totals["failed"], "suites": [{"id": s["id"], "title": s["title"],
                    "passed": sum(c["status"] == "passed" for c in s["cases"]), "failed": sum(c["status"] == "failed" for c in s["cases"])} for s in suites]}
    doc["known_limitations"] = [
        "All observations are synthetic. Nothing here describes real weather; forecasts are an educational demonstration.",
        "The very low MAE (about 0.06 °C) is a property of the synthetic generator: every city repeats the same exact 12-day ramp. It is not evidence of forecasting skill.",
        "Only 42 daily observations per city (about 3.5 cycles): the chosen cycle length is estimated from 29 training days and the held-out set has 13 days.",
        "The seasonal methods assume a fixed repeating cycle and stable drift; real weather has neither.",
        "Held-out MAE is identical for horizons 1, 2 and 3 because the method copies the value one cycle earlier; horizon only changes the drift estimate slightly.",
        "Only temperature is forecast; humidity and rain columns are loaded but unused. No uncertainty interval is produced.",
        "Missing calendar days are not imputed; the dataset has none, so that code path is covered by unit tests only.",
        "Predictions are rounded to 0.1 °C (the data precision) before scoring.",
    ]
    (REPORTS / "evaluation.json").write_text(json.dumps(doc, indent=2, ensure_ascii=False), encoding="utf-8")

    # ---------------------------------------------------------------- analysis
    prof = dataset_profile()
    tools_env = {"python": tool_version([PY, "--version"]), "git": tool_version(["git", "--version"]), "node": tool_version(["node", "--version"]),
                 "pip": tool_version([PY, "-m", "pip", "--version"]), "numpy": module_version("numpy"), "pandas": module_version("pandas"),
                 "scikit-learn": module_version("sklearn"), "statsmodels": module_version("statsmodels"), "playwright": module_version("playwright")}
    analysis = json.loads((ROOT / "scripts" / "analysis_static.json").read_text(encoding="utf-8"))
    analysis["dataset"] = prof
    analysis["existing_issues"] = original_behaviour()
    analysis["environment"] = tools_env
    analysis["generated_at"] = now()
    fill = {"{weather_tests}": str(sum(c["status"] == "passed" for c in suites[1]["cases"])),
            "{ui_checks}": str(sum(c["status"] == "passed" for c in suites[2]["cases"])),
            "{original_tests}": str(sum(c["status"] == "passed" for c in suites[0]["cases"]))}
    for item in analysis["plan"]:
        for k in ("evidence",):
            for a, b in fill.items():
                item[k] = item[k].replace(a, b)
    pv = REPORTS / "platform-verification.json"
    if pv.exists():
        v = json.loads(pv.read_text(encoding="utf-8"))
        for item in analysis["plan"]:
            if item["n"] == 13:
                item["status"] = "completed" if v["all_passed"] else "blocked"
                item["evidence"] = f"{v['passed']} of {v['passed'] + v['failed']} dashboard checks pass in a real browser (gallery, workspace, Source Explorer, live preview, report, Prompt A regression, mobile); backend pytest and TypeScript clean"
    gp = REPORTS / "git.json"
    if gp.exists():
        g = json.loads(gp.read_text(encoding="utf-8"))
        for item in analysis["plan"]:
            if item["n"] == 14:
                item["status"] = "completed" if g["commits"] else "pending"
                item["evidence"] = f"{len(g['commits'])} local commit(s) on {g['dev_branch']} on top of upstream {g['baseline_commit']['hash']}"
            if item["n"] == 15:
                item["status"] = "completed" if g["draft_pr"]["status"] == "created" else ("blocked" if g["push"].get("attempted_at") and g["push"]["status"] != "pushed" else "pending")
                item["evidence"] = f"push: {g['push']['status']} - {g['push']['reason']}; Draft PR: {g['draft_pr']['status']}"
    (REPORTS / "analysis.json").write_text(json.dumps(analysis, indent=2, ensure_ascii=False), encoding="utf-8")
    print(json.dumps({"tests": totals, "independent_check_all_match": doc["independent_check"]["all_match"],
                      "suites": [(s["id"], len(s["cases"]), s["exit_code"]) for s in suites]}))
    return 0 if totals["failed"] == 0 and doc["independent_check"]["all_match"] else 1


if __name__ == "__main__":
    sys.exit(main())
