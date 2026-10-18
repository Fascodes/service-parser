"""Źródło danych bez przeglądarki: te same pliki JSON, które strona pobiera przez fetch.

Surowy HTML listy nie zawiera rekordów, ale zawiera paginację i numer strony
(`#katalog[data-strona]`). Na tej podstawie parser pobiera manifest porcji
`/data/strona-N.json`, porcje z 12 polami listy i `/data/produkty/ID.json` z kompletem 24 pól.
"""
from urllib.parse import urljoin

from bs4 import BeautifulSoup

from parser.extract import count_records, next_page


def json_to_raw(item, base_url):
    """Wartości JSON -> surowe teksty, aby przeszły to samo czyszczenie co dane z HTML."""
    raw = {}
    for key, value in item.items():
        if value is None:
            raw[key] = None
        elif key == "url":
            raw[key] = urljoin(base_url, value)
        else:
            raw[key] = str(value)
    return raw


class JsonSource:
    name = "json"

    def __init__(self, fetcher):
        self.fetcher = fetcher
        self.detail_comparison = None

    def close(self):
        pass

    def listing_page(self, url):
        html = self.fetcher.get(url)
        soup = BeautifulSoup(html, "html.parser")
        section = soup.select_one("#katalog[data-strona]")
        if section is None:
            raise ValueError(f"{url}: brak #katalog[data-strona], nie znam pliku z danymi")
        manifest = self.fetcher.get_json(urljoin(url, f"/data/strona-{section['data-strona']}.json"))
        records = []
        for portion in manifest["porcje"]:
            for item in self.fetcher.get_json(urljoin(url, portion)):
                records.append({**json_to_raw(item, url), "struktura": "json"})
        info = {"url": url, "porcje": len(manifest["porcje"]), "surowy_html": count_records(html),
                "json": len(records)}
        return records, next_page(soup, url), info

    def detail(self, raw):
        item = self.fetcher.get_json(urljoin(raw["url"], f"/data/produkty/{raw['id']}.json"))
        return json_to_raw(item, raw["url"])
