"""Real-browser test (Playwright/Chromium). Exit 0 = pass, 1 = fail, 3 = browser unavailable (skipped, NOT a pass)."""
import sys
from pathlib import Path

repo = Path(sys.argv[1]).resolve()
try:
    from playwright.sync_api import sync_playwright
except ImportError:
    print("playwright not installed"); sys.exit(3)

with sync_playwright() as p:
    try:
        browser = p.chromium.launch()
    except Exception as e:
        print(f"cannot launch chromium: {str(e)[:120]}"); sys.exit(3)
    page = browser.new_page()
    page.goto((repo / "index.html").as_uri())
    assert page.get_attribute("html", "data-theme") == "light", "default theme should be light"
    page.click("#theme-toggle")
    assert page.get_attribute("html", "data-theme") == "dark", "toggle should switch to dark"
    page.reload()
    assert page.get_attribute("html", "data-theme") == "dark", "dark choice should persist after reload"
    page.click("a[href='contact.html']")
    page.click("button[type=submit]")
    assert page.inner_text("#name-error").strip(), "empty name should show an error"
    assert page.inner_text("#email-error").strip(), "empty email should show an error"
    page.fill("#name", "Ann"); page.fill("#email", "ann@example.com"); page.fill("#message", "Hello")
    page.click("button[type=submit]")
    assert page.inner_text("#name-error").strip() == "", "errors should clear when valid"
    browser.close()
print("browser ok")
