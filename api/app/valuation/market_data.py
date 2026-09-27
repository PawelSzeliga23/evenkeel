import datetime as dt
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

BASE_CURRENCY = "PLN"


class Series:
    """Values by day; a later point for the same day replaces an earlier one."""

    def __init__(self, points: Iterable[tuple[dt.date, Decimal]] = ()) -> None:
        by_day = dict(points)
        self.days = sorted(by_day)
        self.values = [by_day[day] for day in self.days]

    def add(self, day: dt.date, value: Decimal) -> None:
        """Appends a point; `day` must not be earlier than the last one (a replay only moves forward)."""
        if self.days and self.days[-1] == day:
            self.values[-1] = value
        else:
            self.days.append(day)
            self.values.append(value)

    def on(self, day: dt.date) -> tuple[dt.date, Decimal] | None:
        """The last point on or before `day`."""
        index = bisect_right(self.days, day)
        return (self.days[index - 1], self.values[index - 1]) if index else None

    def near(self, day: dt.date) -> tuple[dt.date, Decimal] | None:
        """The last point on or before `day`, otherwise the first one after it."""
        found = self.on(day)
        if found is None and self.days:
            return self.days[0], self.values[0]
        return found


@dataclass
class MarketData:
    """Everything the engine looks up, preloaded: one query per table instead of one per day."""

    prices: dict[int, Series] = field(default_factory=dict)  # close in the quote currency, split-adjusted
    currencies: dict[int, str | None] = field(default_factory=dict)  # quote currency per instrument
    fx: dict[str, Series] = field(default_factory=dict)  # NBP table A mid: PLN per unit
    # XTB Open Positions value per unit, in the account currency and in units of the snapshot day
    snapshots: dict[tuple[int, int], Series] = field(default_factory=dict)

    def price(self, instrument_id: int, day: dt.date) -> tuple[dt.date, Decimal] | None:
        series = self.prices.get(instrument_id)
        return series.on(day) if series else None

    def rate(self, currency: str | None, day: dt.date) -> Decimal | None:
        """PLN per unit: the last NBP rate on or before `day`, or the first one after it when the stored
        history starts later (the worker fetches from 10 days before the first transaction). PLN is 1."""
        if currency is None:
            return None
        if currency == BASE_CURRENCY:
            return Decimal(1)
        series = self.fx.get(currency)
        found = series.near(day) if series else None
        return found[1] if found else None
