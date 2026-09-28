"""A (USD) converted 1:2 into B (EUR) on 2026-06-01; one lot of 10 A bought for 4 000 zł on 2026-03-02."""
import datetime as dt
from decimal import Decimal as D

from app.valuation.engine import Conversion, Entry, Split, daily_rows, replay
from app.valuation.market_data import MarketData, Series

A, B = 1, 2
MAR_01, MAR_02, APR_01 = dt.date(2026, 3, 1), dt.date(2026, 3, 2), dt.date(2026, 4, 1)
MAY_31, JUN_01, JUN_02, JUL_01 = dt.date(2026, 5, 31), dt.date(2026, 6, 1), dt.date(2026, 6, 2), dt.date(2026, 7, 1)

BUY_A = Entry(1, 1, A, "buy", MAR_02, D("-4000"), "PLN", D("10"), D("100"), "11")
CONVERSION = Conversion(A, B, JUN_01, D(1), D(2))


def _market() -> MarketData:
    return MarketData(
        prices={A: Series([(MAR_02, D("100.00"))]), B: Series([(JUN_01, D("30.00"))])},
        currencies={A: "USD", B: "EUR"},
        fx={"USD": Series([(MAR_01, D("4.00"))]), "EUR": Series([(MAR_01, D("4.30")), (JUN_01, D("4.40"))])},
    )


def test_conversion_moves_the_lot_with_its_cost_purchase_day_and_position_id() -> None:
    book = replay([BUY_A], [], _market(), JUN_01, conversions=[CONVERSION])

    assert book.position(1, A, JUN_01) is None
    view = book.position(1, B, JUN_01)
    assert view is not None
    # 20 B × 30 EUR × 4.40; purchase rate = EUR on the purchase day (4.30): currency effect 20 × 30 × 0.10
    assert (view.quantity, view.cost_pln, view.value_pln, view.fx_effect_pln, view.price_effect_pln) == (
        D("20"), D("4000.00"), D("2640.00"), D("60.00"), D("-1420.00"))
    (lot,) = view.lots
    assert (lot.position_id, lot.opened_on) == ("11", MAR_02)


def test_daily_rows_switch_instruments_on_the_conversion_day() -> None:
    rows = daily_rows([BUY_A], [], _market(), JUN_01, conversions=[CONVERSION])

    assert {row.instrument_id for row in rows if row.day == MAY_31} == {None, A}
    assert {row.instrument_id for row in rows if row.day == JUN_01} == {None, B}


def test_the_target_is_sold_by_the_original_position_id() -> None:
    sell_b = Entry(2, 1, B, "sell", JUN_02, D("2700"), "PLN", D("20"), D("30"), "11")

    book = replay([BUY_A, sell_b], [], _market(), JUN_02, conversions=[CONVERSION])

    (sale,) = book.sales
    assert (sale.instrument_id, sale.cost_pln, sale.matched) == (B, D("4000"), True)
    assert book.position(1, B, JUN_02) is None


def test_splits_before_and_after_the_conversion_keep_the_units_consistent() -> None:
    splits = [Split(A, APR_01, D(1), D(2)), Split(B, JUL_01, D(1), D(3))]

    book = replay([BUY_A], splits, _market(), JUL_01, conversions=[CONVERSION])

    # 10 A → 20 A (split) → 40 B (conversion 1:2) → 120 B (split 1:3)
    assert book.position(1, B, JUN_01).quantity == D("40")
    assert book.position(1, B, JUL_01).quantity == D("120")


def test_a_conversion_after_the_last_transaction_still_applies() -> None:
    book = replay([BUY_A], [], _market(), JUL_01, conversions=[CONVERSION])
    assert book.position(1, B, JUL_01) is not None
