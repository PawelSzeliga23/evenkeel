import datetime as dt
import json
import time
from decimal import Decimal
from xml.etree import ElementTree

import httpx

from app.market.http import Sleep, ensure_ok, get_with_retry
from app.market.types import FxPoint, ProviderError, RefRatePoint

RATES_URL = "https://api.nbp.pl/api/exchangerates/rates/a/{code}/{start}/{end}/"
FIRST_DATE = dt.date(2002, 1, 2)  # table A history starts here (api.nbp.pl docs)
MAX_DAYS = 93  # "a single enquiry cannot cover a period longer than 93 days" (api.nbp.pl docs)
REF_RATE_URLS = (
    "https://static.nbp.pl/dane/stopy/stopy_procentowe_archiwum.xml",
    "https://static.nbp.pl/dane/stopy/stopy_procentowe.xml",
)
REF_RATE_ID = "ref"


def date_chunks(start: dt.date, end: dt.date, max_days: int = MAX_DAYS) -> list[tuple[dt.date, dt.date]]:
    chunks = []
    while start <= end:
        chunk_end = min(end, start + dt.timedelta(days=max_days - 1))
        chunks.append((start, chunk_end))
        start = chunk_end + dt.timedelta(days=1)
    return chunks


class NbpFxProvider:
    """NBP table A mid rates (PLN per unit of a foreign currency)."""

    name = "nbp"

    def __init__(self, client: httpx.Client, *, sleep: Sleep = time.sleep) -> None:
        self.client = client
        self.sleep = sleep

    def rates(self, currency: str, start: dt.date, end: dt.date) -> list[FxPoint]:
        points: list[FxPoint] = []
        for chunk_start, chunk_end in date_chunks(max(start, FIRST_DATE), end):
            url = RATES_URL.format(code=currency.lower(), start=chunk_start.isoformat(), end=chunk_end.isoformat())
            response = get_with_retry(self.client, url, params={"format": "json"}, sleep=self.sleep)
            if response.status_code == 404:  # no table published in this range (weekend, holidays)
                continue
            ensure_ok(response)
            try:
                payload = json.loads(response.content, parse_float=Decimal)
                points.extend(
                    FxPoint(dt.date.fromisoformat(rate["effectiveDate"]), Decimal(rate["mid"]))
                    for rate in payload["rates"]
                )
            except (ValueError, KeyError, TypeError, ArithmeticError) as exc:
                raise ProviderError(f"NBP {currency}: unexpected response for {chunk_start}..{chunk_end}") from exc
        return points


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def _percent(text: str | None) -> Decimal:
    return Decimal((text or "").strip().replace(",", "."))


def parse_ref_rates(content: bytes) -> dict[dt.date, Decimal]:
    """Reference rates from NBP XML: archive (`<pozycje obowiazuje_od>`) and current (`<pozycja obowiazuje_od>`)."""
    try:
        root = ElementTree.fromstring(content)
        found: dict[dt.date, Decimal] = {}
        for element in root.iter():
            tag = _local(element.tag)
            if tag == "pozycje":
                for item in element:
                    if _local(item.tag) == "pozycja" and item.get("id") == REF_RATE_ID:
                        found[dt.date.fromisoformat(element.get("obowiazuje_od", ""))] = _percent(item.get("oprocentowanie"))
            elif tag == "pozycja" and element.get("id") == REF_RATE_ID and element.get("obowiazuje_od"):
                found[dt.date.fromisoformat(element.get("obowiazuje_od", ""))] = _percent(element.get("oprocentowanie"))
        return found
    except (ElementTree.ParseError, ValueError, ArithmeticError) as exc:
        raise ProviderError("NBP reference rates: unexpected XML") from exc


class NbpRefRateProvider:
    name = "nbp"

    def __init__(self, client: httpx.Client, *, sleep: Sleep = time.sleep) -> None:
        self.client = client
        self.sleep = sleep

    def ref_rates(self) -> list[RefRatePoint]:
        found: dict[dt.date, Decimal] = {}
        for url in REF_RATE_URLS:
            found.update(parse_ref_rates(ensure_ok(get_with_retry(self.client, url, sleep=self.sleep)).content))
        if not found:
            raise ProviderError("NBP: no reference rate found")
        return [RefRatePoint(day, rate) for day, rate in sorted(found.items())]
