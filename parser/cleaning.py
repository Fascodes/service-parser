"""Czyszczenie i walidacja wartości odczytanych ze strony.

Każdy konwerter przyjmuje surowy tekst i zwraca wartość docelowego typu albo
zgłasza ValueError, gdy tekst jest niepoprawny. Pusty tekst oznacza brak danych
i zawsze daje None, bez wyjątku.
"""
import math
import re
from datetime import datetime

EUR_PLN = 4.35  # kurs z README serwisu, użyty do wygenerowania cen w EUR
CURRENCIES = {"PLN", "EUR"}
DATE_FORMATS = ("%Y-%m-%d", "%d.%m.%Y", "%d/%m/%Y")


def clean_text(value):
    """Usuwa nadmiarowe białe znaki (w tym twarde spacje)."""
    return re.sub(r"\s+", " ", str(value).replace("\xa0", " ")).strip()


def to_finite_float(text):
    """float() przyjmuje też 'inf', 'nan' i '1e309' (-> inf); takie wartości odrzucamy.

    Sam zakres ich nie wyłapie: każde porównanie z NaN daje False, a inf przechodzi,
    gdy pole nie ma górnej granicy.
    """
    value = float(text)
    if not math.isfinite(value):
        raise ValueError("wartość nie jest skończoną liczbą (inf/NaN)")
    return value


def parse_price(text):
    """'1299.00 PLN' / '1 299,00 zł' / '209,37 €' -> float."""
    text = clean_text(text)
    if not text:
        return None
    digits = re.sub(r"[^\d,.\-]", "", text.replace(" ", ""))
    if not digits:
        raise ValueError("brak liczby w cenie")
    if "," in digits:
        digits = digits.replace(".", "").replace(",", ".")
    value = to_finite_float(digits)
    if value <= 0:
        raise ValueError("cena musi być dodatnia")
    return value


def number(kind, minimum=None, maximum=None):
    """Konwerter liczby całkowitej lub zmiennoprzecinkowej z opcjonalnym zakresem."""
    def convert(text):
        text = clean_text(text).replace(" ", "").replace(",", ".")
        if not text:
            return None
        value = to_finite_float(text)
        if kind is int:
            if not value.is_integer():
                raise ValueError("oczekiwano liczby całkowitej")
            value = int(value)
        if (minimum is not None and value < minimum) or (maximum is not None and value > maximum):
            raise ValueError(f"wartość poza zakresem [{minimum}, {maximum}]")
        return value
    return convert


def parse_date(text):
    """Ujednolica datę do formatu ISO (RRRR-MM-DD)."""
    text = clean_text(text)
    if not text:
        return None
    for date_format in DATE_FORMATS:
        try:
            return datetime.strptime(text, date_format).date().isoformat()
        except ValueError:
            pass
    raise ValueError("nieznany format daty")


def parse_ean(text):
    """EAN-13 jako tekst (zachowuje wiodące zera) ze sprawdzeniem cyfry kontrolnej."""
    text = clean_text(text).replace(" ", "")
    if not text:
        return None
    if not re.fullmatch(r"\d{13}", text):
        raise ValueError("EAN musi mieć 13 cyfr")
    checksum = sum(int(d) * (1 if i % 2 == 0 else 3) for i, d in enumerate(text[:12]))
    if (-checksum) % 10 != int(text[12]):
        raise ValueError("błędna cyfra kontrolna EAN")
    return text


def pattern(regex):
    def convert(text):
        text = clean_text(text)
        if not text:
            return None
        if not re.fullmatch(regex, text):
            raise ValueError(f"niezgodne ze wzorcem {regex}")
        return text
    return convert


def choice(allowed):
    def convert(text):
        text = clean_text(text)
        if not text:
            return None
        if text not in allowed:
            raise ValueError(f"spoza zbioru {sorted(allowed)}")
        return text
    return convert


def text(value):
    return clean_text(value) or None


SCHEMA = {
    "id": pattern(r"PN-\d{4}"),
    "nazwa": text,
    "cena": parse_price,
    "waluta": choice(CURRENCIES),
    "kategoria": text,
    "producent": text,
    "dostepnosc": text,
    "ocena": number(float, 0, 5),
    "liczba_opinii": number(int, 0),
    "data_dodania": parse_date,
    "gwarancja": number(int, 0),
    "url": pattern(r"https?://\S+"),
    "sku": pattern(r"[A-Z]+-\d+"),
    "ean": parse_ean,
    "waga_g": number(int, 1),
    "wysokosc_cm": number(float, 0.1),
    "szerokosc_cm": number(float, 0.1),
    "glebokosc_cm": number(float, 0.1),
    "kolor": text,
    "kraj_pochodzenia": text,
    # 5.0: pola tworzone w DOM dopiero po rozwinięciu sekcji szczegółów
    "material": text,
    "zuzycie_energii_w": number(float, 0),
    "koszt_dostawy": number(float, 0),  # zawsze PLN, 0 = dostawa gratis
    "dostawca": text,
}


def to_pln(price, currency, rate=EUR_PLN):
    if price is None or currency is None:
        return None
    return price if currency == "PLN" else round(price * rate, 2)


def clean_record(raw, rate=EUR_PLN):
    """Zwraca (rekord, odrzucenia); niepoprawna wartość staje się pustą, a nie wyjątkiem."""
    record, rejected = {}, []
    for field, convert in SCHEMA.items():
        value = raw.get(field)
        try:
            record[field] = None if value is None else convert(value)
        except ValueError as exc:
            record[field] = None
            rejected.append({"id": raw.get("id"), "pole": field, "wartosc": value, "powod": str(exc)})
    record["cena_pln"] = to_pln(record["cena"], record["waluta"], rate)
    return record, rejected
