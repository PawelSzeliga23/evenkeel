"""bonds and savings: bond series (seed EDO0936), holdings, savings accounts, daily valuation components

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-28

"""
import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(20, 4)
PERCENT = sa.Numeric(7, 4)
OLD_UNIQUE = "uq_daily_valuations_account_id_instrument_id_date"
NEW_UNIQUE = "uq_daily_valuations_component_date"
BOND_TYPES = "bond_type IN ('OTS', 'ROR', 'DOR', 'DOS', 'TOS', 'COI', 'EDO', 'ROS', 'ROD')"
# obligacjeskarbowe.pl, oferta wrzesień 2026 (list emisyjny EDO0936): 5,35 % w 1. roku, potem inflacja + 2,00 %.
SERIES = [{"series": "EDO0936", "bond_type": "EDO", "issue_month": dt.date(2026, 9, 1), "maturity_months": 120,
           "first_period_rate": Decimal("5.35"), "margin": Decimal("2.00"), "early_redemption_fee": Decimal("3.00"),
           "interest_mode": "capitalized", "rate_basis": "cpi"}]


def upgrade() -> None:
    series = op.create_table(
        "bond_series",
        sa.Column("series", sa.String(length=10), nullable=False),
        sa.Column("bond_type", sa.String(length=3), nullable=False),
        sa.Column("issue_month", sa.Date(), nullable=False),
        sa.Column("maturity_months", sa.Integer(), nullable=False),
        sa.Column("first_period_rate", PERCENT, nullable=False),
        sa.Column("margin", PERCENT, nullable=False),
        sa.Column("early_redemption_fee", sa.Numeric(6, 2), nullable=False),
        sa.Column("interest_mode", sa.String(length=20), nullable=False),
        sa.Column("rate_basis", sa.String(length=10), nullable=False),
        sa.CheckConstraint(BOND_TYPES, name=op.f("ck_bond_series_bond_type")),
        sa.CheckConstraint(
            "interest_mode IN ('capitalized', 'paid_annually', 'paid_monthly', 'fixed_at_maturity')",
            name=op.f("ck_bond_series_interest_mode"),
        ),
        sa.CheckConstraint("rate_basis IN ('fixed', 'cpi', 'nbp_ref')", name=op.f("ck_bond_series_rate_basis")),
        sa.PrimaryKeyConstraint("series", name=op.f("pk_bond_series")),
    )
    op.bulk_insert(series, SERIES)
    op.create_table(
        "bond_holdings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("bond_type", sa.String(length=3), nullable=False),
        sa.Column("series", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("redeemed_at", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint(BOND_TYPES, name=op.f("ck_bond_holdings_bond_type")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_bond_holdings_quantity_positive")),
        sa.CheckConstraint(
            "redeemed_at IS NULL OR redeemed_at >= purchase_date", name=op.f("ck_bond_holdings_redeemed_after_purchase")
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_bond_holdings_account_id_accounts"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series"], ["bond_series.series"], name=op.f("fk_bond_holdings_series_bond_series")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bond_holdings")),
    )
    op.create_index(op.f("ix_bond_holdings_account_id"), "bond_holdings", ["account_id"])
    op.create_table(
        "savings_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("capitalization", sa.String(length=10), nullable=False),
        sa.CheckConstraint("capitalization IN ('daily', 'monthly', 'quarterly')",
                           name=op.f("ck_savings_accounts_capitalization")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_savings_accounts_account_id_accounts"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_savings_accounts")),
        sa.UniqueConstraint("account_id", name=op.f("uq_savings_accounts_account_id")),
    )
    op.create_table(
        "savings_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("savings_account_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("annual_rate", PERCENT, nullable=False),
        sa.CheckConstraint("annual_rate >= 0", name=op.f("ck_savings_rates_rate_not_negative")),
        sa.ForeignKeyConstraint(["savings_account_id"], ["savings_accounts.id"],
                                name=op.f("fk_savings_rates_savings_account_id_savings_accounts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_savings_rates")),
        sa.UniqueConstraint("savings_account_id", "valid_from",
                            name=op.f("uq_savings_rates_savings_account_id_valid_from")),
    )
    op.create_table(
        "savings_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("savings_account_id", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("balance", MONEY, nullable=False),
        sa.CheckConstraint("balance >= 0", name=op.f("ck_savings_balances_balance_not_negative")),
        sa.ForeignKeyConstraint(["savings_account_id"], ["savings_accounts.id"],
                                name=op.f("fk_savings_balances_savings_account_id_savings_accounts"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_savings_balances")),
        sa.UniqueConstraint("savings_account_id", "as_of_date",
                            name=op.f("uq_savings_balances_savings_account_id_as_of_date")),
    )
    op.add_column("daily_valuations", sa.Column("bond_holding_id", sa.Integer(), nullable=True))
    op.add_column("daily_valuations", sa.Column("savings_account_id", sa.Integer(), nullable=True))
    op.create_foreign_key(op.f("fk_daily_valuations_bond_holding_id_bond_holdings"), "daily_valuations",
                          "bond_holdings", ["bond_holding_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key(op.f("fk_daily_valuations_savings_account_id_savings_accounts"), "daily_valuations",
                          "savings_accounts", ["savings_account_id"], ["id"], ondelete="CASCADE")
    op.drop_index(OLD_UNIQUE, table_name="daily_valuations")
    op.create_index(NEW_UNIQUE, "daily_valuations",
                    ["account_id", "instrument_id", "bond_holding_id", "savings_account_id", "date"],
                    unique=True, postgresql_nulls_not_distinct=True)
    op.create_check_constraint(op.f("ck_daily_valuations_one_component"), "daily_valuations",
                               "num_nonnulls(instrument_id, bond_holding_id, savings_account_id) <= 1")


def downgrade() -> None:
    op.execute("DELETE FROM daily_valuations WHERE bond_holding_id IS NOT NULL OR savings_account_id IS NOT NULL")
    op.drop_constraint(op.f("ck_daily_valuations_one_component"), "daily_valuations", type_="check")
    op.drop_index(NEW_UNIQUE, table_name="daily_valuations")
    op.create_index(OLD_UNIQUE, "daily_valuations", ["account_id", "instrument_id", "date"],
                    unique=True, postgresql_nulls_not_distinct=True)
    op.drop_constraint(op.f("fk_daily_valuations_savings_account_id_savings_accounts"), "daily_valuations",
                       type_="foreignkey")
    op.drop_constraint(op.f("fk_daily_valuations_bond_holding_id_bond_holdings"), "daily_valuations",
                       type_="foreignkey")
    op.drop_column("daily_valuations", "savings_account_id")
    op.drop_column("daily_valuations", "bond_holding_id")
    op.drop_table("savings_balances")
    op.drop_table("savings_rates")
    op.drop_table("savings_accounts")
    op.drop_index(op.f("ix_bond_holdings_account_id"), table_name="bond_holdings")
    op.drop_table("bond_holdings")
    op.drop_table("bond_series")
