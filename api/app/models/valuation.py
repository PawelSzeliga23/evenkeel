import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, Integer, Numeric, String, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.ledger import MONEY, QUANTITY

RATIO = Numeric(18, 8)
CORPORATE_ACTION_TYPES = ("split", "reverse_split", "conversion", "suppress")
CORPORATE_ACTION_SOURCES = ("manual", "xtb", "provider")
WRAPPER_LIMIT_KINDS = ("ike", "ikze", "ikze_self_employed")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class CorporateAction(Base):
    """A split, conversion or `suppress` ("no event that day") of an instrument. Split 10:1 -> ratio_from=1, ratio_to=10.

    Provider and XTB entries (`user_id` NULL) are shared by all users. A manual entry belongs to its author and
    applies to their accounts only; on one instrument and day it wins over XTB, and XTB over the provider.
    """

    __tablename__ = "corporate_actions"
    __table_args__ = (
        Index(
            "uq_ca_inst_ed_src_usr",
            "instrument_id", "effective_date", "source", "user_id", unique=True, postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(_in_list("type", CORPORATE_ACTION_TYPES), name="type"),
        CheckConstraint(_in_list("source", CORPORATE_ACTION_SOURCES), name="source"),
        CheckConstraint("ratio_from > 0 AND ratio_to > 0", name="ratio_positive"),
        CheckConstraint("(source = 'manual') = (user_id IS NOT NULL)", name="manual_has_user"),
        CheckConstraint("(type = 'conversion') = (target_instrument_id IS NOT NULL)", name="conversion_has_target"),
        CheckConstraint("target_instrument_id <> instrument_id", name="target_differs"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    effective_date: Mapped[dt.date] = mapped_column(Date)
    ratio_from: Mapped[Decimal] = mapped_column(RATIO)
    ratio_to: Mapped[Decimal] = mapped_column(RATIO)
    target_instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    source: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)


class DailyValuation(Base):
    """Cache of the valuation engine: one row per account, component and day; can be dropped and rebuilt.

    `instrument_id`, `bond_holding_id`, `savings_account_id` — co najwyżej jeden ustawiony; żaden = gotówka konta.
    `net_flow_pln` carries external flows (deposits, withdrawals, transfers) of that day.
    """

    __tablename__ = "daily_valuations"
    __table_args__ = (
        Index(
            "uq_daily_valuations_component_date",
            "account_id", "instrument_id", "bond_holding_id", "savings_account_id", "date",
            unique=True, postgresql_nulls_not_distinct=True,
        ),
        Index("ix_daily_valuations_user_id_date", "user_id", "date"),
        CheckConstraint("num_nonnulls(instrument_id, bond_holding_id, savings_account_id) <= 1", name="one_component"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    bond_holding_id: Mapped[int | None] = mapped_column(ForeignKey("bond_holdings.id", ondelete="CASCADE"))
    savings_account_id: Mapped[int | None] = mapped_column(ForeignKey("savings_accounts.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column(Date)
    quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    value_pln: Mapped[Decimal] = mapped_column(MONEY)
    cost_pln: Mapped[Decimal] = mapped_column(MONEY)
    net_flow_pln: Mapped[Decimal] = mapped_column(MONEY)
    exit_cost_pln: Mapped[Decimal] = mapped_column(MONEY, server_default=text("0"))
    flags: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))


class WrapperLimit(Base):
    """Statutory yearly contribution limit of an IKE / IKZE (one row per year, seeded by migrations)."""

    __tablename__ = "wrapper_limits"
    __table_args__ = (CheckConstraint(_in_list("wrapper", WRAPPER_LIMIT_KINDS), name="wrapper"),)

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    wrapper: Mapped[str] = mapped_column(String(20), primary_key=True)
    limit_pln: Mapped[Decimal] = mapped_column(MONEY)
