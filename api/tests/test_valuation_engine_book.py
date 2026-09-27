import datetime as dt
from decimal import Decimal as D

from app.valuation.engine import Book, Entry, Split
from app.valuation.market_data import MarketData, Series

MAR_01, MAR_02, MAR_05, JUN_01 = dt.date(2026, 3, 1), dt.date(2026, 3, 2), dt.date(2026, 3, 5), dt.date(2026, 6, 1)
ACCOUNT, USD_ACCOUNT, SXR8 = 1, 2, 1


def _market() -> MarketData:
    return MarketData(
        currencies={SXR8: "EUR"},
        fx={"EUR": Series([(MAR_02, D("4.30"))]), "USD": Series([(MAR_01, D("4.00"))])},
    )


def _entry(
    id_: int, type_: str, day: dt.date, amount: str, *, account: int = ACCOUNT, instrument: int | None = None,
    quantity: str | None = None, position: str | None = None, currency: str = "PLN",
) -> Entry:
    return Entry(id=id_, account_id=account, instrument_id=instrument, type=type_, day=day, amount=D(amount),
                 currency=currency, quantity=None if quantity is None else D(quantity), position_id=position)


def _buy(id_: int, day: dt.date, quantity: str, amount: str, position: str | None = None, **kw: object) -> Entry:
    return _entry(id_, "buy", day, amount, instrument=SXR8, quantity=quantity, position=position, **kw)


def _sell(id_: int, day: dt.date, quantity: str, amount: str, position: str | None = None) -> Entry:
    return _entry(id_, "sell", day, amount, instrument=SXR8, quantity=quantity, position=position)


def _book(*entries: Entry, splits: tuple[Split, ...] = ()) -> Book:
    book = Book(splits, _market())
    for entry in entries:
        book.apply(entry)
    return book


def _lots(book: Book, account: int = ACCOUNT) -> dict[str, tuple[D, D]]:
    return {key: (lot.quantity, lot.cost_pln) for key, lot in book.lots[(account, SXR8)].items()}


def test_buy_opens_a_lot_costed_at_the_cash_amount_with_the_rate_of_its_day() -> None:
    book = _book(_entry(1, "deposit", MAR_01, "10000"), _buy(2, MAR_02, "2", "-4304.30", "777"))

    lot = book.lots[(ACCOUNT, SXR8)]["777"]
    assert (lot.quantity, lot.cost_pln, lot.fx_open, lot.opened_on, lot.position_id) == (
        D("2"), D("4304.30"), D("4.30"), MAR_02, "777")
    assert book.cash[ACCOUNT] == D("5695.70")
    assert dict(book.flows) == {(ACCOUNT, MAR_01): D("10000")}


def test_buys_without_position_id_get_separate_lots() -> None:
    book = _book(_buy(1, MAR_02, "1", "-2150"), _buy(2, MAR_05, "1", "-2200"))
    assert _lots(book) == {"tx-1": (D("1"), D("2150")), "tx-2": (D("1"), D("2200"))}


def test_sale_is_matched_to_its_lot_by_position_id() -> None:
    book = _book(
        _buy(1, MAR_02, "2", "-4304.30", "777"), _buy(2, MAR_05, "1", "-2200.00", "778"),
        _sell(3, JUN_01, "1", "2600.00", "777"),
    )

    assert _lots(book) == {"777": (D("1"), D("2152.15")), "778": (D("1"), D("2200.00"))}
    (sale,) = book.sales
    assert (sale.cost_pln, sale.realized_pln, sale.matched, sale.quantity) == (D("2152.15"), D("447.85"), True, D("1"))


def test_sale_without_position_id_takes_the_cost_from_all_lots_pro_rata() -> None:
    book = _book(
        _buy(1, MAR_02, "2", "-4304.30", "777"), _buy(2, MAR_05, "1", "-2200.00", "778"),
        _sell(3, JUN_01, "1.5", "3300.00"),
    )

    assert _lots(book) == {"777": (D("1"), D("2152.15")), "778": (D("0.5"), D("1100.00"))}
    (sale,) = book.sales
    assert (sale.cost_pln, sale.realized_pln, sale.matched) == (D("3252.15"), D("47.85"), False)


def test_sale_larger_than_the_holding_closes_everything_without_error() -> None:
    book = _book(_buy(1, MAR_02, "2", "-4304.30", "777"), _sell(2, JUN_01, "3", "6000.00", "777"))

    assert _lots(book) == {}
    (sale,) = book.sales
    assert (sale.cost_pln, sale.realized_pln, sale.matched) == (D("4304.30"), D("1695.70"), False)


def test_quantities_are_kept_in_current_units_across_a_split() -> None:
    split = Split(SXR8, dt.date(2024, 6, 10), D(1), D(10))
    book = _book(
        _buy(1, dt.date(2024, 6, 3), "1", "-4800", "1"), _sell(2, dt.date(2024, 6, 20), "5", "2500", "1"),
        splits=(split,),
    )

    assert book.factor(SXR8, dt.date(2024, 6, 9)) == D(10)
    assert book.factor(SXR8, dt.date(2024, 6, 10)) == D(1)
    assert _lots(book) == {"1": (D("5"), D("2400"))}
    assert book.sales[0].cost_pln == D("2400")
    assert book.sales[0].matched is True


def test_cash_flows_and_income_are_booked_separately() -> None:
    book = _book(
        _entry(1, "deposit", MAR_01, "1000"),
        _entry(2, "transfer_out", MAR_02, "-200"),
        _entry(3, "withdrawal", MAR_02, "-100"),
        _entry(4, "dividend", JUN_01, "40", instrument=SXR8),
        _entry(5, "withholding_tax", JUN_01, "-6", instrument=SXR8),
        _entry(6, "interest", JUN_01, "1.5"),
        _entry(7, "fee", JUN_01, "-2"),
        _entry(8, "unknown", JUN_01, "3"),
    )

    assert book.cash[ACCOUNT] == D("736.5")
    assert dict(book.flows) == {(ACCOUNT, MAR_01): D("1000"), (ACCOUNT, MAR_02): D("-300")}
    assert book.dividends[(ACCOUNT, SXR8)] == D("40")
    assert book.withholding[(ACCOUNT, SXR8)] == D("-6")


def test_foreign_currency_account_converts_flows_and_costs_at_the_nbp_rate() -> None:
    book = _book(
        _entry(1, "deposit", MAR_01, "100", account=USD_ACCOUNT, currency="USD"),
        _buy(2, MAR_02, "1", "-50", "9", account=USD_ACCOUNT, currency="USD"),
    )

    assert book.flows[(USD_ACCOUNT, MAR_01)] == D("400.00")
    assert book.lots[(USD_ACCOUNT, SXR8)]["9"].cost_pln == D("200.00")
    assert book.cash[USD_ACCOUNT] == D("50")
    assert book.account_currency[USD_ACCOUNT] == "USD"


def test_series_lookups() -> None:
    series = Series([(MAR_05, D("2")), (MAR_02, D("1")), (MAR_05, D("3"))])
    assert series.on(MAR_01) is None
    assert series.near(MAR_01) == (MAR_02, D("1"))
    assert series.on(JUN_01) == (MAR_05, D("3"))
    series.add(JUN_01, D("4"))
    assert series.on(JUN_01) == (JUN_01, D("4"))
    assert MarketData().rate("PLN", MAR_01) == D(1)
    assert MarketData().rate(None, MAR_01) is None
