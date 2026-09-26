from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class TransactionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    ticker: str | None
    type: str
    xtb_type: str
    occurred_at: datetime
    amount: Decimal
    currency: str
    quantity: Decimal | None
    price: Decimal | None
    implied_fx_rate: Decimal | None
    xtb_position_id: str | None
    external_id: str
    comment: str
    transfer_pair_id: int | None
