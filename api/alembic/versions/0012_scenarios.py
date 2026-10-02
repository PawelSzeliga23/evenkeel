"""scenarios: saved what-if scenarios of the simulator (plan 7b-2)

Revision ID: 0012
Revises: 0011
Create Date: 2026-10-02

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "scenarios",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(80), nullable=False),
        sa.Column("base", sa.String(10), nullable=False),
        sa.Column("allocation", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("steps", postgresql.JSONB(), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("base IN ('portfolio', 'deposits')", name=op.f("ck_scenarios_base")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_scenarios_user_id_users"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_scenarios")),
    )
    op.create_index(op.f("ix_scenarios_user_id"), "scenarios", ["user_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_scenarios_user_id"), table_name="scenarios")
    op.drop_table("scenarios")
