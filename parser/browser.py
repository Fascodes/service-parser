"""Źródło danych przez Selenium: doładowywanie porcji, strony szczegółów i interakcja z `details`.

Selenium steruje przeglądarką i czeka na warunki (WebDriverWait), a gotowy DOM
(`page_source`) parsuje BeautifulSoup tym samym kodem co w 4.0. Dzięki temu nie
przechowujemy uchwytów WebElement, które serwis odtwarza przy każdym renderowaniu.
"""
import logging
import re
import time
from pathlib import Path

from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

from parser.extract import count_fields, count_records, parse_detail, parse_listing
from parser.retry import with_retry

log = logging.getLogger("parser")
COUNTER = re.compile(r"Wczytano (\d+) z (\d+)")
LOAD_MORE = "#wczytaj-wiecej"
EXTRA_SUMMARY = "#dodatkowe-informacje > summary"
EXTRA_LAST_FIELD = '#dodatkowe-pola [data-pole="dostawca"]'

# Jedno wywołanie JS zamiast kilku find_element: stan listy w chwili sprawdzenia.
LISTING_STATE_JS = """
const q = (s) => document.querySelector(s);
const results = q('#wyniki'), error = q('#blad'), button = q('#wczytaj-wiecej'), counter = q('#licznik');
if (!results) return null;
return {busy: results.getAttribute('aria-busy') === 'true', error: !!error && !error.hidden,
        done: !button || button.hidden, counter: counter ? counter.textContent : ''};
"""
DETAIL_STATE_JS = """
if (document.querySelector('.product-detail[data-id]')) return 'ok';
const error = document.querySelector('#blad');
return error && !error.hidden ? 'error' : null;
"""


class PageError(Exception):
    """Serwis pokazał komunikat błędu zamiast danych."""


RETRYABLE = (WebDriverException, PageError)  # TimeoutException dziedziczy po WebDriverException


def portion_settled(loaded):
    """Warunek WebDriverWait: porcja wczytana (licznik większy niż `loaded`) albo błąd; None = czekaj dalej."""
    def condition(driver):
        state = driver.execute_script(LISTING_STATE_JS)
        if not state or state["busy"]:
            return None
        if state["error"]:
            return {"error": True}
        match = COUNTER.search(state["counter"])
        if match and int(match[1]) > loaded:
            return {"error": False, "loaded": int(match[1]), "total": int(match[2]), "done": state["done"]}
        return None
    return condition


class BrowserSource:
    name = "selenium"

    def __init__(self, fetcher, pacer, headless=True, timeout=15, attempts=4, error_dir=None):
        self.fetcher = fetcher  # tylko do pobrania surowego HTML na potrzeby porównania z DOM
        self.pacer = pacer
        self.attempts = attempts
        self.error_dir = Path(error_dir) if error_dir else None
        options = webdriver.ChromeOptions()
        if headless:
            options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,1000")
        options.add_argument("--log-level=3")
        self.driver = webdriver.Chrome(options=options)
        self.wait = WebDriverWait(self.driver, timeout, poll_frequency=0.2)
        self.detail_comparison = None

    def close(self):
        self.driver.quit()

    def retry(self, operation, description):
        return with_retry(operation, description, RETRYABLE, self.attempts, on_error=self.save_diagnostics)

    def save_diagnostics(self, description, attempt, exc):
        """Zrzut ekranu i źródło DOM przy każdym błędzie."""
        if not self.error_dir:
            return
        self.error_dir.mkdir(parents=True, exist_ok=True)
        stem = self.error_dir / f"{time.strftime('%Y%m%d-%H%M%S')}_{re.sub(r'[^A-Za-z0-9-]+', '_', description)[-60:]}_proba{attempt}"
        try:
            self.driver.save_screenshot(str(stem.with_suffix(".png")))
            stem.with_suffix(".html").write_text(self.driver.page_source, encoding="utf-8")
            log.info("Zapisano diagnostykę: %s.png/.html", stem)
        except WebDriverException as failure:
            log.warning("Nie udało się zapisać diagnostyki: %s", failure.msg)

    def open(self, url):
        self.pacer.wait()
        self.driver.get(url)

    def click(self, selector, pace=True):
        if pace:
            self.pacer.wait()
        element = self.wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
        # Strona ma `scroll-behavior: smooth`; bez natychmiastowego przewinięcia Selenium
        # klika w trakcie animacji i trafia w inny element (ElementClickInterceptedException).
        self.driver.execute_script("arguments[0].scrollIntoView({block: 'center', behavior: 'instant'});", element)
        element.click()

    def wait_for_portion(self, loaded):
        state = self.wait.until(portion_settled(loaded))
        if state["error"]:
            raise PageError("serwis zgłosił błąd wczytywania porcji")
        return state

    def listing_page(self, url):
        """Wczytuje wszystkie porcje strony listy i zwraca (rekordy, następna strona, statystyki)."""
        def first_portion():
            self.open(url)
            return self.wait_for_portion(0)

        state = self.retry(first_portion, f"porcja 1 {url}")
        portions = 1
        while not state["done"]:
            loaded = state["loaded"]

            def next_portion():
                # Po błędzie ten sam przycisk ma etykietę „Spróbuj ponownie” i ponawia tę samą porcję.
                self.click(LOAD_MORE)
                return self.wait_for_portion(loaded)

            state = self.retry(next_portion, f"porcja {portions + 1} {url}")
            portions += 1
            log.debug("%s: porcja %d, wczytano %d z %d", url, portions, state["loaded"], state["total"])

        records, next_url = parse_listing(self.driver.page_source, url)
        if len(records) != state["total"]:
            log.warning("%s: w DOM %d rekordów, licznik podaje %d", url, len(records), state["total"])
        info = {"url": url, "porcje": portions, "surowy_html": count_records(self.fetcher.get(url)), "dom": len(records)}
        return records, next_url, info

    def detail(self, raw):
        url = raw["url"]

        def load():
            self.open(url)
            if self.wait.until(lambda d: d.execute_script(DETAIL_STATE_JS)) == "error":
                raise PageError("serwis zgłosił błąd wczytywania szczegółów")
            before = count_fields(self.driver.page_source)
            # Cztery pola powstają w DOM dopiero po rozwinięciu sekcji.
            self.click(EXTRA_SUMMARY, pace=False)  # bez żądania do serwera, więc bez odstępu
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, EXTRA_LAST_FIELD)))
            return self.driver.page_source, before

        html, fields_before = self.retry(load, f"szczegóły {raw['id']}")
        if self.detail_comparison is None:
            self.detail_comparison = {"url": url, "surowy_html": count_fields(self.fetcher.get(url)),
                                      "dom_po_skryptach": fields_before, "dom_po_interakcji": count_fields(html)}
        return parse_detail(html, url)
