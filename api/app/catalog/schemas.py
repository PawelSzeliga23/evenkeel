import datetime as dt
import re

from pydantic import BaseModel, field_validator

TICKER = re.compile(r"^[A-Z0-9][A-Z0-9.\-^=]{0,39}$")


class CatalogItemOut(BaseModel):
    id: int
    ticker: str
    name: str
    currency: str | None
    group: str
    accumulating: bool | None
    prices_from: dt.date | None


class CatalogGroupOut(BaseModel):
    group: str
    items: list[CatalogItemOut]


class CatalogAddIn(BaseModel):
    ticker: str

    @field_validator("ticker")
    @classmethod
    def normalized(cls, value: str) -> str:
        ticker = value.strip().upper()
        if not TICKER.match(ticker):
            raise ValueError("Podaj ticker, np. VWCE.DE albo AAPL.US.")
        return ticker
