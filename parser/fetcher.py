"""Klient HTTP bez przeglądarki: robots.txt, surowy HTML i pliki JSON."""
from urllib import robotparser
from urllib.parse import urljoin

import requests

from parser.retry import Pacer, with_retry

USER_AGENT = "PolnocParser/1.0 (laboratorium PJN)"


class TransientHTTPError(requests.HTTPError):
    """Błąd serwera (5xx), który warto ponowić."""


class Fetcher:
    """Pobiera zasoby jedną sesją, z odstępem między żądaniami i ponawianiem błędów przejściowych."""

    RETRYABLE = (requests.ConnectionError, requests.Timeout, TransientHTTPError)

    def __init__(self, pacer=None, timeout=10, attempts=4, session=None, sleep=None):
        self.pacer = pacer or Pacer()
        self.timeout = timeout
        self.attempts = attempts
        self.session = session or requests.Session()
        self.session.headers["User-Agent"] = USER_AGENT
        self.sleep = sleep
        self.requests = 0

    def _get_once(self, url):
        self.pacer.wait()
        self.requests += 1
        response = self.session.get(url, timeout=self.timeout)
        if response.status_code >= 500:
            raise TransientHTTPError(f"HTTP {response.status_code} dla {url}", response=response)
        response.raise_for_status()
        response.encoding = "utf-8"
        return response

    def _get(self, url):
        options = {"sleep": self.sleep} if self.sleep else {}
        return with_retry(lambda: self._get_once(url), f"GET {url}", self.RETRYABLE, self.attempts, **options)

    def get(self, url):
        return self._get(url).text

    def get_json(self, url):
        return self._get(url).json()

    def allowed(self, url):
        """Sprawdza robots.txt serwisu; brak pliku oznacza zgodę."""
        rules = robotparser.RobotFileParser()
        try:
            rules.parse(self.get(urljoin(url, "/robots.txt")).splitlines())
        except requests.HTTPError:
            return True
        return rules.can_fetch(USER_AGENT, url)
