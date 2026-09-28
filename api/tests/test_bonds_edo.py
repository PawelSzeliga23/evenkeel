"""EDO rules: issue letter EDO0936 (annex 3) and the MF offer page examples."""
import datetime as dt
from decimal import Decimal as D

from app.bonds.edo import (
    Series, anniversary, cpi_month, net_value, period_on, periods, redemption_value, series_name, value,
)

EDO0936 = Series(D("5.35"), D("2.00"), D("3.00"))
BOUGHT = dt.date(2026, 9, 15)
CPI = {dt.date(2027, 7, 1): D("3.0")}  # July 2027 → the 2nd period (from 2027-09-15) earns 3.0 + 2.00 = 5.00 %


def test_series_is_named_after_the_maturity_month() -> None:
    assert (series_name(BOUGHT), series_name(dt.date(2026, 10, 1))) == ("EDO0936", "EDO1036")


def test_anniversary_of_29_february_falls_on_28_february() -> None:
    assert anniversary(dt.date(2024, 2, 29), 1) == dt.date(2025, 2, 28)
    assert anniversary(dt.date(2024, 2, 29), 4) == dt.date(2028, 2, 29)


def test_a_period_uses_the_cpi_of_two_months_before_its_first_month() -> None:
    assert (cpi_month(dt.date(2027, 9, 15)), cpi_month(dt.date(2027, 1, 15))) == (
        dt.date(2027, 7, 1), dt.date(2026, 11, 1))


def test_periods_first_rate_then_cpi_plus_margin_then_estimated_while_cpi_is_unknown() -> None:
    schedule = periods(BOUGHT, EDO0936, CPI)

    assert len(schedule) == 10
    assert [(p.number, p.start, p.end, p.rate, p.estimated) for p in schedule[:3]] == [
        (1, BOUGHT, dt.date(2027, 9, 15), D("5.35"), False),
        (2, dt.date(2027, 9, 15), dt.date(2028, 9, 15), D("5.00"), False),
        (3, dt.date(2028, 9, 15), dt.date(2029, 9, 15), D("5.00"), True),  # CPI for July 2028 not known yet
    ]
    assert schedule[-1].end == dt.date(2036, 9, 15)


def test_negative_inflation_counts_as_zero() -> None:
    schedule = periods(BOUGHT, EDO0936, {dt.date(2027, 7, 1): D("-1.2")})
    assert schedule[1].rate == D("2.00")


def test_value_accrues_within_a_period_and_compounds_after_the_anniversary() -> None:
    schedule = periods(BOUGHT, EDO0936, CPI)

    assert value(schedule, BOUGHT) == D("100.00")
    # 100 × (1 + 5.35 % × 181 / 365)
    assert value(schedule, dt.date(2027, 3, 15)) == D("102.65")
    assert value(schedule, dt.date(2027, 9, 15)) == D("105.35")
    # 105.35 × (1 + 5.00 % × 182 / 366) — the 2nd period contains 29 February 2028
    assert value(schedule, dt.date(2028, 3, 15)) == D("107.97")
    assert period_on(schedule, dt.date(2028, 3, 15)).number == 2


def test_value_at_maturity_compounds_all_ten_periods() -> None:
    schedule = periods(BOUGHT, EDO0936, CPI)  # periods 3–10 estimated at 5.00 %
    # 100 × 1.0535 × 1.05⁹
    assert value(schedule, dt.date(2036, 9, 15)) == D("163.43")
    assert value(schedule, dt.date(2040, 1, 1)) == D("163.43")


def test_net_value_after_tax_matches_the_mf_example() -> None:
    # MF: 47.05 zł of interest before tax → 38.11 zł after it
    assert net_value(D("147.05"), taxed=True) == D("138.11")
    assert net_value(D("147.05"), taxed=False) == D("147.05")


def test_early_redemption_matches_the_mf_example() -> None:
    # MF: 4.16 zł of interest, 2.00 zł fee, tax 0.41 zł on 2.16 zł → 101.75 zł
    assert redemption_value(D("104.16"), D("2.00"), taxed=True) == D("101.75")


def test_early_redemption_fee_never_exceeds_the_interest() -> None:
    assert redemption_value(D("102.65"), D("3.00"), taxed=True) == D("100.00")
    assert redemption_value(D("107.97"), D("3.00"), taxed=True) == D("104.03")  # 107.97 − 3 − 19 % × 4.97
    assert redemption_value(D("107.97"), D("3.00"), taxed=False) == D("104.97")
