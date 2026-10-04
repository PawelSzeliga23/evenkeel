"""Plan 8d: the user's sessions (one per sign-in, kept across token rotation) and deleting the account."""
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, text
from sqlalchemy.orm import Session

from app.models import Account, RefreshToken, User
from tests.test_backup_api import seed

PASSWORD = "bardzo-tajne-haslo"
IPHONE = "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) AppleWebKit/605.1.15 Version/18.0 Mobile Safari/604.1"
WINDOWS = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"


def _device(app: FastAPI, email: str, agent: str) -> tuple[TestClient, dict[str, str]]:
    """A browser of its own (own cookie jar) signed in as `email`."""
    browser = TestClient(app, headers={"User-Agent": agent})
    browser.post("/api/auth/register", json={"email": email, "password": PASSWORD})
    token = browser.post("/api/auth/login", json={"email": email, "password": PASSWORD}).json()["access_token"]
    return browser, {"Authorization": f"Bearer {token}"}


def test_a_session_keeps_its_number_browser_and_start_across_refreshes(make_app: Callable[..., FastAPI]) -> None:
    phone, auth = _device(make_app(), "anna@portfolio.dev", IPHONE)
    before = phone.get("/api/auth/sessions", headers=auth).json()

    phone.post("/api/auth/refresh")
    after = phone.get("/api/auth/sessions", headers=auth).json()

    assert len(before) == len(after) == 1
    assert after[0]["id"] == before[0]["id"] and after[0]["started_at"] == before[0]["started_at"]
    assert after[0]["user_agent"] == IPHONE and after[0]["current"] is True
    assert after[0]["last_used_at"] >= before[0]["last_used_at"]


def test_the_list_shows_own_active_sessions_this_one_first(make_app: Callable[..., FastAPI]) -> None:
    app = make_app()
    phone, auth = _device(app, "anna@portfolio.dev", IPHONE)
    laptop, _ = _device(app, "anna@portfolio.dev", WINDOWS)
    _device(app, "ben@portfolio.dev", WINDOWS)
    gone, _ = _device(app, "anna@portfolio.dev", WINDOWS)
    gone.post("/api/auth/logout")

    listed = phone.get("/api/auth/sessions", headers=auth).json()

    assert [(s["user_agent"], s["current"]) for s in listed] == [(IPHONE, True), (WINDOWS, False)]


def test_signing_out_one_device_and_all_others(make_app: Callable[..., FastAPI]) -> None:
    app = make_app()
    phone, auth = _device(app, "anna@portfolio.dev", IPHONE)
    laptop, _ = _device(app, "anna@portfolio.dev", WINDOWS)
    tablet, _ = _device(app, "anna@portfolio.dev", "Tablet")
    _, ben = _device(app, "ben@portfolio.dev", WINDOWS)
    listed = {s["user_agent"]: s for s in phone.get("/api/auth/sessions", headers=auth).json()}

    assert phone.delete(f"/api/auth/sessions/{listed[IPHONE]['id']}", headers=auth).status_code == 400
    assert phone.delete(f"/api/auth/sessions/{listed[WINDOWS]['id']}", headers=ben).status_code == 404  # not Ben's
    assert phone.delete(f"/api/auth/sessions/{listed[WINDOWS]['id']}", headers=auth).status_code == 204
    # the signed-out laptop tries its cookie: refused, and that must not end the other sessions
    assert laptop.post("/api/auth/refresh").status_code == 401
    assert tablet.post("/api/auth/refresh").status_code == 200
    assert phone.post("/api/auth/refresh").status_code == 200

    assert phone.post("/api/auth/sessions/revoke-others", headers=auth).status_code == 204

    assert tablet.post("/api/auth/refresh").status_code == 401
    assert phone.post("/api/auth/refresh").status_code == 200
    assert [s["current"] for s in phone.get("/api/auth/sessions", headers=auth).json()] == [True]


def test_the_migration_gives_older_tokens_a_session(engine: Engine) -> None:
    with engine.connect() as conn:
        columns = {row[0]: row[1] for row in conn.execute(text(
            "SELECT column_name, is_nullable FROM information_schema.columns WHERE table_name = 'refresh_tokens'"))}
    assert columns["session_id"] == "NO" and columns["session_started_at"] == "NO" and columns["user_agent"] == "YES"


def test_deleting_the_account_takes_every_row_of_the_user_and_nothing_else(
    make_app: Callable[..., FastAPI], engine: Engine,
) -> None:
    app = make_app()
    anna_browser, anna = _device(app, "anna@portfolio.dev", IPHONE)
    _, ben = _device(app, "ben@portfolio.dev", WINDOWS)
    seed(engine, "anna@portfolio.dev")
    seed(engine, "ben@portfolio.dev")

    response = anna_browser.request("DELETE", "/api/auth/account", headers=anna,
                                    json={"password": PASSWORD, "confirm": "USUŃ KONTO"})

    assert response.status_code == 204, response.text
    assert "refresh_token" in response.headers.get("set-cookie", "")
    with Session(engine) as db:
        assert db.scalar(select(User.id).where(User.email == "anna@portfolio.dev")) is None
        with engine.connect() as conn:
            for table in ("accounts", "tags", "theses", "journal_entries", "scenarios", "ai_reviews", "imports",
                          "refresh_tokens", "corporate_actions", "daily_valuations"):
                left = conn.execute(text(f"SELECT count(*) FROM {table} WHERE user_id NOT IN (SELECT id FROM users)"))
                assert left.scalar() == 0, table
        ben_id = db.scalar(select(User.id).where(User.email == "ben@portfolio.dev"))
        assert db.scalar(select(func.count()).select_from(Account).where(Account.user_id == ben_id)) == 4
        assert db.scalar(select(func.count()).select_from(RefreshToken).where(RefreshToken.user_id == ben_id)) == 1
    assert anna_browser.post("/api/auth/login", json={"email": "anna@portfolio.dev", "password": PASSWORD}) \
        .status_code == 401


def test_a_wrong_password_or_phrase_deletes_nothing(make_app: Callable[..., FastAPI], engine: Engine) -> None:
    browser, auth = _device(make_app(), "anna@portfolio.dev", IPHONE)

    wrong = browser.request("DELETE", "/api/auth/account", headers=auth,
                            json={"password": "zle-haslo-123", "confirm": "USUŃ KONTO"})
    phrase = browser.request("DELETE", "/api/auth/account", headers=auth, json={"password": PASSWORD, "confirm": "tak"})

    assert (wrong.status_code, wrong.json()["message"]) == (400, "Hasło jest nieprawidłowe.")
    assert (phrase.status_code, phrase.json()["message"]) == (422, "Wpisz USUŃ KONTO, żeby usunąć konto.")
    with Session(engine) as db:
        assert db.scalar(select(User.id).where(User.email == "anna@portfolio.dev")) is not None
