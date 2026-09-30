"""A savings account's capitalization, rate history and balances copied from the bank. Each change recomputes
the owner's valuations from the affected day in the background."""
import datetime as dt
from dataclasses import asdict
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session_factory
from app.errors import ApiError
from app.models import Account, SavingsAccount, SavingsBalance, SavingsFlow, SavingsRate
from app.savings.interest import SavingsDay, rate_on, savings_days
from app.savings.schemas import (
    CapitalizationOut, SavingsAccountCreate, SavingsAccountOut, SavingsBalanceIn, SavingsBalanceOut, SavingsFlowIn,
    SavingsFlowOut, SavingsRateIn, SavingsRateOut, SavingsSettingsIn, SummaryOut,
)
from app.savings.summary import capitalizations, summarize
from app.scoping import DbId, UserScope, get_scope, not_found
from app.valuation.service import local_today, lock_user, mark_stale, recompute_in_background

router = APIRouter(prefix="/api/savings-accounts/{account_id}", tags=["savings"])
create_router = APIRouter(prefix="/api/savings-accounts", tags=["savings"])
DayQuery = Annotated[dt.date | None, Query(alias="date")]
DUPLICATE = "Dla tego dnia jest już wpis."


def _pl(value: Decimal) -> str:
    text = f"{abs(value):,.2f}".replace(",", " ").replace(".", ",")
    return f"−{text}" if value < 0 else text


def account_days(db: Session, settings: SavingsAccount, account: Account, end: dt.date) -> list[SavingsDay]:
    """The account's computed days up to `end` (balances, rates and flows from the database)."""
    balances = db.execute(select(SavingsBalance.as_of_date, SavingsBalance.balance)
                          .where(SavingsBalance.savings_account_id == settings.id)).all()
    rates = db.execute(select(SavingsRate.valid_from, SavingsRate.annual_rate)
                       .where(SavingsRate.savings_account_id == settings.id).order_by(SavingsRate.valid_from)).all()
    flows = db.execute(select(SavingsFlow.date, SavingsFlow.amount)
                       .where(SavingsFlow.savings_account_id == settings.id)).all()
    return savings_days([tuple(b) for b in balances], [tuple(r) for r in rates], settings.capitalization,
                        account.wrapper == "regular", end, [tuple(f) for f in flows])


def _check_balance(scope: UserScope, settings: SavingsAccount, status: int, code: str, message: str) -> None:
    """After a change is flushed: the balance may never drop below zero. The user's lock makes a concurrent
    change wait until this one is committed, so two withdrawals cannot both pass on the same balance."""
    lock_user(scope.db, scope.user.id)
    account = scope.get_account(settings.account_id)
    low = next((d for d in account_days(scope.db, settings, account, local_today()) if d.balance < 0), None)
    if low is not None:
        scope.db.rollback()
        raise ApiError(status, code, message.format(day=f"{low.day:%d.%m.%Y}", balance=_pl(low.balance)))


def _account(scope: UserScope, account_id: int) -> Account:
    account = scope.get_account(account_id)
    if account.kind != "savings":
        raise ApiError(422, "wrong_account_kind", 'Saldo i stawki wpisuje się na koncie typu „oszczędnościowe”.')
    return account


def _settings(scope: UserScope, account_id: int) -> SavingsAccount | None:
    return scope.db.scalar(select(SavingsAccount).where(SavingsAccount.account_id == _account(scope, account_id).id))


def _configured(scope: UserScope, account_id: int) -> SavingsAccount:
    settings = _settings(scope, account_id)
    if settings is None:
        raise ApiError(409, "savings_not_configured", "Najpierw ustaw kapitalizację konta.")
    return settings


def _out(scope: UserScope, settings: SavingsAccount, day: dt.date | None = None) -> SavingsAccountOut:
    account = scope.get_account(settings.account_id)
    rates = list(scope.db.scalars(select(SavingsRate).where(SavingsRate.savings_account_id == settings.id)
                                  .order_by(SavingsRate.valid_from)))
    balances = scope.db.scalars(select(SavingsBalance).where(SavingsBalance.savings_account_id == settings.id)
                                .order_by(SavingsBalance.as_of_date))
    flows = scope.db.scalars(select(SavingsFlow).where(SavingsFlow.savings_account_id == settings.id)
                             .order_by(SavingsFlow.date, SavingsFlow.id))
    end = day or local_today()
    days = account_days(scope.db, settings, account, end)
    current_rate = rate_on([(r.valid_from, r.annual_rate) for r in rates], end) if rates else None
    return SavingsAccountOut(
        account_id=settings.account_id, capitalization=settings.capitalization,
        rates=[SavingsRateOut.model_validate(rate) for rate in rates],
        balances=[SavingsBalanceOut.model_validate(balance) for balance in balances],
        flows=[SavingsFlowOut.model_validate(flow) for flow in flows],
        summary=SummaryOut(**asdict(summarize(days)), current_rate=current_rate),
        capitalizations=[CapitalizationOut(**asdict(c)) for c in capitalizations(days)],
    )


def _saved(scope: UserScope, day: dt.date, background: BackgroundTasks, sessions: sessionmaker[Session]) -> None:
    try:
        scope.db.flush()
    except IntegrityError:  # (account, day) is unique for rates and balances
        scope.db.rollback()
        raise ApiError(409, "duplicate_date", DUPLICATE) from None
    mark_stale(scope.db, [scope.user.id], day)
    scope.db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)


@router.get("", response_model=SavingsAccountOut)
def get_savings(account_id: DbId, day: DayQuery = None, scope: UserScope = Depends(get_scope)) -> SavingsAccountOut:
    settings = _settings(scope, account_id)
    if settings is None:
        raise not_found()
    return _out(scope, settings, day)


@router.put("", response_model=SavingsAccountOut)
def set_savings(
    account_id: DbId,
    body: SavingsSettingsIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsAccountOut:
    if _account(scope, account_id).currency != "PLN":
        raise ApiError(422, "wrong_currency", "Obligacje i konta oszczędnościowe prowadzi się w PLN.")
    settings = _settings(scope, account_id)
    if settings is None:
        settings = SavingsAccount(account_id=account_id, capitalization=body.capitalization)
        scope.db.add(settings)
    settings.capitalization = body.capitalization
    _saved(scope, dt.date.min, background, sessions)  # the whole history follows the capitalization
    return _out(scope, settings)


@router.post("/rates", status_code=201, response_model=SavingsRateOut)
def add_rate(
    account_id: DbId,
    body: SavingsRateIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsRate:
    rate = SavingsRate(savings_account_id=_configured(scope, account_id).id, valid_from=body.valid_from,
                       annual_rate=body.annual_rate)
    scope.db.add(rate)
    _saved(scope, body.valid_from, background, sessions)
    return rate


@router.post("/balances", status_code=201, response_model=SavingsBalanceOut)
def add_balance(
    account_id: DbId,
    body: SavingsBalanceIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsBalance:
    settings = _configured(scope, account_id)
    if body.as_of_date > local_today():
        raise ApiError(422, "balance_in_future", "Saldo może być najpóźniej z dzisiaj.")
    balance = SavingsBalance(savings_account_id=settings.id, as_of_date=body.as_of_date, balance=body.balance)
    scope.db.add(balance)
    _saved(scope, body.as_of_date, background, sessions)
    return balance


@router.delete("/rates/{entry_id}", status_code=204)
def delete_rate(
    account_id: DbId,
    entry_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    settings = _configured(scope, account_id)
    rate = scope.db.scalar(select(SavingsRate).where(SavingsRate.id == entry_id,
                                                     SavingsRate.savings_account_id == settings.id))
    if rate is None:
        raise not_found()
    day = rate.valid_from
    scope.db.delete(rate)
    _saved(scope, day, background, sessions)
    return Response(status_code=204)


@router.delete("/balances/{entry_id}", status_code=204)
def delete_balance(
    account_id: DbId,
    entry_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    settings = _configured(scope, account_id)
    balance = scope.db.scalar(select(SavingsBalance).where(SavingsBalance.id == entry_id,
                                                           SavingsBalance.savings_account_id == settings.id))
    if balance is None:
        raise not_found()
    day = balance.as_of_date
    scope.db.delete(balance)
    _saved(scope, day, background, sessions)
    return Response(status_code=204)


@router.post("/flows", status_code=201, response_model=SavingsFlowOut)
def add_flow(
    account_id: DbId,
    body: SavingsFlowIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsFlow:
    settings = _configured(scope, account_id)
    if body.date > local_today():
        raise ApiError(422, "date_in_future", "Data wpłaty nie może być z przyszłości.")
    flow = SavingsFlow(savings_account_id=settings.id, date=body.date, amount=body.amount, note=body.note)
    scope.db.add(flow)
    scope.db.flush()
    _check_balance(scope, settings, 422, "insufficient_balance",
                   "Wypłata jest większa niż saldo: {day} saldo spadłoby do {balance} zł.")
    _saved(scope, body.date, background, sessions)
    return flow


@router.delete("/flows/{entry_id}", status_code=204)
def delete_flow(
    account_id: DbId,
    entry_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    settings = _configured(scope, account_id)
    flow = scope.db.scalar(select(SavingsFlow).where(SavingsFlow.id == entry_id,
                                                     SavingsFlow.savings_account_id == settings.id))
    if flow is None:
        raise not_found()
    day = flow.date
    scope.db.delete(flow)
    scope.db.flush()
    _check_balance(scope, settings, 409, "flow_needed",
                   "Bez tego wpisu saldo spadłoby poniżej zera: {day} do {balance} zł. Najpierw usuń późniejszą "
                   "wypłatę.")
    _saved(scope, day, background, sessions)
    return Response(status_code=204)


@create_router.post("", status_code=201, response_model=SavingsAccountOut)
def create_savings_account(
    body: SavingsAccountCreate,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsAccountOut:
    if body.first_deposit.date > local_today():
        raise ApiError(422, "date_in_future", "Data wpłaty nie może być z przyszłości.")
    account = scope.add_account(name=body.name, kind="savings", wrapper=body.wrapper, currency="PLN")
    scope.db.flush()
    settings = SavingsAccount(account_id=account.id, capitalization=body.capitalization)
    scope.db.add(settings)
    scope.db.flush()
    scope.db.add(SavingsRate(savings_account_id=settings.id, valid_from=body.rate_valid_from,
                             annual_rate=body.annual_rate))
    scope.db.add(SavingsFlow(savings_account_id=settings.id, date=body.first_deposit.date,
                             amount=body.first_deposit.amount, note=body.first_deposit.note))
    _saved(scope, min(body.rate_valid_from, body.first_deposit.date), background, sessions)
    return _out(scope, settings)
