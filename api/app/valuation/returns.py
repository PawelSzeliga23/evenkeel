"""Time-weighted return from daily portfolio values and external flows (pure functions, spec §6)."""
import datetime as dt
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

ONE = Decimal(1)
HUNDRED = Decimal(100)
PERCENT_PLACES = Decimal("0.01")


def twr_index(days: Iterable[tuple[dt.date, Decimal, Decimal]]) -> list[tuple[dt.date, Decimal | None]]:
    """For each (day, value, net external flow) in date order: how much 1 zł held since the first day with a
    value has grown to (TWR = factor − 1), or None before that day. A flow counts at the end of its day:
    r = (V_t − F_t) / V_{t−1} − 1. A day after an empty portfolio (V_{t−1} = 0) has no return and is skipped."""
    result: list[tuple[dt.date, Decimal | None]] = []
    factor: Decimal | None = None
    previous = Decimal(0)
    for day, value, flow in days:
        if previous > 0:
            factor = (factor if factor is not None else ONE) * (value - flow) / previous
        elif factor is None and value > 0:
            factor = ONE
        result.append((day, factor))
        previous = value
    return result


def twr_percent(factor: Decimal | None) -> Decimal | None:
    return None if factor is None else ((factor - ONE) * HUNDRED).quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP)
