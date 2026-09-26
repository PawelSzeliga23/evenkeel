from fastapi import Depends
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Account, User


def not_found() -> ApiError:
    return ApiError(404, "not_found", "Nie znaleziono.")


class UserScope:
    """The only way endpoints reach user-owned data: every query here is limited to one user.

    Another user's record is reported exactly like a missing one, so IDs leak nothing.
    """

    def __init__(self, db: Session, user: User) -> None:
        self.db = db
        self.user = user

    def accounts(self) -> Select[tuple[Account]]:
        return select(Account).where(Account.user_id == self.user.id).order_by(Account.id)

    def get_account(self, account_id: int) -> Account:
        account = self.db.scalar(self.accounts().where(Account.id == account_id))
        if account is None:
            raise not_found()
        return account


def get_scope(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserScope:
    return UserScope(db, user)
