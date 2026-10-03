"""Which holding a note is about (plan 7f-2), as a key like Walory and tags use: i:{instrument}, b:{series},
s:{savings account's account}; no holding = the whole portfolio."""
import re

from sqlalchemy import ColumnElement

from app.errors import ApiError
from app.models import BondHolding, JournalEntry, SavingsAccount, Thesis
from app.notes.schemas import NoteTargetIn
from app.scoping import UserScope, not_found

PORTFOLIO = "portfolio"
MAX_ID = 2**31 - 1
_KEY = re.compile(r"^(?:i:(\d{1,10})|b:([A-Z0-9]{1,10})|s:(\d{1,10}))$")
Columns = dict[str, int | str | None]


def bad_target(message: str = "Notatka dotyczy jednego waloru albo całego portfela.") -> ApiError:
    return ApiError(422, "note_target", message)


def key_of(instrument_id: int | None, bond_series: str | None, account_id: int | None) -> str | None:
    if instrument_id is not None:
        return f"i:{instrument_id}"
    if bond_series is not None:
        return f"b:{bond_series}"
    if account_id is not None:
        return f"s:{account_id}"
    return None


def columns(key: str | None) -> Columns:
    """The note columns of a key; None or "portfolio" = no holding. A malformed key is a 422."""
    if key is None or key == PORTFOLIO:
        return {"instrument_id": None, "bond_series": None, "account_id": None}
    match = _KEY.match(key)
    if match is None:
        raise bad_target("Nieznany walor.")
    instrument, series, account = match.groups()
    number = int(instrument or account or 0)
    if number > MAX_ID:
        raise bad_target("Nieznany walor.")
    return {"instrument_id": int(instrument) if instrument else None, "bond_series": series,
            "account_id": int(account) if account else None}


def same_target(model: type[Thesis] | type[JournalEntry], cols: Columns) -> list[ColumnElement[bool]]:
    return [model.instrument_id.is_not_distinct_from(cols["instrument_id"]),
            model.bond_series.is_not_distinct_from(cols["bond_series"]),
            model.account_id.is_not_distinct_from(cols["account_id"])]


def check_target(scope: UserScope, body: NoteTargetIn, *, required: bool) -> str | None:
    """The key of the holding the body names once it is the user's (404 otherwise); None for the portfolio."""
    named = [value for value in (body.instrument_id, body.bond_series, body.account_id) if value is not None]
    if len(named) > 1 or (required and not named):
        raise bad_target()
    if body.instrument_id is not None:
        scope.get_instrument(body.instrument_id)
    elif body.bond_series is not None:
        if scope.db.scalar(scope.bond_holdings().where(BondHolding.series == body.bond_series)) is None:
            raise not_found()
    elif body.account_id is not None:
        scope.get_account(body.account_id)
        if scope.db.scalar(scope.savings_accounts().where(SavingsAccount.account_id == body.account_id)) is None:
            raise bad_target("Bez instrumentu i serii notatka może dotyczyć tylko konta oszczędnościowego.")
    return key_of(body.instrument_id, body.bond_series, body.account_id)
