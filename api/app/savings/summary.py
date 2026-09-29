"""What a savings account has earned, read from its computed days (pure functions)."""
import calendar
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.savings.interest import SavingsDay
from app.valuation.engine import ZERO, money


@dataclass(frozen=True)
class Summary:
    balance: Decimal
    deposits: Decimal  # deposits minus withdrawals (corrections included)
    interest_net: Decimal  # credited interest after tax
    tax: Decimal
    accrued: Decimal  # accrued since the last capitalization, not credited yet (gross)


@dataclass(frozen=True)
class Capitalization:
    period_end: dt.date  # the last day of the month (the quarter's last month for quarterly capitalization)
    gross: Decimal
    tax: Decimal
    net: Decimal


def summarize(days: Sequence[SavingsDay]) -> Summary:
    if not days:
        return Summary(money(ZERO), money(ZERO), money(ZERO), money(ZERO), money(ZERO))
    return Summary(
        balance=money(days[-1].balance),
        deposits=money(sum((d.net_flow for d in days), ZERO)),
        interest_net=money(sum((d.credited - d.tax for d in days), ZERO)),
        tax=money(sum((d.tax for d in days), ZERO)),
        accrued=money(days[-1].accrued),
    )


def capitalizations(days: Sequence[SavingsDay]) -> list[Capitalization]:
    """Credited interest per month, for months that ended by the last day of `days`."""
    if not days:
        return []
    last = days[-1].day
    months: dict[tuple[int, int], list[SavingsDay]] = {}
    for d in days:
        if d.credited:
            months.setdefault((d.day.year, d.day.month), []).append(d)
    result = []
    for (year, month), credited in sorted(months.items()):
        period_end = dt.date(year, month, calendar.monthrange(year, month)[1])
        if period_end <= last:
            gross = sum((d.credited for d in credited), ZERO)
            tax = sum((d.tax for d in credited), ZERO)
            result.append(Capitalization(period_end, money(gross), money(tax), money(gross - tax)))
    return result
