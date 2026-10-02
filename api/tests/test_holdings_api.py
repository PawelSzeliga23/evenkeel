import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, BondHolding, BondSeries, SavingsAccount, SavingsBalance, SavingsRate, Transaction, User
from tests.valuation_seed import FRI, seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
AT_FRI = dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC)


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        sxr8 = seed_market(db)
        account_id = seed_holdings(db, user_id, sxr8)
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "user_id": user_id, "account_id": account_id, "sxr8": sxr8}


def _get(client: TestClient, headers: dict, **params: object) -> dict:
    response = client.get("/api/analytics/holdings", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _trade(engine: Engine, world: dict, type_: str, amount: str, quantity: str) -> None:
    with Session(engine) as db:
        db.add(Transaction(account_id=world["account_id"], instrument_id=world["sxr8"], type=type_, xtb_type=type_,
                           occurred_at=AT_FRI, amount=Decimal(amount), currency="PLN", quantity=Decimal(quantity),
                           price=Decimal("600"), external_id=f"x-{type_}", comment="", raw={}))
        db.commit()
        valuate(db, world["user_id"])


def test_whole_history_gain_is_the_summary_gain(client: TestClient, world: dict) -> None:
    body = _get(client, world["anna"], period="all")

    (item,) = body["items"]
    assert (item["key"], item["kind"], item["ticker"], item["category"]) == (
        f"i:{world['sxr8']}", "instrument", "SXR8.DE", "etf")
    assert (item["value_pln"], item["gain_pln"]) == ("5074.50", "804.20")  # 5074.50 − 4304.30 + 40 − 6
    assert item["gain_pct"] == "18.68"  # 804.20 / 4304.30
    assert item["accounts"] == [{"account_id": world["account_id"], "name": "XTB IKE", "value_pln": "5074.50",
                                 "gain_pln": "804.20"}]
    assert body["by_kind"] == [{"key": "etf", "name": "ETF", "value_pln": "5074.50", "gain_pln": "804.20",
                                "gain_pct": "18.68"}]


def test_day_gain_is_the_change_since_the_previous_session(client: TestClient, world: dict) -> None:
    body = _get(client, world["anna"], period="1d")

    assert body["period"] == {"start": "2026-09-25", "end": "2026-09-25"}  # up to the last session, as on Pulpit
    (item,) = body["items"]
    assert item["gain_pln"] == "796.00"  # Fri 5074.50 − Thu 4278.50 (2 × 500 × 4.30 − 0.5 %)


def test_a_purchase_in_the_period_is_not_a_gain(client: TestClient, world: dict, engine: Engine) -> None:
    _trade(engine, world, "buy", "-2550", "1")  # 1 × 600 EUR × 4.25 on Friday

    (item,) = _get(client, world["anna"], period="1w")["items"]

    assert item["value_pln"] == "7611.75"  # 3 × 600 × 4.25 − 0.5 %
    assert item["gain_pln"] == "783.25"  # 7611.75 − 4278.50 − 2550


def test_a_sale_in_the_period_keeps_its_realized_gain(client: TestClient, world: dict, engine: Engine) -> None:
    _trade(engine, world, "sell", "5100", "2")

    (item,) = _get(client, world["anna"], period="1w")["items"]

    assert (item["value_pln"], item["gain_pln"]) == ("0.00", "821.50")  # 0 − 4278.50 + 5100


def test_bonds_gain_through_their_flows(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        bonds = Account(user_id=world["user_id"], name="Obligacje", kind="bonds", currency="PLN")
        db.add_all([bonds, BondSeries(series="EDO0336", bond_type="EDO", issue_month=dt.date(2026, 3, 1),
                                      maturity_months=120, first_period_rate=Decimal("6.25"), margin=Decimal("2.00"),
                                      early_redemption_fee=Decimal("3.00"), interest_mode="capitalized",
                                      rate_basis="cpi")])
        db.flush()
        db.add(BondHolding(account_id=bonds.id, bond_type="EDO", series="EDO0336", quantity=10,
                           purchase_date=dt.date(2026, 3, 2)))
        db.commit()
        valuate(db, world["user_id"])

    items = {item["key"]: item for item in _get(client, world["anna"], period="all")["items"]}

    bond = items["b:EDO0336"]
    assert (bond["kind"], bond["name"], bond["category"]) == ("bond", "EDO0336", "bonds")
    assert Decimal(bond["gain_pln"]) == Decimal(bond["value_pln"]) - 1000  # value − the purchase
    assert Decimal(bond["gain_pln"]) > 0


def test_one_instrument_on_two_accounts_is_one_item(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        seed_holdings(db, world["user_id"], world["sxr8"], number="11111111")
        valuate(db, world["user_id"])

    (item,) = _get(client, world["anna"], period="all")["items"]

    assert item["value_pln"] == "10149.00" and len(item["accounts"]) == 2


def test_account_filter_and_foreign_accounts(client: TestClient, world: dict) -> None:
    own = client.get("/api/analytics/holdings", params={"account_id": world["account_id"]}, headers=world["anna"])
    foreign = client.get("/api/analytics/holdings", params={"account_id": world["account_id"]}, headers=world["bartek"])

    assert own.status_code == 200 and len(own.json()["items"]) == 1
    assert foreign.status_code == 404


def test_no_valuation_gives_an_empty_answer(client: TestClient, world: dict) -> None:
    body = _get(client, world["bartek"], period="1m")

    assert body == {"period": None, "items": [], "by_account": [], "by_kind": [], "recalculating": False}


def test_unknown_period_is_422(client: TestClient, world: dict) -> None:
    assert client.get("/api/analytics/holdings", params={"period": "5y"}, headers=world["anna"]).status_code == 422


def test_savings_gain_is_the_interest(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        account = Account(user_id=world["user_id"], name="Konto oszcz.", kind="savings", currency="PLN")
        db.add(account)
        db.flush()
        savings = SavingsAccount(account_id=account.id, capitalization="monthly")
        db.add(savings)
        db.flush()
        db.add_all([SavingsRate(savings_account_id=savings.id, valid_from=dt.date(2026, 9, 1), annual_rate=Decimal("5")),
                    SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 9, 1),
                                   balance=Decimal("10000"))])
        db.commit()
        valuate(db, world["user_id"])
        savings_id = savings.id

    body = _get(client, world["anna"], period="all")
    item = {item["key"]: item for item in body["items"]}[f"s:{savings_id}"]

    assert (item["kind"], item["name"], item["category"]) == ("savings", "Konto oszcz.", "savings")
    assert Decimal(item["gain_pln"]) == Decimal(item["value_pln"]) - 10000  # the deposit is not a gain
    assert [group["key"] for group in body["by_kind"]] == ["etf", "savings"]


def test_a_conversion_in_the_period_moves_the_value_not_a_gain(client: TestClient, world: dict) -> None:
    created = client.post("/api/corporate-actions", headers=world["anna"], json={
        "instrument_id": world["sxr8"], "type": "conversion", "effective_date": "2026-09-25", "ratio_from": "1",
        "ratio_to": "1", "target_ticker": "CSPX.UK"})
    assert created.status_code == 201

    items = {item["ticker"]: item for item in _get(client, world["anna"], period="all")["items"]}

    assert (items["SXR8.DE"]["value_pln"], items["SXR8.DE"]["gain_pln"]) == ("0.00", "8.20")  # 4278.50 − 4304.30 + 34
    target = items["CSPX.UK"]
    assert Decimal(target["gain_pln"]) == Decimal(target["value_pln"]) - Decimal("4278.50")  # from the value it got


def test_a_closed_savings_account_is_left_out(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        account = Account(user_id=world["user_id"], name="Stare konto", kind="savings", currency="PLN")
        db.add(account)
        db.flush()
        savings = SavingsAccount(account_id=account.id, capitalization="monthly")
        db.add(savings)
        db.flush()
        db.add(SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 9, 1), balance=Decimal("0")))
        db.commit()
        valuate(db, world["user_id"])

    keys = [item["key"] for item in _get(client, world["anna"], period="1m")["items"]]

    assert keys == [f"i:{world['sxr8']}"]
