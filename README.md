# Północ — katalog do parsowania, ocena 5.0

Serwis do laboratorium „Parser strony WWW”, część **AUTOR**. Dane, marki i ceny są fikcyjne. Serwis nie prowadzi sprzedaży.

## Uruchomienie

Wymagany **Python 3.10+**, bez bibliotek zewnętrznych.

```powershell
git switch ocena-5
python serve.py
```

Otwórz **http://127.0.0.1:8000**. Na Windows można użyć `py` zamiast `python`. Inny port: `python serve.py --port 8001`. `Ctrl+C` zatrzymuje serwer. Po zmianie gałęzi zatrzymaj i uruchom go ponownie, aby przebudować katalog.

Sama generacja: `python build_site.py`. Wynik: ignorowany katalog `public/`, gotowy do udostępnienia serwerem statycznym. Nie edytuj `public/`, bo jest odtwarzany przy każdym uruchomieniu. Serwer udostępnia wyłącznie `public/`, nie pliki repozytorium.

## Wymagania na 5.0

| Wymaganie | Realizacja |
| --- | --- |
| Minimum 400 rekordów i paginacja z 4.0 | 400 unikalnych produktów, 408 wystąpień na 5 stronach |
| Minimum 10 atrybutów na liście | 12 pól, opis poniżej |
| Dwie struktury z poziomu 3.0 | Każda strona zawiera karty `article.produkt` i wiersze `tr.produkt` |
| Osobna strona każdego produktu | 400 stron `/produkty/PN-XXXX.html` |
| Minimum 8 dodatkowych atrybutów z 4.0 | 8 pól technicznych w szczegółach |
| Minimum 22 atrybuty na 5.0 | 24 pola: 12 na liście + 8 w szczegółach + 4 po interakcji |
| Semantyczne klasy i identyfikatory | `.produkt`, `data-id`, `data-pole` |
| Dane JSON dodawane przez `fetch` | Surowy HTML list i szczegółów nie zawiera rekordów |
| Doładowywanie porcjami | Przycisk „Wczytaj więcej”, porcje do 24 pozycji |
| Sztuczne opóźnienie | Losowo 300–2000 ms przed pobraniem każdej porcji |

Poziom 5 zastępuje wymaganie statycznego HTML z poziomów 3/4 dynamicznym renderowaniem. Zachowuje dwie struktury, paginację, szczegóły i trzy utrudnienia z 4.0. Statyczne warianty są na osobnych gałęziach.

Pola listy: `id`, `nazwa`, `cena`, `waluta`, `kategoria`, `producent`, `dostepnosc`, `ocena`, `liczba_opinii`, `data_dodania`, `gwarancja`, `url`. Gwarancja jest w miesiącach. `id` jest w `data-id`, waluta w `data-waluta` przy cenie. Link prowadzi do strony szczegółów.

Pola dodatkowe (wyłącznie w szczegółach): `sku`, `ean`, `waga_g`, `wysokosc_cm`, `szerokosc_cm`, `glebokosc_cm`, `kolor`, `kraj_pochodzenia`. EAN jest tekstem, masa w gramach, wymiary w centymetrach.

Po rozwinięciu „Materiały, zasilanie i dostawa” dochodzą: `material`, `zuzycie_energii_w`, `koszt_dostawy`, `dostawca`. Te elementy są tworzone w DOM dopiero po pierwszym otwarciu `details`. Koszt dostawy zawsze jest w PLN, zero oznacza dostawę gratis. Zużycie energii jest zerowe dla sprzętu bez zasilania.

## Trzy utrudnienia z poziomu 4.0

1. **Ceny lokalizowane i różne waluty.** Zapis `1 299,00 zł`, ze spacją nierozdzielającą U+00A0, oraz euro dla co siódmego produktu. Kod waluty jest przy cenie w `data-waluta`. Kwoty w różnych walutach nie nadają się do wspólnych statystyk bez przeliczenia; kurs użyty tylko do wygenerowania fikcyjnych cen EUR to 4,35 PLN/EUR.
2. **Braki w dwóch polach u 20% produktów.** `producent` i `gwarancja` są puste u 80 z 400 unikalnych produktów. JSON ma `null`, HTML ma puste elementy, a wizualną kreskę dodaje CSS. Brak nie jest tekstem `None` ani liczbą zero.
3. **Dokładnie 8 duplikatów między stronami.** Produkty `PN-0001`–`PN-0008` występują na stronie 1 oraz pojedynczo na stronach 2–5. Identyfikator i wartości są takie same. Po deduplikacji zostaje 400 rekordów.

Te utrudnienia ćwiczą normalizację cen, obsługę braków i deduplikację. Polskie znaki i encje HTML występują również w zwykłej treści, np. `Grań &amp; Szlak`.

## Dwa utrudnienia z poziomu 5.0

1. **Atrybuty po interakcji.** Cztery dodatkowe pola powstają dopiero po kliknięciu podsumowania `#dodatkowe-informacje`. Parser musi rozwinąć sekcję i zaczekać na pola, zamiast odczytywać tylko początkowy DOM.
2. **Filtrowanie i sortowanie bez przeładowania.** Wyszukiwanie po nazwie/marce/ID, filtr kategorii oraz sortowanie po nazwie, cenie i ocenie zmieniają DOM. Ceny są porównywane po demonstracyjnym kursie 4,35 PLN/EUR. Filtry obejmują wczytane pozycje bieżącej strony; przy doładowaniu pozostają aktywne. Do zebrania całego katalogu zostaw ustawienia domyślne.

Przy błędzie sieci pojawia się komunikat i przycisk ponowienia. Nieudana porcja nie przesuwa kursora ładowania i nie dodaje rekordów. Limit oczekiwania na pojedynczy `fetch` to 10 s. Nie wybrano limitu HTTP 429 ani losowej kolejności pól — nie są obowiązkowe, bo lista wymaga wyboru dwóch utrudnień.

## Dla partnera piszącego parser

- Rekordy: `.produkt[data-id]` (karty i tabela).
- Pola mają `data-pole`, np. `[data-pole="cena"]`. Waluta: `data-waluta` tego elementu.
- Link: `[data-pole="url"]` (w karcie to `a`, w tabeli `td` zawierające `a`).
- Kodowanie: UTF-8. Bez JS liczba rekordów wynosi **0**. Po doładowaniu całej strony: **80** na stronie 1 lub **82** na stronach 2–5. Razem: **408 wystąpień i 400 różnych ID**.
- Zacznij od `/strona-1.html`; następne strony wskazuje `.pagination a[rel="next"]`. `/` i `/index.html` to aliasy strony 1, nie dodatkowe strony katalogu.
- Dane szczegółowe są w `.product-detail [data-pole]`. Łącz z listą po `data-id`. Do eksportu usuń 8 nadmiarowych wystąpień.
- Klikaj `#wczytaj-wiecej` do ukrycia przycisku. Zamiast stałego `sleep` czekaj na wzrost liczby `.produkt[data-id]` i `#wyniki[aria-busy="false"]`. Przycisk jest blokowany w trakcie żądania.
- Odczytaj rekordy po zakończeniu doładowywania danej strony. Każde renderowanie dzieli aktualne wyniki na karty i tabelę, więc elementy DOM są odtwarzane i nie należy przechowywać starych uchwytów WebElement.
- Po wejściu w szczegóły czekaj na `.product-detail`, a po rozwinięciu sekcji na `[data-pole="dostawca"]`.
- Źródła: `/data/strona-1.json` zawiera listę plików porcji; `/data/strona-1-porcja-1.json` ma tylko 12 pól listy, a `/data/produkty/PN-0001.json` pełne 24 pola. Nazwy i etykiety: `/data/schema.json`.
- Zalecany odstęp między żądaniami: co najmniej 0,5 s.

## Weryfikacja

```powershell
python -m unittest discover -s tests -v
```

Testy standardowej biblioteki sprawdzają 5 stron i porcje JSON, 408 wystąpień/400 ID, rozrzucenie duplikatów, 400 stron szczegółów, 24 pola, braki, waluty, brak rekordów w surowym HTML oraz poprawność wewnętrznych odnośników.

Opcjonalne testy prawdziwej przeglądarki (Playwright jest potrzebny **tylko do tych testów**, nie do działania serwisu):

```powershell
npm install --no-save --package-lock=false playwright
npx playwright install chromium
# W drugim terminalu, gdy python serve.py już działa:
node tests/browser_check.cjs
```

Przy zainstalowanym Chrome można pominąć pobieranie Chromium: `$env:BROWSER_CHANNEL = 'chrome'`. Test sprawdza wszystkie strony, oba rodzaje rekordów, liczbę pól w DOM, filtrowanie, sortowanie, ujawnianie danych, błąd HTTP 503 i ponowienie, minimalne opóźnienie oraz układ mobilny. Zrzuty zapisuje w ignorowanym `test-results/`.

## Technologia i odtwarzalność

Python generuje HTML i JSON z deterministycznych danych w `catalog.py`. `serve.py` buduje katalog i serwuje sam `public/`. Przeglądarka używa zwykłego JavaScriptu, `fetch`, `Intl.NumberFormat` i zdarzeń DOM. CSS i ikona są lokalne; brak zewnętrznych fontów, obrazów, usług i zależności produkcyjnych. Dzięki temu partner może odtworzyć serwis bez kluczy API i dostępu do internetu.

`public/` jest artefaktem generowanym, a nie źródłem. Nie dodawaj go do Git. Można przekazać partnerowi repo albo folder `public/`, ale ten drugi musi być serwowany przez HTTP z katalogu głównego witryny (nie przez `file://` ani pod prefiksem ścieżki).

## Gałęzie

- `ocena-3` — katalog statyczny.
- `ocena-4` — paginacja, szczegóły i utrudnienia.
- `ocena-5` — dynamiczny JSON, doładowywanie i interakcje.

Każda gałąź jest samodzielną wersją. Po przełączeniu gałęzi ponownie uruchom serwer. Ten checkout kończy pracę na `ocena-5`; `main` zachowuje stan początkowy. Gałęzie są lokalne, dopóki właściciel nie wykona `git push`.

Repo realizuje część **AUTOR**. Test przeglądarkowy służy do kontroli serwisu. Parser partnera, analiza danych, wspólne sprawozdanie PDF i archiwum do oddania to osobne części zadania.
