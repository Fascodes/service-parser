# Północ — katalog do parsowania, ocena 4.0

Serwis do laboratorium „Parser strony WWW”, część **AUTOR**. Dane, marki i ceny są fikcyjne. Serwis nie prowadzi sprzedaży.

## Uruchomienie

Wymagany **Python 3.10+**, bez bibliotek zewnętrznych.

```powershell
git switch ocena-4
python serve.py
```

Otwórz **http://127.0.0.1:8000**. Na Windows można użyć `py` zamiast `python`. Inny port: `python serve.py --port 8001`. `Ctrl+C` zatrzymuje serwer. Po zmianie gałęzi zatrzymaj i uruchom go ponownie, aby przebudować katalog.

Sama generacja: `python build_site.py`. Wynik: ignorowany katalog `public/`, gotowy do udostępnienia serwerem statycznym. Nie edytuj `public/`, bo jest odtwarzany przy każdym uruchomieniu. Serwer udostępnia wyłącznie `public/`, nie pliki repozytorium.

## Wymagania na 4.0

| Wymaganie | Realizacja |
| --- | --- |
| Minimum 200 rekordów i paginacja | 200 unikalnych produktów, 208 wystąpień na 5 stronach |
| Minimum 10 atrybutów na liście | 12 pól, opis poniżej |
| Dwie struktury z poziomu 3.0 | Każda strona zawiera karty `article.produkt` i wiersze `tr.produkt` |
| Osobna strona każdego produktu | 200 stron `/produkty/PN-XXXX.html` |
| Minimum 8 dodatkowych atrybutów | 8 nowych pól w szczegółach, razem 20 |
| Semantyczne klasy i identyfikatory | `.produkt`, `data-id`, `data-pole`, `#produkt-PN-0001` |
| Statyczny HTML bez JavaScriptu | Pełna treść podczas generowania, brak skryptów |

Pola listy: `id`, `nazwa`, `cena`, `waluta`, `kategoria`, `producent`, `dostepnosc`, `ocena`, `liczba_opinii`, `data_dodania`, `gwarancja`, `url`. Gwarancja jest w miesiącach. `id` jest w `data-id`, waluta w `data-waluta` przy cenie. Link prowadzi do strony szczegółów.

Pola dodatkowe (wyłącznie w szczegółach): `sku`, `ean`, `waga_g`, `wysokosc_cm`, `szerokosc_cm`, `glebokosc_cm`, `kolor`, `kraj_pochodzenia`. EAN jest tekstem, masa w gramach, wymiary w centymetrach.

## Wybrane utrudnienia (3 wymagane)

1. **Ceny lokalizowane i różne waluty.** Zapis `1 299,00 zł`, ze spacją nierozdzielającą U+00A0, oraz euro dla co siódmego produktu. Kod waluty jest przy cenie w `data-waluta`. Kwoty w różnych walutach nie nadają się do wspólnych statystyk bez przeliczenia; kurs użyty tylko do wygenerowania fikcyjnych cen EUR to 4,35 PLN/EUR.
2. **Braki w dwóch polach u 20% produktów.** `producent` i `gwarancja` są puste u 40 z 200 unikalnych produktów. HTML ma puste elementy, a wizualną kreskę dodaje CSS. Brak nie jest tekstem `None` ani liczbą zero.
3. **Dokładnie 8 duplikatów między stronami.** Produkty `PN-0001`–`PN-0008` występują na stronie 1 oraz pojedynczo na stronach 2–5. Identyfikator i wartości są takie same. Po deduplikacji zostaje 200 rekordów.

Te utrudnienia ćwiczą normalizację cen, obsługę braków i deduplikację. Polskie znaki i encje HTML występują również w zwykłej treści, np. `Grań &amp; Szlak`.

## Dla partnera piszącego parser

- Rekordy: `.produkt[data-id]` (karty i tabela).
- Pola mają `data-pole`, np. `[data-pole="cena"]`. Waluta: `data-waluta` tego elementu.
- Link: `[data-pole="url"]` (w karcie to `a`, w tabeli `td` zawierające `a`).
- Kodowanie: UTF-8. HTML zawiera rekordy bez wykonywania JS.
- Zacznij od `/strona-1.html`; następne strony wskazuje `.pagination a[rel="next"]`. `/` i `/index.html` to aliasy strony 1, nie dodatkowe strony katalogu.
- Dane szczegółowe są w `.product-detail [data-pole]`. Łącz z listą po `data-id`. Do eksportu usuń 8 nadmiarowych wystąpień.
- Zalecany odstęp między żądaniami: co najmniej 0,5 s.

## Weryfikacja

```powershell
python -m unittest discover -s tests -v
```

Testy sprawdzają oba rodzaje HTML, 5 stron, 208 wystąpień/200 ID, rozrzucenie duplikatów, kompletność 200 stron szczegółów, 20 pól, braki, waluty, brak JS i poprawność wszystkich wewnętrznych odnośników.

## Gałęzie

- `ocena-3` — katalog statyczny.
- `ocena-4` — paginacja, szczegóły i utrudnienia.
- `ocena-5` — dynamiczny JSON, doładowywanie i interakcje.

Każda gałąź jest samodzielną wersją. Repo realizuje część AUTOR. Parser partnera, analiza danych i wspólne sprawozdanie to osobne części zadania.
