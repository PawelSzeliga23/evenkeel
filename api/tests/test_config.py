import pytest
from pydantic import ValidationError

from app.config import Settings

# Every field passed explicitly so these tests never depend on the host's environment
# or a stray .env file.
_BASE = {
    "database_url": "postgresql+psycopg://portfolio:portfolio@localhost:5433/portfolio_test",
    "access_token_minutes": 15,
    "refresh_token_days": 30,
    "registration_mode": "open",
    "invite_codes": "",
    "login_rate_limit_per_minute": 10,
    "register_rate_limit_per_minute": 5,
}

_DEV_DEFAULT_SECRET = "dev-only-insecure-secret-change-me-0123456789"
_SHORT_SECRET = "too-short-secret"  # < 32 bytes
_STRONG_SECRET = "a-unique-and-sufficiently-long-secret-1234"  # >= 32 bytes

assert len(_STRONG_SECRET.encode()) >= 32
assert len(_SHORT_SECRET.encode()) < 32


def test_default_secret_with_cookie_secure_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(**_BASE, cookie_secure=True, jwt_secret=_DEV_DEFAULT_SECRET)


def test_short_secret_with_cookie_secure_is_rejected() -> None:
    with pytest.raises(ValidationError):
        Settings(**_BASE, cookie_secure=True, jwt_secret=_SHORT_SECRET)


def test_strong_custom_secret_with_cookie_secure_is_accepted() -> None:
    Settings(**_BASE, cookie_secure=True, jwt_secret=_STRONG_SECRET)


def test_default_secret_is_accepted_in_local_dev() -> None:
    Settings(**_BASE, cookie_secure=False, jwt_secret=_DEV_DEFAULT_SECRET)
