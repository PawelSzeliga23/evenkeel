import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.models import Instrument, Price, Transaction
from app.valuation.service import local_today
from tests.tag_seed import tag_world

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    return tag_world(client, login_as, engine)


def _thesis(client: TestClient, world: dict, body: str, **target: object) -> object:
    return client.put("/api/theses", json={"body": body, **target}, headers=world["anna"])


def _entry(client: TestClient, world: dict, body: str = "Wpis", **fields: object) -> dict:
    response = client.post("/api/journal", json={"body": body, **fields}, headers=world["anna"])
    assert response.status_code == 201, response.text
    return response.json()


def _journal(client: TestClient, world: dict, target: str | None = None) -> dict:
    response = client.get("/api/journal", params={"target": target} if target else {}, headers=world["anna"])
    assert response.status_code == 200, response.text
    return response.json()


def test_a_thesis_is_saved_changed_and_removed_by_an_empty_text(client: TestClient, world: dict) -> None:
    first = _thesis(client, world, "  Rdzeń portfela.\nNie sprzedaję.  ", instrument_id=world["sxr8"])
    assert first.status_code == 200, first.text
    assert (first.json()["key"], first.json()["body"]) == (f"i:{world['sxr8']}", "Rdzeń portfela.\nNie sprzedaję.")

    second = _thesis(client, world, "Inna teza", instrument_id=world["sxr8"]).json()
    assert (second["id"], second["body"]) == (first.json()["id"], "Inna teza")

    assert _thesis(client, world, " \n  ", instrument_id=world["sxr8"]).status_code == 204
    assert _thesis(client, world, "", instrument_id=world["sxr8"]).status_code == 204  # nothing left to remove
    again = _thesis(client, world, "Nowa", instrument_id=world["sxr8"]).json()
    assert again["id"] != first.json()["id"]  # the blank one was deleted, not kept


def test_theses_go_on_a_series_and_a_savings_account(client: TestClient, world: dict) -> None:
    assert _thesis(client, world, "Na emeryturę", bond_series="EDO0336").json()["key"] == "b:EDO0336"
    assert _thesis(client, world, "Poduszka", account_id=world["savings"]).json()["key"] == f"s:{world['savings']}"


@pytest.mark.parametrize("target", [{}, {"instrument_id": 1, "bond_series": "EDO0336"}])
def test_a_thesis_needs_exactly_one_holding(client: TestClient, world: dict, target: dict) -> None:
    response = _thesis(client, world, "x", **target)

    assert (response.status_code, response.json()["code"]) == (422, "note_target")


def test_a_plain_account_is_not_a_holding(client: TestClient, world: dict) -> None:
    response = _thesis(client, world, "x", account_id=world["plain"])

    assert (response.status_code, response.json()["code"]) == (422, "note_target")


def test_a_thesis_has_at_most_5000_characters(client: TestClient, world: dict) -> None:
    assert _thesis(client, world, "x" * 5001, instrument_id=world["sxr8"]).status_code == 422
    assert _thesis(client, world, "x" * 5000, instrument_id=world["sxr8"]).status_code == 200


def test_someone_elses_holding_or_entry_is_not_found(client: TestClient, world: dict) -> None:
    entry = _entry(client, world, "Anny")
    bartek = world["bartek"]

    assert client.put("/api/theses", json={"body": "x", "instrument_id": world["sxr8"]}, headers=bartek).status_code == 404
    assert client.put("/api/theses", json={"body": "x", "bond_series": "EDO0336"}, headers=bartek).status_code == 404
    assert client.put("/api/theses", json={"body": "x", "account_id": world["savings"]}, headers=bartek).status_code == 404
    assert _thesis(client, world, "x", account_id=world["foreign"]).status_code == 404
    assert client.patch(f"/api/journal/{entry['id']}", json={"body": "y"}, headers=bartek).status_code == 404
    assert client.delete(f"/api/journal/{entry['id']}", headers=bartek).status_code == 404
    assert client.get("/api/journal", headers=bartek).json() == {"entries": [], "count": 0}


def test_entries_default_to_today_and_come_newest_first(client: TestClient, world: dict) -> None:
    today = local_today()
    older = _entry(client, world, "Starszy", entry_date=(today - dt.timedelta(days=30)).isoformat())
    first = _entry(client, world, "Dziś pierwszy")
    second = _entry(client, world, "Dziś drugi", instrument_id=world["sxr8"])

    body = _journal(client, world)

    assert first["entry_date"] == today.isoformat() and first["target"] is None
    assert [e["id"] for e in body["entries"]] == [second["id"], first["id"], older["id"]]
    assert body["count"] == 3


@pytest.mark.parametrize("day", ["future", "1999-12-31"])
def test_an_entry_date_from_the_future_or_before_2000_is_refused(client: TestClient, world: dict, day: str) -> None:
    value = (local_today() + dt.timedelta(days=1)).isoformat() if day == "future" else day

    response = client.post("/api/journal", json={"body": "x", "entry_date": value}, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "entry_date")


@pytest.mark.parametrize("body", ["   ", "x" * 2001])
def test_an_entry_has_1_to_2000_characters(client: TestClient, world: dict, body: str) -> None:
    response = client.post("/api/journal", json={"body": body}, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


def test_an_entry_changes_moves_between_holdings_and_the_portfolio_and_is_deleted(
    client: TestClient, world: dict,
) -> None:
    entry = _entry(client, world, "Wpis", instrument_id=world["sxr8"])
    url = f"/api/journal/{entry['id']}"

    changed = client.patch(url, json={"body": " Nowa treść ", "entry_date": "2026-05-04"}, headers=world["anna"]).json()
    assert (changed["body"], changed["entry_date"], changed["target"]["key"]) == (
        "Nowa treść", "2026-05-04", f"i:{world['sxr8']}")
    moved = client.patch(url, json={"bond_series": "EDO0336"}, headers=world["anna"]).json()
    assert moved["target"]["key"] == "b:EDO0336"
    portfolio = client.patch(url, json={"portfolio": True}, headers=world["anna"]).json()
    assert portfolio["target"] is None
    both = client.patch(url, json={"portfolio": True, "instrument_id": world["sxr8"]}, headers=world["anna"])
    assert (both.status_code, both.json()["code"]) == (422, "note_target")

    assert client.delete(url, headers=world["anna"]).status_code == 204
    assert _journal(client, world)["count"] == 0


def test_the_journal_filters_by_holding_or_portfolio(client: TestClient, world: dict) -> None:
    _entry(client, world, "Portfel")
    _entry(client, world, "SXR8", instrument_id=world["sxr8"])
    _entry(client, world, "EDO", bond_series="EDO0336")
    _entry(client, world, "Oszczędności", account_id=world["savings"])

    def bodies(target: str) -> list[str]:
        return [e["body"] for e in _journal(client, world, target)["entries"]]

    assert bodies("portfolio") == ["Portfel"]
    assert bodies(f"i:{world['sxr8']}") == ["SXR8"]
    assert bodies("b:EDO0336") == ["EDO"]
    assert bodies(f"s:{world['savings']}") == ["Oszczędności"]
    bad = client.get("/api/journal", params={"target": "x:1"}, headers=world["anna"])
    assert (bad.status_code, bad.json()["code"]) == (422, "note_target")


def test_entries_say_what_holding_they_are_about(client: TestClient, world: dict) -> None:
    _entry(client, world, "SXR8", instrument_id=world["sxr8"])
    _entry(client, world, "EDO", bond_series="EDO0336")
    _entry(client, world, "Oszczędności", account_id=world["savings"])

    targets = {e["body"]: e["target"] for e in _journal(client, world)["entries"]}

    assert targets["SXR8"] == {
        "key": f"i:{world['sxr8']}", "label": "SXR8.DE", "sublabel": "Core S&P 500", "closed": False,
        "link": {"kind": "position", "account_id": world["ike"], "instrument_id": world["sxr8"], "bond_holding_id": None},
    }
    assert (targets["EDO"]["label"], targets["EDO"]["closed"], targets["EDO"]["link"]["bond_holding_id"]) == (
        "EDO0336", False, world["bond"])
    assert (targets["Oszczędności"]["label"], targets["Oszczędności"]["closed"], targets["Oszczędności"]["link"]) == (
        "Konto oszczędnościowe", False,
        {"kind": "savings", "account_id": world["savings"], "instrument_id": None, "bond_holding_id": None})


def test_a_series_without_bonds_keeps_its_notes_as_closed_without_a_link(client: TestClient, world: dict) -> None:
    _entry(client, world, "EDO", bond_series="EDO0336")
    assert client.delete(f"/api/bonds/{world['bond']}", headers=world["anna"]).status_code == 204

    target = _journal(client, world)["entries"][0]["target"]

    assert (target["key"], target["label"], target["closed"], target["link"]) == ("b:EDO0336", "EDO0336", True, None)


def test_details_carry_the_thesis_and_the_three_newest_entries(client: TestClient, world: dict) -> None:
    _thesis(client, world, "Rdzeń", instrument_id=world["sxr8"])
    for day in ("2026-05-01", "2026-06-01", "2026-07-01", "2026-08-01"):
        _entry(client, world, day, instrument_id=world["sxr8"], entry_date=day)
    _entry(client, world, "Seria", bond_series="EDO0336")
    _thesis(client, world, "Poduszka", account_id=world["savings"])

    detail = client.get(f"/api/positions/{world['ike']}/{world['sxr8']}", headers=world["anna"]).json()["notes"]
    bond = client.get(f"/api/bonds/{world['bond']}", headers=world["anna"]).json()["notes"]
    savings = client.get(f"/api/savings-accounts/{world['savings']}", headers=world["anna"]).json()["notes"]

    assert detail["thesis"]["body"] == "Rdzeń"
    assert [e["body"] for e in detail["recent"]] == ["2026-08-01", "2026-07-01", "2026-06-01"]
    assert detail["count"] == 4 and "target" not in detail["recent"][0]
    assert (bond["thesis"], [e["body"] for e in bond["recent"]], bond["count"]) == (None, ["Seria"], 1)
    assert (savings["thesis"]["body"], savings["recent"], savings["count"]) == ("Poduszka", [], 0)


def _closed_cdr(engine: Engine, world: dict) -> int:
    """CD Projekt bought and fully sold on the plain account."""
    with Session(engine) as db:
        cdr = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", category="stock", currency="PLN", price_symbol="CDR.WA")
        db.add(cdr)
        db.flush()
        db.add(Price(instrument_id=cdr.id, date=dt.date(2026, 4, 1), close=Decimal("250"), source="yahoo"))
        for number, (kind, amount, day) in enumerate(
                [("deposit", "1000", 1), ("buy", "-500", 2), ("sell", "520", 3)], start=900):
            db.add(Transaction(account_id=world["plain"], type=kind, xtb_type=kind, amount=Decimal(amount),
                               occurred_at=dt.datetime(2026, 4, day, 10, tzinfo=dt.UTC), currency="PLN",
                               external_id=str(number), comment="", raw={},
                               **({} if kind == "deposit" else {"instrument_id": cdr.id, "quantity": Decimal("2"),
                                                                "price": Decimal("250")})))
        db.commit()
        return cdr.id


def test_targets_list_open_holdings_before_closed_ones(client: TestClient, world: dict, engine: Engine) -> None:
    cdr = _closed_cdr(engine, world)

    targets = client.get("/api/journal/targets", headers=world["anna"]).json()

    assert [(t["label"], t["closed"]) for t in targets] == [
        ("EDO0336", False), ("Konto oszczędnościowe", False), ("SXR8.DE", False), ("CDR.PL", True)]
    assert targets[-1]["link"] == {"kind": "position", "account_id": world["plain"], "instrument_id": cdr,
                                   "bond_holding_id": None}


def test_a_closed_position_still_shows_its_notes(client: TestClient, world: dict, engine: Engine) -> None:
    cdr = _closed_cdr(engine, world)
    _thesis(client, world, "Sprzedane po premierze", instrument_id=cdr)

    detail = client.get(f"/api/positions/{world['plain']}/{cdr}", headers=world["anna"]).json()

    assert detail["notes"]["thesis"]["body"] == "Sprzedane po premierze"


def test_deleting_the_savings_account_removes_its_notes(client: TestClient, world: dict) -> None:
    _thesis(client, world, "Poduszka", account_id=world["savings"])
    _entry(client, world, "Wpłata", account_id=world["savings"])
    _entry(client, world, "Portfel")

    usage = client.get(f"/api/accounts/{world['savings']}/usage", headers=world["anna"]).json()
    assert usage["notes"] == 2
    assert client.delete(f"/api/accounts/{world['savings']}", headers=world["anna"]).status_code == 204

    assert [e["body"] for e in _journal(client, world)["entries"]] == ["Portfel"]


def test_the_price_chart_puts_entries_on_closes(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:  # closes: Mon 03-02, Mon 06-15, Fri 09-25 (from the seed and here)
        db.add(Price(instrument_id=world["sxr8"], date=dt.date(2026, 6, 15), close=Decimal("550"), source="yahoo"))
        db.commit()
    _entry(client, world, "przed notowaniami", instrument_id=world["sxr8"], entry_date="2026-03-01")
    _entry(client, world, "w poniedziałek", instrument_id=world["sxr8"], entry_date="2026-03-02")
    sat = _entry(client, world, "w sobotę", instrument_id=world["sxr8"], entry_date="2026-06-13")
    _entry(client, world, "po ostatnim", instrument_id=world["sxr8"], entry_date="2026-09-27")
    _entry(client, world, "o portfelu", entry_date="2026-06-15")

    notes = client.get(f"/api/positions/{world['ike']}/{world['sxr8']}/prices", headers=world["anna"]).json()["notes"]
    later = client.get(f"/api/positions/{world['ike']}/{world['sxr8']}/prices", params={"from": "2026-06-01"},
                       headers=world["anna"]).json()["notes"]

    assert [(n["date"], [e["body"] for e in n["entries"]]) for n in notes] == [
        ("2026-03-02", ["w poniedziałek"]), ("2026-06-15", ["w sobotę"]), ("2026-09-25", ["po ostatnim"])]
    assert notes[1]["entries"][0] == {"id": sat["id"], "entry_date": "2026-06-13", "body": "w sobotę"}
    assert [n["date"] for n in later] == ["2026-06-15", "2026-09-25"]


def test_an_instrument_held_without_its_own_trades_links_to_its_lot_account(
    client: TestClient, world: dict, engine: Engine,
) -> None:
    """E.g. received through a conversion: the user never traded it, but holds a lot of it."""
    from app.models import PositionLot

    with Session(engine) as db:
        new = Instrument(xtb_ticker="NEW.PL", name="Po zamianie", category="stock", currency="PLN", price_symbol="NEW.WA")
        db.add(new)
        db.flush()
        db.add(PositionLot(account_id=world["plain"], instrument_id=new.id, xtb_position_id="conv-1", side="buy",
                           quantity=Decimal("3"), open_price=Decimal("10"),
                           opened_at=dt.datetime(2026, 5, 4, 10, tzinfo=dt.UTC), raw={}))
        db.commit()
        new_id = new.id

    targets = {t["key"]: t for t in client.get("/api/journal/targets", headers=world["anna"]).json()}

    assert targets[f"i:{new_id}"]["link"] == {"kind": "position", "account_id": world["plain"], "instrument_id": new_id,
                                              "bond_holding_id": None}
