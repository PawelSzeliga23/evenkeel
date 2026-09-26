from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

AccountKind = Literal["broker", "bonds", "savings", "cash"]
Wrapper = Literal["regular", "ike", "ikze"]


class AccountCreate(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: AccountKind
    wrapper: Wrapper = "regular"
    broker: Literal["xtb"] | None = None
    external_account_number: str | None = Field(default=None, min_length=1, max_length=50)
    currency: str = Field(default="PLN", pattern=r"^[A-Z]{3}$")

    @model_validator(mode="after")
    def _broker_needs_account_number(self) -> Self:
        if self.broker and not self.external_account_number:
            raise ValueError("Konto brokera wymaga numeru rachunku.")
        return self


class AccountUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    wrapper: Wrapper | None = None

    @model_validator(mode="after")
    def _no_explicit_nulls(self) -> Self:
        for field in self.model_fields_set:
            if getattr(self, field) is None:
                raise ValueError(f"Pole {field} nie może być puste.")
        return self


class AccountOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    kind: AccountKind
    wrapper: Wrapper
    broker: str | None
    external_account_number: str | None
    currency: str
    created_at: datetime
