import datetime as dt
from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.imports.service import apply_import, plan_import
from app.models import DailyValuation, Instrument, User
from app.scoping import UserScope
from app.valuation.engine import FLAG_XTB_PRICE
from app.worker import WorkerState, tick
from app.xtb.report import parse_report
from tests import xtb_factory as xf
from tests.market_fakes import fake_providers
from tests.test_worker import SCHEDULE, _at
from tests.valuation_seed import FRI, seed_holdings, seed_market, seed_user

LoginAs = Callable[[str], dict[str, str]]
IKE = "56216965"
AT = datetime(2026, 3, 2, 9, 30)


def _ike() -> bytes:
    return xf.build_report(
        account_number=IKE,
        cash=[
            xf.cash_row("IKE deposit", 5000.0, "1001", datetime(2026, 3, 1, 8, 0),
                        comment="Transfer in operation on account with id 56204082"),
            xf.buy_row("SXR8.DE", "2", "500.5", -4304.3, "1002", AT, "777"),
        ],
        open_rows=[
            xf.summary_row("SXR8.DE", "Core S&P 500", 2.0, 1020.0, 500.5, 19.0),
            xf.lot_row("SXR8.DE", "777", 2.0, 500.5, AT, 510.0, 1020.0, 19.0),
        ],
    )


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _stale(db: Session, user_id: int) -> dt.date | None:
    return db.scalar(select(User.valuations_stale_from).where(User.id == user_id))


def _import(db: Session, user_id: int) -> None:
    scope = UserScope(db, db.get(User, user_id))
    apply_import(scope, plan_import(scope, [parse_report(xf.filename("IKE", IKE), _ike())]))


def test_import_marks_the_user_from_its_earliest_operation(db: Session) -> None:
    user_id = seed_user(db)
    _import(db, user_id)
    assert _stale(db, user_id) == dt.date(2026, 3, 1)


def test_reimport_of_known_operations_marks_only_the_snapshot_day(db: Session) -> None:
    user_id = seed_user(db)
    _import(db, user_id)
    db.execute(update(User).values(valuations_stale_from=None))
    db.commit()

    _import(db, user_id)

    assert _stale(db, user_id) == dt.date(2026, 9, 26)


def test_committed_import_is_valued_in_the_background(client: TestClient, login_as: LoginAs, engine: Engine) -> None:
    anna = login_as("anna@portfolio.dev")

    response = client.post(
        "/api/imports", files=[("files", (xf.filename("IKE", IKE), _ike(), "application/octet-stream"))], headers=anna
    )

    assert response.status_code == 201, response.json()
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        assert _stale(db, user_id) is None
        rows = {
            (row.date, row.instrument_id is None): row
            for row in db.scalars(select(DailyValuation).where(DailyValuation.user_id == user_id))
        }
    bought = rows[(dt.date(2026, 3, 2), False)]
    assert (bought.value_pln, bought.cost_pln, bought.flags) == (Decimal("4304.30"), Decimal("4304.30"), [FLAG_XTB_PRICE])
    assert rows[(dt.date(2026, 9, 26), False)].value_pln == Decimal("1020.00")
    assert rows[(dt.date(2026, 3, 1), True)].net_flow_pln == Decimal("5000.00")


def test_price_symbol_change_marks_holders_for_a_full_recompute(
    client: TestClient, login_as: LoginAs, engine: Engine
) -> None:
    anna, _ = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        anna_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        bartek_id = db.scalar(select(User.id).where(User.email == "bartek@portfolio.dev"))
        seed_holdings(db, anna_id, instrument_id)

    response = client.patch(f"/api/instruments/{instrument_id}", json={"price_symbol": "CSPX.L"}, headers=anna)

    assert response.status_code == 200, response.json()
    with Session(engine) as db:
        assert (_stale(db, anna_id), _stale(db, bartek_id)) == (dt.date.min, None)


def test_daily_tick_revalues_holders_with_the_new_prices(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))

    assert tick(db, fake_providers(), SCHEDULE, WorkerState(), _at(10)) == "daily"

    assert _stale(db, user_id) is None
    position = db.scalar(select(DailyValuation).where(
        DailyValuation.user_id == user_id, DailyValuation.date == FRI, DailyValuation.instrument_id.is_not(None)))
    assert position.value_pln == Decimal("6067.30")  # 2 × 713.80 EUR (fake provider) × 4.25


def test_backfill_tick_finishes_pending_recomputes(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))
    db.execute(update(User).values(valuations_stale_from=dt.date.min))
    db.execute(update(Instrument).values(price_checked_at=datetime(2026, 9, 25, 7, 0, tzinfo=dt.UTC)))
    db.commit()
    state = WorkerState(last_completed=FRI)

    assert tick(db, fake_providers(), SCHEDULE, state, _at(10, 5)) == "backfill"

    assert _stale(db, user_id) is None
    assert db.scalar(select(DailyValuation.date).where(DailyValuation.user_id == user_id)
                     .order_by(DailyValuation.date.desc()).limit(1)) == FRI
