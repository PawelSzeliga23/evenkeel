import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.ledger import MONEY, QUANTITY

RATIO = Numeric(18, 8)
CORPORATE_ACTION_TYPES = ("split", "reverse_split", "conversion")
CORPORATE_ACTION_SOURCES = ("manual", "xtb", "provider")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class CorporateAction(Base):
    """A split or conversion of an instrument, shared by all users. Split 10:1 -> ratio_from=1, ratio_to=10."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint("instrument_id", "type", "effective_date", "source"),
        CheckConstraint(_in_list("type", CORPORATE_ACTION_TYPES), name="type"),
        CheckConstraint(_in_list("source", CORPORATE_ACTION_SOURCES), name="source"),
        CheckConstraint("ratio_from > 0 AND ratio_to > 0", name="ratio_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    effective_date: Mapped[dt.date] = mapped_column(Date)
    ratio_from: Mapped[Decimal] = mapped_column(RATIO)
    ratio_to: Mapped[Decimal] = mapped_column(RATIO)
    target_instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    source: Mapped[str] = mapped_column(String(10))


class DailyValuation(Base):
    """Cache of the valuation engine: one row per account, component and day; can be dropped and rebuilt.

    `instrument_id` NULL is the account's cash: `quantity` is the balance in the account currency and
    `net_flow_pln` carries its external flows (deposits, withdrawals, transfers) of that day.
    """

    __tablename__ = "daily_valuations"
    __table_args__ = (
        Index(
            "uq_daily_valuations_account_id_instrument_id_date", "account_id", "instrument_id", "date",
            unique=True, postgresql_nulls_not_distinct=True,
        ),
        Index("ix_daily_valuations_user_id_date", "user_id", "date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    date: Mapped[dt.date] = mapped_column(Date)
    quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    value_pln: Mapped[Decimal] = mapped_column(MONEY)
    cost_pln: Mapped[Decimal] = mapped_column(MONEY)
    net_flow_pln: Mapped[Decimal] = mapped_column(MONEY)
    flags: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
