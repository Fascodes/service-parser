# Parser katalogu Północ — ocena 3.0

Część **PARSER** laboratorium. Pobiera stronę katalogu partnera i zapisuje rekordy do CSV.

## Uruchomienie

```powershell
python -m pip install -r parser/requirements.txt
python serve.py                      # w osobnym terminalu
python -m parser.scraper --url http://127.0.0.1:8000/ --out produkty.csv --delay 0.5
```

Testy (budują stronę lokalnie, bez sieci):

```powershell
python -m unittest discover -s parser/tests -t . -v
```

## Realizacja wymagań 3.0

| Wymaganie | Realizacja |
| --- | --- |
| Jeden wiersz = jeden rekord, kolumna = atrybut | 13 kolumn: 12 pól serwisu + `struktura` (`karta`/`tabela`) |
| Minimum 60 wierszy z obu struktur | Selektor `.produkt[data-id]` obejmuje `article` i `tr`; 30 + 30 |
| Wspólny format | Pola po `[data-pole]`, nie po pozycji; `id` z `data-id`, `waluta` z `data-waluta`, link zamieniony na pełny URL |
| Cena jako liczba | `parse_price` usuwa walutę i spacje, obsługuje też przecinek dziesiętny |
| UTF-8, polskie znaki | Odpowiedź dekodowana jako UTF-8, CSV zapisany z BOM (`utf-8-sig`) dla Excela |
| Format CSV | Domyślnie jak w polskim Excelu: separator `;`, przecinek dziesiętny (`459,25`). Standardowy CSV: `--sep , --decimal .` |
| Opóźnienie między żądaniami | `Fetcher` trzyma odstęp `--delay` (domyślnie 0,5 s); przed stroną czyta `robots.txt` |
