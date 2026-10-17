"""Generate the catalogue for the current branch."""
import json
import shutil
from html import escape
from pathlib import Path
from catalog import BASE_FIELDS, DETAIL_FIELDS, INTERACTIVE_FIELDS, catalogue_pages, products

ROOT = Path(__file__).resolve().parent


def h(value):
    return escape(str(value), quote=True)


def shell(title, content, script=""):
    return f'''<!doctype html>
<html lang="pl"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="description" content="Północ — fikcyjny katalog sprzętu outdoorowego. Znajdź swój kierunek.">
<title>{h(title)} · Północ</title><link rel="icon" href="/assets/mark.svg" type="image/svg+xml">
<link rel="stylesheet" href="/assets/style.css"><link rel="stylesheet" href="/assets/details.css"><link rel="stylesheet" href="/assets/dynamic.css">{script}</head><body>
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


def dynamic_listing(page):
    headings = ''.join(f'<th scope="col">{h(label)}</th>' for key, label in BASE_FIELDS.items() if key not in ('id', 'waluta'))
    return f'''<section class="catalog-section" id="katalog" data-strona="{page}">
<div class="section-heading"><div><p class="eyebrow">DOBRZE BYĆ W DRODZE</p><h2>Wybierz swój ekwipunek</h2></div><span>Strona {page} z 5</span></div>
<form class="filters" role="search" id="filtry"><label>Szukaj produktu<input type="search" id="szukaj" placeholder="Nazwa, marka, kierunek…" autocomplete="off"></label>
<label>Kategoria<select id="kategoria"><option value="">Wszystkie kategorie</option></select></label>
<label>Sortowanie<select id="sortowanie"><option value="domyslne">Kolejność katalogu</option><option value="nazwa">Nazwa A–Z</option><option value="cena-rosnaco">Cena w PLN: rosnąco</option><option value="cena-malejaco">Cena w PLN: malejąco</option><option value="ocena">Najwyższa ocena</option></select></label>
<button class="reset-filters" type="reset">Wyczyść filtry ↺</button></form>
<p class="filter-note">Filtry dotyczą wczytanych produktów na tej stronie. Ceny EUR porównujemy po kursie 4,35 PLN/EUR.</p>
<div class="catalog-progress"><p id="licznik" role="status" aria-live="polite">Przygotowujemy katalog…</p><span class="progress-line" aria-hidden="true"><span id="postep"></span></span></div>
<div id="stan-ladowania" class="loading-state" role="status" hidden><span class="spinner" aria-hidden="true"></span> Pakujemy kolejną porcję ekwipunku…</div>
<div id="blad" class="error-state" role="alert" hidden></div><p id="brak-wynikow" class="empty-state" hidden>Nie znaleziono produktów. Zmień filtry lub wczytaj więcej.</p>
<div id="wyniki" aria-busy="false"><div class="section-label"><h3>Na pierwszy plan</h3><span>01 — KARTY PRODUKTÓW</span></div><div class="product-grid" id="karty-produktow"></div>
<div class="section-label table-label"><h3>Spójrz na szczegóły</h3><span>02 — ZESTAWIENIE</span></div><div class="table-scroll" role="region" aria-label="Tabela produktów" tabindex="0"><table class="product-table"><caption>Produkty w zestawieniu tabelarycznym</caption><thead><tr>{headings}</tr></thead><tbody id="wiersze-produktow"></tbody></table></div></div>
<div class="load-more"><button class="button button-dark" id="wczytaj-wiecej" type="button" disabled>Wczytaj więcej ↓</button><p id="koniec" hidden>To już cały ekwipunek na tej stronie. Odkryj następną.</p></div>
<noscript><p class="error-state">Włącz JavaScript, aby zobaczyć katalog i wczytywać produkty.</p></noscript></section>'''


def dynamic_detail(identifier):
    return f'''<section class="detail-page" id="szczegoly" data-id="{h(identifier)}"><a class="back-link" href="/strona-{(int(identifier[3:]) - 1) // 80 + 1}.html#katalog">← Wróć do katalogu</a>
<div id="stan-ladowania" class="loading-state" role="status"><span class="spinner" aria-hidden="true"></span> Przygotowujemy szczegóły produktu…</div>
<div id="blad" class="error-state" role="alert" hidden></div><button class="button button-dark" id="ponow-szczegoly" type="button" hidden>Spróbuj ponownie</button>
<div id="produkt-szczegoly" aria-busy="true"></div><noscript><p class="error-state">Włącz JavaScript, aby zobaczyć informacje o produkcie.</p></noscript></section>'''


def write_json(output, name, data):
    write(output, name, json.dumps(data, ensure_ascii=False, indent=2) + '\n')


def build(destination=None):
    grade = json.loads((ROOT / 'site_config.json').read_text(encoding='utf-8'))['grade']
    if grade != 5:
        raise ValueError('Use the matching branch for another grade')
    output = prepare_output(destination)
    records = products(400)
    write_json(output, 'data/schema.json', {'lista': BASE_FIELDS, 'szczegoly': DETAIL_FIELDS, 'interakcja': INTERACTIVE_FIELDS})
    script = '<script type="module" src="/assets/app.js"></script>'
    for page, items in enumerate(catalogue_pages(records), start=1):
        chunks = [items[start:start + 24] for start in range(0, len(items), 24)]
        filenames = []
        for chunk_number, chunk in enumerate(chunks, start=1):
            name = f'data/strona-{page}-porcja-{chunk_number}.json'
            filenames.append('/' + name)
            # The list never exposes the 12 detail attributes.
            write_json(output, name, [{key: p[key] for key in BASE_FIELDS} for p in chunk])
        write_json(output, f'data/strona-{page}.json', {'strona': page, 'liczba_rekordow': len(items), 'porcje': filenames})
        content = hero(len(records)) + dynamic_listing(page) + pagination(page)
        html = shell(f'Katalog — strona {page}', content, script + f'<link rel="canonical" href="/strona-{page}.html">')
        write(output, f'strona-{page}.html', html)
        if page == 1:
            write(output, 'index.html', html)
    for product in records:
        write_json(output, f'data/produkty/{product["id"]}.json', product)
        # Even the document title must not leak a record before JavaScript runs.
        write(output, f'produkty/{product["id"]}.html', shell('Szczegóły produktu', dynamic_detail(product['id']), script))
    about(output)
    return output


if __name__ == '__main__':
    print(f'Gotowe: {build()}')
