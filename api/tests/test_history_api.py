import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import BondSeries, Instrument, Transaction

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    cash = client.post("/api/accounts", json={"name": "Portfel domowy", "kind": "cash"}, headers=anna).json()["id"]
    xtb = client.post("/api/accounts", json={"name": "XTB", "kind": "broker", "broker": "xtb",
                                             "external_account_number": "1"}, headers=anna).json()["id"]
    bonds = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=anna).json()["id"]
    with Session(engine) as db:
        db.merge(BondSeries(series="EDO0136", bond_type="EDO", issue_month=dt.date(2026, 1, 1), maturity_months=120,
                            first_period_rate=Decimal("6.00"), margin=Decimal("2.00"),
                            early_redemption_fee=Decimal("3.00"), interest_mode="capitalized", rate_basis="cpi"))
        cdr = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", category="STOCK", currency="PLN",
                         exchange_suffix="PL", price_symbol="cdr", price_symbol_overridden=False)
        db.add(cdr)
        db.flush()
        db.add(Transaction(account_id=xtb, instrument_id=cdr.id, type="buy", xtb_type="Stock purchase",
                           external_id="x1", occurred_at=dt.datetime(2026, 3, 2, 9, tzinfo=dt.UTC),
                           amount=Decimal("-500"), currency="PLN", quantity=Decimal("2"), price=Decimal("250"),
                           comment="OPEN BUY 2 @ 250", raw={}))
        db.commit()
        cdr_id = cdr.id
    client.post("/api/transactions", json={"account_id": cash, "type": "deposit", "amount": "1000",
                                           "date": "2026-03-01", "comment": "pensja"}, headers=anna)
    client.post("/api/bonds", json={"account_id": bonds, "bond_type": "EDO", "quantity": 10,
                                    "purchase_date": "2026-01-15"}, headers=anna)
    savings = client.post("/api/savings-accounts", json={
        "name": "Oszczędności", "wrapper": "regular", "capitalization": "monthly", "annual_rate": "5",
        "rate_valid_from": "2026-02-01", "first_deposit": {"date": "2026-02-01", "amount": "10000"}},
        headers=anna).json()["account_id"]
    return {"anna": anna, "bartek": bartek, "cash": cash, "xtb": xtb, "bonds": bonds, "savings": savings,
            "cdr": cdr_id}


def _items(client: TestClient, headers: dict, **params: object) -> list[dict]:
    response = client.get("/api/history", params={"to": "2026-03-31", **params}, headers=headers)
    assert response.status_code == 200, response.json()
    return response.json()["items"]


def test_everything_in_one_list_newest_first(client: TestClient, world: dict) -> None:
    items = _items(client, world["anna"])

    assert [(i["date"], i["kind"], i["type"]) for i in items] == [
        ("2026-03-31", "savings_interest", "savings_interest"),
        ("2026-03-02", "transaction", "buy"),
        ("2026-03-01", "transaction", "deposit"),
        ("2026-02-28", "savings_interest", "savings_interest"),
        ("2026-02-01", "savings_flow", "savings_deposit"),
        ("2026-01-15", "bond_purchase", "bond_purchase"),
    ]
    by_type = {i["type"]: i for i in items}
    assert (by_type["buy"]["name"], by_type["buy"]["ticker"], by_type["buy"]["amount"], by_type["buy"]["delete"]) == (
        "CD Projekt", "CDR.PL", "-500.0000", None)
    assert (by_type["deposit"]["note"], by_type["deposit"]["delete"]["target"]) == ("pensja", "transaction")
    assert (by_type["bond_purchase"]["name"], by_type["bond_purchase"]["amount"],
            by_type["bond_purchase"]["delete"]["target"]) == ("EDO0136", "-1000.00", "bond")
    assert (by_type["savings_deposit"]["amount"], by_type["savings_deposit"]["delete"]["target"]) == (
        "10000.0000", "savings_flow")
    # February: 28 days × 10 000 × 5 % / 365 = 38.36 gross, 7.29 tax
    assert (items[3]["amount"], items[3]["tax"], items[3]["delete"]) == ("31.07", "7.29", None)


def test_filters(client: TestClient, world: dict) -> None:
    anna = world["anna"]

    assert [i["type"] for i in _items(client, anna, account_id=world["cash"])] == ["deposit"]
    assert [i["type"] for i in _items(client, anna, type="bond_purchase")] == ["bond_purchase"]
    assert [i["type"] for i in _items(client, anna, instrument_id=world["cdr"])] == ["buy"]
    assert [i["date"] for i in _items(client, anna, **{"from": "2026-03-01", "to": "2026-03-01"})] == ["2026-03-01"]
    assert [i["type"] for i in _items(client, anna, q="projekt")] == ["buy"]
    assert [i["type"] for i in _items(client, anna, q="PENSJA")] == ["deposit"]


def test_pages_follow_each_other_without_gaps(client: TestClient, world: dict) -> None:
    anna, seen, cursor = world["anna"], [], None
    for _ in range(10):
        params = {"to": "2026-03-31", "limit": 2, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/history", params=params, headers=anna).json()
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert seen == [i["id"] for i in _items(client, anna)]
    assert len(seen) == len(set(seen)) == 6


def test_history_is_private(client: TestClient, world: dict) -> None:
    bartek = world["bartek"]
    foreign = client.get("/api/history", params={"account_id": world["cash"]}, headers=bartek)
    bad_cursor = client.get("/api/history", params={"cursor": "zly"}, headers=bartek)

    assert _items(client, bartek) == []
    assert [(r.status_code, r.json()["code"]) for r in (foreign, bad_cursor)] == [
        (404, "not_found"), (422, "bad_cursor")]


def test_cursor_between_entries_of_the_same_day(client: TestClient, world: dict) -> None:
    anna = world["anna"]
    for amount in ("10", "20"):
        client.post("/api/transactions", json={"account_id": world["cash"], "type": "deposit", "amount": amount,
                                               "date": "2026-03-01", "comment": f"wpłata {amount}"}, headers=anna)
    seen, cursor = [], None
    for _ in range(20):
        params = {"to": "2026-03-31", "limit": 1, **({"cursor": cursor} if cursor else {})}
        page = client.get("/api/history", params=params, headers=anna).json()
        seen += [i["id"] for i in page["items"]]
        cursor = page["next_cursor"]
        if cursor is None:
            break

    assert seen == [i["id"] for i in _items(client, anna)]
    assert len(seen) == len(set(seen)) == 8
