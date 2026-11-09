"""Real browser checks of the Prompt B weather demo (Playwright driving the installed Microsoft Edge).

Starts the demo server itself on a spare port, drives the actual UI, cross-checks what the page shows against the
JSON API, captures screenshots and prints a JSON result on stdout (consumed by run_evidence.py).

    .venv\\Scripts\\python.exe evaluation-projects/prompt-b-weather/scripts/ui_check.py
Requires: pip install playwright  (uses the system Edge/Chrome via channel=, no browser download).
"""
import json
import pathlib
import subprocess
import sys
import time
import urllib.request

ROOT = pathlib.Path(__file__).resolve().parents[1]
SRC = ROOT / "source"
SHOTS = ROOT / "reports" / "screenshots"
PORT = 8012
BASE = f"http://127.0.0.1:{PORT}"
DISCLAIMER = "Educational demonstration using synthetic observations – not a real weather forecast."


def api(path):
    with urllib.request.urlopen(BASE + path, timeout=10) as r:
        return json.loads(r.read())


def main():
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(parents=True, exist_ok=True)
    proc = subprocess.Popen([sys.executable, "-m", "weather_app", "--serve", "--port", str(PORT)], cwd=SRC,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cases = []
    page_errors = []

    def check(name, ok, detail=""):
        cases.append({"name": name, "class": "BrowserUI", "status": "passed" if ok else "failed", "detail": detail})

    try:
        for _ in range(50):
            try:
                api("/api/health"); break
            except Exception:
                time.sleep(0.2)
        else:
            raise RuntimeError("demo server did not start")
        with sync_playwright() as p:
            browser = None
            for channel in ("msedge", "chrome", None):
                try:
                    browser = p.chromium.launch(channel=channel) if channel else p.chromium.launch(); break
                except Exception:
                    continue
            if browser is None:
                raise RuntimeError("no Chromium-based browser available for Playwright")
            ctx = browser.new_context(viewport={"width": 1280, "height": 800})
            pg = ctx.new_page()
            pg.on("pageerror", lambda e: page_errors.append(str(e)))
            pg.goto(BASE + "/")
            pg.wait_for_selector("#cities option", state="attached")

            check("page_shows_synthetic_disclaimer", DISCLAIMER in pg.inner_text("body"))
            ui_cities = pg.eval_on_selector_all("#cities option", "els => els.map(e => e.value)")
            check("city_options_come_from_dataset", ui_cities == api("/api/cities")["cities"] and len(ui_cities) >= 2, str(ui_cities))
            check("horizon_options_are_1_2_3", pg.eval_on_selector_all("#days option", "els => els.map(e => e.value)") == ["1", "2", "3"])

            for city in ("Tokyo", "Sapporo"):
                for days in (1, 2, 3):
                    pg.fill("#city", city)
                    pg.select_option("#days", str(days))
                    pg.click("#go")
                    pg.wait_for_function(f"document.querySelectorAll('.day').length === {days} && document.querySelector('#forecast-out table')")
                    shown_cards = [t.replace("°C", "").strip() for t in pg.locator(".day .temp").all_inner_texts()]
                    shown_rows = [r.split("\t")[2].replace("°C", "").strip() for r in pg.locator("#forecast-out table tbody tr").all_inner_texts()]
                    truth = [f"{d['predicted_temp_c']:.1f}" for d in api(f"/api/forecast?city={city}&days={days}")["forecast"]]
                    check(f"forecast_{city.lower()}_{days}day_ui_matches_api", shown_cards == truth and shown_rows == truth,
                          f"cards={shown_cards} table={shown_rows} api={truth}")
                    if city == "Tokyo" and days == 3:
                        pg.evaluate("window.scrollTo(0,0)")
                        pg.screenshot(path=str(SHOTS / "desktop-1280-fold.png"))
                        pg.screenshot(path=str(SHOTS / "desktop-1280-full.png"), full_page=True)
                        check("chart_is_rendered", pg.locator("#forecast-out svg.chart").count() == 1 and pg.locator("#forecast-out svg.chart circle").count() >= 17)
                        check("method_and_disclaimer_in_result", "Seasonal naive" in pg.inner_text("#forecast-out") and DISCLAIMER in pg.inner_text("#forecast-out"))

            pg.fill("#city", "Paris"); pg.click("#go")
            pg.wait_for_selector("#form-error:not([hidden])")
            check("invalid_city_shows_clear_error", "Unknown city 'Paris'" in pg.inner_text("#form-error") and "Tokyo" in pg.inner_text("#form-error"))
            check("invalid_city_clears_previous_forecast", pg.locator(".day").count() == 0)
            pg.fill("#city", "<img src=x onerror=window.__xss=1>"); pg.click("#go"); pg.wait_for_selector("#form-error:not([hidden])")
            check("html_in_city_is_escaped", pg.locator("#form-error img").count() == 0 and not pg.evaluate("window.__xss === 1"))
            pg2 = ctx.new_page(); pg2.goto(BASE + "/?city=Tokyo&days=9"); pg2.wait_for_selector("#form-error:not([hidden])")
            check("invalid_horizon_via_url_shows_error", "Unsupported forecast horizon" in pg2.inner_text("#form-error"))
            pg2.close()

            pg.click("#tab-evaluation"); pg.wait_for_selector("#eval-out table")
            pg.select_option("#ev-city", "Tokyo")
            pg.wait_for_function("document.querySelector('#eval-out').innerText.includes('Training observations')")
            e = api("/api/evaluation?city=Tokyo")
            txt = pg.inner_text("#eval-out")
            check("evaluation_tab_shows_split_counts", f"Training observations\n{e['split']['train_count']}" in txt and f"Evaluation observations\n{e['split']['evaluation_count']}" in txt)
            check("evaluation_tab_shows_pooled_mae_from_api", f"{e['metrics']['pooled']['mae']:.3f}" in txt)
            rows = pg.locator("#eval-out table").last.locator("tbody tr").count()
            check("evaluation_table_row_count_equals_heldout_count", rows == e["split"]["evaluation_count"], str(rows))
            pg.evaluate("window.scrollTo(0,0)")
            pg.screenshot(path=str(SHOTS / "desktop-1280-evaluation.png"), full_page=True)

            pg.click("#tab-demo"); pg.wait_for_selector("#demo-out article")
            check("six_demonstration_cards", pg.locator("#demo-out article").count() == 6)
            pg.screenshot(path=str(SHOTS / "desktop-1280-demo.png"), full_page=True)
            pg.click("#tab-data"); pg.wait_for_selector("#data-out table")
            check("data_tab_lists_all_cities", all(c in pg.inner_text("#data-out") for c in ui_cities))

            m = browser.new_context(viewport={"width": 375, "height": 800}, device_scale_factor=2).new_page()
            m.on("pageerror", lambda e: page_errors.append(str(e)))
            m.goto(BASE + "/?city=Osaka&days=3"); m.wait_for_selector(".day")
            check("mobile_375_no_horizontal_overflow", not m.evaluate("document.documentElement.scrollWidth > window.innerWidth"))
            m.screenshot(path=str(SHOTS / "mobile-375-full.png"), full_page=True)
            m.screenshot(path=str(SHOTS / "mobile-375-fold.png"))
            m.click("#tab-evaluation"); m.wait_for_selector("#eval-out table")
            check("mobile_375_evaluation_no_page_overflow", not m.evaluate("document.documentElement.scrollWidth > window.innerWidth"))
            m.screenshot(path=str(SHOTS / "mobile-375-evaluation.png"), full_page=True)
            check("no_uncaught_javascript_errors", not page_errors, "; ".join(page_errors))
            browser.close()
    except Exception as exc:                                  # a crash of the check itself is a failure, not a silent pass
        check("ui_check_script_completed", False, f"{type(exc).__name__}: {exc}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
    print(json.dumps({"cases": cases}))
    return 0 if all(c["status"] == "passed" for c in cases) else 1


if __name__ == "__main__":
    sys.exit(main())
