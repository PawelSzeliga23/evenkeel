import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.models import (
    Account, BondSeries, CorporateAction, ImportRecord, Instrument, PositionLot, Price, Transaction, User, XtbSnapshot,
)
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
        "kind", "ticker", "name", "currency", "price_date", "price_source", "value_pln", "exit_fx_pln",
        "exit_spread_pln", "exit_cost_pln", "payout_pln", "spread_pct", "cost_pln", "unrealized_pln",
        "unrealized_pct", "price_effect_pln", "fx_effect_pln", "dividends_net_pln", "realized_pln", "day_change_pln",
        "share_pct", "flags",
    )} == {
        "kind": "instrument", "ticker": "SXR8.DE", "name": "Core S&P 500", "currency": "EUR", "price_date": "2026-09-25",
        "price_source": "provider", "value_pln": "5100.00", "exit_fx_pln": "25.50", "exit_spread_pln": "0.00",
        "exit_cost_pln": "25.50", "payout_pln": "5074.50", "spread_pct": None, "cost_pln": "4304.30",
        # 5 074.50 − 4 304.30 = price 855.70 + currency −60.00 − exit 25.50
        "unrealized_pln": "770.20", "unrealized_pct": "17.89", "price_effect_pln": "855.70", "fx_effect_pln": "-60.00",
        "dividends_net_pln": "34.00", "realized_pln": "0.00", "day_change_pln": "796.00", "share_pct": "46.97",
        "flags": [],
    }
    assert (cash["kind"], cash["name"], cash["currency"], cash["value_pln"], cash["exit_cost_pln"],
            cash["payout_pln"], cash["share_pct"]) == ("cash", "Gotówka", "PLN", "5729.70", "0.00", "5729.70", "53.03")
    assert Decimal(cash["quantity"]) == Decimal("5729.70")
    assert (instrument["price_currency"], cash["price_currency"]) == ("EUR", None)


def test_position_without_provider_prices_is_valued_from_xtb(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.query(Price).delete()
        db.commit()

    instrument = client.get("/api/positions", params=ON, headers=world["anna"]).json()[0]

    assert (instrument["price_source"], instrument["price"], instrument["price_currency"], instrument["price_date"],
            instrument["value_pln"], instrument["flags"]) == (
        "xtb", "2152.1500", "PLN", "2026-03-02", "4304.30", ["xtb_price"])
    assert (instrument["exit_cost_pln"], instrument["payout_pln"]) == ("0.00", "4304.30")


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
    assert {key: lot[key] for key in ("position_id", "opened_on", "open_price", "cost_pln", "value_pln",
                                      "exit_cost_pln", "gain_pln", "price_effect_pln", "fx_effect_pln",
                                      "holding_days", "take_profit")} == {
        "position_id": "777", "opened_on": "2026-03-02", "open_price": "500.5000", "cost_pln": "4304.30",
        "value_pln": "5100.00", "exit_cost_pln": "25.50", "gain_pln": "770.20", "price_effect_pln": "855.70",
        "fx_effect_pln": "-60.00", "holding_days": 208, "take_profit": None,
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


def test_reconciliation_uses_the_newest_import_with_open_positions(
    client: TestClient, world: dict, engine: Engine
) -> None:
    with Session(engine) as db:
        seed_snapshot(db, world["account_id"], world["instrument_id"], "2")
        account = db.get(Account, world["account_id"])
        record = ImportRecord(user_id=account.user_id, account_id=account.id, filename="IKE.xlsx", file_hash="1" * 64,
                              rows_added=0, rows_duplicate=0, rows_unknown=0)
        db.add(record)
        db.flush()
        db.add(XtbSnapshot(import_id=record.id, account_id=account.id, row_kind="account_summary",
                           value=Decimal("5729.70"), taken_at=dt.datetime(2026, 9, 27, 12, 0, tzinfo=dt.UTC), raw={}))
        db.commit()

    reconciliation = _detail(client, world)["reconciliation"]

    assert (reconciliation["status"], reconciliation["taken_at"][:10]) == ("ok", "2026-09-26")


def test_reconciliation_compares_quantities_at_the_stored_precision(
    client: TestClient, world: dict, engine: Engine
) -> None:
    with Session(engine) as db:  # 1:3 reverse split: 2 units become 0.666666666… (XTB reports 0.66666667)
        db.add(CorporateAction(instrument_id=world["instrument_id"], type="reverse_split",
                               effective_date=dt.date(2026, 6, 1), ratio_from=Decimal(3), ratio_to=Decimal(1),
                               source="xtb"))
        db.commit()
        seed_snapshot(db, world["account_id"], world["instrument_id"], "0.66666667")

    assert _detail(client, world)["reconciliation"]["status"] == "ok"


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


def _add(engine: Engine, world: dict, external_id: str, type_: str, amount: str, **fields: object) -> None:
    with Session(engine) as db:
        db.add(Transaction(account_id=world["account_id"], type=type_, xtb_type=type_,
                           occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC), amount=Decimal(amount),
                           currency="PLN", external_id=external_id, comment="", raw={}, **fields))
        db.commit()


def test_fees_of_the_instrument_are_a_separate_part_of_the_gain(
    client: TestClient, world: dict, engine: Engine
) -> None:
    _add(engine, world, "5", "fee", "-5.00", instrument_id=world["instrument_id"])
    _add(engine, world, "6", "fee", "-2.00")

    (instrument, _cash) = client.get("/api/positions", params=ON, headers=world["anna"]).json()

    assert instrument["fees_pln"] == "-5.00"


def test_sale_shows_its_holding_time_and_the_price_and_currency_effects(
    client: TestClient, world: dict, engine: Engine
) -> None:
    _add(engine, world, "5", "sell", "2550.00", instrument_id=world["instrument_id"], quantity=Decimal("1"),
         price=Decimal("600"), xtb_position_id="777")

    (sale,) = _detail(client, world)["sales"]

    # cost ½ × 4 304.30 = 2 152.15; currency effect 1 × 600 EUR × (4.25 − 4.30) = −30.00
    assert {key: sale[key] for key in ("opened_on", "holding_days", "realized_pln", "price_effect_pln",
                                       "fx_effect_pln")} == {
        "opened_on": "2026-03-02", "holding_days": 207, "realized_pln": "397.85", "price_effect_pln": "427.85",
        "fx_effect_pln": "-30.00",
    }


def test_bonds_and_savings_accounts_are_positions(client: TestClient, login_as: LoginAs, engine: Engine) -> None:
    headers = login_as("carol@portfolio.dev")
    with Session(engine) as db:
        db.add(BondSeries(series="EDO0936", bond_type="EDO", issue_month=dt.date(2026, 9, 1), maturity_months=120,
                          first_period_rate=Decimal("5.35"), margin=Decimal("2.00"),
                          early_redemption_fee=Decimal("3.00"), interest_mode="capitalized", rate_basis="cpi"))
        db.commit()
    bonds = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=headers).json()["id"]
    client.post("/api/bonds", json={"account_id": bonds, "bond_type": "EDO", "quantity": 10,
                                    "purchase_date": "2026-09-15"}, headers=headers)
    savings = client.post("/api/accounts", json={"name": "Konto", "kind": "savings"}, headers=headers).json()["id"]
    client.put(f"/api/savings-accounts/{savings}", json={"capitalization": "monthly"}, headers=headers)
    client.post(f"/api/savings-accounts/{savings}/balances", json={"as_of_date": "2026-09-01", "balance": "9000"},
                headers=headers)

    positions = client.get("/api/positions", params=ON, headers=headers).json()

    assert [(p["kind"], p["name"], p["category"], p["value_pln"], p["cost_pln"], p["unrealized_pln"],
             p["day_change_pln"], p["share_pct"]) for p in positions] == [
        ("bond", "EDO0936", "bonds", "1001.30", "1000.00", "1.30", "0.10", "10.01"),
        ("savings", "Konto", "savings", "9000.00", "9000.00", "0.00", "0.00", "89.99"),
    ]
    assert positions[0]["bond_holding_id"] is not None and positions[1]["savings_account_id"] is not None


def test_detail_has_the_lot_open_price_and_the_average_price(client: TestClient, world: dict) -> None:
    detail = _detail(client, world)

    assert [Decimal(lot["open_price"]) for lot in detail["lots"]] == [Decimal("500.5")]
    assert Decimal(detail["average_price"]) == Decimal("500.5")


def _without_quote_currency(engine: Engine) -> None:
    """Like an instrument the provider never quoted: no prices, so no known quote currency and no purchase rate."""
    with Session(engine) as db:
        db.query(Price).delete()
        db.execute(update(Instrument).values(currency=None))
        db.commit()


def test_lot_without_a_purchase_rate_takes_the_xtb_open_price(client: TestClient, world: dict, engine: Engine) -> None:
    _without_quote_currency(engine)

    detail = _detail(client, world)

    assert [Decimal(lot["open_price"]) for lot in detail["lots"]] == [Decimal("500.5")]
    assert Decimal(detail["average_price"]) == Decimal("500.5")
    assert (Decimal(detail["position"]["price"]), detail["position"]["price_currency"]) == (Decimal("2152.15"), "PLN")


def test_xtb_open_price_of_a_different_quantity_is_not_used(client: TestClient, world: dict, engine: Engine) -> None:
    _without_quote_currency(engine)
    with Session(engine) as db:  # e.g. XTB's figures after a split the engine does not know about
        db.execute(update(PositionLot).values(quantity=Decimal("4")))
        db.commit()

    detail = _detail(client, world)

    assert ([lot["open_price"] for lot in detail["lots"]], detail["average_price"]) == ([None], None)


def test_fully_sold_position_has_no_average_price(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.add(Transaction(
            account_id=world["account_id"], type="sell", xtb_type="sell",
            occurred_at=dt.datetime(2026, 9, 25, 9, 0, tzinfo=dt.UTC), amount=Decimal("5100"), currency="PLN",
            external_id="5", comment="", raw={}, instrument_id=world["instrument_id"], quantity=Decimal("2"),
            price=Decimal("600"), xtb_position_id="777",
        ))
        db.commit()

    detail = _detail(client, world)

    assert (detail["lots"], detail["average_price"], detail["position"]["price_currency"]) == ([], None, None)


def test_a_manual_spread_shows_in_the_position_and_its_payout(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.execute(update(Instrument).where(Instrument.id == world["instrument_id"]).values(spread_pct=Decimal("0.1")))
        db.commit()

    position = _detail(client, world)["position"]

    assert (position["spread_pct"], position["exit_fx_pln"], position["exit_spread_pln"], position["exit_cost_pln"],
            position["payout_pln"]) == ("0.1000", "25.50", "5.10", "30.60", "5069.40")
