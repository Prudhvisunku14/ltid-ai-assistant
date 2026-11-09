from html.parser import HTMLParser
from pathlib import Path
import unittest
BASE=Path(__file__).resolve().parents[1]
class PageParser(HTMLParser):
    def __init__(self): super().__init__(); self.ids=set();self.links=[]
    def handle_starttag(self,tag,attrs):
        a=dict(attrs)
        if 'id' in a:self.ids.add(a['id'])
        if tag=='a' and 'href' in a:self.links.append(a['href'])
class StarterSmokeTests(unittest.TestCase):
    def test_page_exists_and_sections(self):
        page=(BASE/'index.html').read_text(encoding='utf-8'); p=PageParser();p.feed(page)
        self.assertIn('Northstar Studio',page)
        for section in ['main','services','work','contact']:self.assertIn(section,p.ids)
    def test_assets_exist(self):
        self.assertTrue((BASE/'styles.css').exists());self.assertTrue((BASE/'app.js').exists())
if __name__=='__main__':unittest.main()
