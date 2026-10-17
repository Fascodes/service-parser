import sys
import tempfile
import unittest
from html.parser import HTMLParser
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from build_site import build
from catalog import BASE_FIELDS, DETAIL_FIELDS, products


class CatalogueParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.records = []
        self.scripts = []
        self.fields = set()
        self.hrefs = []
        self.record_fields = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if 'produkt' in attrs.get('class', '').split():
            self.records.append((tag, attrs['data-id']))
            self.current = {'id'}
        if tag == 'script':
            self.scripts.append(attrs)
        if 'data-pole' in attrs:
            self.fields.add(attrs['data-pole'])
            if self.current is not None:
                self.current.add(attrs['data-pole'])
        if 'data-waluta' in attrs and self.current is not None:
            self.current.add('waluta')
        if 'href' in attrs:
            self.hrefs.append(attrs['href'])

    def handle_endtag(self, tag):
        if tag in ('article', 'tr') and self.current is not None:
            self.record_fields.append(self.current)
            self.current = None


class CatalogueTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        cls.output = build(Path(cls.temp.name) / 'site')

    @classmethod
    def tearDownClass(cls):
        cls.temp.cleanup()

    def test_reproducible_complete_dataset(self):
        records = products(200)
        self.assertEqual(records, products(200))
        self.assertEqual(len({p['id'] for p in records}), 200)
        self.assertTrue(all(set(p) == set(BASE_FIELDS) | set(DETAIL_FIELDS) for p in records))
        self.assertTrue(all(p['cena'] > 0 and 0 <= p['ocena'] <= 5 for p in records))

    def test_both_html_structures_and_no_javascript(self):
        ids = []
        seen_on = {}
        for number in range(1, 6):
            html = (self.output / f'strona-{number}.html').read_text(encoding='utf-8')
            parser = CatalogueParser()
            parser.feed(html)
            self.assertTrue(any(tag == 'article' for tag, _ in parser.records))
            self.assertTrue(any(tag == 'tr' for tag, _ in parser.records))
            self.assertFalse(parser.scripts)
            self.assertEqual(len(parser.record_fields), len(parser.records))
            self.assertTrue(all(set(BASE_FIELDS) <= fields for fields in parser.record_fields))
            for _, identifier in parser.records:
                ids.append(identifier)
                seen_on.setdefault(identifier, set()).add(number)
            self.assertIn('Północ', html)
            self.assertIn('charset="utf-8"', html)
            for page in range(1, 6):
                self.assertIn(f'/strona-{page}.html#katalog', parser.hrefs)
        self.assertEqual(len(ids), 208)
        self.assertEqual(len(set(ids)), 200)
        self.assertEqual(sum(len(pages) > 1 for pages in seen_on.values()), 8)

    def test_all_details_have_eight_additional_fields(self):
        files = list((self.output / 'produkty').glob('*.html'))
        self.assertEqual(len(files), 200)
        for path in files:
            parser = CatalogueParser()
            parser.feed(path.read_text(encoding='utf-8'))
            self.assertEqual(len(parser.records), 1)
            self.assertTrue(set(DETAIL_FIELDS) <= parser.fields)
            self.assertTrue(set(BASE_FIELDS) | set(DETAIL_FIELDS) <= parser.record_fields[0])

    def test_selected_difficulties(self):
        records = products(200)
        self.assertEqual({p['waluta'] for p in records}, {'PLN', 'EUR'})
        for field in ('producent', 'gwarancja'):
            self.assertEqual(sum(p[field] is None for p in records), 40)
        html = ''.join(path.read_text(encoding='utf-8') for path in self.output.glob('strona-*.html'))
        self.assertIn('\u00a0', html)
        self.assertIn('€', html)
        self.assertIn('zł', html)
        self.assertIn('data-pole="producent"></dd>', html)
        self.assertIn('data-pole="gwarancja"></dd>', html)

    def test_every_internal_link_resolves(self):
        for path in self.output.rglob('*.html'):
            parser = CatalogueParser()
            parser.feed(path.read_text(encoding='utf-8'))
            for href in parser.hrefs:
                target = href.split('#')[0]
                if target.startswith('/'):
                    resolved = self.output / target.lstrip('/') if target != '/' else self.output / 'index.html'
                    self.assertTrue(resolved.is_file(), (path, href))

    def test_generated_assets_exist(self):
        for name in ('assets/style.css', 'assets/details.css', 'robots.txt', 'o-katalogu.html'):
            self.assertTrue((self.output / name).is_file())


if __name__ == '__main__':
    unittest.main()
