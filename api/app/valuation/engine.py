"""Valuation engine: pure functions over transactions, splits and preloaded market data (no database, no HTTP).

Quantities are kept in *current units* — the basis of the provider's split-adjusted closes (Yahoo `close`,
verified on NVDA 10:1). A quantity traded on day D becomes `quantity × factor(D)`, where factor(D) multiplies
all splits effective after D; a quantity shown "as of day D" is divided back by factor(D).
"""
import datetime as dt
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.valuation.market_data import BASE_CURRENCY, MarketData, Series

ZERO = Decimal(0)
ONE = Decimal(1)
CENT = Decimal("0.01")
ONE_DAY = dt.timedelta(days=1)
EXTERNAL_FLOWS = frozenset({"deposit", "withdrawal", "transfer_in", "transfer_out"})
FLAG_XTB_PRICE = "xtb_price"
FLAG_FX_MISSING = "fx_missing"
SOURCE_PROVIDER = "provider"
SOURCE_XTB = "xtb"
PRICE_PLACES = Decimal("0.0001")
QUANTITY_EPSILON = Decimal("1e-8")  # quantities are stored with 8 decimal places

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


@dataclass(frozen=True)
class Quote:
    unit_pln: Decimal  # value of one current unit in PLN
    price: Decimal | None  # provider close in the quote currency; None when valued from XTB figures
    price_date: dt.date
    rate: Decimal | None
    source: str


@dataclass(frozen=True)
class LotView:
    position_id: str | None
    opened_on: dt.date
    quantity: Decimal  # units of the valuation day
    open_price: Decimal | None  # effective purchase price per unit of the valuation day, quote currency
    cost_pln: Decimal
    value_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal


@dataclass(frozen=True)
class PositionView:
    account_id: int
    instrument_id: int
    day: dt.date
    quantity: Decimal  # units of the valuation day
    cost_pln: Decimal
    value_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    quote: Quote | None
    lots: tuple[LotView, ...]
    flags: tuple[str, ...]


@dataclass(frozen=True)
class Row:
    """One `daily_valuations` row; `instrument_id` None is the account's cash."""

    account_id: int
    instrument_id: int | None
    day: dt.date
    quantity: Decimal | None
    value_pln: Decimal
    cost_pln: Decimal
    net_flow_pln: Decimal
    flags: tuple[str, ...] = ()


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
        """Removes `quantity` from the lot and returns its cost; a remainder below the stored quantity precision
        is Decimal dust of pro-rata division, so the lot is closed and its remaining cost taken too."""
        cost = lot.cost_pln * quantity / lot.quantity
        lot.quantity -= quantity
        lot.cost_pln -= cost
        if lot.quantity < QUANTITY_EPSILON:
            cost += lot.cost_pln
            del lots[lot.key]
        return cost

    def _take_pro_rata(self, lots: dict[str, Lot], quantity: Decimal) -> Decimal:
        """A sale without (enough of) a matching lot is taken from all open lots in proportion (average cost)."""
        held = sum((lot.quantity for lot in lots.values()), ZERO)
        if held <= 0:
            return ZERO
        if quantity >= held:  # everything: whole lots, no inexact share
            return sum((self._take(lots, lot, lot.quantity) for lot in list(lots.values())), ZERO)
        share = quantity / held
        return sum((self._take(lots, lot, lot.quantity * share) for lot in list(lots.values())), ZERO)

    def quote(self, account_id: int, instrument_id: int, day: dt.date) -> Quote | None:
        """Provider close × NBP rate; without either, the newest XTB figure on or before `day`: a trade of this
        account (PLN per unit, costs included) or the Open Positions value per unit of an import."""
        price = self.market.price(instrument_id, day)
        rate = self.market.rate(self.market.currencies.get(instrument_id), day)
        if price is not None and rate is not None:
            return Quote(price[1] * rate, price[1], price[0], rate, SOURCE_PROVIDER)
        key = (account_id, instrument_id)
        candidates: list[tuple[dt.date, Decimal]] = []
        trades = self.trades.get(key)
        trade = trades.on(day) if trades else None
        if trade is not None:
            candidates.append(trade)
        snapshots = self.market.snapshots.get(key)
        snapshot = snapshots.on(day) if snapshots else None
        if snapshot is not None:
            taken_on, unit = snapshot
            currency = self.account_currency.get(account_id, BASE_CURRENCY)
            candidates.append((taken_on, self.to_pln(unit, currency, taken_on) / self.factor(instrument_id, taken_on)))
        if not candidates:
            return None
        found_on, unit = max(candidates, key=lambda candidate: candidate[0])
        return Quote(unit, None, found_on, None, SOURCE_XTB)

    def position(self, account_id: int, instrument_id: int, day: dt.date) -> PositionView | None:
        """Open lots valued on `day`. Price effect + currency effect = value − cost (spec §6), the purchase
        rate being the NBP rate of the purchase day; positions valued from XTB figures have no currency effect."""
        lots = self.lots.get((account_id, instrument_id))
        if not lots:
            return None
        quote = self.quote(account_id, instrument_id, day)
        factor = self.factor(instrument_id, day)
        views: list[LotView] = []
        quantity = value_total = cost_total = price_total = fx_total = ZERO
        for lot in lots.values():
            value = lot.quantity * quote.unit_pln if quote else ZERO
            fx_effect = ZERO
            if quote is not None and quote.source == SOURCE_PROVIDER and lot.fx_open is not None:
                assert quote.price is not None and quote.rate is not None
                fx_effect = lot.quantity * quote.price * (quote.rate - lot.fx_open)
            price_effect = value - lot.cost_pln - fx_effect
            open_price = (
                (lot.cost_pln * factor / (lot.quantity * lot.fx_open)).quantize(PRICE_PLACES) if lot.fx_open else None
            )
            views.append(LotView(lot.position_id, lot.opened_on, lot.quantity / factor, open_price, money(lot.cost_pln),
                                 money(value), money(price_effect), money(fx_effect)))
            quantity += lot.quantity
            value_total += value
            cost_total += lot.cost_pln
            price_total += price_effect
            fx_total += fx_effect
        flags = () if quote is not None and quote.source == SOURCE_PROVIDER else (FLAG_XTB_PRICE,)
        return PositionView(account_id, instrument_id, day, quantity / factor, money(cost_total), money(value_total),
                            money(price_total), money(fx_total), quote, tuple(views), flags)

    def cash_row(self, account_id: int, day: dt.date) -> Row:
        cash = self.cash[account_id]
        rate = self.market.rate(self.account_currency[account_id], day)
        value = money(cash * rate) if rate is not None else ZERO
        flags = () if rate is not None else (FLAG_FX_MISSING,)
        return Row(account_id, None, day, cash, value, value, money(self.flows.get((account_id, day), ZERO)), flags)

    def rows(self, day: dt.date) -> list[Row]:
        result = [self.cash_row(account_id, day) for account_id in sorted(self.cash)]
        for account_id, instrument_id in sorted(self.lots):
            view = self.position(account_id, instrument_id, day)
            if view is not None:
                result.append(Row(account_id, instrument_id, day, view.quantity, view.value_pln, view.cost_pln,
                                  ZERO, view.flags))
        return result

    def day_change(self, account_id: int, instrument_id: int, session: dt.date, previous: dt.date) -> Decimal:
        """Change of the value of the quantity held now between two sessions' quotes."""
        lots = self.lots.get((account_id, instrument_id))
        if not lots:
            return ZERO
        now, before = self.quote(account_id, instrument_id, session), self.quote(account_id, instrument_id, previous)
        if now is None or before is None:
            return ZERO
        quantity = sum((lot.quantity for lot in lots.values()), ZERO)
        return money(quantity * (now.unit_pln - before.unit_pln))


def _ordered(entries: Iterable[Entry]) -> list[Entry]:
    return sorted(entries, key=lambda entry: (entry.day, entry.id))


def replay(entries: Iterable[Entry], splits: Iterable[Split], market: MarketData, until: dt.date) -> Book:
    """The book after every transaction dated `until` or earlier."""
    book = Book(splits, market)
    for entry in _ordered(entries):
        if entry.day > until:
            break
        book.apply(entry)
    return book


def daily_rows(
    entries: Sequence[Entry], splits: Iterable[Split], market: MarketData, end: dt.date, start: dt.date | None = None
) -> list[Row]:
    """Every day from the first transaction (or from `start`, if later) to `end`: a cash row per account and a
    row per open position. Transactions before `start` are still replayed; only their days get no rows."""
    ordered = _ordered(entries)
    if not ordered:
        return []
    book = Book(splits, market)
    rows: list[Row] = []
    index, day = 0, ordered[0].day
    while day <= end:
        while index < len(ordered) and ordered[index].day <= day:
            book.apply(ordered[index])
            index += 1
        if start is None or day >= start:
            rows.extend(book.rows(day))
        day += ONE_DAY
    return rows


def last_session(day: dt.date) -> dt.date:
    """`day`, or the Friday before it when it falls on a weekend (exchange holidays are not known)."""
    while day.weekday() >= 5:
        day -= ONE_DAY
    return day


def previous_session(day: dt.date) -> dt.date:
    return last_session(day - ONE_DAY)
