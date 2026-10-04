"""Writing a backup: every row of the user's tables with its columns, plus the shared rows they point at."""
import copy
import datetime as dt
import uuid
from decimal import Decimal
from importlib.metadata import PackageNotFoundError, version
from typing import Any

from sqlalchemy import inspect, select
from sqlalchemy.orm import Session

from app.backup import json_ids
from app.backup.tables import FORMAT, SHARED_VOLATILE, TABLES, VERSION, user_rows
from app.models import Account, BondSeries, Instrument, User
from app.models.base import Base


def app_version() -> str:
    try:
        return version("portfolio-api")
    except PackageNotFoundError:  # pragma: no cover - the API always runs installed
        return "0.0.0"


def plain(value: Any) -> Any:
    """A column value as JSON: decimals as text (no lost grosze), dates in ISO."""
    if isinstance(value, Decimal):
        return str(value)
    if isinstance(value, (dt.date, dt.datetime)):
        return value.isoformat()
    if isinstance(value, uuid.UUID):
        return str(value)
    if isinstance(value, (dict, list)):
        return copy.deepcopy(value)  # JSON columns: renumbering must not touch the loaded object
    return value


def row_of(obj: Base, skip: set[str]) -> dict[str, Any]:
    return {c.key: plain(getattr(obj, c.key)) for c in inspect(type(obj)).column_attrs if c.key not in skip}


def export_user(db: Session, user: User) -> dict[str, Any]:
    data: dict[str, Any] = {}
    instruments: set[int] = set()
    series: set[str] = set()

    def note(table: str, value: Any) -> Any:
        if table == "instruments":
            instruments.add(value)
        elif table == "bond_series":
            series.add(value)
        return value

    for spec in TABLES:
        skip = {spec.owner_column} if spec.owner_column else set()
        rows = [row_of(obj, skip) for obj in db.scalars(user_rows(spec, user.id))]
        for row in rows:
            for column, table in spec.refs.items():
                if row.get(column) is not None:
                    note(table, row[column])
            if spec.name in json_ids.ROWS:
                json_ids.ROWS[spec.name](row, note)
        data[spec.name] = rows

    data["instruments"] = [
        row_of(obj, SHARED_VOLATILE - {"id"})
        for obj in db.scalars(select(Instrument).where(Instrument.id.in_(instruments)).order_by(Instrument.id))
    ]
    data["bond_series"] = [
        row_of(obj, set())
        for obj in db.scalars(select(BondSeries).where(BondSeries.series.in_(series)).order_by(BondSeries.series))
    ]
    own = set(db.scalars(select(Account.id).where(Account.user_id == user.id)))
    prefs = dict(user.preferences or {})
    if "accounts_fixed" in prefs:
        prefs["accounts_fixed"] = [i for i in prefs["accounts_fixed"] if i in own]
    data["user"] = {"base_currency": user.base_currency, "preferences": prefs}
    return {
        "format": FORMAT,
        "version": VERSION,
        "exported_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "app_version": app_version(),
        "data": data,
    }
