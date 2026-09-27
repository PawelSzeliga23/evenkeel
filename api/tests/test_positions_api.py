import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Price, Transaction, User
from tests.valuation_seed import seed_holdings, seed_market, seed_snapshot

LoginAs = Callable[[str], dict[str, str]]
ON = {"date": "2026-09-26"}


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = seed_holdings(db, user_id, instrument_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id, "instrument_id": instrument_id}


def _detail(client: TestClient, world: dict, who: str = "anna") -> dict:
    url = f"/api/positions/{world['account_id']}/{world['instrument_id']}"
    return client.get(url, params=ON, headers=world[who]).json()


def test_positions_list_open_instruments_and_cash_with_the_profit_breakdown(client: TestClient, world: dict) -> None:
    instrument, cash = client.get("/api/positions", params=ON, headers=world["anna"]).json()

    assert Decimal(instrument["quantity"]) == 2 and Decimal(instrument["price"]) == 600
    assert {key: instrument[key] for key in (
        "kind", "ticker", "name", "currency", "price_date", "price_source", "value_pln", "cost_pln", "unrealized_pln",
        "unrealized_pct", "price_effect_pln", "fx_effect_pln", "dividends_net_pln", "realized_pln", "day_change_pln",
        "share_pct", "flags",
    )} == {
        "kind": "instrument", "ticker": "SXR8.DE", "name": "Core S&P 500", "currency": "EUR", "price_date": "2026-09-25",
        "price_source": "provider", "value_pln": "5100.00", "cost_pln": "4304.30", "unrealized_pln": "795.70",
        "unrealized_pct": "18.49", "price_effect_pln": "855.70", "fx_effect_pln": "-60.00", "dividends_net_pln": "34.00",
        "realized_pln": "0.00", "day_change_pln": "800.00", "share_pct": "47.09", "flags": [],
    }
    assert (cash["kind"], cash["name"], cash["currency"], cash["value_pln"], cash["share_pct"]) == (
        "cash", "Gotówka", "PLN", "5729.70", "52.91")
    assert Decimal(cash["quantity"]) == Decimal("5729.70")


def test_position_without_provider_prices_is_valued_from_xtb(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.query(Price).delete()
        db.commit()

    instrument = client.get("/api/positions", params=ON, headers=world["anna"]).json()[0]

    assert (instrument["price_source"], instrument["price"], instrument["price_date"], instrument["value_pln"],
            instrument["flags"]) == ("xtb", None, "2026-03-02", "4304.30", ["xtb_price"])


def test_positions_are_private_and_filterable_by_own_account(client: TestClient, world: dict) -> None:
    assert client.get("/api/positions", params=ON, headers=world["bartek"]).json() == []
    foreign = client.get("/api/positions", params={**ON, "account_id": world["account_id"]}, headers=world["bartek"])
    own = client.get("/api/positions", params={**ON, "account_id": world["account_id"]}, headers=world["anna"])
    assert foreign.status_code == 404
    assert len(own.json()) == 2


def test_position_detail_lists_lots_income_transactions_and_reconciles_with_xtb(
    client: TestClient, world: dict, engine: Engine
) -> None:
    with Session(engine) as db:
        seed_snapshot(db, world["account_id"], world["instrument_id"], "2")

    body = _detail(client, world)

    assert body["position"]["value_pln"] == "5100.00"
    (lot,) = body["lots"]
    assert Decimal(lot["quantity"]) == 2 and Decimal(lot["stop_loss"]) == 450
    assert {key: lot[key] for key in ("position_id", "opened_on", "open_price", "cost_pln", "value_pln", "gain_pln",
                                      "price_effect_pln", "fx_effect_pln", "holding_days", "take_profit")} == {
        "position_id": "777", "opened_on": "2026-03-02", "open_price": "500.5000", "cost_pln": "4304.30",
        "value_pln": "5100.00", "gain_pln": "795.70", "price_effect_pln": "855.70", "fx_effect_pln": "-60.00",
        "holding_days": 208, "take_profit": None,
    }
    assert body["sales"] == []
    assert [(i["date"], i["type"], i["amount_pln"]) for i in body["income"]] == [
        ("2026-06-15", "dividend", "40.00"), ("2026-06-15", "withholding_tax", "-6.00")]
    assert [t["type"] for t in body["transactions"]] == ["withholding_tax", "dividend", "buy"]
    reconciliation = body["reconciliation"]
    assert reconciliation["status"] == "ok"
    assert Decimal(reconciliation["xtb_quantity"]) == Decimal(reconciliation["calculated_quantity"]) == 2


@pytest.mark.parametrize(("volume", "status"), [("3", "mismatch"), (None, "no_snapshot")])
def test_reconciliation_reports_mismatch_and_missing_snapshot(
    client: TestClient, world: dict, engine: Engine, volume: str | None, status: str
) -> None:
    if volume is not None:
        with Session(engine) as db:
            seed_snapshot(db, world["account_id"], world["instrument_id"], volume)
    assert _detail(client, world)["reconciliation"]["status"] == status


def test_sold_out_position_leaves_the_list_but_keeps_its_realized_gain(
    client: TestClient, world: dict, engine: Engine
) -> None:
    with Session(engine) as db:
        db.add(Transaction(account_id=world["account_id"], instrument_id=world["instrument_id"], type="sell",
                           xtb_type="Stock sale", occurred_at=dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.UTC),
                           amount=Decimal("5000"), currency="PLN", quantity=Decimal("2"), price=Decimal("600"),
                           xtb_position_id="777", external_id="5", comment="CLOSE BUY 2/2 @ 600", raw={}))
        db.commit()

    positions = client.get("/api/positions", params=ON, headers=world["anna"]).json()
    body = _detail(client, world)

    assert [(p["kind"], p["value_pln"], p["share_pct"]) for p in positions] == [("cash", "10729.70", "100.00")]
    assert (Decimal(body["position"]["quantity"]), body["position"]["realized_pln"], body["lots"]) == (0, "695.70", [])
    (sale,) = body["sales"]
    assert {key: sale[key] for key in ("date", "proceeds_pln", "cost_pln", "realized_pln", "position_id", "matched")} == {
        "date": "2026-09-01", "proceeds_pln": "5000.00", "cost_pln": "4304.30", "realized_pln": "695.70",
        "position_id": "777", "matched": True,
    }


def test_someone_elses_position_is_404(client: TestClient, world: dict) -> None:
    response = client.get(f"/api/positions/{world['account_id']}/{world['instrument_id']}", headers=world["bartek"])
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
