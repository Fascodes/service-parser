"""Reproducible fictional products; Python standard library only."""
from datetime import date, timedelta

BASE_FIELDS = {
    "id": "ID", "nazwa": "Nazwa", "cena": "Cena", "waluta": "Waluta",
    "kategoria": "Kategoria", "producent": "Producent",
    "dostepnosc": "Dostępność", "ocena": "Ocena",
    "liczba_opinii": "Liczba opinii", "data_dodania": "Data dodania",
    "gwarancja": "Gwarancja (mies.)", "url": "Szczegóły",
}
CATEGORIES = (
    ("Plecaki", ("Plecak trekkingowy", "Plecak miejski", "Plecak wyprawowy"), 329),
    ("Namioty", ("Namiot dwuosobowy", "Namiot ekspedycyjny", "Namiot ultralekki"), 1299),
    ("Śpiwory", ("Śpiwór puchowy", "Śpiwór syntetyczny", "Śpiwór letni"), 459),
    ("Oświetlenie", ("Latarka czołowa", "Lampa biwakowa", "Latarka szlakowa"), 119),
    ("Nawigacja", ("Kompas turystyczny", "Nawigator terenowy", "Wysokościomierz"), 249),
    ("Kuchnia", ("Kuchenka turystyczna", "Zestaw naczyń", "Kubek termiczny"), 149),
    ("Odzież", ("Kurtka przeciwdeszczowa", "Polar trekkingowy", "Kamizelka puchowa"), 399),
    ("Akcesoria", ("Kije trekkingowe", "Mata samopompująca", "Worek wodoodporny"), 179),
)


def products(count):
    result = []
    for index in range(count):
        category, names, price = CATEGORIES[index % 8]
        model = ("Nord", "Horyzont", "Przełęcz", "Brzeg", "Grań")[index % 5]
        result.append({
            "id": f"PN-{index + 1:04}",
            "nazwa": f"{names[(index // 8) % 3]} {model} {index + 1:03}",
            "cena": round(price + (index * 37 % 800) + (index % 4) * .25, 2),
            "waluta": "PLN", "kategoria": category,
            "producent": ("Północ Outdoor", "Grań & Szlak", "Leśny Horyzont", "Bóbr Gear")[index % 4],
            "dostepnosc": ("Dostępny", "Dostępny", "Na zamówienie", "Niedostępny")[index % 4],
            "ocena": round(3.5 + (index * 7 % 16) / 10, 1),
            "liczba_opinii": 5 + index * 17 % 390,
            "data_dodania": (date(2026, 1, 1) + timedelta(days=index % 240)).isoformat(),
            "gwarancja": (12, 24, 36)[index % 3],
            "url": f"#produkt-PN-{index + 1:04}",
        })
    return result


def price_text(product):
    return f'{product["cena"]:.2f} {product["waluta"]}'
