from collections.abc import Callable

from fastapi import FastAPI
from fastapi.testclient import TestClient
from httpx import Response

PASSWORD = "bardzo-tajne-haslo"


def register(client: TestClient, email: str = "anna@portfolio.dev", password: str = PASSWORD, **extra: str) -> Response:
    return client.post("/api/auth/register", json={"email": email, "password": password, **extra})


def login(client: TestClient, email: str = "anna@portfolio.dev", password: str = PASSWORD) -> Response:
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_register_creates_user_with_normalised_email(client: TestClient) -> None:
    response = register(client, email="  Anna@Portfolio.DEV ")

    assert response.status_code == 201
    body = response.json()
    assert body["email"] == "anna@portfolio.dev"
    assert body["base_currency"] == "PLN"
    assert "password_hash" not in body


def test_register_rejects_duplicate_email_regardless_of_case(client: TestClient) -> None:
    register(client)
    response = register(client, email="ANNA@portfolio.dev")

    assert response.status_code == 409
    assert response.json()["code"] == "email_taken"


def test_register_rejects_short_password(client: TestClient) -> None:
    response = register(client, password="krotkie")

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_register_rejects_invalid_email(client: TestClient) -> None:
    assert register(client, email="to-nie-email").status_code == 422


def test_invite_mode_requires_valid_code(make_app: Callable[..., FastAPI]) -> None:
    client = TestClient(make_app(registration_mode="invite", invite_codes="znajomi2026, drugi-kod"))

    missing = register(client)
    assert missing.status_code == 403
    assert missing.json()["code"] == "invite_required"
    assert register(client, invite_code="zly-kod").status_code == 403
    assert register(client, invite_code="znajomi2026").status_code == 201


def test_login_returns_access_token_and_sets_refresh_cookie(client: TestClient) -> None:
    register(client)
    response = login(client, email=" ANNA@portfolio.dev")

    assert response.status_code == 200
    assert response.json()["token_type"] == "bearer"
    assert response.json()["access_token"]
    assert response.cookies.get("refresh_token")
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie
    assert "samesite=lax" in cookie
    assert "path=/api/auth" in cookie


def test_wrong_password_and_unknown_email_give_identical_error(client: TestClient) -> None:
    register(client)
    wrong_password = login(client, password="zle-haslo-123")
    unknown_email = login(client, email="nikt@portfolio.dev")

    assert wrong_password.status_code == unknown_email.status_code == 401
    assert wrong_password.json() == unknown_email.json()
    assert wrong_password.json()["code"] == "invalid_credentials"


def test_me_returns_current_user(client: TestClient) -> None:
    register(client)
    token = login(client).json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})

    assert response.status_code == 200
    assert response.json()["email"] == "anna@portfolio.dev"


def test_me_without_token_is_unauthenticated(client: TestClient) -> None:
    response = client.get("/api/auth/me")

    assert response.status_code == 401
    assert response.json()["code"] == "not_authenticated"


def test_me_with_garbage_token_is_invalid_token(client: TestClient) -> None:
    response = client.get("/api/auth/me", headers={"Authorization": "Bearer abc.def.ghi"})

    assert response.status_code == 401
    assert response.json()["code"] == "invalid_token"


def test_login_is_rate_limited(make_app: Callable[..., FastAPI]) -> None:
    client = TestClient(make_app(login_rate_limit_per_minute=3))

    statuses = [login(client, password="zle-haslo-123").status_code for _ in range(4)]

    assert statuses == [401, 401, 401, 429]


def test_register_is_rate_limited(make_app: Callable[..., FastAPI]) -> None:
    client = TestClient(make_app(register_rate_limit_per_minute=2))

    statuses = [register(client, email=f"osoba{i}@portfolio.dev").status_code for i in range(3)]

    assert statuses == [201, 201, 429]
    assert register(client, email="kolejna@portfolio.dev").json()["code"] == "rate_limited"
