from collections.abc import Callable

import httpx
import pytest

from app.market.http import USER_AGENT, ensure_ok, get_with_retry, make_client
from app.market.types import ProviderError

URL = "https://example.test/data"


def _client(statuses: list[int | Exception], seen: list[httpx.Request]) -> httpx.Client:
    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        outcome = statuses[min(len(seen), len(statuses)) - 1]
        if isinstance(outcome, Exception):
            raise outcome
        return httpx.Response(outcome, text="x")

    return make_client(httpx.MockTransport(handler))


def _recorder() -> tuple[list[float], Callable[[float], None]]:
    sleeps: list[float] = []
    return sleeps, sleeps.append


def test_server_error_is_retried_with_backoff() -> None:
    seen: list[httpx.Request] = []
    sleeps, sleep = _recorder()

    response = get_with_retry(_client([503, 503, 200], seen), URL, sleep=sleep)

    assert (response.status_code, len(seen), sleeps) == (200, 3, [1.0, 2.0])


def test_persistent_server_error_becomes_provider_error() -> None:
    seen: list[httpx.Request] = []
    sleeps, sleep = _recorder()

    with pytest.raises(ProviderError, match="HTTP 500"):
        get_with_retry(_client([500], seen), URL, sleep=sleep)

    assert (len(seen), sleeps) == (3, [1.0, 2.0])


def test_network_error_is_retried_then_reported() -> None:
    seen: list[httpx.Request] = []

    with pytest.raises(ProviderError, match="ConnectError"):
        get_with_retry(_client([httpx.ConnectError("refused")], seen), URL, sleep=lambda _: None)

    assert len(seen) == 3


def test_rate_limit_is_retried() -> None:
    seen: list[httpx.Request] = []

    response = get_with_retry(_client([429, 200], seen), URL, sleep=lambda _: None)

    assert (response.status_code, len(seen)) == (200, 2)


def test_not_found_is_returned_without_retry() -> None:
    seen: list[httpx.Request] = []

    response = get_with_retry(_client([404], seen), URL, sleep=lambda _: None)

    assert (response.status_code, len(seen)) == (404, 1)


def test_client_sends_user_agent_and_params() -> None:
    seen: list[httpx.Request] = []

    get_with_retry(_client([200], seen), URL, params={"format": "json"}, sleep=lambda _: None)

    assert seen[0].headers["user-agent"] == USER_AGENT
    assert seen[0].url.params["format"] == "json"


def test_ensure_ok_rejects_client_errors() -> None:
    seen: list[httpx.Request] = []
    response = get_with_retry(_client([400], seen), URL, sleep=lambda _: None)

    with pytest.raises(ProviderError, match="HTTP 400"):
        ensure_ok(response)
