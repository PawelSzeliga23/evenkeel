"""EDO treasury bonds (10 years, inflation-linked, interest capitalized yearly): pure functions on one bond of
100 zł. Rules from the issue letter (EDO0936, annex 3) and the MF offer page; tax and the early redemption fee
are computed per bond."""
import calendar
import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

NOMINAL = Decimal(100)
YEARS = 10
TAX_RATE = Decimal("0.19")
ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)
CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Series:
    first_period_rate: Decimal  # percent a year
    margin: Decimal  # percentage points over CPI from the 2nd period
    early_redemption_fee: Decimal  # zł per bond


@dataclass(frozen=True)
class Period:
    number: int  # 1..10
    start: dt.date
    end: dt.date  # the next anniversary (exclusive)
    rate: Decimal  # percent a year
    estimated: bool  # the CPI it needs is not known yet: the previous period's rate stands in


def series_name(purchase_date: dt.date) -> str:
    """EDO + month and two-digit year of maturity: bought on 2026-09-15 → EDO0936."""
    return f"EDO{purchase_date.month:02d}{(purchase_date.year + YEARS) % 100:02d}"


def anniversary(purchase_date: dt.date, years: int) -> dt.date:
    """The purchase day `years` later; 29 February falls on 28 February in a common year."""
    year = purchase_date.year + years
    return dt.date(year, purchase_date.month, min(purchase_date.day, calendar.monthrange(year, purchase_date.month)[1]))


def cpi_month(period_start: dt.date) -> dt.date:
    """The CPI a period earns: announced by GUS in the month before the period's first month, i.e. the index for
    two months before it (a period from September uses July's year-on-year CPI)."""
    month = period_start.month - 2
    year = period_start.year + (month - 1) // 12
    return dt.date(year, (month - 1) % 12 + 1, 1)


def periods(purchase_date: dt.date, series: Series, cpi: Mapping[dt.date, Decimal]) -> list[Period]:
    """The ten interest periods: the series' first-year rate, then CPI (negative counts as 0) + margin."""
    result: list[Period] = []
    for number in range(1, YEARS + 1):
        start, end = anniversary(purchase_date, number - 1), anniversary(purchase_date, number)
        if number == 1:
            rate, estimated = series.first_period_rate, False
        elif (inflation := cpi.get(cpi_month(start))) is None:
            rate, estimated = result[-1].rate, True
        else:
            rate, estimated = max(inflation, ZERO) + series.margin, False
        result.append(Period(number, start, end, rate, estimated))
    return result


def period_on(schedule: Sequence[Period], day: dt.date) -> Period:
    """The period containing `day`; the last one on and after maturity."""
    return next((period for period in schedule if day < period.end), schedule[-1])


def value(schedule: Sequence[Period], day: dt.date) -> Decimal:
    """One bond on `day` before tax: 100 × Π(1 + r_i) over finished periods × (1 + r_k × a_k / ACT_k), rounded to
    the grosz; on and after maturity the value at maturity."""
    factor = ONE
    for period in schedule:
        rate = period.rate / HUNDRED
        if day < period.end:
            elapsed, length = (day - period.start).days, (period.end - period.start).days
            return _money(NOMINAL * factor * (ONE + rate * elapsed / length))
        factor *= ONE + rate
    return _money(NOMINAL * factor)


def tax(interest: Decimal) -> Decimal:
    return _money(max(interest, ZERO) * TAX_RATE)


def net_value(gross: Decimal, taxed: bool) -> Decimal:
    """One bond after the 19 % tax on its interest (IKE / IKZE: no tax)."""
    return gross - tax(gross - NOMINAL) if taxed else gross


def redemption_value(gross: Decimal, fee: Decimal, taxed: bool) -> Decimal:
    """Early redemption of one bond: the fee is taken in full or up to the interest accrued (the capital is never
    touched), and the tax is on the interest after the fee."""
    interest = gross - NOMINAL
    charged = min(fee, max(interest, ZERO))
    return gross - charged - (tax(interest - charged) if taxed else ZERO)
