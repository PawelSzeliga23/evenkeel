"""The owner's notes (plan 7f-2): one thesis per holding, and dated journal entries about a holding or the portfolio.

A holding is an instrument, a bond series or a savings account (`account_id`), shared across accounts."""
import datetime as dt

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Thesis(Base):
    __tablename__ = "theses"
    __table_args__ = (
        CheckConstraint("num_nonnulls(instrument_id, bond_series, account_id) = 1", name="one_target"),
        Index("uq_theses_target", "user_id", "instrument_id", "bond_series", "account_id",
              unique=True, postgresql_nulls_not_distinct=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    bond_series: Mapped[str | None] = mapped_column(ForeignKey("bond_series.series", ondelete="CASCADE"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    body: Mapped[str] = mapped_column(Text)
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                    onupdate=func.now())


class JournalEntry(Base):
    """No holding at all = an entry about the whole portfolio."""

    __tablename__ = "journal_entries"
    __table_args__ = (
        CheckConstraint("num_nonnulls(instrument_id, bond_series, account_id) <= 1", name="one_target"),
        Index("ix_journal_entries_user_id_entry_date", "user_id", "entry_date"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    entry_date: Mapped[dt.date] = mapped_column(Date)
    body: Mapped[str] = mapped_column(Text)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    bond_series: Mapped[str | None] = mapped_column(ForeignKey("bond_series.series", ondelete="CASCADE"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                    onupdate=func.now())
