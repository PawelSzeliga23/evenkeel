"""users.preferences: the owner's start screen and default views (plan 8a)

Revision ID: 0016
Revises: 0015
Create Date: 2026-10-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("users", sa.Column("preferences", postgresql.JSONB(), server_default=sa.text("'{}'::jsonb"),
                                     nullable=False))


def downgrade() -> None:
    op.drop_column("users", "preferences")
