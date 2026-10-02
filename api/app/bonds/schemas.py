import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.tags.schemas import TagOnOut

SERIES_PATTERN = r"^EDO(0[1-9]|1[0-2])\d{2}$"
DEFAULT_EDO_FEE = Decimal("3.00")  # zł per bond for purchases from 1 September 2024
Rate = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]


class BondSeriesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: str = Field(pattern=SERIES_PATTERN)
    first_period_rate: Rate
    margin: Rate
    early_redemption_fee: Annotated[Decimal, Field(ge=0, max_digits=6, decimal_places=2)] = DEFAULT_EDO_FEE


class BondSeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    series: str
    bond_type: str
    issue_month: dt.date
    maturity_months: int
    first_period_rate: Decimal
    margin: Decimal
    early_redemption_fee: Decimal


class BondIn(BaseModel):
    """A purchase. The series follows from the purchase day; the rates are needed only for a series the
    application does not know yet (a known series keeps its stored rates)."""

    model_config = ConfigDict(extra="forbid")

    account_id: Annotated[int, Field(ge=1, le=2**31 - 1)]
    bond_type: Literal["EDO"]
    quantity: Annotated[int, Field(ge=1, le=1_000_000)]
    purchase_date: dt.date
    first_period_rate: Rate | None = None
    margin: Rate | None = None
    note: Annotated[str, Field(max_length=500)] = ""


class BondUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Annotated[int, Field(ge=1, le=1_000_000)] | None = None
    redeemed_at: dt.date | None = None  # null cancels an early redemption
    note: Annotated[str, Field(max_length=500)] | None = None

    @model_validator(mode="after")
    def _no_null_except_redemption(self) -> Self:
        for name in ("quantity", "note"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"Pole {name} nie może być puste.")
        return self


class BondOut(BaseModel):
    id: int
    account_id: int
    account_name: str
    bond_type: str
    series: str
    quantity: int
    purchase_date: dt.date
    redeemed_at: dt.date | None
    maturity_date: dt.date
    note: str
    status: Literal["active", "redeemed", "matured"]
    value_pln: Decimal  # net of tax on the day; 0 once paid out
    flags: list[str]


class PeriodOut(BaseModel):
    number: int
    start: dt.date
    end: dt.date
    rate: Decimal
    estimated: bool


class BondDetailOut(BaseModel):
    bond: BondOut
    value_per_bond: Decimal  # before tax
    redemption_today_pln: Decimal | None  # early redemption on the day (None once paid out)
    periods: list[PeriodOut]
    tags: list[TagOnOut] = []
