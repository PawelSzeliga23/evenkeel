import datetime as dt
from collections.abc import Sequence

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.accounts.schemas import AccountCreate, AccountOut, AccountUpdate, AccountUsageOut
from app.db import get_session_factory
from app.errors import ApiError
from app.models import (
    Account, BondHolding, ImportRecord, JournalEntry, SavingsAccount, SavingsBalance, SavingsFlow, SavingsRate, Thesis,
    Transaction,
)
from app.scoping import DbId, UserScope, get_scope
from app.valuation.service import mark_stale, recompute_in_background

router = APIRouter(prefix="/api/accounts", tags=["accounts"])


@router.get("", response_model=list[AccountOut])
def list_accounts(scope: UserScope = Depends(get_scope)) -> Sequence[Account]:
    return scope.db.scalars(scope.accounts()).all()


@router.post("", status_code=201, response_model=AccountOut)
def create_account(body: AccountCreate, scope: UserScope = Depends(get_scope)) -> Account:
    account = scope.add_account(**body.model_dump())
    try:
        scope.db.commit()
    except IntegrityError as exc:
        scope.db.rollback()
        raise ApiError(409, "account_exists", "Takie konto już istnieje.") from exc
    scope.db.refresh(account)
    return account


@router.get("/{account_id}", response_model=AccountOut)
def get_account(account_id: DbId, scope: UserScope = Depends(get_scope)) -> Account:
    return scope.get_account(account_id)


@router.get("/{account_id}/usage", response_model=AccountUsageOut)
def get_account_usage(account_id: DbId, scope: UserScope = Depends(get_scope)) -> AccountUsageOut:
    account = scope.get_account(account_id)
    db = scope.db

    def count(model: type, column: object) -> int:
        return db.scalar(select(func.count()).select_from(model).where(column == account.id)) or 0

    savings_ids = select(SavingsAccount.id).where(SavingsAccount.account_id == account.id).scalar_subquery()
    savings_entries = sum(
        db.scalar(select(func.count()).select_from(model).where(model.savings_account_id == savings_ids)) or 0
        for model in (SavingsFlow, SavingsBalance, SavingsRate)
    )
    return AccountUsageOut(
        transactions=count(Transaction, Transaction.account_id),
        imports=count(ImportRecord, ImportRecord.account_id),
        bond_holdings=count(BondHolding, BondHolding.account_id),
        savings_entries=savings_entries,
        notes=count(Thesis, Thesis.account_id) + count(JournalEntry, JournalEntry.account_id),
    )


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(
    account_id: DbId,
    body: AccountUpdate,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Account:
    account = scope.get_account(account_id)
    changes = body.model_dump(exclude_unset=True)
    wrapper_changed = "wrapper" in changes and changes["wrapper"] != account.wrapper
    for field, value in changes.items():
        setattr(account, field, value)
    if wrapper_changed:
        # Podatek od odsetek obligacji i kont zależy od IKE/IKZE — cała historia konta się zmienia.
        mark_stale(scope.db, [scope.user.id], dt.date.min)
    scope.db.commit()
    scope.db.refresh(account)
    if wrapper_changed:
        background.add_task(recompute_in_background, sessions, scope.user.id)
    return account


@router.delete("/{account_id}", status_code=204)
def delete_account(
    account_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    scope.db.delete(scope.get_account(account_id))
    # The account's rows go by cascade, but the user's totals were computed with them — recompute everything.
    mark_stale(scope.db, [scope.user.id], dt.date.min)
    scope.db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)
    return Response(status_code=204)
