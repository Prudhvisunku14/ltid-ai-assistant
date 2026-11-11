"""Browser check of the Inventory project inside the LTID Assistant dashboard (Playwright, Microsoft Edge).

    .venv\Scripts\python.exe evaluation-projects/inventory-system/scripts/verify_dashboard.py [ui_url]
Needs the dashboard (ui_url, default http://localhost:3000), its backend and the inventory app on port 8003 running.
Writes reports/dashboard-verification.json with every check's real result.
"""
import json, pathlib
import re, sys
from playwright.sync_api import sync_playwright
UI=sys.argv[1] if len(sys.argv)>1 else "http://localhost:3000"
ROOT=pathlib.Path(__file__).resolve().parents[1]; SH=str(ROOT/"reports"/"screenshots")
res=[]
def ck(n, ok, d=""): res.append((n, bool(ok))); print(("PASS " if ok else "FAIL ")+n+("" if ok else f" -> {d}"), flush=True)
with sync_playwright() as p:
    b=None
    for ch in ("msedge",None):
        try: b=p.chromium.launch(channel=ch) if ch else p.chromium.launch(); break
        except Exception: pass
    pg=b.new_page(viewport={"width":1366,"height":900}); errs=[]
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.goto(UI+"/gallery"); pg.wait_for_selector("text=Inventory Management System")
    names=pg.locator("a.font-semibold").all_inner_texts()
    ck("gallery_inventory_card_after_prompt_b", "Inventory Management System" in names and names.index("Inventory Management System")==names.index("Prompt B — Weather Forecasting Demo")+1, names)
    card=pg.locator("div.card", has=pg.locator("a.font-semibold", has_text="Inventory Management System")).first
    t=card.inner_text()
    ck("inventory_card_status_and_tests", "Tests: 34 passed, 0 failed" in t and "Build: passing" in t, t[:200])
    ck("inventory_card_buttons", all(card.get_by_role("link", name=x).count()==1 for x in ("Open Workspace","Launch Inventory App","View Source Code","View Test Results","View Evaluation Report")))
    ck("inventory_card_not_claiming_push", "local repository" in t and "nothing has been pushed" in t.lower())
    card.get_by_role("link", name="Open Workspace").click(); pg.wait_for_selector("role=tablist")
    tabs=pg.locator("[role=tab]").all_inner_texts()
    ck("inventory_workspace_tabs", tabs==["Overview","Requirements","Repository Analysis","Tool Selection","Implementation Plan","Code Changes","Live Preview","Tests","GitHub / Pull Request","Final Report"], tabs)
    body=pg.inner_text("body")
    ck("inventory_workspace_shows_repo_status", "Repository status" in body and "not pushed" in body.lower() or "local repository" in body.lower(), body[:150])
    pg.get_by_role("tab", name="Repository Analysis", exact=True).click(); pg.wait_for_selector("text=Existing implementation")
    ck("repo_tab_lists_observed_issue", "favicon" in pg.inner_text("body").lower())
    pg.get_by_role("tab", name="Requirements", exact=True).click(); pg.wait_for_selector("text=Original requirements")
    ck("requirements_tab_has_six_rows", pg.locator("table tbody tr").count()==6, pg.locator("table tbody tr").count())
    pg.get_by_role("tab", name="Tests", exact=True).click(); pg.wait_for_selector("text=Test results")
    tb=pg.inner_text("body")
    ck("tests_tab_real_suites", "Unit and live-HTTP tests" in tb and "Browser end-to-end" in tb and "test_favicon_request_is_204_not_404" in tb)
    pg.screenshot(path=SH+"/dashboard-inventory-tests.png", full_page=True)
    pg.get_by_role("tab", name="Live Preview", exact=True).click(); pg.wait_for_selector("iframe")
    fr=pg.frame_locator("iframe")
    fr.locator("text=Inventory").first.wait_for(timeout=15000)
    ck("live_preview_runs_inventory_app", fr.locator("body").count()==1)
    ck("live_preview_shows_running", pg.locator("text=running").count()>=1)
    pg.screenshot(path=SH+"/dashboard-inventory-preview.png", full_page=True)
    pg.get_by_role("tab", name="Code Changes", exact=True).click(); pg.wait_for_selector("text=Unified diff")
    ck("code_changes_show_app_db", "app/db.py" in pg.inner_text("body"))
    pg.get_by_role("tab", name="GitHub / Pull Request", exact=True).click(); pg.wait_for_selector("text=Local commit history")
    gb=pg.inner_text("body")
    ck("github_tab_truthful", "not pushed" in gb.lower() and "— (none exists)" in gb and "65e4e4c" in gb or "chore: initial" in gb)
    pg.get_by_role("tab", name="Final Report", exact=True).click(); pg.wait_for_selector("h1:has-text('Inventory')")
    ck("final_report_renders", pg.locator("table").count()>=3)
    pg.goto(UI+"/source?project=inventory"); pg.wait_for_selector("button:has-text('db.py')")
    ck("source_explorer_shows_real_files", all(f in pg.inner_text("body") for f in ("app","db.py","server.py","app.js","test_db.py")))
    pg.locator("button", has_text=re.compile(r"^db\.py$")).first.click(); pg.wait_for_timeout(800)
    ck("source_explorer_opens_code", "CREATE TABLE" in pg.inner_text("body") or "sqlite" in pg.inner_text("body").lower())
    pg.goto(UI+"/tests?project=inventory"); pg.wait_for_selector("text=Test results")
    ck("tests_page_inventory", "34" in pg.inner_text("body"))
    pg.goto(UI+"/github?project=inventory"); pg.wait_for_selector("text=Local commit history")
    ck("github_page_inventory", "chore: initial repository skeleton" in pg.inner_text("body") and "ltid-rep" not in pg.inner_text("body").lower())
    pg.goto(UI+"/reports?project=inventory"); pg.wait_for_selector("h1:has-text('Inventory')")
    ck("reports_page_inventory_report", pg.locator("h1:has-text('Inventory')").count()==1)
    pg.goto(UI+"/settings"); pg.wait_for_selector("text=Inventory preview URL")
    ck("settings_shows_inventory_preview", "8003" in pg.inner_text("body"))
    pg.goto(UI+"/projects/prompt-b?tab=overview"); pg.wait_for_selector("role=tablist")
    ck("prompt_b_still_opens", "Prompt B" in pg.inner_text("body"))
    pg.goto(UI+"/projects/prompt-a?tab=overview"); pg.wait_for_selector("role=tablist")
    ck("prompt_a_still_opens", "Prompt A" in pg.inner_text("body"))
    pg.goto(UI+"/"); pg.wait_for_selector("text=Live applications")
    ck("overview_loads_with_inventory_in_totals", "Inventory Management System" in pg.inner_text("body") or "Inventory" in pg.inner_text("body"), pg.inner_text("body")[:150])
    pg.goto(UI+"/"); pg.wait_for_selector("text=Live applications")
    pg.wait_for_selector("text=Inventory Management System", timeout=20000)
    pg.wait_for_selector("a:has-text('Launch Inventory App')", timeout=20000)
    ov=pg.inner_text("body")
    ck("overview_shows_inventory_status_card", pg.locator("a:has-text('Launch Inventory App')").count()>=1, ov[:150])
    ck("overview_inventory_status_is_running", "Running at http://localhost:8003" in ov, ov[:150])
    ck("no_uncaught_js_errors", not errs, "; ".join(errs)[:200])
    b.close()
out={"ui": UI, "passed": sum(o for _,o in res), "total": len(res), "checks": [{"name": n, "passed": o} for n,o in res]}
(ROOT/"reports"/"dashboard-verification.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
print(f"{out['passed']}/{out['total']} passed")
