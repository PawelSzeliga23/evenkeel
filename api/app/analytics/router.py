from fastapi import APIRouter, Depends

from app.analytics.metrics import Period
from app.analytics.schemas import AnalyticsOut
from app.analytics.service import portfolio_analytics
from app.scoping import AccountIds, UserScope, get_scope

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsOut)
def get_analytics(
    scope: UserScope = Depends(get_scope), account_ids: AccountIds = None, period: Period = "all",
) -> AnalyticsOut:
    return portfolio_analytics(scope, scope.account_filter(account_ids), period)
