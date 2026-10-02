from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

LoginAs = Callable[[str], dict[str, str]]

DEPOSITS = {
    "name": "Wszystko w EDO", "base": "deposits",
    "allocation": [{"target": {"bond": "EDO"}, "share_pct": "100"}],
}


@pytest.fixture
def anna(client: TestClient, login_as: LoginAs) -> dict[str, str]:
    return login_as("anna@portfolio.dev")


def test_create_list_read_and_delete(client: TestClient, anna: dict) -> None:
    created = client.post("/api/scenarios", json={**DEPOSITS, "name": "  Wszystko w EDO "}, headers=anna)
    assert created.status_code == 201
    body = created.json()
    assert (body["name"], body["base"], body["steps"]) == ("Wszystko w EDO", "deposits", [])
    assert body["allocation"] == [{"target": {"instrument_id": None, "bond": "EDO"}, "share_pct": "100"}]

    assert [s["id"] for s in client.get("/api/scenarios", headers=anna).json()] == [body["id"]]
    assert client.get(f"/api/scenarios/{body['id']}", headers=anna).json() == body
    assert client.delete(f"/api/scenarios/{body['id']}", headers=anna).status_code == 204
    assert client.get(f"/api/scenarios/{body['id']}", headers=anna).status_code == 404


def test_list_shows_the_last_changed_first(client: TestClient, anna: dict) -> None:
    first = client.post("/api/scenarios", json=DEPOSITS, headers=anna).json()
    second = client.post("/api/scenarios", json={**DEPOSITS, "name": "Drugi"}, headers=anna).json()
    client.patch(f"/api/scenarios/{first['id']}", json={"name": "Pierwszy, zmieniony"}, headers=anna)

    assert [s["id"] for s in client.get("/api/scenarios", headers=anna).json()] == [first["id"], second["id"]]


def test_scenarios_of_another_user_are_not_found(client: TestClient, anna: dict, login_as: LoginAs) -> None:
    own = client.post("/api/scenarios", json=DEPOSITS, headers=anna).json()
    bartek = login_as("bartek@portfolio.dev")

    assert client.get("/api/scenarios", headers=bartek).json() == []
    for response in (
        client.get(f"/api/scenarios/{own['id']}", headers=bartek),
        client.patch(f"/api/scenarios/{own['id']}", json={"name": "Moje"}, headers=bartek),
        client.delete(f"/api/scenarios/{own['id']}", headers=bartek),
    ):
        assert (response.status_code, response.json()["code"]) == (404, "not_found")


def test_patch_changes_only_the_given_fields(client: TestClient, anna: dict) -> None:
    own = client.post("/api/scenarios", json=DEPOSITS, headers=anna).json()
    steps = [{"kind": "recurring", "amount_pln": "1000", "day_of_month": 10, "start": "2024-01",
              "target": {"bond": "EDO"}, "ike": True}]

    body = client.patch(f"/api/scenarios/{own['id']}", json={"steps": steps}, headers=anna).json()

    assert (body["name"], body["allocation"]) == (own["name"], own["allocation"])
    assert body["steps"] == [{"kind": "recurring", "amount_pln": "1000", "day_of_month": 10, "start": "2024-01",
                              "end": None, "target": {"instrument_id": None, "bond": "EDO"}, "ike": True}]


def test_patch_validates_the_merged_scenario(client: TestClient, anna: dict) -> None:
    own = client.post("/api/scenarios", json={"name": "Portfel", "base": "portfolio"}, headers=anna).json()

    response = client.patch(f"/api/scenarios/{own['id']}", json={"base": "deposits"}, headers=anna)

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
    assert client.get(f"/api/scenarios/{own['id']}", headers=anna).json()["base"] == "portfolio"


RECURRING = {"kind": "recurring", "amount_pln": "500", "day_of_month": 1, "start": "2025-01",
             "target": {"bond": "EDO"}}


@pytest.mark.parametrize("body", [
    {"name": "   ", "base": "portfolio"},
    {"name": "x" * 81, "base": "portfolio"},
    {"name": "Bez podziału", "base": "deposits"},
    {"name": "90 %", "base": "deposits", "allocation": [{"target": {"bond": "EDO"}, "share_pct": "90"}]},
    {"name": "Zero", "base": "deposits", "allocation": [{"target": {"bond": "EDO"}, "share_pct": "100"},
                                                        {"target": {"instrument_id": 1}, "share_pct": "0"}]},
    {"name": "Podział w portfelu", "base": "portfolio", "allocation": DEPOSITS["allocation"]},
    {**DEPOSITS, "steps": [{"kind": "replace", "from_instrument_id": 1, "to_instrument_id": 2}]},
    {"name": "Sam w siebie", "base": "portfolio",
     "steps": [{"kind": "replace", "from_instrument_id": 1, "to_instrument_id": 1}]},
    {"name": "Dwa razy", "base": "portfolio",
     "steps": [{"kind": "replace", "from_instrument_id": 1, "to_instrument_id": 2},
               {"kind": "replace", "from_instrument_id": 1, "to_instrument_id": 3}]},
    {"name": "29.", "base": "portfolio", "steps": [{**RECURRING, "day_of_month": 29}]},
    {"name": "Wstecz", "base": "portfolio", "steps": [{**RECURRING, "end": "2024-12"}]},
    {"name": "Miesiąc 13", "base": "portfolio", "steps": [{**RECURRING, "start": "2025-13"}]},
    {"name": "Zero zł", "base": "portfolio", "steps": [{**RECURRING, "amount_pln": "0"}]},
    {"name": "Dwa cele", "base": "portfolio",
     "steps": [{**RECURRING, "target": {"bond": "EDO", "instrument_id": 1}}]},
    {"name": "Bez celu", "base": "portfolio", "steps": [{**RECURRING, "target": {}}]},
    {"name": "Za dużo", "base": "portfolio", "steps": [RECURRING] * 11},
])
def test_invalid_scenarios_are_422(client: TestClient, anna: dict, body: dict) -> None:
    response = client.post("/api/scenarios", json=body, headers=anna)
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


def test_scenarios_need_a_session(client: TestClient) -> None:
    assert client.get("/api/scenarios").status_code == 401
