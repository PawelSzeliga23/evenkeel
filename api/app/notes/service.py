"""A holding's notes for its details (plan 7f-2): the thesis and the newest journal entries."""
from sqlalchemy import func, select

from app.models import JournalEntry, Thesis
from app.notes.keys import columns, same_target
from app.notes.schemas import RECENT, HoldingNotesOut, NoteEntryOut, ThesisBodyOut
from app.scoping import UserScope


def holding_notes(scope: UserScope, key: str) -> HoldingNotesOut:
    cols = columns(key)
    thesis = scope.db.scalar(scope.theses().where(*same_target(Thesis, cols)))
    entries = scope.journal().where(*same_target(JournalEntry, cols))
    count = scope.db.scalar(select(func.count()).select_from(entries.order_by(None).subquery())) or 0
    return HoldingNotesOut(
        thesis=None if thesis is None else ThesisBodyOut(body=thesis.body, updated_at=thesis.updated_at),
        recent=[NoteEntryOut.model_validate(entry) for entry in scope.db.scalars(entries.limit(RECENT))],
        count=count,
    )
