import datetime as dt
import json
import time
from decimal import Decimal
from typing import Any

import httpx

from app.market.http import Sleep, ensure_ok, get_with_retry
from app.market.types import PriceBar, PriceHistory, ProviderError, SymbolNotFound

CHART_URL = "https://query1.finance.yahoo.com/v8/finance/chart/{symbol}"
# XTB ticker suffix -> Yahoo suffix, verified in the 2026-09-26 spike. Other exchanges: manual override.
SUFFIXES = {"DE": ".DE", "UK": ".L", "FR": ".PA", "PL": ".WA", "US": ""}
PENCE_CURRENCIES = frozenset({"GBp", "GBX"})
PRICE_PLACES = Decimal("0.0001")  # Yahoo sends float32 artefacts (711.719970703125 -> 711.7200)
PAUSE_SECONDS = 0.5
ONE_DAY_SECONDS = 86_400


def yahoo_symbol(xtb_ticker: str) -> str | None:
    base, dot, suffix = xtb_ticker.strip().rpartition(".")
    target = SUFFIXES.get(suffix.upper()) if dot and base else None
    if target is None:
        return None
    if suffix.upper() == "US":
        base = base.replace(".", "-")  # BRK.B.US -> BRK-B
    return base + target


def _price(value: Any, divisor: int) -> Decimal:
    return Decimal(value).quantize(PRICE_PLACES) / divisor


def parse_chart(symbol: str, content: bytes) -> PriceHistory:
    try:
        payload = json.loads(content, parse_float=Decimal)
    except ValueError as exc:
        raise ProviderError(f"Yahoo {symbol}: response is not JSON") from exc
    chart = payload.get("chart") if isinstance(payload, dict) else None
    results = (chart or {}).get("result") or []
    if not results:
        raise SymbolNotFound(symbol)
    result = results[0]
    meta = result.get("meta") or {}
    raw_currency = meta.get("currency")
    if not raw_currency:
        raise ProviderError(f"Yahoo {symbol}: no currency in response")
    pence = raw_currency in PENCE_CURRENCIES
    currency = "GBP" if pence else str(raw_currency).upper()
    divisor = 100 if pence else 1
    offset = int(meta.get("gmtoffset") or 0)
    indicators = result.get("indicators") or {}
    closes = ((indicators.get("quote") or [{}])[0]).get("close") or []
    adjusted = ((indicators.get("adjclose") or [{}])[0]).get("adjclose") or []
    bars: dict[dt.date, PriceBar] = {}
    for index, timestamp in enumerate(result.get("timestamp") or []):
        close = closes[index] if index < len(closes) else None
        if close is None:
            continue
        adj = adjusted[index] if index < len(adjusted) else None
        day = dt.datetime.fromtimestamp(int(timestamp) + offset, dt.UTC).date()
        bars[day] = PriceBar(day, _price(close, divisor), None if adj is None else _price(adj, divisor))
    return PriceHistory(symbol=symbol, currency=currency, bars=tuple(bars[day] for day in sorted(bars)))


class YahooPriceProvider:
    """Daily closes from Yahoo's unofficial chart API.

    `close` is split-adjusted (verified on NVDA 10:1, June 2024) but not dividend-adjusted;
    `adj_close` is adjusted for both.
    """

    name = "yahoo"
    split_adjusted = True

    def __init__(self, client: httpx.Client, *, sleep: Sleep = time.sleep, pause: float = PAUSE_SECONDS) -> None:
        self.client = client
        self.sleep = sleep
        self.pause = pause

    def symbol_for(self, xtb_ticker: str) -> str | None:
        return yahoo_symbol(xtb_ticker)

    def history(self, symbol: str, start: dt.date | None) -> PriceHistory:
        period1 = 0 if start is None else int(dt.datetime.combine(start, dt.time(), dt.UTC).timestamp())
        params = {"period1": period1, "period2": int(time.time()) + ONE_DAY_SECONDS, "interval": "1d"}
        response = get_with_retry(self.client, CHART_URL.format(symbol=symbol), params=params, sleep=self.sleep)
        self.sleep(self.pause)
        if response.status_code == 404:
            raise SymbolNotFound(symbol)
        ensure_ok(response)
        return parse_chart(symbol, response.content)
