from fastapi import APIRouter, Depends

from app.analytics.metrics import Period
from app.analytics.holdings import HoldingsPeriod, holdings
from app.analytics.income import IncomePeriod, income
from app.analytics.schemas import AnalyticsOut, HoldingsOut, IncomeOut
from app.analytics.service import portfolio_analytics
from app.scoping import AccountIds, UserScope, get_scope

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsOut)
def get_analytics(
    scope: UserScope = Depends(get_scope), account_ids: AccountIds = None, period: Period = "all",
) -> AnalyticsOut:
    return portfolio_analytics(scope, scope.account_filter(account_ids), period)


@router.get("/analytics/holdings", response_model=HoldingsOut)
def get_holdings(
    scope: UserScope = Depends(get_scope), account_ids: AccountIds = None, period: HoldingsPeriod = "1d",
) -> HoldingsOut:
    return holdings(scope, scope.account_filter(account_ids), period)


@router.get("/analytics/income", response_model=IncomeOut)
def get_income(scope: UserScope = Depends(get_scope), account_ids: AccountIds = None,
               period: IncomePeriod = "ytd") -> IncomeOut:
    return income(scope, scope.account_filter(account_ids), period)
