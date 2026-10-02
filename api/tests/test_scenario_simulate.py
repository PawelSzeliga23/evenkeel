import datetime as dt
from decimal import Decimal as D

from app.bonds import edo
from app.scenarios.simulate import (
    DEPOSITS, PORTFOLIO, PRETEND_ACCOUNT, InstrumentInfo, Plan, Recurring, Replace, Share, Target, World, simulate,
)
from app.valuation.engine import Entry
from app.valuation.market_data import MarketData, Series

SP500, NASDAQ, PKO = 1, 2, 3
MAR2, MAR3 = dt.date(2026, 3, 2), dt.date(2026, 3, 3)
FRI = dt.date(2026, 9, 25)
EDO0336 = edo.Series(D("6.25"), D("2.00"), D("3.00"))
NO_DIVIDENDS = "Dywidendy udawanych instrumentów nie są liczone."


def world(end: dt.date = dt.date(2026, 9, 30)) -> World:
    market = MarketData(
        prices={SP500: Series([(MAR2, D("500"))]),
                NASDAQ: Series([(MAR2, D("1000")), (FRI, D("1200"))]),
                PKO: Series([(MAR2, D("50"))])},
        currencies={SP500: "EUR", NASDAQ: "EUR", PKO: "PLN"},
        fx={"EUR": Series([(dt.date(2026, 2, 20), D("4.30"))])},
    )
    instruments = {SP500: InstrumentInfo("SXR8.DE", False), NASDAQ: InstrumentInfo("SXRV.DE", False),
                   PKO: InstrumentInfo("PKO.PL", True)}
    return World(market, (), instruments, {"EDO0336": EDO0336}, {}, end)


def top_up(amount: str, day: int, start: dt.date, end: dt.date | None, target: Target, ike: bool = False) -> Plan:
    return Plan(PORTFOLIO, steps=(Recurring(D(amount), day, start, end, target, ike),))


def kinds(entries: list[Entry]) -> list[tuple[str, dt.date, D]]:
    return [(entry.type, entry.day, entry.amount) for entry in entries]


def test_a_top_up_buys_at_the_close_with_the_conversion_fee() -> None:
    plan = top_up("1000", 1, dt.date(2026, 3, 1), dt.date(2026, 3, 1), Target(NASDAQ))

    result = simulate(plan, world(), [], [])

    deposit, buy = result.entries
    assert (deposit.account_id, deposit.type, deposit.day, deposit.amount, deposit.currency) == (
        PRETEND_ACCOUNT, "deposit", MAR2, D("1000"), "PLN")  # 1 March is a Sunday
    assert (buy.type, buy.instrument_id, buy.amount, buy.price) == ("buy", NASDAQ, D("-1000"), D("1000"))
    assert buy.quantity == D("1000") / (D("1000") * D("4.30") * D("1.005"))
    assert buy.id > deposit.id  # on one day the deposit comes first
    assert result.notes == []


def test_top_ups_buy_on_the_first_weekday_from_the_day() -> None:
    plan = top_up("1000", 28, dt.date(2026, 3, 1), dt.date(2026, 5, 1), Target(PKO))

    result = simulate(plan, world(), [], [])

    buys = [entry for entry in result.entries if entry.type == "buy"]
    assert [entry.day for entry in buys] == [dt.date(2026, 3, 30), dt.date(2026, 4, 28), dt.date(2026, 5, 28)]
    assert {entry.quantity for entry in buys} == {D(20)}  # a PLN stock: no conversion fee
    assert result.notes == [NO_DIVIDENDS]


def test_top_ups_without_an_end_run_to_the_last_valued_day() -> None:
    plan = top_up("100", 1, dt.date(2026, 8, 1), None, Target(PKO))

    days = [entry.day for entry in simulate(plan, world(), [], []).entries if entry.type == "buy"]

    assert days == [dt.date(2026, 8, 3), dt.date(2026, 9, 1)]


def test_no_close_yet_leaves_cash_and_a_note() -> None:
    plan = top_up("1000", 2, dt.date(2026, 2, 1), dt.date(2026, 3, 1), Target(NASDAQ))

    result = simulate(plan, world(), [], [])

    assert kinds(result.entries) == [("deposit", dt.date(2026, 2, 2), D(1000)), ("deposit", MAR2, D(1000)),
                                     ("buy", MAR2, D(-1000))]
    assert result.notes == ["SXRV.DE ma notowania od 03.2026; wcześniejsze kwoty zostały w gotówce."]


def test_no_quotes_at_all_leave_cash_and_a_note() -> None:
    w = world()
    w.market.prices.pop(NASDAQ)

    result = simulate(top_up("1000", 2, MAR2, MAR2, Target(NASDAQ)), w, [], [])

    assert kinds(result.entries) == [("deposit", MAR2, D(1000))]
    assert result.notes == ["SXRV.DE nie ma notowań; kwoty zostały w gotówce."]


def test_edo_top_up_buys_whole_bonds_and_keeps_the_rest_in_cash() -> None:
    plan = top_up("1050", 2, dt.date(2026, 3, 1), dt.date(2026, 3, 1), Target(bond="EDO"), ike=True)

    result = simulate(plan, world(), [], [])

    assert kinds(result.entries) == [("deposit", MAR2, D(50))]  # the bonds are their own deposit
    [holding] = result.holdings
    assert (holding.account_id, holding.purchase_date, holding.quantity, holding.series, holding.taxed,
            holding.redeemed_at) == (PRETEND_ACCOUNT, MAR2, 10, EDO0336, False, None)
    assert holding.id < 0


def test_missing_edo_issue_leaves_cash_and_a_note() -> None:
    plan = top_up("1050", 2, dt.date(2026, 4, 1), dt.date(2026, 4, 1), Target(bond="EDO"))

    result = simulate(plan, world(), [], [])

    assert (kinds(result.entries), result.holdings) == ([("deposit", dt.date(2026, 4, 2), D(1050))], [])
    assert result.notes == ["Brak parametrów emisji EDO z 04.2026 — dodaj ją w Dodaj → obligacja."]


def test_portfolio_base_keeps_the_real_transactions() -> None:
    real = [Entry(1, 7, None, "deposit", MAR2, D(500), "PLN")]

    result = simulate(top_up("100", 3, MAR3, MAR3, Target(PKO)), world(), real, [])

    assert result.entries[0] == real[0]
    assert kinds(result.entries[1:]) == [("deposit", MAR3, D(100)), ("buy", MAR3, D(-100))]
