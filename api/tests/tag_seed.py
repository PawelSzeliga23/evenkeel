"""Anna's valued portfolio for the tag tests (plan 7f-1): XTB IKE with SXR8.DE and 10 × EDO0336, a savings account,
a second (empty) broker account, and an account of bartek's."""
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, BondHolding, BondSeries, SavingsAccount, User
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]


def tag_world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        bartek_id = db.scalar(select(User.id).where(User.email == "bartek@portfolio.dev"))
        sxr8 = seed_market(db)
        ike = seed_holdings(db, user_id, sxr8)
        savings = Account(user_id=user_id, name="Konto oszczędnościowe", kind="savings", wrapper="regular",
                          currency="PLN")
        plain = Account(user_id=user_id, name="Zwykłe", kind="broker", wrapper="regular", currency="PLN")
        foreign = Account(user_id=bartek_id, name="Bartka", kind="broker", wrapper="regular", currency="PLN")
        db.add_all([savings, plain, foreign])
        db.flush()
        db.add(SavingsAccount(account_id=savings.id, capitalization="monthly"))
        if db.get(BondSeries, "EDO0336") is None:
            db.add(BondSeries(series="EDO0336", bond_type="EDO", issue_month=dt.date(2026, 3, 1), maturity_months=120,
                              first_period_rate=Decimal("5.6"), margin=Decimal("1.5"),
                              early_redemption_fee=Decimal("2"), interest_mode="capitalized", rate_basis="cpi"))
            db.flush()
        bond = BondHolding(account_id=ike, bond_type="EDO", series="EDO0336", quantity=10,
                           purchase_date=dt.date(2026, 3, 10))
        db.add(bond)
        db.commit()
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "user_id": user_id, "ike": ike, "savings": savings.id, "plain": plain.id,
            "foreign": foreign.id, "sxr8": sxr8, "bond": bond.id}


def add_tag(client: TestClient, headers: dict, name: str, **body: object) -> dict:
    response = client.post("/api/tags", json={"name": name, **body}, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def add_link(client: TestClient, world: dict, tag: dict, **body: object) -> dict:
    response = client.post(f"/api/tags/{tag['id']}/links", json=body, headers=world["anna"])
    assert response.status_code in (200, 201), response.text
    return response.json()
