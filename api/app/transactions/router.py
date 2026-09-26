from collections.abc import Sequence
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.models import Transaction
from app.scoping import UserScope, get_scope
from app.transactions.schemas import TransactionOut

router = APIRouter(prefix="/api/transactions", tags=["transactions"])


@router.get("", response_model=list[TransactionOut])
def list_transactions(
    scope: UserScope = Depends(get_scope),
    account_id: Annotated[int | None, Query(ge=1, le=2**31 - 1)] = None,
    type: Annotated[str | None, Query(max_length=20)] = None,  # noqa: A002 — public query name
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
    offset: Annotated[int, Query(ge=0, le=1_000_000)] = 0,
) -> Sequence[Transaction]:
    query = scope.transactions()
    if account_id is not None:
        query = query.where(Transaction.account_id == scope.get_account(account_id).id)
    if type is not None:
        query = query.where(Transaction.type == type)
    return scope.db.scalars(query.limit(limit).offset(offset)).unique().all()
