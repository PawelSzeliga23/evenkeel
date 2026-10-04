import logging
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import ColumnElement, Update, delete, select, update
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.auth.schemas import AccountDeleteIn, LoginIn, PasswordChangeIn, RegisterIn, SessionOut, TokenOut, UserOut
from app.auth.security import (
    create_access_token,
    hash_password,
    hash_refresh_token,
    new_refresh_token,
    verify_password,
)
from app.config import Settings, app_settings
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
    header = request.app.state.settings.client_ip_header
    forwarded = request.headers.get(header) if header else None
    if forwarded:
        return forwarded.strip()
    return request.client.host if request.client else "unknown"


def _rate_limited() -> ApiError:
    return ApiError(429, "rate_limited", "Zbyt wiele prób. Spróbuj ponownie za minutę.")


def _invalid_credentials() -> ApiError:
    return ApiError(401, "invalid_credentials", "Nieprawidłowy e-mail lub hasło.")


@dataclass(frozen=True)
class SessionInfo:
    """What a new refresh token inherits: the session it continues (plan 8d)."""

    session_id: uuid.UUID
    user_agent: str | None
    started_at: datetime


def _new_session(request: Request, now: datetime) -> SessionInfo:
    agent = request.headers.get("user-agent")
    return SessionInfo(uuid.uuid4(), agent[:300] if agent else None, now)


def _issue_tokens(
    db: Session, user: User, response: Response, settings: Settings, session: SessionInfo, now: datetime | None = None
) -> TokenOut:
    now = now or datetime.now(UTC)
    raw, token_hash = new_refresh_token()
    db.add(
        RefreshToken(
            user_id=user.id,
            token_hash=token_hash,
            expires_at=now + timedelta(days=settings.refresh_token_days),
            session_id=session.session_id,
            user_agent=session.user_agent,
            session_started_at=session.started_at,
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
    settings: Settings = Depends(app_settings),
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
    settings: Settings = Depends(app_settings),
) -> TokenOut:
    email = body.email.lower()
    failures = request.app.state.email_limiter
    # Per IP, and wrong passwords per e-mail so that guessing one password from many IPs is slowed down too.
    if not request.app.state.login_limiter.hit(_client_key(request)) or failures.full(email):
        raise _rate_limited()
    user = db.scalar(select(User).where(User.email == email))
    if user is None:
        verify_password(_DUMMY_HASH, body.password)
        failures.hit(email)
        raise _invalid_credentials()
    if not verify_password(user.password_hash, body.password):
        failures.hit(email)
        raise _invalid_credentials()
    now = datetime.now(UTC)
    return _issue_tokens(db, user, response, settings, _new_session(request, now), now)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> UserOut:
    # Not model_validate(user): the stored preferences may hold a layout that no longer validates (plan 9).
    return UserOut(id=user.id, email=user.email, base_currency=user.base_currency,
                   preferences=preferences_of(UserScope(db, user)))


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
    now = datetime.now(UTC)
    others = update(RefreshToken).where(*_active(user, now))
    raw = request.cookies.get(REFRESH_COOKIE)
    if raw:
        others = others.where(RefreshToken.token_hash != hash_refresh_token(raw))
    db.execute(_ended(others, now))
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
    settings: Settings = Depends(app_settings),
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
    claimed = db.execute(
        update(RefreshToken)
        .where(
            RefreshToken.token_hash == token_hash,
            RefreshToken.revoked_at.is_(None),
            RefreshToken.expires_at > now,
        )
        .values(revoked_at=now)
        .returning(RefreshToken.user_id, RefreshToken.session_id, RefreshToken.user_agent,
                   RefreshToken.session_started_at)
    ).one_or_none()

    if claimed is not None:
        user = db.get(User, claimed.user_id)
        if user is None:
            raise _invalid_refresh()
        session = SessionInfo(claimed.session_id, claimed.user_agent, claimed.session_started_at)
        return _issue_tokens(db, user, response, settings, session, now)

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


def _current_session(request: Request, db: Session, user: User) -> uuid.UUID | None:
    """The session of this request: the one its refresh cookie belongs to."""
    raw = request.cookies.get(REFRESH_COOKIE)
    if not raw:
        return None
    return db.scalar(select(RefreshToken.session_id).where(
        RefreshToken.token_hash == hash_refresh_token(raw), RefreshToken.user_id == user.id))


def _ended(tokens: Update, now: datetime) -> Update:
    """Signs the tokens out by expiring them, not revoking: a revoked token that comes back means a stolen cookie
    and ends every session, so the signed-out device trying its cookie once more must not look like that."""
    return tokens.values(expires_at=now)


def _active(user: User, now: datetime) -> tuple[ColumnElement[bool], ...]:
    """Tokens that still sign the user in."""
    return (RefreshToken.user_id == user.id, RefreshToken.revoked_at.is_(None), RefreshToken.expires_at > now)


@router.get("/sessions", response_model=list[SessionOut])
def sessions(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[SessionOut]:
    """The user's signed-in devices: this one first, then the most recently used."""
    current = _current_session(request, db, user)
    rows = db.scalars(select(RefreshToken).where(*_active(user, datetime.now(UTC)))).all()
    latest: dict[uuid.UUID, RefreshToken] = {}
    for token in rows:
        if token.session_id not in latest or token.created_at > latest[token.session_id].created_at:
            latest[token.session_id] = token
    out = [SessionOut(id=t.session_id, user_agent=t.user_agent, started_at=t.session_started_at,
                      last_used_at=t.created_at, current=t.session_id == current) for t in latest.values()]
    return sorted(out, key=lambda s: (not s.current, -s.last_used_at.timestamp()))


@router.delete("/sessions/{session_id}", status_code=204)
def revoke_session(
    session_id: uuid.UUID, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Response:
    if session_id == _current_session(request, db, user):
        raise ApiError(400, "current_session", "To jest ta sesja — użyj Wyloguj.")
    now = datetime.now(UTC)
    result = db.execute(_ended(update(RefreshToken).where(*_active(user, now), RefreshToken.session_id == session_id),
                               now))
    if result.rowcount == 0:
        raise ApiError(404, "not_found", "Nie znaleziono sesji.")
    db.commit()
    return Response(status_code=204)


@router.post("/sessions/revoke-others", status_code=204)
def revoke_other_sessions(
    request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Response:
    now = datetime.now(UTC)
    others = update(RefreshToken).where(*_active(user, now))
    current = _current_session(request, db, user)
    if current is not None:
        others = others.where(RefreshToken.session_id != current)
    db.execute(_ended(others, now))
    db.commit()
    return Response(status_code=204)


DELETE_PHRASE = "USUŃ KONTO"


@router.delete("/account", status_code=204)
def delete_account(
    body: AccountDeleteIn, request: Request, user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Response:
    """The user and everything of theirs; the database's cascades take the rows (plan 8d)."""
    if not request.app.state.login_limiter.hit(_client_key(request)):
        raise _rate_limited()
    if body.confirm.strip() != DELETE_PHRASE:
        raise ApiError(422, "confirm_required", f"Wpisz {DELETE_PHRASE}, żeby usunąć konto.")
    if not verify_password(user.password_hash, body.password):
        raise ApiError(400, "wrong_password", "Hasło jest nieprawidłowe.")
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    response = Response(status_code=204)
    response.delete_cookie(REFRESH_COOKIE, path=REFRESH_COOKIE_PATH)
    return response
