"""catalog_additions: tickers added to the simulator's catalog belong to the user who added them

Revision ID: 0018
Revises: 0017
Create Date: 2026-10-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "catalog_additions",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("instrument_id", sa.Integer(), sa.ForeignKey("instruments.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("user_id", "instrument_id", name="uq_catalog_additions_user_instrument"),
    )
    op.create_index("ix_catalog_additions_user_id", "catalog_additions", ["user_id"])
    op.create_index("ix_catalog_additions_instrument_id", "catalog_additions", ["instrument_id"])
    # Who added a ticker before was not recorded, and every user saw it: keep it so for the users there are now.
    op.execute("""
        INSERT INTO catalog_additions (user_id, instrument_id)
        SELECT users.id, instruments.id FROM users CROSS JOIN instruments
        WHERE instruments.in_catalog AND instruments.catalog_group = 'Dodane przez Ciebie'
    """)


def downgrade() -> None:
    op.drop_table("catalog_additions")
