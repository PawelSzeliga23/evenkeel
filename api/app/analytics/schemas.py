import datetime as dt
from decimal import Decimal

from pydantic import BaseModel


class PeriodOut(BaseModel):
    start: dt.date
    end: dt.date
    days: int
    annualized: bool


class ReturnOut(BaseModel):
    period_pct: Decimal | None
    annual_pct: Decimal | None


class DrawdownOut(BaseModel):
    pct: Decimal
    peak_date: dt.date
    trough_date: dt.date
    recovered_on: dt.date | None


class DayExtremeOut(BaseModel):
    date: dt.date
    pct: Decimal
    pln: Decimal


class DrawdownPointOut(BaseModel):
    date: dt.date
    pct: Decimal


class MonthRowOut(BaseModel):
    year: int
    months: list[Decimal | None]
    year_pct: Decimal | None
    first_partial_month: int | None


class AnalyticsOut(BaseModel):
    period: PeriodOut | None
    profit_pln: Decimal
    twr: ReturnOut
    xirr: ReturnOut
    volatility_pct: Decimal | None
    sharpe: Decimal | None
    short_sample: bool
    max_drawdown: DrawdownOut | None
    current_drawdown_pct: Decimal | None
    best_day: DayExtremeOut | None
    worst_day: DayExtremeOut | None
    drawdown_series: list[DrawdownPointOut]
    monthly: list[MonthRowOut]
    recalculating: bool


class PeriodRangeOut(BaseModel):
    start: dt.date
    end: dt.date


class HoldingAccountOut(BaseModel):
    account_id: int
    name: str
    value_pln: Decimal
    gain_pln: Decimal


class HoldingOut(BaseModel):
    key: str  # i:{instrument id} | b:{bond series} | s:{savings account id}
    kind: str  # instrument | bond | savings
    ticker: str | None
    name: str
    category: str  # etf | stock | other | bonds | savings
    value_pln: Decimal
    gain_pln: Decimal
    gain_pct: Decimal | None
    accounts: list[HoldingAccountOut]


class GroupGainOut(BaseModel):
    key: str
    name: str
    value_pln: Decimal
    gain_pln: Decimal
    gain_pct: Decimal | None


class HoldingsOut(BaseModel):
    period: PeriodRangeOut | None
    items: list[HoldingOut]
    by_account: list[GroupGainOut]
    by_kind: list[GroupGainOut]
    recalculating: bool


class IncomeTotalsOut(BaseModel):
    income_pln: Decimal
    costs_pln: Decimal
    balance_pln: Decimal


class IncomeMonthOut(IncomeTotalsOut):
    month: str  # "2026-09"
    interest_pln: Decimal
    dividends_pln: Decimal
    fx_pln: Decimal
    taxes_pln: Decimal
    fees_pln: Decimal


class IncomeSourceOut(BaseModel):
    key: str  # s:{savings account id} | b:{bond series} | x:{account id} | d:{instrument id}
    kind: str  # savings | bond | xtb_interest | dividend
    name: str
    gross_pln: Decimal
    tax_pln: Decimal
    net_pln: Decimal
    taxed: bool


class IncomeCostOut(BaseModel):
    key: str  # fx | interest_tax | withholding_tax | fees
    name: str
    amount_pln: Decimal
    count: int


class IncomeOut(BaseModel):
    period: PeriodRangeOut | None
    totals: IncomeTotalsOut
    months: list[IncomeMonthOut]
    sources: list[IncomeSourceOut]
    costs: list[IncomeCostOut]
    recalculating: bool
