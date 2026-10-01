"""Analiza (plan 7a): the measures of `metrics.analyze` for the user's portfolio or chosen accounts."""
from dataclasses import asdict
from decimal import Decimal

from sqlalchemy import select

from app.analytics.metrics import Analysis, Period, analyze
from app.analytics.schemas import (
    AnalyticsOut, DayExtremeOut, DrawdownOut, DrawdownPointOut, MonthRowOut, PeriodOut, ReturnOut,
)
from app.models import NbpRefRate, User
from app.portfolio.service import daily_totals
from app.scoping import UserScope

NO_RETURN = ReturnOut(period_pct=None, annual_pct=None)


def _out(result: Analysis, recalculating: bool) -> AnalyticsOut:
    return AnalyticsOut(
        period=PeriodOut(start=result.start, end=result.end, days=result.days, annualized=result.annualized),
        profit_pln=result.profit_pln,
        twr=ReturnOut(period_pct=result.twr_period_pct, annual_pct=result.twr_annual_pct),
        xirr=ReturnOut(period_pct=result.xirr_period_pct, annual_pct=result.xirr_annual_pct),
        volatility_pct=result.volatility_pct, sharpe=result.sharpe, short_sample=result.short_sample,
        max_drawdown=DrawdownOut(**asdict(result.max_drawdown)) if result.max_drawdown else None,
        current_drawdown_pct=result.current_drawdown_pct,
        best_day=DayExtremeOut(**asdict(result.best_day)) if result.best_day else None,
        worst_day=DayExtremeOut(**asdict(result.worst_day)) if result.worst_day else None,
        drawdown_series=[DrawdownPointOut(date=day, pct=pct) for day, pct in result.drawdown_series],
        monthly=[MonthRowOut(**asdict(row)) for row in result.monthly],
        recalculating=recalculating,
    )


def portfolio_analytics(scope: UserScope, account_ids: frozenset[int] | None, period: Period) -> AnalyticsOut:
    db = scope.db
    recalculating = db.scalar(select(User.valuations_stale_from).where(User.id == scope.user.id)) is not None
    rates = [(row.valid_from, row.rate) for row in db.execute(
        select(NbpRefRate.valid_from, NbpRefRate.rate).order_by(NbpRefRate.valid_from))]
    result = analyze(daily_totals(scope, account_ids), rates, period)
    if result is None:
        return AnalyticsOut(
            period=None, profit_pln=Decimal("0.00"), twr=NO_RETURN, xirr=NO_RETURN, volatility_pct=None, sharpe=None,
            short_sample=False, max_drawdown=None, current_drawdown_pct=None, best_day=None, worst_day=None,
            drawdown_series=[], monthly=[], recalculating=recalculating,
        )
    return _out(result, recalculating)
