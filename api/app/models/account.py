from datetime import datetime

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

ACCOUNT_KINDS = ("broker", "bonds", "savings", "cash")
WRAPPERS = ("regular", "ike", "ikze")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        UniqueConstraint("user_id", "broker", "external_account_number"),
        CheckConstraint(_in_list("kind", ACCOUNT_KINDS), name="kind"),
        CheckConstraint(_in_list("wrapper", WRAPPERS), name="wrapper"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(100))
    kind: Mapped[str] = mapped_column(String(20))
    wrapper: Mapped[str] = mapped_column(String(10), server_default="regular")
    broker: Mapped[str | None] = mapped_column(String(20))
    external_account_number: Mapped[str | None] = mapped_column(String(50))
    currency: Mapped[str] = mapped_column(String(3), server_default="PLN")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
