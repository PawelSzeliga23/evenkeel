import logging
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.schemas import LoginIn, PasswordChangeIn, RegisterIn, TokenOut, UserOut
from app.auth.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.config import Settings, get_settings
from app.db import get_db
from app.errors import ApiError
from app.models import RefreshToken, User
from app.preferences.router import preferences_of
from app.scoping import UserScope

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/auth", tags=["auth"])

REFRESH_COOKIE = "refresh_token"
REFRESH_COOKIE_PATH = "/api/auth"

# Verified against when the e-mail is unknown, so both failure paths cost the same time.
_DUMMY_HASH = hash_password("dummy-password-used-to-equalise-timing")


def _client_key(request: Request) -> str:
    return request.client.host if request.client else "unknown"


def _rate_limited() -> ApiError:
    return ApiError(429, "rate_limited", "Zbyt wiele prób. Spróbuj ponownie za minutę.")


def _invalid_credentials() -> ApiError:
    return ApiError(401, "invalid_credentials", "Nieprawidłowy e-mail lub hasło.")


def _issue_tokens(
    db: Session, user: User, response: Response, settings: Settings, now: datetime | None = None
) -> TokenOut:
    now = now or datetime.now(UTC)
    raw, token_hash = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(days=settings.refresh_token_days),
        )
    )
    db.commit()
    response.set_cookie(
        REFRESH_COOKIE,
        raw,
        max_age=settings.refresh_token_days * 24 * 3600,
        httponly=True,
        secure=settings.cookie_secure,
        samesite="lax",
        path=REFRESH_COOKIE_PATH,
    )
    return TokenOut(access_token=create_access_token(user.id, settings, now))


@router.post("/register", status_code=201, response_model=UserOut)
def register(
    body: RegisterIn,
    request: Request,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> User:
    if not request.app.state.register_limiter.hit(_client_key(request)):
        raise _rate_limited()
    if settings.registration_mode == "invite" and body.invite_code not in settings.invite_code_set:
        raise ApiError(403, "invite_required", "Rejestracja wymaga ważnego kodu zaproszenia.")

    email_taken = ApiError(409, "email_taken", "Konto z tym adresem e-mail już istnieje.")
    email = body.email.lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise email_taken
    user = User(email=email, password_hash=hash_password(body.password))
    db.add(user)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise email_taken from exc
    db.refresh(user)
    return user


@router.post("/login", response_model=TokenOut)
def login(
    body: LoginIn,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    if not request.app.state.login_limiter.hit(_client_key(request)):
        raise _rate_limited()
    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        verify_password(_DUMMY_HASH, body.password)
        raise _invalid_credentials()
    if not verify_password(user.password_hash, body.password):
        raise _invalid_credentials()
    return _issue_tokens(db, user, response, settings)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    out = UserOut.model_validate(user)
    out.preferences = preferences_of(UserScope(db, user))
    return out


@router.post("/password", status_code=204)
def change_password(
    body: PasswordChangeIn,
    request: Request,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    """Keeps the session of this request (its refresh cookie) and ends every other one; other devices' access
    tokens are stateless and simply expire within `access_token_minutes`."""
    if not request.app.state.login_limiter.hit(_client_key(request)):
        raise _rate_limited()
    if not verify_password(user.password_hash, body.current_password):
        raise ApiError(400, "wrong_password", "Obecne hasło jest nieprawidłowe.")
    user.password_hash = hash_password(body.new_password)
    others = update(RefreshToken).where(RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None))
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        others = others.where(RefreshToken.token_hash != hash_refresh_token(raw))
    db.execute(others.values(revoked_at=datetime.now(UTC)))
    db.commit()
    return Response(status_code=204)


def _invalid_refresh() -> ApiError:
    # Every 401 from /refresh clears the refresh cookie client-side too, so a dead
    # or stolen token isn't kept around for another (futile, or worse) retry.
    clearing_response = Response()
    clearing_response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return ApiError(
        401,
        "invalid_refresh",
        "Sesja wygasła. Zaloguj się ponownie.",
        headers={"set-cookie": clearing_response.headers["set-cookie"]},
    )


@router.post("/refresh", response_model=TokenOut)
def refresh(
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    settings: Settings = Depends(get_settings),
) -> TokenOut:
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        raise _invalid_refresh()

    token_hash = hash_refresh_token(raw)
    now = datetime.now(UTC)

    # Atomically claim the token: only one concurrent request can flip revoked_at
    # from NULL to now, so a racing replay of the same still-valid cookie can
    # never rotate twice (check-then-act would let both requests read
    # revoked_at IS NULL and both succeed).
    claimed_user_id = db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(revoked_at=now)
        .returning(RefreshToken.user_id)
    ).scalar_one_or_none()

    if claimed_user_id is not None:
        user = db.get(User, claimed_user_id)
        if user is None:
            raise _invalid_refresh()
        return _issue_tokens(db, user, response, settings, now)

    # Nothing claimed: the token is unknown, already revoked (reuse), or expired.
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == token_hash))
    if token is None:
        raise _invalid_refresh()
    if token.revoked_at is not None:
        # A rotated token came back: assume it was stolen and end every session of this user.
        logger.warning("Refresh token reuse detected; revoked all sessions of user %s", token.user_id)
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == token.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.commit()
        raise _invalid_refresh()
    # Otherwise the token was simply expired.
    db.rollback()
    raise _invalid_refresh()


@router.post("/logout", status_code=204)
def logout(request: Request, db: Session = Depends(get_db)) -> Response:
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.token_hash == hash_refresh_token(raw), RefreshToken.revoked_at.is_(None))
            .values(revoked_at=datetime.now(UTC))
        )
        db.commit()
    response = Response(status_code=204)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return response
