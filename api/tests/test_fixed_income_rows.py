import datetime as dt
from decimal import Decimal as D

from app.bonds.edo import Series
from app.valuation.fixed_income import FLAG_RATE_ESTIMATED, Holding, SavingsInput, bond_rows, day_view, savings_rows

EDO0936 = Series(D("5.35"), D("2.00"), D("3.00"))
BOUGHT, SAT = dt.date(2026, 9, 15), dt.date(2026, 9, 26)


def _holding(**fields: object) -> Holding:
    values = {"id": 7, "account_id": 3, "purchase_date": BOUGHT, "quantity": 10, "redeemed_at": None,
              "series": EDO0936, "taxed": True, **fields}
    return Holding(**values)


def test_bond_rows_from_the_purchase_day_with_the_purchase_as_a_deposit() -> None:
    rows = bond_rows([_holding()], {}, dt.date.min, SAT)

    assert [row.day for row in rows] == [BOUGHT + dt.timedelta(days=n) for n in range(12)]
    first, last = rows[0], rows[-1]
    assert (first.value_pln, first.cost_pln, first.net_flow_pln, first.bond_holding_id) == (
        D("1000.00"), D("1000"), D("1000"), 7)
    # 11 days: 100 × (1 + 5.35 % × 11 / 365) = 100.16; tax 0.03 → 100.13 × 10
    assert (last.quantity, last.value_pln, last.net_flow_pln, last.instrument_id, last.flags) == (
        D("10"), D("1001.30"), D("0"), None, ())


def test_ike_bonds_are_valued_without_tax() -> None:
    assert bond_rows([_holding(taxed=False)], {}, SAT, SAT)[0].value_pln == D("1001.60")


def test_early_redemption_pays_out_on_its_day_and_leaves_the_next_day() -> None:
    rows = bond_rows([_holding(redeemed_at=dt.date(2026, 9, 20))], {}, dt.date(2026, 9, 19), SAT)

    # 5 days: 100.07 per bond, the fee takes the 0.07 zł of interest → 100.00 × 10
    assert [(row.day, row.value_pln, row.net_flow_pln) for row in rows] == [
        (dt.date(2026, 9, 19), D("1000.50"), D("0")),  # 100.06 − 0.01 tax
        (dt.date(2026, 9, 20), D("1000.00"), D("0")),
        (dt.date(2026, 9, 21), D("0"), D("-1000.00")),
    ]


def test_maturity_pays_the_net_value_of_all_periods() -> None:
    cpi = {dt.date(year, 7, 1): D("3.0") for year in range(2027, 2036)}  # every period after the 1st: 5.00 %
    rows = bond_rows([_holding(quantity=1)], cpi, dt.date(2036, 9, 14), dt.date(2036, 9, 30))

    # 163.43 gross at maturity, tax 19 % × 63.43 = 12.05 → 151.38
    assert [(row.day, row.value_pln, row.net_flow_pln) for row in rows][1:] == [
        (dt.date(2036, 9, 15), D("151.38"), D("0")), (dt.date(2036, 9, 16), D("0"), D("-151.38"))]


def test_rows_in_an_estimated_period_are_flagged() -> None:
    rows = bond_rows([_holding(purchase_date=dt.date(2025, 9, 15))], {}, SAT, SAT)  # 2nd period: no CPI for 07/2026
    assert rows[0].flags == (FLAG_RATE_ESTIMATED,)


def test_savings_rows_carry_balance_capital_and_flows() -> None:
    account = SavingsInput(4, 5, "monthly", True, [(dt.date(2026, 9, 1), D("10000"))],
                           [(dt.date(2026, 9, 1), D("5.00"))])

    rows = savings_rows([account], dt.date(2026, 10, 1), dt.date(2026, 10, 1))

    (row,) = rows
    assert (row.account_id, row.savings_account_id, row.quantity, row.value_pln, row.cost_pln, row.net_flow_pln) == (
        5, 4, D("10032.18"), D("10032.18"), D("10000.00"), D("0.00"))


def test_day_view_gives_the_row_and_its_change_net_of_the_days_flow() -> None:
    rows = bond_rows([_holding()], {}, dt.date(2026, 9, 25), SAT)

    row, change = day_view(rows, SAT)

    # 25 IX: 10 days → 100.15, tax 0.03 → 100.12 × 10 = 1001.20; 26 IX: 1001.30
    assert (row.value_pln, change) == (D("1001.30"), D("0.10"))
    assert day_view(bond_rows([_holding()], {}, BOUGHT, BOUGHT), BOUGHT)[1] == D("0.00")  # the purchase is a flow
    assert day_view(rows, dt.date(2026, 9, 27)) is None


def test_savings_rows_follow_deposits() -> None:
    sep_01, sep_30 = dt.date(2026, 9, 1), dt.date(2026, 9, 30)
    account = SavingsInput(1, 10, "monthly", True, [], [(sep_01, D("5"))], flows=[(sep_01, D("10000"))])

    rows = savings_rows([account], sep_01, sep_30 + dt.timedelta(days=1))

    assert (rows[0].net_flow_pln, rows[0].savings_account_id) == (D("10000.00"), 1)
    assert (rows[-1].value_pln, rows[-1].cost_pln, rows[-1].net_flow_pln) == (D("10033.29"), D("10000.00"), D("0.00"))
