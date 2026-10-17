"""Testy parsera: python -m unittest discover -s parser/tests -t . -v"""
import csv
import tempfile
import time
import unittest
from pathlib import Path

from build_site import build
from catalog import products
from parser.scraper import (FIELDS, Fetcher, deduplicate, parse_catalog,
                            parse_price, write_csv)

BASE_URL = "http://127.0.0.1:8000/"


class ParseCatalogTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with tempfile.TemporaryDirectory() as tmp:
            html = (build(Path(tmp) / "public") / "index.html").read_text(encoding="utf-8")
        cls.records = parse_catalog(html, BASE_URL)

    def test_all_records_from_both_structures(self):
        self.assertEqual(len(self.records), 60)
        self.assertEqual(sum(r["struktura"] == "karta" for r in self.records), 30)
        self.assertEqual(sum(r["struktura"] == "tabela" for r in self.records), 30)

    def test_every_field_filled_with_common_format(self):
        for record in self.records:
            self.assertEqual(tuple(record), FIELDS)
            self.assertTrue(all(value is not None for value in record.values()), record)
            self.assertIsInstance(record["cena"], float)
            self.assertIsInstance(record["ocena"], float)
            self.assertIsInstance(record["liczba_opinii"], int)
            self.assertIsInstance(record["gwarancja"], int)
            self.assertTrue(record["url"].startswith(BASE_URL + "#produkt-"))

    def test_matches_source_data(self):
        expected = {p["id"]: p for p in products(60)}
        for record in self.records:
            source = expected[record["id"]]
            for field in FIELDS[:-2]:
                self.assertEqual(record[field], source[field], (record["id"], field))

    def test_polish_characters(self):
        producers = {r["producent"] for r in self.records}
        self.assertIn("Północ Outdoor", producers)
        self.assertIn("Grań & Szlak", producers)


class CleaningTest(unittest.TestCase):
    def test_parse_price(self):
        self.assertEqual(parse_price("1299.00 PLN"), 1299.0)
        self.assertEqual(parse_price("1\xa0299,00 zł"), 1299.0)
        self.assertEqual(parse_price("329,25 EUR"), 329.25)
        self.assertIsNone(parse_price(""))

    def test_deduplicate_keeps_first(self):
        records = [{"id": "A", "n": 1}, {"id": "B", "n": 2}, {"id": "A", "n": 3}]
        self.assertEqual(deduplicate(records), records[:2])

    def write_and_read(self, record, delimiter=";", decimal=","):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "out.csv"
            write_csv([record], path, delimiter, decimal)
            with path.open(encoding="utf-8-sig", newline="") as handle:
                return list(csv.DictReader(handle, delimiter=delimiter))[0]

    def test_csv_uses_polish_excel_format_by_default(self):
        record = dict.fromkeys(FIELDS, "")
        record.update(id="PN-1", nazwa="Śpiwór puchowy", cena=459.25, liczba_opinii=12, producent=None)
        row = self.write_and_read(record)
        self.assertEqual(row["nazwa"], "Śpiwór puchowy")
        self.assertEqual(row["cena"], "459,25")
        self.assertEqual(row["liczba_opinii"], "12")
        self.assertEqual(row["producent"], "")

    def test_csv_standard_format_option(self):
        record = dict.fromkeys(FIELDS, "")
        record.update(cena=459.25)
        row = self.write_and_read(record, delimiter=",", decimal=".")
        self.assertEqual(row["cena"], "459.25")


class FetcherDelayTest(unittest.TestCase):
    def test_waits_between_requests(self):
        class FakeResponse:
            text, encoding = "ok", None

            def raise_for_status(self):
                pass

        class FakeSession:
            headers = {}

            def get(self, url, timeout):
                return FakeResponse()

        fetcher = Fetcher(delay=0.2, session=FakeSession())
        start = time.monotonic()
        fetcher.get("a")
        fetcher.get("b")
        self.assertGreaterEqual(time.monotonic() - start, 0.2)


if __name__ == "__main__":
    unittest.main()
