import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import Transaction

LoginAs = Callable[[str], dict[str, str]]
DAY = "2026-09-01"


@pytest.fixture
def world(client: TestClient, login_as: LoginAs) -> dict:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    cash = client.post("/api/accounts", json={"name": "Portfel domowy", "kind": "cash"}, headers=anna).json()["id"]
    bonds = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=anna).json()["id"]
    return {"anna": anna, "bartek": bartek, "cash": cash, "bonds": bonds}


def _add(client: TestClient, headers: dict, **body: object):  # noqa: ANN202
    return client.post("/api/transactions", json={"date": DAY, "comment": "", **body}, headers=headers)


def test_manual_operations_get_their_sign_and_count_as_cash(client: TestClient, world: dict) -> None:
    anna, cash = world["anna"], world["cash"]
    for type_, amount in [("deposit", "1000"), ("withdrawal", "200.50"), ("interest", "3.10"), ("fee", "1")]:
        assert _add(client, anna, account_id=cash, type=type_, amount=amount).status_code == 201

    listed = client.get("/api/transactions", params={"account_id": cash}, headers=anna).json()
    positions = client.get("/api/positions", params={"date": "2026-09-15"}, headers=anna).json()

    assert sorted(Decimal(t["amount"]) for t in listed) == [Decimal("-200.5"), Decimal("-1"), Decimal("3.1"),
                                                             Decimal("1000")]
    assert all(t["manual"] and t["xtb_type"] == "manual" and t["currency"] == "PLN" for t in listed)
    assert {t["occurred_at"][:10] for t in listed} == {"2026-08-31"}  # midnight in Warsaw is 22:00 UTC the day before
    (cash_row,) = [p for p in positions if p["kind"] == "cash"]
    assert cash_row["value_pln"] == "801.60"


def test_manual_operations_only_on_cash_accounts_and_not_in_the_future(client: TestClient, world: dict) -> None:
    anna = world["anna"]
    tomorrow = (dt.date.today() + dt.timedelta(days=2)).isoformat()
    wrong = _add(client, anna, account_id=world["bonds"], type="deposit", amount="10")
    future = client.post("/api/transactions", json={"account_id": world["cash"], "type": "deposit", "amount": "10",
                                                    "date": tomorrow}, headers=anna)
    zero = _add(client, anna, account_id=world["cash"], type="deposit", amount="0")
    buy = _add(client, anna, account_id=world["cash"], type="buy", amount="10")
    foreign = _add(client, world["bartek"], account_id=world["cash"], type="deposit", amount="10")

    assert [(r.status_code, r.json()["code"]) for r in (wrong, future, zero, buy, foreign)] == [
        (422, "wrong_account_kind"), (422, "date_in_future"), (422, "validation_error"), (422, "validation_error"),
        (404, "not_found")]


def test_only_manual_operations_can_be_deleted(client: TestClient, world: dict, engine: Engine) -> None:
    anna, cash = world["anna"], world["cash"]
    manual_id = _add(client, anna, account_id=cash, type="deposit", amount="50").json()["id"]
    with Session(engine) as db:
        imported = Transaction(account_id=cash, type="deposit", xtb_type="Deposit", external_id="xtb-1",
                               occurred_at=dt.datetime(2026, 9, 1, 8, tzinfo=dt.UTC), amount=Decimal("10"),
                               currency="PLN", comment="", raw={})
        db.add(imported)
        db.commit()
        imported_id = imported.id

    foreign = client.delete(f"/api/transactions/{manual_id}", headers=world["bartek"])
    xtb = client.delete(f"/api/transactions/{imported_id}", headers=anna)
    ok = client.delete(f"/api/transactions/{manual_id}", headers=anna)

    assert [(r.status_code, r.json()["code"]) for r in (foreign, xtb)] == [(404, "not_found"), (409, "not_manual")]
    assert ok.status_code == 204
    assert [t["id"] for t in client.get("/api/transactions", headers=anna).json()] == [imported_id]
