"""Operations: the imported and hand-entered ledger. Only hand-entered cash operations can be written or deleted
here; each change recomputes the owner's valuations from its day in the background."""
import datetime as dt
import uuid
from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session_factory
from app.errors import ApiError
from app.models import Transaction
from app.scoping import DbId, UserScope, get_scope, not_found
from app.transactions.schemas import TransactionIn, TransactionOut
from app.valuation.service import ZONE, local_day, local_today, mark_stale, recompute_in_background

router = APIRouter(prefix="/api/transactions", tags=["transactions"])
MANUAL = "manual"  # xtb_type of a hand-entered operation
OUTGOING = frozenset({"withdrawal", "fee"})


def _out(transaction: Transaction) -> TransactionOut:
    return TransactionOut.model_validate(transaction, from_attributes=True).model_copy(
        update={"manual": transaction.xtb_type == MANUAL})


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    scope: UserScope = Depends(get_scope),
    account_id: Annotated[int | None, Query(ge=1, le=2**31 - 1)] = None,
    type: Annotated[str | None, Query(max_length=20)] = None,  # noqa: A002 — public query name
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> list[TransactionOut]:
    query = scope.transactions()
    if account_id is not None:
        query = query.where(Transaction.account_id == scope.get_account(account_id).id)
    if type is not None:
        query = query.where(Transaction.type == type)
    rows: Sequence[Transaction] = scope.db.scalars(query.limit(limit).offset(offset)).unique().all()
    return [_out(row) for row in rows]


def _saved(scope: UserScope, day: dt.date, background: BackgroundTasks, sessions: sessionmaker[Session]) -> None:
    mark_stale(scope.db, [scope.user.id], day)
    scope.db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)


@router.post("", status_code=201, response_model=TransactionOut)
def add_transaction(
    body: TransactionIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> TransactionOut:
    account = scope.get_account(body.account_id)
    if account.kind != "cash":
        raise ApiError(422, "wrong_account_kind", 'Ręczne operacje dodaje się na koncie typu „gotówka”.')
    if body.date > local_today():
        raise ApiError(422, "date_in_future", "Data operacji nie może być z przyszłości.")
    transaction = Transaction(
        account_id=account.id, type=body.type, xtb_type=MANUAL, external_id=f"{MANUAL}:{uuid.uuid4()}",
        occurred_at=dt.datetime.combine(body.date, dt.time(), ZONE),
        amount=-body.amount if body.type in OUTGOING else body.amount,
        currency=account.currency, comment=body.comment, raw={},
    )
    scope.db.add(transaction)
    scope.db.flush()
    _saved(scope, body.date, background, sessions)
    return _out(transaction)


@router.delete("/{transaction_id}", status_code=204)
def delete_transaction(
    transaction_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    transaction = scope.db.scalar(scope.transactions().where(Transaction.id == transaction_id))
    if transaction is None:
        raise not_found()
    if transaction.xtb_type != MANUAL:
        raise ApiError(409, "not_manual", "Operacji z importu XTB nie można usunąć.")
    day = local_day(transaction.occurred_at)
    scope.db.delete(transaction)
    _saved(scope, day, background, sessions)
    return Response(status_code=204)
