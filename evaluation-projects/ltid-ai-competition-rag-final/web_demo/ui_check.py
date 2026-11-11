"""Real browser checks of the RAG web interface (Playwright driving the installed Microsoft Edge / Chrome).

Starts its own server on a spare port WITHOUT any LLM credentials, drives the real UI, saves screenshots and prints a JSON
result on the last stdout line (consumed by evaluation-projects/scripts/collect_external.py).
    python web_demo/ui_check.py      (needs: pip install playwright)
"""
import json
import os
import pathlib
import subprocess
import sys
import tempfile
import time
import urllib.request

HERE = pathlib.Path(__file__).resolve().parent
SHOTS = HERE.parent / "reports" / "screenshots"
PORT = 8018
BASE = f"http://127.0.0.1:{PORT}"


def main():
    from playwright.sync_api import sync_playwright
    SHOTS.mkdir(parents=True, exist_ok=True)
    env = {k: v for k, v in os.environ.items() if k not in ("OPENAI_API_KEY", "RAG_LLM_BASE_URL", "RAG_LLM_MODEL")}
    env.update({"HOST": "127.0.0.1", "PORT": str(PORT), "PYTHONDONTWRITEBYTECODE": "1"})
    proc = subprocess.Popen([sys.executable, "server.py"], cwd=HERE, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    cases, errors = [], []

    def check(name, ok, detail=""):
        cases.append({"name": name, "class": "BrowserUI", "status": "passed" if ok else "failed", "detail": "" if ok else str(detail)[:200]})

    tmp = pathlib.Path(tempfile.mkdtemp(prefix="rag-ui-"))
    try:
        for _ in range(60):
            try:
                urllib.request.urlopen(BASE + "/api/health", timeout=2).read(); break
            except Exception:
                time.sleep(0.3)
        else:
            raise RuntimeError("server did not start")
        with sync_playwright() as p:
            browser = None
            for ch in ("msedge", "chrome", None):
                try:
                    browser = p.chromium.launch(channel=ch) if ch else p.chromium.launch(); break
                except Exception:
                    continue
            if browser is None:
                raise RuntimeError("no Chromium-based browser available")
            pg = browser.new_page(viewport={"width": 1280, "height": 900})
            pg.on("pageerror", lambda e: errors.append(str(e)))
            pg.goto(BASE + "/"); pg.wait_for_selector("#docs tr")
            body = pg.inner_text("body")
            check("page_title_and_method_statement", pg.title() == "LTID AI Competition – RAG" and "No embeddings and no vector database" in body, pg.title())
            rows = pg.locator("#docs tr")
            check("documents_table_lists_the_five_shipped_files", rows.count() == 5 and "Policy_Expense_v2_Current.txt" in body and "superseded by v2" in body, rows.count())
            check("example_questions_come_from_the_project", pg.locator("#examples .chip").count() >= 9)

            pg.locator("#examples .chip", has_text="When must an expense claim be submitted?").click()
            pg.wait_for_selector("#answer .ans")
            ans = pg.inner_text("#answer")
            check("example_question_is_answered_with_filename_line_and_quote", "10 calendar days" in ans and "Policy_Expense_v2_Current.txt" in ans and "line 2" in ans and "Answered from the documents" in ans, ans[:200])
            check("superseded_version_is_reported_not_used", "superseded" in ans.lower() and "30 calendar days" not in ans)
            pg.screenshot(path=str(SHOTS / "prompt-c-rag-answer.png"), full_page=True)

            pg.fill("#q", "Who approved our acquisition of Company Z?"); pg.click("#ask-btn")
            pg.wait_for_function("document.querySelector('#answer').innerText.includes('Not found')")
            ans = pg.inner_text("#answer")
            check("unanswerable_question_abstains_without_sources", "Not found in the documents" in ans and "Sources" not in ans, ans[:200])

            pg.fill("#q", ""); pg.click("#ask-btn"); pg.wait_for_selector("#ask-error:not([hidden])")
            check("empty_question_shows_clear_error", "enter a question" in pg.inner_text("#ask-error").lower())

            pg.fill("#q", "When must an expense claim be submitted?"); pg.check("#use-llm"); pg.click("#ask-btn")
            pg.wait_for_function("!document.querySelector('#ask-error').hidden && document.querySelector('#ask-error').innerText.length > 5")
            check("llm_option_without_credentials_explains_what_to_set", "OPENAI_API_KEY" in pg.inner_text("#ask-error") and "not configured" in pg.inner_text("#llm-state"), pg.inner_text("#ask-error"))
            pg.uncheck("#use-llm")

            good = tmp / "Travel_Policy.txt"
            good.write_text("Travel Policy - version 1 (effective 2026-01-01)\nCar rentals require director approval before booking.", encoding="utf-8")
            pg.set_input_files("#file", str(good)); pg.wait_for_function("document.querySelector('#up-msg').innerText.includes('added')")
            check("upload_adds_a_document_and_reindexes", pg.locator("#docs tr").count() == 6 and "uploaded" in pg.inner_text("#docs"), pg.inner_text("#up-msg"))
            pg.fill("#q", "Who must approve car rentals?"); pg.click("#ask-btn")
            pg.wait_for_function("document.querySelector('#answer').innerText.includes('director approval')")
            ans = pg.inner_text("#answer")
            check("uploaded_document_is_retrieved_and_cited", "director approval" in ans and "Travel_Policy.txt" in ans, ans[:200])

            bad = tmp / "notes.pdf"
            bad.write_text("plain text pretending to be a pdf", encoding="utf-8")
            pg.set_input_files("#file", str(bad)); pg.wait_for_function("document.querySelector('#up-msg').className.includes('err')")
            check("unsupported_file_type_is_rejected_with_message", ".txt" in pg.inner_text("#up-msg") and pg.locator("#docs tr").count() == 6, pg.inner_text("#up-msg"))

            xss = tmp / "Xss_Test.txt"
            xss.write_text("Hostile Policy - version 1\nThe <img src=x onerror=window.__xss=1> hostile marker rule applies to everyone.", encoding="utf-8")
            pg.set_input_files("#file", str(xss)); pg.wait_for_function("document.querySelector('#docs').innerText.includes('Xss_Test.txt')")
            pg.fill("#q", "What hostile marker rule applies to everyone?"); pg.click("#ask-btn")
            pg.wait_for_function("document.querySelector('#answer').innerText.includes('hostile marker')")
            check("html_in_uploaded_text_is_shown_as_text_not_executed", pg.locator("#answer img").count() == 0 and not pg.evaluate("window.__xss === 1") and "<img" in pg.inner_text("#answer"))

            pg.locator("button[data-del='Travel_Policy.txt']").click(); pg.wait_for_function("!document.querySelector('#docs').innerText.includes('Travel_Policy.txt')")
            check("uploaded_document_can_be_removed", "Travel_Policy.txt" not in pg.inner_text("#docs"))
            pg.click("#reset-btn"); pg.wait_for_function("document.querySelectorAll('#docs tr').length === 5")
            check("reset_removes_all_uploads", pg.locator("#docs tr").count() == 5 and "Xss_Test.txt" not in pg.inner_text("#docs"))

            m = browser.new_page(viewport={"width": 375, "height": 800}); m.on("pageerror", lambda e: errors.append("mobile: " + str(e)))
            m.goto(BASE + "/?q=" + urllib.request.quote("What is the hotel reimbursement limit per night?")); m.wait_for_selector("#answer .ans")
            check("mobile_375_answer_and_no_horizontal_overflow", "JPY 15,000" in m.inner_text("#answer") and not m.evaluate("document.documentElement.scrollWidth > window.innerWidth + 1"))
            m.screenshot(path=str(SHOTS / "prompt-c-rag-mobile.png"), full_page=True)
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
    print(json.dumps({"cases": cases}))
    return 0 if all(c["status"] == "passed" for c in cases) else 1


if __name__ == "__main__":
    sys.exit(main())
