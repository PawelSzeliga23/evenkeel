import dataclasses
from collections.abc import Iterator
from datetime import datetime, timedelta
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.imports.service import apply_import, plan_import
from app.models import Account, ImportRecord, Instrument, PositionLot, Transaction, User, XtbSnapshot
from app.scoping import UserScope
from app.xtb.classify import Classified
from app.xtb.report import parse_report
from tests import xtb_factory as xf

AT = datetime(2026, 3, 2, 9, 30)
IKE, PLN = "56216965", "56204082"


@pytest.fixture
def scope(engine: Engine, clean_db: None) -> Iterator[UserScope]:
    with Session(engine, expire_on_commit=False) as session:
        user = User(email="anna@portfolio.dev", password_hash="x")
        session.add(user)
        session.commit()
        yield UserScope(session, user)


def _ike(cash: list[dict], open_rows: list[dict] | None = None, closed: list[dict] | None = None) -> bytes:
    return xf.build_report(account_number=IKE, cash=cash, open_rows=open_rows or [], closed=closed or [])


def _import(scope: UserScope, *files: tuple[str, bytes]) -> list[ImportRecord]:
    return apply_import(scope, plan_import(scope, [parse_report(name, content) for name, content in files]))


def _count(scope: UserScope, model: type) -> int:
    return scope.db.scalar(select(func.count()).select_from(model))


BUY = xf.buy_row("SXR8.DE", "2", "500.5", -4304.3, "1002", AT, "777")
SUMMARY = xf.summary_row("SXR8.DE", "Core S&P 500", 2.0, 1020.0, 500.5, 19.0)
LOT = xf.lot_row("SXR8.DE", "777", 2.0, 500.5, AT, 510.0, 1020.0, 19.0)


def test_import_creates_account_transactions_lots_and_snapshots(scope: UserScope) -> None:
    (record,) = _import(scope, (xf.filename("IKE", IKE), _ike([BUY], [SUMMARY, LOT])))

    account = scope.db.scalar(select(Account))
    assert (account.name, account.wrapper, account.external_account_number) == ("XTB IKE", "ike", IKE)
    assert (record.account_id, record.rows_added, record.rows_duplicate, record.rows_unknown) == (account.id, 1, 0, 0)
    transaction = scope.db.scalar(select(Transaction))
    assert (transaction.type, transaction.ticker, transaction.quantity, transaction.price) == (
        "buy", "SXR8.DE", Decimal("2"), Decimal("500.5"))
    assert transaction.amount == Decimal("-4304.3")
    assert transaction.implied_fx_rate == Decimal("4.3")
    assert transaction.import_id == record.id
    instrument = scope.db.scalar(select(Instrument))
    assert (instrument.name, instrument.category, instrument.exchange_suffix) == ("Core S&P 500", "etf", "DE")
    lot = scope.db.scalar(select(PositionLot))
    assert (lot.xtb_position_id, lot.quantity, lot.closed_at) == ("777", Decimal("2"), None)
    kinds = sorted(scope.db.scalars(select(XtbSnapshot.row_kind)))
    assert kinds == ["account_summary", "account_summary", "instrument_summary", "lot"]


def test_reimporting_the_same_file_adds_nothing(scope: UserScope) -> None:
    file = (xf.filename("IKE", IKE), _ike([BUY], [SUMMARY, LOT]))
    _import(scope, file)

    (record,) = _import(scope, file)

    assert (record.rows_added, record.rows_duplicate) == (0, 1)
    assert (_count(scope, Transaction), _count(scope, PositionLot), _count(scope, Account)) == (1, 1, 1)


def test_closing_a_lot_in_a_later_import_updates_it(scope: UserScope) -> None:
    _import(scope, (xf.filename("IKE", IKE), _ike([BUY], [SUMMARY, LOT])))
    closed = xf.closed_row("SXR8.DE", "777", 2.0, 500.5, AT, 530.0, datetime(2026, 4, 1, 10, 0), name="Core S&P 500")

    _import(scope, (xf.filename("IKE", IKE), _ike([BUY], [], [closed])))

    lot = scope.db.scalar(select(PositionLot))
    assert (lot.close_price, lot.close_origin) == (Decimal("530.0"), "Client")
    assert lot.closed_at is not None
    assert _count(scope, PositionLot) == 1


def test_instrument_name_is_upgraded_once_a_real_name_is_seen(scope: UserScope) -> None:
    """The first import only has an open lot (no name anywhere), so the instrument is created
    with the ticker as a placeholder name; a later import that also knows the real name and
    category must fill them in rather than leaving the placeholder forever."""
    lot_only = xf.lot_row("SXR8.DE", "777", 2.0, 500.5, AT, 510.0, 1020.0, 19.0)
    _import(scope, (xf.filename("IKE", IKE), _ike([], [lot_only])))

    instrument = scope.db.scalar(select(Instrument))
    assert (instrument.name, instrument.category) == ("SXR8.DE", None)

    _import(scope, (xf.filename("IKE", IKE), _ike([], [SUMMARY, lot_only])))

    scope.db.expire_all()
    instrument = scope.db.scalar(select(Instrument))
    assert (instrument.name, instrument.category) == ("Core S&P 500", "etf")
    assert _count(scope, Instrument) == 1


def test_instrument_name_already_set_is_not_overwritten_by_a_worse_one(scope: UserScope) -> None:
    """Once a real name is stored, a later import that only has the ticker (e.g. an open lot with
    no summary) must not clobber it back down to the ticker placeholder."""
    _import(scope, (xf.filename("IKE", IKE), _ike([], [SUMMARY, LOT])))

    lot_only = xf.lot_row("SXR8.DE", "777", 3.0, 500.5, AT, 510.0, 1530.0, 19.0)
    _import(scope, (xf.filename("IKE", IKE), _ike([], [lot_only])))

    scope.db.expire_all()
    instrument = scope.db.scalar(select(Instrument))
    assert (instrument.name, instrument.category) == ("Core S&P 500", "etf")


def test_duplicate_closed_position_ids_in_one_report_do_not_break_the_import(scope: UserScope) -> None:
    first = xf.closed_row("SXR8.DE", "777", 2.0, 500.5, AT, 520.0, datetime(2026, 4, 1, 9, 0), name="Core S&P 500")
    second = xf.closed_row("SXR8.DE", "777", 2.0, 500.5, AT, 530.0, datetime(2026, 4, 1, 10, 0), name="Core S&P 500")

    _import(scope, (xf.filename("IKE", IKE), _ike([], [], [first, second])))

    lot = scope.db.scalar(select(PositionLot))
    assert (lot.close_price, _count(scope, PositionLot)) == (Decimal("530.0"), 1)


def _transfer(direction: str, amount: float, op_id: str, counterparty: str, product: str) -> dict:
    return xf.cash_row("IKE deposit", amount, op_id, AT, product=product,
                       comment=f"Transfer {direction} operation on account with id {counterparty}")


def _own_transfer(direction: str, amount: float, op_id: str, time: datetime, own_number: str, product: str) -> dict:
    """Shaped like a real XTB export: the comment names the transaction's OWN account, not the counterparty's."""
    return xf.cash_row("IKE deposit", amount, op_id, time, product=product,
                       comment=f"Transfer {direction} operation on account with id {own_number}")


def test_transfers_between_own_accounts_are_paired(scope: UserScope) -> None:
    pln = xf.build_report(account_number=PLN, product="My Trades", include_open=False,
                          cash=[_transfer("out", -500.0, "9001", IKE, "My Trades")])
    ike = _ike([_transfer("in", 500.0, "9002", PLN, "IKE")])

    _import(scope, (xf.filename("PLN", PLN), pln), (xf.filename("IKE", IKE), ike))

    out, in_ = (scope.db.scalar(select(Transaction).where(Transaction.external_id == i)) for i in ("9001", "9002"))
    assert (out.type, in_.type) == ("transfer_out", "transfer_in")
    assert (out.transfer_pair_id, in_.transfer_pair_id) == (in_.id, out.id)


def test_transfer_pairs_when_the_other_side_arrives_later(scope: UserScope) -> None:
    pln = xf.build_report(account_number=PLN, product="My Trades", include_open=False,
                          cash=[_transfer("out", -500.0, "9001", IKE, "My Trades")])
    _import(scope, (xf.filename("PLN", PLN), pln))
    assert scope.db.scalar(select(Transaction.transfer_pair_id)) is None

    _import(scope, (xf.filename("IKE", IKE), _ike([_transfer("in", 500.0, "9002", PLN, "IKE")])))

    assert scope.db.scalar(select(func.count()).where(Transaction.transfer_pair_id.is_not(None))) == 2


def test_transfers_with_contradicting_counterparty_numbers_are_not_paired(scope: UserScope) -> None:
    """A owns PLN, IKE and a third account. A PLN->third transfer must not be paired with an
    unrelated IKE->third transfer just because they share amount/time: both name the same third
    account as counterparty, so they can't be two sides of the same transfer."""
    third = "56299999"
    scope.add_account(name="XTB Other", kind="broker", wrapper="regular", broker="xtb",
                      external_account_number=third, currency="PLN")
    scope.db.commit()
    pln = xf.build_report(account_number=PLN, product="My Trades", include_open=False,
                          cash=[_transfer("out", -500.0, "9001", third, "My Trades")])
    ike = _ike([_transfer("in", 500.0, "9002", third, "IKE")])

    _import(scope, (xf.filename("PLN", PLN), pln), (xf.filename("IKE", IKE), ike))

    out, in_ = (scope.db.scalar(select(Transaction).where(Transaction.external_id == i)) for i in ("9001", "9002"))
    assert (out.transfer_pair_id, in_.transfer_pair_id) == (None, None)


def test_transfers_are_not_paired_when_ambiguous_between_two_accounts(scope: UserScope) -> None:
    other = "56299998"
    scope.add_account(name="XTB Other", kind="broker", wrapper="regular", broker="xtb",
                      external_account_number=other, currency="PLN")
    scope.db.commit()
    stranger = "00000000"
    pln = xf.build_report(account_number=PLN, product="My Trades", include_open=False,
                          cash=[_transfer("out", -500.0, "9001", stranger, "My Trades")])
    ike = _ike([_transfer("in", 500.0, "9002", stranger, "IKE")])
    other_report = xf.build_report(account_number=other, product="Other", include_open=False,
                                   cash=[_transfer("in", 500.0, "9003", stranger, "Other")])

    _import(scope, (xf.filename("PLN", PLN), pln), (xf.filename("IKE", IKE), ike),
            (xf.filename("OTHER", other), other_report))

    out = scope.db.scalar(select(Transaction).where(Transaction.external_id == "9001"))
    assert out.transfer_pair_id is None


def test_real_shaped_transfers_naming_their_own_account_are_still_paired(scope: UserScope) -> None:
    """Real XTB exports put each side's OWN account number in the comment, not the counterparty's."""
    pln = xf.build_report(account_number=PLN, product="My Trades", include_open=False,
                          cash=[_own_transfer("out", -500.0, "9001", AT, PLN, "My Trades")])
    ike = _ike([_own_transfer("in", 500.0, "9002", AT, IKE, "IKE")])

    _import(scope, (xf.filename("PLN", PLN), pln), (xf.filename("IKE", IKE), ike))

    out, in_ = (scope.db.scalar(select(Transaction).where(Transaction.external_id == i)) for i in ("9001", "9002"))
    assert (out.transfer_pair_id, in_.transfer_pair_id) == (in_.id, out.id)


def test_real_shaped_transfers_pair_each_out_with_its_nearest_in(scope: UserScope) -> None:
    """Two same-amount transfer pairs an hour apart; each out must match the in seconds away, not the other one."""
    first_out, first_in = AT, AT + timedelta(seconds=5)
    second_out = AT + timedelta(hours=1)
    second_in = second_out + timedelta(seconds=5)
    pln = xf.build_report(account_number=PLN, product="My Trades", include_open=False,
                          cash=[
                              _own_transfer("out", -500.0, "9001", first_out, PLN, "My Trades"),
                              _own_transfer("out", -500.0, "9003", second_out, PLN, "My Trades"),
                          ])
    ike = _ike([
        _own_transfer("in", 500.0, "9002", first_in, IKE, "IKE"),
        _own_transfer("in", 500.0, "9004", second_in, IKE, "IKE"),
    ])

    _import(scope, (xf.filename("PLN", PLN), pln), (xf.filename("IKE", IKE), ike))

    def _get(op_id: str) -> Transaction:
        return scope.db.scalar(select(Transaction).where(Transaction.external_id == op_id))

    out1, in1, out2, in2 = _get("9001"), _get("9002"), _get("9003"), _get("9004")
    assert (out1.transfer_pair_id, in1.transfer_pair_id) == (in1.id, out1.id)
    assert (out2.transfer_pair_id, in2.transfer_pair_id) == (in2.id, out2.id)


def test_failure_leaves_nothing_behind(scope: UserScope) -> None:
    plans = plan_import(scope, [parse_report(xf.filename("IKE", IKE), _ike([BUY]))])
    broken = dataclasses.replace(plans[0].new_operations[0], classified=Classified("bogus"))
    plans[0].new_operations = [broken]

    with pytest.raises(IntegrityError):
        apply_import(scope, plans)

    assert (_count(scope, Account), _count(scope, Transaction), _count(scope, ImportRecord)) == (0, 0, 0)
