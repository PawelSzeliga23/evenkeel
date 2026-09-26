from collections.abc import Sequence

from fastapi import APIRouter, Depends, Response
from sqlalchemy.exc import IntegrityError

from app.accounts.schemas import AccountCreate, AccountOut, AccountUpdate
from app.errors import ApiError
from app.models import Account
from app.scoping import DbId, UserScope, get_scope

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


@router.patch("/{account_id}", response_model=AccountOut)
def update_account(account_id: DbId, body: AccountUpdate, scope: UserScope = Depends(get_scope)) -> Account:
    account = scope.get_account(account_id)
    for field, value in body.model_dump(exclude_unset=True).items():
        setattr(account, field, value)
    scope.db.commit()
    scope.db.refresh(account)
    return account


@router.delete("/{account_id}", status_code=204)
def delete_account(account_id: DbId, scope: UserScope = Depends(get_scope)) -> Response:
    scope.db.delete(scope.get_account(account_id))
    scope.db.commit()
    return Response(status_code=204)
