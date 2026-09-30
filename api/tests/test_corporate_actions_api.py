import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import CorporateAction, Instrument, User
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/corporate-actions"
BEFORE = "10804.20"  # 2 × 600 EUR × 4.25 = 5 100.00 − 0.5 % conversion 25.50, + 5 729.70 zł cash (valuation_seed)
DOUBLED = "15878.70"  # after a 1:2 split effective 2026-09-25: 4 × 600 × 4.25 = 10 200.00 − 51.00, + 5 729.70


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        ids = {email: db.scalar(select(User.id).where(User.email == email))
               for email in ("anna@portfolio.dev", "bartek@portfolio.dev")}
        seed_holdings(db, ids["anna@portfolio.dev"], instrument_id)
        seed_holdings(db, ids["bartek@portfolio.dev"], instrument_id, number="22222222")
        for user_id in ids.values():
            valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "instrument_id": instrument_id,
            "anna_id": ids["anna@portfolio.dev"], "bartek_id": ids["bartek@portfolio.dev"]}


def _value(client: TestClient, headers: dict[str, str]) -> str:
    return client.get("/api/portfolio/summary", headers=headers).json()["value_pln"]


def _split(world: dict, ratio_to: str = "2", day: str = "2026-09-25") -> dict:
    return {"instrument_id": world["instrument_id"], "type": "split", "effective_date": day,
            "ratio_from": "1", "ratio_to": ratio_to}


def _provider_split(engine: Engine, world: dict) -> int:
    with Session(engine) as db:
        action = CorporateAction(instrument_id=world["instrument_id"], type="split", effective_date=dt.date(2026, 9, 25),
                                 ratio_from=Decimal(1), ratio_to=Decimal(2), source="provider")
        db.add(action)
        db.commit()
        for key in ("anna_id", "bartek_id"):
            valuate(db, world[key])
        return action.id


def test_own_split_changes_only_the_authors_valuation(client: TestClient, world: dict) -> None:
    response = client.post(URL, json=_split(world), headers=world["anna"])

    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in ("ticker", "type", "effective_date", "source", "active", "editable",
                                       "target_ticker")} == {
        "ticker": "SXR8.DE", "type": "split", "effective_date": "2026-09-25", "source": "manual", "active": True,
        "editable": True, "target_ticker": None,
    }
    assert (_value(client, world["anna"]), _value(client, world["bartek"])) == (DOUBLED, BEFORE)


def test_created_ratios_are_echoed_at_full_scale(client: TestClient, world: dict) -> None:
    response = client.post(URL, json=_split(world), headers=world["anna"])

    assert (response.json()["ratio_from"], response.json()["ratio_to"]) == ("1.00000000", "2.00000000")


def test_suppress_hides_a_provider_split_for_its_author_only(client: TestClient, world: dict, engine: Engine) -> None:
    _provider_split(engine, world)
    assert _value(client, world["anna"]) == DOUBLED

    response = client.post(URL, json={"instrument_id": world["instrument_id"], "type": "suppress",
                                      "effective_date": "2026-09-25"}, headers=world["anna"])

    assert (response.status_code, response.json()["ratio_from"], response.json()["ratio_to"]) == (
        201, "1.00000000", "1.00000000")
    assert (_value(client, world["anna"]), _value(client, world["bartek"])) == (BEFORE, DOUBLED)


def test_list_shows_shared_and_own_entries_with_precedence(client: TestClient, world: dict, engine: Engine) -> None:
    _provider_split(engine, world)
    client.post(URL, json={"instrument_id": world["instrument_id"], "type": "suppress",
                           "effective_date": "2026-09-25"}, headers=world["anna"])

    anna = client.get(URL, headers=world["anna"]).json()
    bartek = client.get(URL, params={"instrument_id": world["instrument_id"]}, headers=world["bartek"]).json()

    assert [(a["source"], a["type"], a["active"], a["editable"]) for a in anna] == [
        ("provider", "split", False, False), ("manual", "suppress", True, True)]
    assert [(a["source"], a["active"], a["editable"]) for a in bartek] == [("provider", True, False)]


def test_conversion_moves_the_holding_to_a_new_ticker(client: TestClient, world: dict, engine: Engine) -> None:
    response = client.post(URL, json={"instrument_id": world["instrument_id"], "type": "conversion",
                                      "effective_date": "2026-09-01", "ratio_from": "1", "ratio_to": "1",
                                      "target_ticker": " cspx.uk "}, headers=world["anna"])

    assert response.status_code == 201
    assert response.json()["target_ticker"] == "CSPX.UK"
    with Session(engine) as db:
        target = db.scalar(select(Instrument).where(Instrument.xtb_ticker == "CSPX.UK"))
        assert (target.category, target.exchange_suffix, target.price_checked_at) == ("etf", "UK", None)
    (item, _cash) = client.get("/api/positions", params={"date": "2026-09-26"}, headers=world["anna"]).json()
    # No prices for the new ticker yet: quantity and cost carried over, value flagged until the worker fetches them.
    assert (item["ticker"], Decimal(item["quantity"]), item["cost_pln"], item["value_pln"], item["flags"]) == (
        "CSPX.UK", 2, "4304.30", "0.00", ["xtb_price"])
    tickers = {who: [i["xtb_ticker"] for i in client.get("/api/instruments", headers=world[who]).json()]
               for who in ("anna", "bartek")}
    assert tickers == {"anna": ["CSPX.UK", "SXR8.DE"], "bartek": ["SXR8.DE"]}


def test_update_and_delete_own_entry_recompute_the_valuation(client: TestClient, world: dict) -> None:
    action_id = client.post(URL, json=_split(world), headers=world["anna"]).json()["id"]

    updated = client.put(f"{URL}/{action_id}", json=_split(world, ratio_to="3"), headers=world["anna"])
    assert (updated.status_code, _value(client, world["anna"])) == (200, "20953.20")  # 6 × 600 × 4.25 = 15 300.00 − 76.50 + cash

    deleted = client.delete(f"{URL}/{action_id}", headers=world["anna"])
    assert (deleted.status_code, _value(client, world["anna"])) == (204, BEFORE)


def test_shared_entry_is_read_only_and_foreign_entries_are_404(client: TestClient, world: dict, engine: Engine) -> None:
    shared_id = _provider_split(engine, world)
    bartek_id = client.post(URL, json=_split(world, day="2026-09-01"), headers=world["bartek"]).json()["id"]

    shared_put = client.put(f"{URL}/{shared_id}", json=_split(world), headers=world["anna"])
    shared_delete = client.delete(f"{URL}/{shared_id}", headers=world["anna"])
    foreign_put = client.put(f"{URL}/{bartek_id}", json=_split(world), headers=world["anna"])
    foreign_delete = client.delete(f"{URL}/{bartek_id}", headers=world["anna"])

    assert [(r.status_code, r.json()["code"]) for r in (shared_put, shared_delete, foreign_put, foreign_delete)] == [
        (409, "shared_action"), (409, "shared_action"), (404, "not_found"), (404, "not_found")]


def test_entry_for_an_instrument_the_user_does_not_have_is_404(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        other = Instrument(xtb_ticker="NVDA.US", name="NVIDIA")
        db.add(other)
        db.commit()
        other_id = other.id

    response = client.post(URL, json={**_split(world), "instrument_id": other_id}, headers=world["anna"])
    listed = client.get(URL, params={"instrument_id": other_id}, headers=world["anna"])

    assert [(r.status_code, r.json()["code"]) for r in (response, listed)] == [(404, "not_found"), (404, "not_found")]


def test_second_own_entry_on_the_same_day_is_409(client: TestClient, world: dict) -> None:
    client.post(URL, json=_split(world), headers=world["anna"])

    response = client.post(URL, json={"instrument_id": world["instrument_id"], "type": "suppress",
                                      "effective_date": "2026-09-25"}, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (409, "duplicate_action")


def test_conversion_into_itself_is_422(client: TestClient, world: dict) -> None:
    response = client.post(URL, json={"instrument_id": world["instrument_id"], "type": "conversion",
                                      "effective_date": "2026-09-01", "ratio_from": "1", "ratio_to": "1",
                                      "target_ticker": "SXR8.DE"}, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "conversion_to_itself")


@pytest.mark.parametrize(
    "fields",
    [
        {"type": "split", "ratio_from": "2", "ratio_to": "1"},
        {"type": "reverse_split", "ratio_from": "1", "ratio_to": "2"},
        {"type": "split", "ratio_from": "0", "ratio_to": "2"},
        {"type": "split", "ratio_from": "1"},
        {"type": "suppress", "ratio_from": "1", "ratio_to": "2"},
        {"type": "conversion", "ratio_from": "1", "ratio_to": "1"},
        {"type": "split", "ratio_from": "1", "ratio_to": "2", "target_ticker": "CSPX.UK"},
        {"type": "conversion", "ratio_from": "1", "ratio_to": "1", "target_ticker": "..."},
        {"type": "merger", "ratio_from": "1", "ratio_to": "1"},
    ],
)
def test_inconsistent_entries_are_rejected(client: TestClient, world: dict, fields: dict) -> None:
    body = {"instrument_id": world["instrument_id"], "effective_date": "2026-09-25", **fields}

    response = client.post(URL, json=body, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


def test_corporate_actions_require_login(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
