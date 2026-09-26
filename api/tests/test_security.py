from datetime import UTC, datetime, timedelta

import jwt
import pytest

from app.auth.security import (
    create_access_token,
    decode_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.config import Settings
from app.errors import ApiError


def test_password_hash_roundtrip() -> None:
    password_hash = hash_password("bardzo-tajne-haslo")

    assert password_hash != "bardzo-tajne-haslo"
    assert verify_password(password_hash, "bardzo-tajne-haslo")
    assert not verify_password(password_hash, "inne-haslo-123")


def test_verify_password_returns_false_for_malformed_hash() -> None:
    assert not verify_password("to-nie-jest-hash", "cokolwiek")


def test_access_token_roundtrip(settings: Settings) -> None:
    assert decode_access_token(create_access_token(42, settings), settings) == 42


def _assert_invalid(token: str, settings: Settings) -> None:
    with pytest.raises(ApiError) as exc_info:
        decode_access_token(token, settings)
    assert exc_info.value.status_code == 401
    assert exc_info.value.code == "invalid_token"


def test_expired_access_token_is_rejected(settings: Settings) -> None:
    issued = datetime.now(UTC) - timedelta(minutes=settings.access_token_minutes + 1)
    _assert_invalid(create_access_token(42, settings, now=issued), settings)


def test_token_signed_with_other_secret_is_rejected(settings: Settings) -> None:
    other = settings.model_copy(update={"jwt_secret": "another-secret-that-is-at-least-32-bytes"})
    _assert_invalid(create_access_token(42, other), settings)


def test_token_of_other_type_is_rejected(settings: Settings) -> None:
    token = jwt.encode(
        {"sub": "42", "type": "refresh", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    _assert_invalid(token, settings)


def test_garbage_token_is_rejected(settings: Settings) -> None:
    _assert_invalid("to.nie.jest-jwt", settings)


@pytest.mark.parametrize("sub", ["abc", "99999999999", "0", "-1"])
def test_token_with_invalid_sub_is_rejected(sub: str, settings: Settings) -> None:
    token = jwt.encode(
        {"sub": sub, "type": "access", "exp": datetime.now(UTC) + timedelta(minutes=5)},
        settings.jwt_secret,
        algorithm="HS256",
    )
    _assert_invalid(token, settings)


def test_refresh_token_is_stored_only_as_hash() -> None:
    raw, token_hash = new_refresh_token()

    assert token_hash == hash_refresh_token(raw)
    assert raw != token_hash
    assert len(token_hash) == 64
    assert new_refresh_token()[0] != raw
