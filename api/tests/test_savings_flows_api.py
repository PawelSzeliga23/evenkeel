import datetime as dt
import threading
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import User
from app.valuation.service import lock_user

LoginAs = Callable[[str], dict[str, str]]
NEW = {"name": "Konto oszczędnościowe", "wrapper": "regular", "capitalization": "monthly", "annual_rate": "5",
       "rate_valid_from": "2026-09-01", "first_deposit": {"date": "2026-09-01", "amount": "10000"}}


@pytest.fixture
def anna(login_as: LoginAs) -> dict[str, str]:
    return login_as("anna@portfolio.dev")


def _create(client: TestClient, headers: dict, **changes: object) -> dict:
    response = client.post("/api/savings-accounts", json={**NEW, **changes}, headers=headers)
    assert response.status_code == 201, response.json()
    return response.json()


def test_an_account_is_created_with_its_rate_and_first_deposit(client: TestClient, anna: dict) -> None:
    created = _create(client, anna)
    url = f"/api/savings-accounts/{created['account_id']}"

    last_day = client.get(url, params={"date": "2026-09-30"}, headers=anna).json()
    account = client.get(url, params={"date": "2026-10-01"}, headers=anna).json()
    accounts = client.get("/api/accounts", headers=anna).json()

    assert [(a["name"], a["kind"], a["wrapper"], a["currency"]) for a in accounts] == [
        ("Konto oszczędnościowe", "savings", "regular", "PLN")]
    assert (account["capitalization"], [r["annual_rate"] for r in account["rates"]]) == ("monthly", ["5.0000"])
    assert [(f["date"], f["amount"]) for f in account["flows"]] == [("2026-09-01", "10000.0000")]
    assert account["summary"] == {"balance": "10033.29", "deposits": "10000.00", "interest_net": "33.29",
                                  "tax": "7.81", "accrued": "0.00", "current_rate": "5.0000"}
    assert account["capitalizations"] == [
        {"period_end": "2026-09-30", "credited_on": "2026-10-01", "gross": "41.10", "tax": "7.81", "net": "33.29"}]
    # on the month's last day the bank has not credited September yet: 29 finished days accrued
    assert (last_day["summary"]["balance"], last_day["summary"]["accrued"], last_day["capitalizations"]) == (
        "10000.00", "39.73", [])


def test_nothing_is_created_when_the_first_deposit_is_in_the_future(client: TestClient, anna: dict) -> None:
    later = (dt.date.today() + dt.timedelta(days=2)).isoformat()
    response = client.post("/api/savings-accounts", json={**NEW, "first_deposit": {"date": later, "amount": "1"}},
                           headers=anna)

    assert (response.status_code, response.json()["code"]) == (422, "date_in_future")
    assert client.get("/api/accounts", headers=anna).json() == []


def test_deposits_and_withdrawals_move_the_balance(client: TestClient, anna: dict) -> None:
    url = f"/api/savings-accounts/{_create(client, anna)['account_id']}"

    deposit = client.post(f"{url}/flows", json={"date": "2026-09-10", "amount": "2000", "note": "premia"},
                          headers=anna)
    withdrawal = client.post(f"{url}/flows", json={"date": "2026-09-20", "amount": "-500"}, headers=anna)
    too_much = client.post(f"{url}/flows", json={"date": "2026-09-21", "amount": "-20000"}, headers=anna)
    zero = client.post(f"{url}/flows", json={"date": "2026-09-21", "amount": "0"}, headers=anna)
    summary = client.get(url, params={"date": "2026-09-25"}, headers=anna).json()["summary"]

    assert (deposit.status_code, deposit.json()["note"], withdrawal.status_code) == (201, "premia", 201)
    assert [(r.status_code, r.json()["code"]) for r in (too_much, zero)] == [
        (422, "insufficient_balance"), (422, "validation_error")]
    assert (summary["balance"], summary["deposits"]) == ("11500.00", "11500.00")


def test_a_deposit_that_a_later_withdrawal_needs_cannot_be_deleted(client: TestClient, anna: dict) -> None:
    url = f"/api/savings-accounts/{_create(client, anna)['account_id']}"
    deposit_id = client.post(f"{url}/flows", json={"date": "2026-09-10", "amount": "5000"}, headers=anna).json()["id"]
    withdrawal_id = client.post(f"{url}/flows", json={"date": "2026-09-20", "amount": "-12000"},
                                headers=anna).json()["id"]

    blocked = client.delete(f"{url}/flows/{deposit_id}", headers=anna)
    after_block = client.get(url, headers=anna).json()["flows"]
    removed = client.delete(f"{url}/flows/{withdrawal_id}", headers=anna)

    assert (blocked.status_code, blocked.json()["code"]) == (409, "flow_needed")
    assert len(after_block) == 3
    assert removed.status_code == 204


def test_flows_value_the_position_and_stay_private(client: TestClient, anna: dict, login_as: LoginAs) -> None:
    created = _create(client, anna, wrapper="ike")
    url = f"/api/savings-accounts/{created['account_id']}"
    bartek = login_as("bartek@portfolio.dev")

    positions = client.get("/api/positions", params={"date": "2026-09-15"}, headers=anna).json()
    summary = client.get(url, params={"date": "2026-10-01"}, headers=anna).json()["summary"]
    foreign = client.post(f"{url}/flows", json={"date": "2026-09-10", "amount": "1"}, headers=bartek)
    flow_id = client.get(url, headers=anna).json()["flows"][0]["id"]
    foreign_delete = client.delete(f"{url}/flows/{flow_id}", headers=bartek)

    (item,) = [p for p in positions if p["kind"] == "savings"]
    assert item["value_pln"] == "10000.00"  # valued from the deposit, before the first capitalization
    assert (summary["balance"], summary["tax"]) == ("10041.10", "0.00")  # IKE: no tax
    assert [(r.status_code, r.json()["code"]) for r in (foreign, foreign_delete)] == [
        (404, "not_found"), (404, "not_found")]


def test_a_configured_account_without_entries_reads_as_zero(client: TestClient, anna: dict) -> None:
    account_id = client.post("/api/accounts", json={"name": "Puste", "kind": "savings"}, headers=anna).json()["id"]
    url = f"/api/savings-accounts/{account_id}"
    client.put(url, json={"capitalization": "monthly"}, headers=anna)

    account = client.get(url, headers=anna).json()

    assert (account["flows"], account["capitalizations"], account["summary"]["balance"],
            account["summary"]["current_rate"]) == ([], [], "0.00", None)


def test_a_withdrawal_waits_for_another_change_of_the_same_user(
    client: TestClient, anna: dict, engine: Engine
) -> None:
    url = f"/api/savings-accounts/{_create(client, anna)['account_id']}"
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
    finished = threading.Event()
    responses: list = []

    def withdraw() -> None:
        responses.append(client.post(f"{url}/flows", json={"date": "2026-09-20", "amount": "-6000"}, headers=anna))
        finished.set()

    with Session(engine) as other:
        lock_user(other, user_id)  # like a second withdrawal still checking the balance
        thread = threading.Thread(target=withdraw)
        thread.start()
        assert not finished.wait(0.5)  # the balance check waits instead of reading a balance that may change
        other.commit()
    thread.join(10)

    assert finished.is_set()
    assert responses[0].status_code == 201
