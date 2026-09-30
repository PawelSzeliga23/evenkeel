from datetime import datetime
from decimal import Decimal

from sqlalchemy import CheckConstraint, DateTime, Numeric, String, false, func, true
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
