"""The owner's tags (plan 7f-1): on a holding everywhere, on a holding on one account, or on a savings account."""
from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class Tag(Base):
    __tablename__ = "tags"
    __table_args__ = (UniqueConstraint("user_id", "name"),)  # case-insensitive uniqueness is checked by the API

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(30))
    color: Mapped[str] = mapped_column(String(7))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class TagLink(Base):
    """`instrument_id` or `bond_series`: the holding; with `account_id` only on that account. `account_id` alone:
    a savings account."""

    __tablename__ = "tag_links"
    __table_args__ = (
        CheckConstraint("num_nonnulls(instrument_id, bond_series) <= 1", name="one_holding"),
        CheckConstraint("num_nonnulls(instrument_id, bond_series, account_id) >= 1", name="has_target"),
        Index("uq_tag_links_target", "tag_id", "instrument_id", "bond_series", "account_id",
              unique=True, postgresql_nulls_not_distinct=True),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    tag_id: Mapped[int] = mapped_column(ForeignKey("tags.id", ondelete="CASCADE"), index=True)
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"))
    bond_series: Mapped[str | None] = mapped_column(ForeignKey("bond_series.series", ondelete="CASCADE"))
    account_id: Mapped[int | None] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
