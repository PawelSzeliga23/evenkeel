"""instrument catalog for the 7b simulator: catalog columns and the starter list

Revision ID: 0010
Revises: 0009
Create Date: 2026-10-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.catalog.seed import catalog_rows

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("instruments", sa.Column("in_catalog", sa.Boolean(), server_default=sa.false(), nullable=False))
    op.add_column("instruments", sa.Column("catalog_group", sa.String(40), nullable=True))
    op.add_column("instruments", sa.Column("accumulating", sa.Boolean(), nullable=True))
    # Rows this migration inserts are remembered so the downgrade removes only them (an instrument the user
    # already had stays, only losing its catalog flags with the columns).
    op.add_column("instruments", sa.Column("catalog_seeded", sa.Boolean(), server_default=sa.false(), nullable=False))
    upsert = sa.text(
        "INSERT INTO instruments (xtb_ticker, name, category, currency, in_catalog, catalog_group, accumulating, "
        "catalog_seeded) VALUES (:ticker, :name, :category, :currency, true, :group, :accumulating, true) "
        "ON CONFLICT (xtb_ticker) DO UPDATE SET in_catalog = true, catalog_group = EXCLUDED.catalog_group, "
        "accumulating = EXCLUDED.accumulating"
    )
    for row in catalog_rows():
        op.execute(upsert.bindparams(ticker=row.xtb_ticker, name=row.name, category=row.category,
                                     currency=row.currency, group=row.catalog_group, accumulating=row.accumulating))


def downgrade() -> None:
    unused = ("catalog_seeded AND NOT EXISTS (SELECT 1 FROM transactions t WHERE t.instrument_id = instruments.id) "
              "AND NOT EXISTS (SELECT 1 FROM position_lots l WHERE l.instrument_id = instruments.id) "
              "AND NOT EXISTS (SELECT 1 FROM corporate_actions c WHERE c.instrument_id = instruments.id "
              "OR c.target_instrument_id = instruments.id) "
              "AND NOT EXISTS (SELECT 1 FROM xtb_snapshots x WHERE x.instrument_id = instruments.id) "
              "AND NOT EXISTS (SELECT 1 FROM daily_valuations d WHERE d.instrument_id = instruments.id)")
    op.execute(f"DELETE FROM prices WHERE instrument_id IN (SELECT id FROM instruments WHERE {unused})")
    op.execute(f"DELETE FROM instruments WHERE {unused}")
    for column in ("catalog_seeded", "accumulating", "catalog_group", "in_catalog"):
        op.drop_column("instruments", column)
