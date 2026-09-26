import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, Base, User


def test_models_match_migrations(engine: Engine) -> None:
    with engine.connect() as conn:
        context = MigrationContext.configure(conn, opts={"compare_type": True})
        assert compare_metadata(context, Base.metadata) == []


def _user(session: Session, email: str = "anna@portfolio.dev") -> User:
    user = User(email=email, password_hash="x")
    session.add(user)
    session.flush()
    return user


def test_account_kind_is_constrained_in_database(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user = _user(session)
        session.add(Account(user_id=user.id, name="Krypto", kind="crypto", wrapper="regular", currency="PLN"))
        with pytest.raises(IntegrityError):
            session.flush()


def test_broker_account_number_is_unique_per_user(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user = _user(session)
        for _ in range(2):
            session.add(
                Account(
                    user_id=user.id, name="XTB", kind="broker", wrapper="regular",
                    broker="xtb", external_account_number="56204082", currency="PLN",
                )
            )
        with pytest.raises(IntegrityError):
            session.flush()


def test_user_defaults_are_set_by_database(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user = _user(session)
        session.commit()
        session.refresh(user)
        assert user.base_currency == "PLN"
        assert user.created_at is not None
