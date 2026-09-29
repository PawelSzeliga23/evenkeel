"""A savings account from its deposits and withdrawals (pure functions). Interest accrues daily at the annual rate
of the day (balance × rate / 100 / 365) and is credited on each capitalization day, rounded to the grosz, minus the
19 % tax (none on IKE / IKZE). On a day, the day's deposits and withdrawals come first, then that day's interest,
from the balance at the end of the day, as banks count it: money deposited earns from its own day and money withdrawn
stops earning on its day. A balance copied from the bank is
the balance at the end of its day; its difference from the computed balance counts as the owner's deposit or
withdrawal (a correction)."""
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
    net_flow: Decimal  # the owner's deposit (+) or withdrawal (−) that day, corrections included
    credited: Decimal = ZERO  # gross interest credited that day
    tax: Decimal = ZERO  # tax withheld from it
    accrued: Decimal = ZERO  # interest accrued after the day and not credited yet (not rounded)


def is_capitalization_day(day: dt.date, capitalization: str) -> bool:
    if capitalization == "daily":
        return True
    month_end = day.day == calendar.monthrange(day.year, day.month)[1]
    return month_end if capitalization == "monthly" else month_end and day.month in QUARTER_ENDS


def rate_on(rates: Sequence[tuple[dt.date, Decimal]], day: dt.date) -> Decimal:
    """The annual rate valid on `day` (rates sorted by their first day); 0 before the first one."""
    starts = [start for start, _ in rates]
    index = bisect.bisect_right(starts, day) - 1
    return rates[index][1] if index >= 0 else ZERO


def savings_days(
    balances: Sequence[tuple[dt.date, Decimal]], rates: Sequence[tuple[dt.date, Decimal]], capitalization: str,
    taxed: bool, end: dt.date, flows: Sequence[tuple[dt.date, Decimal]] = (),
) -> list[SavingsDay]:
    """Every day from the first entry (a deposit, a withdrawal or a copied balance) to `end`."""
    copied = dict(balances)
    moves: dict[dt.date, Decimal] = {}
    for day, amount in flows:
        moves[day] = moves.get(day, ZERO) + amount
    if not copied and not moves:
        return []
    rate_days = sorted(rates)
    day = min([*copied, *moves])
    balance = accrued = ZERO
    result: list[SavingsDay] = []
    while day <= end:
        flow = moves.get(day, ZERO)
        balance += flow
        accrued += balance * rate_on(rate_days, day) / HUNDRED / DAYS_IN_YEAR
        credited = tax = ZERO
        if is_capitalization_day(day, capitalization):
            credited = _money(accrued)
            tax = _money(credited * TAX_RATE) if taxed else ZERO
            balance += credited - tax
            accrued = ZERO
        if day in copied:
            flow += copied[day] - balance
            balance = copied[day]
        result.append(SavingsDay(day, balance, flow, credited, tax, accrued))
        day += ONE_DAY
    return result
