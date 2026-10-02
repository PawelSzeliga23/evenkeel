import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.analytics.tags import _thin
from app.models import Account, Transaction, User
from tests.tag_seed import add_link as _link
from tests.tag_seed import add_tag as _tag
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        sxr8 = seed_market(db)
        account_id = seed_holdings(db, user_id, sxr8)
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "user_id": user_id, "account_id": account_id, "sxr8": sxr8}


def _get(client: TestClient, headers: dict, **params: object) -> dict:
    response = client.get("/api/analytics/tags", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _second_account_with_cash(engine: Engine, world: dict) -> int:
    with Session(engine) as db:
        account = Account(user_id=world["user_id"], name="Drugie", kind="broker", wrapper="regular", currency="PLN")
        db.add(account)
        db.flush()
        db.add(Transaction(account_id=account.id, type="deposit", xtb_type="deposit",
                           occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC), amount=Decimal("1000"),
                           currency="PLN", external_id="d-2", comment="", raw={}))
        db.commit()
        account_id = account.id
        valuate(db, world["user_id"])
    return account_id


def test_a_tag_sums_its_holdings_with_the_share_of_the_whole_portfolio(client: TestClient, world: dict) -> None:
    usa = _tag(client, world["anna"], "USA")
    _link(client, world, usa, instrument_id=world["sxr8"])
    _link(client, world, usa, instrument_id=world["sxr8"], account_id=world["account_id"])  # both levels

    body = _get(client, world["anna"], period="all")

    assert body["total_pln"] == "10804.20"
    (row,) = body["tags"]
    assert (row["name"], row["value_pln"], row["gain_pln"], row["gain_pct"], row["holdings"]) == (
        "USA", "5074.50", "804.20", "18.68", 1)  # counted once although tagged on both levels
    assert row["share_pct"] == "46.97"  # 5074.50 / 10804.20
    assert body["untagged"] is None
    assert body["cash"] == {"value_pln": "5729.70", "share_pct": "53.03"}


def test_untagged_holdings_and_no_tags(client: TestClient, world: dict) -> None:
    body = _get(client, world["anna"], period="all")

    assert body["tags"] == []
    assert (body["untagged"]["value_pln"], body["untagged"]["holdings"]) == ("5074.50", 1)


def test_a_holding_in_two_tags_counts_in_both(client: TestClient, world: dict) -> None:
    for name in ("USA", "emerytura"):
        _link(client, world, _tag(client, world["anna"], name), instrument_id=world["sxr8"])

    rows = _get(client, world["anna"], period="all")["tags"]

    assert [(r["name"], r["value_pln"]) for r in rows] == [("emerytura", "5074.50"), ("USA", "5074.50")]


def test_a_holding_on_two_accounts_tagged_on_one_counts_there_only(
        client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        seed_holdings(db, world["user_id"], world["sxr8"], number="11111111")
        valuate(db, world["user_id"])
    tag = _tag(client, world["anna"], "IKE")
    _link(client, world, tag, instrument_id=world["sxr8"], account_id=world["account_id"])

    body = _get(client, world["anna"], period="all")

    (row,) = body["tags"]
    assert (row["value_pln"], row["holdings"]) == ("5074.50", 1)
    assert (body["untagged"]["value_pln"], body["untagged"]["holdings"]) == ("5074.50", 1)


def test_the_account_filter_leaves_out_tags_without_value(client: TestClient, world: dict, engine: Engine) -> None:
    other = _second_account_with_cash(engine, world)  # an account of anna with a 1 000 zł deposit, valuated
    tag = _tag(client, world["anna"], "IKE")
    _link(client, world, tag, instrument_id=world["sxr8"], account_id=world["account_id"])

    body = _get(client, world["anna"], period="all", account_id=other)

    assert body["tags"] == [] and body["untagged"] is None and body["cash"]["value_pln"] == "1000.00"


def test_history_shares_with_todays_tags(client: TestClient, world: dict) -> None:
    usa = _tag(client, world["anna"], "USA")
    _link(client, world, usa, instrument_id=world["sxr8"])

    history = _get(client, world["anna"], period="1d")["history"]

    assert history["dates"][0] == "2026-03-01" and history["dates"][-1] == "2026-09-26"
    (series,) = [s for s in history["series"] if s["key"] == str(usa["id"])]
    assert series["share_pct"][0] == "0.00"  # only the deposit on 03-01
    assert series["share_pct"][-1] == "46.97"
    assert len(history["series"]) == 2  # USA and "untagged"


def test_no_valuation_gives_an_empty_answer(client: TestClient, world: dict) -> None:
    body = _get(client, world["bartek"], period="all")

    assert (body["period"], body["tags"], body["untagged"], body["history"]) == (
        None, [], None, {"dates": [], "series": []})


def test_thinning_keeps_at_most_400_days_with_both_ends() -> None:
    kept = _thin(1000)

    assert len(kept) <= 400 and kept[0] == 0 and kept[-1] == 999
    assert _thin(5) == [0, 1, 2, 3, 4]
    assert len(_thin(1001)) <= 400 and _thin(1001)[-1] == 1000
