"""Zapis wyników (CSV, JSON), checkpoint i konfiguracja logowania."""
import csv
import json
import logging
import os
from pathlib import Path

from parser.cleaning import SCHEMA

DATA_FIELDS = tuple(SCHEMA) + ("cena_pln",)
FIELDS = DATA_FIELDS + ("struktura", "strona")

log = logging.getLogger("parser")


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
    """Zapis atomowy: przerwanie w trakcie nie zostawi uszkodzonego pliku."""
    path = Path(path)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with tmp.open("w", encoding="utf-8") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


class Checkpoint:
    """Stan przebiegu zapisywany na dysk, aby przerwany parser mógł ruszyć od miejsca przerwania."""

    def __init__(self, path, key, start_url, resume=False):
        self.path = Path(path)
        self.resumed = False
        if resume and self.path.exists():
            state = json.loads(self.path.read_text(encoding="utf-8"))
            if state.get("klucz") == key:
                self.state, self.resumed = state, True
                return
            log.warning("Checkpoint %s dotyczy innego przebiegu (%s), zaczynam od nowa", self.path, state.get("klucz"))
        self.state = {"klucz": key, "next_url": start_url, "listing_done": False,
                      "strony": [], "wystapienia": [], "szczegoly": {}}

    def save(self):
        write_json(self.state, self.path)

    def remove(self):
        self.path.unlink(missing_ok=True)


def setup_logging(path, append=False):
    log.setLevel(logging.DEBUG)
    log.handlers.clear()
    file_handler = logging.FileHandler(path, mode="a" if append else "w", encoding="utf-8")
    file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)-7s %(message)s"))
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(logging.Formatter("%(levelname)s %(message)s"))
    log.addHandler(file_handler)
    log.addHandler(console)
