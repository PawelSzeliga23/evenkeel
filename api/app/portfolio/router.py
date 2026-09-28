import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.portfolio.closed import closed_investments
from app.portfolio.exposure import currency_exposure
from app.portfolio.schemas import ClosedOut, ExposureOut, HistoryOut, PositionDetailOut, PositionOut, SummaryOut
from app.portfolio.service import list_positions, portfolio_history, portfolio_summary, position_detail
from app.scoping import DbId, UserScope, get_scope
from app.valuation.service import local_today

router = APIRouter(prefix="/api", tags=["portfolio"])

AccountFilter = Annotated[int | None, Query(ge=1, le=2**31 - 1)]


def _account(scope: UserScope, account_id: int | None) -> int | None:
    """A filter by someone else's account is a 404, like the account itself."""
    if account_id is not None:
        scope.get_account(account_id)
    return account_id


@router.get("/portfolio/summary", response_model=SummaryOut)
def get_summary(scope: UserScope = Depends(get_scope), account_id: AccountFilter = None) -> SummaryOut:
    return portfolio_summary(scope, _account(scope, account_id))


@router.get("/portfolio/history", response_model=HistoryOut)
def get_history(
    scope: UserScope = Depends(get_scope),
    account_id: AccountFilter = None,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> HistoryOut:
    return portfolio_history(scope, _account(scope, account_id), start, end)


DayQuery = Annotated[dt.date | None, Query(alias="date")]


@router.get("/positions", response_model=list[PositionOut])
def get_positions(
    scope: UserScope = Depends(get_scope), account_id: AccountFilter = None, day: DayQuery = None
) -> list[PositionOut]:
    return list_positions(scope, _account(scope, account_id), day or local_today())


@router.get("/positions/{account_id}/{instrument_id}", response_model=PositionDetailOut)
def get_position(
    account_id: DbId, instrument_id: DbId, scope: UserScope = Depends(get_scope), day: DayQuery = None
) -> PositionDetailOut:
    account, instrument = scope.get_account(account_id), scope.get_instrument(instrument_id)
    return position_detail(scope, account, instrument, day or local_today())


@router.get("/portfolio/closed", response_model=ClosedOut)
def get_closed(scope: UserScope = Depends(get_scope), account_id: AccountFilter = None) -> ClosedOut:
    return closed_investments(scope, _account(scope, account_id), local_today())


@router.get("/portfolio/exposure", response_model=ExposureOut)
def get_exposure(
    scope: UserScope = Depends(get_scope),
    account_id: AccountFilter = None,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> ExposureOut:
    return currency_exposure(scope, _account(scope, account_id), start, end)
