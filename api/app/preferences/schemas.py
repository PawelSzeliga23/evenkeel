"""The owner's preferences (plan 8a): start screen and default views. Missing keys take their defaults."""
from typing import Annotated, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator

Id = Annotated[int, Field(ge=1, le=2**31 - 1)]
StartScreen = Literal["dashboard", "positions", "history", "analysis"]
AccountsStart = Literal["last", "all", "fixed"]
AnalysisPeriod = Literal["1m", "3m", "1y", "ytd", "all"]
HoldingsPeriod = Literal["1d", "1w", "1m", "1y", "ytd", "all"]
ValueRange = Literal["1M", "3M", "1R", "ALL"]
PriceRange = Literal["buy", "6m", "1y", "5y", "max"]


# Plan 9: the Pulpit's tiles, in order (one layout for the phone and the computer).
Metric = Literal["total_gain", "twr_total", "invested", "income", "cash", "day_change", "fees", "profit", "twr", "xirr",
                 "volatility", "sharpe", "max_drawdown", "current_drawdown", "best_day", "worst_day"]
TileId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,20}$")]
MAX_TILES = 40


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SummarySettings(_Settings):
    fields: list[Metric] = Field(min_length=1, max_length=4)


class MetricSettings(_Settings):
    metric: Metric


class ValueChartSettings(_Settings):
    range: ValueRange


class PriceChartSettings(_Settings):
    account_id: Id | None = None
    instrument_id: Id | None = None
    range: PriceRange


class AllocationSettings(_Settings):
    by: Literal["kind", "account", "currency"]


class AnalysisSettings(_Settings):
    metrics: list[Metric] = Field(min_length=1, max_length=6)
    period: AnalysisPeriod


class MoversSettings(_Settings):
    count: Literal[3, 5, 10]


class NoSettings(_Settings):
    pass


def _tile(kind: str, sizes: tuple[str, ...], settings: type[_Settings]) -> type[BaseModel]:
    name = "".join(part.title() for part in kind.split("_")) + "Tile"
    return create_model(name, __config__=ConfigDict(extra="forbid"), id=(TileId, ...),
                        kind=(Literal[kind], ...), size=(Literal[sizes], ...), settings=(settings, ...))


TILES = (
    _tile("summary", ("M", "L"), SummarySettings),
    _tile("metric", ("S",), MetricSettings),
    _tile("value_chart", ("M", "L"), ValueChartSettings),
    _tile("price_chart", ("M", "L"), PriceChartSettings),
    _tile("allocation", ("S", "L"), AllocationSettings),
    _tile("analysis", ("M", "L"), AnalysisSettings),
    _tile("limits", ("M",), NoSettings),
    _tile("movers", ("M", "L"), MoversSettings),
    *(_tile(kind, ("M",), NoSettings) for kind in ("holdings", "income", "tags", "simulator", "review")),
)
Tile = Annotated[Union[TILES], Field(discriminator="kind")]  # noqa: UP007 - a tuple of generated models


class DashboardLayout(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version: Literal[1]
    tiles: list[Tile] = Field(max_length=MAX_TILES)

    @field_validator("tiles")
    @classmethod
    def _unique_ids(cls, tiles: list[BaseModel]) -> list[BaseModel]:
        ids = [tile.id for tile in tiles]  # type: ignore[attr-defined]
        if len(set(ids)) != len(ids):
            raise ValueError("Kafelki muszą mieć różne id.")
        return tiles


class PreferencesOut(BaseModel):
    start_screen: StartScreen = "dashboard"
    accounts_start: AccountsStart = "last"
    accounts_fixed: list[int] = []
    analysis_period: AnalysisPeriod = "all"
    holdings_period: HoldingsPeriod = "all"
    value_range: ValueRange = "1R"
    price_range: PriceRange = "buy"
    holdings_without_fixed_income: bool = False
    dashboard: DashboardLayout | None = None


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
    dashboard: DashboardLayout | None = None
