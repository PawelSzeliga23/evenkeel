"""IKE / IKZE statutory limits for 2023-2026

Revision ID: 0008
Revises: 0007
Create Date: 2026-09-29

"""
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Obwieszczenia MRPiPS o limitach wpłat na IKE/IKZE (IKE: 3 × przeciętne wynagrodzenie; IKZE: 1,2 ×,
# samozatrudnieni 1,8 ×). IKE 2026 dodaje migracja 0005.
LIMITS = [
    (2023, "ike", Decimal("20805")), (2023, "ikze", Decimal("8322")), (2023, "ikze_self_employed", Decimal("12483")),
    (2024, "ike", Decimal("23472")), (2024, "ikze", Decimal("9388.80")),
    (2024, "ikze_self_employed", Decimal("14083.20")),
    (2025, "ike", Decimal("26019")), (2025, "ikze", Decimal("10407.60")),
    (2025, "ikze_self_employed", Decimal("15611.40")),
    (2026, "ikze", Decimal("11304")), (2026, "ikze_self_employed", Decimal("16956")),
]


def upgrade() -> None:
    insert = sa.text(
        "INSERT INTO wrapper_limits (year, wrapper, limit_pln) VALUES (:year, :wrapper, :limit_pln) "
        "ON CONFLICT (year, wrapper) DO NOTHING"
    )
    for year, wrapper, limit_pln in LIMITS:
        op.execute(insert.bindparams(year=year, wrapper=wrapper, limit_pln=limit_pln))


def downgrade() -> None:
    delete = sa.text("DELETE FROM wrapper_limits WHERE year = :year AND wrapper = :wrapper")
    for year, wrapper, _ in LIMITS:
        op.execute(delete.bindparams(year=year, wrapper=wrapper))
