"""HTTP client for data sources: retries with backoff and a polite delay."""

import time

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

USER_AGENT = (
    "ma-battery-prospecting/0.0.1 (+https://github.com/Ifrad/ma-battery-prospecting)"
)


def _retryable(exc: BaseException) -> bool:
    if isinstance(exc, httpx.HTTPStatusError):
        status = exc.response.status_code
        return status == 429 or status >= 500
    return isinstance(exc, httpx.TransportError)


class Client:
    """GET with retries on 429, 5xx and network errors.

    Waits at least `delay` seconds between requests so paged downloads do
    not hammer public servers.
    """

    def __init__(
        self,
        delay: float = 1.0,
        attempts: int = 5,
        transport: httpx.BaseTransport | None = None,
        sleep=time.sleep,
        clock=time.monotonic,
    ):
        self._http = httpx.Client(
            headers={"User-Agent": USER_AGENT},
            timeout=60,
            follow_redirects=True,
            transport=transport,
        )
        self._delay = delay
        self._sleep = sleep
        self._clock = clock
        self._last: float | None = None
        self._get_with_retry = retry(
            stop=stop_after_attempt(attempts),
            wait=wait_exponential(multiplier=1, min=1, max=60),
            retry=retry_if_exception(_retryable),
            sleep=sleep,
            reraise=True,
        )(self._get_once)

    def get(self, url: str, params: dict | None = None) -> httpx.Response:
        return self._get_with_retry(url, params)

    def _get_once(self, url: str, params: dict | None) -> httpx.Response:
        if self._last is not None:
            wait = self._delay - (self._clock() - self._last)
            if wait > 0:
                self._sleep(wait)
        try:
            response = self._http.get(url, params=params)
        finally:
            self._last = self._clock()
        response.raise_for_status()
        return response

    def close(self) -> None:
        self._http.close()

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()
