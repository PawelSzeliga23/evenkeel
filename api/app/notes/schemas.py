"""Notes (plan 7f-2): a thesis per holding and dated journal entries about a holding or the whole portfolio."""
import datetime as dt
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_THESIS = 5000
MAX_ENTRY = 2000
RECENT = 3  # the newest entries a holding's details show
Id = Annotated[int, Field(ge=1, le=2**31 - 1)]


def _entry_body(value: str | None) -> str | None:
    if value is None:
        return None
    value = value.strip()
    if not 1 <= len(value) <= MAX_ENTRY:
        raise ValueError(f"Wpis ma od 1 do {MAX_ENTRY} znaków.")
    return value


class NoteTargetIn(BaseModel):
    """The holding: an instrument, a bond series or a savings account (its account id)."""

    instrument_id: Id | None = None
    bond_series: str | None = Field(None, min_length=1, max_length=10)
    account_id: Id | None = None


class ThesisIn(NoteTargetIn):
    body: str

    @field_validator("body")
    @classmethod
    def _body(cls, value: str) -> str:
        value = value.strip()
        if len(value) > MAX_THESIS:
            raise ValueError(f"Teza ma najwyżej {MAX_THESIS} znaków.")
        return value


class EntryIn(NoteTargetIn):
    entry_date: dt.date | None = None
    body: str
    _check_body = field_validator("body")(_entry_body)


class EntryPatch(NoteTargetIn):
    """Any of the fields; a holding field (or `portfolio`) moves the entry."""

    entry_date: dt.date | None = None
    body: str | None = None
    portfolio: bool = False
    _check_body = field_validator("body")(_entry_body)


class ThesisOut(BaseModel):
    id: int
    key: str
    body: str
    updated_at: dt.datetime


class ThesisBodyOut(BaseModel):
    body: str
    updated_at: dt.datetime


class NoteEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    entry_date: dt.date
    body: str
    created_at: dt.datetime
    updated_at: dt.datetime


class TargetLinkOut(BaseModel):
    """Where the holding's details are: a position (account + instrument), a bond purchase or a savings account."""

    kind: Literal["position", "bond", "savings"]
    account_id: int | None = None
    instrument_id: int | None = None
    bond_holding_id: int | None = None


class TargetOut(BaseModel):
    key: str
    label: str
    sublabel: str | None
    closed: bool
    link: TargetLinkOut | None


class JournalEntryOut(NoteEntryOut):
    target: TargetOut | None  # None = the whole portfolio


class JournalOut(BaseModel):
    entries: list[JournalEntryOut]
    count: int


class HoldingNotesOut(BaseModel):
    thesis: ThesisBodyOut | None = None
    recent: list[NoteEntryOut] = []
    count: int = 0


class PriceNoteEntryOut(BaseModel):
    id: int
    entry_date: dt.date
    body: str


class PriceNoteOut(BaseModel):
    date: dt.date  # the close the entries sit on
    entries: list[PriceNoteEntryOut]
