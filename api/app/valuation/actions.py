"""Which corporate actions count for one user: one entry per instrument and day (pure functions, no database).

The input is already limited to the shared entries (provider, XTB) and the user's own manual ones.
"""
import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.valuation.engine import Conversion, Split

SOURCE_RANK = {"manual": 0, "xtb": 1, "provider": 2}  # lower wins
SPLIT_TYPES = ("split", "reverse_split")


@dataclass(frozen=True)
class Action:
    id: int
    instrument_id: int
    type: str
    effective_date: dt.date
    ratio_from: Decimal
    ratio_to: Decimal
    target_instrument_id: int | None
    source: str


def action_of(row: Any) -> Action:
    """An `Action` from a `CorporateAction` row (or anything with the same attributes)."""
    return Action(row.id, row.instrument_id, row.type, row.effective_date, row.ratio_from, row.ratio_to,
                  row.target_instrument_id, row.source)


def winning(actions: Iterable[Action]) -> dict[tuple[int, dt.date], Action]:
    """The entry that counts on each (instrument, day): manual > xtb > provider, then the lowest id."""
    best: dict[tuple[int, dt.date], Action] = {}
    for action in actions:
        key = (action.instrument_id, action.effective_date)
        current = best.get(key)
        if current is None or (SOURCE_RANK[action.source], action.id) < (SOURCE_RANK[current.source], current.id):
            best[key] = action
    return best


def resolve(actions: Iterable[Action]) -> tuple[list[Split], list[Conversion]]:
    """The splits and conversions the engine applies; a winning `suppress` removes its day's event."""
    splits: list[Split] = []
    conversions: list[Conversion] = []
    for action in sorted(winning(actions).values(), key=lambda a: (a.effective_date, a.instrument_id)):
        if action.type in SPLIT_TYPES:
            splits.append(Split(action.instrument_id, action.effective_date, action.ratio_from, action.ratio_to))
        elif action.type == "conversion":
            assert action.target_instrument_id is not None
            conversions.append(Conversion(action.instrument_id, action.target_instrument_id, action.effective_date,
                                          action.ratio_from, action.ratio_to))
    return splits, conversions
