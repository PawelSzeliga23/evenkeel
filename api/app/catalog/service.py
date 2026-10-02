"""The simulator's catalog (plan 7b): the starter list, tickers the owner added, and the instruments held."""
import datetime as dt

from sqlalchemy import func, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.catalog.schemas import CatalogGroupOut, CatalogItemOut
from app.catalog.seed import ADDED_GROUP, GROUPS, HELD_GROUP
from app.errors import ApiError
from app.market.providers.yahoo import yahoo_symbol
from app.market.store import replace_provider_splits, upsert_prices
from app.market.types import PriceProvider, ProviderError, SymbolNotFound
from app.models import Instrument, Price
from app.scoping import UserScope

MAX_ADDED = 50  # the catalog is shared and the worker refreshes every instrument in it on each run


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
    listed = list(db.scalars(select(Instrument).where(Instrument.in_catalog.is_(True))))
    first = _prices_from(db, [i.id for i in held + listed])
    groups = [CatalogGroupOut(group=HELD_GROUP, items=[_item(i, HELD_GROUP, first) for i in held])]
    for name in GROUPS:
        groups.append(CatalogGroupOut(group=name, items=[
            _item(i, name, first) for i in listed if i.catalog_group == name]))
    for group in groups:
        group.items.sort(key=lambda item: item.name.lower())
    return [group for group in groups if group.items]


def add_ticker(db: Session, provider: PriceProvider, ticker: str, now: dt.datetime) -> tuple[CatalogItemOut, bool]:
    """(the catalog item, created?). An instrument already known by this ticker or Yahoo symbol is returned (and
    put in the catalog) without fetching; a new one gets its full history now, or nothing is saved."""
    mapped = yahoo_symbol(ticker)
    symbol = mapped or ticker
    existing = db.scalar(select(Instrument).where(or_(Instrument.xtb_ticker == ticker,
                                                      Instrument.price_symbol == symbol)))
    if existing is not None:
        if not existing.in_catalog:
            existing.in_catalog, existing.catalog_group = True, existing.catalog_group or ADDED_GROUP
            db.commit()
        return _item(existing, existing.catalog_group, _prices_from(db, [existing.id])), False
    added = db.scalar(select(func.count()).select_from(Instrument)
                      .where(Instrument.in_catalog.is_(True), Instrument.catalog_group == ADDED_GROUP))
    if added >= MAX_ADDED:
        raise ApiError(422, "catalog_full", f"W katalogu jest już {MAX_ADDED} dodanych instrumentów, więcej nie można dodać.")
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
        if not winner.in_catalog:  # e.g. saved by an XTB import meanwhile: the caller asked for it in the catalog
            winner.in_catalog, winner.catalog_group = True, winner.catalog_group or ADDED_GROUP
            db.commit()
        return _item(winner, winner.catalog_group or ADDED_GROUP, _prices_from(db, [winner.id])), False
    upsert_prices(db, instrument.id, history.bars, provider.name)
    replace_provider_splits(db, instrument.id, history.splits, None)
    db.commit()
    return _item(instrument, ADDED_GROUP, {instrument.id: history.bars[0].date}), True
