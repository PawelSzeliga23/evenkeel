import datetime as dt
from collections.abc import Iterable, Sequence
from decimal import Decimal
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.market.types import CpiPoint, FxPoint, PriceBar, RefRatePoint
from app.models import Cpi, FxRate, NbpRefRate, Price
from app.models.base import Base

BASE_CURRENCY = "PLN"
UPSERT_CHUNK = 1000


def _upsert(db: Session, model: type[Base], rows: Iterable[dict[str, Any]], keys: tuple[str, ...]) -> int:
    """INSERT ... ON CONFLICT DO UPDATE in chunks; a key repeated in `rows` keeps its last row. Does not commit."""
    unique = list({tuple(row[key] for key in keys): row for row in rows}.values())
    for start in range(0, len(unique), UPSERT_CHUNK):
        chunk = unique[start:start + UPSERT_CHUNK]
        statement = insert(model).values(chunk)
        updates = {column: statement.excluded[column] for column in chunk[0] if column not in keys}
        db.execute(statement.on_conflict_do_update(index_elements=list(keys), set_=updates))
    return len(unique)


def upsert_prices(db: Session, instrument_id: int, bars: Iterable[PriceBar], source: str) -> int:
    rows = (
        {"instrument_id": instrument_id, "date": bar.date, "close": bar.close, "adj_close": bar.adj_close, "source": source}
        for bar in bars
    )
    return _upsert(db, Price, rows, ("instrument_id", "date"))


def upsert_fx_rates(db: Session, currency: str, points: Iterable[FxPoint]) -> int:
    rows = ({"currency": currency, "date": point.date, "rate_pln": point.rate_pln} for point in points)
    return _upsert(db, FxRate, rows, ("currency", "date"))


def upsert_cpi(db: Session, points: Iterable[CpiPoint]) -> int:
    rows = ({"year_month": point.year_month, "yoy": point.yoy} for point in points)
    return _upsert(db, Cpi, rows, ("year_month",))


def upsert_ref_rates(db: Session, points: Iterable[RefRatePoint]) -> int:
    rows = ({"valid_from": point.valid_from, "rate": point.rate} for point in points)
    return _upsert(db, NbpRefRate, rows, ("valid_from",))


def delete_prices(db: Session, instrument_id: int) -> int:
    return db.execute(delete(Price).where(Price.instrument_id == instrument_id)).rowcount


def last_price_date(db: Session, instrument_id: int) -> dt.date | None:
    return db.scalar(select(func.max(Price.date)).where(Price.instrument_id == instrument_id))


def fx_date_bounds(db: Session, currency: str) -> tuple[dt.date | None, dt.date | None]:
    low, high = db.execute(
        select(func.min(FxRate.date), func.max(FxRate.date)).where(FxRate.currency == currency)
    ).one()
    return low, high


def price_on(db: Session, instrument_id: int, day: dt.date) -> Price | None:
    """Last known close on or before `day` (weekends and holidays reuse the previous session)."""
    return db.scalar(
        select(Price)
        .where(Price.instrument_id == instrument_id, Price.date <= day)
        .order_by(Price.date.desc())
        .limit(1)
    )


def fx_on(db: Session, currency: str, day: dt.date) -> Decimal | None:
    """PLN per unit of `currency`: last NBP rate on or before `day`; PLN itself is 1."""
    if currency == BASE_CURRENCY:
        return Decimal(1)
    return db.scalar(
        select(FxRate.rate_pln)
        .where(FxRate.currency == currency, FxRate.date <= day)
        .order_by(FxRate.date.desc())
        .limit(1)
    )


def latest_prices(db: Session, instrument_ids: Sequence[int]) -> dict[int, Price]:
    if not instrument_ids:
        return {}
    rows = db.scalars(
        select(Price)
        .where(Price.instrument_id.in_(instrument_ids))
        .order_by(Price.instrument_id, Price.date.desc())
    ).all()
    result = {}
    for row in rows:
        if row.instrument_id not in result:
            result[row.instrument_id] = row
    return result
