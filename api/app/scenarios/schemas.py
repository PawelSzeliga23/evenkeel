"""Scenarios of the simulator (spec 7b §3–4): what is stored and what the result looks like."""
import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.analytics.schemas import DayExtremeOut, DrawdownOut, PeriodOut, ReturnOut

InstrumentId = Annotated[int, Field(ge=1, le=2**31 - 1)]
Month = Annotated[str, Field(pattern=r"^\d{4}-(0[1-9]|1[0-2])$")]  # YYYY-MM
MAX_PARTS = 10
FIRST_MONTH = "2016-01"  # the catalog's prices, NBP rates and EDO issues start here (plan 7b-1)
Base = Literal["portfolio", "deposits"]


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class TargetIn(BaseModel):
    """What new money buys: an instrument from the catalog or the portfolio, or EDO bonds."""

    model_config = ConfigDict(extra="forbid")

    instrument_id: InstrumentId | None = None
    bond: Literal["EDO"] | None = None

    @model_validator(mode="after")
    def _exactly_one(self) -> Self:
        if (self.instrument_id is None) == (self.bond is None):
            raise ValueError("Wybierz instrument albo obligacje EDO.")
        return self


class ShareIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    target: TargetIn
    share_pct: Annotated[Decimal, Field(gt=0, le=100, max_digits=5, decimal_places=2)]


class ReplaceStep(BaseModel):
    """Block B: every purchase of one instrument made in another, sales and dividends following."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["replace"]
    from_instrument_id: InstrumentId
    to_instrument_id: InstrumentId

    @model_validator(mode="after")
    def _different(self) -> Self:
        if self.from_instrument_id == self.to_instrument_id:
            raise ValueError("Instrument nie może zastąpić samego siebie.")
        return self


class RecurringStep(BaseModel):
    """Block C: new money every month."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["recurring"]
    amount_pln: Annotated[Decimal, Field(gt=0, le=1_000_000, max_digits=9, decimal_places=2)]
    day_of_month: Annotated[int, Field(ge=1, le=28)]
    start: Month
    end: Month | None = None
    target: TargetIn
    ike: bool = False

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.start < FIRST_MONTH:
            raise ValueError("Dopłaty mogą zaczynać się najwcześniej w 01.2016.")
        if self.end is not None and self.end < self.start:
            raise ValueError("Koniec dopłat nie może być przed ich początkiem.")
        return self


Step = Annotated[ReplaceStep | RecurringStep, Field(discriminator="kind")]


class ScenarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=80)
    base: Base
    allocation: list[ShareIn] = Field(default_factory=list, max_length=MAX_PARTS)
    steps: list[Step] = Field(default_factory=list, max_length=MAX_PARTS)

    _strip_name = field_validator("name", mode="before")(_strip)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        replaced = [step.from_instrument_id for step in self.steps if isinstance(step, ReplaceStep)]
        if self.base == "deposits":
            if not self.allocation:
                raise ValueError("Podaj, na co idą wpłaty.")
            if sum(share.share_pct for share in self.allocation) != 100:
                raise ValueError("Udziały muszą dawać razem 100 %.")
            if replaced:
                raise ValueError("Podmiana instrumentu działa tylko na punkcie wyjścia „Mój portfel”.")
        elif self.allocation:
            raise ValueError("Podział wpłat dotyczy tylko punktu wyjścia „Moje wpłaty”.")
        if len(replaced) != len(set(replaced)):
            raise ValueError("Każdy instrument można podmienić tylko raz.")
        return self


class ScenarioPatch(BaseModel):
    """Any of the fields; the merged scenario is validated as a whole (`ScenarioIn`)."""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    base: Base | None = None
    allocation: list[ShareIn] | None = None
    steps: list[Step] | None = None


class ScenarioOut(ScenarioIn):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: dt.datetime
    updated_at: dt.datetime


class PointOut(BaseModel):
    date: dt.date
    portfolio_pln: Decimal | None  # None before the real portfolio's first day
    scenario_pln: Decimal | None  # None before the scenario's first day
    invested_pln: Decimal | None
    scenario_invested_pln: Decimal | None


class MeasuresOut(BaseModel):
    """The 7a measures of one line (as `AnalyticsOut`, without the monthly grid and the drawdown series)."""

    period: PeriodOut
    value_pln: Decimal
    invested_pln: Decimal
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


class ScenarioResultOut(BaseModel):
    points: list[PointOut]
    portfolio: MeasuresOut | None
    scenario: MeasuresOut | None
    notes: list[str]
    recalculating: bool
