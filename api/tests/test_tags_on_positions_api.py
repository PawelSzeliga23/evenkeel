from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine

from tests.tag_seed import add_link as _link
from tests.tag_seed import add_tag as _tag
from tests.tag_seed import tag_world

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    return tag_world(client, login_as, engine)


def test_positions_carry_the_tags_of_both_levels(client: TestClient, world: dict) -> None:
    usa, ike = _tag(client, world["anna"], "USA"), _tag(client, world["anna"], "emerytura")
    _link(client, world, usa, instrument_id=world["sxr8"])
    _link(client, world, ike, instrument_id=world["sxr8"], account_id=world["ike"])
    _link(client, world, ike, bond_series="EDO0336")
    _link(client, world, usa, account_id=world["savings"])

    positions = client.get("/api/positions", headers=world["anna"]).json()

    sxr8 = next(p for p in positions if p["kind"] == "instrument")
    assert [(t["name"], t["own"]) for t in sxr8["tags"]] == [("emerytura", True), ("USA", False)]
    bond = next(p for p in positions if p["kind"] == "bond")
    assert [t["name"] for t in bond["tags"]] == ["emerytura"]
    assert all(p["tags"] == [] for p in positions if p["kind"] == "cash")


def test_details_carry_the_tags(client: TestClient, world: dict) -> None:
    usa = _tag(client, world["anna"], "USA")
    link = _link(client, world, usa, instrument_id=world["sxr8"])
    _link(client, world, usa, account_id=world["savings"])
    series = _link(client, world, usa, bond_series="EDO0336")

    detail = client.get(f"/api/positions/{world['ike']}/{world['sxr8']}", headers=world["anna"]).json()
    savings = client.get(f"/api/savings-accounts/{world['savings']}", headers=world["anna"]).json()
    bond = client.get(f"/api/bonds/{world['bond']}", headers=world["anna"]).json()

    assert detail["tags"] == [{"id": usa["id"], "name": "USA", "color": "#F0A43A", "link_id": link["id"], "own": False}]
    assert [t["name"] for t in savings["tags"]] == ["USA"]
    assert [(t["name"], t["link_id"]) for t in bond["tags"]] == [("USA", series["id"])]


def test_a_holding_only_tagged_on_another_account_has_no_tag_here(client: TestClient, world: dict) -> None:
    tag = _tag(client, world["anna"], "x")
    _link(client, world, tag, instrument_id=world["sxr8"], account_id=world["plain"])

    detail = client.get(f"/api/positions/{world['ike']}/{world['sxr8']}", headers=world["anna"]).json()

    assert detail["tags"] == []
