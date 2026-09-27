import datetime as dt
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field

SYMBOL_PATTERN = r"^[A-Z0-9.\-^=]{1,40}$"


def _normalize(value: object) -> object:
    if not isinstance(value, str):
        return value
    symbol = value.strip().upper()
    # pydantic-core's regex engine has no look-around, so "only punctuation" (e.g. ".", "..", which would
    # produce dot-segment URL paths once used as a price symbol) is rejected here instead of in the pattern.
    if symbol and not any(char.isalnum() for char in symbol):
        raise ValueError("Symbol musi zawierać przynajmniej jedną literę lub cyfrę.")
    return symbol


class InstrumentUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    # Pattern constraint applies to the str branch only: pydantic 2.13.5 raises a TypeError (not a 422)
    # if a single BeforeValidator wraps the whole `str | None` union and Field(pattern=...) sits on top of
    # it, because the pattern constraint can no longer be pushed down past the validator when value is None.
    price_symbol: Annotated[Annotated[str, Field(pattern=SYMBOL_PATTERN)] | None, BeforeValidator(_normalize)]


class InstrumentOut(BaseModel):
    id: int
    xtb_ticker: str
    name: str
    category: str | None
    currency: str | None
    price_symbol: str | None
    price_symbol_overridden: bool
    price_error: str | None
    last_price: Decimal | None
    last_price_date: dt.date | None
