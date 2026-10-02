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


def test_xirr_equals_twr_with_a_single_deposit() -> None:
    days = [(day("2026-01-01"), D("1000"), D("1000"))] + [
        (day("2026-01-01") + dt.timedelta(days=t), D("1000"), D("0")) for t in range(1, 29)
    ] + [(day("2026-01-30"), D("1030"), D("0"))]
    result = analyze(days, [], "all")

    assert result.twr_period_pct == D("3.00")
    assert result.xirr_period_pct == D("3.00")


def test_a_return_exactly_to_the_record_counts_as_recovered() -> None:
    days = [
        (day("2026-01-01"), D("100"), D("100")), (day("2026-01-02"), D("102"), D("0")),
        (day("2026-01-03"), D("96.3"), D("0")), (day("2026-01-04"), D("102"), D("0")),
    ]
    result = analyze(days, [], "all")

    assert result.max_drawdown.recovered_on == day("2026-01-04")
    assert result.current_drawdown_pct == D("0.00")


def test_day_amounts_round_half_up() -> None:
    days = [(day("2026-01-01"), D("1000"), D("1000")), (day("2026-01-02"), D("1000.005"), D("0"))]
    assert analyze(days, [], "all").best_day.pln == D("0.01")


def test_a_flat_series_has_its_drawdown_inside_the_history() -> None:
    days = [(day("2026-01-01"), D("100"), D("100")), (day("2026-01-02"), D("100"), D("0"))]
    fall = analyze(days, [], "all").max_drawdown
    assert (fall.pct, fall.peak_date, fall.trough_date) == (D("0.00"), day("2026-01-01"), day("2026-01-01"))


def test_a_flow_on_the_last_day_counts_in_xirr() -> None:
    # 1 000 zł grows to 1 100 zł in a year and 1 000 zł more is paid in on the last day: +10 % a year
    days = [(day("2025-01-01"), D("1000"), D("1000")), (day("2026-01-01"), D("2100"), D("1000"))]
    assert analyze(days, [], "all").xirr_annual_pct == D("10.00")
