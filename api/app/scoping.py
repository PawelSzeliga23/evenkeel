from typing import Annotated

from fastapi import Depends, Path
from sqlalchemy import Select, or_, select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import Account, ImportRecord, Instrument, PositionLot, Transaction, User

# Path parameter type for any database id: keeps Postgres int4 range errors
# (which would otherwise surface as an opaque 500) as a 422 validation_error.
DbId = Annotated[int, Path(ge=1, le=2**31 - 1)]


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

    def add_account(self, **fields: object) -> Account:
        """Creates an account owned by this scope's user; does not commit."""
        account = Account(user_id=self.user.id, **fields)
        self.db.add(account)
        return account

    def broker_account(self, broker: str, number: str) -> Account | None:
        return self.db.scalar(
            self.accounts().where(Account.broker == broker, Account.external_account_number == number)
        )

    def transactions(self) -> Select[tuple[Transaction]]:
        return (
            select(Transaction)
            .join(Account, Transaction.account_id == Account.id)
            .where(Account.user_id == self.user.id)
            .order_by(Transaction.occurred_at.desc(), Transaction.id.desc())
        )

    def imports(self) -> Select[tuple[ImportRecord]]:
        return (
            select(ImportRecord)
            .where(ImportRecord.user_id == self.user.id)
            .order_by(ImportRecord.imported_at.desc(), ImportRecord.id.desc())
        )

    def instruments(self) -> Select[tuple[Instrument]]:
        """Instruments this user has traded or holds. Instruments are shared; visibility is not."""
        own_accounts = select(Account.id).where(Account.user_id == self.user.id)
        traded = select(Transaction.instrument_id).where(
            Transaction.account_id.in_(own_accounts), Transaction.instrument_id.is_not(None)
        )
        held = select(PositionLot.instrument_id).where(PositionLot.account_id.in_(own_accounts))
        return (
            select(Instrument)
            .where(or_(Instrument.id.in_(traded), Instrument.id.in_(held)))
            .order_by(Instrument.xtb_ticker)
        )

    def get_instrument(self, instrument_id: int) -> Instrument:
        instrument = self.db.scalar(self.instruments().where(Instrument.id == instrument_id))
        if instrument is None:
            raise not_found()
        return instrument


def get_scope(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserScope:
    return UserScope(db, user)
