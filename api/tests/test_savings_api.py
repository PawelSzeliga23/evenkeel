from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

LoginAs = Callable[[str], dict[str, str]]
ON = {"date": "2026-10-01"}  # September's interest is credited once 30 September has ended


@pytest.fixture
def world(client: TestClient, login_as: LoginAs) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    savings = client.post("/api/accounts", json={"name": "Konto oszczędnościowe", "kind": "savings"},
                          headers=anna).json()["id"]
    bonds = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=anna).json()["id"]
    return {"anna": anna, "bartek": bartek, "savings": savings, "bonds": bonds,
            "url": f"/api/savings-accounts/{savings}"}


def test_configured_account_with_rate_and_balance_earns_interest(client: TestClient, world: dict) -> None:
    anna, url = world["anna"], world["url"]
    assert client.put(url, json={"capitalization": "monthly"}, headers=anna).status_code == 200
    assert client.post(f"{url}/rates", json={"valid_from": "2026-09-01", "annual_rate": "5"},
                       headers=anna).status_code == 201
    assert client.post(f"{url}/balances", json={"as_of_date": "2026-09-01", "balance": "10000"},
                       headers=anna).status_code == 201

    account = client.get(url, headers=anna).json()
    positions = client.get("/api/positions", params=ON, headers=anna).json()

    assert (account["capitalization"], [r["annual_rate"] for r in account["rates"]],
            [b["balance"] for b in account["balances"]]) == ("monthly", ["5.0000"], ["10000.0000"])
    (item,) = [p for p in positions if p["kind"] == "savings"]
    assert (item["name"], item["value_pln"], item["cost_pln"], item["unrealized_pln"]) == (
        "Konto oszczędnościowe", "10032.18", "10000.00", "32.18")


def test_entries_need_a_configured_account_and_one_entry_per_day(client: TestClient, world: dict) -> None:
    anna, url = world["anna"], world["url"]
    early = client.post(f"{url}/balances", json={"as_of_date": "2026-09-01", "balance": "1"}, headers=anna)
    client.put(url, json={"capitalization": "daily"}, headers=anna)
    client.post(f"{url}/rates", json={"valid_from": "2026-09-01", "annual_rate": "5"}, headers=anna)
    duplicate = client.post(f"{url}/rates", json={"valid_from": "2026-09-01", "annual_rate": "4"}, headers=anna)
    future = client.post(f"{url}/balances", json={"as_of_date": "2999-01-01", "balance": "1"}, headers=anna)

    assert [(r.status_code, r.json()["code"]) for r in (early, duplicate, future)] == [
        (409, "savings_not_configured"), (409, "duplicate_date"), (422, "balance_in_future")]


def test_deleting_an_entry(client: TestClient, world: dict) -> None:
    anna, url = world["anna"], world["url"]
    client.put(url, json={"capitalization": "monthly"}, headers=anna)
    balance_id = client.post(f"{url}/balances", json={"as_of_date": "2026-09-01", "balance": "5"},
                             headers=anna).json()["id"]

    assert client.delete(f"{url}/balances/{balance_id}", headers=anna).status_code == 204
    assert client.get(url, headers=anna).json()["balances"] == []


def test_wrong_kind_and_foreign_accounts(client: TestClient, world: dict) -> None:
    wrong = client.put(f"/api/savings-accounts/{world['bonds']}", json={"capitalization": "monthly"},
                       headers=world["anna"])
    foreign = client.put(world["url"], json={"capitalization": "monthly"}, headers=world["bartek"])
    unset = client.get(world["url"], headers=world["anna"])

    assert [(r.status_code, r.json()["code"]) for r in (wrong, foreign, unset)] == [
        (422, "wrong_account_kind"), (404, "not_found"), (404, "not_found")]


def test_savings_need_a_pln_account(client: TestClient, world: dict) -> None:
    euro = client.post("/api/accounts", json={"name": "Konto EUR", "kind": "savings", "currency": "EUR"},
                       headers=world["anna"]).json()["id"]

    response = client.put(f"/api/savings-accounts/{euro}", json={"capitalization": "monthly"}, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "wrong_currency")
