"""A savings account between balances copied from the bank (pure functions). Interest accrues daily at the annual
rate of the day (balance × rate / 100 / 365) and is credited on each capitalization day, rounded to the grosz,
minus the 19 % tax (none on IKE / IKZE). A copied balance is the balance at the end of its day; its difference
from the computed balance is the owner's deposit or withdrawal."""
import bisect
import calendar
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal(0)
HUNDRED = Decimal(100)
DAYS_IN_YEAR = Decimal(365)
TAX_RATE = Decimal("0.19")
CENT = Decimal("0.01")
ONE_DAY = dt.timedelta(days=1)
QUARTER_ENDS = (3, 6, 9, 12)


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SavingsDay:
    day: dt.date
    balance: Decimal  # at the end of the day
    net_flow: Decimal  # the owner's deposit (+) or withdrawal (−) that day


def is_capitalization_day(day: dt.date, capitalization: str) -> bool:
    if capitalization == "daily":
        return True
    month_end = day.day == calendar.monthrange(day.year, day.month)[1]
    return month_end if capitalization == "monthly" else month_end and day.month in QUARTER_ENDS


def savings_days(
    balances: Sequence[tuple[dt.date, Decimal]], rates: Sequence[tuple[dt.date, Decimal]], capitalization: str,
    taxed: bool, end: dt.date,
) -> list[SavingsDay]:
    """Every day from the first copied balance to `end`."""
    if not balances:
        return []
    copied = dict(balances)
    rate_days = sorted(rates)
    starts = [start for start, _ in rate_days]
    day = min(copied)
    balance = accrued = ZERO
    result: list[SavingsDay] = []
    while day <= end:
        index = bisect.bisect_right(starts, day) - 1
        rate = rate_days[index][1] if index >= 0 else ZERO
        accrued += balance * rate / HUNDRED / DAYS_IN_YEAR
        if is_capitalization_day(day, capitalization):
            gross = _money(accrued)
            balance += gross - (_money(gross * TAX_RATE) if taxed else ZERO)
            accrued = ZERO
        flow = ZERO
        if day in copied:
            flow = copied[day] - balance
            balance = copied[day]
        result.append(SavingsDay(day, balance, flow))
        day += ONE_DAY
    return result
