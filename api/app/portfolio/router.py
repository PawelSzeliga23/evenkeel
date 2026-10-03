import datetime as dt
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session_factory
from app.market.deps import get_market_providers
from app.market.update import MarketProviders, update_fx, update_prices
from app.models import BondHolding
from app.portfolio.closed import closed_investments
from app.portfolio.exposure import currency_exposure
from app.portfolio.limits import wrapper_limits
from app.portfolio.price_chart import price_chart
from app.portfolio.schemas import (
    ClosedOut, ExposureOut, HistoryOut, LimitOut, PositionDetailOut, PositionOut, PriceChartOut, RefreshOut,
    SummaryOut,
)
from app.portfolio.service import (
    list_positions, portfolio_history, portfolio_summary, position_detail, prices_refreshed_at,
)
from app.notes.service import holding_notes
from app.scoping import AccountIds, DbId, UserScope, get_scope
from app.tags.lookup import TagLookup
from app.valuation.service import local_today, mark_market_changes, recompute_in_background

router = APIRouter(prefix="/api", tags=["portfolio"])


@router.get("/portfolio/summary", response_model=SummaryOut)
def get_summary(scope: UserScope = Depends(get_scope), account_ids: AccountIds = None) -> SummaryOut:
    return portfolio_summary(scope, scope.account_filter(account_ids))


@router.get("/portfolio/history", response_model=HistoryOut)
def get_history(
    scope: UserScope = Depends(get_scope),
    account_ids: AccountIds = None,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> HistoryOut:
    return portfolio_history(scope, scope.account_filter(account_ids), start, end)


DayQuery = Annotated[dt.date | None, Query(alias="date")]


@router.get("/positions", response_model=list[PositionOut])
def get_positions(
    scope: UserScope = Depends(get_scope), account_ids: AccountIds = None, day: DayQuery = None
) -> list[PositionOut]:
    positions = list_positions(scope, scope.account_filter(account_ids), day or local_today())
    lookup = TagLookup(scope)
    series = dict(scope.db.execute(scope.bond_holdings().with_only_columns(BondHolding.id, BondHolding.series)).all())
    for p in positions:
        if p.kind == "instrument" and p.instrument_id is not None:
            p.tags = lookup.on(f"i:{p.instrument_id}", p.account_id)
        elif p.kind == "bond" and p.bond_holding_id is not None:
            p.tags = lookup.on(f"b:{series[p.bond_holding_id]}", p.account_id)
        elif p.kind == "savings":
            p.tags = lookup.on("s:", p.account_id)
    return positions


@router.get("/positions/{account_id}/{instrument_id}", response_model=PositionDetailOut)
def get_position(
    account_id: DbId, instrument_id: DbId, scope: UserScope = Depends(get_scope), day: DayQuery = None
) -> PositionDetailOut:
    account, instrument = scope.get_account(account_id), scope.get_instrument(instrument_id)
    detail = position_detail(scope, account, instrument, day or local_today())
    detail.tags = TagLookup(scope).on(f"i:{instrument.id}", account.id)
    detail.notes = holding_notes(scope, f"i:{instrument.id}")
    return detail


@router.get("/positions/{account_id}/{instrument_id}/prices", response_model=PriceChartOut)
def get_position_prices(
    account_id: DbId, instrument_id: DbId, scope: UserScope = Depends(get_scope),
    start: Annotated[dt.date | None, Query(alias="from")] = None,
) -> PriceChartOut:
    account, instrument = scope.get_account(account_id), scope.get_instrument(instrument_id)
    return price_chart(scope, account, instrument, start)


@router.get("/portfolio/closed", response_model=ClosedOut)
def get_closed(scope: UserScope = Depends(get_scope), account_ids: AccountIds = None) -> ClosedOut:
    return closed_investments(scope, scope.account_filter(account_ids), local_today())


@router.get("/portfolio/exposure", response_model=ExposureOut)
def get_exposure(
    scope: UserScope = Depends(get_scope),
    account_ids: AccountIds = None,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> ExposureOut:
    return currency_exposure(scope, scope.account_filter(account_ids), start, end)


@router.get("/portfolio/limits", response_model=list[LimitOut])
def get_limits(scope: UserScope = Depends(get_scope)) -> list[LimitOut]:
    return wrapper_limits(scope, local_today())


REFRESH_THROTTLE = dt.timedelta(seconds=60)


@router.post("/portfolio/refresh", response_model=RefreshOut)
def refresh_prices(
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
    providers: MarketProviders = Depends(get_market_providers),
) -> RefreshOut:
    """Fetches the user's prices and the NBP rates now; the valuation is recomputed right after the response.
    Provider problems land in each instrument's `price_error`, as in the worker; they are not an error here."""
    db = scope.db
    instruments = list(db.scalars(scope.instruments()))
    if not instruments:
        return RefreshOut(refreshed_at=None, fetched=False)
    latest = prices_refreshed_at(scope)
    now = dt.datetime.now(dt.UTC)
    if latest is not None and now - latest < REFRESH_THROTTLE:
        return RefreshOut(refreshed_at=latest, fetched=False)
    prices_from: dict[int, dt.date] = {}
    fx_from: dict[str, dt.date] = {}
    update_prices(db, providers.prices, instruments, now, prices_from)
    update_fx(db, providers.fx, local_today(), fx_from)
    mark_market_changes(db, prices_from, fx_from)
    db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)
    return RefreshOut(refreshed_at=now, fetched=True)
