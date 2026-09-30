"""Several accounts at once: `?account_id=a&account_id=b` gives the sum (or the union) of the single accounts."""
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Transaction, User
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
ON = {"date": "2026-09-26"}
MONEY = ("value_pln", "market_value_pln", "exit_cost_pln", "cash_pln", "invested_pln")


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        ids = [seed_holdings(db, user_id, instrument_id, number=n) for n in ("1", "2", "3")]
        # the first account sells one of its two units, so it differs from the third one
        db.add(Transaction(account_id=ids[0], instrument_id=instrument_id, type="sell", xtb_type="sell",
                           occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC), amount=Decimal("2550.00"),
                           currency="PLN", external_id="5", comment="", raw={}, quantity=Decimal("1"),
                           price=Decimal("600"), xtb_position_id="777"))
        db.commit()
        valuate(db, user_id)
    foreign = client.post("/api/accounts", json={"name": "Bartka", "kind": "cash"}, headers=bartek).json()["id"]
    return {"anna": anna, "ids": ids, "foreign": foreign}


def _get(client: TestClient, world: dict, url: str, ids: list[int] | None, **params: object) -> dict | list:
    query = {**params, **({"account_id": ids} if ids is not None else {})}
    response = client.get(url, params=query, headers=world["anna"])
    assert response.status_code == 200, response.json()
    return response.json()


def test_summary_of_two_accounts_is_the_sum_of_each(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/portfolio/summary", ids) for ids in ([a], [c], [a, c]))

    for field in MONEY:
        assert Decimal(both[field]) == Decimal(one[field]) + Decimal(other[field]), field
    assert {item["key"] for item in both["by_account"]} == {str(a), str(c)}


def test_no_filter_is_the_whole_portfolio_and_a_repeated_id_counts_once(client: TestClient, world: dict) -> None:
    a, b, c = world["ids"]
    singles = [_get(client, world, "/api/portfolio/summary", [i]) for i in (a, b, c)]
    whole = _get(client, world, "/api/portfolio/summary", None)
    repeated = _get(client, world, "/api/portfolio/summary", [a, a])

    assert Decimal(whole["value_pln"]) == sum(Decimal(s["value_pln"]) for s in singles)
    assert repeated == singles[0]


def test_value_history_of_two_accounts_is_the_daily_sum(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/portfolio/history", ids, **{"from": "2026-09-24"})
                        for ids in ([a], [c], [a, c]))

    summed = {p["date"]: Decimal(p["value_pln"]) for p in one["points"]}
    for point in other["points"]:
        summed[point["date"]] += Decimal(point["value_pln"])
    assert {p["date"]: Decimal(p["value_pln"]) for p in both["points"]} == summed


def test_positions_of_two_accounts_are_both_lists(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/positions", ids, **ON) for ids in ([a], [c], [a, c]))

    def keys(items: list[dict]) -> set[tuple]:
        return {(i["kind"], i["account_id"], i["instrument_id"]) for i in items}

    assert keys(both) == keys(one) | keys(other)
    assert abs(sum(Decimal(i["share_pct"]) for i in both) - 100) <= Decimal("0.05")


def test_exposure_of_two_accounts_adds_up_per_currency(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/portfolio/exposure", ids) for ids in ([a], [c], [a, c]))

    def by_currency(body: dict) -> dict[str, Decimal]:
        return {item["currency"]: Decimal(item["value_pln"]) for item in body["current"]}

    expected = by_currency(one)
    for code, value in by_currency(other).items():
        expected[code] = expected.get(code, Decimal(0)) + value
    assert by_currency(both) == expected


def test_closed_of_two_accounts_lists_the_sales_of_both(client: TestClient, world: dict) -> None:
    a, b, c = world["ids"]
    with_sale, without = _get(client, world, "/api/portfolio/closed", [a]), _get(client, world, "/api/portfolio/closed", [c])
    both = _get(client, world, "/api/portfolio/closed", [a, c])

    assert (len(with_sale["sales"]), len(without["sales"]), len(both["sales"])) == (1, 0, 1)
    assert both["totals"] == with_sale["totals"]
    assert _get(client, world, "/api/portfolio/closed", [b, c])["sales"] == []


def test_operation_history_of_two_accounts_is_both_lists(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/history", ids, limit=200) for ids in ([a], [c], [a, c]))

    assert {i["id"] for i in both["items"]} == {i["id"] for i in one["items"]} | {i["id"] for i in other["items"]}
    assert {i["account_id"] for i in both["items"]} == {a, c}


@pytest.mark.parametrize("url", [
    "/api/portfolio/summary", "/api/portfolio/history", "/api/positions", "/api/portfolio/exposure",
    "/api/portfolio/closed", "/api/history",
])
def test_someone_elses_account_in_the_list_is_404(client: TestClient, world: dict, url: str) -> None:
    response = client.get(url, params={"account_id": [world["ids"][0], world["foreign"]]}, headers=world["anna"])
    assert (response.status_code, response.json()["code"]) == (404, "not_found")


@pytest.mark.parametrize("bad", ["0", str(2**31)])
def test_an_id_out_of_range_is_a_validation_error(client: TestClient, world: dict, bad: str) -> None:
    response = client.get("/api/portfolio/summary", params={"account_id": [world["ids"][0], bad]},
                          headers=world["anna"])
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
