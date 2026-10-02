"""What-if scenarios (plan 7b, pure functions): the blocks turn the owner's real transactions, or the real
portfolio's deposits, into pretend transactions (`Entry`) and pretend EDO purchases (`Holding`), which the
valuation engine values like the real portfolio.

Pretend ids are negative and grow, so on one day the pretend entries come in creation order and before the real
ones (the engine orders by day, then id); only end-of-day values count.
"""
import datetime as dt
from collections import defaultdict
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.bonds import edo
from app.valuation.engine import ONE, ONE_DAY, ZERO, Book, Entry, Split
from app.valuation.exit_costs import XTB_FX_FEE
from app.valuation.fixed_income import Holding
from app.valuation.market_data import BASE_CURRENCY, MarketData

PORTFOLIO, DEPOSITS = "portfolio", "deposits"
PRETEND_ACCOUNT = 0  # new money of the blocks lands here: PLN, exit costs like XTB
FIRST_ID = -(2**40)
HUNDRED = Decimal(100)
NO_DIVIDENDS = "Dywidendy udawanych instrumentów nie są liczone."


@dataclass(frozen=True)
class Target:
    instrument_id: int | None = None
    bond: str | None = None  # "EDO"


@dataclass(frozen=True)
class Share:
    target: Target
    pct: Decimal


@dataclass(frozen=True)
class Replace:
    from_id: int
    to_id: int


@dataclass(frozen=True)
class Recurring:
    amount: Decimal
    day_of_month: int
    start: dt.date  # first day of the first month
    end: dt.date | None  # first day of the last month; None: to the last valued day
    target: Target
    ike: bool = False


@dataclass(frozen=True)
class Plan:
    base: str
    allocation: tuple[Share, ...] = ()
    steps: tuple[Replace | Recurring, ...] = ()


@dataclass(frozen=True)
class InstrumentInfo:
    ticker: str
    dividends: bool  # a stock or a distributing ETF: the pretend line misses its dividends


@dataclass(frozen=True)
class World:
    """Everything the blocks look up."""

    market: MarketData
    splits: Sequence[Split]
    instruments: Mapping[int, InstrumentInfo]
    edo_series: Mapping[str, edo.Series]
    cpi: Mapping[dt.date, Decimal]
    end: dt.date  # the last valued day


@dataclass(frozen=True)
class Simulated:
    entries: list[Entry]
    holdings: list[Holding]
    notes: list[str]


@dataclass
class _Bond:
    id: int
    purchase_date: dt.date
    quantity: int
    series: edo.Series
    taxed: bool
    redeemed_at: dt.date | None = None


def instrument_targets(plan: Plan) -> set[int]:
    """Instruments the blocks may buy (their prices and actions must be loaded)."""
    targets = [share.target for share in plan.allocation]
    targets += [step.target for step in plan.steps if isinstance(step, Recurring)]
    ids = {target.instrument_id for target in targets if target.instrument_id is not None}
    return ids | {step.to_id for step in plan.steps if isinstance(step, Replace)}


def uses_bonds(plan: Plan) -> bool:
    targets = [share.target for share in plan.allocation]
    targets += [step.target for step in plan.steps if isinstance(step, Recurring)]
    return any(target.bond is not None for target in targets)


def _next_month(month: dt.date) -> dt.date:
    return (month.replace(day=28) + dt.timedelta(days=4)).replace(day=1)


def recurring_days(step: Recurring, end: dt.date) -> list[dt.date]:
    """The first weekday on or after `day_of_month` in every month from `start` to `end` (or to the last valued
    day); exchange holidays are not known, a holiday buys at the last close."""
    last = step.end if step.end is not None and step.end < end else end
    days: list[dt.date] = []
    month = step.start
    while month <= last:
        day = month.replace(day=step.day_of_month)
        while day.weekday() >= 5:
            day += ONE_DAY
        if day > end:
            break
        days.append(day)
        month = _next_month(month)
    return days


class _Simulator:
    def __init__(self, world: World) -> None:
        self.world = world
        self.basis = Book(world.splits, world.market)  # split factors only
        self.entries: list[Entry] = []
        self.bonds: list[_Bond] = []
        self.notes: list[str] = []
        self.units: dict[int, Decimal] = defaultdict(Decimal)  # the pretend account: current units held
        self.cash = ZERO  # the pretend account's cash, PLN
        self._last_id = FIRST_ID

    def note(self, text: str) -> None:
        if text not in self.notes:
            self.notes.append(text)

    def _id(self) -> int:
        self._last_id += 1
        return self._last_id

    def _add(self, account_id: int, instrument_id: int | None, type_: str, day: dt.date, amount: Decimal,
             currency: str, quantity: Decimal | None = None, price: Decimal | None = None) -> None:
        self.entries.append(Entry(self._id(), account_id, instrument_id, type_, day, amount, currency, quantity, price))

    def quote(self, instrument_id: int, day: dt.date) -> tuple[Decimal, Decimal] | None:
        """(close in the quote currency, PLN value of one current unit): the last close on or before `day`."""
        market = self.world.market
        price = market.price(instrument_id, day)
        rate = market.rate(market.currencies.get(instrument_id), day)
        if price is None or rate is None:
            return None
        return price[1], price[1] * rate

    def _fee(self, instrument_id: int, currency: str) -> Decimal:
        quoted = self.world.market.currencies.get(instrument_id)
        return XTB_FX_FEE if quoted is not None and quoted != currency else ZERO

    def _no_close(self, instrument_id: int) -> None:
        ticker = self.world.instruments[instrument_id].ticker
        series = self.world.market.prices.get(instrument_id)
        if series is not None and series.days:
            self.note(f"{ticker} ma notowania od {series.days[0]:%m.%Y}; wcześniejsze kwoty zostały w gotówce.")
        else:
            self.note(f"{ticker} nie ma notowań; kwoty zostały w gotówce.")

    def buy(self, account_id: int, currency: str, instrument_id: int, day: dt.date, amount: Decimal) -> Decimal:
        """Spends `amount` (> 0, account currency) on the instrument at the day's close, the conversion fee
        included; returns the current units bought, 0 when there is no close yet (the money stays in cash)."""
        quote = self.quote(instrument_id, day)
        rate = self.world.market.rate(currency, day)
        if quote is None or not rate:
            self._no_close(instrument_id)
            return ZERO
        close, unit_pln = quote
        units = amount * rate / (unit_pln * (ONE + self._fee(instrument_id, currency)))
        factor = self.basis.factor(instrument_id, day)
        self._add(account_id, instrument_id, "buy", day, -amount, currency, units / factor, close * factor)
        if self.world.instruments[instrument_id].dividends:
            self.note(NO_DIVIDENDS)
        return units

    def buy_bonds(self, day: dt.date, amount: Decimal, taxed: bool) -> Decimal:
        """Whole EDO bonds of the month's issue for `amount`; returns what they cost (0 without the issue)."""
        count = int(amount // edo.NOMINAL)
        if count == 0:
            return ZERO
        terms = self.world.edo_series.get(edo.series_name(day))
        if terms is None:
            self.note(f"Brak parametrów emisji EDO z {day:%m.%Y} — dodaj ją w Dodaj → obligacja.")
            return ZERO
        self.bonds.append(_Bond(self._id(), day, count, terms, taxed))
        return count * edo.NOMINAL

    def invest(self, day: dt.date, parts: Sequence[tuple[Target, Decimal]], taxed: bool = True) -> None:
        """New money on `day`, split into parts: whole EDO bonds (their own deposit, as in `bond_rows`) or an
        instrument bought from a pretend deposit; what cannot be bought stays in cash."""
        cash_in = ZERO
        buys: list[tuple[int, Decimal]] = []
        for target, amount in parts:
            if target.bond is not None:
                cash_in += amount - self.buy_bonds(day, amount, taxed)
            else:
                assert target.instrument_id is not None
                cash_in += amount
                buys.append((target.instrument_id, amount))
        if cash_in:
            self._add(PRETEND_ACCOUNT, None, "deposit", day, cash_in, BASE_CURRENCY)
            self.cash += cash_in
        for instrument_id, amount in buys:
            units = self.buy(PRETEND_ACCOUNT, BASE_CURRENCY, instrument_id, day, amount)
            if units:
                self.units[instrument_id] += units
                self.cash -= amount

    def holdings(self) -> list[Holding]:
        return [Holding(bond.id, PRETEND_ACCOUNT, bond.purchase_date, bond.quantity, bond.redeemed_at, bond.series,
                        bond.taxed) for bond in self.bonds]


def simulate(plan: Plan, world: World, real: Sequence[Entry], flows: Sequence[tuple[dt.date, Decimal]]) -> Simulated:
    """The plan's pretend transactions and bonds. At `portfolio` the real transactions stay (blocks add to them);
    at `deposits` only the real flows are used, each split by the allocation. Events run in date order, the
    real flows of a day before its top-ups."""
    sim = _Simulator(world)
    kept = list(real) if plan.base == PORTFOLIO else []
    events: list[tuple[dt.date, int, Decimal, Recurring | None]] = []
    if plan.base == DEPOSITS:
        events += [(day, 0, amount, None) for day, amount in flows if amount]
    for step in plan.steps:
        if isinstance(step, Recurring):
            events += [(day, 1, step.amount, step) for day in recurring_days(step, world.end)]
    for day, _, amount, step in sorted(events, key=lambda event: (event[0], event[1])):
        if step is not None:
            sim.invest(day, [(step.target, amount)], taxed=not step.ike)
        elif amount > 0:
            sim.invest(day, [(share.target, amount * share.pct / HUNDRED) for share in plan.allocation])
    return Simulated(kept + sim.entries, sim.holdings(), sim.notes)
