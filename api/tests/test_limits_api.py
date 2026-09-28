import datetime as dt
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, Transaction, User, WrapperLimit
from app.portfolio.limits import wrapper_limits
from app.scoping import UserScope
from tests.valuation_seed import seed_holdings, seed_market, seed_user

LoginAs = Callable[[str], dict[str, str]]
TODAY = dt.date(2026, 9, 26)


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _account(db: Session, user_id: int, name: str, wrapper: str, number: str) -> int:
    account = Account(user_id=user_id, name=name, kind="broker", wrapper=wrapper, broker="xtb",
                      external_account_number=number, currency="PLN")
    db.add(account)
    db.commit()
    return account.id


def _cash(db: Session, account_id: int, external_id: str, type_: str, amount: str, at: dt.datetime) -> None:
    db.add(Transaction(account_id=account_id, type=type_, xtb_type=type_, occurred_at=at, amount=Decimal(amount),
                       currency="PLN", external_id=external_id, comment="", raw={}))
    db.commit()


def test_contributions_to_all_ike_accounts_count_against_one_yearly_limit(db: Session) -> None:
    db.add(WrapperLimit(year=2026, wrapper="ike", limit_pln=Decimal("28260")))
    user_id = seed_user(db)
    first = seed_holdings(db, user_id, seed_market(db))  # "XTB IKE": deposit 10 000 zł on 2026-03-01
    second = _account(db, user_id, "XTB IKE 2", "ike", "22222222")
    _cash(db, second, "1", "transfer_in", "20000", dt.datetime(2026, 5, 1, 10, 0, tzinfo=dt.UTC))
    _cash(db, second, "2", "withdrawal", "-1000", dt.datetime(2026, 6, 1, 10, 0, tzinfo=dt.UTC))
    _cash(db, first, "9", "deposit", "5000", dt.datetime(2025, 12, 1, 10, 0, tzinfo=dt.UTC))
    _account(db, user_id, "XTB", "regular", "33333333")

    limits = wrapper_limits(UserScope(db, db.get(User, user_id)), TODAY)

    assert [item.model_dump(mode="json") for item in limits] == [
        {"wrapper": "ike", "year": 2026, "paid_pln": "30000.00", "limit_pln": "28260.00", "remaining_pln": "0.00",
         "exceeded": True, "accounts": [{"account_id": first, "name": "XTB IKE", "paid_pln": "10000.00"},
                                        {"account_id": second, "name": "XTB IKE 2", "paid_pln": "20000.00"}]},
        {"wrapper": "ike", "year": 2025, "paid_pln": "5000.00", "limit_pln": None, "remaining_pln": None,
         "exceeded": False, "accounts": [{"account_id": first, "name": "XTB IKE", "paid_pln": "5000.00"},
                                         {"account_id": second, "name": "XTB IKE 2", "paid_pln": "0.00"}]},
    ]


def test_ike_without_contributions_shows_the_current_year(db: Session) -> None:
    db.add(WrapperLimit(year=2026, wrapper="ike", limit_pln=Decimal("28260")))
    user_id = seed_user(db)
    _account(db, user_id, "XTB IKE", "ike", "11111111")

    (item,) = wrapper_limits(UserScope(db, db.get(User, user_id)), TODAY)

    assert (item.year, item.paid_pln, item.remaining_pln, item.exceeded) == (
        2026, Decimal("0.00"), Decimal("28260.00"), False)


def test_limits_api_lists_only_the_users_own_wrappers(client: TestClient, login_as: LoginAs, engine: Engine) -> None:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        seed_holdings(db, db.scalar(select(User.id).where(User.email == "anna@portfolio.dev")), seed_market(db))

    own = client.get("/api/portfolio/limits", headers=anna).json()
    other = client.get("/api/portfolio/limits", headers=bartek).json()

    assert [(item["wrapper"], item["year"], item["paid_pln"]) for item in own if item["year"] == 2026] == [
        ("ike", 2026, "10000.00")]
    assert other == []
