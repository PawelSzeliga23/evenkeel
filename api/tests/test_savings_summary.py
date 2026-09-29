import datetime as dt
from decimal import Decimal as D

from app.savings.interest import savings_days
from app.savings.summary import Capitalization, Summary, capitalizations, summarize

SEP_01, OCT_10, OCT_31 = dt.date(2026, 9, 1), dt.date(2026, 10, 10), dt.date(2026, 10, 31)
RATES = [(SEP_01, D("5"))]
FLOWS = [(SEP_01, D("10000")), (OCT_10, D("-1000"))]


def test_summary_of_deposits_interest_and_tax() -> None:
    days = savings_days([], RATES, "monthly", taxed=True, end=OCT_31, flows=FLOWS)

    assert summarize(days) == Summary(balance=D("9065.36"), deposits=D("9000.00"), interest_net=D("65.36"),
                                      tax=D("15.33"), accrued=D("0.00"))
    assert capitalizations(days) == [
        Capitalization(dt.date(2026, 9, 30), D("41.10"), D("7.81"), D("33.29")),
        Capitalization(dt.date(2026, 10, 31), D("39.59"), D("7.52"), D("32.07")),
    ]


def test_accrued_interest_between_capitalizations() -> None:
    days = savings_days([], RATES, "monthly", taxed=True, end=dt.date(2026, 9, 29), flows=FLOWS[:1])

    # 28 finished days (the 29th is still running) × 10 000 × 5 % / 365 = 38.36, not credited yet
    assert (summarize(days).accrued, summarize(days).interest_net, capitalizations(days)) == (D("38.36"), D("0.00"), [])


def test_daily_capitalization_is_summed_per_finished_month() -> None:
    days = savings_days([], RATES, "daily", taxed=True, end=dt.date(2026, 10, 5), flows=FLOWS[:1])

    (september,) = capitalizations(days)
    in_september = [d for d in days if d.day.month == 9]
    assert september.period_end == dt.date(2026, 9, 30)
    assert september.gross == sum(d.credited for d in in_september)
    assert september.net == september.gross - september.tax
    assert summarize(days).interest_net == sum(d.credited - d.tax for d in days)


def test_quarterly_capitalization_gives_one_entry_a_quarter() -> None:
    days = savings_days([], RATES, "quarterly", taxed=False, end=dt.date(2026, 12, 31),
                        flows=[(dt.date(2026, 7, 1), D("10000"))])

    assert [c.period_end for c in capitalizations(days)] == [dt.date(2026, 9, 30), dt.date(2026, 12, 31)]
    assert all(c.tax == 0 for c in capitalizations(days))


def test_an_empty_account() -> None:
    assert summarize([]) == Summary(D("0.00"), D("0.00"), D("0.00"), D("0.00"), D("0.00"))
    assert capitalizations([]) == []


def test_accrued_interest_counts_finished_days_only_like_the_bank() -> None:
    """Trade Republic on 2026-09-29: 10 006.72 zł at 6 % since the August credit → 28 finished days = 46.06 zł."""
    flows = [(dt.date(2026, 8, 26), D("500")), (dt.date(2026, 8, 27), D("9500"))]
    days = savings_days([], [(dt.date(2026, 8, 1), D("6"))], "monthly", taxed=True, end=dt.date(2026, 9, 29),
                        flows=flows)

    assert (summarize(days).balance, summarize(days).accrued) == (D("10006.72"), D("46.06"))


def test_nothing_is_accrued_on_the_first_day_or_right_after_a_capitalization() -> None:
    first = savings_days([], RATES, "monthly", taxed=True, end=SEP_01, flows=FLOWS[:1])
    credited = savings_days([], RATES, "monthly", taxed=True, end=dt.date(2026, 9, 30), flows=FLOWS[:1])

    assert (summarize(first).accrued, summarize(credited).accrued) == (D("0.00"), D("0.00"))
