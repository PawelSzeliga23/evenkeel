"""Dashboard (from the cached daily_valuations) and positions (computed live for one day)."""
import datetime as dt
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.market.store import fx_on
from app.models import Account, DailyValuation, Instrument, PositionLot, Transaction, User, XtbSnapshot
from app.portfolio.schemas import (
    AllocationOut, HistoryEventOut, HistoryOut, HistoryPointOut, IncomeOut, LotOut, PositionDetailOut, PositionOut,
    ReconciliationOut, SaleOut, SummaryOut,
)
from app.scoping import UserScope
from app.transactions.schemas import TransactionOut
from app.valuation.engine import ZERO, Book, PositionView, last_session, money, previous_session, replay
from app.valuation.service import Inputs, load_inputs, local_day

HUNDRED = Decimal(100)
PERCENT_PLACES = Decimal("0.01")
QUANTITY_PLACES = Decimal("1e-8")  # quantities are stored with 8 decimal places
DIVIDEND_TYPES = ("dividend", "withholding_tax")
INTEREST_TYPES = ("interest", "interest_tax")
EVENT_TYPES = ("deposit", "withdrawal", "transfer_in", "transfer_out", "buy", "sell", "dividend")
CASH_KIND = "cash"
OTHER_KIND = "other"
KIND_NAMES = {CASH_KIND: "Gotówka", "etf": "ETF", "stock": "Akcje", OTHER_KIND: "Inne"}
CASH_NAME = "Gotówka"


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


def _instrument_item(book: Book, account: Account, instrument: Instrument, view: PositionView | None,
                     day: dt.date) -> PositionOut:
    key = (account.id, instrument.id)
    realized = sum((s.realized_pln for s in book.sales if (s.account_id, s.instrument_id) == key), ZERO)
    dividends = book.dividends.get(key, ZERO) + book.withholding.get(key, ZERO)
    zero = money(ZERO)
    fields = {
        "kind": "instrument", "account_id": account.id, "account_name": account.name, "instrument_id": instrument.id,
        "ticker": instrument.xtb_ticker, "name": instrument.name, "category": instrument.category,
        "currency": instrument.currency, "dividends_net_pln": money(dividends), "realized_pln": money(realized),
    }
    if view is None:  # fully sold: only realized gain and income remain
        return PositionOut(
            **fields, quantity=ZERO, price=None, price_date=None, price_source=None, value_pln=zero, cost_pln=zero,
            unrealized_pln=zero, unrealized_pct=None, price_effect_pln=zero, fx_effect_pln=zero, day_change_pln=zero,
            flags=[],
        )
    quote = view.quote
    unrealized = view.value_pln - view.cost_pln
    session = last_session(day)
    return PositionOut(
        **fields, quantity=view.quantity,
        price=quote.price if quote else None, price_date=quote.price_date if quote else None,
        price_source=quote.source if quote else None,
        value_pln=view.value_pln, cost_pln=view.cost_pln, unrealized_pln=unrealized,
        unrealized_pct=percent(unrealized, view.cost_pln),
        price_effect_pln=view.price_effect_pln, fx_effect_pln=view.fx_effect_pln,
        day_change_pln=book.day_change(account.id, instrument.id, session, previous_session(session)),
        flags=list(view.flags),
    )


def _cash_item(book: Book, account: Account, day: dt.date) -> PositionOut:
    row = book.cash_row(account.id, day)
    zero = money(ZERO)
    return PositionOut(
        kind="cash", account_id=account.id, account_name=account.name, instrument_id=None, ticker=None, name=CASH_NAME,
        category=None, currency=book.account_currency[account.id], quantity=row.quantity or ZERO, price=None,
        price_date=None, price_source=None, value_pln=row.value_pln, cost_pln=row.value_pln, unrealized_pln=zero,
        unrealized_pct=None, price_effect_pln=zero, fx_effect_pln=zero, dividends_net_pln=zero, realized_pln=zero,
        day_change_pln=zero, flags=list(row.flags),
    )


def build_positions(
    scope: UserScope, inputs: Inputs, day: dt.date, account_id: int | None
) -> tuple[Book, list[PositionOut]]:
    """Open positions, then each account's cash, valued on `day`; shares are of the listed total."""
    db = scope.db
    book = replay(inputs.entries, inputs.splits, inputs.market, day)
    accounts = {account.id: account for account in db.scalars(scope.accounts())}
    instruments = {instrument.id: instrument for instrument in db.scalars(scope.instruments())}
    items: list[PositionOut] = []
    for owner, instrument_id in sorted(book.lots):
        if account_id is not None and owner != account_id:
            continue
        view = book.position(owner, instrument_id, day)
        if view is not None:
            items.append(_instrument_item(book, accounts[owner], instruments[instrument_id], view, day))
    for owner in sorted(book.cash):
        if account_id is None or owner == account_id:
            items.append(_cash_item(book, accounts[owner], day))
    total = sum((item.value_pln for item in items), ZERO)
    for item in items:
        item.share_pct = percent(item.value_pln, total)
    return book, items


def list_positions(scope: UserScope, account_id: int | None, day: dt.date) -> list[PositionOut]:
    return build_positions(scope, load_inputs(scope), day, account_id)[1]


def _reconciliation(db: Session, book: Book, inputs: Inputs, account: Account, instrument: Instrument) -> ReconciliationOut:
    """Our quantity on the day of the account's newest XTB import with Open Positions vs XTB's summary row,
    compared at the stored precision (8 decimal places)."""
    # `account` already passed scope.get_account, so its snapshots are the user's own.
    taken_at = db.scalar(select(func.max(XtbSnapshot.taken_at)).where(
        XtbSnapshot.account_id == account.id, XtbSnapshot.row_kind == "instrument_summary"))
    if taken_at is None:
        return ReconciliationOut(status="no_snapshot", taken_at=None, xtb_quantity=None, calculated_quantity=None)
    xtb = db.scalar(select(func.coalesce(func.sum(XtbSnapshot.volume), 0)).where(
        XtbSnapshot.account_id == account.id, XtbSnapshot.instrument_id == instrument.id,
        XtbSnapshot.row_kind == "instrument_summary", XtbSnapshot.taken_at == taken_at,
    ))
    snapshot_day = local_day(taken_at)
    calculated = sum(
        (
            entry.quantity * book.factor(instrument.id, entry.day) / book.factor(instrument.id, snapshot_day)
            * (1 if entry.type == "buy" else -1)
            for entry in inputs.entries
            if entry.account_id == account.id and entry.instrument_id == instrument.id
            and entry.type in ("buy", "sell") and entry.quantity and entry.day <= snapshot_day
        ),
        ZERO,
    )
    matches = (calculated.quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP)
               == Decimal(xtb).quantize(QUANTITY_PLACES, rounding=ROUND_HALF_UP))
    return ReconciliationOut(status="ok" if matches else "mismatch", taken_at=taken_at,
                             xtb_quantity=xtb, calculated_quantity=calculated)


def position_detail(scope: UserScope, account: Account, instrument: Instrument, day: dt.date) -> PositionDetailOut:
    db = scope.db
    inputs = load_inputs(scope)
    book, items = build_positions(scope, inputs, day, None)
    item = next(
        (i for i in items if i.kind == "instrument" and i.account_id == account.id and i.instrument_id == instrument.id),
        None,
    ) or _instrument_item(book, account, instrument, None, day)
    view = book.position(account.id, instrument.id, day)
    stops = {
        lot.xtb_position_id: lot
        for lot in db.scalars(select(PositionLot).where(
            PositionLot.account_id == account.id, PositionLot.instrument_id == instrument.id))
    }
    lots = []
    for lot in view.lots if view else ():
        stored = stops.get(lot.position_id) if lot.position_id else None
        lots.append(LotOut(
            position_id=lot.position_id, opened_on=lot.opened_on, quantity=lot.quantity, open_price=lot.open_price,
            cost_pln=lot.cost_pln, value_pln=lot.value_pln, gain_pln=lot.value_pln - lot.cost_pln,
            price_effect_pln=lot.price_effect_pln, fx_effect_pln=lot.fx_effect_pln,
            holding_days=(day - lot.opened_on).days,
            stop_loss=stored.stop_loss if stored else None, take_profit=stored.take_profit if stored else None,
        ))
    key = (account.id, instrument.id)
    sales = [
        SaleOut(date=s.day, quantity=s.quantity, proceeds_pln=money(s.proceeds_pln), cost_pln=money(s.cost_pln),
                realized_pln=money(s.realized_pln), position_id=s.position_id, matched=s.matched)
        for s in book.sales if (s.account_id, s.instrument_id) == key
    ]
    transactions = list(db.scalars(scope.transactions().where(
        Transaction.account_id == account.id, Transaction.instrument_id == instrument.id)).unique())
    income = [
        IncomeOut(date=local_day(t.occurred_at), type=t.type, amount=t.amount, currency=t.currency,
                  amount_pln=money(amount_pln(db, t)))
        for t in reversed(transactions) if t.type in DIVIDEND_TYPES
    ]
    return PositionDetailOut(
        position=item, lots=lots, sales=sales, income=income,
        transactions=[TransactionOut.model_validate(t) for t in transactions],
        reconciliation=_reconciliation(db, book, inputs, account, instrument),
    )
