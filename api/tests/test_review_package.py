import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, Instrument, Price, SavingsAccount, SavingsBalance, SavingsRate, Transaction, User
from app.reviews.fmt import money, pct
from app.reviews.prompt import SECTIONS
from app.valuation.service import local_today
from tests.tag_seed import add_link, add_tag, tag_world
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


def _section(body: str, heading: str) -> str:
    """The text of one package section: from its heading to the next `## `."""
    return body.split(f"\n{heading}", 1)[1].split("\n## ", 1)[0]


def _dec(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)


def _savings_balance(engine: Engine, world: dict) -> None:
    """Gives tag_world's savings account a balance, so the package lists it."""
    with Session(engine) as db:
        savings = db.scalar(select(SavingsAccount).where(SavingsAccount.account_id == world["savings"]))
        db.add_all([SavingsRate(savings_account_id=savings.id, valid_from=dt.date(2026, 9, 1), annual_rate=Decimal("5")),
                    SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 9, 1),
                                   balance=Decimal("10000"))])
        db.commit()
        valuate(db, world["user_id"])


def test_holdings_carry_their_tags_once(client: TestClient, tagged: dict, engine: Engine) -> None:
    _savings_balance(engine, tagged)
    anna = tagged["anna"]
    core, spec, retirement, cushion = (add_tag(client, anna, n) for n in ("core", "spekulacja", "emerytura", "poduszka"))
    add_link(client, tagged, core, instrument_id=tagged["sxr8"])
    add_link(client, tagged, core, instrument_id=tagged["sxr8"], account_id=tagged["ike"])  # both levels
    add_link(client, tagged, spec, instrument_id=tagged["sxr8"], account_id=tagged["plain"])  # another account
    add_link(client, tagged, retirement, bond_series="EDO0336")
    add_link(client, tagged, cushion, account_id=tagged["savings"])

    body = _package(client, anna)

    positions = _section(body, "## Pozycje")
    assert "| Uwagi | Tagi |" in positions
    sxr8_row = next(line for line in positions.splitlines() if line.startswith("| SXR8.DE |"))
    assert sxr8_row.endswith("| core |")  # once, and not the plain account's „spekulacja”
    bonds = _section(body, "## Obligacje")
    assert "| Konto | Tagi |" in bonds and "| emerytura |" in bonds
    savings = _section(body, "## Konta oszczędnościowe")
    assert "| poduszka |" in savings
    assert any(word in savings for word in ("| codzienna |", "| miesięczna |", "| kwartalna |"))


def test_a_holding_without_tags_shows_a_dash(client: TestClient, world: dict) -> None:
    positions = _section(_package(client, world["anna"]), "## Pozycje")

    sxr8_row = next(line for line in positions.splitlines() if line.startswith("| SXR8.DE |"))
    assert sxr8_row.endswith("| — |")


def test_package_has_the_tags_with_share_and_gain(client: TestClient, tagged: dict) -> None:
    anna = tagged["anna"]
    core = add_tag(client, anna, "core")
    add_link(client, tagged, core, instrument_id=tagged["sxr8"])
    report = client.get("/api/analytics/tags", params={"period": "all"}, headers=anna).json()
    (row,) = report["tags"]

    section = _section(_package(client, anna), "## Tagi")

    assert "| Tag | Wartość | Udział w portfelu | Zysk (cały okres) | Zysk % | Walorów |" in section
    assert (f"| core | {money(Decimal(row['value_pln']))} | {pct(Decimal(row['share_pct']))} | "
            f"{money(Decimal(row['gain_pln']))} | {pct(Decimal(row['gain_pct']))} | 1 |") in section
    assert "| Bez tagu |" in section  # the bond is not tagged
    assert "udziały mogą sumować się do ponad 100" in section


def test_package_tags_follow_the_account_filter(client: TestClient, tagged: dict) -> None:
    anna = tagged["anna"]
    core = add_tag(client, anna, "core")
    add_link(client, tagged, core, instrument_id=tagged["sxr8"])

    section = _section(_package(client, anna, account_id=tagged["plain"]), "## Tagi")

    assert "| core |" not in section


def test_package_without_tags_says_so(client: TestClient, world: dict) -> None:
    assert _section(_package(client, world["anna"]), "## Tagi").strip() == "Brak tagów."


def test_package_ranks_the_holdings_over_three_periods(client: TestClient, world: dict) -> None:
    anna = world["anna"]
    whole = client.get("/api/analytics/holdings", params={"period": "all"}, headers=anna).json()
    month = client.get("/api/analytics/holdings", params={"period": "1m"}, headers=anna).json()
    (item,) = whole["items"]
    in_month = {i["key"]: i for i in month["items"]}.get(item["key"])

    section = _section(_package(client, anna), "## Walory")

    assert "| Walor | Typ | Wartość | Zysk 1 mies. | % | Zysk 1 rok | % | Zysk cały okres | % |" in section
    month_cells = (f"{money(Decimal(in_month['gain_pln']))} | {pct(_dec(in_month['gain_pct']))}" if in_month
                   else "— | —")
    assert (f"| SXR8.DE — Core S&P 500 | ETF | {money(Decimal(item['value_pln']))} | {month_cells} |") in section
    assert f"| {money(Decimal(item['gain_pln']))} | {pct(Decimal(item['gain_pct']))} |" in section
    assert "### Według kont" in section and "| XTB IKE |" in section
    assert "### Według typów" in section and "| ETF |" in section
    assert "cały okres: " in section  # the dates of the periods


def test_a_holding_outside_a_period_has_dashes(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:  # CD Projekt bought and sold in April: in the whole history only
        cdr = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", category="stock", currency="PLN", price_symbol="CDR.WA")
        db.add(cdr)
        db.flush()
        db.add(Price(instrument_id=cdr.id, date=dt.date(2026, 4, 1), close=Decimal("250"), source="yahoo"))
        for number, (kind, amount, day) in enumerate([("buy", "-500", 2), ("sell", "520", 3)], start=900):
            db.add(Transaction(account_id=world["account_id"], type=kind, xtb_type=kind, amount=Decimal(amount),
                               occurred_at=dt.datetime(2026, 4, day, 10, tzinfo=dt.UTC), currency="PLN",
                               external_id=str(number), comment="", raw={}, instrument_id=cdr.id,
                               quantity=Decimal("2"), price=Decimal("250")))
        db.commit()
        valuate(db, world["user_id"])

    section = _section(_package(client, world["anna"]), "## Walory")

    row = next(line for line in section.splitlines() if line.startswith("| CDR.PL — CD Projekt |"))
    assert "| — | — |" in row  # not in the last month
    assert section.index("| SXR8.DE") < section.index("| CDR.PL")  # by the whole-history gain, highest first


def test_package_has_income_and_costs(client: TestClient, world: dict) -> None:
    section = _section(_package(client, world["anna"]), "## Dochód i koszty")

    assert "| Ostatnie 12 miesięcy |" in section and "| Cały okres |" in section
    assert f"| SXR8.DE Core S&P 500 | dywidenda | {money(Decimal('40'))} | {money(Decimal('6'))} | {money(Decimal('34'))} |" in section
    assert f"| Przewalutowanie XTB | {money(Decimal('21.41'))} | 1 |" in section
    assert "### Miesiące (ostatnie 12)" in section and "| cze 2026 |" in section


def test_package_analysis_follows_the_account_filter(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        other = Account(user_id=world["user_id"], name="Puste", kind="broker", wrapper="regular", currency="PLN")
        db.add(other)
        db.commit()
        other_id = other.id

    body = _package(client, world["anna"], account_id=other_id)

    assert "SXR8.DE" not in _section(body, "## Walory")
    assert "dywidenda" not in _section(body, "## Dochód i koszty")


def test_month_label() -> None:
    from app.reviews.analysis import month_label

    assert month_label("2026-09") == "wrz 2026"


def test_the_instructions_ask_for_w_skrocie_and_read_tags_and_notes() -> None:
    from app.reviews.prompt import INSTRUCTIONS

    assert SECTIONS[0] == "W skrócie" and len(SECTIONS) == 10
    assert INSTRUCTIONS.index("`## W skrócie`") < INSTRUCTIONS.index("`## Ocena ogólna`")
    assert "Wywnioskuj z nich, do czego zmierzam — nie pytaj mnie o to." in INSTRUCTIONS
    assert "Potem od 1 do 5" in INSTRUCTIONS
    assert "rozwiń propozycje z „W skrócie”" in INSTRUCTIONS


def test_the_instructions_read_any_tag_names_as_roles() -> None:
    from app.reviews.prompt import INSTRUCTIONS

    assert "z tagów wynika, jaką rolę pełni każdy walor" in INSTRUCTIONS.replace("\n  ", " ")


def test_package_with_tags_outside_the_chosen_accounts_does_not_say_there_are_none(
    client: TestClient, tagged: dict,
) -> None:
    core = add_tag(client, tagged["anna"], "core")
    add_link(client, tagged, core, instrument_id=tagged["sxr8"])

    section = _section(_package(client, tagged["anna"], account_id=tagged["plain"]), "## Tagi").strip()

    assert section != "Brak tagów." and "nie ma tagów" in section


def test_package_says_when_the_valuation_is_still_being_recalculated(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    from app.valuation.service import mark_stale

    anna = login_as("anna@portfolio.dev")
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        seed_holdings(db, user_id, seed_market(db))
        mark_stale(db, [user_id], dt.date(2026, 3, 1))  # not valued yet: the worker will recompute
        db.commit()

    body = _package(client, anna)

    for heading in ("## Tagi", "## Walory"):  # income comes from the operations, not from the valuation
        assert "w trakcie przeliczania" in _section(body, heading), heading


def test_a_table_cell_stays_on_one_line() -> None:
    from app.reviews.fmt import table

    assert table(["Nazwa"], [["Konto\r\nwspólne | żony"]]) == "| Nazwa |\n|---|\n| Konto wspólne / żony |"
