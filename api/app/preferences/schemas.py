"""The owner's preferences (plan 8a): start screen and default views. Missing keys take their defaults."""
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Id = Annotated[int, Field(ge=1, le=2**31 - 1)]
StartScreen = Literal["dashboard", "positions", "history", "analysis"]
AccountsStart = Literal["last", "all", "fixed"]
AnalysisPeriod = Literal["1m", "3m", "1y", "ytd", "all"]
HoldingsPeriod = Literal["1d", "1w", "1m", "1y", "ytd", "all"]
ValueRange = Literal["1M", "3M", "1R", "ALL"]
PriceRange = Literal["buy", "6m", "1y", "5y", "max"]


class PreferencesOut(BaseModel):
    start_screen: StartScreen = "dashboard"
    accounts_start: AccountsStart = "last"
    accounts_fixed: list[int] = []
    analysis_period: AnalysisPeriod = "all"
    holdings_period: HoldingsPeriod = "all"
    value_range: ValueRange = "1R"
    price_range: PriceRange = "buy"
    holdings_without_fixed_income: bool = False


class PreferencesPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    start_screen: StartScreen | None = None
    accounts_start: AccountsStart | None = None
    accounts_fixed: list[Id] | None = Field(None, max_length=50)
    analysis_period: AnalysisPeriod | None = None
    holdings_period: HoldingsPeriod | None = None
    value_range: ValueRange | None = None
    price_range: PriceRange | None = None
    holdings_without_fixed_income: bool | None = None
