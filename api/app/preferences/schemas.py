"""The owner's preferences (plan 8a): start screen and default views. Missing keys take their defaults."""
from typing import Annotated, Any, Literal, Union

from pydantic import BaseModel, ConfigDict, Field, create_model, field_validator, model_validator

Id = Annotated[int, Field(ge=1, le=2**31 - 1)]
StartScreen = Literal["dashboard", "positions", "history", "analysis"]
AccountsStart = Literal["last", "all", "fixed"]
AnalysisPeriod = Literal["1m", "3m", "1y", "ytd", "all"]
HoldingsPeriod = Literal["1d", "1w", "1m", "1y", "ytd", "all"]
ValueRange = Literal["1M", "3M", "1R", "ALL"]
PriceRange = Literal["buy", "6m", "1y", "5y", "max"]


# Plan 9: the Pulpit's tiles, in order (one layout for the phone and the computer). Plan 9b: a tile has a variant —
# its width (S, M, L) and its height in U on a computer; a variant without a digit grows with the chosen fields.
Metric = Literal["total_gain", "twr_total", "invested", "income", "cash", "day_change", "fees", "profit", "twr", "xirr",
                 "volatility", "sharpe", "max_drawdown", "current_drawdown", "best_day", "worst_day"]
TileId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,20}$")]
MAX_TILES = 40


class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SummarySettings(_Settings):
    fields: list[Metric] = Field(min_length=1, max_length=8)


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


class OperationsSettings(_Settings):
    count: Literal[3, 5, 10]


class ExtremesSettings(_Settings):
    count: Literal[2, 3, 5]
    period: HoldingsPeriod


class NoSettings(_Settings):
    pass


SETTINGS: dict[str, type[_Settings]] = {
    "summary": SummarySettings, "metric": MetricSettings, "value_chart": ValueChartSettings,
    "price_chart": PriceChartSettings, "allocation": AllocationSettings, "analysis": AnalysisSettings,
    "movers": MoversSettings, "operations": OperationsSettings, "extremes": ExtremesSettings,
}
VARIANTS: dict[str, tuple[str, ...]] = {
    "summary": ("S2", "M", "L"), "metric": ("S1", "S2"), "value_chart": ("S2", "M4", "L4", "L6"),
    "price_chart": ("S2", "M5", "L6"), "allocation": ("S2", "M4", "L4"), "analysis": ("S", "M", "L", "Lc"),
    "limits": ("S2", "M2"), "movers": ("S2", "M", "L"), "holdings": ("S3", "M3", "L5"), "income": ("S2", "M2"),
    "tags": ("S2", "M3"), "simulator": ("S2", "M4"), "review": ("S2", "M4", "L4"), "exposure": ("S2", "M3"),
    "operations": ("S2", "M", "L"), "extremes": ("S2", "M", "L"), "cash": ("S2", "M3"), "bonds": ("S2", "M3"),
    "savings": ("S2", "M3"), "journal": ("S2", "M3"),
}
# A layout saved by plan 9 (S/M/L) reads as the nearest variant; the next save stores the variant.
LEGACY_SIZES: dict[str, dict[str, str]] = {
    "summary": {"M": "M", "L": "L"}, "metric": {"S": "S2"}, "value_chart": {"M": "M4", "L": "L6"},
    "price_chart": {"M": "M5", "L": "L6"}, "allocation": {"S": "S2", "L": "L4"}, "analysis": {"M": "M", "L": "Lc"},
    "limits": {"M": "M2"}, "movers": {"M": "M", "L": "L"}, "holdings": {"M": "M3"}, "income": {"M": "M2"},
    "tags": {"M": "M3"}, "simulator": {"M": "M4"}, "review": {"M": "M4"},
}


class _Tile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @model_validator(mode="before")
    @classmethod
    def _from_size(cls, data: Any) -> Any:
        if isinstance(data, dict) and "size" in data and "variant" not in data:
            legacy = LEGACY_SIZES.get(str(data.get("kind")), {})
            if data["size"] in legacy:
                rest = {key: value for key, value in data.items() if key != "size"}
                return {**rest, "variant": legacy[data["size"]]}
        return data


def _tile(kind: str) -> type[BaseModel]:
    name = "".join(part.title() for part in kind.split("_")) + "Tile"
    return create_model(name, __base__=_Tile, id=(TileId, ...), kind=(Literal[kind], ...),
                        variant=(Literal[VARIANTS[kind]], ...), settings=(SETTINGS.get(kind, NoSettings), ...))


TILES = tuple(_tile(kind) for kind in VARIANTS)
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
