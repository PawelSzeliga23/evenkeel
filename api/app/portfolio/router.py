import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.portfolio.schemas import HistoryOut, SummaryOut
from app.portfolio.service import portfolio_history, portfolio_summary
from app.scoping import UserScope, get_scope

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
