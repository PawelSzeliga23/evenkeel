"""The simulator's catalog (plan 7b): the starter list, tickers the user added, and the instruments held."""
import datetime as dt

from sqlalchemy import ColumnElement, Select, func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog.schemas import CatalogGroupOut, CatalogItemOut
from app.catalog.seed import ADDED_GROUP, GROUPS, HELD_GROUP
from app.errors import ApiError
from app.market.providers.yahoo import yahoo_symbol
from app.market.store import replace_provider_splits, upsert_prices
from app.market.types import PriceProvider, ProviderError, SymbolNotFound
from app.models import CatalogAddition, Instrument, Price
from app.scoping import UserScope

MAX_ADDED = 50  # per user: the worker refreshes every added instrument on each run


def added_by(user_id: int) -> Select[tuple[int]]:
    """Ids of the instruments the user added to the catalog."""
    return select(CatalogAddition.instrument_id).where(CatalogAddition.user_id == user_id)


def curated() -> ColumnElement[bool]:
    """The starter list: in the catalog for everyone (added tickers are in it only for who added them)."""
    return Instrument.in_catalog.is_(True) & Instrument.catalog_group.is_distinct_from(ADDED_GROUP)


def _prices_from(db: Session, ids: list[int]) -> dict[int, dt.date]:
    rows = db.execute(select(Price.instrument_id, func.min(Price.date)).where(Price.instrument_id.in_(ids))
                      .group_by(Price.instrument_id))
    return dict(rows.all())


def _item(instrument: Instrument, group: str, first: dict[int, dt.date]) -> CatalogItemOut:
    return CatalogItemOut(id=instrument.id, ticker=instrument.xtb_ticker, name=instrument.name,
                          currency=instrument.currency, group=group, accumulating=instrument.accumulating,
                          prices_from=first.get(instrument.id))


def catalog(scope: UserScope) -> list[CatalogGroupOut]:
    db = scope.db
    held = list(db.scalars(scope.instruments()))
    listed = list(db.scalars(select(Instrument).where(curated())))
    listed += db.scalars(select(Instrument).where(Instrument.id.in_(added_by(scope.user.id)),
                                                   Instrument.id.not_in([i.id for i in listed])))
    first = _prices_from(db, [i.id for i in held + listed])
    groups = [CatalogGroupOut(group=HELD_GROUP, items=[_item(i, HELD_GROUP, first) for i in held])]
    for name in GROUPS:
        groups.append(CatalogGroupOut(group=name, items=[
            _item(i, name, first) for i in listed if (i.catalog_group if curated_row(i) else ADDED_GROUP) == name]))
    for group in groups:
        group.items.sort(key=lambda item: item.name.lower())
    return [group for group in groups if group.items]


def curated_row(instrument: Instrument) -> bool:
    return instrument.in_catalog and instrument.catalog_group not in (None, ADDED_GROUP)


def _keep(db: Session, user_id: int, instrument: Instrument) -> CatalogItemOut:
    """Puts a known instrument in the user's catalog (unless it is on the starter list) and returns its item."""
    if not curated_row(instrument):
        instrument.in_catalog, instrument.catalog_group = True, ADDED_GROUP
        if db.scalar(added_by(user_id).where(CatalogAddition.instrument_id == instrument.id)) is None:
            db.add(CatalogAddition(user_id=user_id, instrument_id=instrument.id))
        db.commit()
    group = instrument.catalog_group if curated_row(instrument) else ADDED_GROUP
    return _item(instrument, group, _prices_from(db, [instrument.id]))


def add_ticker(db: Session, provider: PriceProvider, user_id: int, ticker: str,
               now: dt.datetime) -> tuple[CatalogItemOut, bool]:
    """(the catalog item, created?). An instrument already known by this ticker or Yahoo symbol is returned (and
    put in the user's catalog) without fetching; a new one gets its full history now, or nothing is saved."""
    mapped = yahoo_symbol(ticker)
    symbol = mapped or ticker
    existing = db.scalar(select(Instrument).where(or_(Instrument.xtb_ticker == ticker,
                                                      Instrument.price_symbol == symbol)))
    if existing is not None:
        return _keep(db, user_id, existing), False
    added = db.scalar(select(func.count()).select_from(CatalogAddition).where(CatalogAddition.user_id == user_id))
    if added >= MAX_ADDED:
        raise ApiError(422, "catalog_full", f"Masz już {MAX_ADDED} dodanych instrumentów, więcej nie można dodać.")
    try:
        history = provider.history(symbol, None)
    except SymbolNotFound:
        raise ApiError(422, "unknown_ticker", "Yahoo nie zna tego tickera.") from None
    except ProviderError:
        raise ApiError(502, "provider_failed", "Nie udało się pobrać notowań. Spróbuj za chwilę.") from None
    if not history.bars:
        raise ApiError(422, "unknown_ticker", "Yahoo nie zna tego tickera.")
    instrument = Instrument(
        xtb_ticker=ticker, name=(history.name or ticker)[:200], category=history.kind, currency=history.currency,
        price_symbol=symbol, price_symbol_overridden=mapped is None, price_checked_at=now,
        in_catalog=True, catalog_group=ADDED_GROUP,
    )
    db.add(instrument)
    try:
        db.flush()
    except IntegrityError:  # another request saved the same ticker while this one fetched its history
        db.rollback()
        winner = db.scalar(select(Instrument).where(Instrument.xtb_ticker == ticker))
        if winner is None:
            raise
        return _keep(db, user_id, winner), False  # e.g. saved by an XTB import meanwhile
    db.add(CatalogAddition(user_id=user_id, instrument_id=instrument.id))
    upsert_prices(db, instrument.id, history.bars, provider.name)
    replace_provider_splits(db, instrument.id, history.splits, None)
    db.commit()
    return _item(instrument, ADDED_GROUP, {instrument.id: history.bars[0].date}), True
