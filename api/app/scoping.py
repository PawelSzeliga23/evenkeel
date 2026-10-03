from typing import Annotated

from fastapi import Depends, Path, Query
from pydantic import Field
from sqlalchemy import Select, func, or_, select
from sqlalchemy.orm import Session

from app.auth.deps import get_current_user
from app.db import get_db
from app.errors import ApiError
from app.models import (
    Account, AiReview, BondHolding, CorporateAction, DailyValuation, ImportRecord, Instrument, JournalEntry, PositionLot,
    SavingsAccount, Scenario, Tag, Thesis, Transaction, User, XtbSnapshot,
)

# Path parameter type for any database id: keeps Postgres int4 range errors
# (which would otherwise surface as an opaque 500) as a 422 validation_error.
DbId = Annotated[int, Path(ge=1, le=2**31 - 1)]

# Query parameter `account_id`, repeatable: ?account_id=1&account_id=4. Absent = the whole portfolio.
AccountIds = Annotated[list[Annotated[int, Field(ge=1, le=2**31 - 1)]] | None, Query(alias="account_id")]


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

    def account_filter(self, ids: list[int] | None) -> frozenset[int] | None:
        """Several of the user's accounts, each counted once; None for no filter. Someone else's (or a missing)
        account is a 404, like the account itself."""
        if not ids:
            return None
        wanted = frozenset(ids)
        owned = set(self.db.scalars(
            select(Account.id).where(Account.user_id == self.user.id, Account.id.in_(wanted))))
        if owned != wanted:
            raise not_found()
        return wanted

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

    def snapshots(self) -> Select[tuple[XtbSnapshot]]:
        return (
            select(XtbSnapshot)
            .join(Account, XtbSnapshot.account_id == Account.id)
            .where(Account.user_id == self.user.id)
        )

    def imports(self) -> Select[tuple[ImportRecord]]:
        return (
            select(ImportRecord)
            .where(ImportRecord.user_id == self.user.id)
            .order_by(ImportRecord.imported_at.desc(), ImportRecord.id.desc())
        )

    def instruments(self) -> Select[tuple[Instrument]]:
        """Instruments this user has traded, holds, or converted a holding into. Instruments are shared;
        visibility is not."""
        own_accounts = select(Account.id).where(Account.user_id == self.user.id)
        traded = select(Transaction.instrument_id).where(
            Transaction.account_id.in_(own_accounts), Transaction.instrument_id.is_not(None)
        )
        held = select(PositionLot.instrument_id).where(PositionLot.account_id.in_(own_accounts))
        converted = select(CorporateAction.target_instrument_id).where(
            CorporateAction.user_id == self.user.id, CorporateAction.target_instrument_id.is_not(None)
        )
        return (
            select(Instrument)
            .where(or_(Instrument.id.in_(traded), Instrument.id.in_(held), Instrument.id.in_(converted)))
            .order_by(Instrument.xtb_ticker)
        )

    def get_instrument(self, instrument_id: int) -> Instrument:
        instrument = self.db.scalar(self.instruments().where(Instrument.id == instrument_id))
        if instrument is None:
            raise not_found()
        return instrument

    def bond_holdings(self) -> Select[tuple[BondHolding]]:
        own_accounts = select(Account.id).where(Account.user_id == self.user.id)
        return (
            select(BondHolding).where(BondHolding.account_id.in_(own_accounts))
            .order_by(BondHolding.purchase_date, BondHolding.id)
        )

    def savings_accounts(self) -> Select[tuple[SavingsAccount]]:
        own_accounts = select(Account.id).where(Account.user_id == self.user.id)
        return select(SavingsAccount).where(SavingsAccount.account_id.in_(own_accounts)).order_by(SavingsAccount.id)

    def daily_valuations(self) -> Select[tuple[DailyValuation]]:
        return select(DailyValuation).where(DailyValuation.user_id == self.user.id)

    def scenarios(self) -> Select[tuple[Scenario]]:
        return (
            select(Scenario).where(Scenario.user_id == self.user.id)
            .order_by(Scenario.updated_at.desc(), Scenario.id.desc())
        )

    def get_scenario(self, scenario_id: int) -> Scenario:
        scenario = self.db.scalar(self.scenarios().where(Scenario.id == scenario_id))
        if scenario is None:
            raise not_found()
        return scenario

    def reviews(self) -> Select[tuple[AiReview]]:
        return (
            select(AiReview).where(AiReview.user_id == self.user.id)
            .order_by(AiReview.created_at.desc(), AiReview.id.desc())
        )

    def get_review(self, review_id: int) -> AiReview:
        review = self.db.scalar(self.reviews().where(AiReview.id == review_id))
        if review is None:
            raise not_found()
        return review

    def tags(self) -> Select[tuple[Tag]]:
        return select(Tag).where(Tag.user_id == self.user.id).order_by(func.lower(Tag.name), Tag.id)

    def get_tag(self, tag_id: int) -> Tag:
        tag = self.db.scalar(self.tags().where(Tag.id == tag_id))
        if tag is None:
            raise not_found()
        return tag

    def theses(self) -> Select[tuple[Thesis]]:
        return select(Thesis).where(Thesis.user_id == self.user.id).order_by(Thesis.id)

    def journal(self) -> Select[tuple[JournalEntry]]:
        return (
            select(JournalEntry).where(JournalEntry.user_id == self.user.id)
            .order_by(JournalEntry.entry_date.desc(), JournalEntry.id.desc())
        )

    def get_entry(self, entry_id: int) -> JournalEntry:
        entry = self.db.scalar(self.journal().where(JournalEntry.id == entry_id))
        if entry is None:
            raise not_found()
        return entry


def get_scope(db: Session = Depends(get_db), user: User = Depends(get_current_user)) -> UserScope:
    return UserScope(db, user)
