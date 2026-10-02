from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

import app.tags.router as router
from app.models import Tag
from tests.tag_seed import add_tag as _tag
from tests.tag_seed import tag_world

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    return tag_world(client, login_as, engine)


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


def test_the_database_keeps_names_unique_regardless_of_case(client: TestClient, world: dict, engine: Engine) -> None:
    tag = _tag(client, world["anna"], "USA")
    with Session(engine) as db, pytest.raises(IntegrityError):
        db.add(Tag(user_id=world["user_id"], name="usa", color=tag["color"]))
        db.commit()


def test_a_concurrent_duplicate_tag_is_a_conflict_not_an_error(
        client: TestClient, world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    _tag(client, world["anna"], "USA")
    monkeypatch.setattr("app.tags.router._clash", lambda *args, **kwargs: None)  # the other request passed the check

    response = client.post("/api/tags", json={"name": "usa"}, headers=world["anna"])

    assert response.status_code == 409 and response.json()["code"] == "tag_exists"


def test_a_concurrent_duplicate_link_returns_the_existing_one(
        client: TestClient, world: dict, monkeypatch: pytest.MonkeyPatch) -> None:

    tag = _tag(client, world["anna"], "x")
    url = f"/api/tags/{tag['id']}/links"
    first = client.post(url, json={"instrument_id": world["sxr8"]}, headers=world["anna"]).json()
    real, calls = router._existing_link, []

    def racing(*args: object) -> object:
        calls.append(1)
        return None if len(calls) == 1 else real(*args)  # the first look misses the link the other request just made

    monkeypatch.setattr(router, "_existing_link", racing)
    response = client.post(url, json={"instrument_id": world["sxr8"]}, headers=world["anna"])

    assert response.status_code == 200 and response.json()["id"] == first["id"]
