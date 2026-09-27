import datetime as dt
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class ProviderError(Exception):
    """A market data source failed: network, HTTP error or an unexpected response format."""


class SymbolNotFound(ProviderError):
    def __init__(self, symbol: str) -> None:
        super().__init__(f"Unknown symbol: {symbol}")
        self.symbol = symbol


@dataclass(frozen=True)
class PriceBar:
    date: dt.date
    close: Decimal
    adj_close: Decimal | None = None


@dataclass(frozen=True)
class SplitEvent:
    """`ratio_from` old shares became `ratio_to` new ones on `date` (first session on the new basis)."""

    date: dt.date
    ratio_from: Decimal
    ratio_to: Decimal


@dataclass(frozen=True)
class PriceHistory:
    symbol: str
    currency: str
    bars: tuple[PriceBar, ...]
    splits: tuple[SplitEvent, ...] = ()


@dataclass(frozen=True)
class FxPoint:
    date: dt.date
    rate_pln: Decimal


@dataclass(frozen=True)
class CpiPoint:
    year_month: dt.date
    yoy: Decimal


@dataclass(frozen=True)
class RefRatePoint:
    valid_from: dt.date
    rate: Decimal


class PriceProvider(Protocol):
    name: str
    split_adjusted: bool

    def symbol_for(self, xtb_ticker: str) -> str | None: ...

    def history(self, symbol: str, start: dt.date | None) -> PriceHistory:
        """Daily bars from `start` (inclusive) to today; `start=None` means the full history."""
        ...


class FxProvider(Protocol):
    def rates(self, currency: str, start: dt.date, end: dt.date) -> list[FxPoint]: ...


class InflationProvider(Protocol):
    def cpi(self) -> list[CpiPoint]: ...


class RefRateProvider(Protocol):
    def ref_rates(self) -> list[RefRatePoint]: ...
