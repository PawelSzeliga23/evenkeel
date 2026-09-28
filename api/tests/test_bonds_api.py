import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import BondSeries, DailyValuation

LoginAs = Callable[[str], dict[str, str]]
ON = {"date": "2026-09-26"}


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        db.add(BondSeries(series="EDO0936", bond_type="EDO", issue_month=dt.date(2026, 9, 1), maturity_months=120,
                          first_period_rate=Decimal("5.35"), margin=Decimal("2.00"),
                          early_redemption_fee=Decimal("3.00"), interest_mode="capitalized", rate_basis="cpi"))
        db.commit()
    bonds = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=anna).json()["id"]
    broker = client.post("/api/accounts", json={"name": "XTB", "kind": "broker", "broker": "xtb",
                                                "external_account_number": "1"}, headers=anna).json()["id"]
    return {"anna": anna, "bartek": bartek, "bonds": bonds, "broker": broker}


def _buy(client: TestClient, world: dict, **fields: object) -> object:
    body = {"account_id": world["bonds"], "bond_type": "EDO", "quantity": 10, "purchase_date": "2026-09-15", **fields}
    return client.post("/api/bonds", json=body, headers=world["anna"])


def test_purchase_is_valued_net_of_tax_with_its_schedule(client: TestClient, world: dict, engine: Engine) -> None:
    created = _buy(client, world)
    assert created.status_code == 201
    holding_id = created.json()["id"]

    detail = client.get(f"/api/bonds/{holding_id}", params=ON, headers=world["anna"]).json()

    assert {key: detail["bond"][key] for key in ("series", "quantity", "maturity_date", "status", "value_pln")} == {
        "series": "EDO0936", "quantity": 10, "maturity_date": "2036-09-15", "status": "active", "value_pln": "1001.30"}
    # 11 days: 100.16 per bond; early redemption: the fee takes the 0.16 zł of interest → 100.00 × 10
    assert (detail["value_per_bond"], detail["redemption_today_pln"]) == ("100.16", "1000.00")
    assert [(p["number"], p["start"], p["estimated"]) for p in detail["periods"][:2]] == [
        (1, "2026-09-15", False), (2, "2027-09-15", True)]
    with Session(engine) as db:  # recomputed in the background after the purchase
        assert db.scalar(select(DailyValuation.net_flow_pln).where(
            DailyValuation.bond_holding_id == holding_id, DailyValuation.date == dt.date(2026, 9, 15))) == Decimal(
            "1000.0000")


def test_series_outside_the_table_needs_its_rates_and_is_then_shared(client: TestClient, world: dict) -> None:
    missing = _buy(client, world, purchase_date="2026-08-20")
    added = _buy(client, world, purchase_date="2026-08-20", first_period_rate="5.60", margin="2.00")

    assert (missing.status_code, missing.json()["code"], missing.json()["details"]) == (
        422, "series_unknown", {"series": "EDO0836"})
    assert added.status_code == 201
    series = {s["series"]: s for s in client.get("/api/bond-series", headers=world["bartek"]).json()}
    assert (series["EDO0836"]["first_period_rate"], series["EDO0836"]["early_redemption_fee"],
            series["EDO0836"]["issue_month"]) == ("5.6000", "3.00", "2026-08-01")


def test_early_redemption_marks_the_purchase_redeemed(client: TestClient, world: dict) -> None:
    holding_id = _buy(client, world).json()["id"]

    updated = client.patch(f"/api/bonds/{holding_id}", json={"redeemed_at": "2026-09-20"}, headers=world["anna"])
    listed = client.get("/api/bonds", params=ON, headers=world["anna"]).json()

    assert (updated.status_code, updated.json()["redeemed_at"]) == (200, "2026-09-20")
    assert [(b["status"], b["value_pln"]) for b in listed] == [("redeemed", "0.00")]


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"account_id": "broker"}, "wrong_account_kind"),
        ({"purchase_date": "2999-01-01"}, "purchase_in_future"),
    ],
)
def test_purchase_errors(client: TestClient, world: dict, fields: dict, code: str) -> None:
    if fields.get("account_id") == "broker":
        fields = {**fields, "account_id": world["broker"]}
    response = _buy(client, world, **fields)
    assert (response.status_code, response.json()["code"]) == (422, code)


@pytest.mark.parametrize("day", ["2026-09-14", "2036-09-15"])
def test_redemption_date_must_fall_between_purchase_and_maturity(client: TestClient, world: dict, day: str) -> None:
    holding_id = _buy(client, world).json()["id"]
    response = client.patch(f"/api/bonds/{holding_id}", json={"redeemed_at": day}, headers=world["anna"])
    assert (response.status_code, response.json()["code"]) == (422, "bad_redemption_date")


def test_existing_series_cannot_be_added_again(client: TestClient, world: dict) -> None:
    response = client.post("/api/bond-series", json={"series": "EDO0936", "first_period_rate": "6", "margin": "2"},
                           headers=world["anna"])
    assert (response.status_code, response.json()["code"]) == (409, "series_exists")


def test_someone_elses_bonds_are_404(client: TestClient, world: dict) -> None:
    holding_id = _buy(client, world).json()["id"]
    foreign = [
        client.get(f"/api/bonds/{holding_id}", headers=world["bartek"]),
        client.patch(f"/api/bonds/{holding_id}", json={"note": "x"}, headers=world["bartek"]),
        client.delete(f"/api/bonds/{holding_id}", headers=world["bartek"]),
        client.post("/api/bonds", json={"account_id": world["bonds"], "bond_type": "EDO", "quantity": 1,
                                        "purchase_date": "2026-09-15"}, headers=world["bartek"]),
    ]
    assert [(r.status_code, r.json()["code"]) for r in foreign] == [(404, "not_found")] * 4
    assert client.get("/api/bonds", headers=world["bartek"]).json() == []


def test_deleting_a_purchase_removes_its_valuation(client: TestClient, world: dict, engine: Engine) -> None:
    holding_id = _buy(client, world).json()["id"]

    assert client.delete(f"/api/bonds/{holding_id}", headers=world["anna"]).status_code == 204
    with Session(engine) as db:
        assert db.scalar(select(DailyValuation.id).where(DailyValuation.bond_holding_id == holding_id)) is None
