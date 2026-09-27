import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, CorporateAction, DailyValuation, Instrument, User

DAY = dt.date(2026, 9, 25)


def _world(session: Session) -> tuple[User, Account, Instrument]:
    user = User(email="anna@portfolio.dev", password_hash="x")
    instrument = Instrument(xtb_ticker="SXR8.DE", name="Core S&P 500")
    session.add_all([user, instrument])
    session.flush()
    account = Account(user_id=user.id, name="XTB IKE", kind="broker", wrapper="ike", broker="xtb",
                      external_account_number="56216965", currency="PLN")
    session.add(account)
    session.flush()
    return user, account, instrument


def _row(user: User, account: Account, instrument_id: int | None) -> DailyValuation:
    return DailyValuation(user_id=user.id, account_id=account.id, instrument_id=instrument_id, date=DAY,
                          quantity=Decimal("1"), value_pln=Decimal("10"), cost_pln=Decimal("10"),
                          net_flow_pln=Decimal("0"))


def test_cash_row_is_unique_per_account_and_day(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, account, _ = _world(session)
        session.add(_row(user, account, None))
        session.flush()
        session.add(_row(user, account, None))
        with pytest.raises(IntegrityError):
            session.flush()


def test_instrument_row_is_unique_per_account_instrument_and_day(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, account, instrument = _world(session)
        session.add_all([_row(user, account, instrument.id), _row(user, account, None)])
        session.flush()
        session.add(_row(user, account, instrument.id))
        with pytest.raises(IntegrityError):
            session.flush()


def test_flags_default_to_empty_list_and_rows_go_with_the_account(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, account, instrument = _world(session)
        row = _row(user, account, instrument.id)
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.flags == []
        session.delete(account)
        session.commit()
        assert session.scalar(select(func.count()).select_from(DailyValuation)) == 0


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"type": "merger"}, "type"),
        ({"source": "yahoo"}, "source"),
        ({"ratio_from": Decimal("0")}, "ratio"),
    ],
)
def test_corporate_action_is_constrained(engine: Engine, clean_db: None, fields: dict, reason: str) -> None:
    with Session(engine) as session:
        _, _, instrument = _world(session)
        values = {"type": "split", "effective_date": DAY, "ratio_from": Decimal("1"), "ratio_to": Decimal("10"),
                  "source": "provider", **fields}
        session.add(CorporateAction(instrument_id=instrument.id, **values))
        with pytest.raises(IntegrityError):
            session.flush()


def test_new_instrument_counts_as_split_synced_and_user_is_not_stale(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, _, instrument = _world(session)
        session.commit()
        session.refresh(instrument)
        session.refresh(user)
        assert instrument.splits_synced is True
        assert user.valuations_stale_from is None
