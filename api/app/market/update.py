import datetime as dt
import logging
from collections.abc import Callable, Sequence
from dataclasses import dataclass, field

from sqlalchemy import exists, func, or_, select
from sqlalchemy.orm import Session

from app.market.store import (
    BASE_CURRENCY,
    fx_date_bounds,
    last_price_date,
    upsert_cpi,
    upsert_fx_rates,
    upsert_prices,
    upsert_ref_rates,
)
from app.market.types import (
    FxProvider,
    InflationProvider,
    PriceProvider,
    ProviderError,
    RefRateProvider,
    SymbolNotFound,
)
from app.models import Instrument, PositionLot, Transaction

logger = logging.getLogger(__name__)

PRICE_OVERLAP_DAYS = 5  # re-fetch recent days: a bar fetched during a session is replaced by the final close
FX_MARGIN_DAYS = 10  # rates from before the first transaction, so a "last known rate" exists on day one
ERROR_MAX_LENGTH = 200

MSG_UNMAPPED = "Brak automatycznego symbolu dla tej giełdy — ustaw symbol ręcznie."
MSG_NOT_FOUND = "Dostawca cen nie zna symbolu {symbol} — popraw symbol w ustawieniach."
MSG_FAILED = "Nie udało się pobrać cen ({symbol}) — ponowimy przy następnej aktualizacji."


@dataclass(frozen=True)
class MarketProviders:
    prices: PriceProvider
    fx: FxProvider
    inflation: InflationProvider
    ref_rates: RefRateProvider


@dataclass
class UpdateSummary:
    price_rows: int = 0
    failed_instruments: list[str] = field(default_factory=list)
    fx_rows: int = 0
    failed_currencies: list[str] = field(default_factory=list)
    cpi_rows: int = 0
    ref_rate_rows: int = 0
    failed_sources: list[str] = field(default_factory=list)


def _referenced() -> object:
    """Instruments are shared across users; the worker only touches ones actually held or traded."""
    return or_(
        exists().where(Transaction.instrument_id == Instrument.id),
        exists().where(PositionLot.instrument_id == Instrument.id),
    )


def resolve_symbol(provider: PriceProvider, instrument: Instrument) -> str | None:
    """A manual symbol is kept as-is; otherwise the automatic mapping is (re)applied."""
    if not instrument.price_symbol_overridden:
        instrument.price_symbol = provider.symbol_for(instrument.xtb_ticker)
    return instrument.price_symbol


def update_instrument_prices(db: Session, provider: PriceProvider, instrument: Instrument, now: dt.datetime) -> int:
    """Fetches missing prices of one instrument: full history on first sight, then from the last stored day.

    The instrument list is loaded once per run and kept as a plain Python list for its whole duration, so a
    PATCH committed by another session after the list was loaded would otherwise go unseen (the session's
    identity map keeps serving the pre-PATCH copy). `db.refresh(..., with_for_update=True)` reloads the
    current symbol/override/checked-at and holds the row lock until the caller's per-instrument commit.

    Provider problems end up in `instrument.price_error` (Polish, shown in the UI) and are never raised.
    Does not commit.
    """
    db.refresh(instrument, with_for_update=True)
    instrument.price_checked_at = now
    symbol = resolve_symbol(provider, instrument)
    if symbol is None:
        instrument.price_error = MSG_UNMAPPED
        return 0
    last = last_price_date(db, instrument.id)
    start = None if last is None else last - dt.timedelta(days=PRICE_OVERLAP_DAYS)
    try:
        history = provider.history(symbol, start)
    except SymbolNotFound:
        instrument.price_error = MSG_NOT_FOUND.format(symbol=symbol)[:ERROR_MAX_LENGTH]
        logger.warning("Price provider does not know %s (instrument %s)", symbol, instrument.xtb_ticker)
        return 0
    except ProviderError as exc:
        instrument.price_error = MSG_FAILED.format(symbol=symbol)[:ERROR_MAX_LENGTH]
        logger.warning("Price update failed for %s (%s): %s", instrument.xtb_ticker, symbol, exc)
        return 0
    instrument.currency = history.currency
    instrument.price_error = None
    return upsert_prices(db, instrument.id, history.bars, provider.name)


def _update_prices(
    db: Session, provider: PriceProvider, instruments: Sequence[Instrument], now: dt.datetime
) -> tuple[int, list[str]]:
    rows, failed = 0, []
    for instrument in instruments:
        ticker, instrument_id = instrument.xtb_ticker, instrument.id
        try:
            rows += update_instrument_prices(db, provider, instrument, now)
        except Exception:
            # Not just ProviderError: a malformed-but-valid response (bad JSON shape, a bad decimal) or a
            # DB error must not crash the whole run — roll back, mark the instrument, and move on.
            db.rollback()
            logger.exception("Price update crashed for %s", ticker)
            instrument = db.get(Instrument, instrument_id)
            symbol = instrument.price_symbol or ticker
            instrument.price_error = MSG_FAILED.format(symbol=symbol)[:ERROR_MAX_LENGTH]
            instrument.price_checked_at = now
            db.commit()
            failed.append(ticker)
            continue
        if instrument.price_error:
            failed.append(instrument.xtb_ticker)
        db.commit()  # keep progress: a later failure must not lose earlier instruments
    return rows, failed


def update_all_prices(db: Session, provider: PriceProvider, now: dt.datetime) -> tuple[int, list[str]]:
    instruments = db.scalars(select(Instrument).where(_referenced()).order_by(Instrument.id)).all()
    return _update_prices(db, provider, instruments, now)


def backfill_new_instruments(db: Session, provider: PriceProvider, now: dt.datetime) -> tuple[int, list[str]]:
    """Full history for instruments never tried yet (new from an import, or reset by a symbol override)."""
    instruments = db.scalars(
        select(Instrument)
        .where(Instrument.price_checked_at.is_(None), _referenced())
        .order_by(Instrument.id)
    ).all()
    return _update_prices(db, provider, instruments, now)


def fx_ranges_to_fetch(
    stored_min: dt.date | None, stored_max: dt.date | None, needed_from: dt.date, today: dt.date
) -> list[tuple[dt.date, dt.date]]:
    if stored_min is None or stored_max is None:
        return [(needed_from, today)] if needed_from <= today else []
    ranges = []
    if needed_from < stored_min:
        ranges.append((needed_from, stored_min - dt.timedelta(days=1)))
    if stored_max < today:
        ranges.append((stored_max + dt.timedelta(days=1), today))
    return ranges


def fx_needed_from(db: Session, today: dt.date) -> dt.date:
    """Rates are needed from shortly before the earliest transaction of any user (market data is shared)."""
    first = db.scalar(select(func.min(Transaction.occurred_at)))
    start = first.date() if first is not None else today
    return start - dt.timedelta(days=FX_MARGIN_DAYS)


def update_fx(db: Session, provider: FxProvider, today: dt.date) -> tuple[int, list[str]]:
    currencies = db.scalars(
        select(Instrument.currency)
        .where(Instrument.currency.is_not(None), Instrument.currency != BASE_CURRENCY, _referenced())
        .distinct()
        .order_by(Instrument.currency)
    ).all()
    needed_from = fx_needed_from(db, today)
    rows, failed = 0, []
    for currency in currencies:
        stored_min, stored_max = fx_date_bounds(db, currency)
        try:
            written = sum(
                upsert_fx_rates(db, currency, provider.rates(currency, start, end))
                for start, end in fx_ranges_to_fetch(stored_min, stored_max, needed_from, today)
            )
        except ProviderError as exc:
            db.rollback()
            failed.append(currency)
            logger.warning("FX update failed for %s: %s", currency, exc)
            continue
        except Exception:
            db.rollback()
            failed.append(currency)
            logger.exception("FX update crashed for %s", currency)
            continue
        db.commit()
        rows += written
    return rows, failed


def _source(db: Session, name: str, job: Callable[[], int], summary: UpdateSummary) -> int:
    try:
        rows = job()
    except ProviderError as exc:
        db.rollback()
        summary.failed_sources.append(name)
        logger.warning("Market data source %s failed: %s", name, exc)
        return 0
    except Exception:
        db.rollback()
        summary.failed_sources.append(name)
        logger.exception("Market data source %s crashed", name)
        return 0
    db.commit()
    return rows


def run_market_update(db: Session, providers: MarketProviders, now: dt.datetime, today: dt.date) -> UpdateSummary:
    summary = UpdateSummary()
    summary.price_rows, summary.failed_instruments = update_all_prices(db, providers.prices, now)
    summary.fx_rows, summary.failed_currencies = update_fx(db, providers.fx, today)
    summary.cpi_rows = _source(db, "cpi", lambda: upsert_cpi(db, providers.inflation.cpi()), summary)
    summary.ref_rate_rows = _source(
        db, "nbp_ref_rates", lambda: upsert_ref_rates(db, providers.ref_rates.ref_rates()), summary
    )
    return summary
