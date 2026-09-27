"""valuation: corporate actions, daily valuations cache, stale marker, provider split sync

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(20, 4)
QUANTITY = sa.Numeric(24, 8)
RATIO = sa.Numeric(18, 8)


def upgrade() -> None:
    op.add_column("users", sa.Column("valuations_stale_from", sa.Date(), nullable=True))
    # Existing instruments were fetched without split events: false makes the next update refetch them in full
    # once. New instruments get their full history on first sight anyway, hence the default true afterwards.
    op.add_column("instruments", sa.Column("splits_synced", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.alter_column("instruments", "splits_synced", server_default=sa.text("true"))
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("ratio_from", RATIO, nullable=False),
        sa.Column("ratio_to", RATIO, nullable=False),
        sa.Column("target_instrument_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.CheckConstraint("type IN ('split', 'reverse_split', 'conversion')", name=op.f("ck_corporate_actions_type")),
        sa.CheckConstraint("source IN ('manual', 'xtb', 'provider')", name=op.f("ck_corporate_actions_source")),
        sa.CheckConstraint("ratio_from > 0 AND ratio_to > 0", name=op.f("ck_corporate_actions_ratio_positive")),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"],
            name=op.f("fk_corporate_actions_instrument_id_instruments"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_instrument_id"], ["instruments.id"],
            name=op.f("fk_corporate_actions_target_instrument_id_instruments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corporate_actions")),
        sa.UniqueConstraint(
            "instrument_id", "type", "effective_date", "source",
            name=op.f("uq_corporate_actions_instrument_id_type_effective_date_source"),
        ),
    )
    op.create_index(op.f("ix_corporate_actions_instrument_id"), "corporate_actions", ["instrument_id"])
    op.create_table(
        "daily_valuations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=True),
        sa.Column("value_pln", MONEY, nullable=False),
        sa.Column("cost_pln", MONEY, nullable=False),
        sa.Column("net_flow_pln", MONEY, nullable=False),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_daily_valuations_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_daily_valuations_account_id_accounts"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], name=op.f("fk_daily_valuations_instrument_id_instruments")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_valuations")),
    )
    op.create_index(
        "uq_daily_valuations_account_id_instrument_id_date", "daily_valuations", ["account_id", "instrument_id", "date"],
        unique=True, postgresql_nulls_not_distinct=True,
    )
    op.create_index("ix_daily_valuations_user_id_date", "daily_valuations", ["user_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_daily_valuations_user_id_date", table_name="daily_valuations")
    op.drop_index("uq_daily_valuations_account_id_instrument_id_date", table_name="daily_valuations")
    op.drop_table("daily_valuations")
    op.drop_index(op.f("ix_corporate_actions_instrument_id"), table_name="corporate_actions")
    op.drop_table("corporate_actions")
    op.drop_column("instruments", "splits_synced")
    op.drop_column("users", "valuations_stale_from")
