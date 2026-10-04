"""GET /api/market/schedule (plan 8c): when prices are refreshed — the worker's settings — and when they last were."""
import datetime as dt

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.config import Settings, app_settings
from app.portfolio.service import prices_refreshed_at
from app.scoping import UserScope, get_scope

router = APIRouter(prefix="/api/market", tags=["market"])


class ScheduleOut(BaseModel):
    intraday_every_minutes: int
    intraday_from: str
    intraday_to: str
    daily_at: str
    timezone: str
    last_refreshed_at: dt.datetime | None


@router.get("/schedule", response_model=ScheduleOut)
def schedule(scope: UserScope = Depends(get_scope), settings: Settings = Depends(app_settings)) -> ScheduleOut:
    return ScheduleOut(
        intraday_every_minutes=settings.market_intraday_minutes, intraday_from=settings.market_intraday_from,
        intraday_to=settings.market_intraday_to, daily_at=settings.market_daily_at, timezone=settings.market_timezone,
        last_refreshed_at=prices_refreshed_at(scope),
    )
