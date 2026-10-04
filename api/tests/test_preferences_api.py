from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, User

LoginAs = Callable[[str], dict[str, str]]
DEFAULTS = {"start_screen": "dashboard", "accounts_start": "last", "accounts_fixed": [], "analysis_period": "all",
            "holdings_period": "all", "value_range": "1R", "price_range": "buy",
            "holdings_without_fixed_income": False, "dashboard": None}


def _account(engine: Engine, email: str, name: str) -> int:
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == email))
        account = Account(user_id=user_id, name=name, kind="broker", wrapper="regular", currency="PLN")
        db.add(account)
        db.commit()
        return account.id


def test_a_new_user_has_the_defaults(client: TestClient, login_as: LoginAs) -> None:
    me = client.get("/api/auth/me", headers=login_as("anna@portfolio.dev")).json()

    assert me["preferences"] == DEFAULTS


def test_saving_some_keys_keeps_the_rest(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    saved = client.patch("/api/me/preferences", json={"start_screen": "analysis", "value_range": "ALL"}, headers=anna)
    again = client.patch("/api/me/preferences", json={"holdings_without_fixed_income": True}, headers=anna)

    assert saved.status_code == 200, saved.text
    assert again.json() == {**DEFAULTS, "start_screen": "analysis", "value_range": "ALL",
                            "holdings_without_fixed_income": True}
    assert client.get("/api/auth/me", headers=anna).json()["preferences"] == again.json()


def test_an_unknown_value_or_key_is_refused(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    for body in ({"start_screen": "settings"}, {"analysis_period": "5y"}, {"theme": "dark"}):
        response = client.patch("/api/me/preferences", json=body, headers=anna)
        assert (response.status_code, response.json()["code"]) == (422, "validation_error"), body


def test_fixed_accounts_must_be_the_users_and_deleted_ones_drop_out(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    anna = login_as("anna@portfolio.dev")
    login_as("bartek@portfolio.dev")
    own, other = _account(engine, "anna@portfolio.dev", "IKE"), _account(engine, "anna@portfolio.dev", "Zwykłe")
    foreign = _account(engine, "bartek@portfolio.dev", "Bartka")

    refused = client.patch("/api/me/preferences", json={"accounts_fixed": [own, foreign]}, headers=anna)
    assert refused.status_code == 404
    saved = client.patch("/api/me/preferences", json={"accounts_start": "fixed", "accounts_fixed": [other, own]},
                         headers=anna).json()
    assert saved["accounts_fixed"] == sorted([own, other])
    assert client.delete(f"/api/accounts/{other}", headers=anna).status_code == 204

    assert client.get("/api/auth/me", headers=anna).json()["preferences"]["accounts_fixed"] == [own]


def test_preferences_need_a_session(client: TestClient) -> None:
    assert client.patch("/api/me/preferences", json={"start_screen": "analysis"}).status_code == 401


LAYOUT = {"version": 1, "tiles": [
    {"id": "a1", "kind": "summary", "variant": "L", "settings": {"fields": ["total_gain", "sharpe", "invested", "income"]}},
    {"id": "b2", "kind": "metric", "variant": "S1", "settings": {"metric": "xirr"}},
    {"id": "c3", "kind": "price_chart", "variant": "M5", "settings": {"account_id": 5, "instrument_id": 7, "range": "1y"}},
    {"id": "d4", "kind": "holdings", "variant": "L5", "settings": {}},
    {"id": "e5", "kind": "operations", "variant": "M", "settings": {"count": 5}},
    {"id": "f6", "kind": "extremes", "variant": "L", "settings": {"count": 3, "period": "1y"}},
    {"id": "g7", "kind": "journal", "variant": "S2", "settings": {}},
]}


def test_a_dashboard_layout_is_saved_and_reset(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    saved = client.patch("/api/me/preferences", json={"dashboard": LAYOUT}, headers=anna)

    assert saved.status_code == 200, saved.text
    assert saved.json()["dashboard"] == LAYOUT
    assert client.get("/api/auth/me", headers=anna).json()["preferences"]["dashboard"] == LAYOUT
    other = client.patch("/api/me/preferences", json={"value_range": "3M"}, headers=anna).json()
    assert other["dashboard"] == LAYOUT  # saving another key keeps the layout
    assert client.patch("/api/me/preferences", json={"dashboard": None}, headers=anna).json()["dashboard"] is None


def test_a_bad_layout_is_refused(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    tile = LAYOUT["tiles"][1]
    bad = [
        {**LAYOUT, "version": 2},
        {"version": 1, "tiles": [{**tile, "kind": "weather"}]},
        {"version": 1, "tiles": [{**tile, "variant": "M4"}]},  # a single metric is S only
        {"version": 1, "tiles": [{**tile, "size": "S"}]},  # a size and a variant at once
        {"version": 1, "tiles": [{**{k: v for k, v in tile.items() if k != "variant"}, "size": "L"}]},
        {"version": 1, "tiles": [{**{k: v for k, v in tile.items() if k != "variant"}, "size": ["S"]}]},
        {"version": 1, "tiles": [{**LAYOUT["tiles"][0], "settings": {"fields": ["xirr"] * 9}}]},  # 8 fields at most
        {"version": 1, "tiles": [{**LAYOUT["tiles"][5], "settings": {"count": 4, "period": "1y"}}]},
        {"version": 1, "tiles": [{**tile, "settings": {"metric": "luck"}}]},
        {"version": 1, "tiles": [{**tile, "settings": {"metric": "xirr", "x": 1}}]},
        {"version": 1, "tiles": [{**tile, "id": "bad id!"}]},
        {"version": 1, "tiles": [tile, tile]},  # the same id twice
        {"version": 1, "tiles": [{**tile, "id": f"t{i}"} for i in range(41)]},
    ]

    for layout in bad:
        response = client.patch("/api/me/preferences", json={"dashboard": layout}, headers=anna)
        assert response.status_code == 422, layout


def test_a_stored_layout_that_no_longer_validates_reads_as_the_default(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    anna = login_as("anna@portfolio.dev")
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "anna@portfolio.dev"))
        user.preferences = {"value_range": "3M", "dashboard": {"version": 1, "tiles": [{"kind": "gone"}]}}
        db.commit()

    prefs = client.get("/api/auth/me", headers=anna).json()["preferences"]

    assert (prefs["dashboard"], prefs["value_range"]) == (None, "3M")


def test_a_layout_of_plan_9_reads_and_saves_as_variants(client: TestClient, login_as: LoginAs, engine: Engine) -> None:
    anna = login_as("anna@portfolio.dev")
    old = {"version": 1, "tiles": [
        {"id": "s", "kind": "summary", "size": "L", "settings": {"fields": ["total_gain"]}},
        {"id": "m", "kind": "metric", "size": "S", "settings": {"metric": "xirr"}},
        {"id": "v", "kind": "value_chart", "size": "L", "settings": {"range": "1R"}},
        {"id": "a", "kind": "analysis", "size": "L", "settings": {"metrics": ["xirr"], "period": "all"}},
        {"id": "l", "kind": "limits", "size": "M", "settings": {}},
    ]}
    with Session(engine) as db:
        user = db.scalar(select(User).where(User.email == "anna@portfolio.dev"))
        user.preferences = {"dashboard": old}
        db.commit()

    read = client.get("/api/auth/me", headers=anna).json()["preferences"]["dashboard"]
    saved = client.patch("/api/me/preferences", json={"dashboard": old}, headers=anna).json()["dashboard"]

    assert [(t["id"], t["variant"]) for t in read["tiles"]] == [("s", "L"), ("m", "S2"), ("v", "L6"), ("a", "Lc"), ("l", "M2")]
    assert saved == read
    assert all("size" not in t for t in saved["tiles"])
