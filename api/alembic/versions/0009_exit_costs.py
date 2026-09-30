"""exit costs: daily_valuations.exit_cost_pln and a manual spread per instrument; recompute every history

Revision ID: 0009
Revises: 0008
Create Date: 2026-09-30

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("daily_valuations",
                  sa.Column("exit_cost_pln", sa.Numeric(20, 4), server_default="0", nullable=False))
    op.add_column("instruments", sa.Column("spread_pct", sa.Numeric(6, 4), nullable=True))
    op.create_check_constraint(op.f("ck_instruments_spread_pct_range"), "instruments",
                               "spread_pct IS NULL OR (spread_pct >= 0 AND spread_pct <= 5)")
    # Every stored history was valued without exit costs: the worker rebuilds it from the first day.
    op.execute("UPDATE users SET valuations_stale_from = DATE '0001-01-01' "
               "WHERE id IN (SELECT DISTINCT user_id FROM daily_valuations)")


def downgrade() -> None:
    op.drop_constraint(op.f("ck_instruments_spread_pct_range"), "instruments", type_="check")
    op.drop_column("instruments", "spread_pct")
    op.drop_column("daily_valuations", "exit_cost_pln")
