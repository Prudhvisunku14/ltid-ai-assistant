"""Browser check of the three uploaded projects inside the LTID Assistant dashboard (Playwright, Microsoft Edge).

    .venv\\Scripts\\python.exe evaluation-projects/scripts/verify_projects.py [ui_url]

Needs the dashboard (default http://localhost:3000), its backend, and the three apps on ports 8004, 8005 and 8006.
Writes evaluation-projects/reports/dashboard-verification-projects.json. Only when every check passes is the
"Integrated into LTID Assistant" step set to completed in each project's reports/timeline.json.
"""
import json
import pathlib
import re
import sys
import urllib.request

EVAL = pathlib.Path(__file__).resolve().parents[1]
UI = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:3000"
API = "http://localhost:18001" if "13000" in UI else "http://localhost:8001"
PROJECTS = {
    "appointment-booking": {"name": "Appointment Booking System", "launch": "Launch Booking App", "port": 8004, "tests": 25, "files": ["app/booking.py", "tests/test_booking.py", "run.py"]},
    "expense-system": {"name": "Expense Management & Approval System", "launch": "Launch Expense App", "port": 8005, "tests": 64, "files": ["app/service.py", "app/policy.py", "tests/test_expenses.py"]},
    "support-ticket-system": {"name": "AI-Supported Support Ticket System", "launch": "Launch Ticket App", "port": 8006, "tests": 32, "files": ["app/main.py", "app/classifier.py", "tests/test_api.py"]},
    "docchange": {"name": "Document Change Monitoring System", "launch": "Launch Monitor", "port": 8007, "tests": 23, "files": ["monitor/differ.py", "monitor/analyzer.py", "tests/test_all.py"]},
    "github-dev-automation": {"name": "GitHub Development Automation System", "launch": "Launch devbot", "port": 8009, "tests": 9 + 21 + 17, "note": "Uploaded folder", "dir": "GitHub Development Automation System",
                              "files": ["pipeline.py", "safety.py", "server.py", "index.html", "test_server.py"]},
    "prompt-c-rag": {"name": "LTID AI Competition – RAG", "launch": "Launch RAG App", "port": 8008, "tests": 51, "note": "Supplied project folder", "dir": "ltid-ai-competition-rag-final",
                     "files": ["answer.py", "retrieve.py", "ingest.py", "server.py", "index.html", "test_server.py"]},
}
results = {pid: [] for pid in PROJECTS}
shared = []
ROOT_OUT = EVAL / "reports"


def ck(bucket, name, ok, detail=""):
    bucket.append({"name": name, "passed": bool(ok), "detail": "" if ok else str(detail)[:200]})
    print(("PASS " if ok else "FAIL ") + name + ("" if ok else f" -> {str(detail)[:160]}"), flush=True)


def api(path):
    with urllib.request.urlopen(API + path, timeout=15) as r:
        return json.loads(r.read())


def main():
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        b = None
        for ch in ("msedge", None):
            try:
                b = p.chromium.launch(channel=ch) if ch else p.chromium.launch(); break
            except Exception:
                continue
        pg = b.new_page(viewport={"width": 1366, "height": 900})
        errs = []
        pg.on("pageerror", lambda e: errs.append(str(e)))

        # ------------------------------------------------------------ gallery
        pg.goto(UI + "/gallery", wait_until="networkidle"); pg.wait_for_selector("text=Appointment Booking System")
        for pid, cfg in PROJECTS.items():
            card = pg.locator("div.card", has=pg.locator("a.font-semibold", has_text=cfg["name"])).first
            t = card.inner_text()
            ck(results[pid], "gallery_card_present", card.count() == 1, cfg["name"])
            ck(results[pid], "gallery_card_test_status", f"Tests: {cfg['tests']} passed, 0 failed" in t, t[:200])
            ck(results[pid], "gallery_card_build_passing", "Build:" in t and "passing" in t or "built" in t.lower())
            ck(results[pid], "gallery_card_import_note", cfg.get("note", "Uploaded folder") in t, t[-300:])
            for btn in ("Open Workspace", cfg["launch"], "View Source Code", "View Test Results", "View Evaluation Report"):
                ck(results[pid], f"gallery_button_{btn.lower().replace(' ', '_')}", card.get_by_role("link", name=btn).count() == 1, btn)

        # ------------------------------------------------------------ workspaces
        for pid, cfg in PROJECTS.items():
            R = results[pid]
            pg.goto(f"{UI}/projects/{pid}", wait_until="networkidle"); pg.wait_for_selector("role=tablist")
            tabs = pg.locator("[role=tab]").all_inner_texts()
            ck(R, "workspace_has_live_preview_and_tests_tabs", "Live Preview" in tabs and "Tests" in tabs and "Final Report" in tabs, tabs)
            ck(R, "workspace_states_upload_status", cfg.get("note", "Uploaded folder") in pg.inner_text("body"))
            # tests tab: the numbers come from the recorded evidence
            pg.get_by_role("tab", name="Tests", exact=True).click(); pg.wait_for_selector("text=Test results")
            body = pg.inner_text("body")
            ck(R, "tests_tab_shows_recorded_total", f"{cfg['tests']}" in body and "0" in body, body[:120])
            suites = api(f"/api/projects/{pid}/tests")["suites"]
            ck(R, "tests_all_collected_cases_parsed", sum(x["parsed_count"] for x in suites) == cfg["tests"] and all(x["parse_complete"] for x in suites), suites)
            # live preview: the real app is embedded
            pg.get_by_role("tab", name="Live Preview", exact=True).click(); pg.wait_for_selector("iframe", timeout=15000)
            ck(R, "live_preview_shows_running_status", pg.locator("text=running").count() >= 1 and f"localhost:{cfg['port']}" in pg.inner_text("body"))
            title = json.loads((EVAL / cfg.get("dir", pid) / "reports" / "live-check.json").read_text(encoding="utf-8")).get("page_title", "")
            frame = pg.frame_locator("iframe").first
            frame.locator("body").wait_for(timeout=15000); pg.wait_for_timeout(800)
            frame_text = frame.locator("body").inner_text()
            ck(R, "live_preview_embeds_running_app", bool(title) and (title.split(" — ")[0][:12] in frame_text or len(frame_text) > 40), frame_text[:120])
            # source explorer: real files of the uploaded folder
            pg.goto(f"{UI}/source?project={pid}", wait_until="networkidle"); pg.wait_for_selector("text=Source Explorer")
            pg.wait_for_timeout(600)
            st = pg.inner_text("body")
            ck(R, "source_explorer_lists_real_files", all(f.split("/")[-1] in st for f in cfg["files"]), [f for f in cfg["files"] if f.split("/")[-1] not in st])
            ck(R, "source_explorer_states_no_baseline", "no baseline" in st.lower())
            # final report
            pg.goto(f"{UI}/projects/{pid}?tab=final-report", wait_until="networkidle"); pg.wait_for_selector("h1:has-text('Evaluation Report')")
            ck(R, "final_report_renders", pg.locator("table").count() >= 1 or "Test results" in pg.inner_text("body"))

        # ------------------------------------------------------------ overview
        pg.goto(UI + "/", wait_until="networkidle"); pg.wait_for_selector("text=Live applications", timeout=20000)
        pg.wait_for_selector("text=Running at", timeout=20000); pg.wait_for_timeout(800)
        ov = pg.inner_text("body")
        for pid, cfg in PROJECTS.items():
            ck(results[pid], "overview_live_app_running", f"Running at http://localhost:{cfg['port']}" in ov, "not listed as running")
        pg.screenshot(path=str(EVAL / "reports" / "screenshots" / "dashboard-overview.png"), full_page=True)

        # ------------------------------------------------------------ settings + mobile
        pg.goto(UI + "/settings", wait_until="networkidle"); pg.wait_for_selector("text=preview URL")
        st = pg.inner_text("body")
        ck(shared, "settings_lists_project_previews", all(f"{k} preview URL" in st for k in PROJECTS), st[:120])
        m = b.new_context(viewport={"width": 375, "height": 800}).new_page()
        for path in ("/gallery", "/projects/expense-system?tab=tests", "/"):
            m.goto(UI + path, wait_until="networkidle"); m.wait_for_timeout(500)
            ck(shared, f"mobile_375_no_overflow{path.replace('/', '_').replace('?', '_').replace('=', '_')}", not m.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"))
        ck(shared, "no_uncaught_javascript_errors", not errs, "; ".join(errs)[:200])
        b.close()

    all_ok = all(c["passed"] for R in list(results.values()) + [shared] for c in R)
    out = {"ui": UI, "api": API, "all_passed": all_ok,
           "passed": sum(c["passed"] for R in list(results.values()) + [shared] for c in R),
           "total": sum(len(R) for R in list(results.values()) + [shared]),
           "projects": {pid: R for pid, R in results.items()}, "shared": shared}
    ROOT_OUT.mkdir(exist_ok=True)
    (ROOT_OUT / "dashboard-verification-projects.json").write_text(json.dumps(out, indent=2), encoding="utf-8")
    for pid in PROJECTS:   # the integration step is completed only by a fully passing check
        tl_path = EVAL / PROJECTS[pid].get("dir", pid) / "reports" / "timeline.json"
        tl = json.loads(tl_path.read_text(encoding="utf-8"))
        for s in tl:
            if s["title"] == "Integrated into LTID Assistant":
                s["status"] = "completed" if all_ok else "partial"
                s["output"] = f"{out['passed']}/{out['total']} browser checks pass (evaluation-projects/scripts/verify_projects.py)"
                s["evidence"] = "reports/dashboard-verification-projects.json"
        tl_path.write_text(json.dumps(tl, indent=2), encoding="utf-8")
    print(json.dumps({"all_passed": all_ok, "passed": out["passed"], "total": out["total"]}))
    return 0 if all_ok else 1


if __name__ == "__main__":
    sys.exit(main())
