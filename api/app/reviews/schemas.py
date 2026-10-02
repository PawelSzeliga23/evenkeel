import datetime as dt
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

MAX_CONTENT = 200_000


class ReviewIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    content: str  # Claude's answer as pasted; cleaned and checked by the router
    account_ids: list[Annotated[int, Field(ge=1, le=2**31 - 1)]] = Field(default_factory=list, max_length=50)


class ReviewListItem(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    created_at: dt.datetime
    account_label: str
    sections: int


class ReviewOut(ReviewListItem):
    content: str
