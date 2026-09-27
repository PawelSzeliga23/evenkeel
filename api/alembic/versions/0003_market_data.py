"""market data: prices, fx rates, cpi, nbp reference rates; instrument price status

Revision ID: 0003
Revises: 0002
Create Date: 2026-09-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

PRICE = sa.Numeric(24, 8)
RATE = sa.Numeric(18, 8)


def upgrade() -> None:
    op.add_column("instruments", sa.Column("price_checked_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("instruments", sa.Column("price_error", sa.String(length=200), nullable=True))
    op.create_table(
        "prices",
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("close", PRICE, nullable=False),
        sa.Column("adj_close", PRICE, nullable=True),
        sa.Column("source", sa.String(length=20), nullable=False),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"], name=op.f("fk_prices_instrument_id_instruments"), ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("instrument_id", "date", name=op.f("pk_prices")),
    )
    op.create_table(
        "fx_rates",
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("rate_pln", RATE, nullable=False),
        sa.PrimaryKeyConstraint("currency", "date", name=op.f("pk_fx_rates")),
    )
    op.create_table(
        "cpi",
        sa.Column("year_month", sa.Date(), nullable=False),
        sa.Column("yoy", sa.Numeric(8, 2), nullable=False),
        sa.PrimaryKeyConstraint("year_month", name=op.f("pk_cpi")),
    )
    op.create_table(
        "nbp_ref_rates",
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("rate", sa.Numeric(6, 2), nullable=False),
        sa.PrimaryKeyConstraint("valid_from", name=op.f("pk_nbp_ref_rates")),
    )


def downgrade() -> None:
    op.drop_table("nbp_ref_rates")
    op.drop_table("cpi")
    op.drop_table("fx_rates")
    op.drop_table("prices")
    op.drop_column("instruments", "price_error")
    op.drop_column("instruments", "price_checked_at")
