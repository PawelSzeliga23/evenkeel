from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient

EMAIL = "anna@portfolio.dev"
OLD = "bardzo-tajne-haslo"
NEW = "jeszcze-bardziej-tajne"


def _signed_in(client: TestClient) -> dict[str, str]:
    """Logs in (the client keeps the refresh cookie) and returns the Authorization header."""
    response = client.post("/api/auth/login", json={"email": EMAIL, "password": OLD})
    assert response.status_code == 200, response.json()
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def _change(client: TestClient, headers: dict[str, str], current: str = OLD, new: str = NEW):
    return client.post("/api/auth/password", json={"current_password": current, "new_password": new}, headers=headers)


def test_password_change_keeps_this_session_and_ends_the_others(make_app: Callable[..., FastAPI]) -> None:
    app = make_app()
    phone, laptop = TestClient(app), TestClient(app)
    phone.post("/api/auth/register", json={"email": EMAIL, "password": OLD})
    headers = _signed_in(phone)
    _signed_in(laptop)

    assert _change(phone, headers).status_code == 204

    assert phone.post("/api/auth/refresh").status_code == 200
    assert laptop.post("/api/auth/refresh").status_code == 401
    assert phone.post("/api/auth/login", json={"email": EMAIL, "password": OLD}).status_code == 401
    assert phone.post("/api/auth/login", json={"email": EMAIL, "password": NEW}).status_code == 200


def test_password_change_without_a_refresh_cookie_ends_every_session(make_app: Callable[..., FastAPI]) -> None:
    app = make_app()
    phone = TestClient(app)
    phone.post("/api/auth/register", json={"email": EMAIL, "password": OLD})
    headers = _signed_in(phone)
    phone.cookies.clear()
    laptop = TestClient(app)
    _signed_in(laptop)

    assert _change(phone, headers).status_code == 204
    assert laptop.post("/api/auth/refresh").status_code == 401


def test_wrong_current_password_changes_nothing(client: TestClient) -> None:
    client.post("/api/auth/register", json={"email": EMAIL, "password": OLD})
    headers = _signed_in(client)

    response = _change(client, headers, current="zle-haslo-123")

    assert (response.status_code, response.json()["code"]) == (400, "wrong_password")
    assert response.json()["message"] == "Obecne hasło jest nieprawidłowe."
    assert client.post("/api/auth/login", json={"email": EMAIL, "password": OLD}).status_code == 200
    assert client.post("/api/auth/refresh").status_code == 200


def test_new_password_follows_the_registration_rules(client: TestClient) -> None:
    client.post("/api/auth/register", json={"email": EMAIL, "password": OLD})
    headers = _signed_in(client)

    response = _change(client, headers, new="krotkie")

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


def test_password_change_requires_authentication(client: TestClient) -> None:
    response = client.post("/api/auth/password", json={"current_password": OLD, "new_password": NEW})

    assert (response.status_code, response.json()["code"]) == (401, "not_authenticated")


def test_guessing_the_current_password_is_rate_limited(make_app: Callable[..., FastAPI]) -> None:
    client = TestClient(make_app(login_rate_limit_per_minute=3))
    client.post("/api/auth/register", json={"email": EMAIL, "password": OLD})
    headers = _signed_in(client)  # the login itself is the first hit

    assert _change(client, headers, current="zle-haslo-1").status_code == 400
    assert _change(client, headers, current="zle-haslo-2").status_code == 400
    limited = _change(client, headers)  # the right password, but the budget is spent

    assert (limited.status_code, limited.json()["code"]) == (429, "rate_limited")
