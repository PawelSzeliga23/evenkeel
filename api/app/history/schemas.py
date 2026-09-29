import datetime as dt
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel

Kind = Literal["transaction", "bond_purchase", "bond_payout", "savings_flow", "savings_interest"]


class DeleteTarget(BaseModel):
    target: Literal["transaction", "bond", "savings_flow"]
    id: int


class HistoryItem(BaseModel):
    id: str  # stable: tx:12, bond:7:purchase, bond:7:payout, sflow:3, scap:5:2026-09
    kind: Kind
    type: str  # a transaction type, or bond_purchase / bond_payout / savings_deposit / savings_withdrawal /
    #            savings_interest
    date: dt.date
    account_id: int
    account_name: str
    instrument_id: int | None = None
    ticker: str | None = None
    name: str | None = None  # instrument name or bond series
    quantity: Decimal | None = None
    price: Decimal | None = None
    amount: Decimal  # in the account's currency: − money going out (buy, bond purchase, withdrawal), + coming in
    currency: str
    amount_pln: Decimal | None  # None for an account in another currency
    tax: Decimal | None = None  # withheld from credited savings interest
    note: str = ""
    delete: DeleteTarget | None = None


class HistoryPage(BaseModel):
    items: list[HistoryItem]
    next_cursor: str | None
