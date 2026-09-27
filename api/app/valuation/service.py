"""Loads a user's data for the valuation engine and maintains the `daily_valuations` cache.

A recompute is requested with `mark_stale` (the earliest requested day wins) and done by `recompute_user`.
Both take the user's advisory lock, so a marking transaction (an import) waits for a running recompute,
and the next recompute sees the committed data.
"""
import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.orm import Session

from app.models import Account, CorporateAction, DailyValuation, FxRate, Instrument, Price, Transaction, User, XtbSnapshot
from app.scoping import UserScope
from app.valuation.engine import Entry, Split, daily_rows
from app.valuation.market_data import BASE_CURRENCY, MarketData, Series

logger = logging.getLogger(__name__)

ZONE = ZoneInfo("Europe/Warsaw")  # valuation days are Warsaw calendar days, like the worker's schedule
LOCK_NAMESPACE = 4  # high 32 bits of the advisory lock key "valuations of user N"
INSERT_CHUNK = 1000
SPLIT_TYPES = ("split", "reverse_split")


def local_day(moment: dt.datetime) -> dt.date:
    return moment.astimezone(ZONE).date()


def local_today(now: dt.datetime | None = None) -> dt.date:
    return local_day(now or dt.datetime.now(dt.UTC))


@dataclass(frozen=True)
class Inputs:
    entries: list[Entry]
    splits: list[Split]
    market: MarketData


def _series(points: dict[object, list[tuple[dt.date, object]]]) -> dict:
    return {key: Series(values) for key, values in points.items()}


def load_inputs(scope: UserScope) -> Inputs:
    """The user's transactions and every piece of market data the engine may look up for them."""
    db = scope.db
    entries = [
        Entry(t.id, t.account_id, t.instrument_id, t.type, local_day(t.occurred_at), t.amount, t.currency,
              t.quantity, t.price, t.xtb_position_id)
        for t in db.scalars(scope.transactions()).unique()
    ]
    instrument_ids = sorted({entry.instrument_id for entry in entries if entry.instrument_id is not None})
    market = MarketData()
    splits: list[Split] = []
    if instrument_ids:
        prices: dict[object, list] = defaultdict(list)
        for instrument_id, day, close in db.execute(
            select(Price.instrument_id, Price.date, Price.close).where(Price.instrument_id.in_(instrument_ids))
        ):
            prices[instrument_id].append((day, close))
        market.prices = _series(prices)
        market.currencies = dict(
            db.execute(select(Instrument.id, Instrument.currency).where(Instrument.id.in_(instrument_ids))).all()
        )
        splits = [
            Split(action.instrument_id, action.effective_date, action.ratio_from, action.ratio_to)
            for action in db.scalars(
                select(CorporateAction).where(
                    CorporateAction.instrument_id.in_(instrument_ids), CorporateAction.type.in_(SPLIT_TYPES)
                )
            )
        ]
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
        rates: dict[object, list] = defaultdict(list)
        for currency, day, rate in db.execute(
            select(FxRate.currency, FxRate.date, FxRate.rate_pln).where(FxRate.currency.in_(currencies))
        ):
            rates[currency].append((day, rate))
        market.fx = _series(rates)
    return Inputs(entries, splits, market)


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
    """Users with any transaction in one of the instruments."""
    ids = list(instrument_ids)
    if not ids:
        return []
    return list(db.scalars(
        select(Account.user_id).join(Transaction, Transaction.account_id == Account.id)
        .where(Transaction.instrument_id.in_(ids)).distinct().order_by(Account.user_id)
    ))


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


def recompute_user(db: Session, user_id: int, today: dt.date) -> int:
    """Rebuilds the user's rows from `valuations_stale_from` to `today` and commits; returns the rows written.

    The whole history is replayed in memory (days × positions: cheap); rows before the stale day are kept.
    """
    try:
        lock_user(db, user_id)
        stale_from = db.scalar(select(User.valuations_stale_from).where(User.id == user_id))
        user = db.get(User, user_id)
        if stale_from is None or user is None:
            db.commit()
            return 0
        inputs = load_inputs(UserScope(db, user))
        rows = [row for row in daily_rows(inputs.entries, inputs.splits, inputs.market, today) if row.day >= stale_from]
        db.execute(delete(DailyValuation).where(DailyValuation.user_id == user_id, DailyValuation.date >= stale_from))
        values = [
            {
                "user_id": user_id, "account_id": row.account_id, "instrument_id": row.instrument_id, "date": row.day,
                "quantity": row.quantity, "value_pln": row.value_pln, "cost_pln": row.cost_pln,
                "net_flow_pln": row.net_flow_pln, "flags": list(row.flags),
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
