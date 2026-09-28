"""valuation extensions: private manual corporate actions, suppress, IKE/IKZE limits

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-28

"""
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(20, 4)
UNIQUE_ACTION = "uq_ca_inst_ed_src_usr"
OLD_UNIQUE_ACTION = "uq_corporate_actions_instrument_id_type_effective_date_source"
# Obwieszczenie Ministra Rodziny, Pracy i Polityki Społecznej z 17.11.2025 (M.P. 2025 poz. 1202).
WRAPPER_LIMITS = [{"year": 2026, "wrapper": "ike", "limit_pln": Decimal("28260")}]


def upgrade() -> None:
    op.add_column("corporate_actions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_corporate_actions_user_id_users"), "corporate_actions", "users", ["user_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_corporate_actions_user_id"), "corporate_actions", ["user_id"])
    # Manual entries had neither an API nor an owner before this revision: none can be attributed, none are kept.
    op.execute("DELETE FROM corporate_actions WHERE source = 'manual'")
    op.drop_constraint(op.f(OLD_UNIQUE_ACTION), "corporate_actions", type_="unique")
    op.create_index(
        UNIQUE_ACTION, "corporate_actions", ["instrument_id", "effective_date", "source", "user_id"],
        unique=True, postgresql_nulls_not_distinct=True,
    )
    op.drop_constraint(op.f("ck_corporate_actions_type"), "corporate_actions", type_="check")
    op.create_check_constraint(
        op.f("ck_corporate_actions_type"), "corporate_actions",
        "type IN ('split', 'reverse_split', 'conversion', 'suppress')",
    )
    op.create_check_constraint(
        op.f("ck_corporate_actions_manual_has_user"), "corporate_actions", "(source = 'manual') = (user_id IS NOT NULL)"
    )
    op.create_check_constraint(
        op.f("ck_corporate_actions_conversion_has_target"), "corporate_actions",
        "(type = 'conversion') = (target_instrument_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_corporate_actions_target_differs"), "corporate_actions", "target_instrument_id <> instrument_id"
    )
    limits = op.create_table(
        "wrapper_limits",
        sa.Column("year", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("wrapper", sa.String(length=20), nullable=False),
        sa.Column("limit_pln", MONEY, nullable=False),
        sa.CheckConstraint("wrapper IN ('ike', 'ikze', 'ikze_self_employed')", name=op.f("ck_wrapper_limits_wrapper")),
        sa.PrimaryKeyConstraint("year", "wrapper", name=op.f("pk_wrapper_limits")),
    )
    op.bulk_insert(limits, WRAPPER_LIMITS)


def downgrade() -> None:
    op.drop_table("wrapper_limits")
    for name in ("target_differs", "conversion_has_target", "manual_has_user", "type"):
        op.drop_constraint(op.f(f"ck_corporate_actions_{name}"), "corporate_actions", type_="check")
    op.execute("DELETE FROM corporate_actions WHERE source = 'manual' OR type = 'suppress'")
    op.create_check_constraint(
        op.f("ck_corporate_actions_type"), "corporate_actions", "type IN ('split', 'reverse_split', 'conversion')"
    )
    op.drop_index(UNIQUE_ACTION, table_name="corporate_actions")
    op.create_unique_constraint(
        op.f(OLD_UNIQUE_ACTION), "corporate_actions", ["instrument_id", "type", "effective_date", "source"]
    )
    op.drop_index(op.f("ix_corporate_actions_user_id"), table_name="corporate_actions")
    op.drop_constraint(op.f("fk_corporate_actions_user_id_users"), "corporate_actions", type_="foreignkey")
    op.drop_column("corporate_actions", "user_id")
