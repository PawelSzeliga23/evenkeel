import datetime as dt

from sqlalchemy import delete, or_
from sqlalchemy.orm import Session

from app.models import RefreshToken

REFRESH_TOKEN_RETENTION = dt.timedelta(days=30)


def prune_refresh_tokens(db: Session, now: dt.datetime) -> int:
    """Deletes refresh tokens that expired or were revoked more than 30 days ago. Does not commit.

    Recently revoked tokens are kept on purpose: reuse detection needs them to spot a stolen cookie.
    """
    cutoff = now - REFRESH_TOKEN_RETENTION
    result = db.execute(
        delete(RefreshToken).where(or_(RefreshToken.expires_at < cutoff, RefreshToken.revoked_at < cutoff))
    )
    return result.rowcount
