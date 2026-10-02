import datetime as dt
from collections.abc import Callable
from decimal import ROUND_HALF_UP
from decimal import Decimal as D

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.bonds import edo
from app.models import BondSeries, Instrument, Price, User
from tests.valuation_seed import SAT, seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
CENT = D("0.01")


def money(value: D) -> D:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    """Anna: the valuation seed (SXR8.DE bought 03-02, valued to Saturday 2026-09-26) and SXRV.DE in the catalog."""
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        sxr8 = seed_market(db)
        account_id = seed_holdings(db, user_id, sxr8)
        nasdaq = Instrument(xtb_ticker="SXRV.DE", name="iShares NASDAQ 100", category="etf", currency="EUR",
                            in_catalog=True, catalog_group="ETF: USA", accumulating=True)
        db.add(nasdaq)
        db.flush()
        db.add_all([Price(instrument_id=nasdaq.id, date=dt.date(2026, 3, 2), close=D("1000"), source="yahoo"),
                    Price(instrument_id=nasdaq.id, date=dt.date(2026, 9, 25), close=D("1300"), source="yahoo")])
        db.commit()
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id, "sxr8": sxr8, "nasdaq": nasdaq.id}


def preview(client: TestClient, headers: dict, body: dict, **params: object):
    return client.post("/api/scenarios/preview", json={"name": "Podgląd", **body}, params=params, headers=headers)


def test_portfolio_without_blocks_matches_the_real_line(client: TestClient, world: dict) -> None:
    body = preview(client, world["anna"], {"base": "portfolio"}).json()
    analytics = client.get("/api/analytics", headers=world["anna"]).json()

    assert body["points"][0]["date"] == "2026-03-01"
    assert body["points"][-1] == {"date": "2026-09-26", "portfolio_pln": "10804.20", "scenario_pln": "10804.20",
                                  "invested_pln": "10000.00", "scenario_invested_pln": "10000.00"}
    assert all(p["portfolio_pln"] == p["scenario_pln"] for p in body["points"])
    assert body["scenario"] == body["portfolio"]
    assert (body["portfolio"]["profit_pln"], body["portfolio"]["twr"]) == (analytics["profit_pln"], analytics["twr"])
    assert (body["portfolio"]["value_pln"], body["portfolio"]["invested_pln"]) == ("10804.20", "10000.00")
    assert (body["notes"], body["recalculating"]) == ([], False)


def test_replace_values_the_stand_in(client: TestClient, world: dict) -> None:
    step = {"kind": "replace", "from_instrument_id": world["sxr8"], "to_instrument_id": world["nasdaq"]}

    body = preview(client, world["anna"], {"base": "portfolio", "steps": [step]}).json()

    units = D("4304.30") / (D("1000") * D("4.30") * D("1.005"))
    market = units * (D("1300") * D("4.25"))
    expected = D("5695.70") + money(market) - money(market * D("0.005"))  # cash without the 34 zł of dividends
    assert body["points"][-1]["scenario_pln"] == str(expected)
    assert body["points"][-1]["scenario_invested_pln"] == "10000.00"
    assert body["notes"] == []


def test_deposits_into_edo(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.add(BondSeries(series="EDO0336", bond_type="EDO", issue_month=dt.date(2026, 3, 1), maturity_months=120,
                          first_period_rate=D("6.25"), margin=D("2.00"), early_redemption_fee=D("3.00"),
                          interest_mode="capitalized", rate_basis="cpi"))
        db.commit()
    allocation = [{"target": {"bond": "EDO"}, "share_pct": "100"}]

    body = preview(client, world["anna"], {"base": "deposits", "allocation": allocation}).json()

    schedule = edo.periods(dt.date(2026, 3, 1), edo.Series(D("6.25"), D("2.00"), D("3.00")), {})
    assert body["points"][-1]["scenario_pln"] == str(100 * edo.net_value(edo.value(schedule, SAT), True))
    assert body["points"][-1]["scenario_invested_pln"] == "10000.00"
    assert body["scenario"]["profit_pln"] == str(100 * edo.net_value(edo.value(schedule, SAT), True) - 10000)


def test_top_ups_before_the_history_start_extend_the_timeline(client: TestClient, world: dict) -> None:
    step = {"kind": "recurring", "amount_pln": "500", "day_of_month": 2, "start": "2026-01", "end": "2026-01",
            "target": {"instrument_id": world["sxr8"]}}

    body = preview(client, world["anna"], {"base": "portfolio", "steps": [step]}).json()

    assert body["points"][0] == {"date": "2026-01-02", "portfolio_pln": None, "scenario_pln": "500.00",
                                 "invested_pln": None, "scenario_invested_pln": "500.00"}
    assert body["notes"] == ["SXR8.DE ma notowania od 03.2026; wcześniejsze kwoty zostały w gotówce."]
    assert body["scenario"]["period"]["start"] == "2026-01-02"


def test_saved_scenario_result_with_period_and_accounts(client: TestClient, world: dict) -> None:
    saved = client.post("/api/scenarios", json={"name": "Portfel", "base": "portfolio"}, headers=world["anna"]).json()
    url = f"/api/scenarios/{saved['id']}/result"

    body = client.get(url, params={"period": "1m", "account_id": world["account_id"]}, headers=world["anna"]).json()

    assert body["points"][0]["date"] == "2026-08-27"
    assert body["portfolio"]["period"] == {"start": "2026-08-27", "end": "2026-09-26", "days": 31,
                                           "annualized": False}
    foreign = client.get(url, headers=world["bartek"])
    assert (foreign.status_code, foreign.json()["code"]) == (404, "not_found")
    bartek_account = client.get(url, params={"account_id": 999}, headers=world["anna"])
    assert bartek_account.status_code == 404


def test_unknown_instrument_is_422(client: TestClient, world: dict) -> None:
    step = {"kind": "replace", "from_instrument_id": world["sxr8"], "to_instrument_id": 999999}

    for response in (
        preview(client, world["anna"], {"base": "portfolio", "steps": [step]}),
        client.post("/api/scenarios", json={"name": "X", "base": "portfolio", "steps": [step]}, headers=world["anna"]),
    ):
        assert (response.status_code, response.json()["code"]) == (422, "unknown_instrument")


def test_user_without_history_gets_an_empty_result(client: TestClient, world: dict) -> None:
    body = preview(client, world["bartek"], {"base": "portfolio"}).json()

    assert body == {"points": [], "portfolio": None, "scenario": None, "notes": [], "recalculating": False}
