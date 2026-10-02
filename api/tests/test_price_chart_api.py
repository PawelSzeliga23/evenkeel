import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import CorporateAction, Instrument, Price, Transaction, User
from app.portfolio.price_chart import thin
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        sxr8 = seed_market(db)
        account_id = seed_holdings(db, user_id, sxr8)
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "user_id": user_id, "account_id": account_id, "sxr8": sxr8}


def _url(world: dict, instrument: int | None = None) -> str:
    return f"/api/positions/{world['account_id']}/{instrument or world['sxr8']}/prices"


def _get(client: TestClient, world: dict, **params: object) -> dict:
    response = client.get(_url(world), params=params, headers=world["anna"])
    assert response.status_code == 200, response.text
    return response.json()


def test_closes_markers_and_first_buy(client: TestClient, world: dict) -> None:
    body = _get(client, world)

    assert body["currency"] == "EUR" and body["first_buy"] == "2026-03-02"
    assert body["points"] == [{"date": "2026-03-02", "close": "500.00"}, {"date": "2026-09-25", "close": "600.00"}]
    buy, dividend = body["markers"]
    assert (buy["date"], buy["kind"], buy["price"], buy["quantity"], buy["amount_pln"]) == (
        "2026-03-02", "buy", "500.5", "2", "-4304.30")
    assert buy["price_with_fx"] == "500.50"  # 4304.30 zł ÷ 2 ÷ 4.30
    assert (dividend["kind"], dividend["amount_pln"], dividend["price"]) == ("dividend", "40.00", None)


def test_from_limits_the_closes(client: TestClient, world: dict) -> None:
    assert [p["date"] for p in _get(client, world, **{"from": "2026-06-01"})["points"]] == ["2026-09-25"]


def test_thin_keeps_both_ends() -> None:
    points = [(dt.date(2020, 1, 1) + dt.timedelta(days=i), Decimal(i)) for i in range(2001)]

    kept = thin(points, 800)

    assert len(kept) <= 800 and kept[0] == points[0] and kept[-1] == points[-1]


def test_a_split_adjusts_the_marker(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.add(CorporateAction(instrument_id=world["sxr8"], type="split", effective_date=dt.date(2026, 6, 1),
                               ratio_from=Decimal(1), ratio_to=Decimal(4), source="provider"))
        db.commit()

    buy = _get(client, world)["markers"][0]

    assert (Decimal(buy["price"]), Decimal(buy["quantity"])) == (Decimal("125.125"), Decimal("8"))


def test_a_pln_instrument_has_no_price_with_fx_and_a_missing_price_takes_the_close(
    client: TestClient, world: dict, engine: Engine,
) -> None:
    with Session(engine) as db:
        cdr = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", category="stock", currency="PLN", price_symbol="CDR.WA")
        db.add(cdr)
        db.flush()
        db.add_all([Price(instrument_id=cdr.id, date=dt.date(2026, 9, 21), close=Decimal("270"), source="yahoo"),
                    Transaction(account_id=world["account_id"], instrument_id=cdr.id, type="buy", xtb_type="buy",
                                occurred_at=dt.datetime(2026, 9, 21, 10, tzinfo=dt.UTC), amount=Decimal("-810"),
                                currency="PLN", quantity=Decimal("3"), price=None, external_id="cdr", comment="",
                                raw={})])
        db.commit()
        cdr_id = cdr.id

    body = client.get(_url(world, cdr_id), headers=world["anna"]).json()

    assert body["currency"] == "PLN"
    assert (body["markers"][0]["price"], body["markers"][0]["price_with_fx"]) == ("270.00", None)


def test_foreign_account_is_404(client: TestClient, world: dict) -> None:
    assert client.get(_url(world), headers=world["bartek"]).status_code == 404
