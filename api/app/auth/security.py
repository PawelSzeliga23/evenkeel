import hashlib
import secrets
from datetime import UTC, datetime, timedelta

import jwt
from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from app.config import Settings
from app.errors import ApiError

ALGORITHM = "HS256"
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    try:
        return _hasher.verify(password_hash, password)
    except (VerificationError, InvalidHashError):
        return False


def invalid_token() -> ApiError:
    return ApiError(401, "invalid_token", "Sesja wygasła lub jest nieprawidłowa. Zaloguj się ponownie.")


def create_access_token(user_id: int, settings: Settings, now: datetime | None = None) -> str:
    now = now or datetime.now(UTC)
    payload = {
        "sub": str(user_id),
        "type": "access",
        "iat": now,
        "exp": now + timedelta(minutes=settings.access_token_minutes),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM)


def decode_access_token(token: str, settings: Settings) -> int:
    try:
        payload = jwt.decode(
            token, settings.jwt_secret, algorithms=[ALGORITHM], options={"require": ["exp", "sub"]}
        )
    except jwt.InvalidTokenError as exc:
        raise invalid_token() from exc
    if payload.get("type") != "access":
        raise invalid_token()
    try:
        user_id = int(payload["sub"])
    except (TypeError, ValueError) as exc:
        raise invalid_token() from exc
    if not (1 <= user_id <= 2**31 - 1):
        raise invalid_token()
    return user_id


def hash_refresh_token(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()


def new_refresh_token() -> tuple[str, str]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)
