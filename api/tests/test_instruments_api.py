import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from app.models import Instrument, PositionLot, Price, Transaction, User

LoginAs = Callable[[str], dict[str, str]]
CHECKED_AT = dt.datetime(2026, 9, 25, 21, 0, tzinfo=dt.UTC)


def _account_id(client: TestClient, headers: dict[str, str], number: str) -> int:
    response = client.post(
        "/api/accounts",
        json={"name": "XTB", "kind": "broker", "broker": "xtb", "external_account_number": number},
        headers=headers,
    )
    assert response.status_code == 201, response.json()
    return response.json()["id"]


def _seed(engine: Engine, anna_account: int, bartek_account: int) -> dict[str, int]:
    """Anna bought SXR8.DE (with prices); Bartek holds VIE.FR; nobody uses PKN.PL."""
    with Session(engine) as session:
        sxr8 = Instrument(xtb_ticker="SXR8.DE", name="Core S&P 500", category="etf", currency="EUR",
                          price_symbol="SXR8.DE", price_checked_at=CHECKED_AT)
        vie = Instrument(xtb_ticker="VIE.FR", name="Veolia")
        unused = Instrument(xtb_ticker="PKN.PL", name="Orlen")
        session.add_all([sxr8, vie, unused])
        session.flush()
        session.add(Transaction(account_id=anna_account, instrument_id=sxr8.id, type="buy", xtb_type="Stock purchase",
                                occurred_at=dt.datetime(2026, 3, 2, 9, 30, tzinfo=dt.UTC), amount=Decimal("-4304.30"),
                                currency="PLN", external_id="1002", comment="OPEN BUY 2 @ 500.50", raw={}))
        session.add(PositionLot(account_id=bartek_account, instrument_id=vie.id, xtb_position_id="888", side="buy",
                                quantity=Decimal("3"), open_price=Decimal("30.1"),
                                opened_at=dt.datetime(2026, 3, 3, tzinfo=dt.UTC), raw={}))
        session.add_all([
            Price(instrument_id=sxr8.id, date=dt.date(2026, 9, 24), close=Decimal("711.72"), source="yahoo"),
            Price(instrument_id=sxr8.id, date=dt.date(2026, 9, 25), close=Decimal("713.80"), source="yahoo"),
        ])
        session.commit()
        return {"SXR8.DE": sxr8.id, "VIE.FR": vie.id, "PKN.PL": unused.id}


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    ids = _seed(engine, _account_id(client, anna, "56216965"), _account_id(client, bartek, "11111111"))
    return {"anna": anna, "bartek": bartek, "ids": ids}


def _price_count(engine: Engine, instrument_id: int) -> int:
    with Session(engine) as session:
        return session.scalar(select(func.count()).select_from(Price).where(Price.instrument_id == instrument_id))


def test_list_shows_only_own_instruments_with_last_price(client: TestClient, world: dict) -> None:
    anna = client.get("/api/instruments", headers=world["anna"]).json()
    bartek = client.get("/api/instruments", headers=world["bartek"]).json()

    assert anna == [{
        "id": world["ids"]["SXR8.DE"], "xtb_ticker": "SXR8.DE", "name": "Core S&P 500", "category": "etf",
        "currency": "EUR", "price_symbol": "SXR8.DE", "price_symbol_overridden": False, "price_error": None,
        "spread_pct": None, "last_price": "713.80000000", "last_price_date": "2026-09-25",
    }]
    assert [(i["xtb_ticker"], i["last_price"], i["last_price_date"]) for i in bartek] == [("VIE.FR", None, None)]


def test_user_without_instruments_gets_empty_list(client: TestClient, world: dict, login_as: LoginAs) -> None:
    assert client.get("/api/instruments", headers=login_as("celina@portfolio.dev")).json() == []


def test_override_resets_prices_and_status(client: TestClient, world: dict, engine: Engine) -> None:
    sxr8 = world["ids"]["SXR8.DE"]

    response = client.patch(f"/api/instruments/{sxr8}", json={"price_symbol": " sxr8.f "}, headers=world["anna"])

    assert response.status_code == 200
    body = response.json()
    assert (body["price_symbol"], body["price_symbol_overridden"], body["last_price"]) == ("SXR8.F", True, None)
    assert _price_count(engine, sxr8) == 0
    with Session(engine) as session:
        assert session.get(Instrument, sxr8).price_checked_at is None


def test_same_override_again_keeps_prices(client: TestClient, world: dict, engine: Engine) -> None:
    sxr8 = world["ids"]["SXR8.DE"]
    client.patch(f"/api/instruments/{sxr8}", json={"price_symbol": "SXR8.F"}, headers=world["anna"])
    with Session(engine) as session:
        session.add(Price(instrument_id=sxr8, date=dt.date(2026, 9, 25), close=Decimal("714"), source="yahoo"))
        session.commit()

    response = client.patch(f"/api/instruments/{sxr8}", json={"price_symbol": "sxr8.f"}, headers=world["anna"])

    assert response.json()["last_price"] == "714.00000000"


def test_null_returns_to_automatic_mapping(client: TestClient, world: dict, engine: Engine) -> None:
    sxr8 = world["ids"]["SXR8.DE"]
    client.patch(f"/api/instruments/{sxr8}", json={"price_symbol": "SXR8.F"}, headers=world["anna"])

    body = client.patch(f"/api/instruments/{sxr8}", json={"price_symbol": None}, headers=world["anna"]).json()

    assert (body["price_symbol"], body["price_symbol_overridden"]) == (None, False)


def test_null_on_automatic_symbol_changes_nothing(client: TestClient, world: dict, engine: Engine) -> None:
    sxr8 = world["ids"]["SXR8.DE"]

    body = client.patch(f"/api/instruments/{sxr8}", json={"price_symbol": None}, headers=world["anna"]).json()

    assert (body["price_symbol"], body["last_price"]) == ("SXR8.DE", "713.80000000")
    assert _price_count(engine, sxr8) == 2


@pytest.mark.parametrize("who_and_what", [("bartek", "SXR8.DE"), ("anna", "PKN.PL"), ("anna", None)],
                         ids=["other-users-instrument", "instrument-nobody-uses", "missing-id"])
def test_foreign_or_missing_instrument_is_not_found(
    client: TestClient, world: dict, engine: Engine, who_and_what: tuple[str, str | None]
) -> None:
    who, ticker = who_and_what
    instrument_id = world["ids"][ticker] if ticker else 999_999

    response = client.patch(f"/api/instruments/{instrument_id}", json={"price_symbol": "X.DE"}, headers=world[who])

    assert (response.status_code, response.json()["code"]) == (404, "not_found")
    assert _price_count(engine, world["ids"]["SXR8.DE"]) == 2


@pytest.mark.parametrize(
    "payload",
    [{"price_symbol": ""}, {"price_symbol": "SXR8 DE"}, {"price_symbol": "A" * 41}, {"price_symbol": "SXR8/DE"},
     {"price_symbol": "."}, {"price_symbol": ".."}, {}, {"price_symbol": "X.DE", "extra": 1}],
    ids=["empty", "space", "too-long", "slash", "dot", "dots", "missing-field", "unknown-field"],
)
def test_invalid_symbol_is_rejected(client: TestClient, world: dict, payload: dict) -> None:
    response = client.patch(f"/api/instruments/{world['ids']['SXR8.DE']}", json=payload, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


def test_instruments_require_authentication(client: TestClient) -> None:
    assert client.get("/api/instruments").status_code == 401


def test_a_manual_spread_is_saved_without_touching_the_price_symbol(
    client: TestClient, world: dict, engine: Engine
) -> None:
    sxr8 = world["ids"]["SXR8.DE"]

    saved = client.patch(f"/api/instruments/{sxr8}", json={"spread_pct": "0.1"}, headers=world["anna"])
    cleared = client.patch(f"/api/instruments/{sxr8}", json={"spread_pct": None}, headers=world["anna"])

    assert saved.status_code == 200
    assert (saved.json()["spread_pct"], saved.json()["price_symbol"], saved.json()["price_symbol_overridden"],
            saved.json()["last_price"]) == ("0.1000", "SXR8.DE", False, "713.80000000")
    assert cleared.json()["spread_pct"] is None
    assert _price_count(engine, sxr8) == 2


def test_a_spread_change_marks_the_holders_valuations(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as session:
        session.execute(update(User).values(valuations_stale_from=None))
        session.commit()

    client.patch(f"/api/instruments/{world['ids']['SXR8.DE']}", json={"spread_pct": "0.2"}, headers=world["anna"])

    with Session(engine) as session:
        stale = dict(session.execute(select(User.email, User.valuations_stale_from)).all())
    assert stale["anna@portfolio.dev"] == dt.date.min  # the worker rebuilds her history with the new spread
    assert stale["bartek@portfolio.dev"] is None  # he does not hold SXR8.DE


@pytest.mark.parametrize("spread", ["-0.1", "5.01", "abc"])
def test_a_spread_outside_0_to_5_percent_is_rejected(client: TestClient, world: dict, spread: str) -> None:
    response = client.patch(f"/api/instruments/{world['ids']['SXR8.DE']}", json={"spread_pct": spread},
                            headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
