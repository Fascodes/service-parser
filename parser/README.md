# Parser katalogu Północ — ocena 4.0

Część **PARSER** laboratorium. Przechodzi przez wszystkie strony katalogu partnera, wchodzi w strony szczegółów, łączy dane, czyści je i zapisuje do CSV oraz JSON.

## Uruchomienie

```powershell
python -m pip install -r parser/requirements.txt
python serve.py                      # w osobnym terminalu
python -m parser.scraper --url http://127.0.0.1:8000/strona-1.html --out-dir wyniki
python -m parser.analiza --dir wyniki
```

Opcje parsera: `--pages` (limit stron listy), `--delay` (odstęp, min. 0,5 s), `--kurs-eur` (kurs dla `cena_pln`, domyślnie 4,35), `--sep` / `--decimal` (format CSV, domyślnie `;` i `,` dla polskiego Excela).

Wyniki w `wyniki/` (ignorowane przez git):

| Plik | Zawartość |
| --- | --- |
| `produkty.csv` | 200 rekordów × 23 kolumny, UTF-8 z BOM |
| `produkty.json` | te same dane z zachowaniem typów (`null` = brak) |
| `raport.json` | podsumowanie, braki i odrzucone wartości per kolumna |
| `parser.log` | przebieg: strony, duplikaty, konflikty, błędy, podsumowanie |
| `analiza/` | `analiza.md` i wykresy PNG do sprawozdania |

Testy (budują stronę lokalnie, bez sieci):

```powershell
python -m unittest discover -s parser/tests -t . -v
```

## Działanie

1. `robots.txt` → `/strona-1.html`, kolejne strony po `.pagination a[rel="next"]` (z ochroną przed pętlą).
2. Rekordy z kart i tabeli: `.produkt[data-id]`, pola po `[data-pole]`, waluta z `data-waluta`.
3. Deduplikacja po `data-id` (pierwsze wystąpienie; różniące się kopie są logowane).
4. Szczegóły: `.product-detail[data-id] [data-pole]` ze strony z `[data-pole="url"]`; brakujące pola listy uzupełniane, rozbieżności logowane.
5. Czyszczenie i walidacja (`parser/cleaning.py`): konwerter dla każdej kolumny, wartość niepoprawna → pusta + wpis w raporcie.

## Realizacja wymagań 4.0

| Wymaganie | Realizacja |
| --- | --- |
| Min. 200 rekordów i 18 atrybutów | 200 rekordów, 21 atrybutów danych (20 z serwisu + `cena_pln`) oraz `struktura`, `strona` |
| Wszystkie podstrony + szczegóły, łączenie | Paginacja po `rel="next"`, 200 stron szczegółów łączonych po `data-id` |
| Ceny jako liczby | `1 299,00 zł` / `209,37 €` → `1299.0` / `209.37`; `cena_pln` przelicza EUR |
| Ujednolicone formaty | Daty → ISO, liczby z przecinkiem lub kropką, EAN jako tekst |
| Usunięte duplikaty | 208 wystąpień → 200 rekordów |
| Brak danych = pusta wartość | `None` → puste pole CSV / `null` w JSON; błąd strony szczegółów nie przerywa działania |
| Opóźnienie min. 0,5 s | `Fetcher` pilnuje odstępu, `--delay` < 0,5 jest odrzucane |

## Wybrane rozszerzenia

1. **Walidacja typów wszystkich kolumn + raport odrzuceń.** `SCHEMA` w `cleaning.py` (wzorce, zakresy, zbiory wartości, suma kontrolna EAN). Raport w `raport.json` (`odrzucone`, `odrzucone_wartosci`) i w logu.
2. **Eksport do dwóch formatów:** CSV i JSON.
3. **Logowanie do pliku z podsumowaniem:** liczba stron, rekordów, duplikatów, odrzuceń, błędów, żądań i czas działania.

Dodatkowo: testy jednostkowe funkcji czyszczących i parametry linii poleceń.
