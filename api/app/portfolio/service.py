"""Dashboard (from the cached daily_valuations) and positions (computed live for one day)."""
import datetime as dt
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.market.store import fx_on
from app.models import DailyValuation, Instrument, Transaction, User
from app.portfolio.schemas import AllocationOut, HistoryEventOut, HistoryOut, HistoryPointOut, SummaryOut
from app.scoping import UserScope
from app.valuation.engine import ZERO, last_session, money, previous_session
from app.valuation.service import local_day

HUNDRED = Decimal(100)
PERCENT_PLACES = Decimal("0.01")
DIVIDEND_TYPES = ("dividend", "withholding_tax")
INTEREST_TYPES = ("interest", "interest_tax")
EVENT_TYPES = ("deposit", "withdrawal", "transfer_in", "transfer_out", "buy", "sell", "dividend")
CASH_KIND = "cash"
OTHER_KIND = "other"
KIND_NAMES = {CASH_KIND: "Gotówka", "etf": "ETF", "stock": "Akcje", OTHER_KIND: "Inne"}


def percent(part: Decimal, whole: Decimal) -> Decimal | None:
    return (part * HUNDRED / whole).quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP) if whole else None


def amount_pln(db: Session, transaction: Transaction) -> Decimal:
    """The amount in PLN at the NBP rate of its day (0 while that rate is still missing)."""
    rate = fx_on(db, transaction.currency, local_day(transaction.occurred_at))
    return transaction.amount * rate if rate is not None else ZERO


def _transactions(scope: UserScope, account_id: int | None, types: tuple[str, ...]) -> list[Transaction]:
    query = scope.transactions().where(Transaction.type.in_(types))
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    return list(scope.db.scalars(query).unique())


def _valuations(scope: UserScope, account_id: int | None) -> Select[tuple[DailyValuation]]:
    query = scope.daily_valuations()
    return query if account_id is None else query.where(DailyValuation.account_id == account_id)


def _flow_sum() -> object:
    return func.coalesce(func.sum(DailyValuation.net_flow_pln), 0)


def _allocation(groups: dict[str, tuple[str, Decimal]], total: Decimal) -> list[AllocationOut]:
    items = [
        AllocationOut(key=key, name=name, value_pln=money(value), share_pct=percent(value, total))
        for key, (name, value) in groups.items()
    ]
    return sorted(items, key=lambda item: (-item.value_pln, item.key))


def portfolio_summary(scope: UserScope, account_id: int | None) -> SummaryOut:
    db = scope.db
    rows = _valuations(scope, account_id)
    income = _transactions(scope, account_id, DIVIDEND_TYPES + INTEREST_TYPES)
    dividends = sum((amount_pln(db, t) for t in income if t.type in DIVIDEND_TYPES), ZERO)
    interest = sum((amount_pln(db, t) for t in income if t.type in INTEREST_TYPES), ZERO)
    recalculating = db.scalar(select(User.valuations_stale_from).where(User.id == scope.user.id)) is not None
    latest = db.scalar(rows.with_only_columns(func.max(DailyValuation.date)))
    if latest is None:
        return SummaryOut(
            as_of=None, value_pln=money(ZERO), cash_pln=money(ZERO), invested_pln=money(ZERO),
            total_gain_pln=money(ZERO), total_gain_pct=None, day_change_pln=None, day_change_pct=None,
            dividends_net_pln=money(dividends), interest_net_pln=money(interest), by_account=[], by_kind=[],
            approximate_positions=0, recalculating=recalculating,
        )
    session = last_session(latest)
    previous = previous_session(session)
    totals: dict[dt.date, Decimal] = dict(db.execute(
        rows.with_only_columns(DailyValuation.date, func.sum(DailyValuation.value_pln))
        .where(DailyValuation.date.in_([latest, session, previous]))
        .group_by(DailyValuation.date)
    ).all())
    value = totals[latest]
    invested = db.scalar(rows.with_only_columns(_flow_sum()).where(DailyValuation.date <= latest))
    day_change = day_change_pct = None
    if session in totals and previous in totals:
        flows = db.scalar(rows.with_only_columns(_flow_sum()).where(
            DailyValuation.date > previous, DailyValuation.date <= session))
        day_change = money(totals[session] - totals[previous] - flows)
        day_change_pct = percent(day_change, totals[previous])
    names = {account.id: account.name for account in db.scalars(scope.accounts())}
    latest_rows = db.execute(
        rows.with_only_columns(DailyValuation.account_id, DailyValuation.instrument_id, DailyValuation.value_pln,
                               DailyValuation.flags)
        .where(DailyValuation.date == latest)
    ).all()
    instrument_ids = {row.instrument_id for row in latest_rows if row.instrument_id is not None}
    categories = dict(db.execute(
        select(Instrument.id, Instrument.category).where(Instrument.id.in_(instrument_ids))
    ).all()) if instrument_ids else {}
    by_account: dict[str, tuple[str, Decimal]] = {}
    by_kind: dict[str, tuple[str, Decimal]] = {}
    cash, approximate = ZERO, 0
    for row in latest_rows:
        account_key = str(row.account_id)
        by_account[account_key] = (names[row.account_id], by_account.get(account_key, ("", ZERO))[1] + row.value_pln)
        kind = CASH_KIND if row.instrument_id is None else (categories.get(row.instrument_id) or OTHER_KIND)
        by_kind[kind] = (KIND_NAMES.get(kind, kind), by_kind.get(kind, ("", ZERO))[1] + row.value_pln)
        if row.instrument_id is None:
            cash += row.value_pln
        elif row.flags:
            approximate += 1
    gain = value - invested
    return SummaryOut(
        as_of=latest, value_pln=money(value), cash_pln=money(cash), invested_pln=money(invested),
        total_gain_pln=money(gain), total_gain_pct=percent(gain, invested) if invested > 0 else None,
        day_change_pln=day_change, day_change_pct=day_change_pct,
        dividends_net_pln=money(dividends), interest_net_pln=money(interest),
        by_account=_allocation(by_account, value), by_kind=_allocation(by_kind, value),
        approximate_positions=approximate, recalculating=recalculating,
    )


def portfolio_history(
    scope: UserScope, account_id: int | None, start: dt.date | None, end: dt.date | None
) -> HistoryOut:
    """Daily value with invested capital (cumulative external flows from the very first day) and operations."""
    db = scope.db

    def inside(day: dt.date) -> bool:
        return (start is None or day >= start) and (end is None or day <= end)

    grouped = db.execute(
        _valuations(scope, account_id)
        .with_only_columns(DailyValuation.date, func.sum(DailyValuation.value_pln), func.sum(DailyValuation.net_flow_pln))
        .group_by(DailyValuation.date)
        .order_by(DailyValuation.date)
    ).all()
    invested = ZERO
    points = []
    for day, value, flow in grouped:
        invested += flow
        if inside(day):
            points.append(HistoryPointOut(date=day, value_pln=money(value), invested_pln=money(invested),
                                          net_flow_pln=money(flow)))
    buckets: dict[tuple[dt.date, str], Decimal] = defaultdict(Decimal)
    for transaction in _transactions(scope, account_id, EVENT_TYPES):
        day = local_day(transaction.occurred_at)
        if inside(day):
            buckets[(day, transaction.type)] += amount_pln(db, transaction)
    events = [HistoryEventOut(date=day, type=type_, amount_pln=money(amount))
              for (day, type_), amount in sorted(buckets.items())]
    return HistoryOut(points=points, events=events)
