import datetime as dt
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import (
    Account, BondHolding, BondSeries, Cpi, DailyValuation, SavingsAccount, SavingsBalance, SavingsRate, User,
)
from app.valuation.service import mark_new_days, recompute_user
from tests.valuation_seed import SAT, seed_user, valuate

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _series(db: Session, name: str = "EDO0936", issue: dt.date = dt.date(2026, 9, 1)) -> None:
    db.add(BondSeries(series=name, bond_type="EDO", issue_month=issue, maturity_months=120,
                      first_period_rate=Decimal("5.35"), margin=Decimal("2.00"), early_redemption_fee=Decimal("3.00"),
                      interest_mode="capitalized", rate_basis="cpi"))
    db.commit()


def _account(db: Session, user_id: int, kind: str, wrapper: str = "regular") -> int:
    account = Account(user_id=user_id, name=f"{kind} {wrapper}", kind=kind, wrapper=wrapper, currency="PLN")
    db.add(account)
    db.commit()
    return account.id


def _bonds(db: Session, account_id: int, bought: dt.date = dt.date(2026, 9, 15), series: str = "EDO0936") -> int:
    holding = BondHolding(account_id=account_id, bond_type="EDO", series=series, quantity=10, purchase_date=bought)
    db.add(holding)
    db.commit()
    return holding.id


def _savings(db: Session, account_id: int) -> int:
    savings = SavingsAccount(account_id=account_id, capitalization="monthly")
    db.add(savings)
    db.flush()
    db.add_all([SavingsRate(savings_account_id=savings.id, valid_from=dt.date(2026, 9, 1), annual_rate=Decimal("5")),
                SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 9, 1), balance=Decimal("10000"))])
    db.commit()
    return savings.id


def _row(db: Session, user_id: int, day: dt.date, **component: int) -> DailyValuation:
    return db.scalar(select(DailyValuation).filter_by(user_id=user_id, date=day, **component))


def test_bonds_and_savings_alone_get_daily_rows(db: Session) -> None:
    _series(db)
    user_id = seed_user(db)
    holding_id = _bonds(db, _account(db, user_id, "bonds"))
    savings_id = _savings(db, _account(db, user_id, "savings"))

    valuate(db, user_id)

    bond = _row(db, user_id, SAT, bond_holding_id=holding_id)
    savings = _row(db, user_id, dt.date(2026, 9, 30), savings_account_id=savings_id)
    assert (bond.value_pln, bond.cost_pln, bond.instrument_id) == (Decimal("1001.3000"), Decimal("1000.0000"), None)
    assert savings is None  # valued up to Saturday 2026-09-26 only
    savings = _row(db, user_id, SAT, savings_account_id=savings_id)
    assert (savings.value_pln, savings.net_flow_pln) == (Decimal("10000.0000"), Decimal("0.0000"))
    assert _row(db, user_id, dt.date(2026, 9, 15), bond_holding_id=holding_id).net_flow_pln == Decimal("1000.0000")


def test_new_days_mark_holders_of_bonds_and_savings_and_reopen_estimated_periods(db: Session) -> None:
    _series(db)
    _series(db, "EDO0935", dt.date(2025, 9, 1))
    bonds_only, savings_only = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    _bonds(db, _account(db, bonds_only, "bonds"), dt.date(2025, 9, 15), "EDO0935")  # 2nd period from 2026-09-15
    _savings(db, _account(db, savings_only, "savings"))
    valuate(db, bonds_only)
    valuate(db, savings_only)

    mark_new_days(db, SAT)
    db.commit()

    stale = dict(db.execute(select(User.id, User.valuations_stale_from)).all())
    # no CPI for July 2026 yet: the bond rows from 2026-09-15 are estimated and stay open
    assert (stale[bonds_only], stale[savings_only]) == (dt.date(2026, 9, 15), SAT)


def test_cpi_arrival_replaces_the_estimated_rate(db: Session) -> None:
    _series(db, "EDO0935", dt.date(2025, 9, 1))
    user_id = seed_user(db)
    holding_id = _bonds(db, _account(db, user_id, "bonds"), dt.date(2025, 9, 15), "EDO0935")
    valuate(db, user_id)
    assert _row(db, user_id, SAT, bond_holding_id=holding_id).flags == ["rate_estimated"]

    db.add(Cpi(year_month=dt.date(2026, 7, 1), yoy=Decimal("2.5")))
    db.commit()
    mark_new_days(db, SAT)
    db.commit()
    recompute_user(db, user_id, SAT)

    assert _row(db, user_id, SAT, bond_holding_id=holding_id).flags == []


def test_dashboard_shows_bonds_and_savings_as_their_own_kinds(
    client: TestClient, login_as: LoginAs, engine: Engine
) -> None:
    headers = login_as("anna@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        _series(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        _bonds(db, _account(db, user_id, "bonds"))
        _savings(db, _account(db, user_id, "savings"))
        valuate(db, user_id)

    body = client.get("/api/portfolio/summary", headers=headers).json()

    assert (body["value_pln"], body["cash_pln"], body["invested_pln"]) == ("11001.30", "0.00", "11000.00")
    assert [(item["key"], item["name"], item["value_pln"]) for item in body["by_kind"]] == [
        ("savings", "Konta oszczędnościowe", "10000.00"), ("bonds", "Obligacje", "1001.30")]


def test_switching_an_account_to_ike_revalues_its_history_without_tax(
    client: TestClient, login_as: LoginAs, engine: Engine
) -> None:
    headers = login_as("anna@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        _series(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = _account(db, user_id, "bonds")
        holding_id = _bonds(db, account_id)
        valuate(db, user_id)

    response = client.patch(f"/api/accounts/{account_id}", json={"wrapper": "ike"}, headers=headers)

    assert response.status_code == 200
    with Session(engine) as db:
        rows = db.scalars(select(DailyValuation).filter_by(bond_holding_id=holding_id, date=SAT)).all()
        assert [row.value_pln for row in rows] == [Decimal("1001.6000")]
