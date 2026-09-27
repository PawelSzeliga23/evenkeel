"""Background worker: daily market data update, backfill of new instruments, housekeeping.

A plain loop instead of APScheduler: two jobs in one process, idempotent work, and the daily job
must also run once at start-up to catch up after downtime. ~40 lines cover it without a dependency.
"""
import datetime as dt
import logging
import signal
import threading
from collections.abc import Callable
from contextlib import AbstractContextManager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal
from zoneinfo import ZoneInfo

import httpx
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory
from sqlalchemy import Engine
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session

from app.auth.maintenance import prune_refresh_tokens
from app.config import get_settings
from app.db import get_engine, get_sessionmaker
from app.market.http import make_client
from app.market.providers.gus import GusInflationProvider
from app.market.providers.nbp import NbpFxProvider, NbpRefRateProvider
from app.market.providers.yahoo import YahooPriceProvider
from app.market.update import MarketProviders, backfill_new_instruments, run_market_update

logger = logging.getLogger("app.worker")
ALEMBIC_INI = Path(__file__).resolve().parents[1] / "alembic.ini"

TickFn = Callable[[Any, dt.datetime], str]


@dataclass(frozen=True)
class DailySchedule:
    at: dt.time
    zone: ZoneInfo

    def completed_through(self, now: dt.datetime) -> dt.date:
        """The last local day whose evening run is covered by a run started at `now`."""
        local = now.astimezone(self.zone)
        return local.date() if local.time() >= self.at else local.date() - dt.timedelta(days=1)

    def is_due(self, now: dt.datetime, last_completed: dt.date | None) -> bool:
        return last_completed is None or self.completed_through(now) > last_completed


@dataclass
class WorkerState:
    last_completed: dt.date | None = None


def tick(
    db: Session, providers: MarketProviders, schedule: DailySchedule, state: WorkerState, now: dt.datetime
) -> Literal["daily", "backfill"]:
    if schedule.is_due(now, state.last_completed):
        today = now.astimezone(schedule.zone).date()
        summary = run_market_update(db, providers, now, today)
        pruned = prune_refresh_tokens(db, now)
        db.commit()
        state.last_completed = schedule.completed_through(now)
        logger.info("Daily market update done: %s; pruned %d refresh tokens", summary, pruned)
        return "daily"
    rows, failed = backfill_new_instruments(db, providers.prices, now)
    if rows or failed:
        logger.info("Backfilled new instruments: %d price rows, failed: %s", rows, failed)
    return "backfill"


def run_forever(
    session_factory: Callable[[], AbstractContextManager[Any]],
    tick_fn: TickFn,
    poll_seconds: float,
    stop: threading.Event,
    clock: Callable[[], dt.datetime] = lambda: dt.datetime.now(dt.UTC),
) -> None:
    while not stop.is_set():
        try:
            with session_factory() as db:
                tick_fn(db, clock())
        except Exception:
            logger.exception("Worker iteration failed; retrying after the poll interval")
        stop.wait(poll_seconds)


def schema_is_current(engine: Engine) -> bool:
    heads = set(ScriptDirectory.from_config(Config(str(ALEMBIC_INI))).get_heads())
    with engine.connect() as conn:
        return set(MigrationContext.configure(conn).get_current_heads()) == heads


def wait_for_schema(engine: Engine, stop: threading.Event, poll_seconds: float = 5.0) -> bool:
    """Migrations are run by the api service; the worker waits for them instead of racing it."""
    while not stop.is_set():
        try:
            if schema_is_current(engine):
                return True
            logger.info("Waiting for database migrations to reach head")
        except OperationalError:
            logger.info("Waiting for the database")
        stop.wait(poll_seconds)
    return False


def build_providers(client: httpx.Client) -> MarketProviders:
    return MarketProviders(
        prices=YahooPriceProvider(client),
        fx=NbpFxProvider(client),
        inflation=GusInflationProvider(client),
        ref_rates=NbpRefRateProvider(client),
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    settings = get_settings()
    stop = threading.Event()
    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, lambda *_: stop.set())
    if not wait_for_schema(get_engine(), stop):
        return
    schedule = DailySchedule(dt.time.fromisoformat(settings.market_daily_at), ZoneInfo(settings.market_timezone))
    state = WorkerState()
    logger.info("Worker started: daily update at %s %s", settings.market_daily_at, settings.market_timezone)
    with make_client() as client:
        providers = build_providers(client)
        run_forever(
            get_sessionmaker(),
            lambda db, now: tick(db, providers, schedule, state, now),
            settings.worker_poll_seconds,
            stop,
        )
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
