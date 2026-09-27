import datetime as dt
from decimal import Decimal as D

from app.valuation.engine import (
    FLAG_FX_MISSING,
    FLAG_XTB_PRICE,
    SOURCE_PROVIDER,
    SOURCE_XTB,
    Entry,
    Split,
    daily_rows,
    last_session,
    previous_session,
    replay,
)
from app.valuation.market_data import MarketData, Series

SXR8, NOPRICE, NVDA = 1, 2, 3
MAR_01, MAR_02, MAR_03 = dt.date(2026, 3, 1), dt.date(2026, 3, 2), dt.date(2026, 3, 3)
SEP_10, SEP_20 = dt.date(2026, 9, 10), dt.date(2026, 9, 20)
THU, FRI, SAT = dt.date(2026, 9, 24), dt.date(2026, 9, 25), dt.date(2026, 9, 26)
JUN_07, JUN_10 = dt.date(2024, 6, 7), dt.date(2024, 6, 10)

DEPOSIT = Entry(1, 1, None, "deposit", MAR_01, D("10000"), "PLN")
BUY = Entry(2, 1, SXR8, "buy", MAR_02, D("-4304.30"), "PLN", D("2"), D("500.5"), "777")


def _market() -> MarketData:
    return MarketData(
        prices={
            SXR8: Series([(MAR_02, D("500.00")), (FRI, D("600.00"))]),
            NVDA: Series([(JUN_07, D("120.00")), (JUN_10, D("121.00"))]),
        },
        currencies={SXR8: "EUR", NOPRICE: None, NVDA: "USD"},
        fx={"EUR": Series([(MAR_02, D("4.30")), (FRI, D("4.25"))]), "USD": Series([(dt.date(2024, 6, 3), D("4.00"))])},
        snapshots={(1, NOPRICE): Series([(SEP_20, D("120"))])},
    )


def test_position_value_splits_into_price_and_currency_effects() -> None:
    view = replay([DEPOSIT, BUY], [], _market(), FRI).position(1, SXR8, FRI)

    assert view is not None
    assert (view.quantity, view.value_pln, view.cost_pln) == (D("2"), D("5100.00"), D("4304.30"))
    assert (view.price_effect_pln, view.fx_effect_pln, view.flags) == (D("855.70"), D("-60.00"), ())
    assert view.quote is not None
    assert (view.quote.price, view.quote.price_date, view.quote.rate, view.quote.source) == (
        D("600.00"), FRI, D("4.25"), SOURCE_PROVIDER)
    (lot,) = view.lots
    assert (lot.position_id, lot.open_price, lot.value_pln, lot.price_effect_pln) == ("777", D("500.5"), D("5100.00"), D("855.70"))


def test_weekend_is_valued_with_the_last_session() -> None:
    view = replay([DEPOSIT, BUY], [], _market(), SAT).position(1, SXR8, SAT)
    assert view is not None and view.value_pln == D("5100.00") and view.quote.price_date == FRI


def test_missing_provider_price_falls_back_to_the_newest_xtb_value() -> None:
    buy = Entry(3, 1, NOPRICE, "buy", MAR_02, D("-400"), "PLN", D("4"), D("100"), "5")
    book = replay([buy], [], _market(), FRI)

    latest = book.position(1, NOPRICE, FRI)
    earlier = book.position(1, NOPRICE, SEP_10)

    assert latest is not None and earlier is not None
    assert (latest.value_pln, latest.flags, latest.quote.source, latest.quote.price) == (
        D("480.00"), (FLAG_XTB_PRICE,), SOURCE_XTB, None)
    assert (latest.quote.price_date, latest.fx_effect_pln, latest.price_effect_pln) == (SEP_20, D("0.00"), D("80.00"))
    assert (earlier.value_pln, earlier.quote.price_date) == (D("400.00"), MAR_02)


def test_split_keeps_the_value_continuous_and_shows_the_quantity_of_the_day() -> None:
    split = Split(NVDA, JUN_10, D(1), D(10))
    buy = Entry(4, 1, NVDA, "buy", dt.date(2024, 6, 3), D("-4800"), "PLN", D("1"), D("1200"), "1")
    book = replay([buy], [split], _market(), JUN_10)

    before, after = book.position(1, NVDA, JUN_07), book.position(1, NVDA, JUN_10)

    assert before is not None and after is not None
    assert (before.quantity, before.value_pln, before.lots[0].open_price) == (D("1"), D("4800.00"), D("1200"))
    assert (after.quantity, after.value_pln, after.lots[0].open_price) == (D("10"), D("4840.00"), D("120"))


def test_daily_rows_cover_every_day_with_cash_and_open_positions() -> None:
    rows = daily_rows([DEPOSIT, BUY], [], _market(), MAR_03)

    assert [(r.day, r.instrument_id, r.value_pln, r.net_flow_pln) for r in rows] == [
        (MAR_01, None, D("10000.00"), D("10000.00")),
        (MAR_02, None, D("5695.70"), D("0.00")),
        (MAR_02, SXR8, D("4300.00"), D("0")),
        (MAR_03, None, D("5695.70"), D("0.00")),
        (MAR_03, SXR8, D("4300.00"), D("0")),
    ]
    position = rows[2]
    assert (position.quantity, position.cost_pln, position.flags) == (D("2"), D("4304.30"), ())
    assert (rows[0].quantity, rows[0].cost_pln) == (D("10000"), D("10000.00"))


def test_sold_out_position_has_no_rows_after_the_sale() -> None:
    sell = Entry(5, 1, SXR8, "sell", MAR_03, D("4400"), "PLN", D("2"), D("510"), "777")
    rows = daily_rows([DEPOSIT, BUY, sell], [], _market(), MAR_03)
    assert [(r.instrument_id, r.value_pln) for r in rows if r.day == MAR_03] == [(None, D("10095.70"))]


def test_cash_of_an_account_without_rates_is_flagged() -> None:
    deposit = Entry(6, 2, None, "deposit", MAR_01, D("100"), "CHF")
    (row,) = daily_rows([deposit], [], _market(), MAR_01)
    assert (row.quantity, row.value_pln, row.flags) == (D("100"), D("0"), (FLAG_FX_MISSING,))


def test_day_change_compares_the_quotes_of_two_sessions() -> None:
    book = replay([DEPOSIT, BUY], [], _market(), SAT)
    assert book.day_change(1, SXR8, FRI, THU) == D("800.00")
    assert book.day_change(1, NOPRICE, FRI, THU) == D("0")


def test_sessions_skip_weekends() -> None:
    assert last_session(SAT) == FRI
    assert last_session(FRI) == FRI
    assert previous_session(dt.date(2026, 9, 28)) == FRI
    assert previous_session(FRI) == THU


def test_no_transactions_no_rows() -> None:
    assert daily_rows([], [], MarketData(), FRI) == []
