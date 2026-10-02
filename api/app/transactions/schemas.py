import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    ticker: str | None
    type: str
    xtb_type: str
    occurred_at: dt.datetime
    amount: Decimal
    currency: str
    quantity: Decimal | None
    price: Decimal | None
    implied_fx_rate: Decimal | None
    xtb_position_id: str | None
    external_id: str
    comment: str
    transfer_pair_id: int | None
    manual: bool = False  # set by the router from xtb_type


class TransactionIn(BaseModel):
    """A cash operation entered by hand on a `cash` account; the amount is positive, the type gives its sign."""

    model_config = ConfigDict(extra="forbid")

    account_id: Annotated[int, Field(ge=1, le=2**31 - 1)]
    type: Literal["deposit", "withdrawal", "interest", "fee"]
    amount: Annotated[Decimal, Field(gt=0, max_digits=16, decimal_places=2)]
    date: dt.date
    comment: Annotated[str, Field(max_length=200)] = ""
