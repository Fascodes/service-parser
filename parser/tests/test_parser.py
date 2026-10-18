"""Testy parsera: python -m unittest discover -s parser/tests -t . -v

Testy integracyjne uruchamiają serwis lokalnie (wątek z http.server na wolnym porcie).
Test Selenium wymaga Chrome; bez niego jest pomijany.
"""
import csv
import json
import logging
import tempfile
import threading
import unittest
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import requests

from build_site import build
from catalog import products
from parser.browser import portion_settled
from parser.cleaning import (clean_record, number, parse_date, parse_ean,
                             parse_price, to_pln)
from parser.export import DATA_FIELDS, FIELDS, Checkpoint, write_csv, write_json
from parser.extract import deduplicate, merge_detail
from parser.fetcher import Fetcher
from parser.json_source import JsonSource, json_to_raw
from parser.retry import Pacer, with_retry
from parser.scraper import scrape

logging.getLogger("parser").addHandler(logging.NullHandler())
logging.getLogger("parser").propagate = False
NO_SLEEP = {"sleep": lambda seconds: None}


class QuietHandler(SimpleHTTPRequestHandler):
    def log_message(self, *args):
        pass


class LocalSite:
    """Buduje serwis do katalogu tymczasowego i serwuje go w tle."""

    def __enter__(self):
        self.tmp = tempfile.TemporaryDirectory()
        root = build(Path(self.tmp.name) / "public")
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), partial(QuietHandler, directory=str(root)))
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()
        self.tmp.cleanup()


def expected_value(source, field, base_url):
    if field == "url":
        return base_url + source["url"]
    if field == "cena_pln":
        return to_pln(source["cena"], source["waluta"])
    return source[field]


class JsonPipelineTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.site = LocalSite().__enter__()
        cls.tmp = tempfile.TemporaryDirectory()
        fetcher = Fetcher(Pacer(0), sleep=NO_SLEEP["sleep"])
        checkpoint = Checkpoint(Path(cls.tmp.name) / "cp.json", {"t": 1}, f"{cls.site.url}/strona-1.html")
        cls.records, cls.report = scrape(JsonSource(fetcher), checkpoint)

    @classmethod
    def tearDownClass(cls):
        cls.tmp.cleanup()
        cls.site.__exit__()

    def test_counts(self):
        self.assertEqual(self.report["strony"], 5)
        self.assertEqual(self.report["wystapienia"], 408)
        self.assertEqual(self.report["duplikaty_usuniete"], 8)
        self.assertEqual(self.report["rekordy"], 400)
        self.assertGreaterEqual(self.report["atrybuty"], 22)
        self.assertEqual(self.report["bledy"], 0)
        self.assertEqual(sum(self.report["odrzucone"].values()), 0)

    def test_raw_html_has_no_records(self):
        pages = self.report["html_vs_dom"]["strony_listy"]
        self.assertEqual([p["surowy_html"] for p in pages], [0] * 5)
        self.assertEqual([p["json"] for p in pages], [80, 82, 82, 82, 82])

    def test_all_24_fields_match_source(self):
        expected = {p["id"]: p for p in products(400)}
        for record in self.records:
            for field in DATA_FIELDS:
                self.assertEqual(record[field], expected_value(expected[record["id"]], field, self.site.url),
                                 (record["id"], field))

    def test_missing_values(self):
        self.assertEqual(self.report["braki"]["producent"], 80)
        self.assertEqual(self.report["braki"]["gwarancja"], 80)


class CheckpointTest(unittest.TestCase):
    def setUp(self):
        self.site = LocalSite().__enter__()
        self.addCleanup(self.site.__exit__)
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.path = Path(tmp.name) / "checkpoint.json"
        self.start = f"{self.site.url}/strona-1.html"

    def test_resume_skips_finished_work_and_retries_failures(self):
        class FlakySource(JsonSource):
            calls = {"listing": 0, "detail": []}
            fail = {"PN-0003"}

            def listing_page(self, url):
                self.calls["listing"] += 1
                return super().listing_page(url)

            def detail(self, raw):
                self.calls["detail"].append(raw["id"])
                if raw["id"] in self.fail:
                    self.fail.discard(raw["id"])
                    raise requests.ConnectionError("symulowana awaria")
                return super().detail(raw)

        source = FlakySource(Fetcher(Pacer(0), attempts=1))
        _, report = scrape(source, Checkpoint(self.path, {"t": 1}, self.start), max_pages=1, limit=5)
        self.assertEqual(report["bledy"], 1)
        self.assertEqual(report["szczegoly_pobrane"], 4)

        resumed = Checkpoint(self.path, {"t": 1}, self.start, resume=True)
        self.assertTrue(resumed.resumed)
        records, report = scrape(source, resumed, max_pages=1, limit=5)
        self.assertEqual(source.calls["listing"], 1)  # lista nie była pobierana ponownie
        self.assertEqual(source.calls["detail"][5:], ["PN-0003"])  # tylko nieudany produkt
        self.assertEqual(report["bledy"], 0)
        self.assertTrue(all(r["dostawca"] for r in records))

    def test_other_run_starts_fresh(self):
        Checkpoint(self.path, {"tryb": "json"}, self.start).save()
        checkpoint = Checkpoint(self.path, {"tryb": "selenium"}, self.start, resume=True)
        self.assertFalse(checkpoint.resumed)
        self.assertEqual(checkpoint.state["strony"], [])


@unittest.skipUnless(__import__("shutil").which("chrome") or Path(
    r"C:\Program Files\Google\Chrome\Application\chrome.exe").exists(), "brak Chrome")
class SeleniumTest(unittest.TestCase):
    def test_one_page_with_details_and_interaction(self):
        from parser.browser import BrowserSource
        with LocalSite() as site, tempfile.TemporaryDirectory() as tmp:
            pacer = Pacer(0.5)
            source = BrowserSource(Fetcher(pacer), pacer, error_dir=Path(tmp) / "bledy")
            try:
                checkpoint = Checkpoint(Path(tmp) / "cp.json", {"t": 1}, f"{site.url}/strona-1.html")
                records, report = scrape(source, checkpoint, max_pages=1, limit=2)
            finally:
                source.close()
        self.assertEqual(report["html_vs_dom"]["strony_listy"][0]["surowy_html"], 0)
        self.assertEqual(report["html_vs_dom"]["strony_listy"][0]["dom"], 80)
        fields = report["html_vs_dom"]["szczegoly"]
        self.assertEqual(fields["dom_po_interakcji"] - fields["dom_po_skryptach"], 4)
        self.assertEqual({r["struktura"] for r in records}, {"karta"})
        expected = {p["id"]: p for p in products(400)}
        for record in records:
            for field in DATA_FIELDS:
                self.assertEqual(record[field], expected_value(expected[record["id"]], field, site.url))


class WaitConditionTest(unittest.TestCase):
    class FakeDriver:
        def __init__(self, state):
            self.state = state

        def execute_script(self, script):
            return self.state

    def check(self, loaded, **state):
        base = {"busy": False, "error": False, "done": False, "counter": ""}
        return portion_settled(loaded)(self.FakeDriver({**base, **state}))

    def test_waits_while_busy_or_counter_unchanged(self):
        self.assertIsNone(self.check(0, busy=True, counter="Wczytano 24 z 80"))
        self.assertIsNone(self.check(24, counter="Wczytano 24 z 80"))
        self.assertIsNone(self.check(0, counter="Przygotowujemy katalog…"))

    def test_reports_progress_and_errors(self):
        self.assertEqual(self.check(24, counter="Wczytano 48 z 80 pozycji"),
                         {"error": False, "loaded": 48, "total": 80, "done": False})
        self.assertEqual(self.check(24, error=True), {"error": True})


class RetryTest(unittest.TestCase):
    def test_exponential_backoff_with_limit(self):
        delays, errors = [], []

        def always_fails():
            raise ConnectionError("x")

        with self.assertRaises(ConnectionError):
            with_retry(always_fails, "test", ConnectionError, attempts=4, sleep=delays.append,
                       on_error=lambda *a: errors.append(a[1]))
        self.assertEqual(delays, [1, 2, 4])
        self.assertEqual(errors, [1, 2, 3, 4])  # diagnostyka przy każdym błędzie

    def test_succeeds_after_failure(self):
        results = iter([ConnectionError("x"), "ok"])

        def flaky():
            value = next(results)
            if isinstance(value, Exception):
                raise value
            return value

        self.assertEqual(with_retry(flaky, "test", ConnectionError, sleep=lambda s: None), "ok")

    def test_fetcher_retries_server_errors_but_not_404(self):
        class Response:
            def __init__(self, status):
                self.status_code, self.text, self.encoding = status, "ok", None

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise requests.HTTPError(str(self.status_code))

        class Session:
            headers = {}

            def __init__(self, statuses):
                self.statuses = iter(statuses)

            def get(self, url, timeout):
                return Response(next(self.statuses))

        fetcher = Fetcher(Pacer(0), session=Session([503, 503, 200]), **NO_SLEEP)
        self.assertEqual(fetcher.get("http://x/"), "ok")
        self.assertEqual(fetcher.requests, 3)
        fetcher = Fetcher(Pacer(0), session=Session([404, 200]), **NO_SLEEP)
        self.assertRaises(requests.HTTPError, fetcher.get, "http://x/")
        self.assertEqual(fetcher.requests, 1)


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

    def test_rejects_inf_and_nan(self):
        converters = [number(float, 0.1), number(float, 0, 5), number(int, 0), number(float)]
        for value in ("inf", "-inf", "Infinity", "nan", "NaN", "1e309"):
            for convert in converters:
                with self.assertRaisesRegex(ValueError, "skończoną", msg=value):
                    convert(value)
        self.assertRaises(ValueError, parse_price, "9" * 400 + " zł")  # przepełnienie -> inf
        record, rejected = clean_record({"waga_g": "nan", "wysokosc_cm": "inf", "ocena": "NaN"})
        self.assertEqual((record["waga_g"], record["wysokosc_cm"], record["ocena"]), (None, None, None))
        self.assertEqual({p["pole"] for p in rejected}, {"waga_g", "wysokosc_cm", "ocena"})

    def test_parse_ean_checksum(self):
        self.assertEqual(parse_ean("5901230000011"), "5901230000011")
        self.assertRaises(ValueError, parse_ean, "5901230000012")
        self.assertRaises(ValueError, parse_ean, "12345")

    def test_interaction_fields_allow_zero(self):
        record, rejected = clean_record({"koszt_dostawy": "0", "zuzycie_energii_w": "3.5", "material": "Poliamid"})
        self.assertEqual((record["koszt_dostawy"], record["zuzycie_energii_w"]), (0.0, 3.5))
        self.assertEqual(rejected, [])

    def test_clean_record_rejects_instead_of_raising(self):
        record, rejected = clean_record({"id": "PN-0001", "cena": "abc", "waluta": "EUR", "ocena": "9"})
        self.assertIsNone(record["cena"])
        self.assertIsNone(record["cena_pln"])
        self.assertEqual({p["pole"] for p in rejected}, {"cena", "ocena"})

    def test_to_pln(self):
        self.assertEqual(to_pln(100.0, "EUR"), 435.0)
        self.assertEqual(to_pln(100.0, "PLN"), 100.0)
        self.assertIsNone(to_pln(None, "PLN"))

    def test_json_to_raw(self):
        raw = json_to_raw({"cena": 12.5, "producent": None, "url": "/produkty/A.html"}, "http://x/strona-1.html")
        self.assertEqual(raw, {"cena": "12.5", "producent": None, "url": "http://x/produkty/A.html"})

    def test_deduplicate_keeps_first(self):
        records = [{"id": "A", "strona": 1}, {"id": "B", "strona": 1}, {"id": "A", "strona": 2}]
        self.assertEqual(deduplicate(records), records[:2])

    def test_merge_detail_fills_gaps_without_mutating_list(self):
        raw = {"id": "A", "nazwa": "X", "producent": ""}
        merged = merge_detail(raw, {"nazwa": "X", "producent": "Bóbr Gear", "ean": "1"})
        self.assertEqual(merged, {"id": "A", "nazwa": "X", "producent": "Bóbr Gear", "ean": "1"})
        self.assertEqual(raw["producent"], "")


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
        self.assertFalse(path.with_suffix(".json.tmp").exists())


if __name__ == "__main__":
    unittest.main()
