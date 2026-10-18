# Parser katalogu Północ — ocena 5.0

Część **PARSER** laboratorium. Serwis na 5.0 dodaje rekordy JavaScriptem (`fetch` + JSON), doładowuje je porcjami po kliknięciu „Wczytaj więcej”, a 4 pola szczegółów tworzy dopiero po rozwinięciu sekcji `details`. Surowy HTML nie zawiera żadnego rekordu, dlatego główny tryb parsera steruje przeglądarką przez **Selenium**.

## Uruchomienie

```powershell
python -m pip install -r parser/requirements.txt
python serve.py                                   # w osobnym terminalu
python -m parser.scraper                          # Selenium, Chrome headless, ok. 15 min
python -m parser.analiza --dir wyniki
```

Wymagany zainstalowany Chrome. Pasujący `chromedriver` pobiera automatycznie Selenium Manager.

| Opcja | Działanie |
| --- | --- |
| `--tryb selenium\|json` | przeglądarka (domyślnie) albo pliki JSON strony bez przeglądarki |
| `--wznow` | dokończ przerwany przebieg z `wyniki/checkpoint.json` |
| `--pages N`, `--limit N` | limit stron listy / produktów (szybkie próby) |
| `--pokaz-przegladarke` | Chrome z widocznym oknem zamiast headless |
| `--delay` | odstęp między żądaniami, min. 0,5 s |
| `--timeout`, `--proby` | limit `WebDriverWait` [s] i maks. liczba prób (opóźnienia 1 s, 2 s, 4 s…) |
| `--out-dir`, `--url`, `--kurs-eur`, `--sep`, `--decimal` | jak w 4.0 |

Wyniki w `wyniki/` (ignorowane przez git):

| Plik | Zawartość |
| --- | --- |
| `produkty.csv` / `produkty.json` | 400 rekordów, 25 atrybutów danych + `struktura`, `strona` |
| `raport.json` | podsumowanie, porównanie surowy HTML ↔ DOM, braki i odrzucenia |
| `parser.log` | przebieg, ponowienia, błędy i podsumowanie |
| `bledy/` | zrzut ekranu PNG + źródło DOM przy każdym błędzie |
| `checkpoint.json` | stan przerwanego lub niepełnego przebiegu (usuwany po pełnym sukcesie) |
| `analiza/` | `analiza.md` i wykresy do sprawozdania |

Testy (serwis uruchamiany lokalnie w wątku; test Selenium pomijany bez Chrome):

```powershell
python -m unittest discover -s parser/tests -t . -v
```

## Budowa

| Moduł | Rola |
| --- | --- |
| `scraper.py` | CLI i przebieg: lista → deduplikacja → szczegóły → czyszczenie → eksport, checkpoint |
| `browser.py` | źródło Selenium: porcje, szczegóły, `details`, diagnostyka błędów |
| `json_source.py` | źródło JSON: te same pliki, które pobiera strona |
| `extract.py` | selektory BeautifulSoup, deduplikacja, łączenie listy ze szczegółami |
| `cleaning.py` | konwersja i walidacja 24 pól |
| `retry.py`, `fetcher.py` | odstęp między żądaniami, ponawianie wykładnicze, HTTP bez przeglądarki |
| `export.py`, `analiza.py` | CSV/JSON, checkpoint, log; analiza danych |

## Działanie w trybie Selenium

1. **Lista.** `driver.get("/strona-N.html")`, potem `WebDriverWait` z własnym warunkiem `portion_settled`: `#wyniki[aria-busy="false"]` i licznik „Wczytano X z Y” większy niż przed kliknięciem albo widoczny `#blad`. Klik `#wczytaj-wiecej` aż przycisk zniknie. Brak stałych `sleep` przy oczekiwaniu na dane.
2. **Odczyt.** Po wczytaniu wszystkich porcji `page_source` trafia do BeautifulSoup (te same selektory co w 4.0: `.produkt[data-id]`, `[data-pole]`). Serwis przebudowuje DOM przy każdej porcji, więc nie trzymamy uchwytów `WebElement` (brak `StaleElementReferenceException`).
3. **Szczegóły.** Czekamy na `.product-detail[data-id]`, klikamy `#dodatkowe-informacje > summary` i czekamy na `#dodatkowe-pola [data-pole="dostawca"]`.
4. **Błędy.** Każda operacja (porcja, strona szczegółów) jest ponawiana z opóźnieniem 1 s, 2 s, 4 s, maks. `--proby` razy. Po błędzie porcji klik w ten sam przycisk („Spróbuj ponownie”) ponawia ją w serwisie. Przy każdym błędzie zapis PNG + HTML do `wyniki/bledy/`.
5. **Klikanie.** Strona ma `scroll-behavior: smooth`, więc przed kliknięciem element jest przewijany natychmiast na środek ekranu (inaczej `ElementClickInterceptedException`).

## Realizacja wymagań 5.0

| Wymaganie | Realizacja |
| --- | --- |
| Parser oparty o Selenium | `browser.py`, Chrome (domyślnie headless) |
| Jawne oczekiwanie (`WebDriverWait`) | warunki: porcja wczytana / błąd, `element_to_be_clickable`, `presence_of_element_located` |
| Doładowywanie do wyczerpania | klikanie `#wczytaj-wiecej` aż zniknie; kontrola liczby w DOM z licznikiem |
| Ponawianie z opóźnieniem wykładniczym i limitem | `retry.with_retry`: 1 s, 2 s, 4 s…, `--proby` (domyślnie 4) |
| Min. 400 rekordów i 22 atrybuty | 400 rekordów, 24 pola serwisu + `cena_pln` |
| Porównanie surowy HTML ↔ DOM | `raport.json` → `html_vs_dom`, oraz log (liczby niżej) |

## Wybrane rozszerzenia

1. **Zrzut ekranu i źródło strony przy każdym błędzie** — `BrowserSource.save_diagnostics`, wywoływane przez `with_retry` przy każdej nieudanej próbie.
2. **Wznawianie od checkpointu** — `wyniki/checkpoint.json` zapisywany po każdej stronie listy i co 10 stron szczegółów (zapis atomowy). `--wznow` pomija ukończone strony i produkty, ponawia tylko nieudane. Ctrl+C zapisuje postęp.
3. **Wykrycie i wykorzystanie źródła danych (JSON)** — `--tryb json`. Surowy HTML listy zawiera paginację i `#katalog[data-strona]`, a `assets/app.js` pobiera `/data/strona-N.json` (lista porcji), porcje z 12 polami i `/data/produkty/ID.json` z kompletem 24 pól. Wyniki są identyczne z trybem Selenium.

## Porównanie surowego HTML z DOM (do sprawozdania)

WYNIKI_PORÓWNANIA
