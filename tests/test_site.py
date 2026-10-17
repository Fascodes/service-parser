import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_site import build
from catalog import BASE_FIELDS, products


class CatalogueParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.records = []
        self.scripts = []
        self.fields = set()

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'produkt' in attrs.get('class', '').split():
            self.records.append((tag, attrs['data-id']))
        if tag == 'script':
            self.scripts.append(attrs)
        if 'data-pole' in attrs:
            self.fields.add(attrs['data-pole'])


class CatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = build(Path(cls.temp.name) / 'site')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_reproducible_complete_dataset(self):
        records = products(60)
        self.assertEqual(records, products(60))
        self.assertEqual(len({p['id'] for p in records}), 60)
        self.assertTrue(all(set(p) == set(BASE_FIELDS) for p in records))
        self.assertTrue(all(p['cena'] > 0 and 0 <= p['ocena'] <= 5 for p in records))

    def test_both_html_structures_and_no_javascript(self):
        html = (self.output / 'index.html').read_text(encoding='utf-8')
        parser = CatalogueParser()
        parser.feed(html)
        self.assertEqual(len(parser.records), 60)
        self.assertEqual(sum(tag == 'article' for tag, _ in parser.records), 30)
        self.assertEqual(sum(tag == 'tr' for tag, _ in parser.records), 30)
        self.assertEqual(len(set(parser.records)), 60)
        self.assertFalse(parser.scripts)
        self.assertTrue({'nazwa', 'cena', 'kategoria', 'producent', 'dostepnosc',
                         'ocena', 'liczba_opinii', 'data_dodania', 'gwarancja', 'url'} <= parser.fields)
        self.assertIn('Północ', html)
        self.assertIn('Śpiwór', html)
        self.assertIn('charset="utf-8"', html)

    def test_generated_assets_exist(self):
        for name in ('assets/style.css', 'robots.txt', 'o-katalogu.html'):
            self.assertTrue((self.output / name).is_file())


if __name__ == '__main__':
    unittest.main()
