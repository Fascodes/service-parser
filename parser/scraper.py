"""Parser katalogu Północ (ocena 4.0): python -m parser.scraper --url http://127.0.0.1:8000/strona-1.html"""
import argparse
import csv
import json
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from urllib import robotparser
from urllib.parse import urldefrag, urljoin

import requests
from bs4 import BeautifulSoup

from parser.cleaning import EUR_PLN, SCHEMA, clean_record, clean_text

USER_AGENT = "PolnocParser/1.0 (laboratorium PJN)"
DATA_FIELDS = tuple(SCHEMA) + ("cena_pln",)
FIELDS = DATA_FIELDS + ("struktura", "strona")
MIN_RECORDS = 200
MIN_ATTRIBUTES = 18

log = logging.getLogger("parser")


class Fetcher:
    """Pobiera strony jedną sesją, z odstępem `delay` sekund między żądaniami."""

    def __init__(self, delay=0.5, timeout=10, session=None):
        self.delay = delay
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_request = None
        self.requests = 0

    def get(self, url):
        if self._last_request is not None:
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        try:
            self.requests += 1
            response = self.session.get(url, timeout=self.timeout)
        finally:
            self._last_request = time.monotonic()
        response.raise_for_status()
        response.encoding = "utf-8"
        return response.text

    def allowed(self, url):
        """Sprawdza robots.txt serwisu; brak pliku oznacza zgodę."""
        rules = robotparser.RobotFileParser()
        try:
            rules.parse(self.get(urljoin(url, "/robots.txt")).splitlines())
        except requests.HTTPError:
            return True
        return rules.can_fetch(USER_AGENT, url)


def parse_record(element, base_url):
    """Odczytuje surowe teksty pól z karty, wiersza tabeli lub strony szczegółów."""
    raw = {"id": element["data-id"]}
    for field in element.select("[data-pole]"):
        name = field["data-pole"]
        if name == "url":
            link = field if field.name == "a" else field.find("a", href=True)
            raw["url"] = urljoin(base_url, link["href"]) if link else None
            continue
        if name == "cena" and field.get("data-waluta"):
            raw["waluta"] = field["data-waluta"]
        raw[name] = clean_text(field.get_text())
    return raw


def parse_listing(html, base_url):
    """Zwraca (rekordy, adres następnej strony albo None)."""
    soup = BeautifulSoup(html, "html.parser")
    records = []
    for element in soup.select(".produkt[data-id]"):
        raw = parse_record(element, base_url)
        raw["struktura"] = "karta" if element.name == "article" else "tabela"
        records.append(raw)
    next_link = soup.select_one('.pagination a[rel="next"][href]')
    return records, urljoin(base_url, next_link["href"]) if next_link else None


def parse_detail(html, base_url):
    element = BeautifulSoup(html, "html.parser").select_one(".product-detail[data-id]")
    return parse_record(element, base_url) if element else None


def crawl_listing(fetcher, start_url, max_pages, stats):
    """Przechodzi stronami katalogu po linku rel="next"."""
    occurrences, visited, url = [], set(), start_url
    while url and stats["strony"] < max_pages:
        url = urldefrag(url).url
        if url in visited:
            log.warning("Pętla w paginacji: %s już odwiedzony", url)
            break
        visited.add(url)
        try:
            html = fetcher.get(url)
        except requests.RequestException as exc:
            stats["bledy"] += 1
            log.error("Nie udało się pobrać strony %s: %s", url, exc)
            break
        stats["strony"] += 1
        records, url = parse_listing(html, url)
        for raw in records:
            raw["strona"] = stats["strony"]
        occurrences.extend(records)
        log.info("Strona %d: %d rekordów", stats["strony"], len(records))
    return occurrences


def deduplicate(records):
    """Zostawia pierwsze wystąpienie każdego id; różniące się kopie trafiają do logu."""
    unique = {}
    for raw in records:
        first = unique.setdefault(raw["id"], raw)
        if first is not raw:
            differences = [k for k in SCHEMA if first.get(k) != raw.get(k)]
            if differences:
                log.warning("Duplikat %s (strona %s) różni się w polach: %s",
                            raw["id"], raw["strona"], ", ".join(differences))
    return list(unique.values())


def merge_detail(raw, detail):
    """Uzupełnia rekord z listy polami ze strony szczegółów (lista ma pierwszeństwo)."""
    for field, value in detail.items():
        if raw.get(field) in (None, ""):
            raw[field] = value
        elif value not in (None, "") and value != raw[field]:
            log.warning("%s: pole %s różni się (lista %r, szczegóły %r)", raw["id"], field, raw[field], value)
    return raw


def scrape(fetcher, start_url, max_pages=1000, rate=EUR_PLN):
    """Cały przebieg: lista -> deduplikacja -> szczegóły -> czyszczenie. Zwraca (rekordy, raport)."""
    started = time.monotonic()
    stats = Counter(strony=0, bledy=0)
    occurrences = crawl_listing(fetcher, start_url, max_pages, stats)
    unique = deduplicate(occurrences)
    log.info("Wystąpienia: %d, unikalne: %d, usunięte duplikaty: %d",
             len(occurrences), len(unique), len(occurrences) - len(unique))

    records, rejected = [], []
    for number, raw in enumerate(unique, start=1):
        if raw.get("url"):
            try:
                html = fetcher.get(raw["url"])
            except requests.RequestException as exc:
                stats["bledy"] += 1
                log.error("%s: nie udało się pobrać szczegółów %s: %s", raw["id"], raw["url"], exc)
            else:
                detail = parse_detail(html, raw["url"])
                if detail:
                    merge_detail(raw, detail)
                    stats["szczegoly"] += 1
                else:
                    stats["bledy"] += 1
                    log.error("%s: brak sekcji szczegółów na %s", raw["id"], raw["url"])
        else:
            log.warning("%s: brak odnośnika do szczegółów", raw["id"])
        if number % 50 == 0:
            log.info("Szczegóły: %d/%d", number, len(unique))
        record, problems = clean_record(raw, rate)
        for problem in problems:
            log.warning("%s: odrzucono %s=%r (%s)", problem["id"], problem["pole"], problem["wartosc"], problem["powod"])
        rejected.extend(problems)
        record.update(struktura=raw["struktura"], strona=raw["strona"])
        records.append(record)

    rejected_by_field = Counter(p["pole"] for p in rejected)
    report = {
        "strony": stats["strony"],
        "wystapienia": len(occurrences),
        "duplikaty_usuniete": len(occurrences) - len(unique),
        "rekordy": len(records),
        "atrybuty": len(DATA_FIELDS),
        "szczegoly_pobrane": stats["szczegoly"],
        "zadania_http": fetcher.requests,
        "bledy": stats["bledy"],
        "czas_s": round(time.monotonic() - started, 2),
        # Odrzucona wartość też jest pusta w wyniku, więc braki liczymy bez niej.
        "braki": {f: sum(r[f] is None for r in records) - rejected_by_field[f] for f in DATA_FIELDS},
        "odrzucone": {f: rejected_by_field[f] for f in DATA_FIELDS},
        "odrzucone_wartosci": rejected,
    }
    return records, report


def csv_value(value, decimal):
    if value is None:
        return ""
    if isinstance(value, float):
        return str(value).replace(".", decimal)
    return value


def write_csv(records, path, delimiter=";", decimal=","):
    """Domyślnie format polskiego Excela: średnik między kolumnami, przecinek dziesiętny."""
    # utf-8-sig: BOM pozwala Excelowi poprawnie odczytać polskie znaki.
    with Path(path).open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter=delimiter)
        writer.writeheader()
        for record in records:
            writer.writerow({key: csv_value(record.get(key), decimal) for key in FIELDS})


def write_json(data, path):
    with Path(path).open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)


def setup_logging(path):
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    file_handler = logging.FileHandler(path, mode="w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    log.addHandler(file_handler)
    log.addHandler(console)


def main(argv=None):
    args = argparse.ArgumentParser(description="Parser katalogu Północ (ocena 4.0).")
    args.add_argument("--url", default="http://127.0.0.1:8000/strona-1.html", help="pierwsza strona katalogu")
    args.add_argument("--out-dir", default="wyniki", help="katalog na CSV, JSON, raport i log")
    args.add_argument("--pages", type=int, default=1000, help="maksymalna liczba stron listy")
    args.add_argument("--delay", type=float, default=0.5, help="odstęp między żądaniami [s], min. 0,5")
    args.add_argument("--kurs-eur", type=float, default=EUR_PLN, help="kurs EUR->PLN dla kolumny cena_pln")
    args.add_argument("--sep", default=";", help="separator kolumn CSV (domyślnie ';' dla polskiego Excela)")
    args.add_argument("--decimal", default=",", help="separator dziesiętny w CSV (domyślnie ',')")
    options = args.parse_args(argv)
    if options.sep == options.decimal:
        args.error("--sep i --decimal muszą się różnić")
    if options.delay < 0.5:
        args.error("--delay musi wynosić co najmniej 0,5 s")

    out_dir = Path(options.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    setup_logging(out_dir / "parser.log")
    log.info("Start: %s (odstęp %.1f s)", options.url, options.delay)

    fetcher = Fetcher(delay=options.delay)
    if not fetcher.allowed(options.url):
        log.error("robots.txt zabrania pobierania %s", options.url)
        return 1
    records, report = scrape(fetcher, options.url, options.pages, options.kurs_eur)

    write_csv(records, out_dir / "produkty.csv", options.sep, options.decimal)
    write_json(records, out_dir / "produkty.json")
    write_json(report, out_dir / "raport.json")

    rejected = sum(report["odrzucone"].values())
    log.info("Podsumowanie: strony %d, wystąpienia %d, rekordy %d, atrybuty %d, duplikaty %d, "
             "odrzucone wartości %d, błędy %d, żądania %d, czas %.1f s",
             report["strony"], report["wystapienia"], report["rekordy"], report["atrybuty"],
             report["duplikaty_usuniete"], rejected, report["bledy"], report["zadania_http"], report["czas_s"])
    log.info("Zapisano: %s", ", ".join(str(out_dir / n) for n in ("produkty.csv", "produkty.json", "raport.json", "parser.log")))
    if report["rekordy"] < MIN_RECORDS or report["atrybuty"] < MIN_ATTRIBUTES:
        log.warning("Za mało danych: wymagane %d rekordów i %d atrybutów", MIN_RECORDS, MIN_ATTRIBUTES)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
