import time
from collections.abc import Callable, Mapping
from typing import Any

import httpx

from app.market.types import ProviderError

USER_AGENT = "Mozilla/5.0 (compatible; portfolio-tracker/0.1)"
TIMEOUT_SECONDS = 20.0
RETRY_STATUSES = frozenset({429, 500, 502, 503, 504})
ATTEMPTS = 3
BACKOFF_SECONDS = 1.0

Sleep = Callable[[float], None]


def make_client(transport: httpx.BaseTransport | None = None) -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=TIMEOUT_SECONDS,
        follow_redirects=True,
        transport=transport,
    )


def get_with_retry(
    client: httpx.Client,
    url: str,
    *,
    params: Mapping[str, Any] | None = None,
    sleep: Sleep = time.sleep,
    attempts: int = ATTEMPTS,
    backoff: float = BACKOFF_SECONDS,
) -> httpx.Response:
    """GETs `url`, retrying network errors, 429 and 5xx with exponential backoff.

    Every other response (including 404) is returned as-is for the caller to interpret.
    """
    error = ProviderError(f"GET {url}: no attempt made")
    for attempt in range(attempts):
        if attempt:
            sleep(backoff * 2 ** (attempt - 1))
        try:
            response = client.get(url, params=params)
        except httpx.TransportError as exc:
            error = ProviderError(f"GET {url}: {exc.__class__.__name__}: {exc}")
            continue
        if response.status_code not in RETRY_STATUSES:
            return response
        error = ProviderError(f"GET {url}: HTTP {response.status_code}")
    raise error


def ensure_ok(response: httpx.Response) -> httpx.Response:
    if response.status_code >= 400:
        raise ProviderError(f"GET {response.request.url}: HTTP {response.status_code}")
    return response
