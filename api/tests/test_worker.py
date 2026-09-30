import datetime as dt
import logging
import threading
from collections.abc import Iterator
from contextlib import nullcontext
from zoneinfo import ZoneInfo

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.auth.maintenance import prune_refresh_tokens
from app.models import Cpi, Instrument, Price, RefreshToken, User
from app.worker import DailySchedule, IntradaySchedule, WorkerState, run_forever, schema_is_current, tick
from tests.market_fakes import FakeInflation, fake_providers
from tests.test_market_update import _reference

WARSAW = ZoneInfo("Europe/Warsaw")
SCHEDULE = DailySchedule(at=dt.time(23, 0), zone=WARSAW)
DAY = dt.date(2026, 9, 25)


def _at(hour: int, minute: int = 0, day: dt.date = DAY) -> dt.datetime:
    return dt.datetime.combine(day, dt.time(hour, minute), WARSAW).astimezone(dt.UTC)


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _token(db: Session, user: User, name: str, *, expires_days: int, revoked_days: int | None = None) -> None:
    now = _at(12)
    db.add(RefreshToken(
        user_id=user.id, token_hash=name.ljust(64, "0"),
        expires_at=now + dt.timedelta(days=expires_days),
        revoked_at=None if revoked_days is None else now + dt.timedelta(days=revoked_days),
    ))


@pytest.mark.parametrize(
    ("now", "last_completed", "due"),
    [
        (_at(10), None, True),
        (_at(22, 59), DAY - dt.timedelta(days=1), False),
        (_at(23, 0), DAY - dt.timedelta(days=1), True),
        (_at(23, 30), DAY, False),
        (_at(0, 30, DAY + dt.timedelta(days=1)), DAY, False),
    ],
    ids=["first-start", "before-evening", "evening", "already-done", "after-midnight"],
)
def test_daily_schedule_is_due(now: dt.datetime, last_completed: dt.date | None, due: bool) -> None:
    assert SCHEDULE.is_due(now, last_completed) is due


def test_run_during_the_day_does_not_count_as_the_evening_run() -> None:
    assert SCHEDULE.completed_through(_at(10)) == DAY - dt.timedelta(days=1)
    assert SCHEDULE.completed_through(_at(23, 5)) == DAY


def test_first_tick_runs_daily_job_then_only_backfills_until_evening(db: Session) -> None:
    user = User(email="anna@portfolio.dev", password_hash="x")
    instrument = Instrument(xtb_ticker="SXR8.DE", name="Core S&P 500")
    db.add_all([user, instrument])
    db.flush()
    _token(db, user, "stale", expires_days=-40)
    # The worker only touches instruments referenced by a transaction or position lot (Task 7
    # controller ruling) — `_reference` (from test_market_update.py) commits a PositionLot for it.
    _reference(db, instrument)
    providers = fake_providers()
    state = WorkerState()

    assert tick(db, providers, SCHEDULE, state, _at(10)) == "daily"
    assert state.last_completed == DAY - dt.timedelta(days=1)
    assert tick(db, providers, SCHEDULE, state, _at(10, 5)) == "backfill"
    assert tick(db, providers, SCHEDULE, state, _at(23, 0)) == "daily"
    assert state.last_completed == DAY
    assert db.scalar(select(func.count()).select_from(Price)) == 2
    assert db.scalar(select(func.count()).select_from(Cpi)) == 2
    assert db.scalar(select(func.count()).select_from(RefreshToken)) == 0


def test_prune_refresh_tokens_keeps_recent_ones(db: Session) -> None:
    user = User(email="anna@portfolio.dev", password_hash="x")
    db.add(user)
    db.flush()
    _token(db, user, "expired-long-ago", expires_days=-31)
    _token(db, user, "expired-recently", expires_days=-29)
    _token(db, user, "revoked-long-ago", expires_days=5, revoked_days=-31)
    _token(db, user, "revoked-recently", expires_days=5, revoked_days=-1)
    _token(db, user, "active", expires_days=30)
    db.commit()

    assert prune_refresh_tokens(db, _at(12)) == 2
    db.commit()

    remaining = db.scalars(select(RefreshToken.token_hash)).all()
    assert sorted(name.rstrip("0") for name in remaining) == ["active", "expired-recently", "revoked-recently"]


def test_run_forever_survives_a_failing_iteration(caplog: pytest.LogCaptureFixture) -> None:
    stop = threading.Event()
    calls: list[dt.datetime] = []

    def tick_fn(_: object, now: dt.datetime) -> str:
        calls.append(now)
        if len(calls) == 1:
            raise RuntimeError("boom")
        stop.set()
        return "backfill"

    with caplog.at_level(logging.ERROR, logger="app.worker"):
        run_forever(lambda: nullcontext(object()), tick_fn, 0, stop, clock=lambda: _at(12))

    assert len(calls) == 2
    assert "Worker iteration failed" in caplog.text


def test_schema_is_current_on_migrated_database(engine: Engine) -> None:
    assert schema_is_current(engine) is True


INTRADAY = IntradaySchedule(start=dt.time(9, 0), end=dt.time(22, 30), every=dt.timedelta(minutes=30), zone=WARSAW)
SATURDAY = DAY + dt.timedelta(days=1)


@pytest.mark.parametrize(
    ("now", "last", "due"),
    [
        (_at(10), None, True),
        (_at(10, 20), _at(10), False),
        (_at(10, 31), _at(10), True),
        (_at(12, 0, SATURDAY), None, False),
        (_at(22, 45), None, False),
        (_at(8, 50), None, False),
    ],
    ids=["weekday", "too-soon", "half-hour-later", "saturday", "after-22-30", "before-9"],
)
def test_intraday_schedule_is_due(now: dt.datetime, last: dt.datetime | None, due: bool) -> None:
    assert INTRADAY.is_due(now, last) is due


class CountingInflation(FakeInflation):
    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    def cpi(self):  # noqa: ANN201 — the fake's own return type
        self.calls += 1
        return super().cpi()


def test_prices_and_rates_refresh_every_half_hour_during_the_day(db: Session) -> None:
    instrument = Instrument(xtb_ticker="SXR8.DE", name="Core S&P 500")
    db.add(instrument)
    db.flush()
    _reference(db, instrument)
    inflation = CountingInflation()
    providers = fake_providers(inflation=inflation)
    state = WorkerState()

    assert tick(db, providers, SCHEDULE, state, _at(10), INTRADAY) == "daily"  # the evening run caught up on start
    assert state.last_intraday == _at(10)
    assert tick(db, providers, SCHEDULE, state, _at(10, 5), INTRADAY) == "backfill"
    fetches = len(providers.prices.calls)
    assert tick(db, providers, SCHEDULE, state, _at(10, 31), INTRADAY) == "intraday"
    assert len(providers.prices.calls) == fetches + 1
    assert inflation.calls == 1  # inflation only in the evening run
    assert tick(db, providers, SCHEDULE, state, _at(23, 0), INTRADAY) == "daily"
