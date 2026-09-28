import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

ActionType = Literal["split", "reverse_split", "conversion", "suppress"]
TICKER_PATTERN = r"^[A-Z0-9][A-Z0-9.\-]{0,39}$"  # XTB tickers: SXR8.DE, NVDA.US, CSPX.UK
Ratio = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=8)]


def _ticker(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


class CorporateActionIn(BaseModel):
    """A manual entry. `suppress` ("no event that day") has no ratio; only a conversion has a target."""

    model_config = ConfigDict(extra="forbid")

    instrument_id: Annotated[int, Field(ge=1, le=2**31 - 1)]
    type: ActionType
    effective_date: dt.date
    ratio_from: Ratio | None = None
    ratio_to: Ratio | None = None
    # Pattern on the str branch only (see InstrumentUpdate.price_symbol for why the validator wraps the union).
    target_ticker: Annotated[Annotated[str, Field(pattern=TICKER_PATTERN)] | None, BeforeValidator(_ticker)] = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.type == "suppress":
            if self.ratio_from is not None or self.ratio_to is not None:
                raise ValueError("Wyłączenie zdarzenia nie ma stosunku.")
        elif self.ratio_from is None or self.ratio_to is None:
            raise ValueError("Podaj stosunek: ratio_from i ratio_to.")
        elif self.type == "split" and self.ratio_to <= self.ratio_from:
            raise ValueError("Split zwiększa liczbę akcji: ratio_to musi być większe od ratio_from.")
        elif self.type == "reverse_split" and self.ratio_to >= self.ratio_from:
            raise ValueError("Scalenie zmniejsza liczbę akcji: ratio_to musi być mniejsze od ratio_from.")
        if (self.type == "conversion") != (self.target_ticker is not None):
            raise ValueError("Walor docelowy (target_ticker) podaje się tylko przy konwersji.")
        return self


class CorporateActionOut(BaseModel):
    id: int
    instrument_id: int
    ticker: str
    type: ActionType
    effective_date: dt.date
    ratio_from: Decimal
    ratio_to: Decimal
    target_instrument_id: int | None
    target_ticker: str | None
    source: Literal["manual", "xtb", "provider"]
    active: bool  # the entry that counts for this user on its instrument and day
    editable: bool  # the user's own manual entry
