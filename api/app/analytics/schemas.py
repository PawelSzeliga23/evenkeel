import datetime as dt
from decimal import Decimal

from pydantic import BaseModel


class PeriodOut(BaseModel):
    start: dt.date
    end: dt.date
    days: int
    annualized: bool


class ReturnOut(BaseModel):
    period_pct: Decimal | None
    annual_pct: Decimal | None


class DrawdownOut(BaseModel):
    pct: Decimal
    peak_date: dt.date
    trough_date: dt.date
    recovered_on: dt.date | None


class DayExtremeOut(BaseModel):
    date: dt.date
    pct: Decimal
    pln: Decimal


class DrawdownPointOut(BaseModel):
    date: dt.date
    pct: Decimal


class MonthRowOut(BaseModel):
    year: int
    months: list[Decimal | None]
    year_pct: Decimal | None
    first_partial_month: int | None


class AnalyticsOut(BaseModel):
    period: PeriodOut | None
    profit_pln: Decimal
    twr: ReturnOut
    xirr: ReturnOut
    volatility_pct: Decimal | None
    sharpe: Decimal | None
    short_sample: bool
    max_drawdown: DrawdownOut | None
    current_drawdown_pct: Decimal | None
    best_day: DayExtremeOut | None
    worst_day: DayExtremeOut | None
    drawdown_series: list[DrawdownPointOut]
    monthly: list[MonthRowOut]
    recalculating: bool
