import datetime as dt
from decimal import Decimal
from typing import Any

from app.market.providers.yahoo import yahoo_symbol
from app.market.types import (
    CpiPoint,
    FxPoint,
    PriceBar,
    PriceHistory,
    ProviderError,
    RefRatePoint,
    SymbolNotFound,
)
from app.market.update import MarketProviders

SXR8 = PriceHistory(
    "SXR8.DE", "EUR",
    (PriceBar(dt.date(2026, 9, 24), Decimal("711.72")), PriceBar(dt.date(2026, 9, 25), Decimal("713.80"))),
)


class FakePrices:
    name = "fake"
    split_adjusted = True

    def __init__(self, histories: dict[str, PriceHistory] | None = None, errors: dict[str, Exception] | None = None) -> None:
        self.histories = histories or {}
        self.errors = errors or {}
        self.calls: list[tuple[str, dt.date | None]] = []

    def symbol_for(self, xtb_ticker: str) -> str | None:
        return yahoo_symbol(xtb_ticker)

    def history(self, symbol: str, start: dt.date | None) -> PriceHistory:
        self.calls.append((symbol, start))
        if symbol in self.errors:
            raise self.errors[symbol]
        if symbol not in self.histories:
            raise SymbolNotFound(symbol)
        return self.histories[symbol]


class FakeFx:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.calls: list[tuple[str, dt.date, dt.date]] = []

    def rates(self, currency: str, start: dt.date, end: dt.date) -> list[FxPoint]:
        self.calls.append((currency, start, end))
        if self.error:
            raise self.error
        return [FxPoint(start, Decimal("4.2500")), FxPoint(end, Decimal("4.3000"))]


class FakeInflation:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def cpi(self) -> list[CpiPoint]:
        if self.error:
            raise self.error
        return [CpiPoint(dt.date(2026, 7, 1), Decimal("3.0")), CpiPoint(dt.date(2026, 8, 1), Decimal("3.4"))]


class FakeRefRates:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error

    def ref_rates(self) -> list[RefRatePoint]:
        if self.error:
            raise self.error
        return [RefRatePoint(dt.date(2026, 3, 5), Decimal("3.75"))]


def fake_providers(**overrides: Any) -> MarketProviders:
    fields: dict[str, Any] = {
        "prices": FakePrices({"SXR8.DE": SXR8}),
        "fx": FakeFx(),
        "inflation": FakeInflation(),
        "ref_rates": FakeRefRates(),
    }
    return MarketProviders(**{**fields, **overrides})
