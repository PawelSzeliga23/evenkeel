from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, Instrument, Transaction, User


def _account(session: Session) -> Account:
    user = User(email="anna@portfolio.dev", password_hash="x")
    session.add(user)
    session.flush()
    account = Account(user_id=user.id, name="XTB IKE", kind="broker", wrapper="ike",
                      broker="xtb", external_account_number="56216965", currency="PLN")
    session.add(account)
    session.flush()
    return account


def _transaction(account: Account, external_id: str = "1001", type_: str = "deposit") -> Transaction:
    return Transaction(account_id=account.id, type=type_, xtb_type="Deposit",
                       occurred_at=datetime(2026, 3, 2, 9, 30, tzinfo=UTC), amount=Decimal("500.10"),
                       currency="PLN", external_id=external_id, comment="", raw={})


def test_transaction_external_id_is_unique_per_account(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add_all([_transaction(account), _transaction(account)])
        with pytest.raises(IntegrityError):
            session.flush()


def test_transaction_type_is_constrained(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_transaction(account, type_="bogus"))
        with pytest.raises(IntegrityError):
            session.flush()


def test_money_is_stored_exactly(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_transaction(account))
        session.commit()
        assert session.scalar(select(Transaction.amount)) == Decimal("500.10")


def test_deleting_account_deletes_its_transactions(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_transaction(account))
        session.commit()
        session.delete(account)
        session.commit()
        assert session.scalar(select(func.count()).select_from(Transaction)) == 0


def test_transaction_exposes_instrument_ticker(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        instrument = Instrument(xtb_ticker="SXR8.DE", name="Core S&P 500")
        session.add(instrument)
        session.flush()
        transaction = _transaction(account, type_="buy")
        transaction.instrument_id = instrument.id
        session.add(transaction)
        session.commit()
        session.expire_all()
        assert session.scalar(select(Transaction)).ticker == "SXR8.DE"
