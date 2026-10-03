import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, Instrument, Price, Transaction, User
from app.reviews.prompt import SECTIONS
from app.valuation.service import local_today
from tests.tag_seed import tag_world
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
NBSP = " "


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = seed_holdings(db, user_id, seed_market(db))
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id, "user_id": user_id}


def _package(client: TestClient, headers: dict, **params: object) -> str:
    response = client.get("/api/reviews/package", params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.text


def test_package_has_the_instructions_and_the_answer_headings(client: TestClient, world: dict) -> None:
    response = client.get("/api/reviews/package", headers=world["anna"])

    assert response.headers["content-type"].startswith("text/markdown")
    assert "evenkeel-przeglad-" in response.headers["content-disposition"]
    assert "````markdown" in response.text
    for section in SECTIONS:
        assert f"## {section}" in response.text


def test_package_has_the_portfolio_numbers_from_the_services(client: TestClient, world: dict) -> None:
    body = _package(client, world["anna"])

    assert f"10{NBSP}804,20{NBSP}zł" in body  # the summary's payout value
    assert "SXR8.DE" in body
    assert "02.03.2026" in body  # the lot's purchase day


def test_package_never_has_account_numbers_or_the_email(client: TestClient, world: dict) -> None:
    body = _package(client, world["anna"])

    assert "56216965" not in body
    assert "anna@portfolio.dev" not in body


def test_package_follows_the_account_filter(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        other = Account(user_id=world["user_id"], name="Drugie", kind="broker", broker="xtb",
                        external_account_number="99999999", currency="PLN")
        pko = Instrument(xtb_ticker="PKO.PL", name="PKO Bank Polski", category="stock", currency="PLN")
        db.add_all([other, pko])
        db.flush()
        db.add_all([
            Price(instrument_id=pko.id, date=dt.date(2026, 9, 25), close=Decimal("50"), source="yahoo"),
            Transaction(account_id=other.id, instrument_id=pko.id, type="buy", xtb_type="Stock purchase",
                        occurred_at=dt.datetime(2026, 9, 25, 10, tzinfo=dt.UTC), amount=Decimal("-500"),
                        currency="PLN", quantity=Decimal("10"), price=Decimal("50"), external_id="p1",
                        comment="", raw={}),
        ])
        db.commit()

    chosen = _package(client, world["anna"], account_id=world["account_id"])
    foreign = client.get("/api/reviews/package", params={"account_id": world["account_id"]}, headers=world["bartek"])

    assert "SXR8.DE" in chosen and "PKO.PL" not in chosen
    assert foreign.status_code == 404


def test_package_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/reviews/package").status_code == 401


def test_limits_follow_the_chosen_accounts(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        regular = Account(user_id=world["user_id"], name="Zwykłe", kind="cash", currency="PLN")
        db.add(regular)
        db.commit()
        regular_id = regular.id

    only_regular = _package(client, world["anna"], account_id=regular_id)
    with_ike = _package(client, world["anna"])

    assert "| IKE |" not in only_regular
    assert "| IKE |" in with_ike


def test_package_values_the_portfolio_once(client: TestClient, world: dict, monkeypatch: pytest.MonkeyPatch) -> None:
    import app.reviews.package as package

    calls: dict[str, int] = {"build_positions": 0, "portfolio_analytics": 0}
    for name in calls:
        original = getattr(package, name)

        def counted(*args, _name=name, _original=original, **kwargs):
            calls[_name] += 1
            return _original(*args, **kwargs)

        monkeypatch.setattr(package, name, counted)

    _package(client, world["anna"])

    assert calls == {"build_positions": 1, "portfolio_analytics": 2}  # positions once; analytics for all and 1y


@pytest.fixture
def tagged(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    return tag_world(client, login_as, engine)


def _note(client: TestClient, world: dict, url: str, method: str = "post", **body: object) -> None:
    response = getattr(client, method)(url, json=body, headers=world["anna"])
    assert response.status_code in (200, 201), response.text


def test_package_has_the_owners_theses_and_recent_entries(client: TestClient, tagged: dict) -> None:
    today = local_today()
    _note(client, tagged, "/api/theses", "put", instrument_id=tagged["sxr8"], body="Rdzeń portfela.\nNie sprzedaję.")
    _note(client, tagged, "/api/theses", "put", bond_series="EDO0336", body="Na emeryturę.")
    _note(client, tagged, "/api/journal", body="Zmieniam podział na 80/20.", entry_date=(today - dt.timedelta(days=10)).isoformat())
    _note(client, tagged, "/api/journal", body="Dokupiłem.", instrument_id=tagged["sxr8"], entry_date=today.isoformat())
    _note(client, tagged, "/api/journal", body="Bardzo stary wpis.", entry_date=(today - dt.timedelta(days=400)).isoformat())

    body = _package(client, tagged["anna"])

    section = body.split("## Notatki właściciela", 1)[1].split("## Scenariusze", 1)[0]
    assert "- **SXR8.DE — Core S&P 500:** Rdzeń portfela.\n  Nie sprzedaję." in section
    assert "- **EDO0336:** Na emeryturę." in section
    old, new = (today - dt.timedelta(days=10)).strftime("%d.%m.%Y"), today.strftime("%d.%m.%Y")
    assert section.index(f"- {old} · portfel: Zmieniam podział na 80/20.") < section.index(f"- {new} · SXR8.DE: Dokupiłem.")
    assert "Bardzo stary wpis." not in section
    assert "### Dziennik (ostatnie 12 miesięcy)" in section


def test_package_notes_follow_the_account_filter(client: TestClient, tagged: dict) -> None:
    _note(client, tagged, "/api/theses", "put", instrument_id=tagged["sxr8"], body="Rdzeń portfela.")
    _note(client, tagged, "/api/journal", body="O całym portfelu.")

    body = _package(client, tagged["anna"], account_id=tagged["plain"])

    assert "Rdzeń portfela." not in body
    assert "· portfel: O całym portfelu." in body


def test_package_without_notes_says_so_or_leaves_them_out(client: TestClient, world: dict) -> None:
    assert "## Notatki właściciela\n\nBrak notatek." in _package(client, world["anna"])
    assert "## Notatki właściciela" not in _package(client, world["anna"], notes="false")
