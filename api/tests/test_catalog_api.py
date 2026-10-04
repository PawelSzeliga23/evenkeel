import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.market.deps import get_market_providers
from app.market.types import PriceBar, PriceHistory, ProviderError
from app.models import CatalogAddition, Instrument, Price, User
from tests.market_fakes import FakePrices, fake_providers
from tests.valuation_seed import seed_holdings, seed_market

LoginAs = Callable[[str], dict[str, str]]
VWCE = PriceHistory(
    "VWCE.DE", "EUR", (PriceBar(dt.date(2019, 7, 25), Decimal("50.00")), PriceBar(dt.date(2026, 9, 25), Decimal("140.00"))),
    name="Vanguard FTSE All-World UCITS ETF USD Accumulation", kind="etf",
)


@pytest.fixture
def anna(client: TestClient, login_as: LoginAs) -> dict[str, str]:
    return login_as("anna@portfolio.dev")


@pytest.fixture
def prices(client: TestClient) -> FakePrices:
    fake = FakePrices({"VWCE.DE": VWCE})
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(prices=fake)
    return fake


def _catalog(engine: Engine, *instruments: Instrument) -> None:
    with Session(engine) as db:
        db.add_all(instruments)
        db.commit()


def test_catalog_lists_held_first_then_groups_in_order(client: TestClient, anna: dict, engine: Engine) -> None:
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        seed_holdings(db, user_id, seed_market(db))  # SXR8.DE, held, with two prices
    _catalog(engine,
             Instrument(xtb_ticker="PKO.PL", name="PKO Bank Polski", currency="PLN", in_catalog=True,
                        catalog_group="Akcje GPW"),
             Instrument(xtb_ticker="EUNL.DE", name="iShares Core MSCI World", currency="EUR", in_catalog=True,
                        catalog_group="ETF: świat", accumulating=True))

    body = client.get("/api/catalog", headers=anna).json()

    assert [group["group"] for group in body] == ["Twój portfel", "ETF: świat", "Akcje GPW"]
    held = body[0]["items"][0]
    assert (held["ticker"], held["prices_from"], held["group"]) == ("SXR8.DE", "2026-03-02", "Twój portfel")
    assert body[1]["items"][0] == {
        "id": body[1]["items"][0]["id"], "ticker": "EUNL.DE", "name": "iShares Core MSCI World", "currency": "EUR",
        "group": "ETF: świat", "accumulating": True, "prices_from": None,
    }


def test_add_fetches_history_and_files_it_under_added(client: TestClient, anna: dict, prices: FakePrices,
                                                    engine: Engine) -> None:
    response = client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=anna)

    assert response.status_code == 201
    assert response.json()["name"] == "Vanguard FTSE All-World UCITS ETF USD Accumulation"
    assert (response.json()["group"], response.json()["prices_from"]) == ("Dodane przez Ciebie", "2019-07-25")
    with Session(engine) as db:
        added = db.scalar(select(Instrument).where(Instrument.xtb_ticker == "VWCE.DE"))
        assert (added.in_catalog, added.category, added.currency, added.price_symbol) == (True, "etf", "EUR", "VWCE.DE")
        assert added.price_checked_at is not None
        assert db.scalar(select(func.count()).select_from(Price).where(Price.instrument_id == added.id)) == 2


def test_add_normalizes_the_ticker(client: TestClient, anna: dict, prices: FakePrices) -> None:
    assert client.post("/api/catalog", json={"ticker": " vwce.de "}, headers=anna).json()["ticker"] == "VWCE.DE"


def test_add_a_plain_yahoo_symbol_keeps_it_as_a_manual_symbol(client: TestClient, anna: dict, engine: Engine) -> None:
    fake = FakePrices({"QQQM": PriceHistory("QQQM", "USD", (PriceBar(dt.date(2020, 10, 13), Decimal("100")),),
                                            name="Invesco NASDAQ 100 ETF", kind="etf")})
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(prices=fake)

    assert client.post("/api/catalog", json={"ticker": "qqqm"}, headers=anna).status_code == 201
    with Session(engine) as db:
        added = db.scalar(select(Instrument).where(Instrument.xtb_ticker == "QQQM"))
        assert (added.price_symbol, added.price_symbol_overridden) == ("QQQM", True)


def test_add_existing_ticker_returns_it_without_fetching(client: TestClient, anna: dict, prices: FakePrices,
                                                        engine: Engine) -> None:
    _catalog(engine, Instrument(xtb_ticker="EUNL.DE", name="MSCI World", in_catalog=True, catalog_group="ETF: świat"),
             Instrument(xtb_ticker="VIE.FR", name="Veolia", price_symbol="VIE.PA"))

    first = client.post("/api/catalog", json={"ticker": "eunl.de"}, headers=anna)
    second = client.post("/api/catalog", json={"ticker": "VIE.PA"}, headers=anna)

    assert (first.status_code, first.json()["group"]) == (200, "ETF: świat")
    assert (second.status_code, second.json()["group"]) == (200, "Dodane przez Ciebie")
    assert prices.calls == []


def test_add_unknown_ticker_is_422(client: TestClient, anna: dict, prices: FakePrices, engine: Engine) -> None:
    response = client.post("/api/catalog", json={"ticker": "NOPE.DE"}, headers=anna)

    assert (response.status_code, response.json()["code"], response.json()["message"]) == (
        422, "unknown_ticker", "Yahoo nie zna tego tickera.")
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Instrument)) == 0


def test_add_when_yahoo_fails_saves_nothing(client: TestClient, anna: dict, engine: Engine) -> None:
    fake = FakePrices(errors={"VWCE.DE": ProviderError("HTTP 503")})
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(prices=fake)

    response = client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=anna)

    assert (response.status_code, response.json()["code"]) == (502, "provider_failed")
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Instrument)) == 0


@pytest.mark.parametrize("ticker", ["", "   ", "A" * 41, "VWCE DE", "<script>"])
def test_add_rejects_malformed_tickers(client: TestClient, anna: dict, prices: FakePrices, ticker: str) -> None:
    assert client.post("/api/catalog", json={"ticker": ticker}, headers=anna).status_code == 422
    assert prices.calls == []


def test_catalog_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/catalog").status_code == 401
    assert client.post("/api/catalog", json={"ticker": "VWCE.DE"}).status_code == 401


def _added_by(engine: Engine, email: str, count: int) -> None:
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == email))
        for i in range(count):
            instrument = Instrument(xtb_ticker=f"X{i}.DE", name=f"X{i}", in_catalog=True,
                                    catalog_group="Dodane przez Ciebie")
            db.add(instrument)
            db.flush()
            db.add(CatalogAddition(user_id=user_id, instrument_id=instrument.id))
        db.commit()


def test_a_user_adds_at_most_50_instruments(client: TestClient, anna: dict, prices: FakePrices,
                                            engine: Engine, login_as: LoginAs) -> None:
    bartek = login_as("bartek@portfolio.dev")
    _added_by(engine, "anna@portfolio.dev", 50)

    response = client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=anna)

    assert (response.status_code, response.json()["code"]) == (422, "catalog_full")
    assert prices.calls == []
    assert client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=bartek).status_code == 201


def test_added_tickers_are_shown_only_to_who_added_them(client: TestClient, anna: dict, prices: FakePrices,
                                                         login_as: LoginAs) -> None:
    bartek = login_as("bartek@portfolio.dev")
    client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=anna)

    def added(headers: dict) -> list[str]:
        groups = {g["group"]: [i["ticker"] for i in g["items"]] for g in client.get("/api/catalog", headers=headers).json()}
        return groups.get("Dodane przez Ciebie", [])

    assert (added(anna), added(bartek)) == (["VWCE.DE"], [])
    again = client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=bartek)  # known: no second fetch
    assert (again.status_code, added(bartek), len(prices.calls)) == (200, ["VWCE.DE"], 1)


def test_adding_is_rate_limited_per_user(make_app: Callable, login_as: LoginAs) -> None:
    client = TestClient(make_app(catalog_add_rate_limit_per_minute=2))
    fake = FakePrices({"VWCE.DE": VWCE})
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(prices=fake)
    password = "bardzo-tajne-haslo"
    client.post("/api/auth/register", json={"email": "anna@portfolio.dev", "password": password})
    token = client.post("/api/auth/login", json={"email": "anna@portfolio.dev", "password": password}).json()
    anna = {"Authorization": f"Bearer {token['access_token']}"}

    codes = [client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=anna).status_code for _ in range(3)]

    assert codes == [201, 200, 429]


def test_add_racing_another_add_returns_the_existing(client: TestClient, anna: dict, engine: Engine) -> None:
    class Racing(FakePrices):
        def history(self, symbol: str, start: dt.date | None) -> PriceHistory:
            with Session(engine) as db:  # another request saves the same ticker while ours fetches
                db.add(Instrument(xtb_ticker="VWCE.DE", name="Vanguard", currency="EUR", price_symbol="VWCE.DE",
                                  in_catalog=True, catalog_group="Dodane przez Ciebie"))
                db.commit()
            return super().history(symbol, start)

    fake = Racing({"VWCE.DE": VWCE})
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(prices=fake)

    response = client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=anna)

    assert (response.status_code, response.json()["ticker"]) == (200, "VWCE.DE")
    assert client.get("/api/catalog", headers=anna).status_code == 200


def test_add_racing_an_import_puts_the_winner_in_the_catalog(client: TestClient, anna: dict, engine: Engine) -> None:
    class Racing(FakePrices):
        def history(self, symbol: str, start: dt.date | None) -> PriceHistory:
            with Session(engine) as db:  # an XTB import saves the same ticker meanwhile, outside the catalog
                db.add(Instrument(xtb_ticker="VWCE.DE", name="Vanguard", currency="EUR"))
                db.commit()
            return super().history(symbol, start)

    fake = Racing({"VWCE.DE": VWCE})
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(prices=fake)

    client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=anna)

    groups = {group["group"]: [item["ticker"] for item in group["items"]]
              for group in client.get("/api/catalog", headers=anna).json()}
    assert groups["Dodane przez Ciebie"] == ["VWCE.DE"]
