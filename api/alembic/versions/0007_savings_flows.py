"""savings flows: deposits and withdrawals on savings accounts

Revision ID: 0007
Revises: 0006
Create Date: 2026-09-29

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0007"
down_revision: str | None = "0006"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(20, 4)


def upgrade() -> None:
    op.create_table(
        "savings_flows",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("savings_account_id", sa.Integer(), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount <> 0", name=op.f("ck_savings_flows_amount_not_zero")),
        sa.ForeignKeyConstraint(["savings_account_id"], ["savings_accounts.id"],
                                name=op.f("fk_savings_flows_savings_account_id_savings_accounts"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_savings_flows")),
    )
    op.create_index(op.f("ix_savings_flows_savings_account_id"), "savings_flows", ["savings_account_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_savings_flows_savings_account_id"), table_name="savings_flows")
    op.drop_table("savings_flows")
