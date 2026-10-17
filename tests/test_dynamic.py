import json
import sys
import tempfile
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_site import build
from catalog import BASE_FIELDS, DETAIL_FIELDS, INTERACTIVE_FIELDS


class PageParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.records = []
        self.scripts = []
        self.hrefs = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'produkt' in attrs.get('class', '').split():
            self.records.append(attrs['data-id'])
        if tag == 'script':
            self.scripts.append(attrs)
        if 'href' in attrs:
            self.hrefs.append(attrs['href'])


class DynamicCatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = build(Path(cls.temp.name) / 'site')
        cls.records = []
        cls.pages = []
        for page in range(1, 6):
            manifest = json.loads((cls.output / f'data/strona-{page}.json').read_text(encoding='utf-8'))
            rows = []
            for path in manifest['porcje']:
                rows.extend(json.loads((cls.output / path.lstrip('/')).read_text(encoding='utf-8')))
            cls.pages.append((manifest, rows))
            cls.records.extend(rows)

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_five_pages_400_unique_records_and_eight_duplicates(self):
        self.assertEqual(len(self.records), 408)
        counts = Counter(p['id'] for p in self.records)
        self.assertEqual(len(counts), 400)
        self.assertEqual(sum(n - 1 for n in counts.values()), 8)
        self.assertEqual(sum(n == 2 for n in counts.values()), 8)
        first_page = {p['id'] for p in self.pages[0][1]}
        duplicates_on_later_pages = []
        for manifest, rows in self.pages[1:]:
            duplicates = [p['id'] for p in rows if p['id'] in first_page]
            self.assertEqual(len(duplicates), 2)
            duplicates_on_later_pages.extend(duplicates)
        self.assertEqual(len(set(duplicates_on_later_pages)), 8)
        by_id = {}
        for p in self.records:
            self.assertEqual(p, by_id.setdefault(p['id'], p))

    def test_portions_and_list_schema(self):
        for manifest, rows in self.pages:
            self.assertEqual(len(rows), manifest['liczba_rekordow'])
            self.assertEqual(len(manifest['porcje']), 4)
            for path in manifest['porcje']:
                portion = json.loads((self.output / path.lstrip('/')).read_text(encoding='utf-8'))
                self.assertTrue(1 <= len(portion) <= 24)
                self.assertTrue(all(set(p) == set(BASE_FIELDS) for p in portion))

    def test_no_products_in_raw_html(self):
        for path in self.output.rglob('*.html'):
            html = path.read_text(encoding='utf-8')
            parser = PageParser()
            parser.feed(html)
            self.assertFalse(parser.records, path)
            self.assertIn('charset="utf-8"', html)
            self.assertNotIn('data-pole="nazwa"', html)
            self.assertNotIn('Plecak trekkingowy Nord 001', html)
            if path.name != 'o-katalogu.html':
                self.assertEqual(parser.scripts, [{'type': 'module', 'src': '/assets/app.js'}])

    def test_every_product_has_24_attributes_and_a_detail_page(self):
        json_files = list((self.output / 'data/produkty').glob('*.json'))
        self.assertEqual(len(json_files), 400)
        self.assertEqual(len(list((self.output / 'produkty').glob('*.html'))), 400)
        all_fields = set(BASE_FIELDS) | set(DETAIL_FIELDS) | set(INTERACTIVE_FIELDS)
        self.assertEqual(len(all_fields), 24)
        for path in json_files:
            p = json.loads(path.read_text(encoding='utf-8'))
            self.assertEqual(set(p), all_fields)
            self.assertTrue((self.output / p['url'].lstrip('/')).is_file())
            self.assertIsInstance(p['cena'], (int, float))
            self.assertGreater(p['cena'], 0)
            self.assertTrue(0 <= p['ocena'] <= 5)
            self.assertEqual(len(p['ean']), 13)

    def test_inherited_difficulties(self):
        unique = {p['id']: p for p in self.records}.values()
        self.assertEqual({p['waluta'] for p in unique}, {'PLN', 'EUR'})
        for field in ('producent', 'gwarancja'):
            self.assertEqual(sum(p[field] is None for p in unique), 80)

    def test_internal_links_and_pagination(self):
        for path in self.output.rglob('*.html'):
            parser = PageParser()
            parser.feed(path.read_text(encoding='utf-8'))
            for href in parser.hrefs:
                target = href.split('#')[0]
                if target.startswith('/'):
                    resolved = self.output / target.lstrip('/') if target != '/' else self.output / 'index.html'
                    self.assertTrue(resolved.is_file(), (path, href))
        for page in range(1, 6):
            html = (self.output / f'strona-{page}.html').read_text(encoding='utf-8')
            for number in range(1, 6):
                self.assertIn(f'href="/strona-{number}.html#katalog"', html)
            if page < 5:
                self.assertIn(f'rel="next" href="/strona-{page + 1}.html#katalog"', html)


if __name__ == '__main__':
    unittest.main()
