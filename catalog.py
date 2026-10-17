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

DETAIL_FIELDS = {
    "sku": "SKU", "ean": "EAN", "waga_g": "Waga (g)",
    "wysokosc_cm": "Wysokość (cm)", "szerokosc_cm": "Szerokość (cm)",
    "glebokosc_cm": "Głębokość (cm)", "kolor": "Kolor",
    "kraj_pochodzenia": "Kraj pochodzenia",
}

INTERACTIVE_FIELDS = {
    'material': 'Materiał', 'zuzycie_energii_w': 'Zużycie energii (W)',
    'koszt_dostawy': 'Koszt dostawy (PLN)', 'dostawca': 'Dostawca',
}


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
    for index, product in enumerate(result):
        product['url'] = f'/produkty/{product["id"]}.html'
        if index % 7 == 0:
            product['cena'] = round(product['cena'] / 4.35, 2)
            product['waluta'] = 'EUR'
        # Deliberate missing data: the same 20% of records lack both fields.
        if index % 5 == 0:
            product['producent'] = None
            product['gwarancja'] = None
        ean_base = f'590123{index + 1:06}'
        check_digit = (-sum(int(d) * (1 if i % 2 == 0 else 3)
                            for i, d in enumerate(ean_base))) % 10
        product.update({
            'sku': f'POL-{index + 1:06}', 'ean': ean_base + str(check_digit),
            'waga_g': 150 + index * 43 % 3500,
            'wysokosc_cm': round(10 + index * 3 % 65 + .5, 1),
            'szerokosc_cm': 8 + index * 7 % 42,
            'glebokosc_cm': 5 + index * 2 % 30,
            'kolor': ('Leśna zieleń', 'Grafit', 'Piaskowy', 'Granat')[index % 4],
            'kraj_pochodzenia': ('Polska', 'Czechy', 'Niemcy', 'Szwecja')[index % 4],
            'material': ('Poliamid', 'Poliester', 'Aluminium', 'Stal nierdzewna')[index % 4],
            'zuzycie_energii_w': round(1 + (index % 12) * .5, 1) if product['kategoria'] in ('Oświetlenie', 'Nawigacja') else 0,
            'koszt_dostawy': (0, 12.99, 15.99)[index % 3],
            'dostawca': ('Leśna Logistyka', 'Szlak Dystrybucja', 'Północ Partner')[index % 3],
        })
    return result


def catalogue_pages(records):
    if len(records) % 5:
        raise ValueError('The catalogue must split into five equal pages')
    size = len(records) // 5
    pages = [list(records[i * size:(i + 1) * size]) for i in range(5)]
    # Exactly 8 duplicate records, all on pages other than their originals.
    for index in range(8):
        pages[1 + index % 4].append(dict(records[index]))
    return pages


def price_text(product):
    amount = f'{product["cena"]:,.2f}'.replace(',', '\u00a0').replace('.', ',')
    return f'{amount} {"zł" if product["waluta"] == "PLN" else "€"}'
