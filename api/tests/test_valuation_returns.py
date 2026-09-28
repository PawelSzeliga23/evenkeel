import datetime as dt
from decimal import Decimal as D

from app.valuation.returns import twr_index, twr_percent

D1, D2, D3, D4, D5, D6 = (dt.date(2026, 3, day) for day in range(1, 7))


def test_a_deposit_in_the_middle_does_not_count_as_return() -> None:
    days = [(D1, D("100"), D("100")), (D2, D("110"), D("0")), (D3, D("160"), D("50")), (D4, D("176"), D("0"))]

    factors = twr_index(days)

    # +10 % on day 2, 0 % on day 3 (the 50 zł deposit), +10 % on day 4
    assert [twr_percent(factor) for _, factor in factors] == [D("0.00"), D("10.00"), D("10.00"), D("21.00")]


def test_days_after_an_empty_portfolio_are_skipped() -> None:
    days = [(D1, D("0"), D("0")), (D2, D("100"), D("100")), (D3, D("0"), D("-100")), (D4, D("0"), D("0")),
            (D5, D("200"), D("200")), (D6, D("220"), D("0"))]

    assert [twr_percent(factor) for _, factor in twr_index(days)] == [
        None, D("0.00"), D("0.00"), D("0.00"), D("0.00"), D("10.00")]


def test_a_same_day_flow_counts_at_the_start_of_the_day() -> None:
    # V0=1000, then a 100000 deposit invested the same day closing at 100500: the day's small gap on the new
    # money must not be charged to the old 1000 zł base (old end-of-day formula gave -50.00 %).
    days = [(D1, D("1000"), D("1000")), (D2, D("100500"), D("100000"))]

    assert [twr_percent(factor) for _, factor in twr_index(days)] == [D("0.00"), D("-0.50")]


def test_zero_factor_persists_when_portfolio_resumes() -> None:
    # A total loss (factor = 0) followed by recovery should keep the factor at 0, not reset.
    days = [(D1, D("100"), D("100")), (D2, D("0"), D("0")), (D3, D("50"), D("50")), (D4, D("60"), D("0"))]

    assert [twr_percent(factor) for _, factor in twr_index(days)] == [
        D("0.00"), D("-100.00"), D("-100.00"), D("-100.00")]
