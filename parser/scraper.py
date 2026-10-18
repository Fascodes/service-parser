"""Parser katalogu Północ (ocena 5.0).

    python -m parser.scraper                     # Selenium (domyślnie, headless)
    python -m parser.scraper --tryb json         # bez przeglądarki, z plików JSON strony
    python -m parser.scraper --wznow             # dokończ przerwany przebieg z checkpointu
"""
import argparse
import logging
import sys
import time
from collections import Counter
from pathlib import Path
from urllib.parse import urldefrag

from parser.cleaning import EUR_PLN, clean_record
from parser.export import DATA_FIELDS, Checkpoint, setup_logging, write_csv, write_json
from parser.extract import deduplicate, merge_detail
from parser.fetcher import Fetcher
from parser.retry import Pacer

MIN_RECORDS = 400
MIN_ATTRIBUTES = 22
SAVE_EVERY = 10  # co ile stron szczegółów zapisywać checkpoint

log = logging.getLogger("parser")


def crawl_listing(source, checkpoint, max_pages):
    """Strony listy po rel="next"; każda ukończona strona trafia do checkpointu."""
    state, errors = checkpoint.state, 0
    while not state["listing_done"]:
        url = state["next_url"]
        if not url or len(state["strony"]) >= max_pages:
            state["listing_done"] = True
            break
        url = urldefrag(url).url
        if url in {page["url"] for page in state["strony"]}:
            log.warning("Pętla w paginacji: %s już odwiedzony", url)
            state["listing_done"] = True
            break
        try:
            records, next_url, info = source.listing_page(url)
        except Exception as exc:  # źródło samo ponawia; tu zostaje tylko porażka ostateczna
            errors += 1
            log.error("Nie udało się wczytać strony %s: %s", url, exc)
            break  # next_url zostaje w checkpoincie, --wznow spróbuje ponownie
        number = len(state["strony"]) + 1
        for raw in records:
            raw["strona"] = number
        state["strony"].append({"strona": number, **info})
        state["wystapienia"].extend(records)
        state["next_url"] = next_url
        checkpoint.save()
        log.info("Strona %d: %d rekordów w DOM/JSON, %d w surowym HTML, porcje: %d",
                 number, len(records), info["surowy_html"], info["porcje"])
    return errors


def fetch_details(source, checkpoint, products):
    """Szczegóły każdego produktu; produkty już zapisane w checkpoincie są pomijane."""
    details, errors, pending = checkpoint.state["szczegoly"], 0, 0
    skipped = sum(raw["id"] in details for raw in products)
    if skipped:
        log.info("Checkpoint: %d szczegółów już pobranych, pomijam", skipped)
    for number, raw in enumerate(products, start=1):
        if raw["id"] in details:
            continue
        if not raw.get("url"):
            log.warning("%s: brak odnośnika do szczegółów", raw["id"])
            continue
        try:
            detail = source.detail(raw)
        except Exception as exc:
            errors += 1
            log.error("%s: nie udało się pobrać szczegółów: %s", raw["id"], exc)
            continue
        if detail is None:
            errors += 1
            log.error("%s: brak sekcji szczegółów", raw["id"])
            continue
        details[raw["id"]] = detail
        pending += 1
        if pending >= SAVE_EVERY:
            checkpoint.save()
            pending = 0
        if number % 50 == 0:
            log.info("Szczegóły: %d/%d", number, len(products))
    checkpoint.save()
    return errors


def scrape(source, checkpoint, max_pages=1000, limit=None, rate=EUR_PLN):
    """Lista -> deduplikacja -> szczegóły -> czyszczenie. Zwraca (rekordy, raport)."""
    started = time.monotonic()
    errors = crawl_listing(source, checkpoint, max_pages)
    occurrences = checkpoint.state["wystapienia"]
    unique = deduplicate(occurrences)
    duplicates = len(occurrences) - len(unique)
    log.info("Wystąpienia: %d, unikalne: %d, usunięte duplikaty: %d", len(occurrences), len(unique), duplicates)
    if limit:
        unique = unique[:limit]
    errors += fetch_details(source, checkpoint, unique)

    details = checkpoint.state["szczegoly"]
    records, rejected = [], []
    for raw in unique:
        merged = merge_detail(raw, details[raw["id"]]) if raw["id"] in details else raw
        record, problems = clean_record(merged, rate)
        for problem in problems:
            log.warning("%s: odrzucono %s=%r (%s)", problem["id"], problem["pole"], problem["wartosc"], problem["powod"])
        rejected.extend(problems)
        record.update(struktura=raw["struktura"], strona=raw["strona"])
        records.append(record)

    rejected_by_field = Counter(p["pole"] for p in rejected)
    report = {
        "tryb": source.name,
        "wznowiony": checkpoint.resumed,
        "strony": len(checkpoint.state["strony"]),
        "wystapienia": len(occurrences),
        "duplikaty_usuniete": duplicates,
        "rekordy": len(records),
        "atrybuty": len(DATA_FIELDS),
        "szczegoly_pobrane": sum(raw["id"] in details for raw in unique),
        "bledy": errors,
        "czas_s": round(time.monotonic() - started, 2),
        "html_vs_dom": {"strony_listy": checkpoint.state["strony"], "szczegoly": source.detail_comparison},
        # Odrzucona wartość też jest pusta w wyniku, więc braki liczymy bez niej.
        "braki": {f: sum(r[f] is None for r in records) - rejected_by_field[f] for f in DATA_FIELDS},
        "odrzucone": {f: rejected_by_field[f] for f in DATA_FIELDS},
        "odrzucone_wartosci": rejected,
    }
    return records, report


def make_source(options, fetcher, pacer, out_dir):
    if options.tryb == "json":
        from parser.json_source import JsonSource
        return JsonSource(fetcher)
    from parser.browser import BrowserSource  # Selenium importowany tylko w tym trybie
    return BrowserSource(fetcher, pacer, headless=not options.pokaz_przegladarke, timeout=options.timeout,
                         attempts=options.proby, error_dir=out_dir / "bledy")


def main(argv=None):
    args = argparse.ArgumentParser(description="Parser katalogu Północ (ocena 5.0).")
    args.add_argument("--url", default="http://127.0.0.1:8000/strona-1.html", help="pierwsza strona katalogu")
    args.add_argument("--tryb", choices=("selenium", "json"), default="selenium",
                      help="selenium: przeglądarka; json: pliki danych strony bez przeglądarki")
    args.add_argument("--out-dir", default="wyniki", help="katalog na wyniki, log, checkpoint i diagnostykę")
    args.add_argument("--pages", type=int, default=1000, help="maksymalna liczba stron listy")
    args.add_argument("--limit", type=int, help="przetwórz tylko N pierwszych produktów (szybkie próby)")
    args.add_argument("--delay", type=float, default=0.5, help="odstęp między żądaniami [s], min. 0,5")
    args.add_argument("--timeout", type=float, default=15, help="limit WebDriverWait [s]")
    args.add_argument("--proby", type=int, default=4, help="maks. liczba prób (opóźnienia 1 s, 2 s, 4 s…)")
    args.add_argument("--pokaz-przegladarke", action="store_true", help="uruchom Chrome z oknem (domyślnie headless)")
    args.add_argument("--wznow", action="store_true", help="kontynuuj z checkpoint.json w --out-dir")
    args.add_argument("--kurs-eur", type=float, default=EUR_PLN, help="kurs EUR->PLN dla kolumny cena_pln")
    args.add_argument("--sep", default=";", help="separator kolumn CSV (domyślnie ';' dla polskiego Excela)")
    args.add_argument("--decimal", default=",", help="separator dziesiętny w CSV (domyślnie ',')")
    options = args.parse_args(argv)
    if options.sep == options.decimal:
        args.error("--sep i --decimal muszą się różnić")
    if options.delay < 0.5:
        args.error("--delay musi wynosić co najmniej 0,5 s")
    if options.proby < 1:
        args.error("--proby musi wynosić co najmniej 1")

    out_dir = Path(options.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    checkpoint = Checkpoint(out_dir / "checkpoint.json", {"tryb": options.tryb, "url": options.url},
                            options.url, resume=options.wznow)
    setup_logging(out_dir / "parser.log", append=checkpoint.resumed)
    log.info("Start (%s%s): %s, odstęp %.1f s", options.tryb, ", wznowienie" if checkpoint.resumed else "",
             options.url, options.delay)

    pacer = Pacer(options.delay)
    fetcher = Fetcher(pacer, attempts=options.proby)
    if not fetcher.allowed(options.url):
        log.error("robots.txt zabrania pobierania %s", options.url)
        return 1
    source = make_source(options, fetcher, pacer, out_dir)
    try:
        records, report = scrape(source, checkpoint, options.pages, options.limit, options.kurs_eur)
    except KeyboardInterrupt:
        checkpoint.save()
        log.warning("Przerwano. Postęp zapisany w %s, dokończ z --wznow", checkpoint.path)
        return 130
    finally:
        source.close()

    write_csv(records, out_dir / "produkty.csv", options.sep, options.decimal)
    write_json(records, out_dir / "produkty.json")
    write_json(report, out_dir / "raport.json")

    complete = checkpoint.state["listing_done"] and report["bledy"] == 0
    if complete:
        checkpoint.remove()
    else:
        log.warning("Przebieg niepełny (błędy: %d). Checkpoint zachowany, ponów z --wznow", report["bledy"])
    comparison = ", ".join(f"s{p['strona']}: {p['surowy_html']}→{p.get('dom', p.get('json'))}"
                           for p in report["html_vs_dom"]["strony_listy"])
    log.info("Rekordy w surowym HTML → po skryptach: %s", comparison)
    log.info("Podsumowanie: tryb %s, strony %d, wystąpienia %d, rekordy %d, atrybuty %d, duplikaty %d, "
             "odrzucone wartości %d, błędy %d, żądania HTTP poza przeglądarką %d, czas %.1f s",
             report["tryb"], report["strony"], report["wystapienia"], report["rekordy"], report["atrybuty"],
             report["duplikaty_usuniete"], sum(report["odrzucone"].values()), report["bledy"],
             fetcher.requests, report["czas_s"])
    if options.limit is None and (report["rekordy"] < MIN_RECORDS or report["atrybuty"] < MIN_ATTRIBUTES):
        log.warning("Za mało danych: wymagane %d rekordów i %d atrybutów", MIN_RECORDS, MIN_ATTRIBUTES)
        return 2
    return 0 if complete else 3


if __name__ == "__main__":
    sys.exit(main())
