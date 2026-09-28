import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Transaction, User
from tests.valuation_seed import seed_holdings, seed_market

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/portfolio/closed"


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = seed_holdings(db, user_id, instrument_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id, "instrument_id": instrument_id}


def _add(engine: Engine, world: dict, external_id: str, type_: str, amount: str, **fields: object) -> None:
    with Session(engine) as db:
        db.add(Transaction(account_id=world["account_id"], instrument_id=world["instrument_id"], type=type_,
                           xtb_type=type_, occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC),
                           amount=Decimal(amount), currency="PLN", external_id=external_id, comment="", raw={},
                           **fields))
        db.commit()


def _sell_one(engine: Engine, world: dict, external_id: str) -> None:
    _add(engine, world, external_id, "sell", "2550.00", quantity=Decimal("1"), price=Decimal("600"),
         xtb_position_id="777")


def test_partial_sale_with_dividends_and_fees(client: TestClient, world: dict, engine: Engine) -> None:
    _sell_one(engine, world, "5")
    _add(engine, world, "6", "fee", "-5.00")

    body = client.get(URL, headers=world["anna"]).json()

    (sale,) = body["sales"]
    assert {key: sale[key] for key in (
        "ticker", "opened_on", "closed_on", "holding_days", "cost_pln", "proceeds_pln", "realized_pln",
        "price_effect_pln", "fx_effect_pln", "return_pct", "matched",
    )} == {
        "ticker": "SXR8.DE", "opened_on": "2026-03-02", "closed_on": "2026-09-25", "holding_days": 207,
        "cost_pln": "2152.15", "proceeds_pln": "2550.00", "realized_pln": "397.85", "price_effect_pln": "427.85",
        "fx_effect_pln": "-30.00", "return_pct": "18.49", "matched": True,
    }
    (investment,) = body["investments"]
    assert {key: investment[key] for key in (
        "status", "first_buy", "last_sale", "sold_cost_pln", "realized_pln", "dividends_net_pln", "fees_pln",
        "total_pln", "return_pct",
    )} == {
        "status": "partial", "first_buy": "2026-03-02", "last_sale": "2026-09-25", "sold_cost_pln": "2152.15",
        "realized_pln": "397.85", "dividends_net_pln": "34.00", "fees_pln": "-5.00", "total_pln": "426.85",
        "return_pct": "19.83",
    }
    assert body["totals"] == {"sold_cost_pln": "2152.15", "realized_pln": "397.85", "dividends_net_pln": "34.00",
                              "fees_pln": "-5.00", "total_pln": "426.85", "return_pct": "19.83"}


def test_everything_sold_is_closed(client: TestClient, world: dict, engine: Engine) -> None:
    _sell_one(engine, world, "5")
    _sell_one(engine, world, "6")

    body = client.get(URL, params={"account_id": world["account_id"]}, headers=world["anna"]).json()

    assert [s["realized_pln"] for s in body["sales"]] == ["397.85", "397.85"]
    (investment,) = body["investments"]
    assert (investment["status"], investment["sold_cost_pln"], investment["total_pln"]) == (
        "closed", "4304.30", "829.70")  # 795.70 realized + 34.00 dividends


def test_nothing_sold_gives_empty_lists_and_zero_totals(client: TestClient, world: dict) -> None:
    body = client.get(URL, headers=world["bartek"]).json()

    assert (body["sales"], body["investments"]) == ([], [])
    assert body["totals"] == {"sold_cost_pln": "0.00", "realized_pln": "0.00", "dividends_net_pln": "0.00",
                              "fees_pln": "0.00", "total_pln": "0.00", "return_pct": None}


def test_foreign_account_filter_is_404(client: TestClient, world: dict) -> None:
    response = client.get(URL, params={"account_id": world["account_id"]}, headers=world["bartek"])
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
