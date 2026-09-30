"""Background worker: daily market data update, a refresh of prices and NBP rates every half hour of the trading day, backfill of new instruments, valuation recompute, housekeeping.

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
from app.market.update import (
    MarketProviders, backfill_new_instruments, run_market_update, update_all_prices, update_fx,
)
from app.valuation.service import mark_market_changes, mark_new_days, recompute_stale

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


@dataclass(frozen=True)
class IntradaySchedule:
    """Prices and NBP rates during the trading day: weekdays between `start` and `end` local time, every `every`."""
    start: dt.time
    end: dt.time
    every: dt.timedelta
    zone: ZoneInfo

    def is_due(self, now: dt.datetime, last: dt.datetime | None) -> bool:
        local = now.astimezone(self.zone)
        in_session = local.weekday() < 5 and self.start <= local.time() <= self.end
        return in_session and (last is None or now - last >= self.every)


@dataclass
class WorkerState:
    last_completed: dt.date | None = None
    last_intraday: dt.datetime | None = None  # the evening run counts too: prices are fresh after it


def tick(
    db: Session, providers: MarketProviders, schedule: DailySchedule, state: WorkerState, now: dt.datetime,
    intraday: IntradaySchedule | None = None,
) -> Literal["daily", "intraday", "backfill"]:
    today = now.astimezone(schedule.zone).date()
    result: Literal["daily", "intraday", "backfill"]
    if schedule.is_due(now, state.last_completed):
        summary = run_market_update(db, providers, now, today)
        mark_market_changes(db, summary.prices_changed_from, summary.fx_changed_from)
        # Advisory locks of one transaction must be taken in a single ascending-id pass, so the
        # market-change locks are committed before mark_new_days takes its own ascending-id pass below.
        db.commit()
        mark_new_days(db, today)  # every portfolio gets the new day and any day missed while the worker was down
        pruned = prune_refresh_tokens(db, now)
        db.commit()
        state.last_completed = schedule.completed_through(now)
        state.last_intraday = now
        logger.info("Daily market update done: %s; pruned %d refresh tokens", summary, pruned)
        result = "daily"
    elif intraday is not None and intraday.is_due(now, state.last_intraday):
        prices_from: dict[int, dt.date] = {}
        fx_from: dict[str, dt.date] = {}
        rows, failed = update_all_prices(db, providers.prices, now, prices_from)
        fx_rows, failed_fx = update_fx(db, providers.fx, today, fx_from)
        mark_market_changes(db, prices_from, fx_from)
        db.commit()
        state.last_intraday = now
        logger.info("Intraday refresh: %d price rows (failed: %s), %d FX rows (failed: %s)",
                    rows, failed, fx_rows, failed_fx)
        result = "intraday"
    else:
        changed: dict[int, dt.date] = {}
        rows, failed = backfill_new_instruments(db, providers.prices, now, changed)
        mark_market_changes(db, changed, {})
        db.commit()
        if rows or failed:
            logger.info("Backfilled new instruments: %d price rows, failed: %s", rows, failed)
        result = "backfill"
    recomputed = recompute_stale(db, today)  # also retries recomputes whose background run failed
    if recomputed:
        logger.info("Recomputed valuations of %d users", recomputed)
    return result


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
    zone = ZoneInfo(settings.market_timezone)
    schedule = DailySchedule(dt.time.fromisoformat(settings.market_daily_at), zone)
    intraday = IntradaySchedule(
        dt.time.fromisoformat(settings.market_intraday_from), dt.time.fromisoformat(settings.market_intraday_to),
        dt.timedelta(minutes=settings.market_intraday_minutes), zone,
    )
    state = WorkerState()
    logger.info("Worker started: daily update at %s %s", settings.market_daily_at, settings.market_timezone)
    with make_client() as client:
        providers = build_providers(client)
        run_forever(
            get_sessionmaker(),
            lambda db, now: tick(db, providers, schedule, state, now, intraday),
            settings.worker_poll_seconds,
            stop,
        )
    logger.info("Worker stopped")


if __name__ == "__main__":
    main()
