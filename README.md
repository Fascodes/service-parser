# Północ — katalog do parsowania, ocena 3.0

Serwis do laboratorium „Parser strony WWW”, część **AUTOR**. Dane, marki i ceny są fikcyjne. Serwis nie prowadzi sprzedaży.

## Uruchomienie

Wymagany **Python 3.10+**, bez bibliotek zewnętrznych.

```powershell
git switch ocena-3
python serve.py
```

Otwórz **http://127.0.0.1:8000**. Na Windows można użyć `py` zamiast `python`. Inny port: `python serve.py --port 8001`. `Ctrl+C` zatrzymuje serwer. Po zmianie gałęzi zatrzymaj i uruchom go ponownie, aby przebudować katalog.

Sama generacja: `python build_site.py`. Wynik: ignorowany katalog `public/`, gotowy do udostępnienia serwerem statycznym. Nie edytuj `public/`, bo jest odtwarzany przy każdym uruchomieniu. Serwer udostępnia wyłącznie `public/`, nie pliki repozytorium.

## Wymagania na 3.0

| Wymaganie | Realizacja |
| --- | --- |
| Minimum 60 rekordów | 60 różnych produktów na `/` |
| Minimum 10 atrybutów | 12 pól, opis poniżej |
| Dwie struktury | 30 kart `article.produkt` i 30 wierszy `tr.produkt` |
| Semantyczne klasy i identyfikatory | `.produkt`, `data-id`, `data-pole`, `#produkt-PN-0001` |
| Statyczny HTML bez JavaScriptu | Pełna treść podczas generowania, brak skryptów |

Pola: `id`, `nazwa`, `cena`, `waluta`, `kategoria`, `producent`, `dostepnosc`, `ocena`, `liczba_opinii`, `data_dodania`, `gwarancja`, `url`. Gwarancja jest w miesiącach. `id` jest w `data-id`, waluta w `data-waluta` przy cenie. Link na tym poziomie prowadzi do kotwicy produktu.

## Dla partnera piszącego parser

- Rekordy: `.produkt[data-id]` (karty i tabela).
- Pola mają `data-pole`, np. `[data-pole="cena"]`. Waluta: `data-waluta` tego elementu.
- Link: `[data-pole="url"]` (w karcie to `a`, w tabeli `td` zawierające `a`).
- Kodowanie: UTF-8. HTML zawiera rekordy bez wykonywania JS.
- Zalecany odstęp między żądaniami: co najmniej 0,5 s.

## Weryfikacja

```powershell
python -m unittest discover -s tests -v
```

Testy sprawdzają dane, oba rodzaje HTML, liczbę rekordów, pola, polskie znaki, brak JS i zasoby.

## Gałęzie

- `ocena-3` — katalog statyczny.
- `ocena-4` — paginacja, szczegóły i utrudnienia.
- `ocena-5` — dynamiczny JSON, doładowywanie i interakcje.

Każda gałąź jest samodzielną wersją. Repo realizuje część AUTOR. Parser partnera, analiza danych i wspólne sprawozdanie to osobne części zadania.
