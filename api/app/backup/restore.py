"""Reading and restoring a backup: the whole file is checked first, then the user's data is replaced in one go."""
import datetime as dt
import json
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy import JSON, Column, delete, inspect, select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.backup import json_ids
from app.backup.tables import FORMAT, SHARED_KEYS, SHARED_VOLATILE, TABLES, VERSION
from app.errors import ApiError
from app.models import (
    Account,
    AiReview,
    BondSeries,
    CorporateAction,
    Instrument,
    JournalEntry,
    Scenario,
    Tag,
    Thesis,
    Transaction,
    User,
)
from app.models.base import Base
from app.valuation.service import mark_stale

NOT_A_BACKUP = "To nie jest plik kopii Evenkeel."
NEWER = "Kopia pochodzi z nowszej wersji Evenkeel. Zaktualizuj aplikację."
SHARED_MODELS: dict[str, type[Base]] = {"instruments": Instrument, "bond_series": BondSeries}


def _corrupt(detail: str) -> ApiError:
    return ApiError(422, "invalid_backup", f"Plik kopii jest uszkodzony: {detail}.")


@dataclass
class Backup:
    exported_at: str
    app_version: str
    # table → rows with Python values; `id` (or the shared key) is the number inside the file
    tables: dict[str, list[dict[str, Any]]]
    user: dict[str, Any]


def _columns(model: type[Base]) -> dict[str, Column[Any]]:
    return {attr.key: attr.columns[0] for attr in inspect(model).column_attrs}


def _value(column: Column[Any], value: Any, where: str) -> Any:
    """A file value as the column's Python type; a wrong one makes the file corrupt."""
    if value is None:
        if not column.nullable and column.server_default is None and column.default is None:
            raise _corrupt(f"brak wartości {where}")
        return None
    if isinstance(column.type, JSON):
        return value
    try:
        kind = column.type.python_type
    except NotImplementedError:  # pragma: no cover - every column type here has one
        return value
    try:
        if kind is Decimal:
            if isinstance(value, bool) or not isinstance(value, (str, int)):
                raise ValueError
            return Decimal(str(value))
        if kind is dt.datetime:
            return dt.datetime.fromisoformat(value)
        if kind is dt.date:
            return dt.date.fromisoformat(value)
        if kind is bool:
            if not isinstance(value, bool):
                raise ValueError
            return value
        if kind is int:
            if isinstance(value, bool) or not isinstance(value, int):
                raise ValueError
            return value
        if kind is str:
            if not isinstance(value, str):
                raise ValueError
            return value
    except (ValueError, TypeError, InvalidOperation):
        raise _corrupt(f"zła wartość {where}") from None
    return value


def _rows(data: dict[str, Any], name: str, model: type[Base], skip: set[str]) -> list[dict[str, Any]]:
    rows = data.get(name, [])
    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
        raise _corrupt(f"tabela {name}")
    columns = {key: col for key, col in _columns(model).items() if key not in skip}
    out = []
    for n, row in enumerate(rows, start=1):
        unknown = sorted(set(row) - set(columns))
        if unknown:
            raise _corrupt(f"nieznana kolumna {unknown[0]} w tabeli {name}")
        parsed = {}
        for key, column in columns.items():
            where = f"{key} w tabeli {name} (wiersz {n})"
            if key not in row:
                if key == "id" or (not column.nullable and column.server_default is None and column.default is None
                                   and not column.primary_key):
                    raise _corrupt(f"brak kolumny {where}")
                continue
            parsed[key] = _value(column, row[key], where)
        out.append(parsed)
    return out


def read_backup(content: bytes) -> Backup:
    try:
        raw = json.loads(content)
    except (ValueError, UnicodeDecodeError):
        raise ApiError(422, "invalid_backup", NOT_A_BACKUP) from None
    if not isinstance(raw, dict) or raw.get("format") != FORMAT or not isinstance(raw.get("version"), int):
        raise ApiError(422, "invalid_backup", NOT_A_BACKUP)
    if raw["version"] > VERSION:
        raise ApiError(422, "backup_too_new", NEWER)
    data = raw.get("data")
    if not isinstance(data, dict):
        raise _corrupt("brak danych")
    known = {spec.name for spec in TABLES} | set(SHARED_KEYS) | {"user"}
    unknown = sorted(set(data) - known)
    if unknown:
        raise _corrupt(f"nieznana tabela {unknown[0]}")

    tables = {
        "instruments": _rows(data, "instruments", Instrument, SHARED_VOLATILE - {"id"}),
        "bond_series": _rows(data, "bond_series", BondSeries, set()),
    }
    for spec in TABLES:
        tables[spec.name] = _rows(data, spec.name, spec.model, {spec.owner_column} if spec.owner_column else set())

    ids: dict[str, set[Any]] = {}
    for name, rows in tables.items():
        key = "series" if name == "bond_series" else "id"
        values = [row[key] for row in rows]
        if len(set(values)) != len(values):
            raise _corrupt(f"powtórzony numer w tabeli {name}")
        ids[name] = set(values)
    tickers = [row["xtb_ticker"] for row in tables["instruments"]]
    if len(set(tickers)) != len(tickers):
        raise _corrupt("powtórzony instrument")

    def check(table: str, value: Any) -> Any:
        if value not in ids[table]:
            raise _corrupt(f"odwołanie do {table} {value}, którego nie ma w pliku")
        return value

    for spec in TABLES:
        for row in tables[spec.name]:
            for column, table in spec.refs.items():
                if row.get(column) is not None:
                    check(table, row[column])
            if spec.name in json_ids.ROWS:
                try:
                    json_ids.ROWS[spec.name](row, check)
                except (AttributeError, KeyError, TypeError):
                    raise _corrupt(f"zła wartość w tabeli {spec.name}") from None

    user = data.get("user", {})
    if not isinstance(user, dict) or not isinstance(user.get("preferences", {}), dict):
        raise _corrupt("ustawienia")
    return Backup(str(raw.get("exported_at", "")), str(raw.get("app_version", "")), tables, user)


def counts(backup: Backup) -> dict[str, int]:
    t = backup.tables
    return {
        "accounts": len(t["accounts"]), "transactions": len(t["transactions"]),
        "bond_holdings": len(t["bond_holdings"]), "savings_accounts": len(t["savings_accounts"]),
        "tags": len(t["tags"]), "notes": len(t["theses"]) + len(t["journal_entries"]),
        "scenarios": len(t["scenarios"]), "ai_reviews": len(t["ai_reviews"]),
    }


def _wipe(db: Session, user_id: int) -> None:
    """Everything of the user; rows hanging on the accounts go by the database's cascade."""
    for model in (Tag, Thesis, JournalEntry, Scenario, AiReview):
        db.execute(delete(model).where(model.user_id == user_id))
    db.execute(delete(CorporateAction).where(CorporateAction.user_id == user_id))
    db.execute(delete(Account).where(Account.user_id == user_id))


def _shared(db: Session, backup: Backup) -> dict[str, dict[Any, Any]]:
    """File numbers of instruments → this server's ids; missing instruments and series are added, never changed."""
    instruments: dict[Any, Any] = {}
    for row in backup.tables["instruments"]:
        found = db.scalar(select(Instrument.id).where(Instrument.xtb_ticker == row["xtb_ticker"]))
        if found is None:
            instrument = Instrument(**{k: v for k, v in row.items() if k != "id"})
            db.add(instrument)
            db.flush()
            found = instrument.id
        instruments[row["id"]] = found
    for row in backup.tables["bond_series"]:
        if db.get(BondSeries, row["series"]) is None:
            db.add(BondSeries(**row))
    db.flush()
    return {"instruments": instruments, "bond_series": {s: s for s in (r["series"] for r in backup.tables["bond_series"])}}


def restore(db: Session, user: User, backup: Backup) -> None:
    """Replaces the user's data with the backup and asks for a full recompute. Commits; on error nothing changes."""
    try:
        _wipe(db, user.id)
        maps = _shared(db, backup)
        pairs: list[tuple[Transaction, Any]] = []
        for spec in TABLES:
            created = []
            for source in backup.tables[spec.name]:
                row = {k: v for k, v in source.items() if k != "id"}
                for column, table in spec.refs.items():
                    if row.get(column) is not None and not (spec.name == "transactions" and column == "transfer_pair_id"):
                        row[column] = maps[table][row[column]]
                if spec.name in json_ids.ROWS:
                    json_ids.ROWS[spec.name](row, lambda table, value: maps[table][value])
                if spec.owner_column:
                    row[spec.owner_column] = user.id
                pair = row.pop("transfer_pair_id", None) if spec.name == "transactions" else None
                obj = spec.model(**row)
                db.add(obj)
                created.append((source["id"], obj))
                if pair is not None:
                    pairs.append((obj, pair))  # type: ignore[arg-type]
            db.flush()
            maps[spec.name] = {file_id: obj.id for file_id, obj in created}  # type: ignore[attr-defined]
        for transaction, pair in pairs:
            transaction.transfer_pair_id = maps["transactions"][pair]
        prefs = dict(backup.user.get("preferences") or {})
        own = maps["accounts"]
        if prefs.get("accounts_fixed"):
            prefs["accounts_fixed"] = sorted(own[i] for i in prefs["accounts_fixed"] if i in own)
        user.preferences = prefs
        if isinstance(backup.user.get("base_currency"), str):
            user.base_currency = backup.user["base_currency"]
        mark_stale(db, [user.id], dt.date.min)
        db.commit()
    except SQLAlchemyError as error:
        db.rollback()
        raise _corrupt(str(getattr(error, "orig", error)).splitlines()[0][:200]) from None
