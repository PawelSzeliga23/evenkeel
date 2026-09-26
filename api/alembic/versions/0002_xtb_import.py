"""xtb import: instruments, imports, transactions, position lots, snapshots

Revision ID: 0002
Revises: 0001
Create Date: 2026-09-26

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: str | None = "0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(20, 4)
QUANTITY = sa.Numeric(24, 8)
PRICE = sa.Numeric(24, 8)
RATE = sa.Numeric(18, 8)
TYPES = (
    "'buy', 'sell', 'dividend', 'withholding_tax', 'interest', 'interest_tax', "
    "'deposit', 'withdrawal', 'transfer_in', 'transfer_out', 'fee', 'unknown'"
)


def _created_at() -> sa.Column:
    return sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False)


def upgrade() -> None:
    op.create_table(
        "instruments",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("xtb_ticker", sa.String(length=40), nullable=False),
        sa.Column("name", sa.String(length=200), nullable=False),
        sa.Column("category", sa.String(length=20), nullable=True),
        sa.Column("currency", sa.String(length=3), nullable=True),
        sa.Column("exchange_suffix", sa.String(length=10), nullable=True),
        sa.Column("price_symbol", sa.String(length=40), nullable=True),
        sa.Column("price_symbol_overridden", sa.Boolean(), server_default=sa.text("false"), nullable=False),
        sa.Column("isin", sa.String(length=12), nullable=True),
        _created_at(),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_instruments")),
        sa.UniqueConstraint("xtb_ticker", name=op.f("uq_instruments_xtb_ticker")),
    )
    op.create_table(
        "imports",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("filename", sa.String(length=255), nullable=False),
        sa.Column("file_hash", sa.String(length=64), nullable=False),
        sa.Column("report_from", sa.DateTime(timezone=True), nullable=True),
        sa.Column("report_to", sa.DateTime(timezone=True), nullable=True),
        sa.Column("imported_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("rows_added", sa.Integer(), nullable=False),
        sa.Column("rows_duplicate", sa.Integer(), nullable=False),
        sa.Column("rows_unknown", sa.Integer(), nullable=False),
        sa.Column("warnings", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_imports_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_imports_account_id_accounts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_imports")),
    )
    op.create_index(op.f("ix_imports_user_id"), "imports", ["user_id"])
    op.create_index(op.f("ix_imports_account_id"), "imports", ["account_id"])
    op.create_table(
        "transactions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("xtb_type", sa.String(length=60), nullable=False),
        sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("amount", MONEY, nullable=False),
        sa.Column("currency", sa.String(length=3), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=True),
        sa.Column("price", PRICE, nullable=True),
        sa.Column("implied_fx_rate", RATE, nullable=True),
        sa.Column("xtb_position_id", sa.String(length=40), nullable=True),
        sa.Column("external_id", sa.String(length=64), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        sa.Column("counterparty_account", sa.String(length=50), nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("transfer_pair_id", sa.Integer(), nullable=True),
        sa.Column("import_id", sa.Integer(), nullable=True),
        sa.CheckConstraint(f"type IN ({TYPES})", name=op.f("ck_transactions_type")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_transactions_account_id_accounts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], name=op.f("fk_transactions_instrument_id_instruments")),
        sa.ForeignKeyConstraint(["transfer_pair_id"], ["transactions.id"], name=op.f("fk_transactions_transfer_pair_id_transactions"), ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["import_id"], ["imports.id"], name=op.f("fk_transactions_import_id_imports"), ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_transactions")),
        sa.UniqueConstraint("account_id", "external_id", name=op.f("uq_transactions_account_id_external_id")),
    )
    op.create_index(op.f("ix_transactions_account_id"), "transactions", ["account_id"])
    op.create_table(
        "position_lots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("xtb_position_id", sa.String(length=40), nullable=False),
        sa.Column("side", sa.String(length=10), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=False),
        sa.Column("open_price", PRICE, nullable=False),
        sa.Column("opened_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("open_commission", MONEY, nullable=True),
        sa.Column("swap", MONEY, nullable=True),
        sa.Column("rollover", MONEY, nullable=True),
        sa.Column("margin", MONEY, nullable=True),
        sa.Column("stop_loss", PRICE, nullable=True),
        sa.Column("take_profit", PRICE, nullable=True),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_price", PRICE, nullable=True),
        sa.Column("close_origin", sa.String(length=40), nullable=True),
        sa.Column("open_conversion_rate", RATE, nullable=True),
        sa.Column("close_conversion_rate", RATE, nullable=True),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_position_lots_account_id_accounts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], name=op.f("fk_position_lots_instrument_id_instruments")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_position_lots")),
        sa.UniqueConstraint("account_id", "xtb_position_id", name=op.f("uq_position_lots_account_id_xtb_position_id")),
    )
    op.create_index(op.f("ix_position_lots_account_id"), "position_lots", ["account_id"])
    op.create_table(
        "xtb_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("import_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("xtb_position_id", sa.String(length=40), nullable=True),
        sa.Column("row_kind", sa.String(length=20), nullable=False),
        sa.Column("volume", QUANTITY, nullable=True),
        sa.Column("value", MONEY, nullable=True),
        sa.Column("current_price", PRICE, nullable=True),
        sa.Column("net_profit", MONEY, nullable=True),
        sa.Column("net_profit_pct", sa.Numeric(12, 4), nullable=True),
        sa.Column("gross_profit", MONEY, nullable=True),
        sa.Column("taken_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("raw", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.CheckConstraint("row_kind IN ('instrument_summary', 'lot', 'account_summary')", name=op.f("ck_xtb_snapshots_row_kind")),
        sa.ForeignKeyConstraint(["import_id"], ["imports.id"], name=op.f("fk_xtb_snapshots_import_id_imports"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_xtb_snapshots_account_id_accounts"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], name=op.f("fk_xtb_snapshots_instrument_id_instruments")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_xtb_snapshots")),
    )
    op.create_index(op.f("ix_xtb_snapshots_import_id"), "xtb_snapshots", ["import_id"])
    op.create_index(op.f("ix_xtb_snapshots_account_id"), "xtb_snapshots", ["account_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_xtb_snapshots_account_id"), table_name="xtb_snapshots")
    op.drop_index(op.f("ix_xtb_snapshots_import_id"), table_name="xtb_snapshots")
    op.drop_table("xtb_snapshots")
    op.drop_index(op.f("ix_position_lots_account_id"), table_name="position_lots")
    op.drop_table("position_lots")
    op.drop_index(op.f("ix_transactions_account_id"), table_name="transactions")
    op.drop_table("transactions")
    op.drop_index(op.f("ix_imports_account_id"), table_name="imports")
    op.drop_index(op.f("ix_imports_user_id"), table_name="imports")
    op.drop_table("imports")
    op.drop_table("instruments")
