from collections import defaultdict
from collections.abc import Iterable, Iterator
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Any

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.models import Account, ImportRecord, Instrument, PositionLot, Transaction, XtbSnapshot
from app.scoping import UserScope
from app.xtb.report import CashOperation, XtbReport

FX_PLACES = Decimal("0.00000001")
TRANSFER_PAIR_WINDOW = timedelta(days=1)
TRANSFER_PAIR_TIGHT_WINDOW = timedelta(minutes=10)
INSERT_CHUNK = 1000

NEW_ACCOUNT_NAMES = {"ike": "XTB IKE", "ikze": "XTB IKZE"}


@dataclass
class FilePlan:
    report: XtbReport
    account: Account | None
    new_account: dict[str, Any] | None
    new_operations: list[CashOperation]
    duplicate_count: int
    unknown_count: int
    warnings: list[dict[str, Any]] = field(default_factory=list)

    @property
    def account_name(self) -> str:
        return self.account.name if self.account else str(self.new_account["name"])


def _fmt(value: Decimal) -> str:
    return format(value.normalize(), "f")


def _new_account_fields(report: XtbReport) -> dict[str, Any]:
    return {
        "name": NEW_ACCOUNT_NAMES.get(report.wrapper, f"XTB {report.currency}"),
        "kind": "broker",
        "wrapper": report.wrapper,
        "broker": "xtb",
        "external_account_number": report.account_number,
        "currency": report.currency,
    }


def plan_import(scope: UserScope, reports: list[XtbReport]) -> list[FilePlan]:
    """Works out what importing the reports would change. Writes nothing."""
    plans: list[FilePlan] = []
    seen_in_batch: dict[str, set[str]] = defaultdict(set)
    for report in reports:
        account = scope.broker_account("xtb", report.account_number)
        known = _existing_ids(scope, account, report) if account else set()
        batch_seen = seen_in_batch[report.account_number]
        new_operations: list[CashOperation] = []
        duplicates = 0
        for operation in report.cash_operations:
            if operation.external_id in known or operation.external_id in batch_seen:
                duplicates += 1
                continue
            batch_seen.add(operation.external_id)
            new_operations.append(operation)
        unknown = [op for op in new_operations if op.classified.type == "unknown"]
        plan = FilePlan(
            report=report,
            account=account,
            new_account=None if account else _new_account_fields(report),
            new_operations=new_operations,
            duplicate_count=duplicates,
            unknown_count=len(unknown),
        )
        if unknown:
            plan.warnings.append({
                "code": "unknown_operations",
                "message": f"Nierozpoznane operacje: {len(unknown)}. Zostaną zapisane i oznaczone do wyjaśnienia.",
                "details": {"types": sorted({op.xtb_type for op in unknown})},
            })
        plan.warnings.extend(_reconciliation_warnings(scope, account, report, new_operations))
        plans.append(plan)
    return plans


def _existing_ids(scope: UserScope, account: Account, report: XtbReport) -> set[str]:
    ids = [op.external_id for op in report.cash_operations]
    return set(
        scope.db.scalars(
            select(Transaction.external_id).where(Transaction.account_id == account.id, Transaction.external_id.in_(ids))
        )
    )


def _reconciliation_warnings(
    scope: UserScope, account: Account | None, report: XtbReport, new_operations: list[CashOperation]
) -> list[dict[str, Any]]:
    """Compares holdings implied by the transaction history with what XTB reports as open."""
    if not report.has_open_positions:
        return []
    held: dict[str, Decimal] = defaultdict(Decimal)
    if account is not None:
        stored = scope.db.execute(
            select(Instrument.xtb_ticker, Transaction.type, Transaction.quantity)
            .join(Instrument, Transaction.instrument_id == Instrument.id)
            .where(Transaction.account_id == account.id, Transaction.type.in_(("buy", "sell")))
        )
        for ticker, type_, quantity in stored:
            held[ticker] += quantity if type_ == "buy" else -quantity
    for operation in new_operations:
        classified = operation.classified
        if classified.type in ("buy", "sell") and operation.ticker and classified.quantity is not None:
            held[operation.ticker] += classified.quantity if classified.type == "buy" else -classified.quantity
    reported = {summary.ticker: summary.volume or Decimal(0) for summary in report.instrument_summaries}
    warnings = []
    for ticker in sorted(set(held) | set(reported)):
        calculated, xtb = held.get(ticker, Decimal(0)), reported.get(ticker, Decimal(0))
        if calculated != xtb:
            warnings.append({
                "code": "reconciliation_mismatch",
                "message": f"{ticker}: z historii wynika {_fmt(calculated)} szt., a XTB pokazuje {_fmt(xtb)} szt.",
                "details": {"ticker": ticker, "calculated": _fmt(calculated), "xtb": _fmt(xtb)},
            })
    return warnings


def apply_import(scope: UserScope, plans: list[FilePlan]) -> list[ImportRecord]:
    """Writes the planned imports in a single database transaction (all or nothing)."""
    db = scope.db
    records: list[ImportRecord] = []
    try:
        for plan in plans:
            account = plan.account or scope.add_account(**plan.new_account)
            db.flush()
            plan.account = account
            report = plan.report
            record = ImportRecord(
                user_id=scope.user.id, account_id=account.id, filename=report.filename,
                file_hash=report.file_hash, report_from=report.report_from, report_to=report.report_to,
                rows_added=0, rows_duplicate=plan.duplicate_count, rows_unknown=plan.unknown_count,
                warnings=plan.warnings,
            )
            db.add(record)
            db.flush()
            instruments = _ensure_instruments(db, report)
            record.rows_added = _insert_transactions(db, account, record, plan.new_operations, instruments)
            _upsert_lots(db, account, report, instruments)
            _insert_snapshots(db, account, record, report, instruments)
            records.append(record)
        pair_transfers(scope)
        db.commit()
    except Exception:
        db.rollback()
        raise
    return records


def _chunks(rows: list[dict[str, Any]]) -> Iterator[list[dict[str, Any]]]:
    for start in range(0, len(rows), INSERT_CHUNK):
        yield rows[start:start + INSERT_CHUNK]


def _category(value: str | None) -> str | None:
    return value.lower() if value else None


def _suffix(ticker: str) -> str | None:
    return ticker.rsplit(".", 1)[1].upper() if "." in ticker else None


def _ensure_instruments(db: Session, report: XtbReport) -> dict[str, int]:
    """Creates missing instruments (shared by all users) and returns ticker → id."""
    known: dict[str, tuple[str | None, str | None]] = {}
    for summary in report.instrument_summaries:
        known[summary.ticker] = (summary.name, summary.category)
    for operation in report.cash_operations:
        if operation.ticker:
            known.setdefault(operation.ticker, (operation.instrument_name, operation.category))
    for lot in report.closed_lots:
        known.setdefault(lot.ticker, (lot.name, lot.category))
    for lot in report.open_lots:
        known.setdefault(lot.ticker, (None, None))
    if not known:
        return {}
    rows = [
        {"xtb_ticker": ticker, "name": name or ticker, "category": _category(category), "exchange_suffix": _suffix(ticker)}
        for ticker, (name, category) in known.items()
    ]
    db.execute(insert(Instrument).values(rows).on_conflict_do_nothing(index_elements=["xtb_ticker"]))
    return dict(db.execute(select(Instrument.xtb_ticker, Instrument.id).where(Instrument.xtb_ticker.in_(known))).all())


def _implied_fx(operation: CashOperation) -> Decimal | None:
    quantity, price = operation.classified.quantity, operation.classified.price
    if not quantity or not price:
        return None
    return (abs(operation.amount) / (quantity * price)).quantize(FX_PLACES)


def _insert_transactions(
    db: Session, account: Account, record: ImportRecord, operations: list[CashOperation], instruments: dict[str, int]
) -> int:
    rows = [
        {
            "account_id": account.id,
            "instrument_id": instruments.get(op.ticker) if op.ticker else None,
            "type": op.classified.type,
            "xtb_type": op.xtb_type,
            "occurred_at": op.occurred_at,
            "amount": op.amount,
            "currency": account.currency,
            "quantity": op.classified.quantity,
            "price": op.classified.price,
            "implied_fx_rate": _implied_fx(op),
            "xtb_position_id": op.xtb_position_id,
            "external_id": op.external_id,
            "comment": op.comment,
            "counterparty_account": op.classified.counterparty_account,
            "raw": op.raw,
            "import_id": record.id,
        }
        for op in operations
    ]
    added = 0
    for chunk in _chunks(rows):
        statement = (
            insert(Transaction)
            .values(chunk)
            .on_conflict_do_nothing(constraint="uq_transactions_account_id_external_id")
            .returning(Transaction.id)
        )
        added += len(db.execute(statement).all())
    return added


def _upsert(db: Session, rows: list[dict[str, Any]]) -> None:
    for chunk in _chunks(rows):
        statement = insert(PositionLot).values(chunk)
        updated = {c: statement.excluded[c] for c in chunk[0] if c not in ("account_id", "xtb_position_id")}
        db.execute(
            statement.on_conflict_do_update(constraint="uq_position_lots_account_id_xtb_position_id", set_=updated)
        )


def _dedupe_by_position(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Keeps the last row for each xtb_position_id: a single upsert statement cannot touch the same row twice."""
    deduped: dict[str, dict[str, Any]] = {}
    for row in rows:
        deduped[row["xtb_position_id"]] = row
    return list(deduped.values())


def _upsert_lots(db: Session, account: Account, report: XtbReport, instruments: dict[str, int]) -> None:
    open_rows = [
        {
            "account_id": account.id, "instrument_id": instruments[lot.ticker], "xtb_position_id": lot.xtb_position_id,
            "side": lot.side, "quantity": lot.quantity, "open_price": lot.open_price, "opened_at": lot.opened_at,
            "open_commission": lot.open_commission, "swap": lot.swap, "rollover": lot.rollover, "margin": lot.margin,
            "stop_loss": lot.stop_loss, "take_profit": lot.take_profit, "raw": lot.raw,
        }
        for lot in report.open_lots
    ]
    closed_rows = [
        {
            "account_id": account.id, "instrument_id": instruments[lot.ticker], "xtb_position_id": lot.xtb_position_id,
            "side": lot.side, "quantity": lot.quantity, "open_price": lot.open_price, "opened_at": lot.opened_at,
            "open_commission": lot.commission, "swap": lot.swap, "rollover": lot.rollover, "margin": lot.margin,
            "stop_loss": lot.stop_loss, "take_profit": lot.take_profit, "closed_at": lot.closed_at,
            "close_price": lot.close_price, "close_origin": lot.close_origin,
            "open_conversion_rate": lot.open_conversion_rate, "close_conversion_rate": lot.close_conversion_rate,
            "raw": lot.raw,
        }
        for lot in report.closed_lots
    ]
    if open_rows:
        _upsert(db, _dedupe_by_position(open_rows))
    if closed_rows:
        _upsert(db, _dedupe_by_position(closed_rows))


def _insert_snapshots(
    db: Session, account: Account, record: ImportRecord, report: XtbReport, instruments: dict[str, int]
) -> None:
    taken_at = report.generated_at or datetime.now(UTC)
    base = {"import_id": record.id, "account_id": account.id, "taken_at": taken_at}
    rows: list[dict[str, Any]] = []
    for s in report.instrument_summaries:
        rows.append({**base, "instrument_id": instruments.get(s.ticker), "xtb_position_id": None,
                     "row_kind": "instrument_summary", "volume": s.volume, "value": s.value,
                     "current_price": None, "net_profit": s.net_profit, "net_profit_pct": s.net_profit_pct,
                     "gross_profit": s.gross_profit, "raw": s.raw})
    for lot in report.open_lots:
        rows.append({**base, "instrument_id": instruments.get(lot.ticker), "xtb_position_id": lot.xtb_position_id,
                     "row_kind": "lot", "volume": lot.quantity, "value": lot.value,
                     "current_price": lot.current_price, "net_profit": lot.net_profit,
                     "net_profit_pct": lot.net_profit_pct, "gross_profit": lot.gross_profit, "raw": lot.raw})
    for row in report.account_summary:
        rows.append({**base, "instrument_id": None, "xtb_position_id": None, "row_kind": "account_summary",
                     "volume": None, "value": row.amount, "current_price": None, "net_profit": None,
                     "net_profit_pct": None, "gross_profit": None, "raw": row.raw})
    for chunk in _chunks(rows):
        db.execute(insert(XtbSnapshot).values(chunk))


def pair_transfers(scope: UserScope) -> int:
    """Links transfer_out/transfer_in between the user's own accounts so they aren't counted as new money.

    A pair: different accounts, equal absolute amount, within a day. The account number XTB puts in the
    comment is preferred when it identifies the other side. Real XTB exports, though, sometimes put the
    transaction's OWN account number in that comment instead of the counterparty's — that carries no
    pairing information, so it's treated as if there were no counterparty number at all (see `_effective`).

    Without an exact match, a single remaining candidate is paired only when neither side's (effective)
    counterparty number names an account the user owns (so it can't be contradicting an unimported third
    account). When more than one candidate remains, they're narrowed to those within a tight time window
    of the outgoing transfer, and paired only if that leaves exactly one.
    """
    db = scope.db
    unpaired = db.scalars(
        scope.transactions().where(
            Transaction.type.in_(("transfer_in", "transfer_out")), Transaction.transfer_pair_id.is_(None)
        )
    ).all()
    numbers = {account.id: account.external_account_number for account in db.scalars(scope.accounts())}
    owned_numbers = {number for number in numbers.values() if number is not None}

    def _effective(t: Transaction) -> str | None:
        counterparty = t.counterparty_account
        return None if counterparty == numbers.get(t.account_id) else counterparty

    incoming = [t for t in unpaired if t.type == "transfer_in"]
    paired = 0
    for out in sorted((t for t in unpaired if t.type == "transfer_out"), key=lambda t: t.occurred_at):
        out_counterparty = _effective(out)
        candidates = [
            t for t in incoming
            if t.transfer_pair_id is None
            and t.account_id != out.account_id
            and abs(t.amount) == abs(out.amount)
            and abs(t.occurred_at - out.occurred_at) <= TRANSFER_PAIR_WINDOW
        ]
        exact = [
            t for t in candidates
            if out_counterparty == numbers.get(t.account_id)
            or _effective(t) == numbers.get(out.account_id)
        ]
        pool = exact
        if not pool and out_counterparty not in owned_numbers:
            fallback = [t for t in candidates if _effective(t) not in owned_numbers]
            if len(fallback) > 1:
                fallback = [t for t in fallback if abs(t.occurred_at - out.occurred_at) <= TRANSFER_PAIR_TIGHT_WINDOW]
            if len(fallback) == 1:
                pool = fallback
        if not pool:
            continue
        match = min(pool, key=lambda t: abs(t.occurred_at - out.occurred_at))
        out.transfer_pair_id, match.transfer_pair_id = match.id, out.id
        paired += 1
    db.flush()
    return paired
