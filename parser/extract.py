"""Odczyt rekordów z HTML (BeautifulSoup) oraz deduplikacja i łączenie listy ze szczegółami."""
import logging
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from parser.cleaning import SCHEMA, clean_text

log = logging.getLogger("parser")
RECORD = ".produkt[data-id]"


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
    for element in soup.select(RECORD):
        raw = parse_record(element, base_url)
        raw["struktura"] = "karta" if element.name == "article" else "tabela"
        records.append(raw)
    return records, next_page(soup, base_url)


def next_page(soup, base_url):
    link = soup.select_one('.pagination a[rel="next"][href]')
    return urljoin(base_url, link["href"]) if link else None


def parse_detail(html, base_url):
    element = BeautifulSoup(html, "html.parser").select_one(".product-detail[data-id]")
    return parse_record(element, base_url) if element else None


def count_records(html):
    return len(BeautifulSoup(html, "html.parser").select(RECORD))


def count_fields(html):
    return len(BeautifulSoup(html, "html.parser").select("[data-pole]"))


def deduplicate(records):
    """Zostawia pierwsze wystąpienie każdego id; różniące się kopie trafiają do logu."""
    unique = {}
    for raw in records:
        first = unique.setdefault(raw["id"], raw)
        if first is not raw:
            differences = [k for k in SCHEMA if first.get(k) != raw.get(k)]
            if differences:
                log.warning("Duplikat %s (strona %s) różni się w polach: %s",
                            raw["id"], raw.get("strona"), ", ".join(differences))
    return list(unique.values())


def merge_detail(raw, detail):
    """Zwraca kopię rekordu z listy uzupełnioną polami szczegółów (lista ma pierwszeństwo)."""
    merged = dict(raw)
    for field, value in detail.items():
        if merged.get(field) in (None, ""):
            merged[field] = value
        elif value not in (None, "") and value != merged[field]:
            log.warning("%s: pole %s różni się (lista %r, szczegóły %r)", raw["id"], field, merged[field], value)
    return merged
