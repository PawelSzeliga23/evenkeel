# Plan 7a — Returns and Risk Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A new Analiza screen, linked from a Pulpit card. For a chosen period and the chosen accounts it shows profit, TWR, XIRR, volatility, max and current drawdown, Sharpe, the best and worst day, a drawdown chart and the monthly returns.

**Architecture:** A new API module `app/analytics` has pure functions in `metrics.py`. They use pandas and numpy for the series and pyxirr for XIRR, and run on the same daily totals the Pulpit uses (`daily_totals`). One endpoint, `GET /api/analytics`, returns everything the screen needs. The web app gets a self-hiding `AnalyticsCard` on Pulpit, an `AnalysisScreen` at `/analiza`, a small `DrawdownChart`, and a `MonthlyReturns` grid. The grid uses one DOM and CSS-only phone and desktop layouts, so nothing ever scrolls sideways.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, pandas, numpy, pyxirr, pytest. React 19, TypeScript, TanStack Query, Vitest, and Playwright.

**Spec:** `docs/superpowers/specs/2026-10-01-07a-returns-and-risk-design.md`

## Global Constraints

- New API dependencies are exactly `pandas`, `numpy` and `pyxirr`. Do not add `empyrical-reloaded` or `quantstats`.
- Money stays `Decimal`, quantized to 0.01. Statistical measures are computed on `float` and quantized to 2 places only on output, as strings in JSON.
- The daily return is `r_t = V_t / (V_{t−1} + F_t) − 1`, the same rule as `twr_index`, with the flow counted at the start of its day. Days where `V_{t−1} + F_t ≤ 0` have no return.
- Calendar days are used, not trading days. The annualization factor is √365, and a year is 365 days.
- Returns (TWR, XIRR) are shown **for the period** when the period is shorter than 365 days, and **annual** when it is 365 days or longer.
- Volatility and Sharpe are always annual. They are `null` with fewer than 30 daily returns, and marked `short_sample` when the period is shorter than a year.
- The risk-free rate is the NBP reference rate in force on each day (`nbp_ref_rates`) divided by 365. Before the first known rate, the first rate applies; with no rates at all, it is 0.
- The monthly table always covers the whole history, whatever the period.
- UI copy is in Polish. The period labels are `1M`, `3M`, `1R`, `Od pocz. roku` and `Wszystko`.
- The monthly returns never scroll horizontally.
- Every measure has a "?" tooltip (`InfoTip`) with what it means and a "Jak liczymy:" line saying how it is counted. It opens on mouse hover, and on a tap or Enter/Space. Esc, a tap elsewhere or scrolling closes it. Measures are the Analiza tiles and section headings, the Pulpit card, and the Pulpit stats (Zysk łącznie, Stopa zwrotu (TWR), Wpłacono, Dywidendy i odsetki).
- Test commands:
  - API: `docker compose run --rm api pytest`
  - Web: `npm test` and `npx tsc -b`, run in `web/`
  - e2e: `npm run e2e`, run in `web/`

## Review Focus

1. **A period longer than the history** (1R on 7 months): it must clamp to the first day, start from a base of 0 and not annualize. This is pinned in Task 1 `test_period_start_*` and Task 2 `test_ytd_*`.
2. **A portfolio that never fell below its record**: the max drawdown is 0 with no fake dates, and the screen says "bez spadku od rekordu". This is pinned in Task 1 `test_never_falling_*` and Task 3 `shows a portfolio without a fall`.
3. **XIRR with no solution or a single cash flow** (everything withdrawn, or only today's value) must return `null`, not a 500. This is pinned in Task 1 `test_annual_xirr_without_a_solution_is_none`.
4. **numpy floats reaching `Decimal`**: `repr(np.float64)` is `np.float64(…)` in numpy 2, so every conversion goes through `float()`. This is pinned in Task 1 by the monthly and drawdown tests, which pass numpy values through `rounded`.
5. **Switching accounts or period while data loads**: the screen keeps the previous numbers (`placeholderData`) and never shows two monthly grids or a sideways scroll. This is pinned in Task 4 by the single-DOM grid test.

---

## File Structure

API:
- Create `api/app/analytics/__init__.py`: empty.
- Create `api/app/analytics/metrics.py`: pure functions (period, daily frame, XIRR, volatility, Sharpe, drawdown, monthly) and `analyze`.
- Create `api/app/analytics/schemas.py`: Pydantic response models.
- Create `api/app/analytics/service.py`: loads the daily totals and the NBP rates, calls `analyze`, and maps the result to the schema.
- Create `api/app/analytics/router.py`: `GET /api/analytics`.
- Modify `api/app/portfolio/service.py`: rename `_daily_totals` to `daily_totals` (public, same behaviour).
- Modify `api/app/main.py`: include the analytics router.
- Modify `api/pyproject.toml`: add the dependencies.
- Create `api/tests/test_analytics_metrics.py` and `api/tests/test_analytics_api.py`.

Web:
- Create `web/src/ui/InfoTip.tsx`, `web/src/ui/InfoTip.module.css`, `web/src/ui/help.ts` (all tooltip texts) and `web/src/ui/InfoTip.test.tsx`.
- Modify `web/src/api/types.ts`, `web/src/api/endpoints.ts` and `web/src/api/queryKeys.ts`.
- Create `web/src/screens/analysis/model.ts`: periods, captions, help texts, month names and cell colour.
- Create `web/src/screens/analysis/AnalysisScreen.tsx` and `Analysis.module.css`.
- Create `web/src/screens/analysis/MonthlyReturns.tsx`.
- Create `web/src/charts/DrawdownChart.tsx` and `DrawdownChart.module.css`.
- Create `web/src/screens/analysis/AnalyticsCard.tsx`: the Pulpit card.
- Modify `web/src/routes.tsx` and `web/src/screens/dashboard/DashboardScreen.tsx`.
- Create `web/src/screens/analysis/analysis.test.tsx`, and modify `web/src/test/fixtures.ts`.
- Modify `web/e2e/app.spec.ts`.
- Modify `docs/superpowers/plans/2026-09-26-00-roadmap.md`.

---

### Task 1: Pure metrics with pandas and pyxirr

**Files:**
- Modify: `api/pyproject.toml`
- Create: `api/app/analytics/__init__.py`, `api/app/analytics/metrics.py`
- Test: `api/tests/test_analytics_metrics.py`

**Interfaces:**
- Consumes: `app.valuation.returns.twr_index` (only in a test, to prove the daily rule matches).
- Produces:
  - `Day = tuple[dt.date, Decimal, Decimal]`
  - `Period = Literal["1m", "3m", "1y", "ytd", "all"]`
  - `period_start(period, first, end) -> dt.date`
  - `daily_frame(days) -> pd.DataFrame` (index `DatetimeIndex`, columns `r: float`, `gain: Decimal`)
  - `annual_xirr(flows: dict[dt.date, Decimal]) -> float | None`
  - `volatility(returns: pd.Series) -> float | None`
  - `risk_free(dates: pd.DatetimeIndex, rates) -> pd.Series`
  - `sharpe(returns, rf) -> float | None`
  - `monthly_returns(returns) -> list[MonthRow]`
  - `rounded(fraction, scale=100) -> Decimal | None`
  - `analyze(days, rates, period) -> Analysis | None`
  - Dataclasses `DayExtreme(date, pct, pln)`, `Drawdown(pct, peak_date, trough_date, recovered_on)`, `MonthRow(year, months, year_pct, first_partial_month)` and `Analysis` (fields below).

- [ ] **Step 1: Add the dependencies and rebuild the image**

In `api/pyproject.toml`, add these lines to `dependencies` after `"tzdata>=2024.1",`:

```toml
  "numpy>=2.3",
  "pandas>=3.0",
  "pyxirr>=0.10.8",
```

Run: `docker compose build api worker`
Expected: the build finishes. Then run `docker compose run --rm api python -c "import pandas, numpy, pyxirr, inspect; print(pandas.__version__, numpy.__version__); print(inspect.signature(pyxirr.xirr))"`.
Expected: the versions print, and the signature shows a keyword-only `silent` parameter. If there is no `silent` parameter, drop `silent=True` from `annual_xirr` in Step 3 and keep only the `except`.

- [ ] **Step 2: Write the failing tests**

Create `api/tests/test_analytics_metrics.py`:

```python
import datetime as dt
from decimal import Decimal

import pandas as pd
import pytest

from app.analytics.metrics import (
    Drawdown, DayExtreme, MonthRow, analyze, annual_xirr, daily_frame, monthly_returns, period_start, risk_free,
    rounded, sharpe, volatility,
)
from app.valuation.returns import twr_index

D = Decimal


def day(text: str) -> dt.date:
    return dt.date.fromisoformat(text)


# 1 000 zł in, +10 %, −10 %, 500 zł more, +10 %:
# returns 0, 0.1, −0.1, 0, 0.1 → TWR 1.1 × 0.9 × 1.1 − 1 = 8.90 %
FIVE_DAYS = [
    (day("2026-01-01"), D("1000"), D("1000")),
    (day("2026-01-02"), D("1100"), D("0")),
    (day("2026-01-03"), D("990"), D("0")),
    (day("2026-01-04"), D("1490"), D("500")),
    (day("2026-01-05"), D("1639"), D("0")),
]


@pytest.mark.parametrize(("period", "expected"), [
    ("1m", "2025-08-31"), ("3m", "2025-07-01"), ("1y", "2024-10-01"), ("ytd", "2025-01-01"), ("all", "2024-03-01"),
])
def test_period_start_counts_back_from_the_last_day(period: str, expected: str) -> None:
    assert period_start(period, day("2024-03-01"), day("2025-09-30")) == day(expected)


def test_period_start_is_clamped_to_the_first_day() -> None:
    assert period_start("1y", day("2026-03-01"), day("2026-09-30")) == day("2026-03-01")
    assert period_start("ytd", day("2026-03-01"), day("2026-09-30")) == day("2026-03-01")


def test_period_start_of_one_month_at_a_month_end() -> None:
    assert period_start("1m", day("2026-01-01"), day("2026-03-31")) == day("2026-03-01")  # 02-28 + 1 day


def test_daily_frame_uses_the_twr_rule() -> None:
    frame = daily_frame(FIVE_DAYS)

    assert list(frame["r"].round(10)) == [0.0, 0.1, -0.1, 0.0, 0.1]
    assert list(frame["gain"]) == [D("0"), D("100"), D("-110"), D("0"), D("149")]
    factor = twr_index(FIVE_DAYS)[-1][1]
    assert float((1 + frame["r"]).prod()) == pytest.approx(float(factor))


def test_daily_frame_skips_days_without_a_base() -> None:
    frame = daily_frame([(day("2026-01-01"), D("0"), D("0")), (day("2026-01-02"), D("100"), D("100"))])
    assert list(frame.index.date) == [day("2026-01-02")]


def test_analyze_the_whole_short_history() -> None:
    result = analyze(FIVE_DAYS, [], "all")

    assert (result.start, result.end, result.days, result.annualized) == (day("2026-01-01"), day("2026-01-05"), 5, False)
    assert result.profit_pln == D("139.00")
    assert (result.twr_period_pct, result.twr_annual_pct) == (D("8.90"), None)
    assert result.xirr_period_pct is not None and result.xirr_annual_pct is None
    assert (result.volatility_pct, result.sharpe, result.short_sample) == (None, None, True)
    assert result.max_drawdown == Drawdown(D("-10.00"), day("2026-01-02"), day("2026-01-03"), None)
    assert result.current_drawdown_pct == D("-1.00")
    assert result.best_day == DayExtreme(day("2026-01-02"), D("10.00"), D("100.00"))
    assert result.worst_day == DayExtreme(day("2026-01-03"), D("-10.00"), D("-110.00"))
    assert result.drawdown_series[0] == (day("2026-01-01"), D("0.00"))
    assert result.drawdown_series[2] == (day("2026-01-03"), D("-10.00"))
    assert len(result.drawdown_series) == 5
    assert result.monthly == [MonthRow(2026, [D("8.90")] + [None] * 11, D("8.90"), None)]


def test_analyze_a_recovered_drawdown() -> None:
    days = FIVE_DAYS + [(day("2026-01-06"), D("1700"), D("0"))]  # 1 700 / 1 639 → above the 01-02 record
    assert analyze(days, [], "all").max_drawdown.recovered_on == day("2026-01-06")


def test_never_falling_portfolio_has_a_zero_drawdown() -> None:
    days = [(day("2026-01-01"), D("100"), D("100")), (day("2026-01-02"), D("110"), D("0"))]
    result = analyze(days, [], "all")

    assert result.max_drawdown == Drawdown(D("0.00"), day("2026-01-02"), day("2026-01-02"), None)
    assert result.current_drawdown_pct == D("0.00")


def test_a_period_starts_from_the_value_of_the_day_before() -> None:
    days = [
        (day("2025-12-30"), D("1000"), D("1000")),
        (day("2025-12-31"), D("1100"), D("0")),
        (day("2026-01-02"), D("1210"), D("0")),
    ]
    result = analyze(days, [], "ytd")

    assert (result.start, result.days) == (day("2026-01-01"), 2)
    assert (result.profit_pln, result.twr_period_pct) == (D("110.00"), D("10.00"))
    assert [row.year for row in result.monthly] == [2026, 2025]  # the whole history, newest first


def test_a_year_long_period_is_annualized() -> None:
    start = day("2024-01-01")
    days = [
        (start + dt.timedelta(days=t), D(1000 * 1.1 ** (t / 365)).quantize(D("0.01")), D("1000") if t == 0 else D("0"))
        for t in range(731)
    ]
    result = analyze(days, [], "1y")

    assert (result.start, result.days, result.annualized, result.short_sample) == (day("2025-01-01"), 365, True, False)
    assert (result.twr_period_pct, result.twr_annual_pct) == (D("10.00"), D("10.00"))
    assert (result.xirr_period_pct, result.xirr_annual_pct) == (D("10.00"), D("10.00"))


def test_analyze_without_valuations_is_none() -> None:
    assert analyze([], [], "all") is None


def test_analyze_with_only_zero_values_has_no_returns() -> None:
    result = analyze([(day("2026-01-01"), D("0"), D("0"))], [], "all")

    assert (result.twr_period_pct, result.max_drawdown, result.best_day, result.monthly) == (None, None, None, [])
    assert result.drawdown_series == []


def test_annual_xirr_matches_excel() -> None:
    flows = {
        day("2008-01-01"): D("-10000"), day("2008-03-01"): D("2750"), day("2008-10-30"): D("4250"),
        day("2009-02-15"): D("3250"), day("2009-04-01"): D("2750"),
    }
    assert rounded(annual_xirr(flows)) == D("37.34")  # Excel XIRR: 0.373362535


def test_annual_xirr_without_a_solution_is_none() -> None:
    assert annual_xirr({day("2026-01-01"): D("100"), day("2026-02-01"): D("50")}) is None  # money only comes out
    assert annual_xirr({day("2026-01-01"): D("100")}) is None


ALTERNATING = pd.Series([0.01 if i % 2 == 0 else -0.01 for i in range(30)],
                        index=pd.date_range("2026-01-01", periods=30))


def test_volatility_is_the_annualized_standard_deviation() -> None:
    assert rounded(volatility(ALTERNATING)) == D("19.43")
    assert volatility(ALTERNATING.iloc[:29]) is None


def test_sharpe_against_the_nbp_rate() -> None:
    rf = risk_free(ALTERNATING.index, [(day("2020-01-01"), D("5.00"))])
    assert rounded(sharpe(ALTERNATING, rf), scale=1) == D("-0.26")
    assert sharpe(ALTERNATING.iloc[:29], rf.iloc[:29]) is None


def test_risk_free_follows_the_rate_in_force() -> None:
    dates = pd.DatetimeIndex(pd.to_datetime(["2025-12-31", "2026-01-01", "2026-01-02", "2026-01-03"]))
    rf = risk_free(dates, [(day("2026-01-01"), D("5.75")), (day("2026-01-03"), D("5.00"))])

    assert list((rf * 365 * 100).round(6)) == [5.75, 5.75, 5.75, 5.0]
    assert list(risk_free(dates, [])) == [0.0] * 4


def test_monthly_returns_with_a_partial_first_month() -> None:
    returns = daily_frame([
        (day("2026-01-15"), D("1000"), D("1000")),
        (day("2026-01-31"), D("1050"), D("0")),
        (day("2026-02-28"), D("1029"), D("0")),
    ])["r"]
    assert monthly_returns(returns) == [
        MonthRow(2026, [D("5.00"), D("-2.00")] + [None] * 10, D("2.90"), 1),
    ]


def test_rounded_accepts_numpy_floats_and_rejects_nan() -> None:
    assert rounded(pd.Series([0.05]).iloc[0]) == D("5.00")
    assert rounded(float("nan")) is None
    assert rounded(None) is None
```

- [ ] **Step 3: Run the tests to verify they fail**

Run: `docker compose run --rm api pytest tests/test_analytics_metrics.py -q`
Expected: the run FAILS with `ModuleNotFoundError: No module named 'app.analytics'`.

- [ ] **Step 4: Write the implementation**

Create an empty `api/app/analytics/__init__.py`.

Create `api/app/analytics/metrics.py`:

```python
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
    trough = fall.idxmin()
    if fall[trough] >= 0:
        record = wealth.idxmax().date()
        return Drawdown(rounded(0.0), record, record, None), fall.iloc[1:]
    peak = wealth.loc[:trough].idxmax()
    later = wealth.loc[trough:].iloc[1:]
    back = later[later >= wealth[peak]]
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

    drawdown, fall = _drawdown(returns, start - ONE_DAY) if len(returns) else (None, pd.Series(dtype=float))
    return Analysis(
        start=start, end=end, days=span, annualized=annualized,
        profit_pln=profit.quantize(PLACES),
        twr_period_pct=rounded(twr),
        twr_annual_pct=rounded(annualize(twr, span)) if annualized and twr is not None else None,
        xirr_period_pct=rounded((1 + yearly) ** (span / DAYS_PER_YEAR) - 1) if yearly is not None else None,
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
```

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose run --rm api pytest tests/test_analytics_metrics.py -q`
Expected: all tests PASS. If `test_never_falling_portfolio_has_a_zero_drawdown` fails on the record date, check that `wealth.idxmax()` returns the **first** maximum (pandas does). The record in that test is 2026-01-02.

- [ ] **Step 6: Run the whole API suite**

Run: `docker compose run --rm api pytest -q`
Expected: all tests PASS (595 before this plan, plus the new ones).

- [ ] **Step 7: Commit**

```bash
git add api/pyproject.toml api/app/analytics api/tests/test_analytics_metrics.py
git commit -m "feat(api): return and risk measures for a portfolio's daily values (pandas, pyxirr)"
```

---

### Task 2: `GET /api/analytics`

**Files:**
- Modify: `api/app/portfolio/service.py` (rename `_daily_totals`; it is called at about lines 71, 161 and 183)
- Create: `api/app/analytics/schemas.py`, `api/app/analytics/service.py`, `api/app/analytics/router.py`
- Modify: `api/app/main.py`
- Test: `api/tests/test_analytics_api.py`

**Interfaces:**
- Consumes: `analyze`, `Analysis`, `Period` and `Rate` from Task 1; `UserScope`, `AccountIds` and `get_scope` from `app.scoping`.
- Produces:
  - `daily_totals(scope, account_ids) -> list[tuple[date, Decimal, Decimal]]` in `app.portfolio.service`
  - `portfolio_analytics(scope, account_ids, period) -> AnalyticsOut`
  - JSON as below, consumed by Task 3

```
{ period: {start, end, days, annualized} | null, profit_pln, twr: {period_pct, annual_pct}, xirr: {…},
  volatility_pct, sharpe, short_sample, max_drawdown: {pct, peak_date, trough_date, recovered_on} | null,
  current_drawdown_pct, best_day: {date, pct, pln} | null, worst_day, drawdown_series: [{date, pct}],
  monthly: [{year, months[12], year_pct, first_partial_month}], recalculating }
```

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_analytics_api.py`:

```python
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, DailyValuation, User
from app.valuation.service import mark_stale

LoginAs = Callable[[str], dict[str, str]]

FIVE_DAYS = [
    ("2026-01-01", "1000", "1000"), ("2026-01-02", "1100", "0"), ("2026-01-03", "990", "0"),
    ("2026-01-04", "1490", "500"), ("2026-01-05", "1639", "0"),
]


def seed_days(engine: Engine, email: str, rows: list[tuple[str, str, str]], name: str = "Gotówka") -> int:
    """A cash account of `email` with one valuation per (day, value, flow); returns the account id."""
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == email))
        account = Account(user_id=user_id, name=name, kind="cash", currency="PLN")
        db.add(account)
        db.flush()
        db.add_all(
            DailyValuation(user_id=user_id, account_id=account.id, date=dt.date.fromisoformat(day),
                           value_pln=Decimal(value), cost_pln=Decimal(value), net_flow_pln=Decimal(flow))
            for day, value, flow in rows
        )
        db.commit()
        return account.id


@pytest.fixture
def anna(client: TestClient, login_as: LoginAs) -> dict[str, str]:
    return login_as("anna@portfolio.dev")


def test_analytics_of_the_whole_history(client: TestClient, anna: dict, engine: Engine) -> None:
    seed_days(engine, "anna@portfolio.dev", FIVE_DAYS)
    body = client.get("/api/analytics", headers=anna).json()

    assert body["period"] == {"start": "2026-01-01", "end": "2026-01-05", "days": 5, "annualized": False}
    assert body["profit_pln"] == "139.00"
    assert body["twr"] == {"period_pct": "8.90", "annual_pct": None}
    assert body["xirr"]["period_pct"] is not None and body["xirr"]["annual_pct"] is None
    assert (body["volatility_pct"], body["sharpe"], body["short_sample"]) == (None, None, True)
    assert body["max_drawdown"] == {
        "pct": "-10.00", "peak_date": "2026-01-02", "trough_date": "2026-01-03", "recovered_on": None,
    }
    assert body["current_drawdown_pct"] == "-1.00"
    assert body["best_day"] == {"date": "2026-01-02", "pct": "10.00", "pln": "100.00"}
    assert body["worst_day"] == {"date": "2026-01-03", "pct": "-10.00", "pln": "-110.00"}
    assert body["drawdown_series"][2] == {"date": "2026-01-03", "pct": "-10.00"}
    assert body["monthly"] == [
        {"year": 2026, "months": ["8.90"] + [None] * 11, "year_pct": "8.90", "first_partial_month": None},
    ]
    assert body["recalculating"] is False


def test_ytd_starts_from_the_last_value_of_the_previous_year(client: TestClient, anna: dict, engine: Engine) -> None:
    seed_days(engine, "anna@portfolio.dev", [
        ("2025-12-30", "1000", "1000"), ("2025-12-31", "1100", "0"), ("2026-01-02", "1210", "0"),
    ])
    body = client.get("/api/analytics", params={"period": "ytd"}, headers=anna).json()

    assert body["period"] == {"start": "2026-01-01", "end": "2026-01-02", "days": 2, "annualized": False}
    assert (body["profit_pln"], body["twr"]["period_pct"]) == ("110.00", "10.00")
    assert [row["year"] for row in body["monthly"]] == [2026, 2025]
    assert body["monthly"][1]["first_partial_month"] == 12


def test_analytics_of_selected_accounts(client: TestClient, anna: dict, login_as: LoginAs, engine: Engine) -> None:
    first = seed_days(engine, "anna@portfolio.dev", FIVE_DAYS)
    seed_days(engine, "anna@portfolio.dev", [("2026-01-01", "500", "500"), ("2026-01-05", "400", "0")], name="Drugie")
    bartek = login_as("bartek@portfolio.dev")

    own = client.get("/api/analytics", params={"account_id": first}, headers=anna).json()
    foreign = client.get("/api/analytics", params={"account_id": first}, headers=bartek)

    assert own["profit_pln"] == "139.00"
    assert (foreign.status_code, foreign.json()["code"]) == (404, "not_found")
    assert client.get("/api/analytics", headers=anna).json()["profit_pln"] == "39.00"  # 139 − 100


def test_user_without_valuations_gets_an_empty_answer(client: TestClient, anna: dict) -> None:
    body = client.get("/api/analytics", headers=anna).json()

    assert (body["period"], body["profit_pln"], body["twr"], body["max_drawdown"]) == (
        None, "0.00", {"period_pct": None, "annual_pct": None}, None)
    assert (body["drawdown_series"], body["monthly"], body["best_day"]) == ([], [], None)


def test_unknown_period_is_422(client: TestClient, anna: dict) -> None:
    assert client.get("/api/analytics", params={"period": "5y"}, headers=anna).status_code == 422


def test_analytics_says_when_a_recompute_is_pending(client: TestClient, anna: dict, engine: Engine) -> None:
    seed_days(engine, "anna@portfolio.dev", FIVE_DAYS)
    with Session(engine) as db:
        mark_stale(db, [db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))], dt.date(2026, 1, 1))
        db.commit()
    assert client.get("/api/analytics", headers=anna).json()["recalculating"] is True


def test_analytics_needs_a_session(client: TestClient) -> None:
    assert client.get("/api/analytics").status_code == 401
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `docker compose run --rm api pytest tests/test_analytics_api.py -q`
Expected: the tests FAIL with 404 on `/api/analytics`. The 401 test may already pass, because unknown routes are 404 regardless; that is fine.

- [ ] **Step 3: Make `daily_totals` public**

In `api/app/portfolio/service.py`, rename the function `_daily_totals` to `daily_totals` and update both of its callers in `portfolio_summary` and `portfolio_history`. Run `grep -rn "_daily_totals" api/` afterwards; expected: no matches.

- [ ] **Step 4: Write the schemas, service and router**

Create `api/app/analytics/schemas.py`:

```python
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
```

Create `api/app/analytics/service.py`:

```python
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
```

Create `api/app/analytics/router.py`:

```python
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
```

In `api/app/main.py`, add `from app.analytics.router import router as analytics_router` as the first router import (the imports are alphabetical) and `app.include_router(analytics_router)` after `app.include_router(history_router)`.

- [ ] **Step 5: Run the tests to verify they pass**

Run: `docker compose run --rm api pytest tests/test_analytics_api.py tests/test_portfolio_api.py -q`
Expected: all tests PASS. In particular, the portfolio tests still pass after the rename.

- [ ] **Step 6: Run the whole API suite**

Run: `docker compose run --rm api pytest -q`
Expected: all tests PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/analytics api/app/portfolio/service.py api/app/main.py api/tests/test_analytics_api.py
git commit -m "feat(api): GET /api/analytics with returns, risk, drawdown and monthly returns"
```

---

### Task 3: Tooltips for measures (`InfoTip`) and the Pulpit stats

**Files:**
- Create: `web/src/ui/InfoTip.tsx`, `web/src/ui/InfoTip.module.css`, `web/src/ui/help.ts`
- Modify: `web/src/screens/dashboard/DashboardScreen.tsx` (the `<dl className={styles.stats}>` block, about lines 137–142)
- Test: `web/src/ui/InfoTip.test.tsx`

**Interfaces:**
- Produces:
  - `<InfoTip label={string} help={Help} />`: a "?" button labelled `Co to jest: <label>`; when open, a `role="tooltip"` bubble
  - `Help = { what: string; how: string }` and `HELP: Record<string, Help>` in `ui/help.ts`, keyed by the visible measure name

- [ ] **Step 1: Write the failing tests**

Create `web/src/ui/InfoTip.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { InfoTip } from "./InfoTip";

function setup() {
  const user = userEvent.setup();
  render(<div><InfoTip label="XIRR" help={{ what: "Twój osobisty zwrot.", how: "stopa jak w Excelu." }} /><p>obok</p></div>);
  return { user, button: screen.getByRole("button", { name: "Co to jest: XIRR" }) };
}

describe("InfoTip", () => {
  it("opens on hover and closes when the mouse leaves", async () => {
    const { user, button } = setup();

    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
    await user.hover(button);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Twój osobisty zwrot.Jak liczymy: stopa jak w Excelu.");
    expect(button).toHaveAccessibleDescription(/Twój osobisty zwrot\.\s*Jak liczymy: stopa jak w Excelu\./);
    await user.unhover(button);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("toggles on a tap and closes on Escape or a tap elsewhere", async () => {
    const { user, button } = setup();

    await user.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    await user.keyboard("{Escape}");
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await user.click(button);
    await user.click(screen.getByText("obok"));
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();

    await user.click(button);
    await user.click(button);
    expect(screen.queryByRole("tooltip")).not.toBeInTheDocument();
  });

  it("keeps the bubble inside a narrow screen", async () => {
    window.innerWidth = 320;
    const { user, button } = setup();

    await user.click(button);
    const bubble = screen.getByRole("tooltip");
    expect(bubble.style.left).toBe("16px");
    expect(bubble.style.width).toBe("260px");
  });
});
```

Add to the existing Pulpit test file `web/src/screens/dashboard/dashboard.test.tsx` a test that follows the file's own setup for a signed-in Pulpit with `SUMMARY` (copy its route list from the first test there):

```tsx
  it("explains the stats behind their question marks", async () => {
    // same routes as the first test in this file
    const { user } = renderApp("/");

    await user.click(await screen.findByRole("button", { name: "Co to jest: Stopa zwrotu (TWR)" }));
    expect(screen.getByRole("tooltip")).toHaveTextContent("Jak liczymy: zwrot każdego dnia");
    for (const name of ["Zysk łącznie", "Wpłacono", "Dywidendy i odsetki"]) {
      expect(screen.getByRole("button", { name: `Co to jest: ${name}` })).toBeInTheDocument();
    }
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- src/ui/InfoTip src/screens/dashboard` (in `web/`)
Expected: the run FAILS, because `./InfoTip` does not exist and the Pulpit has no "Co to jest" buttons.

- [ ] **Step 3: Write the texts, the component and its style**

Create `web/src/ui/help.ts`:

```ts
/** What each measure means and how it is counted, in plain words; keyed by the name shown on screen (spec 7a §5). */
export interface Help { what: string; how: string }

export const HELP: Record<string, Help> = {
  "Zysk": {
    what: "Ile zarobiłeś w okresie, nie licząc tego, co sam dopłaciłeś.",
    how: "wartość na koniec okresu − wartość na początku − wpłaty netto w okresie.",
  },
  "TWR": {
    what: "Jak radziły sobie same inwestycje, niezależnie od terminów wpłat; tę miarę porównuje się z funduszami.",
    how: "zwrot każdego dnia liczony bez wpływu wpłat (wpłata liczy się na początku dnia), a zwroty dni mnożone przez siebie; od roku wzwyż przeliczony na rok.",
  },
  "XIRR": {
    what: "Twój osobisty zwrot z uwzględnieniem tego, kiedy i ile wpłacałeś; jak oprocentowanie lokaty o tym samym wyniku.",
    how: "stopa, przy której Twoje wpłaty, wypłaty i dzisiejsza wartość się równoważą (jak XIRR w Excelu); dla okresu krótszego niż rok przeliczona na okres.",
  },
  "Maks. obsunięcie": {
    what: "Największy spadek od szczytu do dołka w okresie.",
    how: "z dziennych zwrotów (TWR), więc wpłaty nie zasłaniają spadków: najniższy poziom względem najwyższego wcześniejszego.",
  },
  "Obecne obsunięcie": {
    what: "Ile dziś brakuje do najwyższego poziomu.",
    how: "dzisiejszy poziom TWR względem najwyższego w okresie.",
  },
  "Zmienność": {
    what: "Jak mocno wartość skacze; 15 % znaczy, że typowy rok mieści się mniej więcej w ±15 %.",
    how: "odchylenie standardowe dziennych zwrotów × √365; potrzeba co najmniej 30 dni.",
  },
  "Sharpe": {
    what: "Ile zysku przypada na jednostkę ryzyka ponad bezpieczną lokatę; powyżej 1 dobrze, poniżej 0 lokata wypadła lepiej.",
    how: "(średni dzienny zwrot − dzienna stopa referencyjna NBP) ÷ odchylenie dziennych zwrotów × √365; potrzeba co najmniej 30 dni.",
  },
  "Najlepszy dzień": {
    what: "Największy dzienny wzrost w okresie.",
    how: "dzień z najwyższym zwrotem; kwota to zmiana wartości tego dnia bez wpłat i wypłat.",
  },
  "Najgorszy dzień": {
    what: "Największy dzienny spadek w okresie.",
    how: "dzień z najniższym zwrotem; kwota to zmiana wartości tego dnia bez wpłat i wypłat.",
  },
  "Obsunięcie w czasie": {
    what: "Jak głęboko i jak długo portfel był poniżej swojego najwyższego poziomu; 0 % to nowy rekord.",
    how: "każdego dnia poziom TWR względem najwyższego wcześniejszego w okresie.",
  },
  "Zwrot w miesiącach": {
    what: "Zwrot w każdym miesiącu i roku, za całą historię, niezależnie od wybranego okresu.",
    how: "dzienne zwroty TWR mnożone w obrębie miesiąca; rok to iloczyn jego miesięcy.",
  },
  "Zysk łącznie": {
    what: "Ile zarobiłeś od początku.",
    how: "dzisiejsza wartość do wypłaty − wpłaty netto (wpłaty minus wypłaty).",
  },
  "Stopa zwrotu (TWR)": {
    what: "Jak radziły sobie same inwestycje od początku, niezależnie od terminów wpłat.",
    how: "zwrot każdego dnia liczony bez wpływu wpłat, a zwroty dni od pierwszego dnia historii mnożone przez siebie.",
  },
  "Wpłacono": {
    what: "Ile pieniędzy włożyłeś w portfel.",
    how: "suma wpłat na wybrane konta minus wypłaty, w złotych.",
  },
  "Dywidendy i odsetki": {
    what: "Dochód, który wpłynął na konta.",
    how: "dywidendy i odsetki po pobranym podatku, w złotych po kursie NBP z dnia wpływu.",
  },
};
```

Create `web/src/ui/InfoTip.module.css`:

```css
.wrap { display: inline-flex; vertical-align: middle; margin-left: 6px; }
.button { width: 22px; height: 22px; padding: 0; border-radius: 50%; border: 1px solid var(--rule); background: none; color: var(--dim); font-size: 11px; line-height: 1; cursor: help; }
.button[aria-expanded="true"] { color: var(--amber); border-color: var(--amber); }
.bubble { position: fixed; z-index: 30; background: var(--slab); color: var(--ink); border: 1px solid var(--rule); border-radius: var(--r-control); padding: 8px 10px; font-size: 12px; font-weight: 400; line-height: 1.4; text-align: left; box-shadow: 0 8px 24px rgba(0, 0, 0, .45); }
.how { display: block; margin-top: 6px; color: var(--dim); }
```

Create `web/src/ui/InfoTip.tsx`:

```tsx
import { useEffect, useId, useRef, useState, type CSSProperties } from "react";
import type { Help } from "./help";
import styles from "./InfoTip.module.css";

const WIDTH = 260;
const GUTTER = 16;

/** A "?" that explains a measure. A mouse opens it by hovering; a tap (or Enter/Space) pins it open until a second
 * tap, Esc, a tap elsewhere or scrolling. The bubble is fixed to the viewport and stays 16 px inside its edges. */
export function InfoTip({ label, help }: { label: string; help: Help }) {
  const id = useId();
  const button = useRef<HTMLButtonElement>(null);
  const [pinned, setPinned] = useState(false);
  const [hovered, setHovered] = useState(false);
  const [place, setPlace] = useState<CSSProperties>({});
  const open = pinned || hovered;

  useEffect(() => {
    if (!open || !button.current) return;
    const rect = button.current.getBoundingClientRect();
    const width = Math.min(WIDTH, window.innerWidth - 2 * GUTTER);
    const left = Math.min(Math.max(rect.right - width, GUTTER), window.innerWidth - GUTTER - width);
    setPlace({ top: rect.bottom + 6, left, width });
    const close = () => { setPinned(false); setHovered(false); };
    const onKey = (event: KeyboardEvent) => { if (event.key === "Escape") close(); };
    const onDown = (event: PointerEvent) => { if (!button.current?.contains(event.target as Node)) close(); };
    window.addEventListener("keydown", onKey);
    window.addEventListener("pointerdown", onDown);
    window.addEventListener("scroll", close, true);
    return () => {
      window.removeEventListener("keydown", onKey);
      window.removeEventListener("pointerdown", onDown);
      window.removeEventListener("scroll", close, true);
    };
  }, [open]);

  return (
    <span className={styles.wrap}>
      <button ref={button} type="button" className={styles.button} aria-label={`Co to jest: ${label}`}
        aria-expanded={open} aria-describedby={open ? id : undefined}
        onClick={() => { setPinned(!pinned); setHovered(false); }}
        onPointerEnter={(event) => { if (event.pointerType === "mouse") setHovered(true); }}
        onPointerLeave={(event) => { if (event.pointerType === "mouse") setHovered(false); }}>
        ?
      </button>
      {open && (
        <span role="tooltip" id={id} className={styles.bubble} style={place}>
          {help.what}
          <span className={styles.how}>Jak liczymy: {help.how}</span>
        </span>
      )}
    </span>
  );
}
```

A click on a hovered tip pins it (`pinned` becomes true). A second click unpins it. Leaving with the mouse while it is pinned keeps it open. If the "tap elsewhere" test fails because `user.click` sends no `pointerdown` in this jsdom, use `user.pointer({ keys: "[MouseLeft]", target: screen.getByText("obok") })` in the test instead.

- [ ] **Step 4: Add the tips to the Pulpit stats**

In `DashboardScreen.tsx`, import `InfoTip` from `../../ui/InfoTip` and `HELP` from `../../ui/help`. Inside each `<dt>` of the `styles.stats` list, keep the label in a `<span>` (so tests that look up the label text still find it) followed by the tip, e.g.:

```tsx
          <div><dt><span>Zysk łącznie</span><InfoTip label="Zysk łącznie" help={HELP["Zysk łącznie"]!} /></dt><dd><Money value={data.total_gain_pln} sign tone /></dd></div>
```

Do the same for `Stopa zwrotu (TWR)`, `Wpłacono` and `Dywidendy i odsetki`. Leave the `<dd>` elements unchanged.

- [ ] **Step 5: Run the tests and the type check**

Run: `npm test` and `npx tsc -b` (in `web/`)
Expected: all tests PASS, including every existing Pulpit test, and there are no type errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/ui/InfoTip.tsx web/src/ui/InfoTip.module.css web/src/ui/help.ts web/src/ui/InfoTip.test.tsx web/src/screens/dashboard
git commit -m "feat(web): question-mark tooltips that explain measures, on the Pulpit stats first"
```

---

### Task 4: API client and the Analiza screen with its tiles

**Files:**
- Modify: `web/src/api/types.ts`, `web/src/api/endpoints.ts`, `web/src/api/queryKeys.ts`, `web/src/routes.tsx`, `web/src/test/fixtures.ts`
- Create: `web/src/screens/analysis/model.ts`, `web/src/screens/analysis/AnalysisScreen.tsx`, `web/src/screens/analysis/Analysis.module.css`
- Test: `web/src/screens/analysis/analysis.test.tsx`

**Interfaces:**
- Consumes: `GET /api/analytics` (Task 2); `InfoTip` and `HELP` (Task 3); `useAccountSelection`, `AccountSelect`, `Segmented`, `BackLink`, `Money`, the `States` components and `RECALC_POLL_MS`.
- Produces:
  - Types `Analytics`, `AnalyticsPeriod`, `PeriodReturn`, `MonthReturns`
  - `api.analytics(ids, period)` and `keys.analytics(ids, period)`
  - From `model.ts`: `PERIODS`, `MONTHS`, `shownReturn` and `cellBackground`
  - The fixtures `ANALYTICS` and `ANALYTICS_EMPTY`
  - The screen leaves a slot that Task 5 fills: the comment `{/* Task 5: drawdown chart and monthly returns */}`

- [ ] **Step 1: Add the types, endpoint, key and fixtures**

Append to `web/src/api/types.ts`:

```ts
export type AnalyticsPeriod = "1m" | "3m" | "1y" | "ytd" | "all";
export interface PeriodReturn { period_pct: Money | null; annual_pct: Money | null }
export interface DayExtreme { date: IsoDate; pct: Money; pln: Money }
export interface MonthReturns { year: number; months: (Money | null)[]; year_pct: Money | null; first_partial_month: number | null }
export interface Analytics {
  period: { start: IsoDate; end: IsoDate; days: number; annualized: boolean } | null;
  profit_pln: Money;
  twr: PeriodReturn;
  xirr: PeriodReturn;
  volatility_pct: Money | null;
  sharpe: Money | null;
  short_sample: boolean;
  max_drawdown: { pct: Money; peak_date: IsoDate; trough_date: IsoDate; recovered_on: IsoDate | null } | null;
  current_drawdown_pct: Money | null;
  best_day: DayExtreme | null;
  worst_day: DayExtreme | null;
  drawdown_series: { date: IsoDate; pct: Money }[];
  monthly: MonthReturns[];
  recalculating: boolean;
}
```

In `web/src/api/endpoints.ts`, add `Analytics, AnalyticsPeriod` to the type import, and add after `limits`:

```ts
  analytics: (ids: readonly number[], period: AnalyticsPeriod) =>
    request<Analytics>("/api/analytics", { query: { account_id: ids, period } }),
```

In `web/src/api/queryKeys.ts`, add after `limits`:

```ts
  analytics: (ids: readonly number[], period: string) => ["portfolio", "analytics", ids, period] as const,
```

Append to `web/src/test/fixtures.ts`, and add `Analytics` to its type import:

```ts
export const ANALYTICS: Analytics = {
  period: { start: "2026-03-01", end: "2026-09-26", days: 210, annualized: false },
  profit_pln: "804.20",
  twr: { period_pct: "8.04", annual_pct: null },
  xirr: { period_pct: "6.40", annual_pct: null },
  volatility_pct: "14.80",
  sharpe: "0.62",
  short_sample: true,
  max_drawdown: { pct: "-8.20", peak_date: "2026-08-12", trough_date: "2026-08-22", recovered_on: "2026-09-18" },
  current_drawdown_pct: "-1.30",
  best_day: { date: "2026-08-05", pct: "2.90", pln: "48.00" },
  worst_day: { date: "2026-08-14", pct: "-3.40", pln: "-57.00" },
  drawdown_series: [
    { date: "2026-08-12", pct: "0.00" }, { date: "2026-08-22", pct: "-8.20" }, { date: "2026-09-18", pct: "0.00" },
    { date: "2026-09-26", pct: "-1.30" },
  ],
  monthly: [{
    year: 2026,
    months: [null, null, "1.20", "0.50", "-0.70", "2.00", "3.10", "-3.00", "3.80", null, null, null],
    year_pct: "5.10", first_partial_month: null,
  }],
  recalculating: false,
};

export const ANALYTICS_EMPTY: Analytics = {
  period: null, profit_pln: "0.00", twr: { period_pct: null, annual_pct: null }, xirr: { period_pct: null, annual_pct: null },
  volatility_pct: null, sharpe: null, short_sample: false, max_drawdown: null, current_drawdown_pct: null,
  best_day: null, worst_day: null, drawdown_series: [], monthly: [], recalculating: false,
};
```

- [ ] **Step 2: Write the failing tests**

Create `web/src/screens/analysis/analysis.test.tsx`:

```tsx
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, ANALYTICS, ANALYTICS_EMPTY } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";
import { formatPercent } from "../../format";
import { cellBackground, shownReturn } from "./model";

function routes(answer: (url: URL) => unknown) {
  return mockFetch([
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/analytics", respond: answer },
  ]);
}

const tile = (name: string) => screen.getByRole("group", { name });

describe("Analiza", () => {
  it("shows every measure with its caption", async () => {
    routes(() => ANALYTICS);
    renderApp("/analiza");

    expect(await screen.findByRole("heading", { name: "Analiza" })).toBeInTheDocument();
    expect(within(await screen.findByRole("group", { name: "Zysk" })).getByText("+804,20 zł")).toBeInTheDocument();
    expect(within(tile("TWR")).getByText("+8,0 %")).toBeInTheDocument();
    expect(within(tile("TWR")).getByText("za okres")).toBeInTheDocument();
    expect(within(tile("XIRR")).getByText("+6,4 %")).toBeInTheDocument();
    expect(within(tile("Maks. obsunięcie")).getByText("−8,2 %")).toBeInTheDocument();
    expect(within(tile("Maks. obsunięcie")).getByText("12.08.2026 → 22.08.2026 · odrobione 18.09.2026")).toBeInTheDocument();
    expect(within(tile("Obecne obsunięcie")).getByText("−1,3 %")).toBeInTheDocument();
    expect(within(tile("Zmienność")).getByText("14,8 %")).toBeInTheDocument();
    expect(within(tile("Zmienność")).getByText("rocznie · orientacyjnie")).toBeInTheDocument();
    expect(within(tile("Sharpe")).getByText("0,62")).toBeInTheDocument();
    expect(within(tile("Najlepszy dzień")).getByText("+2,9 %")).toBeInTheDocument();
    expect(within(tile("Najlepszy dzień")).getByText("+48,00 zł · 05.08.2026")).toBeInTheDocument();
    expect(within(tile("Najgorszy dzień")).getByText("−3,4 %")).toBeInTheDocument();
  });

  it("explains a measure behind its question mark", async () => {
    routes(() => ANALYTICS);
    const { user } = renderApp("/analiza");

    const help = await screen.findByRole("button", { name: "Co to jest: XIRR" });
    await user.hover(help);
    expect(screen.getByRole("tooltip")).toHaveTextContent("Twój osobisty zwrot");
    expect(screen.getByRole("tooltip")).toHaveTextContent("Jak liczymy: stopa, przy której");
    await user.unhover(help);
    for (const name of ["Zysk", "TWR", "Maks. obsunięcie", "Obecne obsunięcie", "Zmienność", "Sharpe", "Najlepszy dzień", "Najgorszy dzień"]) {
      expect(screen.getByRole("button", { name: `Co to jest: ${name}` })).toBeInTheDocument();
    }
  });

  it("asks for the chosen period", async () => {
    const fetchMock = routes(() => ANALYTICS);
    const { user } = renderApp("/analiza");

    await screen.findByRole("group", { name: "Zysk" });
    expect(screen.getByRole("button", { name: "Wszystko" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "Od pocz. roku" }));
    expect(fetchMock.mock.calls.map(([url]) => String(url)).some((u) => u.includes("period=ytd"))).toBe(true);
  });

  it("shows annual returns for a period of a year or more", async () => {
    routes(() => ({
      ...ANALYTICS,
      period: { ...ANALYTICS.period!, days: 365, annualized: true },
      twr: { period_pct: "9.70", annual_pct: "9.70" },
      short_sample: false,
    }));
    renderApp("/analiza");

    expect(within(await screen.findByRole("group", { name: "TWR" })).getByText("rocznie · za okres +9,7 %")).toBeInTheDocument();
    expect(within(tile("Zmienność")).getByText("rocznie")).toBeInTheDocument();
  });

  it("says when there is too little data for the risk measures", async () => {
    routes(() => ({ ...ANALYTICS, volatility_pct: null, sharpe: null }));
    renderApp("/analiza");

    expect(within(await screen.findByRole("group", { name: "Zmienność" })).getByText("za mało danych")).toBeInTheDocument();
    expect(within(tile("Sharpe")).getByText("za mało danych")).toBeInTheDocument();
  });

  it("shows a portfolio without a fall", async () => {
    routes(() => ({
      ...ANALYTICS,
      max_drawdown: { pct: "0.00", peak_date: "2026-09-26", trough_date: "2026-09-26", recovered_on: null },
      current_drawdown_pct: "0.00",
    }));
    renderApp("/analiza");

    expect(within(await screen.findByRole("group", { name: "Maks. obsunięcie" })).getByText("bez spadku od rekordu")).toBeInTheDocument();
  });

  it("shows an empty state without valuations", async () => {
    routes(() => ANALYTICS_EMPTY);
    renderApp("/analiza");

    expect(await screen.findByText("Nie ma jeszcze wyceny do pokazania.")).toBeInTheDocument();
  });

  it("shows an error with a retry", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/analytics", status: 500, respond: () => ({ code: "server_error", message: "x", details: {} }) }]);
    renderApp("/analiza");

    expect(await screen.findByRole("button", { name: "Spróbuj ponownie" })).toBeInTheDocument();
  });
});

describe("analysis model", () => {
  it("picks the period or the annual return", () => {
    expect(shownReturn({ period_pct: "5.00", annual_pct: null }, false)).toEqual({ value: "5.00", caption: "za okres" });
    expect(shownReturn({ period_pct: "12.00", annual_pct: "10.00" }, true))
      .toEqual({ value: "10.00", caption: `rocznie · za okres ${formatPercent("12.00", { places: 1 })}` });
  });

  it("colours a month by its return, saturated at ±5 %", () => {
    expect(cellBackground(null)).toBe("transparent");
    expect(cellBackground("0.00")).toBe("transparent");
    expect(cellBackground("2.50")).toBe("rgba(93, 185, 138, 0.28)");
    expect(cellBackground("-9.00")).toBe("rgba(224, 103, 110, 0.55)");
  });
});
```

Before relying on the error-state test, check `web/src/ui/States.tsx` `ErrorState` for the retry button's exact name, and use that name in the test.

- [ ] **Step 3: Run the tests to verify they fail**

Run: `npm test -- src/screens/analysis` (in `web/`)
Expected: the run FAILS, because `./model` does not exist and `/analiza` redirects to `/`.

- [ ] **Step 4: Write the model**

Create `web/src/screens/analysis/model.ts`:

```ts
import type { AnalyticsPeriod, Money, PeriodReturn } from "../../api/types";
import { formatPercent } from "../../format";

export const PERIODS: { value: AnalyticsPeriod; label: string }[] = [
  { value: "1m", label: "1M" }, { value: "3m", label: "3M" }, { value: "1y", label: "1R" },
  { value: "ytd", label: "Od pocz. roku" }, { value: "all", label: "Wszystko" },
];

export const MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];

/** Returns are for the period below a year and annual from a year on (owner's decision 7a). */
export function shownReturn(value: PeriodReturn, annualized: boolean): { value: Money | null; caption: string } {
  if (!annualized) return { value: value.period_pct, caption: "za okres" };
  return { value: value.annual_pct, caption: `rocznie · za okres ${formatPercent(value.period_pct, { places: 1 })}` };
}

const SATURATION_PCT = 5;
const MAX_ALPHA = 0.55;

/** Green or red behind a month, stronger with the size of the return, full at ±5 %. */
export function cellBackground(pct: Money | null): string {
  const value = pct === null ? 0 : Number(pct);
  if (value === 0) return "transparent";
  const alpha = Math.round(Math.min(Math.abs(value) / SATURATION_PCT, 1) * MAX_ALPHA * 100) / 100;
  return value > 0 ? `rgba(93, 185, 138, ${alpha})` : `rgba(224, 103, 110, ${alpha})`;
}
```

For 2.50, alpha = 0.5 × 0.55 = 0.275, which rounds to 0.28. The colours are the `--gain` and `--loss` tokens.

- [ ] **Step 5: Write the screen**

Create `web/src/screens/analysis/Analysis.module.css`:

```css
.tiles { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 8px; }
@media (min-width: 900px) { .tiles { grid-template-columns: repeat(4, minmax(0, 1fr)); } }
.tile { background: var(--slab); border: 1px solid var(--rule); border-radius: var(--r-sheet); padding: 12px; display: grid; gap: 2px; align-content: start; }
.tileHead { display: flex; justify-content: space-between; align-items: center; color: var(--dim); font-size: 12px; }
.value { font-size: 20px; font-weight: 600; font-variant-numeric: tabular-nums; }
.caption { color: var(--dim); font-size: 11px; }
```

Create `web/src/screens/analysis/AnalysisScreen.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useState, type ReactNode } from "react";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Analytics, AnalyticsPeriod, DayExtreme } from "../../api/types";
import { formatDate, formatDecimal, formatMoney, formatPercent, signOf } from "../../format";
import { AccountSelect } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { BackLink } from "../../ui/BackLink";
import { Segmented } from "../../ui/Segmented";
import { HELP } from "../../ui/help";
import { InfoTip } from "../../ui/InfoTip";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { RECALC_POLL_MS } from "../dashboard/model";
import styles from "./Analysis.module.css";
import { PERIODS, shownReturn } from "./model";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");
const TOO_LITTLE = "za mało danych";

function Tile({ title, value, caption }: { title: string; value: ReactNode; caption: string }) {
  return (
    <div className={styles.tile} role="group" aria-label={title}>
      <div className={styles.tileHead}>
        <span>{title}</span>
        <InfoTip label={title} help={HELP[title]!} />
      </div>
      <div className={styles.value}>{value}</div>
      <div className={styles.caption}>{caption}</div>
    </div>
  );
}

const percent = (value: string | null, sign = true) => (
  <span className={`num ${sign ? tone(value) : ""}`}>{formatPercent(value, { places: 1, sign })}</span>
);

function dayCaption(day: DayExtreme | null): string {
  return day ? `${formatMoney(day.pln, { sign: true })} · ${formatDate(day.date)}` : TOO_LITTLE;
}

function drawdownCaption(data: Analytics): string {
  const fall = data.max_drawdown;
  if (!fall) return TOO_LITTLE;
  if (signOf(fall.pct) === 0) return "bez spadku od rekordu";
  const back = fall.recovered_on ? `odrobione ${formatDate(fall.recovered_on)}` : "nieodrobione";
  return `${formatDate(fall.peak_date)} → ${formatDate(fall.trough_date)} · ${back}`;
}

function Tiles({ data }: { data: Analytics }) {
  const annualized = data.period!.annualized;
  const twr = shownReturn(data.twr, annualized);
  const xirr = shownReturn(data.xirr, annualized);
  const risk = data.short_sample ? "rocznie · orientacyjnie" : "rocznie";
  return (
    <div className={styles.tiles}>
      <Tile title="Zysk" value={<Money value={data.profit_pln} sign tone />} caption="za okres" />
      <Tile title="TWR" value={percent(twr.value)} caption={twr.caption} />
      <Tile title="XIRR" value={percent(xirr.value)} caption={xirr.caption} />
      <Tile title="Maks. obsunięcie" value={percent(data.max_drawdown?.pct ?? null)} caption={drawdownCaption(data)} />
      <Tile title="Obecne obsunięcie" value={percent(data.current_drawdown_pct)} caption="od najwyższego poziomu" />
      <Tile title="Zmienność" value={percent(data.volatility_pct, false)} caption={data.volatility_pct === null ? TOO_LITTLE : risk} />
      <Tile title="Sharpe" value={<span className="num">{data.sharpe === null ? "—" : formatDecimal(data.sharpe, 2)}</span>}
        caption={data.sharpe === null ? TOO_LITTLE : risk} />
      <Tile title="Najlepszy dzień" value={percent(data.best_day?.pct ?? null)} caption={dayCaption(data.best_day)} />
      <Tile title="Najgorszy dzień" value={percent(data.worst_day?.pct ?? null)} caption={dayCaption(data.worst_day)} />
    </div>
  );
}

export function AnalysisScreen() {
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  const [period, setPeriod] = useState<AnalyticsPeriod>("all");
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const analytics = useQuery({
    queryKey: keys.analytics(accountIds, period),
    queryFn: () => api.analytics(accountIds, period),
    enabled: ready,
    placeholderData: (previous) => previous,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });

  return (
    <div className={ui.page}>
      <BackLink to="/" label="Pulpit" />
      <h1 className={ui.pageTitle}>Analiza</h1>
      {accounts.data && <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />}
      <Segmented label="Okres" options={PERIODS} value={period} onChange={setPeriod} />
      {analytics.isPending ? <Skeleton rows={4} />
        : analytics.isError ? <ErrorState error={analytics.error} onRetry={() => void analytics.refetch()} />
        : analytics.data.period === null ? <EmptyState title="Nie ma jeszcze wyceny do pokazania." />
        : (
          <>
            {analytics.data.recalculating && <Recalculating />}
            <Tiles data={analytics.data} />
            {/* Task 5: drawdown chart and monthly returns */}
          </>
        )}
    </div>
  );
}
```

In `web/src/routes.tsx`, import `AnalysisScreen` and add `{ path: "/analiza", element: <AnalysisScreen /> },` after the `/limity` route.

Before running, check that `useAccountSelection` returns `[ids, set, ready]` exactly as `ExposureScreen` uses it, and that `signOf` and `formatMoney` are exported from `../../format`. Both are, according to `format/index.ts`.

- [ ] **Step 6: Run the tests and the type check**

Run: `npm test -- src/screens/analysis` and then `npx tsc -b` (in `web/`)
Expected: all tests PASS and tsc reports no errors. If a formatted string differs only in the spacing character (`formatPercent` uses NBSP before `%`), match it with a regex in the test, e.g. `getByText(/^\+8,0\s%$/)`, rather than changing the formatter.

- [ ] **Step 7: Commit**

```bash
git add web/src/api web/src/routes.tsx web/src/test/fixtures.ts web/src/screens/analysis
git commit -m "feat(web): Analiza screen with period, accounts and measure tiles"
```

---

### Task 5: Drawdown chart and monthly returns

**Files:**
- Create: `web/src/charts/DrawdownChart.tsx`, `web/src/charts/DrawdownChart.module.css`
- Create: `web/src/screens/analysis/MonthlyReturns.tsx`
- Modify: `web/src/screens/analysis/AnalysisScreen.tsx` (replace the Task 5 comment), `web/src/screens/analysis/Analysis.module.css`
- Test: `web/src/screens/analysis/analysis.test.tsx` (add cases)

**Interfaces:**
- Consumes: `InfoTip` and `HELP` (Task 3); `Analytics["drawdown_series"]` and `MonthReturns[]` (Task 4); `timeTicks(points, view, plotWidth)` from `charts/timeTicks`; `fullWindow(count)` from `charts/viewport`; `ChartPoint` from `charts/geometry`; `MONTHS` and `cellBackground` (Task 4).
- Produces: `<DrawdownChart points={…} />` and `<MonthlyReturns rows={…} />`.

- [ ] **Step 1: Write the failing tests**

Append inside `describe("Analiza", …)` in `analysis.test.tsx`:

```tsx
  it("draws the drawdown over time", async () => {
    routes(() => ANALYTICS);
    renderApp("/analiza");

    expect(await screen.findByRole("img", { name: /^Obsunięcie w czasie, najgłębiej −8,2\s%$/ })).toBeInTheDocument();
  });

  it("lists monthly returns per year without a second copy", async () => {
    routes(() => ANALYTICS);
    renderApp("/analiza");

    const year = await screen.findByRole("group", { name: "Rok 2026" });
    expect(within(year).getByText("+5,1 %")).toBeInTheDocument();
    expect(within(year).getByRole("listitem", { name: "sie 2026" })).toHaveTextContent("−3,0 %");
    expect(within(year).getByRole("listitem", { name: "sty 2026" })).toHaveTextContent("–");
    expect(within(year).getAllByRole("listitem")).toHaveLength(12);
    expect(screen.getAllByRole("group", { name: /^Rok / })).toHaveLength(1);
    expect(screen.getByRole("button", { name: "Co to jest: Zwrot w miesiącach" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Co to jest: Obsunięcie w czasie" })).toBeInTheDocument();
  });

  it("marks the partial first month", async () => {
    routes(() => ({ ...ANALYTICS, monthly: [{ ...ANALYTICS.monthly[0]!, first_partial_month: 3 }] }));
    renderApp("/analiza");

    const march = await screen.findByRole("listitem", { name: "mar 2026, niepełny miesiąc" });
    expect(march).toHaveTextContent("+1,2 %");
  });
```

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- src/screens/analysis`
Expected: the 3 new tests FAIL (no img, and no group "Rok 2026").

- [ ] **Step 3: Write the drawdown chart**

Create `web/src/charts/DrawdownChart.module.css`:

```css
.chart { margin: 0; }
.chart svg { width: 100%; height: auto; display: block; }
.grid { stroke: var(--rule); }
.area { fill: var(--loss-soft); }
.line { fill: none; stroke: var(--loss); stroke-width: 1.5; vector-effect: non-scaling-stroke; }
.label { fill: var(--dim); font-size: 11px; }
.note { color: var(--dim); font-size: 13px; }
```

Create `web/src/charts/DrawdownChart.tsx`:

```tsx
import { formatPercent } from "../format";
import type { ChartPoint } from "./geometry";
import styles from "./DrawdownChart.module.css";
import { timeTicks } from "./timeTicks";
import { fullWindow } from "./viewport";

const W = 350;
const H = 150;
const LEFT = 44;
const TOP = 8;
const BOTTOM = 22;
const PLOT_W = W - LEFT;
const PLOT_H = H - TOP - BOTTOM;

/** The fall below the running record on each day of the period (0 at a record, negative below it). */
export function DrawdownChart({ points }: { points: { date: string; pct: string }[] }) {
  if (points.length < 2) return <p className={styles.note}>Wykres pojawi się, gdy okres obejmie co najmniej dwa dni.</p>;
  const values = points.map((p) => Number(p.pct));
  const deepest = Math.min(...values);
  const floor = Math.min(deepest, -1);
  const x = (i: number) => LEFT + (i / (points.length - 1)) * PLOT_W;
  const y = (v: number) => TOP + (v / floor) * PLOT_H;
  const line = values.map((v, i) => `${i ? "L" : "M"}${x(i).toFixed(1)} ${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(points.length - 1).toFixed(1)} ${TOP} L${LEFT} ${TOP} Z`;
  const chartPoints: ChartPoint[] = points.map((p, i) => ({ date: p.date, value: values[i]!, invested: 0, flow: 0 }));
  const ticks = timeTicks(chartPoints, fullWindow(points.length), PLOT_W);
  const lowest = formatPercent(floor.toFixed(2), { places: 1 });

  return (
    <figure className={styles.chart}>
      <svg viewBox={`0 0 ${W} ${H}`} role="img"
        aria-label={`Obsunięcie w czasie, najgłębiej ${formatPercent(deepest.toFixed(2), { places: 1 })}`}>
        <line className={styles.grid} x1={LEFT} x2={W} y1={TOP} y2={TOP} />
        <line className={styles.grid} x1={LEFT} x2={W} y1={TOP + PLOT_H} y2={TOP + PLOT_H} strokeDasharray="2 3" />
        <text className={styles.label} x={0} y={TOP + 4}>0 %</text>
        <text className={styles.label} x={0} y={TOP + PLOT_H + 4}>{lowest}</text>
        <path className={styles.area} d={area} />
        <path className={styles.line} d={line} />
        {ticks.map((tick) => (
          <text key={tick.index} className={styles.label} x={x(tick.index)} y={H - 4} textAnchor="middle">{tick.label}</text>
        ))}
      </svg>
    </figure>
  );
}
```

- [ ] **Step 4: Write the monthly returns**

Append to `web/src/screens/analysis/Analysis.module.css`:

```css
/* One DOM for both layouts: phone = a card per year with 4 × 3 months; desktop = one row per year. */
.years { display: grid; gap: 8px; }
.year { background: var(--slab); border: 1px solid var(--rule); border-radius: var(--r-sheet); padding: 12px; display: grid; gap: 8px; }
.yearHead { display: flex; justify-content: space-between; font-weight: 600; }
.months { list-style: none; margin: 0; padding: 0; display: grid; grid-template-columns: repeat(4, minmax(0, 1fr)); gap: 4px; }
.month { border: 1px solid var(--rule); border-radius: 8px; padding: 6px; font-size: 13px; font-weight: 600; font-variant-numeric: tabular-nums; min-width: 0; }
.month span { display: block; color: var(--dim); font-size: 11px; font-weight: 400; }
.partial { border-style: dashed; border-color: var(--dim); }
.legend { color: var(--dim); font-size: 11px; }
@media (min-width: 900px) {
  .year { grid-template-columns: 56px minmax(0, 1fr); align-items: center; padding: 8px 12px; }
  .yearHead { display: grid; gap: 2px; }
  .months { grid-template-columns: repeat(12, minmax(0, 1fr)); }
  .month { padding: 4px; font-size: 12px; text-align: right; }
}
```

Create `web/src/screens/analysis/MonthlyReturns.tsx`:

```tsx
import type { MonthReturns } from "../../api/types";
import { formatPercent, signOf } from "../../format";
import styles from "./Analysis.module.css";
import { MONTHS, cellBackground } from "./model";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

/** Monthly TWR for the whole history, newest year first; never scrolls sideways. */
export function MonthlyReturns({ rows }: { rows: MonthReturns[] }) {
  const partial = rows.some((row) => row.first_partial_month !== null);
  return (
    <div className={styles.years}>
      {rows.map((row) => (
        <div key={row.year} className={styles.year} role="group" aria-label={`Rok ${row.year}`}>
          <div className={styles.yearHead}>
            <span>{row.year}</span>
            <span className={`num ${tone(row.year_pct)}`}>{formatPercent(row.year_pct, { places: 1 })}</span>
          </div>
          <ul className={styles.months}>
            {row.months.map((pct, i) => {
              const isPartial = row.first_partial_month === i + 1;
              return (
                <li key={MONTHS[i]} className={`${styles.month} ${isPartial ? styles.partial : ""}`}
                  style={{ background: cellBackground(pct) }}
                  aria-label={`${MONTHS[i]} ${row.year}${isPartial ? ", niepełny miesiąc" : ""}`}>
                  <span>{MONTHS[i]}</span>
                  {pct === null ? "–" : formatPercent(pct, { places: 1 })}
                </li>
              );
            })}
          </ul>
        </div>
      ))}
      {partial && <p className={styles.legend}>Przerywana ramka to niepełny miesiąc na początku historii.</p>}
    </div>
  );
}
```

In `AnalysisScreen.tsx`, import `DrawdownChart` from `../../charts/DrawdownChart` and `MonthlyReturns` from `./MonthlyReturns`, and replace `{/* Task 5: drawdown chart and monthly returns */}` with:

```tsx
            <section className={ui.section} aria-labelledby="drawdown-title">
              <h2 id="drawdown-title" className={ui.sectionTitle}>
                Obsunięcie w czasie<InfoTip label="Obsunięcie w czasie" help={HELP["Obsunięcie w czasie"]!} />
              </h2>
              <DrawdownChart points={analytics.data.drawdown_series} />
            </section>
            <section className={ui.section} aria-labelledby="monthly-title">
              <h2 id="monthly-title" className={ui.sectionTitle}>
                Zwrot w miesiącach<InfoTip label="Zwrot w miesiącach" help={HELP["Zwrot w miesiącach"]!} />
              </h2>
              <MonthlyReturns rows={analytics.data.monthly} />
            </section>
```

- [ ] **Step 5: Run the tests and the type check**

Run: `npm test -- src/screens/analysis` and `npx tsc -b`
Expected: all tests PASS and there are no type errors.

- [ ] **Step 6: Look at it at 320 px and 1280 px**

With `docker compose up -d db api worker` and `npm run dev`, open http://localhost:5173/analiza. Run this in the DevTools console, at 320 px width and at 1280 px width: `document.documentElement.scrollWidth <= window.innerWidth`.
Expected: `true` both times, with no sideways scroll. Do not use DevTools device-mode zoom for this check.

- [ ] **Step 7: Commit**

```bash
git add web/src/charts/DrawdownChart.tsx web/src/charts/DrawdownChart.module.css web/src/screens/analysis
git commit -m "feat(web): drawdown chart and monthly returns grid on the Analiza screen"
```

---

### Task 6: Pulpit card, e2e and roadmap

**Files:**
- Create: `web/src/screens/analysis/AnalyticsCard.tsx`
- Modify: `web/src/screens/dashboard/DashboardScreen.tsx` (render the card before `<LimitsCard />`)
- Test: `web/src/screens/analysis/analysis.test.tsx` (add cases), `web/e2e/app.spec.ts`
- Modify: `docs/superpowers/plans/2026-09-26-00-roadmap.md`

**Interfaces:**
- Consumes: `api.analytics`, `keys.analytics`, `useAccountSelection` (Task 4); `InfoTip` and `HELP` (Task 3).
- Produces: `<AnalyticsCard />`, which hides itself when there is no data or the request fails, like `LimitsCard`. Existing Pulpit tests do not mock `/api/analytics`, so the request returns 404 there and the card stays hidden.

- [ ] **Step 1: Write the failing tests**

Add `HISTORY, POSITIONS, SUMMARY, EXPOSURE` to the fixtures import in `analysis.test.tsx`, then append:

```tsx
describe("Pulpit card", () => {
  function dashboard(analytics: () => unknown) {
    return mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/portfolio/summary", respond: () => SUMMARY },
      { path: "/api/portfolio/history", respond: () => HISTORY },
      { path: "/api/portfolio/exposure", respond: () => EXPOSURE },
      { path: "/api/positions", respond: () => POSITIONS },
      { path: "/api/portfolio/limits", respond: () => [] },
      { path: "/api/analytics", respond: analytics },
    ]);
  }

  it("shows XIRR and the max drawdown of the whole history and leads to Analiza", async () => {
    const fetchMock = dashboard(() => ANALYTICS);
    const { user } = renderApp("/");

    const card = await screen.findByRole("region", { name: "Analiza" });
    expect(within(card).getByText("+6,4 %")).toBeInTheDocument();
    expect(within(card).getByText("−8,2 %")).toBeInTheDocument();
    expect(fetchMock.mock.calls.map(([url]) => String(url)).some((u) => u.includes("/api/analytics?period=all"))).toBe(true);

    expect(within(card).getByRole("button", { name: "Co to jest: XIRR" })).toBeInTheDocument();
    await user.click(within(card).getByRole("link", { name: "Szczegóły analizy" }));
    expect(await screen.findByRole("heading", { name: "Analiza" })).toBeInTheDocument();
  });

  it("stays hidden without valuations", async () => {
    dashboard(() => ANALYTICS_EMPTY);
    renderApp("/");

    await screen.findByRole("img", { name: /Wykres wartości portfela/ });
    expect(screen.queryByRole("region", { name: "Analiza" })).not.toBeInTheDocument();
  });
});
```

The query string order depends on `request`. If `period=all` is not right after `?`, assert `u.includes("/api/analytics") && u.includes("period=all")` instead.

- [ ] **Step 2: Run the tests to verify they fail**

Run: `npm test -- src/screens/analysis`
Expected: the first new test FAILS, because there is no region "Analiza".

- [ ] **Step 3: Write the card**

Create `web/src/screens/analysis/AnalyticsCard.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { formatPercent, signOf } from "../../format";
import { HELP } from "../../ui/help";
import { InfoTip } from "../../ui/InfoTip";
import ui from "../../ui/ui.module.css";
import { shownReturn } from "./model";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

/** XIRR and the max drawdown of the whole history; hidden until there is a valuation (or when the request fails). */
export function AnalyticsCard() {
  const [accountIds, , ready] = useAccountSelection();
  const analytics = useQuery({
    queryKey: keys.analytics(accountIds, "all"), queryFn: () => api.analytics(accountIds, "all"), enabled: ready,
  });
  const data = analytics.data;
  if (!data || data.period === null) return null;
  const xirr = shownReturn(data.xirr, data.period.annualized).value;
  const fall = data.max_drawdown?.pct ?? null;
  return (
    <section className={ui.section} aria-labelledby="analytics-title">
      <div className={ui.sectionHead}>
        <h2 id="analytics-title" className={ui.sectionTitle}>Analiza</h2>
        <Link className={ui.sectionMore} to="/analiza" aria-label="Szczegóły analizy">Szczegóły</Link>
      </div>
      <dl className={ui.kv}>
        <dt><span>XIRR</span><InfoTip label="XIRR" help={HELP.XIRR!} /></dt>
        <dd className={tone(xirr)}>{formatPercent(xirr, { places: 1 })}</dd>
        <dt><span>Maks. obsunięcie</span><InfoTip label="Maks. obsunięcie" help={HELP["Maks. obsunięcie"]!} /></dt>
        <dd className={tone(fall)}>{formatPercent(fall, { places: 1 })}</dd>
      </dl>
    </section>
  );
}
```

In `DashboardScreen.tsx`, import `AnalyticsCard` from `../analysis/AnalyticsCard` and render `<AnalyticsCard />` right before `<LimitsCard />`.

- [ ] **Step 4: Run all web tests and the type check**

Run: `npm test` and `npx tsc -b` (in `web/`)
Expected: all tests PASS, including the existing dashboard tests.

- [ ] **Step 5: Extend the e2e test**

In `web/e2e/app.spec.ts`, in the first test, add these lines right before `await page.goto("/limity");`:

```ts
  await page.goto("/");
  await page.getByRole("link", { name: "Szczegóły analizy" }).click();
  await expect(page.getByRole("heading", { name: "Analiza" })).toBeVisible();
  await expect(page.getByRole("group", { name: "TWR" })).toBeVisible();
```

Run: `docker compose build api worker`, then `npm run e2e` (in `web/`).
Expected: 3 tests PASS. The e2e profile builds from the same image, so the rebuild picks up pandas and pyxirr.

- [ ] **Step 6: Update the roadmap**

In `docs/superpowers/plans/2026-09-26-00-roadmap.md`, change the status cell of row `7a` from `spec gotowy` to `✅ zrobiony (\`2026-10-01-07a-returns-and-risk.md\`)`.

- [ ] **Step 7: Commit**

```bash
git add web/src/screens/analysis web/src/screens/dashboard/DashboardScreen.tsx web/e2e/app.spec.ts docs/superpowers/plans/2026-09-26-00-roadmap.md
git commit -m "feat(web): Analiza card on Pulpit, e2e step and roadmap"
```

After merging: `docker compose build api worker && docker compose up -d api worker`. The new dependencies need the rebuilt image. There is no migration.
