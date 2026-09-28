"""Treasury bonds and savings accounts. Series are shared (like prices); holdings, rates and balances belong to
the owner of their account."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.ledger import MONEY

BOND_TYPES = ("OTS", "ROR", "DOR", "DOS", "TOS", "COI", "EDO", "ROS", "ROD")
INTEREST_MODES = ("capitalized", "paid_annually", "paid_monthly", "fixed_at_maturity")
RATE_BASES = ("fixed", "cpi", "nbp_ref")
CAPITALIZATIONS = ("daily", "monthly", "quarterly")
PERCENT = Numeric(7, 4)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class BondSeries(Base):
    """One monthly issue of a treasury bond, e.g. EDO0936: 5.35 % in the first year, then CPI + 2.00 %."""

    __tablename__ = "bond_series"
    __table_args__ = (
        CheckConstraint(_in_list("bond_type", BOND_TYPES), name="bond_type"),
        CheckConstraint(_in_list("interest_mode", INTEREST_MODES), name="interest_mode"),
        CheckConstraint(_in_list("rate_basis", RATE_BASES), name="rate_basis"),
    )

    series: Mapped[str] = mapped_column(String(10), primary_key=True)
    bond_type: Mapped[str] = mapped_column(String(3))
    issue_month: Mapped[dt.date] = mapped_column(Date)  # first day of the month the series was sold in
    maturity_months: Mapped[int] = mapped_column(Integer)
    first_period_rate: Mapped[Decimal] = mapped_column(PERCENT)  # percent a year
    margin: Mapped[Decimal] = mapped_column(PERCENT)  # percentage points over the rate basis
    early_redemption_fee: Mapped[Decimal] = mapped_column(Numeric(6, 2))  # zł per bond of 100 zł
    interest_mode: Mapped[str] = mapped_column(String(20))
    rate_basis: Mapped[str] = mapped_column(String(10))


class BondHolding(Base):
    """One purchase of bonds: interest periods run from the purchase day. `redeemed_at`: early redemption of all
    of them."""

    __tablename__ = "bond_holdings"
    __table_args__ = (
        CheckConstraint(_in_list("bond_type", BOND_TYPES), name="bond_type"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("redeemed_at IS NULL OR redeemed_at >= purchase_date", name="redeemed_after_purchase"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    bond_type: Mapped[str] = mapped_column(String(3))
    series: Mapped[str] = mapped_column(ForeignKey("bond_series.series"))
    quantity: Mapped[int] = mapped_column(Integer)  # bonds of 100 zł
    purchase_date: Mapped[dt.date] = mapped_column(Date)
    redeemed_at: Mapped[dt.date | None] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, server_default="")


class SavingsAccount(Base):
    __tablename__ = "savings_accounts"
    __table_args__ = (CheckConstraint(_in_list("capitalization", CAPITALIZATIONS), name="capitalization"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), unique=True)
    capitalization: Mapped[str] = mapped_column(String(10))


class SavingsRate(Base):
    """Annual interest rate in percent, valid from `valid_from` until the next row."""

    __tablename__ = "savings_rates"
    __table_args__ = (
        UniqueConstraint("savings_account_id", "valid_from"),
        CheckConstraint("annual_rate >= 0", name="rate_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    savings_account_id: Mapped[int] = mapped_column(ForeignKey("savings_accounts.id", ondelete="CASCADE"))
    valid_from: Mapped[dt.date] = mapped_column(Date)
    annual_rate: Mapped[Decimal] = mapped_column(PERCENT)


class SavingsBalance(Base):
    """The balance at the end of `as_of_date`, copied from the bank."""

    __tablename__ = "savings_balances"
    __table_args__ = (
        UniqueConstraint("savings_account_id", "as_of_date"),
        CheckConstraint("balance >= 0", name="balance_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    savings_account_id: Mapped[int] = mapped_column(ForeignKey("savings_accounts.id", ondelete="CASCADE"))
    as_of_date: Mapped[dt.date] = mapped_column(Date)
    balance: Mapped[Decimal] = mapped_column(MONEY)
