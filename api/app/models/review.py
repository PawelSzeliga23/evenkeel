"""Claude's reviews of the portfolio, pasted back by their owner (spec 2026-10-02 §3)."""
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base


class AiReview(Base):
    __tablename__ = "ai_reviews"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    account_ids: Mapped[list[Any]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))  # [] = whole portfolio
    account_label: Mapped[str] = mapped_column(String(300))
    content: Mapped[str] = mapped_column(Text)
    sections: Mapped[int] = mapped_column(Integer)
