import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import httpx
import pytest

from app.market.http import make_client
from app.market.providers.nbp import NbpFxProvider, NbpRefRateProvider, date_chunks, parse_ref_rates
from app.market.types import ProviderError

Handler = Callable[[httpx.Request], httpx.Response]

ARCHIVE = (
    '<?xml version="1.0" encoding="UTF-8"?>\n'
    '<stopy_procentowe_archiwum xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance" data_publikacji="2015-03-04">\n'
    '  <pozycje obowiazuje_od="1998-02-26">\n'
    '    <pozycja id="ref" oprocentowanie="24,00" />\n'
    '    <pozycja id="lom" oprocentowanie="27,00" />\n'
    '  </pozycje>\n'
    '  <pozycje obowiazuje_od="2025-12-04">\n'
    '    <pozycja id="ref" oprocentowanie="4,00" />\n'
    '    <pozycja id="lom" oprocentowanie="4,50" />\n'
    '  </pozycje>\n'
    '</stopy_procentowe_archiwum>\n'
).encode()

CURRENT = (
    '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>\n'
    '<stopy_procentowe data_publikacji="2026-03-05">\n'
    '  <tabela id="stoproc" naglowek="Stopa procentowa:">\n'
    '    <pozycja id="ref" nazwa="Stopa referencyjna" oprocentowanie="3,75" obowiazuje_od="2026-03-05" />\n'
    '    <pozycja id="lom" nazwa="Stopa lombardowa" oprocentowanie="4,25" obowiazuje_od="2026-03-05" />\n'
    '  </tabela>\n'
    '</stopy_procentowe>\n'
).encode()


def _fx(handler: Handler) -> NbpFxProvider:
    return NbpFxProvider(make_client(httpx.MockTransport(handler)), sleep=lambda _: None)


def _rates_json(*items: tuple[str, str]) -> bytes:
    rates = ",".join(
        f'{{"no":"{i}/A/NBP/2026","effectiveDate":"{day}","mid":{mid}}}' for i, (day, mid) in enumerate(items, 1)
    )
    return f'{{"table":"A","currency":"euro","code":"EUR","rates":[{rates}]}}'.encode()


def test_date_chunks_never_exceed_93_days() -> None:
    assert date_chunks(dt.date(2026, 1, 1), dt.date(2026, 7, 19)) == [
        (dt.date(2026, 1, 1), dt.date(2026, 4, 3)),
        (dt.date(2026, 4, 4), dt.date(2026, 7, 5)),
        (dt.date(2026, 7, 6), dt.date(2026, 7, 19)),
    ]


def test_date_chunks_single_day_and_empty_range() -> None:
    day = dt.date(2026, 9, 7)

    assert date_chunks(day, day) == [(day, day)]
    assert date_chunks(day, day - dt.timedelta(days=1)) == []


def test_rates_are_fetched_in_chunks_and_missing_chunks_are_empty() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        if "/2026-04-04/" in request.url.path:
            return httpx.Response(200, content=_rates_json(("2026-04-07", "4.2627"), ("2026-04-08", "4.3100")))
        return httpx.Response(404, text="404 NotFound - Not Found - Brak danych")

    points = _fx(handler).rates("EUR", dt.date(2026, 1, 1), dt.date(2026, 7, 19))

    assert [request.url.path for request in seen] == [
        "/api/exchangerates/rates/a/eur/2026-01-01/2026-04-03/",
        "/api/exchangerates/rates/a/eur/2026-04-04/2026-07-05/",
        "/api/exchangerates/rates/a/eur/2026-07-06/2026-07-19/",
    ]
    assert all(request.url.params["format"] == "json" for request in seen)
    assert [(point.date, str(point.rate_pln)) for point in points] == [
        (dt.date(2026, 4, 7), "4.2627"), (dt.date(2026, 4, 8), "4.3100"),
    ]


def test_start_before_table_a_history_is_clamped() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_rates_json(("2002-01-02", "3.9860")))

    _fx(handler).rates("USD", dt.date(2001, 6, 1), dt.date(2002, 1, 10))

    assert [request.url.path for request in seen] == ["/api/exchangerates/rates/a/usd/2002-01-02/2002-01-10/"]


def test_empty_range_makes_no_requests() -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(200, content=_rates_json())

    assert _fx(handler).rates("EUR", dt.date(2026, 9, 8), dt.date(2026, 9, 7)) == []
    assert seen == []


def test_bad_request_is_provider_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(400, text="400 BadRequest - Limit exceeded")

    with pytest.raises(ProviderError, match="HTTP 400"):
        _fx(handler).rates("EUR", dt.date(2026, 9, 1), dt.date(2026, 9, 7))


def test_malformed_rates_payload_is_provider_error() -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b'{"table":"A"}')

    with pytest.raises(ProviderError):
        _fx(handler).rates("EUR", dt.date(2026, 9, 1), dt.date(2026, 9, 7))


def test_parse_ref_rates_reads_archive_and_current_formats() -> None:
    assert parse_ref_rates(ARCHIVE) == {dt.date(1998, 2, 26): Decimal("24.00"), dt.date(2025, 12, 4): Decimal("4.00")}
    assert parse_ref_rates(CURRENT) == {dt.date(2026, 3, 5): Decimal("3.75")}


def test_ref_rate_provider_merges_archive_and_current() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ARCHIVE if request.url.path.endswith("archiwum.xml") else CURRENT)

    provider = NbpRefRateProvider(make_client(httpx.MockTransport(handler)), sleep=lambda _: None)

    assert [(point.valid_from, point.rate) for point in provider.ref_rates()] == [
        (dt.date(1998, 2, 26), Decimal("24.00")),
        (dt.date(2025, 12, 4), Decimal("4.00")),
        (dt.date(2026, 3, 5), Decimal("3.75")),
    ]


@pytest.mark.parametrize(
    "content",
    [b"<stopy_procentowe><tabela/></stopy_procentowe>", b"<not-closed", b'<a><pozycja id="ref" oprocentowanie="x" obowiazuje_od="2026-03-05"/></a>'],
    ids=["no-ref-rate", "invalid-xml", "bad-number"],
)
def test_unusable_ref_rate_documents_are_provider_errors(content: bytes) -> None:
    def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=content)

    provider = NbpRefRateProvider(make_client(httpx.MockTransport(handler)), sleep=lambda _: None)

    with pytest.raises(ProviderError):
        provider.ref_rates()
