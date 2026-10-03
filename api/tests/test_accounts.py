import datetime as dt
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

import app.accounts.router as accounts_router
from app.models import User

LoginAs = Callable[[str], dict[str, str]]

XTB_IKE = {
    "name": "XTB IKE",
    "kind": "broker",
    "wrapper": "ike",
    "broker": "xtb",
    "external_account_number": "56216965",
}


def _create(client: TestClient, headers: dict[str, str], payload: dict[str, str] = XTB_IKE) -> int:
    response = client.post("/api/accounts", json=payload, headers=headers)
    assert response.status_code == 201, response.json()
    return response.json()["id"]


def test_create_and_list_accounts(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    account_id = _create(client, anna)
    listing = client.get("/api/accounts", headers=anna)

    assert listing.status_code == 200
    assert [(a["id"], a["name"], a["wrapper"], a["currency"]) for a in listing.json()] == [
        (account_id, "XTB IKE", "ike", "PLN")
    ]


def test_account_defaults(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    response = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=anna)

    assert response.status_code == 201
    body = response.json()
    assert (body["wrapper"], body["broker"], body["external_account_number"], body["currency"]) == (
        "regular", None, None, "PLN",
    )


@pytest.mark.parametrize(
    "payload",
    [
        {"name": "Krypto", "kind": "crypto"},
        {"name": "", "kind": "cash"},
        {"name": "   ", "kind": "cash"},
        {"name": "XTB", "kind": "broker", "broker": "xtb"},
        {"name": "Konto", "kind": "cash", "currency": "zloty"},
        {"name": "Konto", "kind": "cash", "unexpected": "field"},
        {"kind": "savings", "name": "Oszczędnościowe", "broker": "xtb", "external_account_number": "1"},
        {"kind": "broker", "name": "X"},
    ],
    ids=[
        "unknown-kind",
        "empty-name",
        "whitespace-only-name",
        "broker-without-number",
        "bad-currency",
        "unknown-field",
        "broker-without-kind-broker",
        "kind-broker-without-broker",
    ],
)
def test_create_rejects_invalid_payload(client: TestClient, login_as: LoginAs, payload: dict[str, str]) -> None:
    response = client.post("/api/accounts", json=payload, headers=login_as("anna@portfolio.dev"))

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_create_strips_name_whitespace(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    response = client.post(
        "/api/accounts", json={"name": "  Obligacje  ", "kind": "bonds"}, headers=anna
    )

    assert response.status_code == 201
    assert response.json()["name"] == "Obligacje"


def test_duplicate_broker_account_is_rejected(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    _create(client, anna)

    response = client.post("/api/accounts", json=XTB_IKE, headers=anna)

    assert response.status_code == 409
    assert response.json()["code"] == "account_exists"


def test_same_broker_account_is_allowed_for_different_users(client: TestClient, login_as: LoginAs) -> None:
    _create(client, login_as("anna@portfolio.dev"))
    _create(client, login_as("bartek@portfolio.dev"))


def test_update_changes_only_given_fields(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    account_id = _create(client, anna)

    response = client.patch(f"/api/accounts/{account_id}", json={"name": "IKE w XTB"}, headers=anna)

    assert response.status_code == 200
    assert (response.json()["name"], response.json()["wrapper"]) == ("IKE w XTB", "ike")


def test_update_rejects_explicit_null(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    account_id = _create(client, anna)

    response = client.patch(f"/api/accounts/{account_id}", json={"name": None}, headers=anna)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_update_rejects_unknown_field(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    account_id = _create(client, anna)

    response = client.patch(f"/api/accounts/{account_id}", json={"currency": "USD"}, headers=anna)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_update_rejects_whitespace_only_name(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    account_id = _create(client, anna)

    response = client.patch(f"/api/accounts/{account_id}", json={"name": "   "}, headers=anna)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_update_strips_name_whitespace(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    account_id = _create(client, anna)

    response = client.patch(f"/api/accounts/{account_id}", json={"name": "  IKE w XTB  "}, headers=anna)

    assert response.status_code == 200
    assert response.json()["name"] == "IKE w XTB"


@pytest.mark.parametrize("account_id", [0, 2147483648, 99999999999999999999999])
@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_out_of_range_account_id_is_a_validation_error(
    client: TestClient, login_as: LoginAs, method: str, account_id: int
) -> None:
    anna = login_as("anna@portfolio.dev")
    kwargs = {"json": {"name": "Cokolwiek"}} if method == "PATCH" else {}

    response = client.request(method, f"/api/accounts/{account_id}", headers=anna, **kwargs)

    assert response.status_code == 422
    assert response.json()["code"] == "validation_error"


def test_delete_account(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    account_id = _create(client, anna)

    assert client.delete(f"/api/accounts/{account_id}", headers=anna).status_code == 204
    assert client.get(f"/api/accounts/{account_id}", headers=anna).status_code == 404


def test_accounts_require_authentication(client: TestClient) -> None:
    assert client.get("/api/accounts").status_code == 401


def test_list_shows_only_own_accounts(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    bartek = login_as("bartek@portfolio.dev")
    _create(client, anna)

    assert client.get("/api/accounts", headers=bartek).json() == []


@pytest.mark.parametrize("method", ["GET", "PATCH", "DELETE"])
def test_other_user_cannot_touch_account(client: TestClient, login_as: LoginAs, method: str) -> None:
    anna = login_as("anna@portfolio.dev")
    bartek = login_as("bartek@portfolio.dev")
    account_id = _create(client, anna)
    kwargs = {"json": {"name": "Przejęte"}} if method == "PATCH" else {}

    foreign = client.request(method, f"/api/accounts/{account_id}", headers=bartek, **kwargs)
    missing = client.request(method, "/api/accounts/999999", headers=bartek, **kwargs)

    assert foreign.status_code == 404
    assert foreign.json() == missing.json()
    assert client.get(f"/api/accounts/{account_id}", headers=anna).json()["name"] == "XTB IKE"


def test_usage_counts_what_deleting_the_account_would_remove(
    client: TestClient, login_as: LoginAs, engine: Engine
) -> None:
    from tests.valuation_seed import seed_holdings, seed_market, seed_snapshot

    anna = login_as("anna@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = seed_holdings(db, user_id, instrument_id)
        seed_snapshot(db, account_id, instrument_id, "2")

    response = client.get(f"/api/accounts/{account_id}/usage", headers=anna)

    assert response.status_code == 200
    assert response.json() == {"transactions": 4, "imports": 1, "bond_holdings": 0, "savings_entries": 0, "notes": 0}


def test_usage_of_a_savings_account_counts_its_rates_and_flows(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    created = client.post("/api/savings-accounts", headers=anna, json={
        "name": "Konto oszczędnościowe", "wrapper": "regular", "capitalization": "monthly", "annual_rate": "5",
        "rate_valid_from": "2026-09-01", "first_deposit": {"date": "2026-09-01", "amount": "10000"},
    })
    assert created.status_code == 201, created.json()

    usage = client.get(f"/api/accounts/{created.json()['account_id']}/usage", headers=anna).json()

    assert usage == {"transactions": 0, "imports": 0, "bond_holdings": 0, "savings_entries": 2, "notes": 0}


def test_usage_of_someone_elses_account_is_not_found(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    bartek = login_as("bartek@portfolio.dev")
    account_id = _create(client, anna)

    response = client.get(f"/api/accounts/{account_id}/usage", headers=bartek)

    assert (response.status_code, response.json()["code"]) == (404, "not_found")


def test_deleting_an_account_recomputes_the_valuation(
    client: TestClient, login_as: LoginAs, engine: Engine, monkeypatch: pytest.MonkeyPatch
) -> None:
    anna = login_as("anna@portfolio.dev")
    account_id = _create(client, anna)
    recomputed: list[int] = []
    monkeypatch.setattr(accounts_router, "recompute_in_background", lambda _sessions, user_id: recomputed.append(user_id))

    assert client.delete(f"/api/accounts/{account_id}", headers=anna).status_code == 204

    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "anna@portfolio.dev"))
        assert (user.valuations_stale_from, recomputed) == (dt.date.min, [user.id])
