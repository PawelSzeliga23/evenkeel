from collections import defaultdict
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from sqlalchemy import select

from app.models import Account, Instrument, Transaction
from app.scoping import UserScope
from app.xtb.report import CashOperation, XtbReport

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
