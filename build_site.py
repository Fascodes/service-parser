"""Generate the catalogue for the current branch."""
import json
import shutil
from html import escape
from pathlib import Path
from catalog import BASE_FIELDS, DETAIL_FIELDS, catalogue_pages, price_text, products

ROOT = Path(__file__).resolve().parent


def h(value):
    return escape(str(value), quote=True)


def value_text(product, field):
    value = product.get(field)
    return "" if value is None else str(value)


def shell(title, content, script=""):
    return f'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Północ — fikcyjny katalog sprzętu outdoorowego. Znajdź swój kierunek.">
<title>{h(title)} · Północ</title><link rel="icon" href="/assets/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/style.css"><link rel="stylesheet" href="/assets/details.css">{script}</head><body>
<a class="skip-link" href="#main">Przejdź do treści</a>
<header class="header"><div class="header-inner"><a class="brand" href="/"><span class="brand-mark" aria-hidden="true">↗</span> północ<span class="brand-dot">.</span></a>
<nav aria-label="Główna nawigacja"><a href="/#katalog">Katalog</a><a href="/o-katalogu.html">O katalogu</a></nav>
<span class="header-note">MNIEJ RZECZY. WIĘCEJ DROGI.</span></div></header>
<main id="main">{content}</main><footer class="footer"><a class="brand" href="/">północ.</a><p>Twój następny krok zaczyna się tutaj.</p><span>Fikcyjny katalog edukacyjny · 2026</span></footer></body></html>'''


def hero(unique):
    return f'''<section class="hero"><div><p class="eyebrow"><span></span> EKWIPUNEK NA DOBRĄ DROGĘ</p>
<h1>Znajdź swój<br><em>kierunek.</em></h1><p class="hero-copy">Od pierwszego szlaku po daleki horyzont.<br>Sprzęt, z którym ruszysz dalej.</p>
<a class="button button-dark" href="#katalog">Odkryj katalog <span aria-hidden="true">↘</span></a></div>
<div class="hero-map" aria-hidden="true"><div class="contour contour-one"></div><div class="contour contour-two"></div><div class="contour contour-three"></div><span class="map-north">N</span><span class="map-cross">✳</span><span class="map-location">52°13′ N &nbsp; 21°00′ E</span><span class="map-caption">POZA UTARTYM SZLAKIEM</span></div></section>
<section class="stats" aria-label="Katalog w liczbach"><div><strong>{unique}</strong><span>produktów do odkrycia</span></div><div><strong>08</strong><span>kategorii na szlak</span></div><div><strong>01</strong><span>kierunek: przed siebie</span></div></section>'''


def fields_dl(product, fields):
    return '<dl class="product-facts">' + "".join(
        f'<div><dt>{h(label)}</dt><dd data-pole="{field}">{h(value_text(product, field))}</dd></div>'
        for field, label in fields.items()) + '</dl>'


def card(product):
    fields = {k: v for k, v in BASE_FIELDS.items() if k not in ("id", "nazwa", "cena", "waluta", "kategoria", "url")}
    return f'''<article class="produkt product-card" data-id="{h(product['id'])}" id="produkt-{h(product['id'])}">
<div class="product-visual" aria-hidden="true"><span>{h(product['kategoria'])}</span><strong>↗</strong><small>{h(product['id'])}</small></div>
<div class="product-body"><span class="category" data-pole="kategoria">{h(product['kategoria'])}</span><h3 data-pole="nazwa">{h(product['nazwa'])}</h3>
<p class="price" data-pole="cena" data-waluta="{h(product['waluta'])}">{h(price_text(product))}</p>
{fields_dl(product, fields)}<a class="product-link" data-pole="url" href="{h(product['url'])}">Zobacz produkt <span aria-hidden="true">↗</span></a></div></article>'''


def table(records):
    fields = {k: v for k, v in BASE_FIELDS.items() if k not in ("id", "waluta")}
    header = ''.join(f'<th scope="col">{h(label)}</th>' for label in fields.values())
    rows = []
    for product in records:
        cells = []
        for field in fields:
            content, extra = h(value_text(product, field)), ''
            if field == 'cena':
                content = h(price_text(product))
                extra = f' data-waluta="{h(product["waluta"])}"'
            elif field == 'url':
                content = f'<a href="{h(product[field])}">Zobacz ↗</a>'
            cells.append(f'<td data-pole="{field}"{extra}>{content}</td>')
        rows.append(f'<tr class="produkt" data-id="{h(product["id"])}" id="produkt-{h(product["id"])}">' + ''.join(cells) + '</tr>')
    return f'''<div class="table-scroll" role="region" aria-label="Tabela produktów" tabindex="0"><table class="product-table"><caption>Produkty w zestawieniu tabelarycznym</caption><thead><tr>{header}</tr></thead><tbody>{''.join(rows)}</tbody></table></div>'''


def listing(records):
    midpoint = len(records) // 2
    return f'''<section class="catalog-section" id="katalog"><div class="section-heading"><div><p class="eyebrow">DOBRZE BYĆ W DRODZE</p><h2>Wybierz swój ekwipunek</h2></div><span>{len(records)} pozycji</span></div>
<div class="section-label"><h3>Na pierwszy plan</h3><span>01 — KARTY PRODUKTÓW</span></div><div class="product-grid">{''.join(card(p) for p in records[:midpoint])}</div>
<div class="section-label table-label"><h3>Spójrz na szczegóły</h3><span>02 — ZESTAWIENIE</span></div>{table(records[midpoint:])}</section>'''


def write(output, name, content):
    target = output / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding='utf-8', newline='\n')


def prepare_output(destination=None):
    output = ROOT / 'public' if destination is None else Path(destination)
    if destination is None and output.exists():
        # Delete only our resolved generated folder, never a symlink or another path.
        if output.is_symlink() or output.resolve() != ROOT / 'public':
            raise ValueError('Unsafe output directory')
        shutil.rmtree(output)
    output.mkdir(parents=True, exist_ok=True)
    if any(output.iterdir()):
        raise ValueError('Build destination must be empty')
    shutil.copytree(ROOT / 'assets', output / 'assets')
    return output


def about(output):
    write(output, 'o-katalogu.html', shell('O katalogu', '''<section class="info-page"><p class="eyebrow">O NAS</p><h1>Blisko natury.<br>Daleko od pośpiechu.</h1><p>Północ to fikcyjny katalog sprzętu outdoorowego przygotowany do nauki pozyskiwania danych ze stron WWW. Produkty, marki i ceny są przykładowe. Serwis nie prowadzi sprzedaży.</p><a class="button button-dark" href="/">Wróć do katalogu ↗</a></section>'''))
    write(output, 'robots.txt', 'User-agent: *\nAllow: /\n# Katalog edukacyjny. Zalecany odstęp między żądaniami: 0.5 s.\n')


def pagination(page):
    links = []
    if page > 1:
        links.append(f'<a rel="prev" href="/strona-{page - 1}.html#katalog">← Poprzednia</a>')
    for number in range(1, 6):
        current = ' aria-current="page"' if number == page else ''
        links.append(f'<a href="/strona-{number}.html#katalog"{current}>{number}</a>')
    if page < 5:
        links.append(f'<a rel="next" href="/strona-{page + 1}.html#katalog">Następna →</a>')
    return '<nav class="pagination" aria-label="Strony katalogu">' + ''.join(links) + '</nav>'


def detail(product):
    fields = {k: v for k, v in BASE_FIELDS.items() if k not in ('id', 'nazwa', 'cena', 'waluta', 'kategoria', 'url')}
    original_page = (int(product['id'][3:]) - 1) // 40 + 1
    return f'''<section class="detail-page"><a class="back-link" href="/strona-{original_page}.html#katalog">← Wróć do katalogu</a>
<article class="produkt product-detail" data-id="{h(product['id'])}"><div class="detail-lead"><div><p class="eyebrow" data-pole="kategoria">{h(product['kategoria'])}</p><h1 data-pole="nazwa">{h(product['nazwa'])}</h1><p class="price" data-pole="cena" data-waluta="{h(product['waluta'])}">{h(price_text(product))}</p><a data-pole="url" class="permalink" href="{h(product['url'])}">Stały link do produktu ↗</a></div>
<div class="detail-visual" aria-hidden="true"><span>↗</span><small>{h(product['id'])}</small></div></div>
<div class="detail-columns"><section><h2>Informacje o produkcie</h2>{fields_dl(product, fields)}</section><section><h2>Specyfikacja techniczna</h2>{fields_dl(product, DETAIL_FIELDS)}</section></div></article></section>'''


def build(destination=None):
    output = prepare_output(destination)
    records = products(200)
    for page, items in enumerate(catalogue_pages(records), start=1):
        content = hero(len(records)) + listing(items) + pagination(page)
        html = shell(f'Katalog — strona {page}', content,
                     f'<link rel="canonical" href="/strona-{page}.html">')
        write(output, f'strona-{page}.html', html)
        if page == 1:
            write(output, 'index.html', html)
    for product in records:
        write(output, f'produkty/{product["id"]}.html', shell(product['nazwa'], detail(product)))
    about(output)
    return output


if __name__ == '__main__':
    print(f'Gotowe: {build()}')
