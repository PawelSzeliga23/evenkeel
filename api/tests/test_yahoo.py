import datetime as dt
from collections.abc import Callable
from decimal import Decimal
from typing import Any

import httpx
import pytest

from app.market.http import make_client
from app.market.providers.yahoo import YahooPriceProvider, yahoo_symbol
from app.market.types import ProviderError, SplitEvent, SymbolNotFound

AUG_31_2300 = 1788217200  # 2026-08-31 23:00 UTC = 2026-09-01 01:00 in Frankfurt (gmtoffset 7200)
SEP_01_0700 = 1788246000  # 2026-09-01 07:00 UTC
SEP_04_0700 = 1788505200  # 2026-09-04 07:00 UTC
NVDA_JUN_07 = 1717767000  # 2024-06-07 13:30 UTC = 09:30 in New York (gmtoffset -14400)

Handler = Callable[[httpx.Request], httpx.Response]


def _chart(
    timestamps: list[int], closes: list[float | None], *, adjclose: list[float] | None = None,
    currency: str | None = "EUR", gmtoffset: int = 7200,
) -> dict[str, Any]:
    indicators: dict[str, Any] = {"quote": [{"close": closes}]}
    if adjclose is not None:
        indicators["adjclose"] = [{"adjclose": adjclose}]
    meta = {"currency": currency, "gmtoffset": gmtoffset}
    return {"chart": {"result": [{"meta": meta, "timestamp": timestamps, "indicators": indicators}], "error": None}}


def _serving(payload: Any, status: int = 200, seen: list[httpx.Request] | None = None) -> Handler:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(status, json=payload)

    return handler


def _provider(handler: Handler, sleep: Callable[[float], None] = lambda _: None) -> YahooPriceProvider:
    return YahooPriceProvider(make_client(httpx.MockTransport(handler)), sleep=sleep)


@pytest.mark.parametrize(
    ("xtb", "yahoo"),
    [
        ("SXR8.DE", "SXR8.DE"),
        ("EIMI.UK", "EIMI.L"),
        ("VIE.FR", "VIE.PA"),
        ("PKN.PL", "PKN.WA"),
        ("AAPL.US", "AAPL"),
        ("BRK.B.US", "BRK-B"),
        ("ASML.NL", None),
        ("BITCOIN", None),
        (".DE", None),
    ],
)
def test_xtb_ticker_maps_to_yahoo_symbol(xtb: str, yahoo: str | None) -> None:
    assert yahoo_symbol(xtb) == yahoo


def test_full_history_is_parsed_in_exchange_local_dates() -> None:
    seen: list[httpx.Request] = []
    payload = _chart([AUG_31_2300, SEP_04_0700], [711.719970703125, 713.7999877929688], adjclose=[700.5, 702.25])

    history = _provider(_serving(payload, seen=seen)).history("SXR8.DE", None)

    assert (history.symbol, history.currency) == ("SXR8.DE", "EUR")
    assert [(bar.date, bar.close, bar.adj_close) for bar in history.bars] == [
        (dt.date(2026, 9, 1), Decimal("711.72"), Decimal("700.5")),
        (dt.date(2026, 9, 4), Decimal("713.80"), Decimal("702.25")),
    ]
    assert seen[0].url.path == "/v8/finance/chart/SXR8.DE"
    assert (seen[0].url.params["period1"], seen[0].url.params["interval"]) == ("0", "1d")


def test_us_session_date_uses_new_york_offset() -> None:
    payload = _chart([NVDA_JUN_07], [120.88800048828125], currency="USD", gmtoffset=-14400)

    (bar,) = _provider(_serving(payload)).history("NVDA", None).bars

    assert (bar.date, bar.close) == (dt.date(2024, 6, 7), Decimal("120.888"))


def test_incremental_request_starts_at_midnight_utc_of_start_date() -> None:
    seen: list[httpx.Request] = []

    _provider(_serving(_chart([], []), seen=seen)).history("SXR8.DE", dt.date(2026, 9, 5))

    assert seen[0].url.params["period1"] == "1788566400"


def test_pence_quotes_are_converted_to_pounds() -> None:
    payload = _chart([SEP_01_0700, SEP_04_0700], [542.9000244140625, 558.5], currency="GBp", gmtoffset=3600)

    history = _provider(_serving(payload)).history("BP.L", None)

    assert history.currency == "GBP"
    assert [(bar.close, bar.adj_close) for bar in history.bars] == [(Decimal("5.429"), None), (Decimal("5.585"), None)]


def test_null_closes_are_skipped_and_same_day_bars_keep_the_last() -> None:
    payload = _chart([SEP_01_0700, SEP_04_0700, SEP_04_0700 + 8 * 3600], [None, 10.0, 10.5])

    history = _provider(_serving(payload)).history("SXR8.DE", None)

    assert [(bar.date, bar.close) for bar in history.bars] == [(dt.date(2026, 9, 4), Decimal("10.5"))]


def test_unknown_symbol_404_raises_symbol_not_found() -> None:
    payload = {"chart": {"result": None, "error": {"code": "Not Found", "description": "No data found"}}}

    with pytest.raises(SymbolNotFound) as caught:
        _provider(_serving(payload, status=404)).history("NOPE.DE", None)

    assert caught.value.symbol == "NOPE.DE"


def test_empty_result_is_symbol_not_found() -> None:
    with pytest.raises(SymbolNotFound):
        _provider(_serving({"chart": {"result": None, "error": None}})).history("NOPE.DE", None)


def test_server_errors_become_provider_error_after_retries() -> None:
    seen: list[httpx.Request] = []

    with pytest.raises(ProviderError):
        _provider(_serving({}, status=503, seen=seen)).history("SXR8.DE", None)

    assert len(seen) == 3


def test_non_json_response_is_provider_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, text="<html>verify you are human</html>")

    with pytest.raises(ProviderError, match="not JSON"):
        _provider(handler).history("SXR8.DE", None)


def test_missing_currency_is_provider_error() -> None:
    with pytest.raises(ProviderError, match="currency"):
        _provider(_serving(_chart([SEP_01_0700], [1.0], currency=None))).history("SXR8.DE", None)


def test_provider_pauses_after_each_request() -> None:
    sleeps: list[float] = []

    _provider(_serving(_chart([], [])), sleep=sleeps.append).history("SXR8.DE", None)

    assert sleeps == [0.5]


NVDA_JUN_10 = 1718026200  # 2024-06-10 13:30 UTC = 09:30 in New York: first session on the 10:1 basis


def _with_split(payload: dict[str, Any], timestamp: int, numerator: Any, denominator: Any) -> dict[str, Any]:
    event = {"date": timestamp, "numerator": numerator, "denominator": denominator, "splitRatio": f"{numerator}:{denominator}"}
    payload["chart"]["result"][0]["events"] = {"splits": {str(timestamp): event}}
    return payload


def test_split_events_are_requested_and_parsed_on_the_exchange_day() -> None:
    payload = _with_split(_chart([NVDA_JUN_10], [121.79], currency="USD", gmtoffset=-14400), NVDA_JUN_10, 10, 1)
    seen: list[httpx.Request] = []

    history = _provider(_serving(payload, seen=seen)).history("NVDA", None)

    assert seen[0].url.params["events"] == "split"
    assert history.splits == (SplitEvent(dt.date(2024, 6, 10), Decimal(1), Decimal(10)),)


def test_response_without_events_has_no_splits() -> None:
    history = _provider(_serving(_chart([SEP_01_0700], [711.72]))).history("SXR8.DE", None)
    assert history.splits == ()


def test_one_to_one_split_is_ignored() -> None:
    payload = _with_split(_chart([NVDA_JUN_10], [121.79], currency="USD", gmtoffset=-14400), NVDA_JUN_10, 1, 1)
    assert _provider(_serving(payload)).history("NVDA", None).splits == ()


def test_malformed_split_event_is_a_provider_error() -> None:
    payload = _with_split(_chart([NVDA_JUN_10], [121.79], currency="USD", gmtoffset=-14400), NVDA_JUN_10, "abc", 1)
    with pytest.raises(ProviderError):
        _provider(_serving(payload)).history("NVDA", None)


def test_parse_takes_the_name_and_kind_from_meta() -> None:
    payload = _chart([SEP_01_0700], [100.0])
    payload["chart"]["result"][0]["meta"].update({"longName": "Vanguard FTSE All-World UCITS ETF", "instrumentType": "ETF"})
    history = _provider(_serving(payload)).history("VWCE.DE", None)

    assert (history.name, history.kind) == ("Vanguard FTSE All-World UCITS ETF", "etf")


@pytest.mark.parametrize(("meta", "expected"), [
    ({"shortName": "Apple Inc.", "instrumentType": "EQUITY"}, ("Apple Inc.", "stock")),
    ({"instrumentType": "INDEX"}, (None, None)),
])
def test_parse_falls_back_to_the_short_name_and_unknown_kinds(meta: dict, expected: tuple) -> None:
    payload = _chart([SEP_01_0700], [100.0])
    payload["chart"]["result"][0]["meta"].update(meta)
    history = _provider(_serving(payload)).history("X", None)

    assert (history.name, history.kind) == expected
