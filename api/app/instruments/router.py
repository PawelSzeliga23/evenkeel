import datetime as dt
import logging

from fastapi import APIRouter, Depends
from sqlalchemy import exists, select

from app.catalog.service import curated
from app.errors import ApiError
from app.instruments.schemas import InstrumentOut, InstrumentUpdate
from app.market.store import delete_prices, latest_prices
from app.models import Account, CatalogAddition, Instrument, PositionLot, Price, User
from app.scoping import DbId, UserScope, get_scope
from app.valuation.service import holders, mark_stale

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/instruments", tags=["instruments"])


def _out(instrument: Instrument, latest: Price | None) -> InstrumentOut:
    return InstrumentOut(
        id=instrument.id,
        xtb_ticker=instrument.xtb_ticker,
        name=instrument.name,
        category=instrument.category,
        currency=instrument.currency,
        price_symbol=instrument.price_symbol,
        price_symbol_overridden=instrument.price_symbol_overridden,
        price_error=instrument.price_error,
        last_price=latest.close if latest else None,
        last_price_date=latest.date if latest else None,
        spread_pct=instrument.spread_pct,
    )


@router.get("", response_model=list[InstrumentOut])
def list_instruments(scope: UserScope = Depends(get_scope)) -> list[InstrumentOut]:
    instruments = scope.db.scalars(scope.instruments()).all()
    latest = latest_prices(scope.db, [instrument.id for instrument in instruments])
    return [_out(instrument, latest.get(instrument.id)) for instrument in instruments]


@router.patch("/{instrument_id}", response_model=InstrumentOut)
def update_instrument(instrument_id: DbId, body: InstrumentUpdate, scope: UserScope = Depends(get_scope)) -> InstrumentOut:
    instrument = scope.get_instrument(instrument_id)
    if body.model_fields_set & {"price_symbol", "spread_pct"} and _used_by_others(scope, instrument):
        raise ApiError(409, "shared_instrument", "Ten instrument mają też inne osoby albo jest w katalogu symulatora — "
                                                 "zmiana symbolu lub spreadu zmieniłaby ich wyceny.")
    if "price_symbol" in body.model_fields_set:
        _update_symbol(scope, instrument, body.price_symbol)
    if "spread_pct" in body.model_fields_set and body.spread_pct != instrument.spread_pct:
        instrument.spread_pct = body.spread_pct
        # Every holder's payout value depends on the spread (plan 6d); the worker rebuilds their histories.
        mark_stale(scope.db, holders(scope.db, [instrument.id]), dt.date.min)
        scope.db.commit()
        logger.info("User %s set spread of %s to %s %%", scope.user.id, instrument.xtb_ticker, body.spread_pct)
    return _out(instrument, latest_prices(scope.db, [instrument.id]).get(instrument.id))


def _used_by_others(scope: UserScope, instrument: Instrument) -> bool:
    """Instruments are shared: their symbol and spread may be changed only by their sole user."""
    if any(user_id != scope.user.id for user_id in holders(scope.db, [instrument.id])):
        return True
    others = select(Account.id).where(Account.user_id != scope.user.id)
    return bool(scope.db.scalar(select(
        exists().where(PositionLot.instrument_id == instrument.id, PositionLot.account_id.in_(others))
        | exists().where(CatalogAddition.instrument_id == instrument.id, CatalogAddition.user_id != scope.user.id)
        # the starter list is in every user's simulator
        | (exists().where(Instrument.id == instrument.id, curated()) & exists().where(User.id != scope.user.id)))))


def _update_symbol(scope: UserScope, instrument: Instrument, symbol: str | None) -> None:
    unchanged = (symbol is None and not instrument.price_symbol_overridden) or (
        symbol is not None and instrument.price_symbol_overridden and symbol == instrument.price_symbol
    )
    if unchanged:
        return
    # Prices of the old symbol are wrong for the new one: drop them and let the worker refetch the history.
    instrument.price_symbol = symbol
    instrument.price_symbol_overridden = symbol is not None
    instrument.price_checked_at = None
    instrument.price_error = None
    delete_prices(scope.db, instrument.id)
    # Every holder's history was valued with the old symbol's prices.
    mark_stale(scope.db, holders(scope.db, [instrument.id]), dt.date.min)
    scope.db.commit()
    logger.info("User %s set price symbol of %s to %r", scope.user.id, instrument.xtb_ticker, symbol)
