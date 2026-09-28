"""Time-weighted return from daily portfolio values and external flows (pure functions, spec §6)."""
import datetime as dt
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

ONE = Decimal(1)
HUNDRED = Decimal(100)
PERCENT_PLACES = Decimal("0.01")


def twr_index(days: Iterable[tuple[dt.date, Decimal, Decimal]]) -> list[tuple[dt.date, Decimal | None]]:
    """For each (day, value, net external flow) in date order: how much 1 zł held since the first day with a
    positive base has grown to (TWR = factor − 1), or None before that day. A flow counts at the START of its
    day — XTB users deposit and buy the same day, so the day's spread/close gap on the new money must not be
    charged to the old base: r = V_t / (V_{t−1} + F_t) − 1. A day whose denominator V_{t−1} + F_t ≤ 0 has no
    return and is skipped (the factor stays as it was)."""
    result: list[tuple[dt.date, Decimal | None]] = []
    factor: Decimal | None = None
    previous = Decimal(0)
    for day, value, flow in days:
        denominator = previous + flow
        if denominator > 0:
            factor = (factor if factor is not None else ONE) * value / denominator
        result.append((day, factor))
        previous = value
    return result


def twr_percent(factor: Decimal | None) -> Decimal | None:
    return None if factor is None else ((factor - ONE) * HUNDRED).quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP)
