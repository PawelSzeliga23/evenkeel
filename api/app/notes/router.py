"""Notes (plan 7f-2): theses and the journal. Someone else's entry or holding is a 404 like a missing one."""
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy.exc import IntegrityError

from app.errors import ApiError
from app.models import JournalEntry, Thesis
from app.notes.keys import bad_target, check_target, columns, same_target
from app.notes.schemas import EntryIn, EntryPatch, JournalEntryOut, JournalOut, TargetOut, ThesisIn, ThesisOut
from app.notes.targets import Targets, entry_out
from app.scoping import DbId, UserScope, get_scope
from app.valuation.service import local_today

router = APIRouter(prefix="/api", tags=["notes"])
EARLIEST = dt.date(2000, 1, 1)
HOLDING_FIELDS = {"instrument_id", "bond_series", "account_id"}
TargetQuery = Annotated[str | None, Query(max_length=20)]


def _day(day: dt.date) -> dt.date:
    if day > local_today():
        raise ApiError(422, "entry_date", "Data wpisu nie może być z przyszłości.")
    if day < EARLIEST:
        raise ApiError(422, "entry_date", "Data wpisu nie może być sprzed 2000 roku.")
    return day


@router.put("/theses", response_model=ThesisOut, responses={204: {"description": "Pusta teza została usunięta."}})
def save_thesis(body: ThesisIn, scope: UserScope = Depends(get_scope)) -> ThesisOut | Response:
    key = check_target(scope, body, required=True)
    cols = columns(key)
    find = scope.theses().where(*same_target(Thesis, cols))
    thesis = scope.db.scalar(find)
    if not body.body:
        if thesis is not None:
            scope.db.delete(thesis)
            scope.db.commit()
        return Response(status_code=204)
    if thesis is None:
        scope.db.add(Thesis(user_id=scope.user.id, body=body.body, **cols))
    else:
        thesis.body = body.body
    try:
        scope.db.commit()
    except IntegrityError:  # the same holding's thesis was created concurrently: this text replaces it
        scope.db.rollback()
        existing = scope.db.scalar(find)
        if existing is None:
            raise
        existing.body = body.body
        scope.db.commit()
    saved = scope.db.scalar(find)
    assert saved is not None and key is not None
    return ThesisOut(id=saved.id, key=key, body=saved.body, updated_at=saved.updated_at)


@router.get("/journal", response_model=JournalOut)
def list_journal(target: TargetQuery = None, scope: UserScope = Depends(get_scope)) -> JournalOut:
    query = scope.journal()
    if target is not None:
        query = query.where(*same_target(JournalEntry, columns(target)))
    entries = list(scope.db.scalars(query))
    if not entries:
        return JournalOut(entries=[], count=0)
    targets = Targets(scope, local_today())
    return JournalOut(entries=[entry_out(e, targets) for e in entries], count=len(entries))


@router.get("/journal/targets", response_model=list[TargetOut])
def journal_targets(scope: UserScope = Depends(get_scope)) -> list[TargetOut]:
    return Targets(scope, local_today()).choices()


@router.post("/journal", response_model=JournalEntryOut, status_code=201)
def add_entry(body: EntryIn, scope: UserScope = Depends(get_scope)) -> JournalEntryOut:
    key = check_target(scope, body, required=False)
    entry = JournalEntry(user_id=scope.user.id, entry_date=_day(body.entry_date or local_today()), body=body.body,
                         **columns(key))
    scope.db.add(entry)
    scope.db.commit()
    scope.db.refresh(entry)
    return entry_out(entry, Targets(scope, local_today()))


@router.patch("/journal/{entry_id}", response_model=JournalEntryOut)
def update_entry(entry_id: DbId, body: EntryPatch, scope: UserScope = Depends(get_scope)) -> JournalEntryOut:
    entry = scope.get_entry(entry_id)
    moved = HOLDING_FIELDS & body.model_fields_set
    if body.portfolio and moved:
        raise bad_target()
    if body.portfolio or moved:
        key = None if body.portfolio else check_target(scope, body, required=True)
        for column, value in columns(key).items():
            setattr(entry, column, value)
    if body.entry_date is not None:
        entry.entry_date = _day(body.entry_date)
    if body.body is not None:
        entry.body = body.body
    scope.db.commit()
    scope.db.refresh(entry)
    return entry_out(entry, Targets(scope, local_today()))


@router.delete("/journal/{entry_id}", status_code=204)
def delete_entry(entry_id: DbId, scope: UserScope = Depends(get_scope)) -> Response:
    scope.db.delete(scope.get_entry(entry_id))
    scope.db.commit()
    return Response(status_code=204)
