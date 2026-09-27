import datetime as dt
from decimal import Decimal

from sqlalchemy import Date, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.ledger import PRICE, RATE

YOY = Numeric(8, 2)
REF_RATE = Numeric(6, 2)


class Price(Base):
    """Daily close of an instrument in its quote currency (instruments.currency). Shared by all users."""

    __tablename__ = "prices"

    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    close: Mapped[Decimal] = mapped_column(PRICE)
    adj_close: Mapped[Decimal | None] = mapped_column(PRICE)
    source: Mapped[str] = mapped_column(String(20))


class FxRate(Base):
    """NBP table A mid rate: PLN per one unit of `currency`, published on `date`."""

    __tablename__ = "fx_rates"

    currency: Mapped[str] = mapped_column(String(3), primary_key=True)
    date: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    rate_pln: Mapped[Decimal] = mapped_column(RATE)


class Cpi(Base):
    """GUS CPI, same month of previous year = 100, stored as a change in percent (103.4 -> 3.40)."""

    __tablename__ = "cpi"

    year_month: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    yoy: Mapped[Decimal] = mapped_column(YOY)


class NbpRefRate(Base):
    """NBP reference rate in percent, valid from `valid_from` until the next row."""

    __tablename__ = "nbp_ref_rates"

    valid_from: Mapped[dt.date] = mapped_column(Date, primary_key=True)
    rate: Mapped[Decimal] = mapped_column(REF_RATE)
