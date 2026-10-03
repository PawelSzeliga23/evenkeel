"""theses and journal_entries: the owner's notes on holdings and the portfolio (plan 7f-2)

Revision ID: 0015
Revises: 0014
Create Date: 2026-10-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0015"
down_revision: str | None = "0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def _targets(table: str) -> list[sa.schema.SchemaItem]:
    return [
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f(f"fk_{table}_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"],
                                name=op.f(f"fk_{table}_instrument_id_instruments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bond_series"], ["bond_series.series"],
                                name=op.f(f"fk_{table}_bond_series_bond_series"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f(f"fk_{table}_account_id_accounts"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f(f"pk_{table}")),
    ]


def upgrade() -> None:
    op.create_table(
        "theses",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("bond_series", sa.String(10), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("num_nonnulls(instrument_id, bond_series, account_id) = 1",
                           name=op.f("ck_theses_one_target")),
        *_targets("theses"),
    )
    op.create_index(op.f("ix_theses_user_id"), "theses", ["user_id"])
    op.create_index(op.f("ix_theses_account_id"), "theses", ["account_id"])
    op.create_index("uq_theses_target", "theses", ["user_id", "instrument_id", "bond_series", "account_id"],
                    unique=True, postgresql_nulls_not_distinct=True)
    op.create_table(
        "journal_entries",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("bond_series", sa.String(10), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("num_nonnulls(instrument_id, bond_series, account_id) <= 1",
                           name=op.f("ck_journal_entries_one_target")),
        *_targets("journal_entries"),
    )
    op.create_index("ix_journal_entries_user_id_entry_date", "journal_entries", ["user_id", "entry_date"])
    op.create_index(op.f("ix_journal_entries_account_id"), "journal_entries", ["account_id"])


def downgrade() -> None:
    op.drop_table("journal_entries")
    op.drop_table("theses")
