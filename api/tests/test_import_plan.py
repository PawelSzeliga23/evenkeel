from collections.abc import Iterator
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from sqlalchemy import Engine
from sqlalchemy.orm import Session

from app.imports.service import plan_import
from app.models import Account, Transaction, User
from app.scoping import UserScope
from app.xtb.report import XtbReport, parse_report
from tests import xtb_factory as xf

AT = datetime(2026, 3, 2, 9, 30)


@pytest.fixture
def session(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _scope(session: Session, email: str = "anna@portfolio.dev") -> UserScope:
    user = User(email=email, password_hash="x")
    session.add(user)
    session.commit()
    return UserScope(session, user)


def _report(cash: list[dict], open_rows: list[dict] | None = None, **kwargs: object) -> XtbReport:
    content = xf.build_report(cash=cash, open_rows=open_rows or [], include_open=open_rows is not None, **kwargs)
    return parse_report(xf.filename(), content)


def _buy(op_id: str, qty: str = "2", position_id: str = "777") -> dict:
    return xf.buy_row("SXR8.DE", qty, "500.5", -4304.3, op_id, AT, position_id)


def test_new_account_is_proposed_for_unknown_xtb_account(session: Session) -> None:
    scope = _scope(session)

    (plan,) = plan_import(scope, [_report([_buy("1002")])])

    assert plan.account is None
    assert plan.new_account == {
        "name": "XTB IKE", "kind": "broker", "wrapper": "ike", "broker": "xtb",
        "external_account_number": "56216965", "currency": "PLN",
    }
    assert plan.account_name == "XTB IKE"
    assert ([op.external_id for op in plan.new_operations], plan.duplicate_count) == (["1002"], 0)


def test_known_operations_are_counted_as_duplicates(session: Session) -> None:
    scope = _scope(session)
    account = scope.add_account(name="Moje IKE", kind="broker", wrapper="ike", broker="xtb",
                                external_account_number="56216965", currency="PLN")
    session.flush()
    session.add(Transaction(account_id=account.id, type="deposit", xtb_type="Deposit",
                            occurred_at=datetime(2026, 3, 1, tzinfo=UTC), amount=Decimal("1"),
                            currency="PLN", external_id="1001", comment="", raw={}))
    session.commit()

    (plan,) = plan_import(scope, [_report([xf.cash_row("Deposit", 1.0, "1001", AT), _buy("1002")])])

    assert plan.account is not None and plan.account.id == account.id
    assert plan.new_account is None
    assert ([op.external_id for op in plan.new_operations], plan.duplicate_count) == (["1002"], 1)


def test_same_file_twice_in_one_batch_is_all_duplicates_the_second_time(session: Session) -> None:
    report = _report([_buy("1002")])

    first, second = plan_import(_scope(session), [report, report])

    assert (len(first.new_operations), second.duplicate_count, len(second.new_operations)) == (1, 1, 0)


def test_unknown_operations_produce_a_warning(session: Session) -> None:
    (plan,) = plan_import(_scope(session), [_report([xf.cash_row("Mystery", 1.0, "1", AT)])])

    assert plan.unknown_count == 1
    assert plan.warnings[0]["code"] == "unknown_operations"
    assert plan.warnings[0]["details"] == {"types": ["Mystery"]}


def test_matching_holdings_reconcile_without_warnings(session: Session) -> None:
    summary = xf.summary_row("SXR8.DE", "Core S&P 500", 3.0, 1530.0, 500.5, 10.0)

    (plan,) = plan_import(_scope(session), [_report([_buy("1", "2", "777"), _buy("2", "1", "778")], [summary])])

    assert plan.warnings == []


def test_holdings_mismatch_is_reported(session: Session) -> None:
    summary = xf.summary_row("SXR8.DE", "Core S&P 500", 5.0, 2550.0, 500.5, 10.0)

    (plan,) = plan_import(_scope(session), [_report([_buy("1", "2")], [summary])])

    (warning,) = plan.warnings
    assert warning["code"] == "reconciliation_mismatch"
    assert warning["details"] == {"ticker": "SXR8.DE", "calculated": "2", "xtb": "5"}


def test_report_without_open_positions_is_not_reconciled(session: Session) -> None:
    (plan,) = plan_import(_scope(session), [_report([_buy("1")])])

    assert plan.warnings == []


def test_other_users_account_is_never_matched(session: Session) -> None:
    other = _scope(session, "bartek@portfolio.dev")
    other.add_account(name="XTB IKE", kind="broker", wrapper="ike", broker="xtb",
                      external_account_number="56216965", currency="PLN")
    session.commit()

    (plan,) = plan_import(_scope(session), [_report([_buy("1")])])

    assert plan.account is None and plan.new_account is not None
