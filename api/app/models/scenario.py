"""Saved what-if scenarios of the simulator (plan 7b): a starting point and building blocks, owned by one user."""
from datetime import datetime
from typing import Any

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base

SCENARIO_BASES = ("portfolio", "deposits")


class Scenario(Base):
    """`allocation` and `steps` hold the validated `ScenarioIn` lists as JSON (app/scenarios/schemas.py)."""

    __tablename__ = "scenarios"
    __table_args__ = (CheckConstraint("base IN ('portfolio', 'deposits')", name="base"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80))
    base: Mapped[str] = mapped_column(String(10))
    allocation: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    steps: Mapped[list[dict[str, Any]]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(),
                                                 onupdate=func.now())
