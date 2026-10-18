"""Odstęp między żądaniami i ponawianie z opóźnieniem wykładniczym."""
import logging
import time

log = logging.getLogger("parser")


class Pacer:
    """Pilnuje minimalnego odstępu między kolejnymi żądaniami do serwera."""

    def __init__(self, delay=0.5):
        self.delay = delay
        self._last = None

    def wait(self):
        if self._last is not None:
            remaining = self.delay - (time.monotonic() - self._last)
            if remaining > 0:
                time.sleep(remaining)
        self._last = time.monotonic()


def with_retry(operation, description, retryable, attempts=4, base_delay=1.0,
               on_error=None, sleep=time.sleep):
    """Wywołuje operation(); po błędzie czeka 1 s, 2 s, 4 s… i próbuje ponownie, najwyżej `attempts` razy."""
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except retryable as exc:
            if on_error:
                on_error(description, attempt, exc)
            if attempt == attempts:
                log.error("%s: porażka po %d próbach (%s)", description, attempts, short(exc))
                raise
            delay = base_delay * 2 ** (attempt - 1)
            log.warning("%s: próba %d/%d nieudana (%s), ponowienie za %.0f s",
                        description, attempt, attempts, short(exc), delay)
            sleep(delay)


def short(exc):
    message = str(exc).strip().splitlines()
    return f"{type(exc).__name__}: {message[0]}" if message else type(exc).__name__
