import threading
from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import Engine, text

from app.auth.security import hash_refresh_token

PASSWORD = "bardzo-tajne-haslo"


def _register_and_login(client: TestClient) -> str:
    client.post("/api/auth/register", json={"email": "anna@portfolio.dev", "password": PASSWORD})
    response = client.post("/api/auth/login", json={"email": "anna@portfolio.dev", "password": PASSWORD})
    return response.cookies["refresh_token"]


def _refresh_with(app: FastAPI, raw_cookie: str) -> int:
    """Refresh from a separate client that holds only the given cookie (e.g. an attacker)."""
    other = TestClient(app)
    return other.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={raw_cookie}"}).status_code


def test_refresh_issues_new_access_token_and_rotates_cookie(client: TestClient) -> None:
    old_cookie = _register_and_login(client)

    response = client.post("/api/auth/refresh")

    assert response.status_code == 200
    new_cookie = response.cookies["refresh_token"]
    assert new_cookie != old_cookie
    token = response.json()["access_token"]
    assert client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"}).status_code == 200


def test_refresh_without_cookie_is_rejected(client: TestClient) -> None:
    response = client.post("/api/auth/refresh")

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_refresh"


def _assert_clears_refresh_cookie(response: object) -> None:
    cookie = response.headers["set-cookie"].lower()  # type: ignore[attr-defined]
    assert "refresh_token=" in cookie
    assert "max-age=0" in cookie
    assert "path=/api/auth" in cookie


def test_refresh_without_cookie_clears_refresh_cookie(client: TestClient) -> None:
    _assert_clears_refresh_cookie(client.post("/api/auth/refresh"))


def test_expired_refresh_clears_refresh_cookie(client: TestClient, engine: Engine) -> None:
    _register_and_login(client)
    with engine.begin() as conn:
        conn.execute(text("UPDATE refresh_tokens SET expires_at = now() - interval '1 minute'"))

    _assert_clears_refresh_cookie(client.post("/api/auth/refresh"))


def test_reused_refresh_token_clears_refresh_cookie(make_app: Callable[..., FastAPI]) -> None:
    app = make_app()
    client = TestClient(app)
    old_cookie = _register_and_login(client)
    assert client.post("/api/auth/refresh").status_code == 200

    other = TestClient(app)
    response = other.post("/api/auth/refresh", headers={"Cookie": f"refresh_token={old_cookie}"})

    _assert_clears_refresh_cookie(response)


def test_reusing_rotated_refresh_token_revokes_all_sessions(make_app: Callable[..., FastAPI]) -> None:
    app = make_app()
    client = TestClient(app)
    old_cookie = _register_and_login(client)
    assert client.post("/api/auth/refresh").status_code == 200  # client now holds the rotated cookie

    assert _refresh_with(app, old_cookie) == 401
    # The legitimate session is killed too: someone replayed a stolen token.
    assert client.post("/api/auth/refresh").status_code == 401


def test_expired_refresh_token_is_rejected(client: TestClient, engine: Engine) -> None:
    _register_and_login(client)
    with engine.begin() as conn:
        conn.execute(text("UPDATE refresh_tokens SET expires_at = now() - interval '1 minute'"))

    assert client.post("/api/auth/refresh").status_code == 401


def test_logout_revokes_refresh_token_and_clears_cookie(make_app: Callable[..., FastAPI]) -> None:
    app = make_app()
    client = TestClient(app)
    cookie = _register_and_login(client)

    response = client.post("/api/auth/logout")

    assert response.status_code == 204
    assert "max-age=0" in response.headers["set-cookie"].lower()
    assert _refresh_with(app, cookie) == 401


def test_logout_without_cookie_is_harmless(client: TestClient) -> None:
    assert client.post("/api/auth/logout").status_code == 204


def test_concurrent_claims_of_the_same_token_only_succeed_once(
    client: TestClient, engine: Engine
) -> None:
    """Regression test for the check-then-act race: the claim must be a single
    atomic UPDATE, so two overlapping attempts on the same still-valid token
    can never both succeed. One thread holds the row lock inside an open
    transaction (simulating a concurrent request mid-claim); a second,
    independent connection then runs the exact same conditional UPDATE the
    endpoint uses. Whether it blocks on the lock or arrives after the first
    commits, it must see the row already claimed."""
    raw_cookie = _register_and_login(client)
    token_hash = hash_refresh_token(raw_cookie)
    claim_sql = text(
        "UPDATE refresh_tokens SET revoked_at = now() "
        "WHERE token_hash = :token_hash AND revoked_at IS NULL AND expires_at > now() "
        "RETURNING user_id"
    )

    holder_claimed = threading.Event()
    release_holder = threading.Event()
    results: dict[str, object] = {}

    def hold_claim() -> None:
        with engine.begin() as conn:
            results["first"] = conn.execute(claim_sql, {"token_hash": token_hash}).scalar()
            holder_claimed.set()
            release_holder.wait(timeout=5)
        # Transaction commits on exiting the `with` block, releasing the row lock.

    holder = threading.Thread(target=hold_claim)
    holder.start()
    assert holder_claimed.wait(timeout=5), "holder thread never claimed the token"

    release_holder.set()
    with engine.begin() as conn:
        results["second"] = conn.execute(claim_sql, {"token_hash": token_hash}).scalar()
    holder.join(timeout=5)

    assert results["first"] is not None
    assert results["second"] is None
