import datetime as dt
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, Instrument, Transaction, User
from app.portfolio.closed import closed_investments
from app.scoping import UserScope
from tests.valuation_seed import seed_holdings, seed_market, seed_user

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


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _lot(db: Session, account_id: int, instrument_id: int, position: str, buy: str, sell: str, day: dt.date) -> None:
    """A fully bought-then-sold lot (matched by position, no pro-rata rounding): realized = sell − buy exactly."""
    buy_at = dt.datetime(day.year, day.month, day.day, 9, 0, tzinfo=dt.UTC)
    sell_at = dt.datetime(day.year, day.month, day.day + 1, 9, 0, tzinfo=dt.UTC)
    db.add_all([
        Transaction(account_id=account_id, instrument_id=instrument_id, type="buy", xtb_type="buy", occurred_at=buy_at,
                   amount=Decimal(f"-{buy}"), currency="PLN", quantity=Decimal("1"), price=Decimal(buy),
                   xtb_position_id=position, external_id=f"buy-{position}", comment="", raw={}),
        Transaction(account_id=account_id, instrument_id=instrument_id, type="sell", xtb_type="sell", occurred_at=sell_at,
                   amount=Decimal(sell), currency="PLN", quantity=Decimal("1"), price=Decimal(sell),
                   xtb_position_id=position, external_id=f"sell-{position}", comment="", raw={}),
    ])
    db.commit()


def test_investment_totals_reconcile_with_the_sum_of_its_rounded_sales(db: Session) -> None:
    # Two lots whose unrounded realized gain is 10.0050 zł each (a half-grosz, same direction): each sale rounds
    # (ROUND_HALF_UP) to 10.01, so the investment must total 20.02 — not money(10.0050 + 10.0050) = 20.01.
    user_id = seed_user(db)
    instrument = Instrument(xtb_ticker="LOCAL.PL", name="Local Co", currency="PLN")
    db.add(instrument)
    db.flush()
    account = Account(user_id=user_id, name="XTB", kind="broker", wrapper="regular", broker="xtb",
                      external_account_number="1", currency="PLN")
    db.add(account)
    db.flush()
    _lot(db, account.id, instrument.id, "P1", "100.0050", "110.0100", dt.date(2026, 1, 5))
    _lot(db, account.id, instrument.id, "P2", "200.0050", "210.0100", dt.date(2026, 2, 5))

    result = closed_investments(UserScope(db, db.get(User, user_id)), None, dt.date(2026, 9, 26))

    assert [sale.realized_pln for sale in result.sales] == [Decimal("10.01"), Decimal("10.01")]
    (investment,) = result.investments
    assert (investment.sold_cost_pln, investment.realized_pln, investment.total_pln) == (
        Decimal("300.02"), Decimal("20.02"), Decimal("20.02"))
    assert result.totals.sold_cost_pln == Decimal("300.02")
    assert result.totals.realized_pln == Decimal("20.02")
