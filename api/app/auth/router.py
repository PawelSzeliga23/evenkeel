from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.schemas import LoginIn, RegisterIn, TokenOut, UserOut
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
def me(user: User = Depends(get_current_user)) -> User:
    return user


def _invalid_refresh() -> ApiError:
    return ApiError(401, "invalid_refresh", "Sesja wygasła. Zaloguj się ponownie.")


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
    token = db.scalar(select(RefreshToken).where(RefreshToken.token_hash == hash_refresh_token(raw)))
    if token is None:
        raise _invalid_refresh()

    now = datetime.now(UTC)
    if token.revoked_at is not None:
        # A rotated token came back: assume it was stolen and end every session of this user.
        db.execute(
            update(RefreshToken)
            .where(RefreshToken.user_id == token.user_id, RefreshToken.revoked_at.is_(None))
            .values(revoked_at=now)
        )
        db.commit()
        raise _invalid_refresh()
    if token.expires_at <= now:
        raise _invalid_refresh()

    token.revoked_at = now
    user = db.get(User, token.user_id)
    if user is None:
        raise _invalid_refresh()
    return _issue_tokens(db, user, response, settings, now)


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
