from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Numeric, String, UniqueConstraint, false, func, true
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Instrument(Base):
    """A traded instrument, shared by all users (prices are the same for everyone)."""

    __tablename__ = "instruments"
    __table_args__ = (
        CheckConstraint("spread_pct IS NULL OR (spread_pct >= 0 AND spread_pct <= 5)", name="spread_pct_range"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    xtb_ticker: Mapped[str] = mapped_column(String(40), unique=True)
    name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(20))
    currency: Mapped[str | None] = mapped_column(String(3))
    exchange_suffix: Mapped[str | None] = mapped_column(String(10))
    price_symbol: Mapped[str | None] = mapped_column(String(40))
    price_symbol_overridden: Mapped[bool] = mapped_column(server_default=false())
    isin: Mapped[str | None] = mapped_column(String(12))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    price_checked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    price_error: Mapped[str | None] = mapped_column(String(200))
    spread_pct: Mapped[Decimal | None] = mapped_column(Numeric(6, 4))  # manual half-spread, percent (plan 6d)
    # False = the stored price history predates split events; the next update refetches it in full once.
    splits_synced: Mapped[bool] = mapped_column(server_default=true())
    # Plan 7b: shown in the simulator's catalog even when nobody holds it; the worker keeps its prices fresh.
    in_catalog: Mapped[bool] = mapped_column(server_default=false())
    catalog_group: Mapped[str | None] = mapped_column(String(40))
    accumulating: Mapped[bool | None] = mapped_column()  # an accumulating ETF: dividends stay in the price
    catalog_seeded: Mapped[bool] = mapped_column(server_default=false())  # inserted by migration 0010


class CatalogAddition(Base):
    """A ticker a user added to the simulator's catalog: shown under „Dodane przez Ciebie” to that user only."""

    __tablename__ = "catalog_additions"
    __table_args__ = (UniqueConstraint("user_id", "instrument_id", name="uq_catalog_additions_user_instrument"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
