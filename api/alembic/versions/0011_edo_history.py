"""EDO issues since 2016 (plan 7b simulator): first-year rate, margin and fee from the issuer's series pages

Revision ID: 0011
Revises: 0010
Create Date: 2026-10-01

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

from app.bonds.edo_history import edo_issues

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    insert = sa.text(
        "INSERT INTO bond_series (series, bond_type, issue_month, maturity_months, first_period_rate, margin, "
        "early_redemption_fee, interest_mode, rate_basis) VALUES (:series, 'EDO', :issue_month, 120, :rate, "
        ":margin, :fee, 'capitalized', 'cpi') ON CONFLICT (series) DO NOTHING"
    )
    for issue in edo_issues():
        op.execute(insert.bindparams(series=issue.series, issue_month=issue.issue_month,
                                     rate=issue.first_period_rate, margin=issue.margin,
                                     fee=issue.early_redemption_fee))


def downgrade() -> None:
    # Series someone holds stay (and so may rows the user entered by hand under the same names).
    delete = sa.text("DELETE FROM bond_series WHERE series = :series "
                     "AND NOT EXISTS (SELECT 1 FROM bond_holdings h WHERE h.series = bond_series.series)")
    for issue in edo_issues():
        op.execute(delete.bindparams(series=issue.series))
