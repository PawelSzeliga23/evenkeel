"""GET /api/history: one list of everything that happened on the user's accounts, with filters and cursor pages."""
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.errors import ApiError
from app.history.schemas import HistoryPage
from app.history.service import history_items, matches
from app.scoping import AccountIds, UserScope, get_scope
from app.valuation.service import local_today

router = APIRouter(prefix="/api/history", tags=["history"])
IdQuery = Annotated[int | None, Query(ge=1, le=2**31 - 1)]


def _cursor(value: str) -> tuple[dt.date, str]:
    try:
        day, item_id = value.split("|", 1)
        return dt.date.fromisoformat(day), item_id
    except ValueError:
        raise ApiError(422, "bad_cursor", "Nieprawidłowy kursor stronicowania. Wczytaj historię od początku.") from None


@router.get("", response_model=HistoryPage)
def get_history(
    scope: UserScope = Depends(get_scope),
    account_ids: AccountIds = None,
    type: Annotated[str | None, Query(max_length=30)] = None,  # noqa: A002 — public query name
    instrument_id: IdQuery = None,
    date_from: Annotated[dt.date | None, Query(alias="from")] = None,
    date_to: Annotated[dt.date | None, Query(alias="to")] = None,
    q: Annotated[str | None, Query(max_length=100)] = None,
    cursor: Annotated[str | None, Query(max_length=100)] = None,
    limit: Annotated[int, Query(ge=1, le=200)] = 50,
) -> HistoryPage:
    after = _cursor(cursor) if cursor else None
    accounts = scope.account_filter(account_ids)
    if instrument_id is not None:
        scope.get_instrument(instrument_id)
    items = [
        item for item in history_items(scope, local_today())
        if (accounts is None or item.account_id in accounts)
        and (type is None or item.type == type)
        and (instrument_id is None or item.instrument_id == instrument_id)
        and (date_from is None or item.date >= date_from)
        and (date_to is None or item.date <= date_to)
        and (not q or matches(item, q.strip()))
        and (after is None or (item.date, item.id) < after)
    ]
    page = items[:limit]
    more = len(items) > limit
    return HistoryPage(items=page, next_cursor=f"{page[-1].date.isoformat()}|{page[-1].id}" if more else None)
