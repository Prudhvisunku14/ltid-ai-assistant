"""Verifies the LTID Assistant integration of Prompt B (and that Prompt A still works) in a real browser.

    python verify_platform.py --ui http://localhost:3000 --api http://localhost:8001 [--shots DIR] [--skip-builds]

Needs the dashboard, backend, Prompt A preview and the Prompt B weather server to be running. Writes
reports/platform-verification.json. Every check records what it observed; nothing is assumed.
"""
import argparse
import datetime as dt
import json
import pathlib
import re
import subprocess
import sys
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
PLATFORM = ROOT.parents[1]
ap = argparse.ArgumentParser()
ap.add_argument("--ui", default="http://localhost:3000")
ap.add_argument("--api", default="http://localhost:8001")
ap.add_argument("--shots", default=None)
ap.add_argument("--skip-builds", action="store_true")
args = ap.parse_args()
UI, API = args.ui.rstrip("/"), args.api.rstrip("/")
SHOTS = pathlib.Path(args.shots) if args.shots else None
if SHOTS: SHOTS.mkdir(parents=True, exist_ok=True)
checks, errors = [], []


def check(name, ok, detail=""):
    checks.append({"name": name, "passed": bool(ok), "detail": str(detail)[:300]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f"  -> {detail}"), flush=True)


def api(path):
    with urllib.request.urlopen(API + path, timeout=15) as r:
        return json.loads(r.read())


def http_status(url):
    try:
        with urllib.request.urlopen(url, timeout=15) as r:
            return r.status, r.read(8)
    except Exception as exc:
        return getattr(exc, "code", 0), b""


def run(cmd, cwd):
    p = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True, encoding="utf-8", errors="replace", shell=sys.platform == "win32")
    return p.returncode, (p.stdout + p.stderr)


def main():
    from playwright.sync_api import sync_playwright
    if not args.skip_builds:
        code, out = run([sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider"], PLATFORM / "backend")
        last = [l for l in out.strip().splitlines() if "passed" in l or "failed" in l][-1:] or [out[-120:]]
        check("backend_pytest_all_pass", code == 0, last[0])
        code, out = run("npx tsc --noEmit", PLATFORM / "frontend")
        check("frontend_typescript_clean", code == 0, out[-200:])
    with sync_playwright() as p:
        browser = None
        for ch in ("msedge", "chrome", None):
            try:
                browser = p.chromium.launch(channel=ch) if ch else p.chromium.launch(); break
            except Exception:
                continue
        ctx = browser.new_context(viewport={"width": 1366, "height": 900})
        pg = ctx.new_page()
        pg.on("pageerror", lambda e: errors.append(str(e)))
        pg.on("console", lambda m: errors.append("console: " + m.text) if m.type == "error" and "Failed to load resource" not in m.text else None)

        # ------------------------------------------------------------------ gallery
        pg.goto(UI + "/gallery"); pg.wait_for_selector("text=Prompt B — Weather Forecasting Demo")
        names = pg.locator("a.font-semibold").all_inner_texts()
        check("gallery_lists_prompt_a_and_prompt_b_side_by_side", names[:2] == ["Prompt A — Website Development", "Prompt B — Weather Forecasting Demo"], names[:3])
        card = pg.locator("div.card", has=pg.locator("a.font-semibold", has_text="Prompt B")).first
        txt = card.inner_text()
        for needle in ("Eastbay City Lab", "Data Science / Machine Learning", "educational temperature forecasting application", "Synthetic dataset", "Build:", "Tests:", "Last updated:",
                       "stdlib only", "unittest", "LTID-rep/ltid-ai-competition-weather", "Imported ZIP snapshot"):
            check(f"prompt_b_card_shows_{needle.strip(':').replace(' ', '_').lower()}", needle.lower() in txt.lower(), txt[:200] if needle.lower() not in txt.lower() else "")
        for b in ("Open Workspace", "Launch Weather Demo", "View Source Code", "View Test Results", "View Evaluation Report"):
            check(f"prompt_b_card_button_{b.replace(' ', '_').lower()}", card.get_by_role("link", name=b).count() == 1)
        check("prompt_b_card_has_thumbnail", card.locator("img").count() == 1 and card.locator("img").evaluate("i => i.complete && i.naturalWidth > 100"))
        check("prompt_a_card_still_present_with_buttons", pg.locator("div.card", has=pg.locator("a.font-semibold", has_text="Prompt A")).first.get_by_role("link", name="Open Application").count() == 1)
        if SHOTS: pg.screenshot(path=str(SHOTS / "gallery.png"), full_page=True)

        # ------------------------------------------------------------------ Prompt B workspace
        card.get_by_role("link", name="Open Workspace").click(); pg.wait_for_selector("role=tablist")
        tabs = pg.locator("[role=tab]").all_inner_texts()
        check("prompt_b_workspace_has_all_tabs", all(t in tabs for t in ("Overview", "Requirements", "Repository Analysis", "Tool Selection", "Data & Method", "Implementation Plan", "Code Changes", "Live Preview", "Tests", "Evaluation", "GitHub / Pull Request", "Final Report")), tabs)
        check("workspace_labels_zip_snapshot", "Imported ZIP snapshot" in pg.inner_text("body"))
        check("workspace_overview_shows_synthetic_disclaimer", "not a real weather forecast" in pg.inner_text("body"))

        def tab(name, wait):
            pg.get_by_role("tab", name=name, exact=True).click(); pg.wait_for_selector(wait, timeout=15000)
        tab("Requirements", "text=Original requirements"); check("requirements_tab_reads_drive_docx", "Google Drive" in pg.inner_text("body") and "Inputs" in pg.inner_text("body"))
        tab("Repository Analysis", "text=Existing implementation"); body = pg.inner_text("body")
        check("repository_tab_shows_zip_snapshot_and_real_issues", "Imported ZIP snapshot" in body and "KeyError" in body and "ValueError" in body)
        tab("Tool Selection", "text=Detected on the build machine"); check("tool_tab_lists_selected_and_rejected_tools", "Not selected" in pg.inner_text("body") and "Selected" in pg.inner_text("body"))
        tab("Data & Method", "text=Available data"); body = pg.inner_text("body")
        check("data_tab_shows_actual_dataset_facts", "126" in body and "weather_history.csv" in body and "Osaka" in body and "2026-08-01" in body)
        check("method_tab_explains_method_and_limits", "Seasonal naive with drift" in body and "Limitations" in body and "machine-learning" in body)
        check("architecture_diagram_has_all_8_stages", all(s in body for s in ("Synthetic dataset", "Data validation", "Data preprocessing", "Time-ordered train/evaluation split", "Forecasting method", "Temperature prediction", "MAE evaluation", "Weather demo interface")))
        if SHOTS: pg.screenshot(path=str(SHOTS / "b-data-method.png"), full_page=True)
        tab("Implementation Plan", "text=Verification evidence"); check("plan_table_has_15_numbered_tasks", pg.locator("table tbody tr").count() == 15, pg.locator("table tbody tr").count())
        tab("Code Changes", "text=Unified diff"); pg.wait_for_selector("text=weather_app/evaluation.py")
        check("code_changes_show_actual_diffs", "weather_app/data.py" in pg.inner_text("body") and "weather_app/core.py" in pg.inner_text("body"))
        tab("Tests", "text=Test results"); body = pg.inner_text("body")
        check("tests_tab_shows_real_suites", "Starter tests" in body and "test_06_invalid_horizon_is_rejected" in body and "Browser UI checks" in body)
        tab("GitHub / Pull Request", "text=Local commit history"); body = pg.inner_text("body")
        check("github_tab_is_truthful_about_unpushed_state", "not pushed" in body.lower() and "— (none exists)" in body and "Remote publication pending" in body and "ltid-assistant/prompt-b-weather" in body and "a7022f3" in body)
        tab("Final Report", "h1:has-text('Evaluation Report')"); body = pg.inner_text("body")
        check("report_tab_renders_17_sections_and_tables", all(f"{n}. " in body for n in range(1, 18)) and pg.locator("table").count() >= 10, pg.locator("table").count())
        check("report_download_links_present", all(pg.get_by_role("link", name=n).count() >= 1 for n in ("Download report (.md)", "Download report (.pdf)", "Evaluation JSON")))
        if SHOTS: pg.screenshot(path=str(SHOTS / "b-report.png"), full_page=True)

        # ------------------------------------------------------------------ evaluation dashboard
        tab("Evaluation", "text=Weather evaluation"); body = pg.inner_text("body")
        e = api("/api/projects/prompt-b/evaluation")
        check("evaluation_shows_actual_overall_mae", f"{e['evaluation']['overall']['mae']:.3f}" in body)
        check("evaluation_shows_six_demonstrations", all(c["case"].split(" – ")[0] in body for c in e["demonstrations"]["cases"]) and pg.locator("table", has_text="Day 1").first.locator("tbody tr").count() == 6)
        check("evaluation_shows_charts_tables_limitations", pg.locator(".recharts-wrapper").count() >= 4 and "Known limitations" in body and "Data validation results" in body and "synthetic" in body.lower())
        check("evaluation_lists_robustness_checks", pg.locator("table", has_text="Actual outcome").locator("tbody tr").count() == len(e["robustness_checks"]))
        if SHOTS: pg.screenshot(path=str(SHOTS / "b-evaluation.png"), full_page=True)
        check("evaluation_downloads_work", http_status(API + "/api/projects/prompt-b/evaluation/download")[0] == 200 and http_status(API + "/api/projects/prompt-b/report/download")[0] == 200 and http_status(API + "/api/projects/prompt-b/report/download.pdf")[1][:4] == b"%PDF")

        # ------------------------------------------------------------------ live preview (real running app)
        tab("Live Preview", "iframe")
        url = api("/api/projects/prompt-b/preview")["url"]
        check("preview_shows_local_url_and_controls", url in pg.inner_text("body") and all(pg.get_by_role("button", name=n).count() == 1 or pg.get_by_role("link", name=n).count() == 1 for n in ("Refresh", "New tab", "Full screen")))
        fr = pg.frame_locator("iframe[title='Prompt B weather demo']")
        fr.locator("#cities option").first.wait_for(state="attached", timeout=15000)
        fr.locator("#city").fill("Sapporo"); fr.locator("#days").select_option("2"); fr.locator("#go").click(); fr.locator(".day").nth(1).wait_for()
        shown = [t.replace("°C", "").strip() for t in fr.locator(".day .temp").all_inner_texts()]
        truth = [f"{d['predicted_temp_c']:.1f}" for d in json.loads(urllib.request.urlopen(url + "/api/forecast?city=Sapporo&days=2").read())["forecast"]]
        check("live_preview_runs_actual_weather_app_and_matches_api", shown == truth and len(shown) == 2, f"iframe={shown} api={truth}")
        fr.locator("#city").fill("Paris"); fr.locator("#go").click(); fr.locator("#form-error:not([hidden])").wait_for()
        check("live_preview_invalid_city_error_inside_iframe", "Unknown city" in fr.locator("#form-error").inner_text())
        pg.get_by_role("button", name="Refresh").click(); pg.wait_for_timeout(800)
        check("preview_refresh_reloads_iframe", pg.frame_locator("iframe[title='Prompt B weather demo']").locator("#city").count() == 1)
        pg.get_by_role("button", name="Full screen").click(); pg.wait_for_timeout(300)
        check("preview_full_screen_toggles", pg.locator("div.fixed.inset-0").count() == 1)
        pg.keyboard.press("Escape"); pg.wait_for_timeout(300)
        check("preview_full_screen_exits_with_escape", pg.locator("div.fixed.inset-0").count() == 0)
        if SHOTS: pg.screenshot(path=str(SHOTS / "b-live-preview.png"), full_page=True)

        # ------------------------------------------------------------------ shared pages with the project switcher
        pg.goto(UI + "/source?project=prompt-b"); pg.wait_for_selector("text=Source Explorer")
        pg.wait_for_selector("button:has-text('service.py')")
        check("source_explorer_defaults_to_prompt_b_when_requested", "weather_app/service.py" in pg.inner_text("body") or pg.locator("text=service.py").count() > 0)
        body = pg.inner_text("body")
        check("source_explorer_shows_actual_tree", all(f in body for f in ("forecast.py", "evaluation.py", "data.py", "test_evaluation.py", "app.js", "weather_history.csv")), body[:200])
        check("source_explorer_shows_added_modified_deleted_counts", "Added" in body and "Modified" in body and "Deleted" in body)
        pg.locator("button", has_text=re.compile(r"^core\.py$")).first.click(); pg.wait_for_selector("text=load_rows")
        pg.locator("button", has_text=re.compile(r"^diff$", re.I)).click(); pg.wait_for_selector("text=@@")
        check("source_explorer_shows_code_and_diff", "def load_rows" in pg.inner_text("body") and pg.locator("text=@@").count() > 0)
        pg.locator("button", has_text=re.compile(r"^original$", re.I)).click(); pg.wait_for_selector("text=Intentional baseline")
        check("source_explorer_original_view", True)
        pg.get_by_label("Changed files only").check(); pg.wait_for_timeout(200)
        check("changed_only_filter_hides_unchanged_files", pg.locator("button:has-text('TASK_PUBLIC.md')").count() == 0 and pg.locator("button:has-text('weather_history.csv')").count() == 0)
        if SHOTS: pg.screenshot(path=str(SHOTS / "b-source.png"), full_page=True)
        pg.get_by_role("tab", name="Prompt A — Website Development").click(); pg.wait_for_selector("button:has-text('index.html')")
        check("project_switcher_moves_to_prompt_a_source", pg.locator("button:has-text('app.js')").count() >= 1 and "project=prompt-a" in pg.url, pg.url)
        pg.get_by_role("tab", name="Prompt B — Weather Forecasting Demo").click(); pg.wait_for_selector("button:has-text('forecast.py')")
        check("project_switcher_returns_to_prompt_b", "project=prompt-b" in pg.url)

        # ------------------------------------------------------------------ Prompt A regression
        pg.goto(UI + "/projects/prompt-a"); pg.wait_for_selector("role=tablist")
        tabs_a = pg.locator("[role=tab]").all_inner_texts()
        check("prompt_a_workspace_tabs_unchanged", tabs_a == ["Overview", "Requirements", "Repository Analysis", "Tool Selection", "Implementation Plan", "Code Changes", "Live Preview", "Tests", "GitHub / Pull Request", "Final Report"], tabs_a)
        pg.get_by_role("tab", name="Tests", exact=True).click(); pg.wait_for_selector("text=Test results")
        ta = api("/api/projects/prompt-a/tests")["totals"]
        check("prompt_a_tests_tab_shows_recorded_results", f"{ta['passed']}" in pg.inner_text("body") and ta["failed"] == 0)
        pg.get_by_role("tab", name="Live Preview", exact=True).click(); pg.wait_for_selector("iframe")
        fa = pg.frame_locator("iframe[title='Prompt A live preview']")
        fa.locator("body").wait_for(); pg.wait_for_timeout(1000)
        check("prompt_a_live_preview_still_renders_website", "Northstar" in fa.locator("body").inner_text(), fa.locator("body").inner_text()[:80])
        pg.get_by_role("tab", name="Final Report", exact=True).click(); pg.wait_for_selector("h1:has-text('Evaluation Report')")
        check("prompt_a_report_still_renders", "Prompt A" in pg.inner_text("body"))
        pg.goto(UI + "/reports"); pg.wait_for_selector("text=Evaluation Reports"); check("reports_page_defaults_to_prompt_a", "Prompt A" in pg.inner_text("body") and "Weather Evaluation dashboard" not in pg.inner_text("body"))
        pg.goto(UI + "/reports?project=prompt-b"); pg.wait_for_selector("text=Weather evaluation"); check("reports_page_prompt_b_has_dashboard_and_report_toggle", pg.get_by_role("tab", name="Final report").count() == 1)
        pg.goto(UI + "/tests"); pg.wait_for_selector("text=Test results"); check("tests_page_defaults_to_prompt_a", "Node" in pg.inner_text("body") or "Playwright" in pg.inner_text("body") or "Python" in pg.inner_text("body"))
        pg.goto(UI + "/github?project=prompt-b"); pg.wait_for_selector("text=Local commit history"); check("github_page_prompt_b", "ltid-ai-competition-weather" in pg.inner_text("body"))
        pg.goto(UI + "/"); pg.wait_for_selector("text=Live applications"); pg.wait_for_selector("text=Running at", timeout=20000); body = pg.inner_text("body")
        check("overview_lists_prompt_b_live_app_and_cards", "Prompt B" in body and "Launch Weather Demo" in body and "Implemented projects" in body)
        pg.goto(UI + "/agent?project=prompt-b"); pg.wait_for_selector("text=Agent execution timeline"); check("agent_page_shows_prompt_b_timeline", "Push branch and open Draft PR" in pg.inner_text("body"))
        pg.goto(UI + "/gallery?q=weather"); pg.wait_for_selector("text=Prompt B"); check("gallery_search_finds_prompt_b", pg.locator("a.font-semibold").count() == 1)

        # ------------------------------------------------------------------ mobile
        m = browser.new_context(viewport={"width": 375, "height": 800}).new_page()
        m.on("pageerror", lambda e: errors.append("mobile: " + str(e)))
        for label, path, wait in (("gallery", "/gallery", "text=Prompt B"), ("workspace_overview", "/projects/prompt-b", "role=tablist"), ("evaluation", "/projects/prompt-b?tab=evaluation", "text=Weather evaluation"),
                                  ("data_method", "/projects/prompt-b?tab=data-method", "text=Available data"), ("live_preview", "/projects/prompt-b?tab=live-preview", "iframe"), ("report", "/projects/prompt-b?tab=final-report", "h1:has-text('Evaluation Report')")):
            m.goto(UI + path); m.wait_for_selector(wait); m.wait_for_timeout(500)
            check(f"mobile_375_{label}_no_page_overflow", not m.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"), m.evaluate("document.documentElement.scrollWidth"))
            if SHOTS: m.screenshot(path=str(SHOTS / f"mobile-{label}.png"), full_page=True)
        check("no_uncaught_javascript_errors_in_dashboard", not errors, "; ".join(errors)[:250])
        browser.close()
    out = {"ran_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"), "ui": UI, "api": API,
           "all_passed": all(c["passed"] for c in checks), "passed": sum(c["passed"] for c in checks), "failed": sum(not c["passed"] for c in checks), "checks": checks}
    (ROOT / "reports" / "platform-verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    print(json.dumps({k: out[k] for k in ("all_passed", "passed", "failed")}))
    return 0 if out["all_passed"] else 1


if __name__ == "__main__":
    sys.exit(main())
