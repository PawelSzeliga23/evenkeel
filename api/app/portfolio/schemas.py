import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.transactions.schemas import TransactionOut


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
    fees_pln: Decimal
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


class PositionOut(BaseModel):
    kind: Literal["instrument", "cash"]
    account_id: int
    account_name: str
    instrument_id: int | None
    ticker: str | None
    name: str
    category: str | None
    currency: str | None
    quantity: Decimal  # units of the valuation day; for cash the balance in the account currency
    price: Decimal | None
    price_date: dt.date | None
    price_source: Literal["provider", "xtb"] | None
    value_pln: Decimal
    cost_pln: Decimal
    unrealized_pln: Decimal
    unrealized_pct: Decimal | None
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    dividends_net_pln: Decimal
    fees_pln: Decimal
    realized_pln: Decimal
    day_change_pln: Decimal
    share_pct: Decimal | None = None
    flags: list[str]


class LotOut(BaseModel):
    position_id: str | None
    opened_on: dt.date
    quantity: Decimal
    open_price: Decimal | None
    cost_pln: Decimal
    value_pln: Decimal
    gain_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    holding_days: int
    stop_loss: Decimal | None
    take_profit: Decimal | None


class SaleOut(BaseModel):
    date: dt.date
    opened_on: dt.date
    holding_days: int
    quantity: Decimal
    proceeds_pln: Decimal
    cost_pln: Decimal
    realized_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    position_id: str | None
    matched: bool


class IncomeOut(BaseModel):
    date: dt.date
    type: str
    amount: Decimal
    currency: str
    amount_pln: Decimal


class ReconciliationOut(BaseModel):
    status: Literal["ok", "mismatch", "no_snapshot"]
    taken_at: dt.datetime | None
    xtb_quantity: Decimal | None
    calculated_quantity: Decimal | None


class PositionDetailOut(BaseModel):
    position: PositionOut
    lots: list[LotOut]
    sales: list[SaleOut]
    income: list[IncomeOut]
    transactions: list[TransactionOut]
    reconciliation: ReconciliationOut


class ClosedSaleOut(BaseModel):
    account_id: int
    account_name: str
    instrument_id: int
    ticker: str
    name: str
    opened_on: dt.date
    closed_on: dt.date
    holding_days: int
    quantity: Decimal  # as traded
    cost_pln: Decimal
    proceeds_pln: Decimal
    realized_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    return_pct: Decimal | None
    matched: bool


class ClosedTotalsOut(BaseModel):
    sold_cost_pln: Decimal
    realized_pln: Decimal
    dividends_net_pln: Decimal
    fees_pln: Decimal
    total_pln: Decimal  # realized + dividends + fees
    return_pct: Decimal | None  # total / sold cost


class ClosedInvestmentOut(ClosedTotalsOut):
    account_id: int
    account_name: str
    instrument_id: int
    ticker: str
    name: str
    status: Literal["closed", "partial"]
    first_buy: dt.date
    last_sale: dt.date


class ClosedOut(BaseModel):
    sales: list[ClosedSaleOut]
    investments: list[ClosedInvestmentOut]
    totals: ClosedTotalsOut


class ExposureItemOut(BaseModel):
    currency: str  # ISO code of the quote currency (cash: the account currency) or "unknown"
    value_pln: Decimal
    share_pct: Decimal | None


class ExposurePointOut(BaseModel):
    date: dt.date
    values: dict[str, Decimal]  # currency → value in PLN


class ExposureOut(BaseModel):
    as_of: dt.date | None
    current: list[ExposureItemOut]
    history: list[ExposurePointOut]
