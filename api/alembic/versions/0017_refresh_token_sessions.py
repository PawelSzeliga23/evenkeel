"""refresh_tokens: a session number carried across rotations, the browser and when the session began (plan 8d)

Revision ID: 0017
Revises: 0016
Create Date: 2026-10-04

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # Tokens issued before: each its own session, of an unknown device, begun when the token was issued.
    op.add_column("refresh_tokens", sa.Column("session_id", postgresql.UUID(as_uuid=True),
                                              server_default=sa.text("gen_random_uuid()"), nullable=False))
    op.alter_column("refresh_tokens", "session_id", server_default=None)
    op.add_column("refresh_tokens", sa.Column("user_agent", sa.String(300), nullable=True))
    op.add_column("refresh_tokens", sa.Column("session_started_at", sa.DateTime(timezone=True), nullable=True))
    op.execute("UPDATE refresh_tokens SET session_started_at = created_at")
    op.alter_column("refresh_tokens", "session_started_at", nullable=False)
    op.create_index("ix_refresh_tokens_session_id", "refresh_tokens", ["session_id"])


def downgrade() -> None:
    op.drop_index("ix_refresh_tokens_session_id", table_name="refresh_tokens")
    op.drop_column("refresh_tokens", "session_started_at")
    op.drop_column("refresh_tokens", "user_agent")
    op.drop_column("refresh_tokens", "session_id")
