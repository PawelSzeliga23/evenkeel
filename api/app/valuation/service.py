"""Loads a user's data for the valuation engine and maintains the `daily_valuations` cache.

A recompute is requested with `mark_stale` (the earliest requested day wins) and done by `recompute_user`.
Both take the user's advisory lock, so a marking transaction (an import) waits for a running recompute,
and the next recompute sees the committed data.
"""
import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, insert, or_, select, text, update
from sqlalchemy.dialects.postgresql import distinct_on
from sqlalchemy.orm import Session

from app.bonds.edo import Series as BondTerms
from app.models import (
    Account, BondHolding, BondSeries, CorporateAction, Cpi, DailyValuation, FxRate, Instrument, Price, SavingsAccount,
    SavingsBalance, SavingsFlow, SavingsRate, Transaction, User, XtbSnapshot,
)
from app.scoping import UserScope
from app.valuation.actions import Action, action_of, resolve
from app.valuation.engine import Conversion, Entry, Split, daily_rows
from app.valuation.exit_costs import ExitRules
from app.valuation.fixed_income import FLAG_RATE_ESTIMATED, Holding, SavingsInput, bond_rows, savings_rows
from app.valuation.market_data import BASE_CURRENCY, MarketData, Series

logger = logging.getLogger(__name__)

ZONE = ZoneInfo("Europe/Warsaw")  # valuation days are Warsaw calendar days, like the worker's schedule
LOCK_NAMESPACE = 4  # high 32 bits of the advisory lock key "valuations of user N"
INSERT_CHUNK = 1000
XTB_BROKER = "xtb"  # accounts of this broker pay the currency conversion fee on a sale


def local_day(moment: dt.datetime) -> dt.date:
    return moment.astimezone(ZONE).date()


def local_today(now: dt.datetime | None = None) -> dt.date:
    return local_day(now or dt.datetime.now(dt.UTC))


@dataclass(frozen=True)
class Inputs:
    entries: list[Entry]
    splits: list[Split]
    market: MarketData
    conversions: list[Conversion] = field(default_factory=list)
    exit_rules: ExitRules = field(default_factory=ExitRules)


def _series(points: dict[object, list[tuple[dt.date, object]]]) -> dict:
    return {key: Series(values) for key, values in points.items()}


def _series_from(db: Session, key: Any, day: Any, value: Any, keys: Iterable[object], first_day: dt.date) -> dict:
    """Points of `keys` from `first_day` on, plus the last one before it per key, so a "last known on or before"
    lookup still answers on the first day without loading decades of history."""
    points: dict[object, list] = defaultdict(list)
    before = (
        select(key, day, value).where(key.in_(keys), day < first_day).ext(distinct_on(key)).order_by(key, day.desc())
    )
    since = select(key, day, value).where(key.in_(keys), day >= first_day)
    for query in (before, since):
        for found_key, found_day, found_value in db.execute(query):
            points[found_key].append((found_day, found_value))
    return _series(points)


def _actions(db: Session, user_id: int, instrument_ids: set[int]) -> list[Action]:
    """Shared corporate actions and the user's own manual ones for the instruments, following conversion targets
    (a converted holding needs the target's actions too)."""
    found: dict[int, Action] = {}
    seen: set[int] = set()
    pending = set(instrument_ids)
    while pending:
        seen |= pending
        rows = db.scalars(select(CorporateAction).where(
            CorporateAction.instrument_id.in_(pending),
            or_(CorporateAction.user_id.is_(None), CorporateAction.user_id == user_id),
        )).all()
        pending = set()
        for row in rows:
            found[row.id] = action_of(row)
            if row.target_instrument_id is not None and row.target_instrument_id not in seen:
                pending.add(row.target_instrument_id)
    return list(found.values())


def load_inputs(scope: UserScope) -> Inputs:
    """The user's transactions and the market data the engine may look up for them (from the first transaction)."""
    db = scope.db
    entries = [
        Entry(t.id, t.account_id, t.instrument_id, t.type, local_day(t.occurred_at), t.amount, t.currency,
              t.quantity, t.price, t.xtb_position_id)
        for t in db.scalars(scope.transactions()).unique()
    ]
    if not entries:
        return Inputs(entries, [], MarketData())
    first_day = min(entry.day for entry in entries)
    traded = {entry.instrument_id for entry in entries if entry.instrument_id is not None}
    splits, conversions = resolve(_actions(db, scope.user.id, traded))
    instrument_ids = sorted(traded | {conversion.target_instrument_id for conversion in conversions})
    market = MarketData()
    if instrument_ids:
        market.prices = _series_from(db, Price.instrument_id, Price.date, Price.close, instrument_ids, first_day)
        market.currencies = dict(
            db.execute(select(Instrument.id, Instrument.currency).where(Instrument.id.in_(instrument_ids))).all()
        )
        snapshots: dict[object, list] = defaultdict(list)
        for snapshot in db.scalars(
            scope.snapshots()
            .where(
                XtbSnapshot.row_kind == "instrument_summary",
                XtbSnapshot.instrument_id.is_not(None),
                XtbSnapshot.value.is_not(None),
                XtbSnapshot.volume > 0,
            )
            .order_by(XtbSnapshot.taken_at, XtbSnapshot.id)
        ):
            key = (snapshot.account_id, snapshot.instrument_id)
            snapshots[key].append((local_day(snapshot.taken_at), snapshot.value / snapshot.volume))
        market.snapshots = _series(snapshots)
    currencies = ({c for c in market.currencies.values() if c} | {entry.currency for entry in entries}) - {BASE_CURRENCY}
    if currencies:
        market.fx = _series_from(db, FxRate.currency, FxRate.date, FxRate.rate_pln, sorted(currencies), first_day)
    fee_accounts = frozenset(account.id for account in db.scalars(scope.accounts()) if account.broker == XTB_BROKER)
    spreads = dict(db.execute(
        select(Instrument.id, Instrument.spread_pct)
        .where(Instrument.id.in_(instrument_ids), Instrument.spread_pct.is_not(None))
    ).all()) if instrument_ids else {}
    return Inputs(entries, splits, market, conversions, ExitRules(fee_accounts, spreads))


@dataclass(frozen=True)
class FixedIncome:
    holdings: list[Holding]
    savings: list[SavingsInput]
    cpi: dict[dt.date, Decimal]


def load_fixed_income(scope: UserScope) -> FixedIncome:
    """The user's bond purchases (with their series) and savings accounts (with balances and rates); CPI when
    there are bonds. Accounts marked IKE / IKZE pay no tax."""
    db = scope.db
    taxed = {account.id: account.wrapper == "regular" for account in db.scalars(scope.accounts())}
    holdings = [
        Holding(holding.id, holding.account_id, holding.purchase_date, holding.quantity, holding.redeemed_at,
                BondTerms(series.first_period_rate, series.margin, series.early_redemption_fee),
                taxed[holding.account_id])
        for holding, series in db.execute(
            scope.bond_holdings().add_columns(BondSeries).join(BondSeries, BondSeries.series == BondHolding.series)
        )
    ]
    savings = []
    for account in db.scalars(scope.savings_accounts()):
        balances = db.execute(select(SavingsBalance.as_of_date, SavingsBalance.balance)
                              .where(SavingsBalance.savings_account_id == account.id)
                              .order_by(SavingsBalance.as_of_date)).all()
        rates = db.execute(select(SavingsRate.valid_from, SavingsRate.annual_rate)
                           .where(SavingsRate.savings_account_id == account.id)
                           .order_by(SavingsRate.valid_from)).all()
        flows = db.execute(select(SavingsFlow.date, SavingsFlow.amount)
                           .where(SavingsFlow.savings_account_id == account.id)
                           .order_by(SavingsFlow.date, SavingsFlow.id)).all()
        savings.append(SavingsInput(account.id, account.account_id, account.capitalization, taxed[account.account_id],
                                    [tuple(b) for b in balances], [tuple(r) for r in rates],
                                    [tuple(f) for f in flows]))
    cpi = dict(db.execute(select(Cpi.year_month, Cpi.yoy)).all()) if holdings else {}
    return FixedIncome(holdings, savings, cpi)


def lock_user(db: Session, user_id: int) -> None:
    """Transaction-scoped: released on commit or rollback."""
    db.execute(text("SELECT pg_advisory_xact_lock(CAST(:key AS bigint))"), {"key": (LOCK_NAMESPACE << 32) | user_id})


def _mark_stale_days(db: Session, days: dict[int, dt.date]) -> None:
    """Locks every affected user exactly once, in ascending id order (so two markers never wait for each
    other in a cycle), then sets each `valuations_stale_from` to the earliest of the existing and
    requested day. Does not commit."""
    ids = sorted(days)
    if not ids:
        return
    for user_id in ids:
        lock_user(db, user_id)
    by_day: dict[dt.date, list[int]] = defaultdict(list)
    for user_id in ids:
        by_day[days[user_id]].append(user_id)
    for day, group in by_day.items():
        earliest = func.least(func.coalesce(User.valuations_stale_from, day), day)
        db.execute(
            update(User).where(User.id.in_(group)).values(valuations_stale_from=earliest)
            .execution_options(synchronize_session=False)
        )


def mark_stale(db: Session, user_ids: Iterable[int], from_day: dt.date) -> None:
    """Requests a recompute of the users' valuations from `from_day`; an earlier pending day wins. Does not commit."""
    _mark_stale_days(db, {user_id: from_day for user_id in user_ids})


def holders(db: Session, instrument_ids: Iterable[int]) -> list[int]:
    """Users with any transaction in one of the instruments, or whose own conversion leads into one of them."""
    ids = list(instrument_ids)
    if not ids:
        return []
    traded = db.scalars(
        select(Account.user_id).join(Transaction, Transaction.account_id == Account.id)
        .where(Transaction.instrument_id.in_(ids)).distinct()
    )
    converted = db.scalars(
        select(CorporateAction.user_id).where(
            CorporateAction.target_instrument_id.in_(ids), CorporateAction.user_id.is_not(None)
        ).distinct()
    )
    return sorted(set(traded) | set(converted))


def users_with_transactions(db: Session) -> list[int]:
    return list(db.scalars(
        select(Account.user_id).join(Transaction, Transaction.account_id == Account.id)
        .distinct().order_by(Account.user_id)
    ))


def mark_market_changes(db: Session, prices_from: dict[int, dt.date], fx_from: dict[str, dt.date]) -> None:
    """New prices or splits concern the instrument's holders; new NBP rates concern everyone with transactions
    (cash in a foreign currency too). Every affected user is locked exactly once, in ascending id order,
    regardless of how many instruments or currencies changed. Does not commit."""
    days: dict[int, dt.date] = {}
    for instrument_id, day in prices_from.items():
        for user_id in holders(db, [instrument_id]):
            if user_id not in days or day < days[user_id]:
                days[user_id] = day
    if fx_from:
        fx_day = min(fx_from.values())
        for user_id in users_with_transactions(db):
            if user_id not in days or fx_day < days[user_id]:
                days[user_id] = fx_day
    _mark_stale_days(db, days)


def users_with_holdings(db: Session) -> list[int]:
    """Users with anything to value: transactions, bond purchases or a savings account."""
    traded = select(Account.user_id).join(Transaction, Transaction.account_id == Account.id)
    bonds = select(Account.user_id).join(BondHolding, BondHolding.account_id == Account.id)
    savings = select(Account.user_id).join(SavingsAccount, SavingsAccount.account_id == Account.id)
    return sorted(set(db.scalars(traded)) | set(db.scalars(bonds)) | set(db.scalars(savings)))


def mark_new_days(db: Session, today: dt.date) -> None:
    """Requests the days each user's history is missing: from the day after their last stored row (at most
    `today`, so today's row is refreshed), or the whole history when they have no rows yet; and from the first
    row valued at an estimated bond rate (the CPI may have arrived since). Days missed while the worker was down
    are filled this way. Does not commit."""
    last_rows = dict(db.execute(
        select(DailyValuation.user_id, func.max(DailyValuation.date)).group_by(DailyValuation.user_id)
    ).all())
    estimated = dict(db.execute(
        select(DailyValuation.user_id, func.min(DailyValuation.date))
        .where(DailyValuation.flags.contains([FLAG_RATE_ESTIMATED]))
        .group_by(DailyValuation.user_id)
    ).all())
    days = {}
    for user_id in users_with_holdings(db):
        day = min(today, last_rows[user_id] + dt.timedelta(days=1)) if user_id in last_rows else dt.date.min
        days[user_id] = min(day, estimated.get(user_id, day))
    _mark_stale_days(db, days)


def recompute_user(db: Session, user_id: int, today: dt.date) -> int:
    """Rebuilds the user's rows from `valuations_stale_from` to `today` and commits; returns the rows written.

    Every transaction is replayed in memory, but rows are built only from the stale day; earlier rows are kept.
    """
    try:
        lock_user(db, user_id)
        stale_from = db.scalar(select(User.valuations_stale_from).where(User.id == user_id))
        user = db.get(User, user_id)
        if stale_from is None or user is None:
            db.commit()
            return 0
        inputs = load_inputs(UserScope(db, user))
        rows = daily_rows(inputs.entries, inputs.splits, inputs.market, today, start=stale_from,
                          conversions=inputs.conversions, exit_rules=inputs.exit_rules)
        fixed = load_fixed_income(UserScope(db, user))
        rows += bond_rows(fixed.holdings, fixed.cpi, stale_from, today) + savings_rows(fixed.savings, stale_from, today)
        db.execute(delete(DailyValuation).where(DailyValuation.user_id == user_id, DailyValuation.date >= stale_from))
        values = [
            {
                "user_id": user_id, "account_id": row.account_id, "instrument_id": row.instrument_id, "date": row.day,
                "quantity": row.quantity, "value_pln": row.value_pln, "cost_pln": row.cost_pln,
                "net_flow_pln": row.net_flow_pln, "exit_cost_pln": row.exit_cost_pln, "flags": list(row.flags),
                "bond_holding_id": row.bond_holding_id, "savings_account_id": row.savings_account_id,
            }
            for row in rows
        ]
        for start in range(0, len(values), INSERT_CHUNK):
            db.execute(insert(DailyValuation), values[start:start + INSERT_CHUNK])
        db.execute(
            update(User).where(User.id == user_id).values(valuations_stale_from=None)
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(rows)


def recompute_stale(db: Session, today: dt.date) -> int:
    """Recomputes every user with a pending request; one user's failure does not stop the others."""
    user_ids = db.scalars(
        select(User.id).where(User.valuations_stale_from.is_not(None)).order_by(User.id)
    ).all()
    for user_id in user_ids:
        try:
            recompute_user(db, user_id, today)
        except Exception:
            logger.exception("Valuation recompute failed for user %s; it stays marked for the next run", user_id)
    return len(user_ids)


def recompute_in_background(sessions: Callable[[], Session], user_id: int) -> None:
    """Runs right after an import's response; on failure the worker's next tick retries (the user stays marked)."""
    try:
        with sessions() as db:
            recompute_user(db, user_id, local_today())
    except Exception:
        logger.exception("Background valuation recompute failed for user %s", user_id)
