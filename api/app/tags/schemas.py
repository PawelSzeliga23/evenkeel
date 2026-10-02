from typing import Annotated

from pydantic import BaseModel, Field, field_validator

PALETTE = ("#F0A43A", "#7FB6E6", "#5DB98A", "#C98BD9", "#E0C36A", "#E0676E", "#6FC7C0", "#B0B7C3")
MAX_NAME = 30
Id = Annotated[int, Field(ge=1, le=2**31 - 1)]


def _name(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not 1 <= len(value) <= MAX_NAME:
        raise ValueError(f"Nazwa tagu ma od 1 do {MAX_NAME} znaków.")
    return value


def _color(value: str | None) -> str | None:
    if value is not None and value.upper() not in PALETTE:
        raise ValueError("Wybierz kolor z palety.")
    return value.upper() if value else None


class TagIn(BaseModel):
    name: str
    color: str | None = None
    _check_name = field_validator("name")(_name)
    _check_color = field_validator("color")(_color)


class TagPatch(BaseModel):
    name: str | None = None
    color: str | None = None
    _check_name = field_validator("name")(_name)
    _check_color = field_validator("color")(_color)


class TagOut(BaseModel):
    id: int
    name: str
    color: str
    links: int


class TagLinkIn(BaseModel):
    instrument_id: Id | None = None
    bond_series: str | None = Field(None, max_length=10)
    account_id: Id | None = None


class TagLinkOut(BaseModel):
    id: int
    tag_id: int
    instrument_id: int | None
    bond_series: str | None
    account_id: int | None


class TagOnOut(BaseModel):
    """A tag as it shows on a holding: `own` = only on this account."""

    id: int
    name: str
    color: str
    link_id: int
    own: bool
