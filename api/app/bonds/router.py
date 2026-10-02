"""Treasury bond purchases (the owner's) and bond series (shared). Each change recomputes the owner's valuations
from the purchase day in the background."""
import datetime as dt
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.bonds import edo
from app.bonds.schemas import (
    DEFAULT_EDO_FEE, BondDetailOut, BondIn, BondOut, BondSeriesIn, BondSeriesOut, BondUpdate,
)
from app.bonds.service import bond_detail
from app.db import get_session_factory
from app.errors import ApiError
from app.models import BondHolding, BondSeries
from app.scoping import DbId, UserScope, get_scope, not_found
from app.tags.lookup import TagLookup
from app.valuation.service import load_fixed_income, local_today, mark_stale, recompute_in_background

router = APIRouter(prefix="/api", tags=["bonds"])

DayQuery = Annotated[dt.date | None, Query(alias="date")]
EDO_MONTHS = 120


def _new_series(name: str, first_period_rate: Decimal, margin: Decimal, fee: Decimal) -> BondSeries:
    """An EDO series from its name: EDOmmyy matures in month mm of 20yy and was sold ten years earlier."""
    month, year = int(name[3:5]), 2000 + int(name[5:7])
    return BondSeries(series=name, bond_type="EDO", issue_month=dt.date(year - edo.YEARS, month, 1),
                      maturity_months=EDO_MONTHS, first_period_rate=first_period_rate, margin=margin,
                      early_redemption_fee=fee, interest_mode="capitalized", rate_basis="cpi")


def _series_exists(name: str) -> ApiError:
    return ApiError(409, "series_exists", f"Seria {name} już jest w aplikacji.")


def _holding(scope: UserScope, holding_id: int) -> BondHolding:
    holding = scope.db.scalar(scope.bond_holdings().where(BondHolding.id == holding_id))
    if holding is None:
        raise not_found()
    return holding


def _saved(scope: UserScope, day: dt.date, background: BackgroundTasks, sessions: sessionmaker[Session]) -> None:
    mark_stale(scope.db, [scope.user.id], day)
    scope.db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)


def _detail(scope: UserScope, holding: BondHolding, day: dt.date) -> BondDetailOut:
    detail = bond_detail(holding, scope.get_account(holding.account_id), load_fixed_income(scope), day)
    detail.tags = TagLookup(scope).on(f"b:{holding.series}", holding.account_id)
    return detail


@router.get("/bond-series", response_model=list[BondSeriesOut])
def list_series(scope: UserScope = Depends(get_scope)) -> list[BondSeries]:
    return list(scope.db.scalars(select(BondSeries).order_by(BondSeries.issue_month, BondSeries.series)))


@router.post("/bond-series", status_code=201, response_model=BondSeriesOut)
def add_series(body: BondSeriesIn, scope: UserScope = Depends(get_scope)) -> BondSeries:
    if scope.db.get(BondSeries, body.series) is not None:
        raise _series_exists(body.series)
    series = _new_series(body.series, body.first_period_rate, body.margin, body.early_redemption_fee)
    scope.db.add(series)
    try:
        scope.db.commit()
    except IntegrityError:  # the same series was added concurrently
        scope.db.rollback()
        raise _series_exists(body.series) from None
    return series


@router.get("/bonds", response_model=list[BondOut])
def list_bonds(scope: UserScope = Depends(get_scope), day: DayQuery = None) -> list[BondOut]:
    fixed = load_fixed_income(scope)
    accounts = {account.id: account for account in scope.db.scalars(scope.accounts())}
    on = day or local_today()
    return [bond_detail(h, accounts[h.account_id], fixed, on).bond
            for h in scope.db.scalars(scope.bond_holdings()) if h.purchase_date <= on]


@router.get("/bonds/{holding_id}", response_model=BondDetailOut)
def get_bond(holding_id: DbId, scope: UserScope = Depends(get_scope), day: DayQuery = None) -> BondDetailOut:
    holding = _holding(scope, holding_id)
    on = day or local_today()
    if on < holding.purchase_date:
        raise ApiError(422, "date_before_purchase", "Wybrany dzień jest wcześniejszy niż data zakupu obligacji.")
    return _detail(scope, holding, on)


@router.post("/bonds", status_code=201, response_model=BondOut)
def buy_bonds(
    body: BondIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> BondOut:
    account = scope.get_account(body.account_id)
    if account.kind != "bonds":
        raise ApiError(422, "wrong_account_kind", 'Obligacje zapisuje się na koncie typu „obligacje”.')
    if account.currency != "PLN":
        raise ApiError(422, "wrong_currency", "Obligacje i konta oszczędnościowe prowadzi się w PLN.")
    if body.purchase_date > local_today():
        raise ApiError(422, "purchase_in_future", "Data zakupu nie może być z przyszłości.")
    name = edo.series_name(body.purchase_date)
    if scope.db.get(BondSeries, name) is None:
        if body.first_period_rate is None or body.margin is None:
            raise ApiError(422, "series_unknown",
                           f"Serii {name} nie ma jeszcze w aplikacji — podaj oprocentowanie 1. roku i marżę.",
                           {"series": name})
        scope.db.add(_new_series(name, body.first_period_rate, body.margin, DEFAULT_EDO_FEE))
        try:
            scope.db.flush()
        except IntegrityError:  # the same series was added concurrently
            scope.db.rollback()
            raise _series_exists(name) from None
    holding = BondHolding(account_id=account.id, bond_type=body.bond_type, series=name, quantity=body.quantity,
                          purchase_date=body.purchase_date, note=body.note)
    scope.db.add(holding)
    scope.db.flush()
    _saved(scope, holding.purchase_date, background, sessions)
    return _detail(scope, holding, local_today()).bond


@router.patch("/bonds/{holding_id}", response_model=BondOut)
def update_bonds(
    holding_id: DbId,
    body: BondUpdate,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> BondOut:
    holding = _holding(scope, holding_id)
    if "redeemed_at" in body.model_fields_set and body.redeemed_at is not None:
        maturity = edo.anniversary(holding.purchase_date, edo.YEARS)
        if not holding.purchase_date <= body.redeemed_at < maturity:
            raise ApiError(422, "bad_redemption_date",
                           "Data wcześniejszego wykupu musi przypadać od dnia zakupu do dnia przed terminem wykupu.")
    for name in body.model_fields_set:
        setattr(holding, name, getattr(body, name))
    _saved(scope, holding.purchase_date, background, sessions)
    return _detail(scope, holding, local_today()).bond


@router.delete("/bonds/{holding_id}", status_code=204)
def delete_bonds(
    holding_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    holding = _holding(scope, holding_id)
    day = holding.purchase_date
    scope.db.delete(holding)
    _saved(scope, day, background, sessions)
    return Response(status_code=204)
