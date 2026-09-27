import datetime as dt
import logging

from fastapi import APIRouter, Depends

from app.instruments.schemas import InstrumentOut, InstrumentUpdate
from app.market.store import delete_prices, latest_prices
from app.models import Instrument, Price
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
    )


@router.get("", response_model=list[InstrumentOut])
def list_instruments(scope: UserScope = Depends(get_scope)) -> list[InstrumentOut]:
    instruments = scope.db.scalars(scope.instruments()).all()
    latest = latest_prices(scope.db, [instrument.id for instrument in instruments])
    return [_out(instrument, latest.get(instrument.id)) for instrument in instruments]


@router.patch("/{instrument_id}", response_model=InstrumentOut)
def update_instrument(instrument_id: DbId, body: InstrumentUpdate, scope: UserScope = Depends(get_scope)) -> InstrumentOut:
    instrument = scope.get_instrument(instrument_id)
    symbol = body.price_symbol
    unchanged = (symbol is None and not instrument.price_symbol_overridden) or (
        symbol is not None and instrument.price_symbol_overridden and symbol == instrument.price_symbol
    )
    if not unchanged:
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
    return _out(instrument, latest_prices(scope.db, [instrument.id]).get(instrument.id))
