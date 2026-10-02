"""tags and tag_links: the owner's tags on holdings, bond series and savings accounts (plan 7f-1)

Revision ID: 0014
Revises: 0013
Create Date: 2026-10-03

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "tags",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(30), nullable=False),
        sa.Column("color", sa.String(7), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_tags_user_id_users"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tags")),
        sa.UniqueConstraint("user_id", "name", name=op.f("uq_tags_user_id_name")),
    )
    op.create_index(op.f("ix_tags_user_id"), "tags", ["user_id"])
    op.create_table(
        "tag_links",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("tag_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("bond_series", sa.String(10), nullable=True),
        sa.Column("account_id", sa.Integer(), nullable=True),
        sa.CheckConstraint("num_nonnulls(instrument_id, bond_series) <= 1", name=op.f("ck_tag_links_one_holding")),
        sa.CheckConstraint("num_nonnulls(instrument_id, bond_series, account_id) >= 1",
                           name=op.f("ck_tag_links_has_target")),
        sa.ForeignKeyConstraint(["tag_id"], ["tags.id"], name=op.f("fk_tag_links_tag_id_tags"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"],
                                name=op.f("fk_tag_links_instrument_id_instruments"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["bond_series"], ["bond_series.series"],
                                name=op.f("fk_tag_links_bond_series_bond_series"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_tag_links_account_id_accounts"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_tag_links")),
    )
    op.create_index(op.f("ix_tag_links_tag_id"), "tag_links", ["tag_id"])
    op.create_index(op.f("ix_tag_links_account_id"), "tag_links", ["account_id"])
    op.create_index("uq_tag_links_target", "tag_links", ["tag_id", "instrument_id", "bond_series", "account_id"],
                    unique=True, postgresql_nulls_not_distinct=True)


def downgrade() -> None:
    op.drop_table("tag_links")
    op.drop_table("tags")
