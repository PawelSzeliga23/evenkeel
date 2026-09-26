from typing import Annotated

from pydantic import BaseModel, BeforeValidator, ConfigDict, EmailStr, Field


def _strip(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class RegisterIn(BaseModel):
    email: Annotated[EmailStr, BeforeValidator(_strip)]
    password: str = Field(min_length=10, max_length=128)
    invite_code: Annotated[str | None, BeforeValidator(_strip)] = None


class LoginIn(BaseModel):
    email: Annotated[str, BeforeValidator(_strip), Field(max_length=320)]
    password: str = Field(max_length=128)


class TokenOut(BaseModel):
    access_token: str
    token_type: str = "bearer"


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    email: str
    base_currency: str
