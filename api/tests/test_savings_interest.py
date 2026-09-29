import datetime as dt
from decimal import Decimal as D

from app.savings.interest import is_capitalization_day, rate_on, savings_days

SEP_01, SEP_30, OCT_10, OCT_31 = dt.date(2026, 9, 1), dt.date(2026, 9, 30), dt.date(2026, 10, 10), dt.date(2026, 10, 31)
RATES = [(SEP_01, D("5.00"))]


def _on(days: list, day: dt.date):  # noqa: ANN202
    return next(d for d in days if d.day == day)


def test_capitalization_days() -> None:
    assert is_capitalization_day(dt.date(2026, 9, 12), "daily")
    assert (is_capitalization_day(SEP_30, "monthly"), is_capitalization_day(dt.date(2026, 9, 29), "monthly")) == (
        True, False)
    assert (is_capitalization_day(SEP_30, "quarterly"), is_capitalization_day(OCT_31, "quarterly")) == (True, False)


def test_first_balance_is_a_deposit_and_interest_is_credited_monthly_after_tax() -> None:
    days = savings_days([(SEP_01, D("10000"))], RATES, "monthly", taxed=True, end=OCT_31)

    assert (days[0].day, days[0].balance, days[0].net_flow) == (SEP_01, D("10000"), D("10000"))
    assert _on(days, dt.date(2026, 9, 29)).balance == D("10000")  # nothing credited before month end
    # 29 days (2–30 Sep) × 10 000 × 5 % / 365 = 39.73 gross, 7.55 tax
    assert _on(days, SEP_30).balance == D("10032.18")
    # 31 days × 10 032.18 × 5 % / 365 = 42.60 gross, 8.09 tax
    assert _on(days, OCT_31).balance == D("10066.69")
    assert days[-1].day == OCT_31 and all(d.net_flow == 0 for d in days[1:])


def test_ike_savings_pay_no_tax() -> None:
    days = savings_days([(SEP_01, D("10000"))], RATES, "monthly", taxed=False, end=SEP_30)
    assert days[-1].balance == D("10039.73")


def test_a_copied_balance_that_differs_is_a_deposit_and_interest_follows_it() -> None:
    days = savings_days([(SEP_01, D("10000")), (OCT_10, D("11032.18"))], RATES, "monthly", taxed=True, end=OCT_31)

    assert _on(days, OCT_10).net_flow == D("1000.00")
    # 10 days on 10 032.18 + 21 days on 11 032.18 = 45.48 gross, 8.64 tax
    assert _on(days, OCT_31).balance == D("11069.02")


def test_rate_changes_apply_from_their_day_and_no_rate_earns_nothing() -> None:
    days = savings_days([(SEP_01, D("10000"))], [(dt.date(2026, 9, 16), D("3.65"))], "monthly", taxed=False, end=SEP_30)
    # 15 days (16–30 Sep) × 10 000 × 3.65 % / 365 = 15.00
    assert days[-1].balance == D("10015.00")


def test_no_balances_no_days() -> None:
    assert savings_days([], RATES, "monthly", taxed=True, end=OCT_31) == []


OCT_01 = dt.date(2026, 10, 1)


def test_a_deposit_starts_the_account_like_a_first_balance() -> None:
    days = savings_days([], RATES, "monthly", taxed=True, end=OCT_31, flows=[(SEP_01, D("10000"))])

    assert (days[0].day, days[0].balance, days[0].net_flow) == (SEP_01, D("10000"), D("10000"))
    assert (_on(days, SEP_30).balance, _on(days, OCT_31).balance) == (D("10033.29"), D("10067.80"))


def test_a_withdrawal_lowers_the_balance_and_earns_nothing_from_its_day() -> None:
    days = savings_days([], RATES, "monthly", taxed=True, end=OCT_31,
                        flows=[(SEP_01, D("10000")), (OCT_10, D("-1000"))])

    assert (_on(days, OCT_10).balance, _on(days, OCT_10).net_flow) == (D("9033.29"), D("-1000"))
    # 9 days × 10 033.29 + 22 days × 9 033.29, × 5 % / 365 = 39.59 gross, 7.52 tax
    assert (_on(days, OCT_31).credited, _on(days, OCT_31).tax, _on(days, OCT_31).balance) == (
        D("39.59"), D("7.52"), D("9065.36"))


def test_a_deposit_on_a_capitalization_day_earns_for_that_day() -> None:
    days = savings_days([], RATES, "monthly", taxed=True, end=OCT_01,
                        flows=[(SEP_01, D("10000")), (SEP_30, D("5000"))])

    # 29 days × 10 000 + 1 day × 15 000, × 5 % / 365 = 41.78 gross, 7.94 tax
    assert _on(days, SEP_30).balance == D("15033.84")
    assert _on(days, OCT_01).accrued == D("15033.84") * D("5") / 100 / 365


def test_a_rate_change_applies_from_its_day() -> None:
    rates = [(SEP_01, D("5")), (dt.date(2026, 9, 16), D("3"))]
    days = savings_days([], rates, "monthly", taxed=True, end=SEP_30, flows=[(SEP_01, D("10000"))])

    # 15 days at 5 % + 15 days at 3 % = 32.88 gross, 6.25 tax
    assert (_on(days, SEP_30).credited, _on(days, SEP_30).tax, _on(days, SEP_30).balance) == (
        D("32.88"), D("6.25"), D("10026.63"))


def test_deposits_on_the_same_day_add_up_and_a_copied_balance_still_corrects() -> None:
    days = savings_days([(OCT_10, D("12000"))], RATES, "monthly", taxed=True, end=OCT_10,
                        flows=[(SEP_01, D("6000")), (SEP_01, D("4000"))])

    assert _on(days, SEP_01).net_flow == D("10000")
    assert (_on(days, OCT_10).balance, _on(days, OCT_10).net_flow) == (D("12000"), D("12000") - D("10033.29"))


def test_the_rate_on_a_day() -> None:
    rates = [(SEP_01, D("5")), (OCT_10, D("4"))]
    assert [rate_on(rates, day) for day in (dt.date(2026, 8, 31), SEP_30, OCT_10)] == [D("0"), D("5"), D("4")]


def test_money_earns_from_the_day_it_arrives_like_the_bank_counts_it() -> None:
    """Trade Republic, August 2026: 6 %, 500 zł on the 26th and 9 500 zł on the 27th → 6.72 zł net on the 31st."""
    aug_26, aug_27, aug_31 = dt.date(2026, 8, 26), dt.date(2026, 8, 27), dt.date(2026, 8, 31)
    days = savings_days([], [(dt.date(2026, 8, 1), D("6"))], "monthly", taxed=True, end=aug_31,
                        flows=[(aug_26, D("500")), (aug_27, D("4500")), (aug_27, D("5000"))])

    # 6 days × 500 + 5 days × 9 500, × 6 % / 365 = 8.30 gross, 1.58 tax
    assert (_on(days, aug_31).credited, _on(days, aug_31).tax, _on(days, aug_31).balance) == (
        D("8.30"), D("1.58"), D("10006.72"))
