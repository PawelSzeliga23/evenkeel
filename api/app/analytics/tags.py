"""Analiza → Tagi (plan 7f-1): the Walory parts summed by tag, and each tag's share of the portfolio over time."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal
from typing import Any

from app.analytics.holdings import HoldingsPeriod, _pct, _Part, collect
from app.analytics.schemas import (
    CashShareOut, PeriodRangeOut, TagHistoryOut, TagRowOut, TagSeriesOut, TagsOut, UntaggedOut,
)
from app.models import BondHolding, DailyValuation
from app.portfolio.service import PAYOUT, percent
from app.scoping import UserScope
from app.tags.lookup import TagLookup
from app.valuation.engine import ZERO, money

HISTORY_LIMIT = 400
UNTAGGED = "untagged"
NO_SHARE = Decimal("0.00")


def _thin(count: int, limit: int = HISTORY_LIMIT) -> list[int]:
    """Indices of every n-th day so that at most `limit` remain, always with the first and the last."""
    if count <= limit:
        return list(range(count))
    step = -(-(count - 1) // (limit - 1))
    kept = list(range(0, count, step))
    return kept if kept[-1] == count - 1 else [*kept[:limit - 1], count - 1]


def _key(row: Any, series: dict[int, str]) -> str | None:
    if row.instrument_id is not None:
        return f"i:{row.instrument_id}"
    if row.bond_holding_id is not None:
        return f"b:{series[row.bond_holding_id]}"
    if row.savings_account_id is not None:
        return f"s:{row.savings_account_id}"
    return None  # the account's cash


def _sums(group: list[tuple[str, _Part]]) -> tuple[Decimal, Decimal, Decimal | None, int]:
    value = sum((p.end for _, p in group), ZERO)
    gain = sum((p.gain for _, p in group), ZERO)
    base = sum((p.base + p.bought for _, p in group), ZERO)
    held = len({key for key, p in group if p.end != ZERO})
    return money(value), money(gain), _pct(gain, base), held


def tag_analytics(scope: UserScope, account_ids: frozenset[int] | None, period: HoldingsPeriod) -> TagsOut:
    db = scope.db
    data = collect(scope, account_ids, period)
    if data.start is None or data.end is None:
        return TagsOut(period=None, total_pln=ZERO, tags=[], untagged=None,
                       cash=CashShareOut(value_pln=ZERO, share_pct=None), history=TagHistoryOut(dates=[], series=[]),
                       recalculating=data.recalculating)
    lookup = TagLookup(scope)
    tags = {tag.id: tag for tag in db.scalars(scope.tags())}
    series = dict(db.execute(scope.bond_holdings().with_only_columns(BondHolding.id, BondHolding.series)).all())

    rows = scope.daily_valuations()
    if account_ids is not None:
        rows = rows.where(DailyValuation.account_id.in_(account_ids))
    columns = rows.with_only_columns(
        DailyValuation.date, DailyValuation.account_id, DailyValuation.instrument_id, DailyValuation.bond_holding_id,
        DailyValuation.savings_account_id, PAYOUT.label("payout"))
    total = cash = ZERO
    by_day: dict[dt.date, dict[str, Decimal]] = defaultdict(lambda: defaultdict(lambda: ZERO))
    for row in db.execute(columns.order_by(DailyValuation.date)):
        key = _key(row, series)
        day = by_day[row.date]
        day["total"] += row.payout
        if key is not None:
            ids = lookup.ids(key, row.account_id)
            for tag_id in ids:
                day[str(tag_id)] += row.payout
            if not ids:
                day[UNTAGGED] += row.payout
        if row.date == data.end:
            total += row.payout
            if key is None:
                cash += row.payout

    parts: dict[int | str, list[tuple[str, _Part]]] = defaultdict(list)
    for key, item in data.found.items():
        for account_id, part in item.parts.items():
            for tag_id in lookup.ids(key, account_id) or {UNTAGGED}:
                parts[tag_id].append((key, part))

    rows_out = []
    for tag_id, tag in tags.items():
        if tag_id not in parts:
            continue
        value, gain, gain_pct, held = _sums(parts[tag_id])
        if value == ZERO and gain == ZERO:
            continue
        rows_out.append(TagRowOut(id=tag.id, name=tag.name, color=tag.color, value_pln=value,
                                  share_pct=percent(value, total), gain_pln=gain, gain_pct=gain_pct, holdings=held))
    rows_out.sort(key=lambda r: (-r.value_pln, r.name.lower()))
    untagged = None
    if UNTAGGED in parts:
        value, gain, gain_pct, held = _sums(parts[UNTAGGED])
        if value != ZERO or gain != ZERO:
            untagged = UntaggedOut(value_pln=value, share_pct=percent(value, total), gain_pln=gain,
                                   gain_pct=gain_pct, holdings=held)

    dates = sorted(by_day)
    kept = [dates[i] for i in _thin(len(dates))]
    keys = [str(tag_id) for tag_id in tags if tag_id in parts] + [UNTAGGED]
    history = TagHistoryOut(dates=kept, series=[
        TagSeriesOut(key=key, share_pct=[percent(by_day[d][key], by_day[d]["total"]) or NO_SHARE for d in kept])
        for key in keys])
    return TagsOut(period=PeriodRangeOut(start=data.start, end=data.end), total_pln=money(total), tags=rows_out,
                   untagged=untagged, cash=CashShareOut(value_pln=money(cash), share_pct=percent(cash, total)),
                   history=history, recalculating=data.recalculating)
