from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.models import Instrument, User
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/portfolio/exposure"


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = seed_holdings(db, user_id, seed_market(db))
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id}


def test_exposure_now_and_over_time(client: TestClient, world: dict) -> None:
    body = client.get(URL, params={"from": "2026-09-24", "to": "2026-09-25"}, headers=world["anna"]).json()

    assert body["as_of"] == "2026-09-26"
    assert body["current"] == [
        {"currency": "PLN", "value_pln": "5729.70", "share_pct": "52.91"},
        {"currency": "EUR", "value_pln": "5100.00", "share_pct": "47.09"},
    ]
    assert body["history"] == [
        {"date": "2026-09-24", "values": {"EUR": "4300.00", "PLN": "5729.70"}},  # 2 × 500 EUR × 4.30
        {"date": "2026-09-25", "values": {"EUR": "5100.00", "PLN": "5729.70"}},
    ]


def test_instrument_without_a_known_currency_is_unknown(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.execute(update(Instrument).values(currency=None))
        db.commit()

    current = client.get(URL, params={"account_id": world["account_id"]}, headers=world["anna"]).json()["current"]

    assert [(item["currency"], item["value_pln"]) for item in current] == [("PLN", "5729.70"), ("unknown", "5100.00")]


def test_no_valuations_and_foreign_account(client: TestClient, world: dict) -> None:
    empty = client.get(URL, headers=world["bartek"]).json()
    foreign = client.get(URL, params={"account_id": world["account_id"]}, headers=world["bartek"])

    assert empty == {"as_of": None, "current": [], "history": []}
    assert (foreign.status_code, foreign.json()["code"]) == (404, "not_found")
