"""Testy parsera: python -m unittest discover -s parser/tests -t . -v"""
import csv
import json
import logging
import tempfile
import time
import unittest
from pathlib import Path
from urllib.parse import urlsplit

import requests

from build_site import build
from catalog import products
from parser.cleaning import (clean_record, number, parse_date, parse_ean,
                             parse_price, to_pln)
from parser.scraper import (DATA_FIELDS, FIELDS, Fetcher, deduplicate, scrape,
                            write_csv, write_json)

BASE_URL = "http://127.0.0.1:8000"
logging.getLogger("parser").addHandler(logging.NullHandler())
logging.getLogger("parser").propagate = False


class SiteFetcher:
    """Udaje serwer: zwraca pliki z wygenerowanego katalogu public/."""

    def __init__(self, root, missing=()):
        self.root, self.missing, self.requests = root, set(missing), 0

    def get(self, url):
        self.requests += 1
        path = urlsplit(url).path.lstrip("/") or "index.html"
        if path in self.missing:
            raise requests.HTTPError(f"404 {url}")
        return (self.root / path).read_text(encoding="utf-8")


class ScrapeSiteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = tempfile.TemporaryDirectory()
        cls.site = build(Path(cls.tmp.name) / "public")
        cls.records, cls.report = scrape(SiteFetcher(cls.site), f"{BASE_URL}/strona-1.html")

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()

    def test_walks_all_pages_and_removes_duplicates(self):
        self.assertEqual(self.report["strony"], 5)
        self.assertEqual(self.report["wystapienia"], 208)
        self.assertEqual(self.report["duplikaty_usuniete"], 8)
        self.assertEqual(len(self.records), 200)
        self.assertEqual(len({r["id"] for r in self.records}), 200)

    def test_joins_list_and_details(self):
        self.assertEqual(self.report["szczegoly_pobrane"], 200)
        self.assertGreaterEqual(self.report["atrybuty"], 18)
        self.assertEqual({r["struktura"] for r in self.records}, {"karta", "tabela"})

    def test_matches_source_data(self):
        expected = {p["id"]: p for p in products(200)}
        for record in self.records:
            source = expected[record["id"]]
            for field in DATA_FIELDS:
                if field == "url":
                    self.assertEqual(record["url"], BASE_URL + source["url"])
                elif field == "cena_pln":
                    self.assertEqual(record["cena_pln"], to_pln(source["cena"], source["waluta"]))
                else:
                    self.assertEqual(record[field], source[field], (record["id"], field))

    def test_missing_values_are_empty_not_rejected(self):
        self.assertEqual(self.report["braki"]["producent"], 40)
        self.assertEqual(self.report["braki"]["gwarancja"], 40)
        self.assertEqual(sum(self.report["odrzucone"].values()), 0)
        self.assertEqual(self.report["bledy"], 0)

    def test_failed_detail_page_does_not_stop_run(self):
        fetcher = SiteFetcher(self.site, missing={"produkty/PN-0002.html"})
        records, report = scrape(fetcher, f"{BASE_URL}/strona-1.html", max_pages=1)
        self.assertEqual(report["bledy"], 1)
        broken = next(r for r in records if r["id"] == "PN-0002")
        self.assertIsNone(broken["ean"])
        self.assertIsNotNone(broken["nazwa"])


class CleaningTest(unittest.TestCase):
    def test_parse_price(self):
        self.assertEqual(parse_price("1299.00 PLN"), 1299.0)
        self.assertEqual(parse_price("1\xa0299,00 zł"), 1299.0)
        self.assertEqual(parse_price("209,37 €"), 209.37)
        self.assertIsNone(parse_price(""))
        self.assertRaises(ValueError, parse_price, "brak")
        self.assertRaises(ValueError, parse_price, "0,00 zł")

    def test_parse_date_unifies_formats(self):
        self.assertEqual(parse_date("2026-08-26"), "2026-08-26")
        self.assertEqual(parse_date("26.08.2026"), "2026-08-26")
        self.assertRaises(ValueError, parse_date, "wczoraj")

    def test_number_ranges(self):
        rating = number(float, 0, 5)
        self.assertEqual(rating("4,5"), 4.5)
        self.assertRaises(ValueError, rating, "7")
        self.assertRaises(ValueError, number(int), "1.5")
        self.assertEqual(number(int)("1 200"), 1200)

    def test_parse_ean_checksum(self):
        self.assertEqual(parse_ean("5901230000011"), "5901230000011")
        self.assertRaises(ValueError, parse_ean, "5901230000012")
        self.assertRaises(ValueError, parse_ean, "12345")

    def test_clean_record_rejects_instead_of_raising(self):
        record, rejected = clean_record({"id": "PN-0001", "cena": "abc", "waluta": "EUR", "ocena": "9"})
        self.assertIsNone(record["cena"])
        self.assertIsNone(record["cena_pln"])
        self.assertEqual({p["pole"] for p in rejected}, {"cena", "ocena"})

    def test_to_pln(self):
        self.assertEqual(to_pln(100.0, "EUR"), 435.0)
        self.assertEqual(to_pln(100.0, "PLN"), 100.0)
        self.assertIsNone(to_pln(None, "PLN"))

    def test_deduplicate_keeps_first(self):
        records = [{"id": "A", "strona": 1}, {"id": "B", "strona": 1}, {"id": "A", "strona": 2}]
        self.assertEqual(deduplicate(records), records[:2])


class ExportTest(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.record = dict.fromkeys(FIELDS)
        self.record.update(id="PN-1", nazwa="Śpiwór puchowy", cena=459.25, liczba_opinii=12)

    def read_csv(self, delimiter=";", decimal=","):
        path = Path(self.tmp.name) / "out.csv"
        write_csv([self.record], path, delimiter, decimal)
        with path.open(encoding="utf-8-sig", newline="") as handle:
            return list(csv.DictReader(handle, delimiter=delimiter))[0]

    def test_csv_uses_polish_excel_format_by_default(self):
        row = self.read_csv()
        self.assertEqual(row["nazwa"], "Śpiwór puchowy")
        self.assertEqual(row["cena"], "459,25")
        self.assertEqual(row["liczba_opinii"], "12")
        self.assertEqual(row["producent"], "")

    def test_csv_standard_format_option(self):
        self.assertEqual(self.read_csv(delimiter=",", decimal=".")["cena"], "459.25")

    def test_json_keeps_types_and_polish_characters(self):
        path = Path(self.tmp.name) / "out.json"
        write_json([self.record], path)
        self.assertIn("Śpiwór", path.read_text(encoding="utf-8"))
        loaded = json.loads(path.read_text(encoding="utf-8"))[0]
        self.assertEqual(loaded["cena"], 459.25)
        self.assertIsNone(loaded["producent"])


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
