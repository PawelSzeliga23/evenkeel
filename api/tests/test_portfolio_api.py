import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Transaction, User
from app.valuation.service import mark_stale
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]


def _user_id(db: Session, email: str) -> int:
    return db.scalar(select(User.id).where(User.email == email))


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = _user_id(db, "anna@portfolio.dev")
        account_id = seed_holdings(db, user_id, seed_market(db))
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id}


def test_summary_shows_value_gain_day_change_income_and_allocation(client: TestClient, world: dict) -> None:
    body = client.get("/api/portfolio/summary", headers=world["anna"]).json()

    assert {key: body[key] for key in (
        "as_of", "value_pln", "cash_pln", "invested_pln", "total_gain_pln", "total_gain_pct",
        "day_change_pln", "day_change_pct", "dividends_net_pln", "interest_net_pln", "approximate_positions",
        "recalculating",
    )} == {
        "as_of": "2026-09-26", "value_pln": "10829.70", "cash_pln": "5729.70", "invested_pln": "10000.00",
        "total_gain_pln": "829.70", "total_gain_pct": "8.30", "day_change_pln": "800.00", "day_change_pct": "7.98",
        "dividends_net_pln": "34.00", "interest_net_pln": "0.00", "approximate_positions": 0, "recalculating": False,
    }
    assert body["by_kind"] == [
        {"key": "cash", "name": "Gotówka", "value_pln": "5729.70", "share_pct": "52.91"},
        {"key": "etf", "name": "ETF", "value_pln": "5100.00", "share_pct": "47.09"},
    ]
    assert body["by_account"] == [
        {"key": str(world["account_id"]), "name": "XTB IKE", "value_pln": "10829.70", "share_pct": "100.00"},
    ]


def test_summary_filtered_by_own_account_and_foreign_account_is_404(client: TestClient, world: dict) -> None:
    own = client.get("/api/portfolio/summary", params={"account_id": world["account_id"]}, headers=world["anna"])
    foreign = client.get("/api/portfolio/summary", params={"account_id": world["account_id"]}, headers=world["bartek"])

    assert own.json()["value_pln"] == "10829.70"
    assert (foreign.status_code, foreign.json()["code"]) == (404, "not_found")


def test_user_without_data_gets_an_empty_summary(client: TestClient, world: dict) -> None:
    body = client.get("/api/portfolio/summary", headers=world["bartek"]).json()
    assert (body["as_of"], body["value_pln"], body["by_kind"], body["day_change_pln"], body["recalculating"]) == (
        None, "0.00", [], None, False)


def test_summary_says_when_a_recompute_is_pending(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        mark_stale(db, [_user_id(db, "anna@portfolio.dev")], dt.date(2026, 9, 1))
        db.commit()
    assert client.get("/api/portfolio/summary", headers=world["anna"]).json()["recalculating"] is True


def test_history_in_a_range(client: TestClient, world: dict) -> None:
    body = client.get("/api/portfolio/history", params={"from": "2026-09-24", "to": "2026-09-26"},
                      headers=world["anna"]).json()

    assert body["points"] == [
        {"date": "2026-09-24", "value_pln": "10029.70", "invested_pln": "10000.00", "net_flow_pln": "0.00",
         "twr_pct": "0.30"},
        {"date": "2026-09-25", "value_pln": "10829.70", "invested_pln": "10000.00", "net_flow_pln": "0.00",
         "twr_pct": "8.30"},
        {"date": "2026-09-26", "value_pln": "10829.70", "invested_pln": "10000.00", "net_flow_pln": "0.00",
         "twr_pct": "8.30"},
    ]
    assert body["events"] == []


def test_full_history_starts_with_the_first_deposit_and_marks_operations(client: TestClient, world: dict) -> None:
    body = client.get("/api/portfolio/history", headers=world["anna"]).json()

    assert len(body["points"]) == 210
    assert body["points"][0] == {"date": "2026-03-01", "value_pln": "10000.00", "invested_pln": "10000.00",
                                 "net_flow_pln": "10000.00", "twr_pct": "0.00"}
    assert body["events"] == [
        {"date": "2026-03-01", "type": "deposit", "amount_pln": "10000.00"},
        {"date": "2026-03-02", "type": "buy", "amount_pln": "-4304.30"},
        {"date": "2026-06-15", "type": "dividend", "amount_pln": "40.00"},
    ]


def test_portfolio_requires_login(client: TestClient) -> None:
    assert client.get("/api/portfolio/summary").status_code == 401


def test_summary_shows_all_fees(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        for external_id, amount in (("5", "-5.00"), ("6", "-2.00")):
            db.add(Transaction(account_id=world["account_id"], type="fee", xtb_type="SEC fee",
                               occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC), amount=Decimal(amount),
                               currency="PLN", external_id=external_id, comment="", raw={}))
        db.commit()

    assert client.get("/api/portfolio/summary", headers=world["anna"]).json()["fees_pln"] == "-7.00"


def test_summary_shows_the_time_weighted_return(client: TestClient, world: dict) -> None:
    anna = client.get("/api/portfolio/summary", headers=world["anna"]).json()
    bartek = client.get("/api/portfolio/summary", headers=world["bartek"]).json()

    assert (anna["twr_pct"], bartek["twr_pct"]) == ("8.30", None)
