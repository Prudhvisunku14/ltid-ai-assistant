"""Browser tests (Playwright + Chromium). Serves the site locally; no network needed.
Run: python -m unittest tests.e2e.test_browser -v   (needs: pip install playwright && playwright install chromium)
Also writes desktop/mobile screenshots to ./screenshots/ .
"""
import functools, http.server, threading, unittest
from pathlib import Path

try:
    from playwright.sync_api import sync_playwright
except ImportError:  # pragma: no cover
    sync_playwright = None

BASE = Path(__file__).resolve().parents[2]
SHOTS = BASE / 'screenshots'


class Quiet(http.server.SimpleHTTPRequestHandler):
    def log_message(self, *a): pass


@unittest.skipIf(sync_playwright is None, 'playwright not installed')
class BrowserTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        handler = functools.partial(Quiet, directory=str(BASE))
        cls.httpd = http.server.ThreadingHTTPServer(('127.0.0.1', 0), handler)
        cls.url = f'http://127.0.0.1:{cls.httpd.server_address[1]}/index.html'
        threading.Thread(target=cls.httpd.serve_forever, daemon=True).start()
        cls.pw = sync_playwright().start()
        cls.browser = cls.pw.chromium.launch()
        SHOTS.mkdir(exist_ok=True)

    @classmethod
    def tearDownClass(cls):
        cls.browser.close(); cls.pw.stop(); cls.httpd.shutdown()

    def page(self, width, height):
        ctx = self.browser.new_context(viewport={'width': width, 'height': height})
        pg = ctx.new_page(); self.errors = []
        pg.on('pageerror', lambda e: self.errors.append(str(e)))
        pg.goto(self.url); pg.wait_for_selector('#project-grid .card')
        self.addCleanup(ctx.close)
        return pg

    def test_portfolio_renders_at_least_three_cards_with_alt(self):
        pg = self.page(1280, 800)
        self.assertGreaterEqual(pg.locator('#project-grid .card').count(), 3)
        for img in pg.locator('#project-grid img').all():
            self.assertTrue(img.get_attribute('alt'))
        self.assertEqual(self.errors, [])

    def test_mobile_nav_toggle_with_keyboard(self):
        pg = self.page(375, 800)
        toggle = pg.locator('#nav-toggle'); nav = pg.locator('#site-nav')
        self.assertTrue(toggle.is_visible()); self.assertFalse(nav.is_visible())
        toggle.focus(); pg.keyboard.press('Enter')
        self.assertTrue(nav.is_visible())
        self.assertEqual(toggle.get_attribute('aria-expanded'), 'true')
        pg.keyboard.press('Escape')
        self.assertFalse(nav.is_visible())
        self.assertEqual(toggle.get_attribute('aria-expanded'), 'false')
        self.assertTrue(pg.evaluate("document.activeElement.id === 'nav-toggle'"))

    def test_desktop_hides_toggle_and_shows_nav(self):
        pg = self.page(1280, 800)
        self.assertFalse(pg.locator('#nav-toggle').is_visible())
        self.assertTrue(pg.locator('#site-nav').is_visible())

    def test_contact_form_errors_then_success(self):
        pg = self.page(1280, 800)
        pg.click('#contact-form button[type=submit]')
        self.assertEqual(pg.locator('.field-error:not([hidden])').count(), 3)
        self.assertIn('fix 3 fields', pg.inner_text('#form-status'))
        self.assertEqual(pg.get_attribute('#name', 'aria-invalid'), 'true')
        pg.fill('#name', 'Ada Lovelace'); pg.fill('#email', 'ada@example.com')
        pg.fill('#message', 'We would like a new homepage.')
        pg.click('#contact-form button[type=submit]')
        txt = pg.inner_text('#form-status')
        self.assertIn('not sent', txt)
        self.assertEqual(pg.locator('.field-error:not([hidden])').count(), 0)
        self.assertEqual(pg.input_value('#name'), '')

    def test_focus_ring_is_visible(self):
        pg = self.page(1280, 800)
        pg.keyboard.press('Tab')  # skip link
        self.assertNotEqual(pg.evaluate("getComputedStyle(document.activeElement).outlineStyle"), 'none')

    def test_no_horizontal_overflow_on_mobile_and_desktop(self):
        for w in (375, 1280):
            pg = self.page(w, 800)
            self.assertLessEqual(pg.evaluate("document.documentElement.scrollWidth"), w, f'overflow at {w}px')

    def test_zz_capture_screenshots(self):
        for name, w, h in (('desktop-1280', 1280, 900), ('mobile-375', 375, 800)):
            pg = self.page(w, h)
            pg.screenshot(path=str(SHOTS / f'{name}-full.png'), full_page=True)
            pg.screenshot(path=str(SHOTS / f'{name}-fold.png'))
        pg = self.page(375, 800)
        pg.click('#nav-toggle'); pg.screenshot(path=str(SHOTS / 'mobile-375-menu-open.png'))
        self.assertTrue((SHOTS / 'mobile-375-full.png').exists())


if __name__ == '__main__':
    unittest.main()
