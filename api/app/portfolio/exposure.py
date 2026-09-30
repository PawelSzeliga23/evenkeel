"""Currency exposure from the cached daily valuations: by quote currency (spec §6), cash in its account currency."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func

from app.models import Account, DailyValuation, Instrument
from app.portfolio.schemas import ExposureItemOut, ExposureOut, ExposurePointOut
from app.portfolio.service import _valuations, percent
from app.scoping import UserScope
from app.valuation.engine import ZERO, money

UNKNOWN_CURRENCY = "unknown"  # an instrument the price provider has no quotes for


def currency_exposure(
    scope: UserScope, account_ids: frozenset[int] | None, start: dt.date | None, end: dt.date | None
) -> ExposureOut:
    # Grouped by plain columns (a CASE with a bound literal would differ between SELECT and GROUP BY in
    # Postgres); the currency of each group is decided below.
    is_cash = DailyValuation.instrument_id.is_(None)
    query = (
        _valuations(scope, account_ids)
        .with_only_columns(DailyValuation.date, is_cash, Account.currency, Instrument.currency,
                           func.sum(DailyValuation.value_pln))
        .select_from(DailyValuation)
        .join(Account, Account.id == DailyValuation.account_id)
        .outerjoin(Instrument, Instrument.id == DailyValuation.instrument_id)
        .group_by(DailyValuation.date, is_cash, Account.currency, Instrument.currency)
    )
    points: dict[dt.date, dict[str, Decimal]] = defaultdict(dict)
    for day, cash, account_currency, quote_currency, value in scope.db.execute(query):
        code = account_currency if cash else (quote_currency or UNKNOWN_CURRENCY)
        points[day][code] = points[day].get(code, ZERO) + value
    if not points:
        return ExposureOut(as_of=None, current=[], history=[])
    latest = max(points)
    total = sum(points[latest].values(), ZERO)
    current = sorted(
        (ExposureItemOut(currency=code, value_pln=money(value), share_pct=percent(value, total))
         for code, value in points[latest].items()),
        key=lambda item: (-item.value_pln, item.currency),
    )
    history = [
        ExposurePointOut(date=day, values={code: money(value) for code, value in sorted(values.items())})
        for day, values in sorted(points.items())
        if (start is None or day >= start) and (end is None or day <= end)
    ]
    return ExposureOut(as_of=latest, current=current, history=history)
