"""Walory (plan 7c): each holding's gain over a period, from the cached payout values and the money that went in.

Gain = V(end) − V(base) − net money in + income, where V is the payout value (as XTB would pay out), the base is the
day before the period, and the money is what the transactions cost in PLN (instruments: purchases, sales,
dividends, withholding tax and fees of the instrument) or the rows' own flows (bonds, savings accounts).
"""
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass, field
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import func, select

from app.analytics.metrics import period_start
from app.analytics.schemas import GroupGainOut, HoldingAccountOut, HoldingOut, HoldingsOut, PeriodRangeOut
from app.models import BondHolding, DailyValuation, Instrument, Transaction, User
from app.portfolio.service import PAYOUT, amount_pln
from app.scoping import UserScope
from app.valuation.engine import ONE_DAY, ZERO, last_session, money, previous_session
from app.valuation.actions import resolve
from app.valuation.service import _actions, local_day

HoldingsPeriod = Literal["1d", "1w", "1m", "1y", "ytd", "all"]
TRADES = ("buy", "sell")
INCOME = ("dividend", "withholding_tax", "fee")
KINDS = {"etf": "ETF", "stock": "Akcje", "other": "Inne", "bonds": "Obligacje", "savings": "Oszczędności"}
HUNDRED = Decimal(100)


@dataclass
class _Part:
    """One holding on one account."""

    base: Decimal = ZERO
    end: Decimal = ZERO
    money_in: Decimal = ZERO  # net money put in during the period
    bought: Decimal = ZERO  # money put in only (the gain % base adds it to the base value)
    income: Decimal = ZERO

    @property
    def gain(self) -> Decimal:
        return self.end - self.base - self.money_in + self.income


@dataclass
class _Holding:
    kind: str
    name: str
    ticker: str | None
    category: str
    parts: dict[int, _Part] = field(default_factory=lambda: defaultdict(_Part))


def _pct(gain: Decimal, base: Decimal) -> Decimal | None:
    return (gain * HUNDRED / base).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP) if base > 0 else None


def window(period: HoldingsPeriod, first: dt.date, end: dt.date) -> tuple[dt.date, dt.date]:
    """(base, start): the day whose value the period starts from, and the period's first day."""
    if period == "1d":
        base = previous_session(last_session(end))
    elif period == "1w":
        base = end - dt.timedelta(days=7)
    else:
        base = period_start(period, first, end) - ONE_DAY
    return base, base + ONE_DAY


def _group(name_key: str, parts: list[_Part]) -> GroupGainOut:
    value = sum((p.end for p in parts), ZERO)
    gain = sum((p.gain for p in parts), ZERO)
    base = sum((p.base + p.bought for p in parts), ZERO)
    return GroupGainOut(key=name_key, name=KINDS.get(name_key, name_key), value_pln=money(value),
                        gain_pln=money(gain), gain_pct=_pct(gain, base))


def holdings(scope: UserScope, account_ids: frozenset[int] | None, period: HoldingsPeriod) -> HoldingsOut:
    db = scope.db
    recalculating = db.scalar(select(User.valuations_stale_from).where(User.id == scope.user.id)) is not None
    rows = scope.daily_valuations()
    if account_ids is not None:
        rows = rows.where(DailyValuation.account_id.in_(account_ids))
    first, end = db.execute(rows.with_only_columns(func.min(DailyValuation.date), func.max(DailyValuation.date))).one()
    if end is None:
        return HoldingsOut(period=None, items=[], by_account=[], by_kind=[], recalculating=recalculating)
    if period == "1d":
        end = last_session(end)  # the day's change ends on the last session, as on Pulpit
    base, start = window(period, first, end)

    accounts = {account.id: account.name for account in db.scalars(scope.accounts())}
    found: dict[str, _Holding] = {}
    series = dict(db.execute(scope.bond_holdings().with_only_columns(BondHolding.id, BondHolding.series)).all())

    def holding(row_instrument: int | None, bond: int | None, savings: int | None, account_id: int) -> _Holding:
        if bond is not None:
            key, kind, name, ticker, category = f"b:{series[bond]}", "bond", series[bond], None, "bonds"
        elif savings is not None:
            key, kind, name, ticker, category = f"s:{savings}", "savings", accounts[account_id], None, "savings"
        else:
            key, kind, name, ticker, category = f"i:{row_instrument}", "instrument", "", None, "other"
        return found.setdefault(key, _Holding(kind, name, ticker, category))

    held = rows.where(DailyValuation.instrument_id.is_not(None) | DailyValuation.bond_holding_id.is_not(None)
                      | DailyValuation.savings_account_id.is_not(None))
    for row in db.execute(held.with_only_columns(
        DailyValuation.date, DailyValuation.account_id, DailyValuation.instrument_id, DailyValuation.bond_holding_id,
        DailyValuation.savings_account_id, PAYOUT.label("payout"), DailyValuation.net_flow_pln,
    ).where(DailyValuation.date.between(base, end))):
        part =holding(row.instrument_id, row.bond_holding_id, row.savings_account_id, row.account_id).parts[row.account_id]
        if row.date == base:
            part.base += row.payout
        if row.date == end:
            part.end += row.payout
        if row.instrument_id is None and row.date >= start:
            part.money_in += row.net_flow_pln
            part.bought += max(row.net_flow_pln, ZERO)

    trades = scope.transactions().where(Transaction.instrument_id.is_not(None), Transaction.type.in_(TRADES + INCOME))
    if account_ids is not None:
        trades = trades.where(Transaction.account_id.in_(account_ids))
    for transaction in db.scalars(trades).unique():
        if not start <= local_day(transaction.occurred_at) <= end:
            continue
        amount = amount_pln(db, transaction)
        part = holding(transaction.instrument_id, None, None, transaction.account_id).parts[transaction.account_id]
        if transaction.type in TRADES:
            part.money_in -= amount
            part.bought += max(-amount, ZERO)
        else:
            part.income += amount

    # A conversion moves the holding to another instrument without a transaction: the source's payout value on the
    # day before goes out of the source and into the target, so neither shows it as a gain or a loss.
    traded = {int(key[2:]) for key in found if key.startswith("i:")}
    _, conversions = resolve(_actions(db, scope.user.id, traded))
    for conversion in conversions:
        if not start <= conversion.effective_date <= end:
            continue
        moved = rows.with_only_columns(DailyValuation.account_id, func.sum(PAYOUT)).where(
            DailyValuation.instrument_id == conversion.instrument_id,
            DailyValuation.date == conversion.effective_date - ONE_DAY,
        ).group_by(DailyValuation.account_id)
        for account_id, value in db.execute(moved):
            holding(conversion.instrument_id, None, None, account_id).parts[account_id].money_in -= value
            target = holding(conversion.target_instrument_id, None, None, account_id).parts[account_id]
            target.money_in += value
            target.bought += max(value, ZERO)

    for key in [key for key, item in found.items() if all(
            p.base == p.end == p.money_in == p.income == ZERO for p in item.parts.values())]:
        del found[key]  # nothing held and nothing happened (e.g. a closed savings account)

    instrument_ids = [int(key[2:]) for key in found if key.startswith("i:")]
    for instrument in db.scalars(select(Instrument).where(Instrument.id.in_(instrument_ids))):
        item = found[f"i:{instrument.id}"]
        item.name, item.ticker = instrument.name, instrument.xtb_ticker
        item.category = instrument.category if instrument.category in ("etf", "stock") else "other"

    items = []
    for key, item in found.items():
        parts = list(item.parts.values())
        gain = sum((p.gain for p in parts), ZERO)
        items.append(HoldingOut(
            key=key, kind=item.kind, ticker=item.ticker, name=item.name, category=item.category,
            value_pln=money(sum((p.end for p in parts), ZERO)), gain_pln=money(gain),
            gain_pct=_pct(gain, sum((p.base + p.bought for p in parts), ZERO)),
            accounts=[HoldingAccountOut(account_id=account_id, name=accounts[account_id], value_pln=money(p.end),
                                        gain_pln=money(p.gain)) for account_id, p in sorted(item.parts.items())],
        ))
    items.sort(key=lambda item: (-item.gain_pln, item.name))

    by_account: dict[int, list[_Part]] = defaultdict(list)
    by_kind: dict[str, list[_Part]] = defaultdict(list)
    for item in found.values():
        for account_id, part in item.parts.items():
            by_account[account_id].append(part)
            by_kind[item.category].append(part)
    return HoldingsOut(
        period=PeriodRangeOut(start=start, end=end), items=items,
        by_account=[_group(str(account_id), parts).model_copy(update={"name": accounts[account_id]})
                    for account_id, parts in sorted(by_account.items())],
        by_kind=[_group(kind, by_kind[kind]) for kind in KINDS if kind in by_kind],
        recalculating=recalculating,
    )
