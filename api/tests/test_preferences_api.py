from collections.abc import Callable

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, User

LoginAs = Callable[[str], dict[str, str]]
DEFAULTS = {"start_screen": "dashboard", "accounts_start": "last", "accounts_fixed": [], "analysis_period": "all",
            "holdings_period": "all", "value_range": "1R", "price_range": "buy",
            "holdings_without_fixed_income": False}


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
