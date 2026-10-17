"""Parser katalogu Północ (ocena 3.0): python -m parser.scraper --url http://127.0.0.1:8000/"""
import argparse
import csv
import re
import sys
import time
from pathlib import Path
from urllib import robotparser
from urllib.parse import urljoin

import requests
from bs4 import BeautifulSoup

USER_AGENT = "PolnocParser/1.0 (laboratorium PJN)"
FIELDS = (
    "id", "nazwa", "cena", "waluta", "kategoria", "producent", "dostepnosc",
    "ocena", "liczba_opinii", "data_dodania", "gwarancja", "url", "struktura",
)
MIN_RECORDS = 60


class Fetcher:
    """Pobiera strony jedną sesją, z odstępem `delay` sekund między żądaniami."""

    def __init__(self, delay=0.5, timeout=10, session=None):
        self.delay = delay
        self.timeout = timeout
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self._last_request = None

    def get(self, url):
        if self._last_request is not None:
            wait = self.delay - (time.monotonic() - self._last_request)
            if wait > 0:
                time.sleep(wait)
        try:
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


def clean_text(value):
    """Usuwa nadmiarowe białe znaki (w tym twarde spacje)."""
    return re.sub(r"\s+", " ", value.replace("\xa0", " ")).strip()


def parse_price(text):
    """'1299.00 PLN' / '1 299,00 zł' -> 1299.0; pusta wartość -> None."""
    digits = re.sub(r"[^\d,.\-]", "", text.replace("\xa0", "").replace(" ", ""))
    if not digits:
        return None
    if "," in digits:
        digits = digits.replace(".", "").replace(",", ".")
    return float(digits)


def parse_number(text, kind):
    text = clean_text(text).replace(",", ".")
    if not text:
        return None
    return kind(float(text)) if kind is int else kind(text)


CONVERTERS = {
    "cena": parse_price,
    "ocena": lambda text: parse_number(text, float),
    "liczba_opinii": lambda text: parse_number(text, int),
    "gwarancja": lambda text: parse_number(text, int),
}


def parse_record(element, base_url):
    """Zamienia kartę `article.produkt` lub wiersz `tr.produkt` na słownik pól."""
    record = dict.fromkeys(FIELDS)
    record["id"] = element["data-id"]
    record["struktura"] = "karta" if element.name == "article" else "tabela"
    for field in element.select("[data-pole]"):
        name = field["data-pole"]
        if name not in record:
            continue
        if name == "url":
            link = field if field.name == "a" else field.find("a", href=True)
            record["url"] = urljoin(base_url, link["href"]) if link else None
            continue
        if name == "cena":
            record["waluta"] = field.get("data-waluta") or record["waluta"]
        text = clean_text(field.get_text())
        record[name] = CONVERTERS[name](text) if name in CONVERTERS else (text or None)
    return record


def parse_catalog(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    return [parse_record(element, base_url) for element in soup.select(".produkt[data-id]")]


def deduplicate(records):
    seen, unique = set(), []
    for record in records:
        if record["id"] not in seen:
            seen.add(record["id"])
            unique.append(record)
    return unique


def csv_value(value, decimal):
    if value is None:
        return ""
    if isinstance(value, float):
        return str(value).replace(".", decimal)
    return value


def write_csv(records, path, delimiter=";", decimal=","):
    """Domyślnie format polskiego Excela: średnik między kolumnami, przecinek dziesiętny."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # utf-8-sig: BOM pozwala Excelowi poprawnie odczytać polskie znaki.
    with path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, delimiter=delimiter)
        writer.writeheader()
        for record in records:
            writer.writerow({key: csv_value(value, decimal) for key, value in record.items()})


def main(argv=None):
    args = argparse.ArgumentParser(description="Parser katalogu Północ (ocena 3.0).")
    args.add_argument("--url", default="http://127.0.0.1:8000/", help="adres strony katalogu")
    args.add_argument("--out", default="produkty.csv", help="plik wynikowy CSV")
    args.add_argument("--delay", type=float, default=0.5, help="odstęp między żądaniami [s]")
    args.add_argument("--sep", default=";", help="separator kolumn CSV (domyślnie ';' dla polskiego Excela)")
    args.add_argument("--decimal", default=",", help="separator dziesiętny (domyślnie ',')")
    options = args.parse_args(argv)
    if options.sep == options.decimal:
        args.error("--sep i --decimal muszą się różnić")

    fetcher = Fetcher(delay=options.delay)
    if not fetcher.allowed(options.url):
        print(f"robots.txt zabrania pobierania {options.url}", file=sys.stderr)
        return 1
    records = parse_catalog(fetcher.get(options.url), options.url)
    unique = deduplicate(records)
    write_csv(unique, options.out, options.sep, options.decimal)

    by_structure = {name: sum(r["struktura"] == name for r in unique) for name in ("karta", "tabela")}
    print(f"Rekordy: {len(unique)} (karty: {by_structure['karta']}, tabela: {by_structure['tabela']}, "
          f"duplikaty usunięte: {len(records) - len(unique)}) -> {options.out}")
    if len(unique) < MIN_RECORDS:
        print(f"Uwaga: mniej niż {MIN_RECORDS} rekordów.", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
