import datetime as dt
from decimal import Decimal as D

from app.valuation.engine import Entry, daily_rows, replay
from app.valuation.exit_costs import XTB_FX_FEE, ExitRules, exit_part
from app.valuation.market_data import MarketData, Series

MAR_02, THU, FRI = dt.date(2026, 3, 2), dt.date(2026, 9, 24), dt.date(2026, 9, 25)
XTB, BANK, XTB_USD = 1, 2, 3
SXR8, CDR, NOPRICE = 10, 11, 12
RULES = ExitRules(fee_accounts=frozenset({XTB, XTB_USD}))


def _market() -> MarketData:
    """SXR8 in EUR: 500 × 4.30 on 03-02, 600 × 4.25 from Friday 09-25; CDR in PLN at 250; NOPRICE has no prices."""
    return MarketData(
        prices={SXR8: Series([(MAR_02, D("500")), (FRI, D("600"))]), CDR: Series([(MAR_02, D("250"))])},
        currencies={SXR8: "EUR", CDR: "PLN", NOPRICE: None},
        fx={"EUR": Series([(MAR_02, D("4.30")), (FRI, D("4.25"))]), "USD": Series([(MAR_02, D("4.00"))])},
    )


def _buy(id_: int, account: int, instrument: int, quantity: str, amount: str, position: str | None = None) -> Entry:
    return Entry(id_, account, instrument, "buy", MAR_02, D(amount), "PLN", D(quantity), position_id=position)


def test_the_fee_is_half_a_percent_for_xtb_accounts_with_a_foreign_currency() -> None:
    assert XTB_FX_FEE == D("0.005")
    assert (RULES.fx_fee(XTB, "EUR", "PLN"), RULES.fx_fee(XTB, "PLN", "PLN"), RULES.fx_fee(BANK, "EUR", "PLN"),
            RULES.fx_fee(XTB_USD, None, "USD")) == (D("0.005"), D("0"), D("0"), D("0.005"))
    assert (exit_part(D("5100"), D("0.005")), exit_part(D("-10"), D("0.005")), exit_part(D("100"), D("0"))) == (
        D("25.50"), D("0.00"), D("0.00"))


def test_a_foreign_currency_position_on_xtb_pays_the_conversion_fee() -> None:
    view = replay([_buy(1, XTB, SXR8, "2", "-4304.30")], [], _market(), FRI, exit_rules=RULES).position(XTB, SXR8, FRI)

    assert view is not None
    # 2 × 600 EUR × 4.25 = 5 100.00 zł; 0.5 % = 25.50 zł
    assert (view.value_pln, view.exit_fx_pln, view.exit_spread_pln, view.exit_cost_pln) == (
        D("5100.00"), D("25.50"), D("0.00"), D("25.50"))
    assert view.lots[0].exit_cost_pln == D("25.50")


def test_a_pln_position_on_xtb_and_a_foreign_one_elsewhere_pay_nothing() -> None:
    book = replay([_buy(1, XTB, CDR, "2", "-500"), _buy(2, BANK, SXR8, "2", "-4304.30")], [], _market(), FRI,
                  exit_rules=RULES)

    assert (book.position(XTB, CDR, FRI).exit_cost_pln, book.position(BANK, SXR8, FRI).exit_cost_pln) == (
        D("0.00"), D("0.00"))


def test_a_manual_spread_adds_to_the_conversion_fee() -> None:
    rules = ExitRules(fee_accounts=frozenset({XTB}), spreads={SXR8: D("0.10"), CDR: D("0.20")})
    book = replay([_buy(1, XTB, SXR8, "2", "-4304.30"), _buy(2, XTB, CDR, "2", "-500")], [], _market(), FRI,
                  exit_rules=rules)

    sxr8, cdr = book.position(XTB, SXR8, FRI), book.position(XTB, CDR, FRI)
    assert (sxr8.exit_fx_pln, sxr8.exit_spread_pln, sxr8.exit_cost_pln) == (D("25.50"), D("5.10"), D("30.60"))
    assert (cdr.exit_fx_pln, cdr.exit_spread_pln) == (D("0.00"), D("1.00"))  # 500 × 0.20 %, no conversion in PLN


def test_a_position_valued_from_xtb_figures_has_no_exit_costs() -> None:
    view = replay([_buy(1, XTB, NOPRICE, "2", "-400")], [], _market(), FRI, exit_rules=RULES).position(XTB, NOPRICE, FRI)

    assert (view.quote.source, view.value_pln, view.exit_cost_pln) == ("xtb", D("400.00"), D("0.00"))


def test_the_position_cost_is_the_sum_of_its_lots_rounded() -> None:
    book = replay([_buy(1, XTB, SXR8, "0.3", "-645"), _buy(2, XTB, SXR8, "0.7", "-1505")], [], _market(), FRI,
                  exit_rules=RULES)

    view = book.position(XTB, SXR8, FRI)
    # 765.00 × 0.5 % = 3.825 → 3.83; 1 785.00 × 0.5 % = 8.925 → 8.93
    assert [lot.exit_cost_pln for lot in view.lots] == [D("3.83"), D("8.93")]
    assert view.exit_cost_pln == D("12.76")


def test_rows_carry_the_exit_cost_and_foreign_cash_on_xtb_pays_the_fee() -> None:
    entries = [
        Entry(1, XTB, None, "deposit", MAR_02, D("10000"), "PLN"),
        _buy(2, XTB, SXR8, "2", "-4304.30"),
        Entry(3, XTB_USD, None, "deposit", MAR_02, D("1000"), "USD"),
    ]

    rows = {(row.account_id, row.instrument_id): row for row in daily_rows(entries, [], _market(), FRI,
                                                                         start=FRI, exit_rules=RULES)}

    assert rows[(XTB, SXR8)].exit_cost_pln == D("25.50")
    assert rows[(XTB, None)].exit_cost_pln == D("0.00")  # PLN cash
    assert (rows[(XTB_USD, None)].value_pln, rows[(XTB_USD, None)].exit_cost_pln) == (D("4000.00"), D("20.00"))


def test_the_day_change_is_net_of_the_exit_costs() -> None:
    book = replay([_buy(1, XTB, SXR8, "2", "-4304.30")], [], _market(), FRI, exit_rules=RULES)

    # 2 × (600 × 4.25 − 500 × 4.30) = 800.00 at market, × 99.5 % = 796.00
    assert book.day_change(XTB, SXR8, FRI, THU) == D("796.00")


def test_without_rules_nothing_is_charged() -> None:
    view = replay([_buy(1, XTB, SXR8, "2", "-4304.30")], [], _market(), FRI).position(XTB, SXR8, FRI)

    assert view.exit_cost_pln == D("0.00")
