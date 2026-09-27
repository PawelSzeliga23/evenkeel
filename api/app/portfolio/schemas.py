import datetime as dt
from decimal import Decimal

from pydantic import BaseModel


class AllocationOut(BaseModel):
    key: str
    name: str
    value_pln: Decimal
    share_pct: Decimal | None


class SummaryOut(BaseModel):
    as_of: dt.date | None
    value_pln: Decimal
    cash_pln: Decimal
    invested_pln: Decimal
    total_gain_pln: Decimal
    total_gain_pct: Decimal | None
    day_change_pln: Decimal | None
    day_change_pct: Decimal | None
    dividends_net_pln: Decimal
    interest_net_pln: Decimal
    by_account: list[AllocationOut]
    by_kind: list[AllocationOut]
    approximate_positions: int
    recalculating: bool


class HistoryPointOut(BaseModel):
    date: dt.date
    value_pln: Decimal
    invested_pln: Decimal
    net_flow_pln: Decimal


class HistoryEventOut(BaseModel):
    date: dt.date
    type: str
    amount_pln: Decimal


class HistoryOut(BaseModel):
    points: list[HistoryPointOut]
    events: list[HistoryEventOut]
