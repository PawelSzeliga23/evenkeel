"""A savings account's capitalization, rate history and balances copied from the bank. Each change recomputes
the owner's valuations from the affected day in the background."""
import datetime as dt

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session_factory
from app.errors import ApiError
from app.models import Account, SavingsAccount, SavingsBalance, SavingsRate
from app.savings.schemas import (
    SavingsAccountOut, SavingsBalanceIn, SavingsBalanceOut, SavingsRateIn, SavingsRateOut, SavingsSettingsIn,
)
from app.scoping import DbId, UserScope, get_scope, not_found
from app.valuation.service import local_today, mark_stale, recompute_in_background

router = APIRouter(prefix="/api/savings-accounts/{account_id}", tags=["savings"])
DUPLICATE = "Dla tego dnia jest już wpis."


def _account(scope: UserScope, account_id: int) -> Account:
    account = scope.get_account(account_id)
    if account.kind != "savings":
        raise ApiError(422, "wrong_account_kind", 'Saldo i stawki wpisuje się na koncie typu "oszczędnościowe".')
    return account


def _settings(scope: UserScope, account_id: int) -> SavingsAccount | None:
    return scope.db.scalar(select(SavingsAccount).where(SavingsAccount.account_id == _account(scope, account_id).id))


def _configured(scope: UserScope, account_id: int) -> SavingsAccount:
    settings = _settings(scope, account_id)
    if settings is None:
        raise ApiError(409, "savings_not_configured", "Najpierw ustaw kapitalizację konta.")
    return settings


def _out(scope: UserScope, settings: SavingsAccount) -> SavingsAccountOut:
    rates = scope.db.scalars(select(SavingsRate).where(SavingsRate.savings_account_id == settings.id)
                             .order_by(SavingsRate.valid_from))
    balances = scope.db.scalars(select(SavingsBalance).where(SavingsBalance.savings_account_id == settings.id)
                                .order_by(SavingsBalance.as_of_date))
    return SavingsAccountOut(
        account_id=settings.account_id, capitalization=settings.capitalization,
        rates=[SavingsRateOut.model_validate(rate) for rate in rates],
        balances=[SavingsBalanceOut.model_validate(balance) for balance in balances],
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
def get_savings(account_id: DbId, scope: UserScope = Depends(get_scope)) -> SavingsAccountOut:
    settings = _settings(scope, account_id)
    if settings is None:
        raise not_found()
    return _out(scope, settings)


@router.put("", response_model=SavingsAccountOut)
def set_savings(
    account_id: DbId,
    body: SavingsSettingsIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsAccountOut:
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
