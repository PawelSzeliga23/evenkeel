import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

from app.tags.schemas import TagOnOut
from app.transactions.schemas import TransactionOut


class AllocationOut(BaseModel):
    key: str
    name: str
    value_pln: Decimal
    share_pct: Decimal | None


class SummaryOut(BaseModel):
    as_of: dt.date | None
    value_pln: Decimal  # payout value: market value − exit costs
    market_value_pln: Decimal
    exit_cost_pln: Decimal
    cash_pln: Decimal
    invested_pln: Decimal
    total_gain_pln: Decimal
    total_gain_pct: Decimal | None
    day_change_pln: Decimal | None
    day_change_pct: Decimal | None
    twr_pct: Decimal | None
    dividends_net_pln: Decimal
    interest_net_pln: Decimal
    fees_pln: Decimal
    by_account: list[AllocationOut]
    by_kind: list[AllocationOut]
    approximate_positions: int
    recalculating: bool
    prices_refreshed_at: dt.datetime | None = None  # latest price check of the user's instruments


class RefreshOut(BaseModel):
    refreshed_at: dt.datetime | None
    fetched: bool  # False: nothing to fetch, or checked less than a minute ago


class HistoryPointOut(BaseModel):
    date: dt.date
    value_pln: Decimal
    invested_pln: Decimal
    net_flow_pln: Decimal
    twr_pct: Decimal | None


class HistoryEventOut(BaseModel):
    date: dt.date
    type: str
    amount_pln: Decimal


class HistoryOut(BaseModel):
    points: list[HistoryPointOut]
    events: list[HistoryEventOut]


class PositionOut(BaseModel):
    kind: Literal["instrument", "cash", "bond", "savings"]
    account_id: int
    account_name: str
    instrument_id: int | None
    ticker: str | None
    name: str
    category: str | None
    currency: str | None
    quantity: Decimal  # units of the valuation day; for cash the balance in the account currency
    price: Decimal | None
    price_currency: str | None = None  # "PLN" when valued from XTB figures (price = PLN per unit)
    price_date: dt.date | None
    price_source: Literal["provider", "xtb"] | None
    value_pln: Decimal  # market value
    exit_fx_pln: Decimal  # XTB currency conversion fee on a sale
    exit_spread_pln: Decimal  # manual half-spread
    exit_cost_pln: Decimal
    payout_pln: Decimal  # value − exit costs; gain, share and day change are from this
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
    spread_pct: Decimal | None = None  # the instrument's manual half-spread, percent
    bond_holding_id: int | None = None
    savings_account_id: int | None = None
    tags: list[TagOnOut] = []


class LotOut(BaseModel):
    position_id: str | None
    opened_on: dt.date
    quantity: Decimal
    open_price: Decimal | None  # XTB's own purchase price (quote currency), as XTB shows it
    open_price_with_fx: Decimal | None = None  # what one unit cost with XTB's conversion (foreign instruments only)
    cost_pln: Decimal
    value_pln: Decimal
    exit_cost_pln: Decimal
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
    average_price: Decimal | None = None  # quantity-weighted lot open price, quote currency
    tags: list[TagOnOut] = []


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


class LimitAccountOut(BaseModel):
    account_id: int
    name: str
    paid_pln: Decimal


class LimitOut(BaseModel):
    wrapper: Literal["ike", "ikze"]
    year: int
    paid_pln: Decimal
    limit_pln: Decimal | None  # None: no statutory limit stored for that year
    remaining_pln: Decimal | None
    exceeded: bool
    accounts: list[LimitAccountOut]


class PricePointOut(BaseModel):
    date: dt.date
    close: Decimal


class PriceMarkerOut(BaseModel):
    date: dt.date
    kind: Literal["buy", "sell", "dividend"]
    price: Decimal | None  # quote currency, after later splits
    price_with_fx: Decimal | None  # PLN paid ÷ quantity ÷ NBP rate (XTB's conversion inside), foreign only
    quantity: Decimal | None  # after later splits
    amount_pln: Decimal


class PriceChartOut(BaseModel):
    currency: str | None
    points: list[PricePointOut]
    markers: list[PriceMarkerOut]
    first_buy: dt.date | None
