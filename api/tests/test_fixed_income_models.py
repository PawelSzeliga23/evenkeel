import datetime as dt
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Account, BondHolding, BondSeries, DailyValuation, Instrument, SavingsAccount, SavingsBalance, SavingsRate, User,
)
from tests.conftest import API_DIR, TEST_DATABASE_URL

DAY = dt.date(2026, 9, 25)


def _series(**fields: object) -> BondSeries:
    values = {"series": "EDO0936", "bond_type": "EDO", "issue_month": dt.date(2026, 9, 1), "maturity_months": 120,
              "first_period_rate": Decimal("5.35"), "margin": Decimal("2.00"), "early_redemption_fee": Decimal("3.00"),
              "interest_mode": "capitalized", "rate_basis": "cpi", **fields}
    return BondSeries(**values)


def _account(session: Session, kind: str = "bonds") -> Account:
    user = User(email=f"{kind}@portfolio.dev", password_hash="x")
    session.add(user)
    session.flush()
    account = Account(user_id=user.id, name=kind, kind=kind, wrapper="regular", currency="PLN")
    session.add(account)
    session.flush()
    return account


def _holding(account: Account, **fields: object) -> BondHolding:
    values = {"account_id": account.id, "bond_type": "EDO", "series": "EDO0936", "quantity": 10,
              "purchase_date": dt.date(2026, 9, 15), **fields}
    return BondHolding(**values)


def test_holding_references_its_series_and_defaults(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_series())
        session.flush()
        holding = _holding(account)
        session.add(holding)
        session.commit()
        session.refresh(holding)
        assert (holding.note, holding.redeemed_at) == ("", None)


@pytest.mark.parametrize(
    "fields",
    [
        {"quantity": 0},
        {"redeemed_at": dt.date(2026, 9, 14)},  # before the purchase
        {"series": "EDO1036"},  # not in bond_series
        {"bond_type": "XYZ"},
    ],
)
def test_holding_is_constrained(engine: Engine, clean_db: None, fields: dict) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_series())
        session.flush()
        session.add(_holding(account, **fields))
        with pytest.raises(IntegrityError):
            session.flush()


@pytest.mark.parametrize("fields", [{"interest_mode": "weekly"}, {"rate_basis": "wibor"}, {"bond_type": "ABC"}])
def test_series_is_constrained(engine: Engine, clean_db: None, fields: dict) -> None:
    with Session(engine) as session:
        session.add(_series(**fields))
        with pytest.raises(IntegrityError):
            session.flush()


def test_savings_rates_and_balances_are_unique_per_day(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        savings = SavingsAccount(account_id=_account(session, "savings").id, capitalization="monthly")
        session.add(savings)
        session.flush()
        session.add(SavingsRate(savings_account_id=savings.id, valid_from=DAY, annual_rate=Decimal("5.00")))
        session.add(SavingsBalance(savings_account_id=savings.id, as_of_date=DAY, balance=Decimal("100")))
        session.flush()
        session.add(SavingsBalance(savings_account_id=savings.id, as_of_date=DAY, balance=Decimal("200")))
        with pytest.raises(IntegrityError):
            session.flush()


@pytest.mark.parametrize(
    ("model", "fields"),
    [
        (SavingsAccount, {"capitalization": "yearly"}),
        (SavingsRate, {"valid_from": DAY, "annual_rate": Decimal("-1")}),
        (SavingsBalance, {"as_of_date": DAY, "balance": Decimal("-1")}),
    ],
)
def test_savings_values_are_constrained(engine: Engine, clean_db: None, model: type, fields: dict) -> None:
    with Session(engine) as session:
        account = _account(session, "savings")
        if model is SavingsAccount:
            session.add(SavingsAccount(account_id=account.id, **fields))
        else:
            savings = SavingsAccount(account_id=account.id, capitalization="monthly")
            session.add(savings)
            session.flush()
            session.add(model(savings_account_id=savings.id, **fields))
        with pytest.raises(IntegrityError):
            session.flush()


def _row(account: Account, **component: object) -> DailyValuation:
    return DailyValuation(user_id=account.user_id, account_id=account.id, date=DAY, quantity=Decimal("1"),
                          value_pln=Decimal("100"), cost_pln=Decimal("100"), net_flow_pln=Decimal("0"), **component)


def test_valuation_rows_are_unique_per_component_and_have_one_component(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_series())
        session.flush()
        first, second = _holding(account), _holding(account, quantity=5)
        session.add_all([first, second])
        session.flush()
        session.add_all([_row(account), _row(account, bond_holding_id=first.id), _row(account, bond_holding_id=second.id)])
        session.flush()  # the cash row and two holdings of one account on one day
        session.add(_row(account, bond_holding_id=first.id))
        with pytest.raises(IntegrityError):
            session.flush()
    with Session(engine) as session:
        account = _account(session)
        session.add(_series())
        instrument = Instrument(xtb_ticker="SXR8.DE", name="SXR8")
        session.add(instrument)
        session.flush()
        holding = _holding(account)
        session.add(holding)
        session.flush()
        session.add(_row(account, instrument_id=instrument.id, bond_holding_id=holding.id))
        with pytest.raises(IntegrityError):
            session.flush()


def test_migration_seeds_edo0936(engine: Engine, clean_db: None) -> None:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.downgrade(config, "0005")  # also exercises the downgrade of 0006
    command.upgrade(config, "head")
    with Session(engine) as session:
        series = session.get(BondSeries, "EDO0936")
        assert series is not None
        assert (series.first_period_rate, series.margin, series.early_redemption_fee, series.issue_month) == (
            Decimal("5.3500"), Decimal("2.0000"), Decimal("3.00"), dt.date(2026, 9, 1))
