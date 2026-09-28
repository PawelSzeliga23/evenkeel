"""Corporate actions: shared entries (provider, XTB) are read-only; a user's manual entries apply to their own
accounts only and trigger a recompute of their valuations."""
import datetime as dt
import logging
from collections.abc import Iterable
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy import Select, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.corporate_actions.schemas import CorporateActionIn, CorporateActionOut
from app.db import get_session_factory
from app.errors import ApiError
from app.models import CorporateAction, Instrument
from app.scoping import DbId, UserScope, get_scope, not_found
from app.valuation.actions import action_of, winning
from app.valuation.service import mark_stale, recompute_in_background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/corporate-actions", tags=["corporate-actions"])

InstrumentFilter = Annotated[int | None, Query(ge=1, le=2**31 - 1)]
ONE = Decimal("1.00000000")  # full NUMERIC(18,8) scale: the session never re-reads it from the DB after commit
DUPLICATE = "Masz już własny wpis dla tego waloru w tym dniu."


def _visible(scope: UserScope, instrument_ids: object) -> Select[tuple[CorporateAction]]:
    """Shared entries and the user's own manual ones of the given instruments."""
    return select(CorporateAction).where(
        CorporateAction.instrument_id.in_(instrument_ids),
        or_(CorporateAction.user_id.is_(None), CorporateAction.user_id == scope.user.id),
    ).order_by(CorporateAction.instrument_id, CorporateAction.effective_date, CorporateAction.id)


def _out(scope: UserScope, actions: list[CorporateAction]) -> list[CorporateActionOut]:
    active = {action.id for action in winning(action_of(a) for a in actions).values()}
    ids = {a.instrument_id for a in actions} | {a.target_instrument_id for a in actions if a.target_instrument_id}
    tickers = dict(scope.db.execute(
        select(Instrument.id, Instrument.xtb_ticker).where(Instrument.id.in_(ids))
    ).all()) if ids else {}
    return [
        CorporateActionOut(
            id=a.id, instrument_id=a.instrument_id, ticker=tickers[a.instrument_id], type=a.type,
            effective_date=a.effective_date, ratio_from=a.ratio_from, ratio_to=a.ratio_to,
            target_instrument_id=a.target_instrument_id, target_ticker=tickers.get(a.target_instrument_id),
            source=a.source, active=a.id in active, editable=a.user_id == scope.user.id,
        )
        for a in actions
    ]


def _out_one(scope: UserScope, action: CorporateAction) -> CorporateActionOut:
    """The entry as the list shows it (`active` depends on the other entries of its instrument and day)."""
    items = _out(scope, list(scope.db.scalars(_visible(scope, [action.instrument_id]))))
    return next(item for item in items if item.id == action.id)


def _target(db: Session, ticker: str, source: Instrument) -> int:
    """The instrument with this XTB ticker; a new one is created (shared, like on import) and gets its price
    history in the worker's next backfill tick."""
    db.execute(
        insert(Instrument).values(
            xtb_ticker=ticker, name=ticker, category=source.category,
            exchange_suffix=ticker.rsplit(".", 1)[1] if "." in ticker else None,
        ).on_conflict_do_nothing(index_elements=["xtb_ticker"])
    )
    return db.scalar(select(Instrument.id).where(Instrument.xtb_ticker == ticker))


def _fill(scope: UserScope, action: CorporateAction, body: CorporateActionIn) -> None:
    instrument = scope.get_instrument(body.instrument_id)
    duplicate = select(CorporateAction.id).where(
        CorporateAction.user_id == scope.user.id, CorporateAction.instrument_id == instrument.id,
        CorporateAction.effective_date == body.effective_date,
    )
    if action.id is not None:
        duplicate = duplicate.where(CorporateAction.id != action.id)
    if scope.db.scalar(duplicate) is not None:
        raise ApiError(409, "duplicate_action", DUPLICATE)
    target_id = None
    if body.type == "conversion":
        assert body.target_ticker is not None
        if body.target_ticker == instrument.xtb_ticker:
            raise ApiError(422, "conversion_to_itself", "Walor nie może zostać zamieniony sam na siebie.")
        target_id = _target(scope.db, body.target_ticker, instrument)
    action.instrument_id = instrument.id
    action.type = body.type
    action.effective_date = body.effective_date
    action.ratio_from = body.ratio_from if body.ratio_from is not None else ONE  # suppress is stored as 1:1
    action.ratio_to = body.ratio_to if body.ratio_to is not None else ONE
    action.target_instrument_id = target_id


def _save(
    scope: UserScope, days: Iterable[dt.date], background: BackgroundTasks, sessions: sessionmaker[Session]
) -> None:
    """Marks the author's valuations from the earliest affected day, commits, recomputes after the response."""
    try:
        scope.db.flush()
    except IntegrityError:  # a concurrent request stored an entry for the same instrument and day first
        scope.db.rollback()
        raise ApiError(409, "duplicate_action", DUPLICATE) from None
    mark_stale(scope.db, [scope.user.id], min(days))
    scope.db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)


def _own(scope: UserScope, action_id: int) -> CorporateAction:
    """The user's own manual entry; a shared entry of their instrument is read-only (409), anything else is 404."""
    action = scope.db.get(CorporateAction, action_id)
    if action is None or action.user_id not in (None, scope.user.id):
        raise not_found()
    if action.user_id is None:
        scope.get_instrument(action.instrument_id)  # 404 unless the user has the instrument
        raise ApiError(409, "shared_action", "Wpis z Yahoo lub XTB można tylko przykryć własnym wpisem.")
    return action


@router.get("", response_model=list[CorporateActionOut])
def list_actions(scope: UserScope = Depends(get_scope), instrument_id: InstrumentFilter = None) -> list[CorporateActionOut]:
    if instrument_id is not None:
        ids: object = [scope.get_instrument(instrument_id).id]
    else:
        ids = scope.instruments().with_only_columns(Instrument.id).order_by(None)
    return _out(scope, list(scope.db.scalars(_visible(scope, ids))))


@router.post("", status_code=201, response_model=CorporateActionOut)
def create_action(
    body: CorporateActionIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> CorporateActionOut:
    action = CorporateAction(user_id=scope.user.id, source="manual")
    _fill(scope, action, body)
    scope.db.add(action)
    _save(scope, [action.effective_date], background, sessions)
    logger.info("User %s added a %s of instrument %s", scope.user.id, action.type, action.instrument_id)
    return _out_one(scope, action)


@router.put("/{action_id}", response_model=CorporateActionOut)
def update_action(
    action_id: DbId,
    body: CorporateActionIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> CorporateActionOut:
    action = _own(scope, action_id)
    before = action.effective_date
    _fill(scope, action, body)
    _save(scope, [before, action.effective_date], background, sessions)
    return _out_one(scope, action)


@router.delete("/{action_id}", status_code=204)
def delete_action(
    action_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    action = _own(scope, action_id)
    day = action.effective_date
    scope.db.delete(action)
    _save(scope, [day], background, sessions)
    return Response(status_code=204)
