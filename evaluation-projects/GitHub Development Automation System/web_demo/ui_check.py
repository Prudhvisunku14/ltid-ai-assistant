"""Real browser checks of the devbot web interface (Playwright driving the installed Microsoft Edge / Chrome).

Starts its own server on a spare port WITHOUT any credentials in its environment. The "GPT" path is pointed at a tiny local
fake OpenAI endpoint that always answers 401, so the check proves the key prompt and the error handling, NOT a live model.
Saves screenshots and prints a JSON result on the last stdout line (read by evaluation-projects/scripts/collect_external.py).
    python web_demo/ui_check.py      (needs: pip install playwright)
"""
import json
import os
import pathlib
import subprocess
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer

HERE = pathlib.Path(__file__).resolve().parent
SHOTS = HERE.parent / "reports" / "screenshots"
PORT = 8019
BASE = f"http://127.0.0.1:{PORT}"
FAKE_KEY = "sk-browser-check-UNIQUE-0123456789abcdef"


class Fake401(BaseHTTPRequestHandler):
    def log_message(self, *a):
        pass

    def do_POST(self):
        self.rfile.read(int(self.headers.get("Content-Length") or 0))
        body = json.dumps({"error": {"message": "Incorrect API key provided: " + self.headers.get("Authorization", "")[7:],
                                     "code": "invalid_api_key"}}).encode()
        self.send_response(401)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)


def main():
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(parents=True, exist_ok=True)
    fake = HTTPServer(("127.0.0.1", 0), Fake401)
    threading.Thread(target=fake.serve_forever, daemon=True).start()
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "GITHUB_TOKEN", "OPENAI_BASE_URL")}
    env.update({"HOST": "127.0.0.1", "PORT": str(PORT), "PYTHONDONTWRITEBYTECODE": "1",
                "DEVBOT_WEB_OPENAI_BASE_URL": f"http://127.0.0.1:{fake.server_address[1]}/v1"})
    proc = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cases, errors = [], []

    def until(cond, timeout=60, what="condition"):
        end = time.time() + timeout
        while time.time() < end:
            try:
                if cond():
                    return
            except Exception:
                pass
            time.sleep(0.15)
        raise RuntimeError("timed out waiting for " + what)

    def check(name, ok, detail=""):
        cases.append({"name": name, "class": "BrowserUI", "status": "passed" if ok else "failed", "detail": "" if ok else str(detail)[:200]})

    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "/api/health", timeout=2).read()
                break
            except Exception:
                time.sleep(0.3)
        else:
            raise RuntimeError("server did not start")
        with sync_playwright() as p:
            browser = None
            for ch in ("msedge", "chrome", None):
                try:
                    browser = p.chromium.launch(channel=ch) if ch else p.chromium.launch()
                    break
                except Exception:
                    continue
            if browser is None:
                raise RuntimeError("no Chromium-based browser available")
            pg = browser.new_page(viewport={"width": 1280, "height": 900})
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(BASE + "/")
            until(lambda: len(pg.input_value("#request")) > 10, 20, "request prefill")
            body = pg.inner_text("body")
            check("page_states_dry_run_and_never_merges", "Dry-run only" in body and "never merges or deploys" in body)
            check("offline_demo_is_default_and_asks_for_no_key", pg.is_checked("#mode-mock") and not pg.is_visible("#openai-key"))
            pg.check("#mode-openai")
            check("gpt_mode_asks_for_the_users_api_key_in_a_masked_field",
                  pg.is_visible("#openai-key") and pg.get_attribute("#openai-key", "type") == "password" and pg.input_value("#model") == "gpt-4o-mini")
            pg.screenshot(path=str(SHOTS / "devbot-key-prompt.png"), full_page=True)

            pg.click("#run-btn")
            pg.wait_for_selector("#form-error:not([hidden])")
            check("gpt_without_key_is_refused_with_clear_message", "OpenAI API key" in pg.inner_text("#form-error"), pg.inner_text("#form-error"))

            pg.fill("#openai-key", FAKE_KEY)
            pg.click("#run-btn")
            until(lambda: pg.is_visible("#run-error"), 30, "run error")
            err = pg.inner_text("#run-error")
            check("rejected_key_shows_friendly_error_and_never_displays_the_key",
                  "rejected the API key" in err and FAKE_KEY not in pg.inner_text("body") and FAKE_KEY not in pg.content(), err)
            check("key_is_not_in_url_or_browser_storage",
                  FAKE_KEY not in pg.url and FAKE_KEY not in pg.evaluate("JSON.stringify([Object.entries(localStorage), Object.entries(sessionStorage), document.cookie])"))
            pg.click("#clear-key")
            check("clear_key_button_empties_the_field", pg.input_value("#openai-key") == "")

            pg.check("#src-github"); pg.fill("#repo-url", "https://github.com/octocat/Hello-World"); pg.fill("#openai-key", FAKE_KEY)
            pg.click("#run-btn")
            until(lambda: "trust" in pg.inner_text("#form-error"), 20, "trust message")
            check("github_repo_requires_trust_confirmation", "trust" in pg.inner_text("#form-error"), pg.inner_text("#form-error"))
            pg.fill("#repo-url", "C:\\Users\\someone\\project"); pg.check("#trust"); pg.click("#run-btn")
            until(lambda: "github.com" in pg.inner_text("#form-error"), 20, "bad url message")
            check("local_paths_are_not_accepted", "local paths are not" in pg.inner_text("#form-error"))
            pg.check("#src-demo"); pg.fill("#openai-key", "")

            pg.check("#mode-mock")
            pg.click("#analyze-btn"); pg.wait_for_selector("#analysis-card:not([hidden])")
            a = pg.inner_text("#analysis")
            check("analyse_shows_languages_and_test_command", "Python" in a and "unittest" in a, a[:200])

            pg.click("#run-btn")
            pg.wait_for_selector("#approval:not([hidden])", timeout=60000)
            check("plan_is_shown_and_nothing_is_edited_before_approval", "Files to change" in pg.inner_text("#plan") and "Step 6" not in pg.inner_text("#log"))
            pg.screenshot(path=str(SHOTS / "devbot-plan-approval.png"), full_page=True)
            pg.click("#reject-btn")
            pg.wait_for_selector("#result:not([hidden])", timeout=30000)
            check("rejecting_the_plan_changes_nothing", "did not approve" in pg.inner_text("#result-box") and "Step 6" not in pg.inner_text("#log"))

            pg.click("#run-btn"); pg.wait_for_selector("#approval:not([hidden])", timeout=60000)
            pg.click("#approve-btn")
            until(lambda: pg.inner_text("#run-status") == "finished", 90, "run to finish")
            res = pg.inner_text("#result")
            check("approved_run_repairs_tests_and_prepares_a_draft_pr_preview",
                  "Done" in res and "passing" in res and "Repair attempts" in res and "1" in pg.inner_text("#result-kv"), res[:300])
            pg.evaluate("document.querySelectorAll('#result details').forEach(d => d.open = true)")
            check("diff_and_draft_pr_preview_are_shown_as_text",
                  "BULK_THRESHOLD" in pg.inner_text("#diff") and "Human review required" in pg.inner_text("#pr"))
            check("log_confirms_original_unchanged_and_no_merge",
                  "original repository unchanged" in pg.inner_text("#log") and "never merges" in pg.inner_text("#log"))
            pg.screenshot(path=str(SHOTS / "devbot-result.png"), full_page=True)

            m = browser.new_page(viewport={"width": 375, "height": 800})
            m.on("pageerror", lambda e: errors.append("mobile: " + str(e)))
            m.goto(BASE + "/"); until(lambda: len(m.input_value("#request")) > 10, 20, "request prefill")
            m.check("#mode-openai")
            check("mobile_375_no_horizontal_overflow", not m.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"))
            m.screenshot(path=str(SHOTS / "devbot-mobile.png"), full_page=True)
            check("no_uncaught_javascript_errors", not errors, "; ".join(errors))
            browser.close()
    except Exception as exc:
        check("ui_check_script_completed", False, f"{type(exc).__name__}: {exc}")
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
        fake.shutdown()
    print(json.dumps({"cases": cases}))
    return 0 if all(c["status"] == "passed" for c in cases) else 1


if __name__ == "__main__":
    sys.exit(main())
