from datetime import datetime
from decimal import Decimal
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.instrument import Instrument

MONEY = Numeric(20, 4)
QUANTITY = Numeric(24, 8)
PRICE = Numeric(24, 8)
RATE = Numeric(18, 8)
PERCENT = Numeric(12, 4)

TRANSACTION_TYPES = (
    "buy", "sell", "dividend", "withholding_tax", "interest", "interest_tax",
    "deposit", "withdrawal", "transfer_in", "transfer_out", "fee", "unknown",
)
SNAPSHOT_KINDS = ("instrument_summary", "lot", "account_summary")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class ImportRecord(Base):
    __tablename__ = "imports"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    filename: Mapped[str] = mapped_column(String(255))
    file_hash: Mapped[str] = mapped_column(String(64))
    report_from: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    report_to: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    imported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    rows_added: Mapped[int] = mapped_column(Integer)
    rows_duplicate: Mapped[int] = mapped_column(Integer)
    rows_unknown: Mapped[int] = mapped_column(Integer)
    warnings: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        UniqueConstraint("account_id", "external_id"),
        CheckConstraint(_in_list("type", TRANSACTION_TYPES), name="type"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    type: Mapped[str] = mapped_column(String(20))
    xtb_type: Mapped[str] = mapped_column(String(60))
    occurred_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    amount: Mapped[Decimal] = mapped_column(MONEY)
    currency: Mapped[str] = mapped_column(String(3))
    quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    price: Mapped[Decimal | None] = mapped_column(PRICE)
    implied_fx_rate: Mapped[Decimal | None] = mapped_column(RATE)
    xtb_position_id: Mapped[str | None] = mapped_column(String(40))
    external_id: Mapped[str] = mapped_column(String(64))
    comment: Mapped[str] = mapped_column(Text)
    counterparty_account: Mapped[str | None] = mapped_column(String(50))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)
    transfer_pair_id: Mapped[int | None] = mapped_column(ForeignKey("transactions.id", ondelete="SET NULL"))
    import_id: Mapped[int | None] = mapped_column(ForeignKey("imports.id", ondelete="SET NULL"))

    instrument: Mapped[Instrument | None] = relationship(lazy="joined")

    @property
    def ticker(self) -> str | None:
        return self.instrument.xtb_ticker if self.instrument else None


class PositionLot(Base):
    __tablename__ = "position_lots"
    __table_args__ = (UniqueConstraint("account_id", "xtb_position_id"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id"))
    xtb_position_id: Mapped[str] = mapped_column(String(40))
    side: Mapped[str] = mapped_column(String(10))
    quantity: Mapped[Decimal] = mapped_column(QUANTITY)
    open_price: Mapped[Decimal] = mapped_column(PRICE)
    opened_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    open_commission: Mapped[Decimal | None] = mapped_column(MONEY)
    swap: Mapped[Decimal | None] = mapped_column(MONEY)
    rollover: Mapped[Decimal | None] = mapped_column(MONEY)
    margin: Mapped[Decimal | None] = mapped_column(MONEY)
    stop_loss: Mapped[Decimal | None] = mapped_column(PRICE)
    take_profit: Mapped[Decimal | None] = mapped_column(PRICE)
    closed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    close_price: Mapped[Decimal | None] = mapped_column(PRICE)
    close_origin: Mapped[str | None] = mapped_column(String(40))
    open_conversion_rate: Mapped[Decimal | None] = mapped_column(RATE)
    close_conversion_rate: Mapped[Decimal | None] = mapped_column(RATE)
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)


class XtbSnapshot(Base):
    """What XTB itself reported at export time; used to reconcile our own valuation."""

    __tablename__ = "xtb_snapshots"
    __table_args__ = (CheckConstraint(_in_list("row_kind", SNAPSHOT_KINDS), name="row_kind"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    import_id: Mapped[int] = mapped_column(ForeignKey("imports.id", ondelete="CASCADE"), index=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    xtb_position_id: Mapped[str | None] = mapped_column(String(40))
    row_kind: Mapped[str] = mapped_column(String(20))
    volume: Mapped[Decimal | None] = mapped_column(QUANTITY)
    value: Mapped[Decimal | None] = mapped_column(MONEY)
    current_price: Mapped[Decimal | None] = mapped_column(PRICE)
    net_profit: Mapped[Decimal | None] = mapped_column(MONEY)
    net_profit_pct: Mapped[Decimal | None] = mapped_column(PERCENT)
    gross_profit: Mapped[Decimal | None] = mapped_column(MONEY)
    taken_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    raw: Mapped[dict[str, Any]] = mapped_column(JSONB)
