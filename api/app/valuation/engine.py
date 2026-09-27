"""Valuation engine: pure functions over transactions, splits and preloaded market data (no database, no HTTP).

Quantities are kept in *current units* — the basis of the provider's split-adjusted closes (Yahoo `close`,
verified on NVDA 10:1). A quantity traded on day D becomes `quantity × factor(D)`, where factor(D) multiplies
all splits effective after D; a quantity shown "as of day D" is divided back by factor(D).
"""
import datetime as dt
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.valuation.market_data import MarketData, Series

ZERO = Decimal(0)
ONE = Decimal(1)
CENT = Decimal("0.01")
ONE_DAY = dt.timedelta(days=1)
EXTERNAL_FLOWS = frozenset({"deposit", "withdrawal", "transfer_in", "transfer_out"})

Key = tuple[int, int]  # (account_id, instrument_id)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Entry:
    """One transaction as the engine sees it; `amount` is in the account currency `currency`."""

    id: int
    account_id: int
    instrument_id: int | None
    type: str
    day: dt.date
    amount: Decimal
    currency: str
    quantity: Decimal | None = None
    price: Decimal | None = None
    position_id: str | None = None


@dataclass(frozen=True)
class Split:
    instrument_id: int
    effective_date: dt.date  # first day on the new basis
    ratio_from: Decimal
    ratio_to: Decimal

    @property
    def factor(self) -> Decimal:
        return self.ratio_to / self.ratio_from


@dataclass
class Lot:
    key: str
    position_id: str | None
    opened_on: dt.date
    quantity: Decimal  # current units
    cost_pln: Decimal
    fx_open: Decimal | None  # NBP rate of the quote currency on the purchase day


@dataclass(frozen=True)
class Sale:
    account_id: int
    instrument_id: int
    day: dt.date
    quantity: Decimal  # as traded
    proceeds_pln: Decimal
    cost_pln: Decimal
    position_id: str | None
    matched: bool  # the whole quantity came from the lot named by position_id

    @property
    def realized_pln(self) -> Decimal:
        return self.proceeds_pln - self.cost_pln


class Book:
    """Replays transactions in date order and keeps lots, cash, external flows, income and sales."""

    def __init__(self, splits: Iterable[Split], market: MarketData) -> None:
        self.market = market
        self.splits: dict[int, list[Split]] = defaultdict(list)
        for split in splits:
            self.splits[split.instrument_id].append(split)
        self.lots: dict[Key, dict[str, Lot]] = defaultdict(dict)
        self.cash: dict[int, Decimal] = {}
        self.account_currency: dict[int, str] = {}
        self.flows: dict[tuple[int, dt.date], Decimal] = defaultdict(Decimal)
        self.dividends: dict[Key, Decimal] = defaultdict(Decimal)
        self.withholding: dict[Key, Decimal] = defaultdict(Decimal)
        self.sales: list[Sale] = []
        self.trades: dict[Key, Series] = {}

    def factor(self, instrument_id: int, day: dt.date) -> Decimal:
        """How many current units one unit held on `day` has become."""
        result = ONE
        for split in self.splits.get(instrument_id, ()):
            if split.effective_date > day:
                result *= split.factor
        return result

    def to_pln(self, amount: Decimal, currency: str, day: dt.date) -> Decimal:
        """An account-currency amount in PLN. Without any NBP rate for the currency the amount counts as 0;
        the account's cash rows are flagged `fx_missing` until the worker has fetched the rates."""
        rate = self.market.rate(currency, day)
        return amount * rate if rate is not None else ZERO

    def apply(self, entry: Entry) -> None:
        self.account_currency.setdefault(entry.account_id, entry.currency)
        self.cash[entry.account_id] = self.cash.get(entry.account_id, ZERO) + entry.amount
        if entry.type in EXTERNAL_FLOWS:
            self.flows[(entry.account_id, entry.day)] += self.to_pln(entry.amount, entry.currency, entry.day)
        if entry.instrument_id is None:
            return
        key = (entry.account_id, entry.instrument_id)
        if entry.type == "dividend":
            self.dividends[key] += self.to_pln(entry.amount, entry.currency, entry.day)
        elif entry.type == "withholding_tax":
            self.withholding[key] += self.to_pln(entry.amount, entry.currency, entry.day)
        elif entry.type == "buy" and entry.quantity:
            self._buy(key, entry)
        elif entry.type == "sell" and entry.quantity:
            self._sell(key, entry)

    def _record_trade(self, key: Key, day: dt.date, unit_pln: Decimal) -> None:
        self.trades.setdefault(key, Series()).add(day, unit_pln)

    def _buy(self, key: Key, entry: Entry) -> None:
        assert entry.quantity is not None and entry.instrument_id is not None
        quantity = entry.quantity * self.factor(entry.instrument_id, entry.day)
        cost = -self.to_pln(entry.amount, entry.currency, entry.day)
        lot_key = entry.position_id or f"tx-{entry.id}"
        lots = self.lots[key]
        lot = lots.get(lot_key)
        if lot is None:
            fx_open = self.market.rate(self.market.currencies.get(entry.instrument_id), entry.day)
            lots[lot_key] = Lot(lot_key, entry.position_id, entry.day, quantity, cost, fx_open)
        else:
            lot.quantity += quantity
            lot.cost_pln += cost
        self._record_trade(key, entry.day, cost / quantity)

    def _sell(self, key: Key, entry: Entry) -> None:
        assert entry.quantity is not None and entry.instrument_id is not None
        quantity = entry.quantity * self.factor(entry.instrument_id, entry.day)
        proceeds = self.to_pln(entry.amount, entry.currency, entry.day)
        lots = self.lots[key]
        target = lots.get(entry.position_id) if entry.position_id else None
        matched = target is not None and target.quantity >= quantity
        cost, remaining = ZERO, quantity
        if target is not None:
            taken = min(remaining, target.quantity)
            cost += self._take(lots, target, taken)
            remaining -= taken
        if remaining > 0:
            cost += self._take_pro_rata(lots, remaining)
        self.sales.append(Sale(entry.account_id, entry.instrument_id, entry.day, entry.quantity, proceeds, cost,
                               entry.position_id, matched))
        self._record_trade(key, entry.day, proceeds / quantity)

    @staticmethod
    def _take(lots: dict[str, Lot], lot: Lot, quantity: Decimal) -> Decimal:
        cost = lot.cost_pln * quantity / lot.quantity
        lot.quantity -= quantity
        lot.cost_pln -= cost
        if lot.quantity <= 0:
            del lots[lot.key]
        return cost

    def _take_pro_rata(self, lots: dict[str, Lot], quantity: Decimal) -> Decimal:
        """A sale without (enough of) a matching lot is taken from all open lots in proportion (average cost)."""
        held = sum((lot.quantity for lot in lots.values()), ZERO)
        if held <= 0:
            return ZERO
        share = min(quantity, held) / held
        return sum((self._take(lots, lot, lot.quantity * share) for lot in list(lots.values())), ZERO)
