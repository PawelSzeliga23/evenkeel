import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.analytics.income import fx_cost
from app.models import (Account, BondHolding, BondSeries, Instrument, SavingsAccount, SavingsBalance, SavingsRate,
                        Transaction, User)
from tests.valuation_seed import SAT, seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/analytics/income"


@pytest.fixture(autouse=True)
def saturday(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.analytics.income.local_today", lambda: SAT)


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
    response = client.get(URL, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


AFTER_CAPITALIZATION = dt.date(2026, 10, 5)  # September's interest is credited on 1 October


def _savings(engine: Engine, world: dict, monkeypatch: pytest.MonkeyPatch, wrapper: str = "regular") -> int:
    """A savings account with 10 000 zł from 1 September at 5 %, valued (and „today”) after its first credit."""
    monkeypatch.setattr("app.analytics.income.local_today", lambda: AFTER_CAPITALIZATION)
    with Session(engine) as db:
        account = Account(user_id=world["user_id"], name="Trade Republic", kind="savings", wrapper=wrapper, currency="PLN")
        db.add(account)
        db.flush()
        savings = SavingsAccount(account_id=account.id, capitalization="monthly")
        db.add(savings)
        db.flush()
        db.add_all([SavingsRate(savings_account_id=savings.id, valid_from=dt.date(2026, 9, 1), annual_rate=Decimal("5")),
                    SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 9, 1), balance=Decimal("10000"))])
        db.commit()
        valuate(db, world["user_id"], AFTER_CAPITALIZATION)
        return account.id


def test_fx_cost_is_the_fee_inside_the_amount() -> None:
    assert fx_cost(Decimal("-4304.30"), Decimal("0.005")) == Decimal("21.41")  # 4304.30 × 0.005 / 1.005
    assert fx_cost(Decimal("5100.00"), Decimal("0.005")) == Decimal("25.63")  # 5100 × 0.005 / 0.995
    assert fx_cost(Decimal("-810.00"), Decimal("0")) == Decimal("0")


def test_whole_history_income_and_costs(client: TestClient, world: dict) -> None:
    body = _get(client, world["anna"], period="all")

    assert body["period"] == {"start": "2026-03-01", "end": "2026-09-26"}
    assert body["totals"] == {"income_pln": "40.00", "costs_pln": "27.41", "balance_pln": "12.59"}  # 21.41 FX + 6 tax
    assert [m["month"] for m in body["months"]] == [f"2026-{m:02d}" for m in range(3, 10)]
    march = body["months"][0]
    assert (march["fx_pln"], march["costs_pln"], march["income_pln"]) == ("21.41", "21.41", "0.00")
    june = body["months"][3]
    assert (june["dividends_pln"], june["taxes_pln"], june["balance_pln"]) == ("40.00", "6.00", "34.00")
    assert body["sources"] == [{"key": f"d:{world['sxr8']}", "kind": "dividend", "name": "SXR8.DE Core S&P 500",
                                "gross_pln": "40.00", "tax_pln": "6.00", "net_pln": "34.00", "taxed": True}]
    assert body["costs"] == [
        {"key": "fx", "name": "Przewalutowanie XTB", "amount_pln": "21.41", "count": 1},
        {"key": "interest_tax", "name": "Podatek od odsetek", "amount_pln": "0.00", "count": 0},
        {"key": "withholding_tax", "name": "Podatek u źródła", "amount_pln": "6.00", "count": 1},
        {"key": "fees", "name": "Prowizje i opłaty", "amount_pln": "0.00", "count": 0},
    ]


def test_ytd_starts_at_the_first_month_with_history(client: TestClient, world: dict) -> None:
    body = _get(client, world["anna"], period="ytd")

    assert body["period"]["start"] == "2026-03-01" and body["months"][0]["month"] == "2026-03"


def test_twelve_months_end_in_the_current_month(client: TestClient, world: dict) -> None:
    months = _get(client, world["anna"], period="12m")["months"]

    assert (months[0]["month"], months[-1]["month"]) == ("2026-03", "2026-09")  # clamped to the history


def test_savings_interest_is_accrued_gross_and_the_deposit_is_not_income(
    client: TestClient, world: dict, engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _savings(engine, world, monkeypatch)

    body = _get(client, world["anna"], period="all")
    source = next(s for s in body["sources"] if s["kind"] == "savings")
    net, tax = Decimal(source["net_pln"]), Decimal(source["tax_pln"])

    assert source["name"] == "Trade Republic" and source["taxed"] is True
    assert Decimal("0") < net < Decimal("50")  # September's interest on 10 000 zł at 5 %, not the deposit
    assert abs(tax - net * Decimal(19) / Decimal(81)) <= Decimal("0.01")
    assert Decimal(body["costs"][1]["amount_pln"]) == tax


def test_savings_on_ike_pay_no_tax(
    client: TestClient, world: dict, engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    _savings(engine, world, monkeypatch, wrapper="ike")

    source = next(s for s in _get(client, world["anna"], period="all")["sources"] if s["kind"] == "savings")

    assert (source["tax_pln"], source["taxed"]) == ("0.00", False)


def test_a_bond_bought_in_the_period_earns_only_its_interest(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        bonds = Account(user_id=world["user_id"], name="Obligacje", kind="bonds", currency="PLN")
        db.add_all([bonds, BondSeries(series="EDO0336", bond_type="EDO", issue_month=dt.date(2026, 3, 1),
                                      maturity_months=120, first_period_rate=Decimal("6.25"), margin=Decimal("2.00"),
                                      early_redemption_fee=Decimal("3.00"), interest_mode="capitalized",
                                      rate_basis="cpi")])
        db.flush()
        db.add(BondHolding(account_id=bonds.id, bond_type="EDO", series="EDO0336", quantity=10,
                           purchase_date=dt.date(2026, 3, 2)))
        db.commit()
        valuate(db, world["user_id"])

    body = _get(client, world["anna"], period="all")
    bond = next(s for s in body["sources"] if s["kind"] == "bond")

    assert bond["key"] == "b:EDO0336"
    assert Decimal("0") < Decimal(bond["gross_pln"]) < Decimal("40")  # ~6.25 % of 1000 zł for 7 months, not 1000


def test_pln_instrument_on_xtb_has_no_conversion_cost(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        cdr = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", category="stock", currency="PLN", price_symbol="CDR.WA")
        db.add(cdr)
        db.flush()
        db.add(Transaction(account_id=world["account_id"], instrument_id=cdr.id, type="buy", xtb_type="buy",
                           occurred_at=dt.datetime(2026, 9, 21, 10, tzinfo=dt.UTC), amount=Decimal("-810"),
                           currency="PLN", quantity=Decimal("3"), price=Decimal("270"), external_id="cdr", comment="",
                           raw={}))
        db.commit()

    assert _get(client, world["anna"], period="all")["costs"][0]["count"] == 1  # only the SXR8.DE purchase


def test_xtb_interest_and_fees(client: TestClient, world: dict, engine: Engine) -> None:
    def tx(external_id: str, type_: str, amount: str) -> Transaction:
        return Transaction(account_id=world["account_id"], type=type_, xtb_type=type_, amount=Decimal(amount),
                           occurred_at=dt.datetime(2026, 9, 10, 10, tzinfo=dt.UTC), currency="PLN",
                           external_id=external_id, comment="", raw={})

    with Session(engine) as db:
        db.add_all([tx("i", "interest", "5.00"), tx("t", "interest_tax", "-0.95"), tx("f", "fee", "-2.00")])
        db.commit()

    body = _get(client, world["anna"], period="all")
    september = body["months"][-1]

    assert (september["interest_pln"], september["taxes_pln"], september["fees_pln"]) == ("5.00", "0.95", "2.00")
    xtb = next(s for s in body["sources"] if s["kind"] == "xtb_interest")
    assert (xtb["name"], xtb["net_pln"]) == ("Odsetki od wolnych środków · XTB IKE", "4.05")
    assert (body["costs"][1]["amount_pln"], body["costs"][3]["count"]) == ("0.95", 1)


def test_account_filter_on_a_savings_account(
    client: TestClient, world: dict, engine: Engine, monkeypatch: pytest.MonkeyPatch,
) -> None:
    savings_id = _savings(engine, world, monkeypatch)

    body = _get(client, world["anna"], period="all", account_id=savings_id)

    assert [s["kind"] for s in body["sources"]] == ["savings"]
    assert body["costs"][0]["amount_pln"] == "0.00"
    foreign = client.get(URL, params={"account_id": savings_id}, headers=world["bartek"])
    assert foreign.status_code == 404


def test_no_data_and_unknown_period(client: TestClient, world: dict) -> None:
    assert _get(client, world["bartek"]) == {
        "period": None, "totals": {"income_pln": "0.00", "costs_pln": "0.00", "balance_pln": "0.00"},
        "months": [], "sources": [], "costs": [], "recalculating": False}
    assert client.get(URL, params={"period": "5y"}, headers=world["anna"]).status_code == 422
