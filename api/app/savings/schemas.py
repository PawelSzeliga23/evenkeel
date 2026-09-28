import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Capitalization = Literal["daily", "monthly", "quarterly"]


class SavingsSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capitalization: Capitalization


class SavingsRateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_from: dt.date
    annual_rate: Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]  # percent a year


class SavingsBalanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: dt.date
    balance: Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2)]


class SavingsRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    valid_from: dt.date
    annual_rate: Decimal


class SavingsBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    as_of_date: dt.date
    balance: Decimal


class SavingsAccountOut(BaseModel):
    account_id: int
    capitalization: Capitalization
    rates: list[SavingsRateOut]
    balances: list[SavingsBalanceOut]
