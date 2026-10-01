import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, DailyValuation, User
from app.valuation.service import mark_stale

LoginAs = Callable[[str], dict[str, str]]

FIVE_DAYS = [
    ("2026-01-01", "1000", "1000"), ("2026-01-02", "1100", "0"), ("2026-01-03", "990", "0"),
    ("2026-01-04", "1490", "500"), ("2026-01-05", "1639", "0"),
]


def seed_days(engine: Engine, email: str, rows: list[tuple[str, str, str]], name: str = "Gotówka") -> int:
    """A cash account of `email` with one valuation per (day, value, flow); returns the account id."""
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == email))
        account = Account(user_id=user_id, name=name, kind="cash", currency="PLN")
        db.add(account)
        db.flush()
        db.add_all(
            DailyValuation(user_id=user_id, account_id=account.id, date=dt.date.fromisoformat(day),
                           value_pln=Decimal(value), cost_pln=Decimal(value), net_flow_pln=Decimal(flow))
            for day, value, flow in rows
        )
        db.commit()
        return account.id


@pytest.fixture
def anna(client: TestClient, login_as: LoginAs) -> dict[str, str]:
    return login_as("anna@portfolio.dev")


def test_analytics_of_the_whole_history(client: TestClient, anna: dict, engine: Engine) -> None:
    seed_days(engine, "anna@portfolio.dev", FIVE_DAYS)
    body = client.get("/api/analytics", headers=anna).json()

    assert body["period"] == {"start": "2026-01-01", "end": "2026-01-05", "days": 5, "annualized": False}
    assert body["profit_pln"] == "139.00"
    assert body["twr"] == {"period_pct": "8.90", "annual_pct": None}
    assert body["xirr"]["period_pct"] is not None and body["xirr"]["annual_pct"] is None
    assert (body["volatility_pct"], body["sharpe"], body["short_sample"]) == (None, None, True)
    assert body["max_drawdown"] == {
        "pct": "-10.00", "peak_date": "2026-01-02", "trough_date": "2026-01-03", "recovered_on": None,
    }
    assert body["current_drawdown_pct"] == "-1.00"
    assert body["best_day"] == {"date": "2026-01-02", "pct": "10.00", "pln": "100.00"}
    assert body["worst_day"] == {"date": "2026-01-03", "pct": "-10.00", "pln": "-110.00"}
    assert body["drawdown_series"][2] == {"date": "2026-01-03", "pct": "-10.00"}
    assert body["monthly"] == [
        {"year": 2026, "months": ["8.90"] + [None] * 11, "year_pct": "8.90", "first_partial_month": None},
    ]
    assert body["recalculating"] is False


def test_ytd_starts_from_the_last_value_of_the_previous_year(client: TestClient, anna: dict, engine: Engine) -> None:
    seed_days(engine, "anna@portfolio.dev", [
        ("2025-12-30", "1000", "1000"), ("2025-12-31", "1100", "0"), ("2026-01-02", "1210", "0"),
    ])
    body = client.get("/api/analytics", params={"period": "ytd"}, headers=anna).json()

    assert body["period"] == {"start": "2026-01-01", "end": "2026-01-02", "days": 2, "annualized": False}
    assert (body["profit_pln"], body["twr"]["period_pct"]) == ("110.00", "10.00")
    assert [row["year"] for row in body["monthly"]] == [2026, 2025]
    assert body["monthly"][1]["first_partial_month"] == 12


def test_analytics_of_selected_accounts(client: TestClient, anna: dict, login_as: LoginAs, engine: Engine) -> None:
    first = seed_days(engine, "anna@portfolio.dev", FIVE_DAYS)
    seed_days(engine, "anna@portfolio.dev", [("2026-01-01", "500", "500"), ("2026-01-05", "400", "0")], name="Drugie")
    bartek = login_as("bartek@portfolio.dev")

    own = client.get("/api/analytics", params={"account_id": first}, headers=anna).json()
    foreign = client.get("/api/analytics", params={"account_id": first}, headers=bartek)

    assert own["profit_pln"] == "139.00"
    assert (foreign.status_code, foreign.json()["code"]) == (404, "not_found")
    assert client.get("/api/analytics", headers=anna).json()["profit_pln"] == "39.00"  # 139 − 100


def test_user_without_valuations_gets_an_empty_answer(client: TestClient, anna: dict) -> None:
    body = client.get("/api/analytics", headers=anna).json()

    assert (body["period"], body["profit_pln"], body["twr"], body["max_drawdown"]) == (
        None, "0.00", {"period_pct": None, "annual_pct": None}, None)
    assert (body["drawdown_series"], body["monthly"], body["best_day"]) == ([], [], None)


def test_unknown_period_is_422(client: TestClient, anna: dict) -> None:
    assert client.get("/api/analytics", params={"period": "5y"}, headers=anna).status_code == 422


def test_analytics_says_when_a_recompute_is_pending(client: TestClient, anna: dict, engine: Engine) -> None:
    seed_days(engine, "anna@portfolio.dev", FIVE_DAYS)
    with Session(engine) as db:
        mark_stale(db, [db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))], dt.date(2026, 1, 1))
        db.commit()
    assert client.get("/api/analytics", headers=anna).json()["recalculating"] is True


def test_analytics_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/analytics").status_code == 401
