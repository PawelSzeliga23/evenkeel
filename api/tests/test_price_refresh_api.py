"""POST /api/portfolio/refresh: fetches the user's prices and NBP rates now, at most once a minute."""
import datetime as dt
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.market.deps import get_market_providers
from app.market.types import ProviderError
from app.models import Account, Instrument, PositionLot, User
from tests.market_fakes import SXR8, FakePrices, fake_providers
from tests.valuation_seed import AT_BUY, seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/portfolio/refresh"


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict:
    anna, bartek, celina = (login_as(f"{name}@portfolio.dev") for name in ("anna", "bartek", "celina"))
    with Session(engine, expire_on_commit=False) as db:
        users = {u.email: u.id for u in db.scalars(select(User))}
        sxr8 = seed_market(db)
        seed_holdings(db, users["anna@portfolio.dev"], sxr8)
        other = Instrument(xtb_ticker="EIMI.UK", name="EM IMI", category="etf", currency="USD", price_symbol="EIMI.L",
                           price_checked_at=dt.datetime(2026, 9, 25, 21, 0, tzinfo=dt.UTC))
        db.add(other)
        account = Account(user_id=users["bartek@portfolio.dev"], name="XTB", kind="broker", wrapper="regular",
                          broker="xtb", external_account_number="1", currency="PLN")
        db.add(account)
        db.flush()
        db.add(PositionLot(account_id=account.id, instrument_id=other.id, xtb_position_id="1", side="buy",
                           quantity=1, open_price=10, opened_at=AT_BUY, raw={}))
        db.commit()
        valuate(db, users["anna@portfolio.dev"])
    prices = FakePrices({"SXR8.DE": SXR8, "EIMI.L": SXR8})
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(prices=prices)
    return {"anna": anna, "bartek": bartek, "celina": celina, "prices": prices, "sxr8": sxr8}


def _when(value: str | None) -> dt.datetime | None:
    return None if value is None else dt.datetime.fromisoformat(value)


def test_refresh_fetches_only_the_users_instruments_and_reports_the_time(client: TestClient, world: dict) -> None:
    before = dt.datetime.now(dt.UTC)
    body = client.post(URL, headers=world["anna"]).json()

    assert body["fetched"] is True
    assert _when(body["refreshed_at"]) >= before - dt.timedelta(seconds=1)
    assert [symbol for symbol, _ in world["prices"].calls] == ["SXR8.DE"]
    summary = client.get("/api/portfolio/summary", headers=world["anna"]).json()
    assert _when(summary["prices_refreshed_at"]) == _when(body["refreshed_at"])


def test_a_second_refresh_within_a_minute_fetches_nothing(client: TestClient, world: dict) -> None:
    first = client.post(URL, headers=world["anna"]).json()
    second = client.post(URL, headers=world["anna"]).json()

    assert (second["fetched"], _when(second["refreshed_at"])) == (False, _when(first["refreshed_at"]))
    assert len(world["prices"].calls) == 1


def test_a_user_without_instruments_gets_nothing_to_refresh(client: TestClient, world: dict) -> None:
    body = client.post(URL, headers=world["celina"]).json()
    summary = client.get("/api/portfolio/summary", headers=world["celina"]).json()

    assert body == {"refreshed_at": None, "fetched": False}
    assert summary["prices_refreshed_at"] is None
    assert world["prices"].calls == []


def test_a_provider_failure_is_reported_on_the_instrument_not_as_an_error(
    client: TestClient, world: dict, engine: Engine,
) -> None:
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(
        prices=FakePrices(errors={"SXR8.DE": ProviderError("rate limited")}))

    response = client.post(URL, headers=world["anna"])

    assert (response.status_code, response.json()["fetched"]) == (200, True)
    with Session(engine) as db:
        assert db.get(Instrument, world["sxr8"]).price_error is not None


def test_refresh_needs_a_signed_in_user(client: TestClient, world: dict) -> None:
    assert client.post(URL).status_code == 401
