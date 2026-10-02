"""Dochód i koszty (plan 7d): passive income against costs, month by month.

Income (gross): interest accrued on savings accounts and bonds (the day's change of the cached value less its flows;
the value is after the 19 % tax on regular accounts, so gross = net ÷ 0.81), XTB free-funds interest and dividends.
Costs: XTB's 0.5 % currency conversion inside purchases and sales, taxes (interest, withholding) and fees.
"""
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import func, or_, select

from app.analytics.schemas import (IncomeCostOut, IncomeMonthOut, IncomeOut, IncomeSourceOut, IncomeTotalsOut,
                                   PeriodRangeOut)
from app.models import BondHolding, DailyValuation, Instrument, Transaction, User
from app.portfolio.service import amount_pln
from app.scoping import UserScope
from app.valuation.engine import ONE_DAY, ZERO, money
from app.valuation.exit_costs import XTB_FX_FEE
from app.valuation.service import local_day, local_today

IncomePeriod = Literal["12m", "ytd", "all"]
CENT = Decimal("0.01")
NET_SHARE = Decimal("0.81")  # interest left after the 19 % tax
XTB = "xtb"
TYPES = ("buy", "sell", "dividend", "withholding_tax", "interest", "interest_tax", "fee")
COSTS = {"fx": "Przewalutowanie XTB", "interest_tax": "Podatek od odsetek", "withholding_tax": "Podatek u źródła",
         "fees": "Prowizje i opłaty"}


def fx_cost(amount: Decimal, fee: Decimal) -> Decimal:
    """XTB's fee inside a trade's PLN amount: a purchase pays converted × (1 + fee), a sale gets converted × (1 − fee)."""
    if not fee or not amount:
        return ZERO
    base = 1 + fee if amount < 0 else 1 - fee
    return (abs(amount) * fee / base).quantize(CENT, rounding=ROUND_HALF_UP)


def _month(day: dt.date) -> str:
    return f"{day.year}-{day.month:02d}"


def _months(start: dt.date, end: dt.date) -> list[str]:
    months, year, month = [], start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def window(period: IncomePeriod, first: dt.date, today: dt.date) -> dt.date:
    """The period's first day, never before the month of the first data."""
    if period == "12m":
        months_back = today.year * 12 + today.month - 1 - 11
        start = dt.date(months_back // 12, months_back % 12 + 1, 1)
    elif period == "ytd":
        start = dt.date(today.year, 1, 1)
    else:
        start = first
    return max(start, first.replace(day=1)) if period != "all" else first.replace(day=1)


@dataclass
class _Month:
    interest: Decimal = ZERO
    dividends: Decimal = ZERO
    fx: Decimal = ZERO
    taxes: Decimal = ZERO
    fees: Decimal = ZERO


@dataclass
class _Source:
    kind: str
    name: str
    taxed: bool
    gross: Decimal = ZERO
    tax: Decimal = ZERO


def _totals(income: Decimal, costs: Decimal) -> dict[str, Decimal]:
    return {"income_pln": money(income), "costs_pln": money(costs), "balance_pln": money(income - costs)}


def income(scope: UserScope, account_ids: frozenset[int] | None, period: IncomePeriod) -> IncomeOut:
    db = scope.db
    today = local_today()
    recalculating = db.scalar(select(User.valuations_stale_from).where(User.id == scope.user.id)) is not None
    accounts = {account.id: account for account in db.scalars(scope.accounts())}
    wanted = (lambda column: column.in_(account_ids)) if account_ids is not None else (lambda column: True)

    fixed = scope.daily_valuations().where(
        or_(DailyValuation.bond_holding_id.is_not(None), DailyValuation.savings_account_id.is_not(None)),
        wanted(DailyValuation.account_id))
    trades = scope.transactions().where(Transaction.type.in_(TYPES), wanted(Transaction.account_id))
    transactions = list(db.scalars(trades).unique())
    days = [local_day(t.occurred_at) for t in transactions]
    first_valued = db.scalar(fixed.with_only_columns(func.min(DailyValuation.date)))
    firsts = days + ([first_valued] if first_valued else [])
    if not firsts:
        return IncomeOut(period=None, totals=IncomeTotalsOut(**_totals(ZERO, ZERO)), months=[], sources=[], costs=[],
                         recalculating=recalculating)
    start = window(period, min(firsts), today)
    months: dict[str, _Month] = {month: _Month() for month in _months(start, today)}
    sources: dict[str, _Source] = {}
    costs = {key: [ZERO, 0] for key in COSTS}

    def source(key: str, kind: str, name: str, taxed: bool) -> _Source:
        return sources.setdefault(key, _Source(kind, name, taxed))

    series = dict(db.execute(scope.bond_holdings().with_only_columns(BondHolding.id, BondHolding.series)).all())
    previous: dict[tuple[int | None, int | None], tuple[dt.date, Decimal]] = {}
    for row in db.execute(fixed.with_only_columns(
        DailyValuation.date, DailyValuation.account_id, DailyValuation.bond_holding_id,
        DailyValuation.savings_account_id, DailyValuation.value_pln, DailyValuation.net_flow_pln,
    ).where(DailyValuation.date.between(start - ONE_DAY, today)).order_by(
        DailyValuation.bond_holding_id, DailyValuation.savings_account_id, DailyValuation.date,
    )):
        component = (row.bond_holding_id, row.savings_account_id)
        last = previous.get(component)
        previous[component] = (row.date, row.value_pln)
        if row.date < start:
            continue
        before = last[1] if last is not None and last[0] == row.date - ONE_DAY else ZERO
        net = row.value_pln - before - row.net_flow_pln
        if not net:
            continue
        taxed = accounts[row.account_id].wrapper == "regular"
        gross = net / NET_SHARE if taxed else net
        month = months[_month(row.date)]
        month.interest += gross
        month.taxes += gross - net
        costs["interest_tax"][0] += gross - net
        if row.bond_holding_id is not None:
            # per account: one series on IKE and on a regular account is taxed differently
            name = f"{series[row.bond_holding_id]} · {accounts[row.account_id].name}"
            item = source(f"b:{series[row.bond_holding_id]}:{row.account_id}", "bond", name, taxed)
        else:
            item = source(f"s:{row.savings_account_id}", "savings", accounts[row.account_id].name, taxed)
        item.gross += gross
        item.tax += gross - net

    instruments = {i.id: i for i in db.scalars(select(Instrument).where(
        Instrument.id.in_({t.instrument_id for t in transactions if t.instrument_id is not None})))}
    for transaction, day in zip(transactions, days):
        if not start <= day <= today:
            continue
        month = months[_month(day)]
        account = accounts[transaction.account_id]
        amount = amount_pln(db, transaction)
        kind = transaction.type
        if kind in ("buy", "sell"):
            instrument = instruments.get(transaction.instrument_id)
            # XTB converts only when the quote currency differs from the account's (a EUR account buying a EUR ETF pays none)
            quote = instrument.currency if instrument and instrument.currency else transaction.currency
            cost = fx_cost(amount, XTB_FX_FEE if account.broker == XTB and quote != account.currency else ZERO)
            if cost:
                month.fx += cost
                costs["fx"][0] += cost
                costs["fx"][1] += 1
        elif kind in ("dividend", "withholding_tax"):
            instrument = instruments.get(transaction.instrument_id)
            name = f"{instrument.xtb_ticker} {instrument.name}" if instrument else "Dywidendy"
            item = source(f"d:{transaction.instrument_id}", "dividend", name, True)
            if kind == "dividend":
                month.dividends += amount
                item.gross += amount
            else:
                month.taxes -= amount
                item.tax -= amount
                costs["withholding_tax"][0] -= amount
                costs["withholding_tax"][1] += 1
        elif kind in ("interest", "interest_tax"):
            label = "Odsetki od wolnych środków" if account.broker == XTB else "Odsetki"
            item = source(f"x:{account.id}", "xtb_interest", f"{label} · {account.name}",
                          account.wrapper == "regular")
            if kind == "interest":
                month.interest += amount
                item.gross += amount
            else:
                month.taxes -= amount
                item.tax -= amount
                costs["interest_tax"][0] -= amount
                costs["interest_tax"][1] += 1
        else:  # fee
            month.fees -= amount
            costs["fees"][0] -= amount
            costs["fees"][1] += 1

    out_months = []
    for key, m in months.items():
        earned, spent = m.interest + m.dividends, m.fx + m.taxes + m.fees
        out_months.append(IncomeMonthOut(
            month=key, interest_pln=money(m.interest), dividends_pln=money(m.dividends), fx_pln=money(m.fx),
            taxes_pln=money(m.taxes), fees_pln=money(m.fees), **_totals(earned, spent)))
    earned = sum((m.interest + m.dividends for m in months.values()), ZERO)
    spent = sum((m.fx + m.taxes + m.fees for m in months.values()), ZERO)
    shown = sorted((s for s in sources.items() if s[1].gross or s[1].tax), key=lambda s: (-s[1].gross, s[1].name))
    return IncomeOut(
        period=PeriodRangeOut(start=start, end=today), totals=IncomeTotalsOut(**_totals(earned, spent)),
        months=out_months,
        sources=[IncomeSourceOut(key=key, kind=s.kind, name=s.name, gross_pln=money(s.gross), tax_pln=money(s.tax),
                                 net_pln=money(s.gross - s.tax), taxed=s.taxed) for key, s in shown],
        costs=[IncomeCostOut(key=key, name=COSTS[key], amount_pln=money(amount), count=count)
               for key, (amount, count) in costs.items()],
        recalculating=recalculating,
    )
