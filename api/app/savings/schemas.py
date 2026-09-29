import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

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


Money = Annotated[Decimal, Field(max_digits=16, decimal_places=2)]
Wrapper = Literal["regular", "ike", "ikze"]


class SavingsFlowIn(BaseModel):
    """A deposit (+) or a withdrawal (−)."""

    model_config = ConfigDict(extra="forbid")

    date: dt.date
    amount: Money
    note: Annotated[str, Field(max_length=200)] = ""

    @model_validator(mode="after")
    def _not_zero(self) -> Self:
        if self.amount == 0:
            raise ValueError("Kwota nie może być zerem.")
        return self


class SavingsFlowOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    date: dt.date
    amount: Decimal
    note: str


class SummaryOut(BaseModel):
    balance: Decimal
    deposits: Decimal
    interest_net: Decimal
    tax: Decimal
    accrued: Decimal
    current_rate: Decimal | None


class CapitalizationOut(BaseModel):
    period_end: dt.date
    gross: Decimal
    tax: Decimal
    net: Decimal


class SavingsAccountCreate(BaseModel):
    """A new savings account with its capitalization, first rate and first deposit, created at once."""

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str, Field(min_length=1, max_length=100)]
    wrapper: Wrapper = "regular"
    capitalization: Capitalization
    annual_rate: Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]
    rate_valid_from: dt.date
    first_deposit: SavingsFlowIn

    @field_validator("name", mode="before")
    @classmethod
    def _strip(cls, value: object) -> object:
        return value.strip() if isinstance(value, str) else value

    @model_validator(mode="after")
    def _deposit_positive(self) -> Self:
        if self.first_deposit.amount < 0:
            raise ValueError("Pierwsza wpłata musi być dodatnia.")
        return self


class SavingsAccountOut(BaseModel):
    account_id: int
    capitalization: Capitalization
    rates: list[SavingsRateOut]
    balances: list[SavingsBalanceOut]
    flows: list[SavingsFlowOut]
    summary: SummaryOut
    capitalizations: list[CapitalizationOut]
