import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, BondHolding, BondSeries, SavingsAccount, User
from tests.valuation_seed import seed_holdings, seed_market

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        bartek_id = db.scalar(select(User.id).where(User.email == "bartek@portfolio.dev"))
        sxr8 = seed_market(db)
        ike = seed_holdings(db, user_id, sxr8)
        savings = Account(user_id=user_id, name="Konto oszczędnościowe", kind="savings", wrapper="regular",
                          currency="PLN")
        plain = Account(user_id=user_id, name="Zwykłe", kind="broker", wrapper="regular", currency="PLN")
        foreign = Account(user_id=bartek_id, name="Bartka", kind="broker", wrapper="regular", currency="PLN")
        db.add_all([savings, plain, foreign])
        db.flush()
        db.add(SavingsAccount(account_id=savings.id, capitalization="monthly"))
        if db.get(BondSeries, "EDO0336") is None:
            db.add(BondSeries(series="EDO0336", bond_type="EDO", issue_month=dt.date(2026, 3, 1), maturity_months=120,
                              first_period_rate=Decimal("5.6"), margin=Decimal("1.5"),
                              early_redemption_fee=Decimal("2"), interest_mode="capitalized", rate_basis="cpi"))
            db.flush()
        db.add(BondHolding(account_id=ike, bond_type="EDO", series="EDO0336", quantity=10,
                           purchase_date=dt.date(2026, 3, 10)))
        db.commit()
    return {"anna": anna, "bartek": bartek, "ike": ike, "savings": savings.id, "plain": plain.id,
            "foreign": foreign.id, "sxr8": sxr8}


def _tag(client: TestClient, headers: dict, name: str, **body: object) -> dict:
    response = client.post("/api/tags", json={"name": name, **body}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_tags_get_palette_colours_in_turn_and_are_listed_by_name(client: TestClient, world: dict) -> None:
    usa, emerytura = _tag(client, world["anna"], " USA "), _tag(client, world["anna"], "emerytura")

    assert (usa["name"], usa["color"], emerytura["color"]) == ("USA", "#F0A43A", "#7FB6E6")
    assert [t["name"] for t in client.get("/api/tags", headers=world["anna"]).json()] == ["emerytura", "USA"]
    assert client.get("/api/tags", headers=world["bartek"]).json() == []


def test_a_name_differing_only_in_case_is_a_conflict(client: TestClient, world: dict) -> None:
    _tag(client, world["anna"], "USA")

    response = client.post("/api/tags", json={"name": "usa"}, headers=world["anna"])

    assert response.status_code == 409 and response.json()["code"] == "tag_exists"


@pytest.mark.parametrize("body", [{"name": "  "}, {"name": "x" * 31}, {"name": "ok", "color": "#123456"}])
def test_bad_names_and_colours_are_rejected(client: TestClient, world: dict, body: dict) -> None:
    assert client.post("/api/tags", json=body, headers=world["anna"]).status_code == 422


def test_rename_recolour_and_delete(client: TestClient, world: dict) -> None:
    tag, other = _tag(client, world["anna"], "USA"), _tag(client, world["anna"], "Polska")

    renamed = client.patch(f"/api/tags/{tag['id']}", json={"name": "Stany", "color": "#5DB98A"}, headers=world["anna"])
    clash = client.patch(f"/api/tags/{other['id']}", json={"name": "stany"}, headers=world["anna"])

    assert renamed.json()["name"] == "Stany" and renamed.json()["color"] == "#5DB98A"
    assert clash.status_code == 409
    assert client.delete(f"/api/tags/{tag['id']}", headers=world["anna"]).status_code == 204
    assert [t["name"] for t in client.get("/api/tags", headers=world["anna"]).json()] == ["Polska"]


def test_links_on_both_levels_a_series_and_a_savings_account(client: TestClient, world: dict) -> None:
    tag = _tag(client, world["anna"], "emerytura")
    url = f"/api/tags/{tag['id']}/links"
    bodies = [{"instrument_id": world["sxr8"]}, {"instrument_id": world["sxr8"], "account_id": world["ike"]},
              {"bond_series": "EDO0336"}, {"account_id": world["savings"]}]

    created = [client.post(url, json=body, headers=world["anna"]) for body in bodies]
    again = client.post(url, json=bodies[0], headers=world["anna"])

    assert [r.status_code for r in created] == [201, 201, 201, 201]
    assert again.status_code == 200 and again.json()["id"] == created[0].json()["id"]
    assert client.get("/api/tags", headers=world["anna"]).json()[0]["links"] == 4
    link_id = created[1].json()["id"]
    assert client.delete(f"/api/tag-links/{link_id}", headers=world["bartek"]).status_code == 404
    assert client.delete(f"/api/tag-links/{link_id}", headers=world["anna"]).status_code == 204


@pytest.mark.parametrize("body", [{}, {"account_id": "plain"}, {"instrument_id": "sxr8", "bond_series": "EDO0336"}])
def test_a_link_needs_one_target(client: TestClient, world: dict, body: dict) -> None:
    tag = _tag(client, world["anna"], "x")
    body = {k: (world[v] if isinstance(v, str) and v in world else v) for k, v in body.items()}

    response = client.post(f"/api/tags/{tag['id']}/links", json=body, headers=world["anna"])

    assert response.status_code == 422 and response.json()["code"] == "link_target"


def test_someone_elses_tag_account_or_series_is_404(client: TestClient, world: dict) -> None:
    tag = _tag(client, world["anna"], "x")
    url = f"/api/tags/{tag['id']}/links"

    assert client.post(url, json={"instrument_id": world["sxr8"]}, headers=world["bartek"]).status_code == 404
    assert client.post(url, json={"instrument_id": world["sxr8"], "account_id": world["foreign"]},
                       headers=world["anna"]).status_code == 404
    assert client.post(url, json={"bond_series": "EDO0336", "account_id": world["plain"]},
                       headers=world["anna"]).status_code == 404  # no bond of that series there
    assert client.patch(f"/api/tags/{tag['id']}", json={"name": "y"}, headers=world["bartek"]).status_code == 404
