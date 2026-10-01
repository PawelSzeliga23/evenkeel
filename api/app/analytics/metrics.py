"""Return and risk measures from a portfolio's daily values and external flows (pure functions, plan 7a).

Series work goes through pandas; XIRR through pyxirr. Only the daily return is ours: it follows `twr_index` (a flow
counts at the start of its day), so the TWR here and on Pulpit agree.
"""
import datetime as dt
import math
from collections import defaultdict
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

import pandas as pd
from pyxirr import InvalidPaymentsError, xirr

Day = tuple[dt.date, Decimal, Decimal]  # (day, value, net external flow), in date order
Rate = tuple[dt.date, Decimal]  # (valid from, NBP reference rate in percent), in date order
Period = Literal["1m", "3m", "1y", "ytd", "all"]

PERIOD_MONTHS = {"1m": 1, "3m": 3, "1y": 12}
DAYS_PER_YEAR = 365
MIN_RISK_DAYS = 30
TOLERANCE = 1e-12  # products of float returns land a hair off a level they reach exactly
ONE_DAY = dt.timedelta(days=1)
PLACES = Decimal("0.01")
ZERO = Decimal(0)


@dataclass(frozen=True)
class DayExtreme:
    date: dt.date
    pct: Decimal
    pln: Decimal


@dataclass(frozen=True)
class Drawdown:
    pct: Decimal
    peak_date: dt.date
    trough_date: dt.date
    recovered_on: dt.date | None


@dataclass(frozen=True)
class MonthRow:
    year: int
    months: list[Decimal | None]  # January … December
    year_pct: Decimal | None
    first_partial_month: int | None  # 1–12 when the history starts inside that month


@dataclass(frozen=True)
class Analysis:
    start: dt.date
    end: dt.date
    days: int
    annualized: bool
    profit_pln: Decimal
    twr_period_pct: Decimal | None
    twr_annual_pct: Decimal | None
    xirr_period_pct: Decimal | None
    xirr_annual_pct: Decimal | None
    volatility_pct: Decimal | None
    sharpe: Decimal | None
    short_sample: bool
    max_drawdown: Drawdown | None
    current_drawdown_pct: Decimal | None
    best_day: DayExtreme | None
    worst_day: DayExtreme | None
    drawdown_series: list[tuple[dt.date, Decimal]]
    monthly: list[MonthRow]


def rounded(fraction: float | None, scale: int = 100) -> Decimal | None:
    """A fraction as a percentage (scale=1: a plain ratio) with 2 decimal places; None for a missing or NaN value.
    `float()` first: in numpy 2 `repr(np.float64(x))` is "np.float64(x)", which Decimal cannot read."""
    if fraction is None:
        return None
    value = float(fraction) * scale
    if math.isnan(value) or math.isinf(value):
        return None
    return Decimal(repr(value)).quantize(PLACES, rounding=ROUND_HALF_UP)


def period_start(period: Period, first: dt.date, end: dt.date) -> dt.date:
    """The first day whose return counts in the period (its base is the value of the day before), never before the
    first day of the history."""
    if period == "all":
        start = first
    elif period == "ytd":
        start = dt.date(end.year, 1, 1)
    else:
        start = (pd.Timestamp(end) - pd.DateOffset(months=PERIOD_MONTHS[period])).date() + ONE_DAY
    return max(start, first)


def daily_frame(days: Sequence[Day]) -> pd.DataFrame:
    """One row per day with a return: `r` = V_t / (V_{t−1} + F_t) − 1 and `gain` = V_t − V_{t−1} − F_t in zł.
    A day whose base V_{t−1} + F_t ≤ 0 has no return (as in `twr_index`)."""
    rows: list[tuple[pd.Timestamp, float, Decimal]] = []
    previous = ZERO
    for day, value, flow in days:
        base = previous + flow
        if base > 0:
            rows.append((pd.Timestamp(day), float(value / base - 1), value - previous - flow))
        previous = value
    # An explicit DatetimeIndex: an empty frame must still slice by date in `analyze`.
    index = pd.DatetimeIndex([at for at, _, _ in rows], name="date")
    return pd.DataFrame({"r": pd.Series([r for _, r, _ in rows], index=index, dtype=float),
                         "gain": pd.Series([g for _, _, g in rows], index=index, dtype=object)})


def annualize(fraction: float, days: int) -> float:
    return (1 + fraction) ** (DAYS_PER_YEAR / days) - 1


def annual_xirr(flows: dict[dt.date, Decimal]) -> float | None:
    """The investor's money-weighted yearly rate (paid in < 0, value out > 0); None when it has no solution."""
    dates = sorted(day for day, amount in flows.items() if amount)
    if len(dates) < 2:
        return None
    try:
        rate = xirr(dates, [float(flows[day]) for day in dates], silent=True)
    except InvalidPaymentsError:
        return None
    return None if rate is None or math.isnan(rate) else float(rate)


def volatility(returns: pd.Series) -> float | None:
    """Annualized sample standard deviation of the daily returns; None below MIN_RISK_DAYS returns."""
    if len(returns) < MIN_RISK_DAYS:
        return None
    return float(returns.std(ddof=1)) * math.sqrt(DAYS_PER_YEAR)


def risk_free(dates: pd.DatetimeIndex, rates: Sequence[Rate]) -> pd.Series:
    """The daily risk-free return on each date: the NBP reference rate in force / 365 (before the first known rate,
    the first one; without any rate, 0)."""
    if not rates:
        return pd.Series(0.0, index=dates)
    table = pd.Series([float(rate) / 100 / DAYS_PER_YEAR for _, rate in rates],
                      index=pd.DatetimeIndex([pd.Timestamp(day) for day, _ in rates]))
    return table.reindex(dates, method="ffill").fillna(table.iloc[0])


def sharpe(returns: pd.Series, rf: pd.Series) -> float | None:
    """Annualized Sharpe ratio of the daily returns over the risk-free ones; None below MIN_RISK_DAYS or without
    any movement."""
    if len(returns) < MIN_RISK_DAYS:
        return None
    deviation = float(returns.std(ddof=1))
    if deviation == 0:
        return None
    return float((returns - rf).mean()) / deviation * math.sqrt(DAYS_PER_YEAR)


def _drawdown(returns: pd.Series, base_day: dt.date) -> tuple[Drawdown, pd.Series]:
    """The deepest fall of 1 zł grown since the base day below its running record, and the fall on each day."""
    wealth = pd.concat([pd.Series([1.0], index=[pd.Timestamp(base_day)]), (1 + returns).cumprod()])
    fall = wealth / wealth.cummax() - 1
    fall = fall.where(fall < -TOLERANCE, 0.0)  # back exactly at the record is a record, not −0.0000000001 %
    trough = fall.idxmin()
    if fall[trough] >= 0:
        record = wealth.idxmax().date()
        return Drawdown(rounded(0.0), record, record, None), fall.iloc[1:]
    peak = wealth.loc[:trough].idxmax()
    later = wealth.loc[trough:].iloc[1:]
    back = later[later >= wealth[peak] * (1 - TOLERANCE)]
    recovered = back.index[0].date() if len(back) else None
    return Drawdown(rounded(fall[trough]), peak.date(), trough.date(), recovered), fall.iloc[1:]


def monthly_returns(returns: pd.Series) -> list[MonthRow]:
    """TWR of every calendar month and year with returns, newest year first."""
    if returns.empty:
        return []
    growth = 1 + returns
    years, months = returns.index.year, returns.index.month
    by_month = growth.groupby([years, months]).prod() - 1
    first = returns.index[0]
    rows: list[MonthRow] = []
    for year in sorted(set(years), reverse=True):
        cells = [rounded(by_month[(year, month)]) if (year, month) in by_month.index else None for month in range(1, 13)]
        partial = first.month if year == first.year and first.day != 1 else None
        rows.append(MonthRow(int(year), cells, rounded(growth[years == year].prod() - 1), partial))
    return rows


def _extreme(frame: pd.DataFrame, at: pd.Timestamp) -> DayExtreme:
    return DayExtreme(at.date(), rounded(frame.at[at, "r"]), frame.at[at, "gain"].quantize(PLACES))


def analyze(days: Sequence[Day], rates: Sequence[Rate], period: Period) -> Analysis | None:
    """Every 7a measure for the period ending on the last valued day; None without any valuation."""
    if not days:
        return None
    first, end = days[0][0], days[-1][0]
    start = period_start(period, first, end)
    span = (end - start).days + 1
    annualized = span >= DAYS_PER_YEAR

    frame = daily_frame(days)
    window = frame.loc[pd.Timestamp(start):]
    returns = window["r"]

    base_value = next((value for day, value, _ in reversed(days) if day < start), ZERO)
    flows = [(day, flow) for day, _, flow in days if day >= start and flow]
    end_value = days[-1][1]
    profit = end_value - base_value - sum((flow for _, flow in flows), ZERO)

    twr = float((1 + returns).prod() - 1) if len(returns) else None
    cash: defaultdict[dt.date, Decimal] = defaultdict(Decimal)
    if base_value:
        cash[start - ONE_DAY] -= base_value
    for day, flow in flows:
        cash[day] -= flow
    cash[end] += end_value
    yearly = annual_xirr(dict(cash))
    held = (end - min(cash)).days  # pyxirr's span: from the first cash flow, which is `start` itself without a base

    drawdown, fall = _drawdown(returns, start - ONE_DAY) if len(returns) else (None, pd.Series(dtype=float))
    return Analysis(
        start=start, end=end, days=span, annualized=annualized,
        profit_pln=profit.quantize(PLACES),
        twr_period_pct=rounded(twr),
        twr_annual_pct=rounded(annualize(twr, span)) if annualized and twr is not None else None,
        xirr_period_pct=rounded((1 + yearly) ** (held / DAYS_PER_YEAR) - 1) if yearly is not None else None,
        xirr_annual_pct=rounded(yearly) if annualized and yearly is not None else None,
        volatility_pct=rounded(volatility(returns)),
        sharpe=rounded(sharpe(returns, risk_free(returns.index, rates)), scale=1),
        short_sample=not annualized,
        max_drawdown=drawdown,
        current_drawdown_pct=rounded(fall.iloc[-1]) if len(fall) else None,
        best_day=_extreme(window, returns.idxmax()) if len(returns) else None,
        worst_day=_extreme(window, returns.idxmin()) if len(returns) else None,
        drawdown_series=[(at.date(), rounded(value)) for at, value in fall.items()],
        monthly=monthly_returns(frame["r"]),
    )
