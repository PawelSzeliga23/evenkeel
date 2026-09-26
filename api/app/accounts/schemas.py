from datetime import datetime
from typing import Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

AccountKind = Literal["broker", "bonds", "savings", "cash"]
Wrapper = Literal["regular", "ike", "ikze"]


def _strip_str(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=100)
    kind: AccountKind
    wrapper: Wrapper = "regular"
    broker: Literal["xtb"] | None = None
    external_account_number: str | None = Field(default=None, min_length=1, max_length=50)
    currency: str = Field(default="PLN", pattern=r"^[A-Z]{3}$")

    _strip_name = field_validator("name", mode="before")(_strip_str)

    @model_validator(mode="after")
    def _broker_consistency(self) -> Self:
        if self.kind == "broker" and not self.broker:
            raise ValueError("Konto typu broker wymaga wskazania brokera.")
        if self.broker and self.kind != "broker":
            raise ValueError("Pole broker jest dozwolone tylko dla konta typu broker.")
        if self.broker and not self.external_account_number:
            raise ValueError("Konto brokera wymaga numeru rachunku.")
        return self


class AccountUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str | None = Field(default=None, min_length=1, max_length=100)
    wrapper: Wrapper | None = None

    _strip_name = field_validator("name", mode="before")(_strip_str)

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
