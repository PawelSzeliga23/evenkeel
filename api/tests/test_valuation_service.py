import datetime as dt
import threading
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from app.models import Account, CorporateAction, DailyValuation, FxRate, Instrument, Price, Transaction, User
from app.scoping import UserScope
from app.valuation import service
from app.valuation.engine import FLAG_XTB_PRICE, Conversion, Split
from app.valuation.service import (
    holders,
    load_inputs,
    local_day,
    mark_market_changes,
    mark_new_days,
    mark_stale,
    recompute_stale,
    recompute_user,
    users_with_transactions,
)
from tests.valuation_seed import FRI, SAT, seed_holdings, seed_market, seed_snapshot, seed_user, valuate

MAR_01 = dt.date(2026, 3, 1)


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _rows(db: Session, user_id: int, day: dt.date) -> dict[int | None, DailyValuation]:
    rows = db.scalars(select(DailyValuation).where(DailyValuation.user_id == user_id, DailyValuation.date == day))
    return {row.instrument_id: row for row in rows}


def _count(db: Session, user_id: int) -> int:
    return db.scalar(select(func.count()).select_from(DailyValuation).where(DailyValuation.user_id == user_id))


def _stale(db: Session, user_id: int) -> dt.date | None:
    return db.scalar(select(User.valuations_stale_from).where(User.id == user_id))


def test_local_day_is_the_warsaw_calendar_day() -> None:
    assert local_day(dt.datetime(2026, 3, 1, 23, 30, tzinfo=dt.UTC)) == dt.date(2026, 3, 2)


def test_load_inputs_reads_only_the_users_own_data(db: Session) -> None:
    instrument_id = seed_market(db)
    anna, bartek = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    anna_account = seed_holdings(db, anna, instrument_id)
    seed_holdings(db, bartek, instrument_id, number="11111111")
    seed_snapshot(db, anna_account, instrument_id, "2")

    inputs = load_inputs(UserScope(db, db.get(User, anna)))

    assert sorted(entry.type for entry in inputs.entries) == ["buy", "deposit", "dividend", "withholding_tax"]
    assert {entry.account_id for entry in inputs.entries} == {anna_account}
    assert min(entry.day for entry in inputs.entries) == MAR_01
    assert inputs.market.currencies == {instrument_id: "EUR"}
    assert inputs.market.price(instrument_id, SAT) == (FRI, Decimal("600.00000000"))
    assert inputs.market.rate("EUR", SAT) == Decimal("4.25000000")
    assert inputs.market.snapshots[(anna_account, instrument_id)].on(SAT) == (SAT, Decimal("2550"))


def test_load_inputs_reads_market_data_from_the_last_point_before_the_first_transaction(db: Session) -> None:
    instrument_id = seed_market(db)  # EUR 4.30 from 02-20, first transaction 03-01, first close 03-02
    db.add_all([
        Price(instrument_id=instrument_id, date=dt.date(2026, 1, 15), close=Decimal("480"), source="yahoo"),
        Price(instrument_id=instrument_id, date=dt.date(2026, 2, 27), close=Decimal("490"), source="yahoo"),
        FxRate(currency="EUR", date=dt.date(2026, 1, 10), rate_pln=Decimal("4.10")),
    ])
    user_id = seed_user(db)
    seed_holdings(db, user_id, instrument_id)

    market = load_inputs(UserScope(db, db.get(User, user_id))).market

    assert market.price(instrument_id, MAR_01) == (dt.date(2026, 2, 27), Decimal("490.00000000"))
    assert market.prices[instrument_id].days == [dt.date(2026, 2, 27), dt.date(2026, 3, 2), FRI]
    assert market.rate("EUR", MAR_01) == Decimal("4.30000000")
    assert market.fx["EUR"].days == [dt.date(2026, 2, 20), FRI]


def test_load_inputs_keeps_the_first_rate_after_the_first_transaction_when_none_is_before(db: Session) -> None:
    instrument_id = seed_market(db)
    db.query(FxRate).filter(FxRate.date < MAR_01).delete()
    user_id = seed_user(db)
    seed_holdings(db, user_id, instrument_id)

    market = load_inputs(UserScope(db, db.get(User, user_id))).market

    assert market.rate("EUR", MAR_01) == Decimal("4.25000000")


def test_recompute_writes_every_day_and_clears_the_marker(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))

    valuate(db, user_id)

    days = (SAT - MAR_01).days + 1
    assert _count(db, user_id) == days + (days - 1)
    rows = _rows(db, user_id, SAT)
    assert (rows[None].value_pln, rows[None].quantity) == (Decimal("5729.70"), Decimal("5729.70"))
    position = next(row for key, row in rows.items() if key is not None)
    assert (position.value_pln, position.cost_pln, position.quantity, position.flags) == (
        Decimal("5100.00"), Decimal("4304.30"), Decimal("2"), [])
    assert _rows(db, user_id, MAR_01)[None].net_flow_pln == Decimal("10000.00")
    assert _stale(db, user_id) is None


def test_recompute_only_rewrites_rows_from_the_stale_date(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))
    valuate(db, user_id)
    db.execute(update(DailyValuation).where(DailyValuation.date.in_([dt.date(2026, 4, 1), dt.date(2026, 9, 1)]))
               .values(value_pln=Decimal("1")))
    db.commit()

    mark_stale(db, [user_id], dt.date(2026, 8, 1))
    db.commit()
    recompute_user(db, user_id, SAT)

    assert _rows(db, user_id, dt.date(2026, 4, 1))[None].value_pln == Decimal("1")
    assert _rows(db, user_id, dt.date(2026, 9, 1))[None].value_pln == Decimal("5729.70")


def test_marking_keeps_the_earliest_date(db: Session) -> None:
    user_id = seed_user(db)
    mark_stale(db, [user_id], dt.date(2026, 5, 1))
    mark_stale(db, [user_id], dt.date(2026, 6, 1))
    mark_stale(db, [], dt.date(2020, 1, 1))
    db.commit()
    assert _stale(db, user_id) == dt.date(2026, 5, 1)
    mark_stale(db, [user_id], dt.date(2026, 4, 1))
    db.commit()
    assert _stale(db, user_id) == dt.date(2026, 4, 1)


def test_recompute_of_a_user_without_transactions_clears_old_rows(db: Session) -> None:
    user_id = seed_user(db)
    account_id = seed_holdings(db, user_id, seed_market(db))
    valuate(db, user_id)
    db.query(Transaction).filter(Transaction.account_id == account_id).delete()
    db.commit()

    valuate(db, user_id)

    assert _count(db, user_id) == 0


def test_instrument_without_prices_is_valued_from_xtb_and_flagged(db: Session) -> None:
    instrument_id = seed_market(db)
    user_id = seed_user(db)
    seed_holdings(db, user_id, instrument_id)
    db.query(Price).delete()
    db.commit()

    valuate(db, user_id)

    position = next(row for key, row in _rows(db, user_id, SAT).items() if key is not None)
    assert (position.value_pln, position.flags) == (Decimal("4304.30"), [FLAG_XTB_PRICE])


def test_new_days_are_marked_from_the_day_after_each_users_last_row(db: Session) -> None:
    instrument_id = seed_market(db)
    behind, current, fresh = seed_user(db), seed_user(db, "bartek@portfolio.dev"), seed_user(db, "carol@portfolio.dev")
    seed_holdings(db, behind, instrument_id)
    seed_holdings(db, current, instrument_id, number="22222222")
    seed_holdings(db, fresh, instrument_id, number="33333333")
    valuate(db, behind, today=dt.date(2026, 9, 23))  # rows end three days before today: the worker was down
    valuate(db, current, today=SAT)

    mark_new_days(db, SAT)
    db.commit()

    assert (_stale(db, behind), _stale(db, current), _stale(db, fresh)) == (dt.date(2026, 9, 24), SAT, dt.date.min)


def test_market_changes_mark_holders_and_fx_marks_everyone(db: Session) -> None:
    instrument_id = seed_market(db)
    anna, bartek, carol = seed_user(db), seed_user(db, "bartek@portfolio.dev"), seed_user(db, "carol@portfolio.dev")
    seed_holdings(db, anna, instrument_id)
    bartek_account = seed_holdings(db, bartek, instrument_id, number="22222222")
    db.query(Transaction).filter(Transaction.account_id == bartek_account, Transaction.instrument_id.is_not(None)).delete()
    db.commit()

    assert holders(db, [instrument_id]) == [anna]
    assert users_with_transactions(db) == [anna, bartek]
    mark_market_changes(db, {instrument_id: FRI}, {})
    db.commit()
    assert (_stale(db, anna), _stale(db, bartek), _stale(db, carol)) == (FRI, None, None)
    mark_market_changes(db, {}, {"EUR": dt.date(2026, 9, 1), "USD": dt.date(2026, 8, 1)})
    db.commit()
    assert (_stale(db, anna), _stale(db, bartek), _stale(db, carol)) == (dt.date(2026, 8, 1), dt.date(2026, 8, 1), None)


def test_mark_market_changes_locks_every_user_once_in_ascending_id_order(
    db: Session, monkeypatch: pytest.MonkeyPatch
) -> None:
    instrument1 = seed_market(db)
    instrument2 = Instrument(xtb_ticker="OTHER.US", name="Other ETF", currency="USD")
    db.add(instrument2)
    db.flush()
    low, high = seed_user(db, "low@portfolio.dev"), seed_user(db, "high@portfolio.dev")
    assert low < high
    seed_holdings(db, high, instrument1, number="11111111")  # holder of the instrument listed first
    seed_holdings(db, low, instrument2.id, number="22222222")  # holder of the instrument listed second

    calls: list[int] = []
    original_lock_user = service.lock_user

    def recording_lock_user(db_: Session, user_id: int) -> None:
        calls.append(user_id)
        original_lock_user(db_, user_id)

    monkeypatch.setattr(service, "lock_user", recording_lock_user)

    mark_market_changes(db, {instrument1: dt.date(2026, 1, 1), instrument2.id: dt.date(2026, 1, 2)}, {})

    assert calls == [low, high]


def test_recompute_stale_handles_every_marked_user(db: Session) -> None:
    instrument_id = seed_market(db)
    anna, bartek = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    seed_holdings(db, anna, instrument_id)
    seed_holdings(db, bartek, instrument_id, number="11111111")
    mark_stale(db, [anna, bartek], dt.date.min)
    db.commit()

    assert recompute_stale(db, SAT) == 2
    assert _count(db, anna) == _count(db, bartek) > 0
    assert (_stale(db, anna), _stale(db, bartek)) == (None, None)
    assert recompute_stale(db, SAT) == 0


def test_recompute_waits_for_a_concurrent_marking(engine: Engine, db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))
    finished = threading.Event()

    def run() -> None:
        with Session(engine) as worker_db:
            recompute_user(worker_db, user_id, SAT)
        finished.set()

    with Session(engine) as importer:
        mark_stale(importer, [user_id], dt.date.min)  # holds the user's lock until commit, like an import
        thread = threading.Thread(target=run)
        thread.start()
        assert not finished.wait(0.5)
        importer.commit()
    thread.join(10)

    assert finished.is_set()
    assert _count(db, user_id) > 0
    assert _stale(db, user_id) is None


JUN_01, JUL_01 = dt.date(2026, 6, 1), dt.date(2026, 7, 1)


def _manual(db: Session, user_id: int, instrument_id: int, type_: str, day: dt.date, ratio: tuple[int, int] = (1, 1),
            target: int | None = None) -> None:
    db.add(CorporateAction(instrument_id=instrument_id, type=type_, effective_date=day, ratio_from=Decimal(ratio[0]),
                           ratio_to=Decimal(ratio[1]), target_instrument_id=target, source="manual", user_id=user_id))
    db.commit()


def _cspx(db: Session) -> int:
    """The conversion target: EUR, one close of 50 EUR on Friday 2026-09-25."""
    instrument = Instrument(xtb_ticker="CSPX.UK", name="CSPX.UK", category="etf", currency="EUR", price_symbol="CSPX.L",
                            price_checked_at=dt.datetime(2026, 9, 25, 21, 0, tzinfo=dt.UTC))
    db.add(instrument)
    db.flush()
    db.add(Price(instrument_id=instrument.id, date=FRI, close=Decimal("50.00"), source="yahoo"))
    db.commit()
    return instrument.id


def test_load_inputs_applies_shared_and_own_actions_but_not_other_users(db: Session) -> None:
    instrument_id = seed_market(db)
    anna, bartek = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    seed_holdings(db, anna, instrument_id)
    seed_holdings(db, bartek, instrument_id, number="22222222")
    db.add(CorporateAction(instrument_id=instrument_id, type="split", effective_date=JUN_01, ratio_from=Decimal(1),
                           ratio_to=Decimal(2), source="provider"))
    db.commit()
    _manual(db, anna, instrument_id, "suppress", JUN_01)
    _manual(db, bartek, instrument_id, "split", JUL_01, (1, 3))

    for_anna = load_inputs(UserScope(db, db.get(User, anna)))
    for_bartek = load_inputs(UserScope(db, db.get(User, bartek)))

    assert (for_anna.splits, for_anna.conversions) == ([], [])
    assert for_bartek.splits == [Split(instrument_id, JUN_01, Decimal(1), Decimal(2)),
                                 Split(instrument_id, JUL_01, Decimal(1), Decimal(3))]


def test_own_conversion_moves_the_valuation_to_the_target(db: Session) -> None:
    instrument_id = seed_market(db)
    target_id = _cspx(db)
    anna = seed_user(db)
    seed_holdings(db, anna, instrument_id)
    _manual(db, anna, instrument_id, "conversion", dt.date(2026, 9, 1), target=target_id)

    inputs = load_inputs(UserScope(db, db.get(User, anna)))
    valuate(db, anna)

    assert inputs.conversions == [Conversion(instrument_id, target_id, dt.date(2026, 9, 1), Decimal(1), Decimal(1))]
    assert (inputs.market.currencies[target_id], target_id in inputs.market.prices) == ("EUR", True)
    assert set(_rows(db, anna, dt.date(2026, 8, 31))) == {None, instrument_id}
    rows = _rows(db, anna, SAT)
    assert set(rows) == {None, target_id}
    assert (rows[target_id].quantity, rows[target_id].value_pln, rows[target_id].cost_pln) == (
        Decimal("2.00000000"), Decimal("425.0000"), Decimal("4304.3000"))  # 2 × 50 EUR × 4.25


def test_conversion_target_is_visible_to_its_author_only_and_makes_them_a_holder(db: Session) -> None:
    instrument_id = seed_market(db)
    target_id = _cspx(db)
    anna, bartek = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    seed_holdings(db, anna, instrument_id)
    seed_holdings(db, bartek, instrument_id, number="22222222")
    _manual(db, anna, instrument_id, "conversion", dt.date(2026, 9, 1), target=target_id)

    def tickers(user_id: int) -> list[str]:
        return [i.xtb_ticker for i in db.scalars(UserScope(db, db.get(User, user_id)).instruments())]

    assert (tickers(anna), tickers(bartek)) == (["CSPX.UK", "SXR8.DE"], ["SXR8.DE"])
    assert holders(db, [target_id]) == [anna]


def test_recompute_stores_the_exit_costs(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))  # an XTB account in PLN holding SXR8.DE (EUR)

    valuate(db, user_id)

    rows = _rows(db, user_id, SAT)
    position = next(row for key, row in rows.items() if key is not None)
    assert (position.value_pln, position.exit_cost_pln) == (Decimal("5100.00"), Decimal("25.50"))  # 0.5 %
    assert rows[None].exit_cost_pln == Decimal("0.00")  # PLN cash


def test_a_manual_spread_is_part_of_the_stored_exit_cost(db: Session) -> None:
    instrument_id = seed_market(db)
    db.execute(update(Instrument).where(Instrument.id == instrument_id).values(spread_pct=Decimal("0.10")))
    db.commit()
    user_id = seed_user(db)
    seed_holdings(db, user_id, instrument_id)

    inputs = load_inputs(UserScope(db, db.get(User, user_id)))
    valuate(db, user_id)

    assert inputs.exit_rules.spreads == {instrument_id: Decimal("0.1000")}
    position = next(row for key, row in _rows(db, user_id, SAT).items() if key is not None)
    assert position.exit_cost_pln == Decimal("30.60")  # 25.50 conversion + 5.10 spread


def test_accounts_outside_xtb_pay_no_conversion_fee(db: Session) -> None:
    user_id = seed_user(db)
    account_id = seed_holdings(db, user_id, seed_market(db))
    db.execute(update(Account).where(Account.id == account_id).values(broker=None))
    db.commit()

    valuate(db, user_id)

    assert load_inputs(UserScope(db, db.get(User, user_id))).exit_rules.fee_accounts == frozenset()
    position = next(row for key, row in _rows(db, user_id, SAT).items() if key is not None)
    assert position.exit_cost_pln == Decimal("0.00")
