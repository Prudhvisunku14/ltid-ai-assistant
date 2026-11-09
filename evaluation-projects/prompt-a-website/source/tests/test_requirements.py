"""Static checks mapping to the Release 1.0 requirements (no browser needed)."""
from html.parser import HTMLParser
from pathlib import Path
import json, re, subprocess, unittest

BASE = Path(__file__).resolve().parents[1]


class Collect(HTMLParser):
    def __init__(self):
        super().__init__()
        self.tags = []
    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


def parsed():
    p = Collect(); p.feed((BASE / 'index.html').read_text(encoding='utf-8')); return p.tags


class RequirementTests(unittest.TestCase):
    def test_semantic_landmarks(self):
        names = {t for t, _ in parsed()}
        for tag in ('header', 'nav', 'main', 'footer', 'section', 'h1', 'form'):
            self.assertIn(tag, names, f'missing <{tag}>')
        self.assertEqual(sum(1 for t, _ in parsed() if t == 'h1'), 1, 'exactly one h1')

    def test_nav_toggle_is_accessible(self):
        btn = next(a for t, a in parsed() if t == 'button' and a.get('id') == 'nav-toggle')
        self.assertEqual(btn.get('aria-controls'), 'site-nav')
        self.assertIn('aria-expanded', btn)
        self.assertTrue(any(a.get('id') == 'site-nav' for _, a in parsed()))

    def test_contact_form_fields_have_labels(self):
        tags = parsed()
        labels = {a.get('for') for t, a in tags if t == 'label'}
        for field in ('name', 'email', 'message'):
            self.assertIn(field, labels, f'{field} has no <label for>')
            self.assertTrue(any(a.get('id') == field and 'required' in a for _, a in tags), f'{field} not required')

    def test_status_region_is_live(self):
        status = next(a for _, a in parsed() if a.get('id') == 'form-status')
        self.assertEqual(status.get('role'), 'status')
        self.assertEqual(status.get('aria-live'), 'polite')

    def test_form_does_not_claim_to_send_email(self):
        html = (BASE / 'index.html').read_text(encoding='utf-8').lower()
        self.assertIn('not</strong> sent', html)
        self.assertNotIn('we will email you', html)

    def test_portfolio_data_has_three_valid_projects(self):
        out = subprocess.run(['node', '-e', "console.log(JSON.stringify(require('./data/projects-data.js')))"],
                             cwd=BASE, capture_output=True, text=True, check=True).stdout
        projects = json.loads(out)
        self.assertGreaterEqual(len(projects), 3)
        for p in projects:
            for key in ('id', 'title', 'summary', 'category', 'image', 'alt'):
                self.assertTrue(p.get(key), f'{p.get("id")} missing {key}')
            self.assertTrue((BASE / p['image']).exists(), f'missing image {p["image"]}')

    def test_focus_styles_and_mobile_breakpoint_in_css(self):
        css = (BASE / 'styles.css').read_text(encoding='utf-8')
        self.assertIn(':focus-visible', css)
        self.assertRegex(css, r'@media\(max-width:700px\)')
        self.assertNotIn('outline:none', css.replace(' ', ''))

    def test_no_external_resources(self):
        text = ''.join((BASE / f).read_text(encoding='utf-8') for f in ('index.html', 'styles.css', 'app.js'))
        self.assertIsNone(re.search(r'(src|href)=["\']https?://', text), 'external asset reference found')
        self.assertNotIn('fetch(', text)


if __name__ == '__main__':
    unittest.main()
