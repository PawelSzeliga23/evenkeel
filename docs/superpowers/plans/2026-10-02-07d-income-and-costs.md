# Plan 7d — Dochód i koszty Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Analiza → Dochód i koszty: passive income (accrued interest on savings and bonds, XTB free-funds interest, dividends) against costs (XTB currency conversion, taxes, fees), month by month, with sources, cost kinds and a card on Analiza.

**Architecture:**
- **API:** `app/analytics/income.py` reads the user's bond and savings rows in `daily_valuations` (day-to-day value change minus flows = accrued interest after tax) and the transactions in the window (`amount_pln`). It buckets everything by month. `GET /api/analytics/income` serves it.
- **Web:** `screens/income/` holds the screen, a stacked bar chart (SVG) with tap targets per month, the source and cost lists, the month table and the card.

**Tech Stack:** FastAPI, SQLAlchemy, pytest; React, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-02-07d-income-and-costs-design.md`

## Global Constraints

- Periods are the wire values `12m|ytd|all`, labelled „12 mies.”, „Od pocz. roku”, „Wszystko”; the default is `ytd`.
- **Income is gross.** Taxes count only among the costs. Balance = income − costs.
- **Interest is accrued:** net of the day = `value_pln(d) − value_pln(d−1) − net_flow_pln(d)`. On regular accounts gross = net ÷ 0,81; on IKE/IKZE gross = net.
- **FX cost:** only on XTB accounts (`broker == "xtb"`), for buy or sell when the instrument or the account currency is not PLN.
  - Purchase: |amount| × 0,005 ÷ 1,005.
  - Sale: amount × 0,005 ÷ 0,995.
  - Rounded per transaction to the grosz.
- Exit costs (a sale today) are not counted.
- Commands:
  - `docker compose run --rm api pytest -q`;
  - `cd web && NO_COLOR=1 npx vitest run && npx tsc --noEmit`;
  - `npx playwright test`.

## Review Focus

1. **A deposit to a savings account inside a month** is not income; only the interest is. Pinned in Task 1.
2. **A purchase of a PLN instrument on XTB** (e.g. CDR.PL) has no conversion cost. This is the owner's real case. Pinned in Task 1.
3. **A bond bought inside the period:** its purchase day adds no income. Pinned in Task 1.
4. **A month with only costs, or a period with all zeros:** the chart draws under the zero line and does not divide by zero. Pinned in Task 2.
5. **The account filter on a savings-only account** shows only that account's interest and no XTB costs. Pinned in Task 1.

---

### Task 1: API

**Files:**
- Create `api/app/analytics/income.py` and `api/tests/test_income_api.py`.
- Modify `api/app/analytics/schemas.py` and `api/app/analytics/router.py`.

**Interfaces — Produces:**
- `IncomePeriod = Literal["12m", "ytd", "all"]`;
- `income(scope, account_ids, period) -> IncomeOut` (today = `local_today()`, patched in the tests);
- the schemas `IncomeTotalsOut`, `IncomeMonthOut`, `IncomeSourceOut`, `IncomeCostOut` and `IncomeOut`;
- `fx_cost(amount, fee) -> Decimal`;
- route `GET /api/analytics/income?period=&account_id=` (default `ytd`).

- [ ] **Step 1: Failing tests.** `api/tests/test_income_api.py`, using the valuation seed (XTB IKE, PLN account, SXR8.DE in EUR):
  - buy −4304.30 on 2026-03-02;
  - dividend 40 and withholding tax −6 on 06-15;
  - valued to Sat 2026-09-26.

  The tests use the route and patch `app.analytics.income.local_today` to Saturday:

```python
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.analytics.income import fx_cost
from app.models import (Account, BondHolding, BondSeries, Instrument, SavingsAccount, SavingsBalance, SavingsRate,
                        Transaction, User)
from tests.valuation_seed import SAT, seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/analytics/income"


@pytest.fixture(autouse=True)
def saturday(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("app.analytics.income.local_today", lambda: SAT)


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        sxr8 = seed_market(db)
        account_id = seed_holdings(db, user_id, sxr8)
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "user_id": user_id, "account_id": account_id, "sxr8": sxr8}


def _get(client: TestClient, headers: dict, **params: object) -> dict:
    response = client.get(URL, params=params, headers=headers)
    assert response.status_code == 200, response.text
    return response.json()


def _savings(engine: Engine, world: dict, wrapper: str = "regular") -> int:
    with Session(engine) as db:
        account = Account(user_id=world["user_id"], name="Trade Republic", kind="savings", wrapper=wrapper, currency="PLN")
        db.add(account)
        db.flush()
        savings = SavingsAccount(account_id=account.id, capitalization="monthly")
        db.add(savings)
        db.flush()
        db.add_all([SavingsRate(savings_account_id=savings.id, valid_from=dt.date(2026, 9, 1), annual_rate=Decimal("5")),
                    SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 9, 1), balance=Decimal("10000"))])
        db.commit()
        valuate(db, world["user_id"])
        return account.id


def test_fx_cost_is_the_fee_inside_the_amount() -> None:
    assert fx_cost(Decimal("-4304.30"), Decimal("0.005")) == Decimal("21.41")  # 4304.30 × 0.005 / 1.005
    assert fx_cost(Decimal("5100.00"), Decimal("0.005")) == Decimal("25.63")  # 5100 × 0.005 / 0.995
    assert fx_cost(Decimal("-810.00"), Decimal("0")) == Decimal("0")


def test_whole_history_income_and_costs(client: TestClient, world: dict) -> None:
    body = _get(client, world["anna"], period="all")

    assert body["period"] == {"start": "2026-03-01", "end": "2026-09-26"}
    assert body["totals"] == {"income_pln": "40.00", "costs_pln": "27.41", "balance_pln": "12.59"}  # 21.41 FX + 6 tax
    assert [m["month"] for m in body["months"]] == [f"2026-{m:02d}" for m in range(3, 10)]
    march = body["months"][0]
    assert (march["fx_pln"], march["costs_pln"], march["income_pln"]) == ("21.41", "21.41", "0.00")
    june = body["months"][3]
    assert (june["dividends_pln"], june["taxes_pln"], june["balance_pln"]) == ("40.00", "6.00", "34.00")
    assert body["sources"] == [{"key": f"d:{world['sxr8']}", "kind": "dividend", "name": "SXR8.DE Core S&P 500",
                                "gross_pln": "40.00", "tax_pln": "6.00", "net_pln": "34.00", "taxed": True}]
    assert body["costs"] == [
        {"key": "fx", "name": "Przewalutowanie XTB", "amount_pln": "21.41", "count": 1},
        {"key": "interest_tax", "name": "Podatek od odsetek", "amount_pln": "0.00", "count": 0},
        {"key": "withholding_tax", "name": "Podatek u źródła", "amount_pln": "6.00", "count": 1},
        {"key": "fees", "name": "Prowizje i opłaty", "amount_pln": "0.00", "count": 0},
    ]


def test_ytd_starts_at_the_first_month_with_history(client: TestClient, world: dict) -> None:
    body = _get(client, world["anna"], period="ytd")

    assert body["period"]["start"] == "2026-03-01" and body["months"][0]["month"] == "2026-03"


def test_twelve_months_end_in_the_current_month(client: TestClient, world: dict) -> None:
    months = _get(client, world["anna"], period="12m")["months"]

    assert (months[0]["month"], months[-1]["month"]) == ("2026-03", "2026-09")  # clamped to the history


def test_savings_interest_is_accrued_gross_and_the_deposit_is_not_income(
    client: TestClient, world: dict, engine: Engine,
) -> None:
    _savings(engine, world)

    body = _get(client, world["anna"], period="all")
    source = next(s for s in body["sources"] if s["kind"] == "savings")
    net, tax = Decimal(source["net_pln"]), Decimal(source["tax_pln"])

    assert source["name"] == "Trade Republic" and source["taxed"] is True
    assert Decimal("0") < net < Decimal("50")  # 10 000 zł at 5 % for September, not the deposit
    assert abs(tax - net * Decimal(19) / Decimal(81)) <= Decimal("0.01")
    assert Decimal(body["costs"][1]["amount_pln"]) == tax


def test_savings_on_ike_pay_no_tax(client: TestClient, world: dict, engine: Engine) -> None:
    _savings(engine, world, wrapper="ike")

    source = next(s for s in _get(client, world["anna"], period="all")["sources"] if s["kind"] == "savings")

    assert (source["tax_pln"], source["taxed"]) == ("0.00", False)


def test_a_bond_bought_in_the_period_earns_only_its_interest(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        bonds = Account(user_id=world["user_id"], name="Obligacje", kind="bonds", currency="PLN")
        db.add_all([bonds, BondSeries(series="EDO0336", bond_type="EDO", issue_month=dt.date(2026, 3, 1),
                                      maturity_months=120, first_period_rate=Decimal("6.25"), margin=Decimal("2.00"),
                                      early_redemption_fee=Decimal("3.00"), interest_mode="capitalized",
                                      rate_basis="cpi")])
        db.flush()
        db.add(BondHolding(account_id=bonds.id, bond_type="EDO", series="EDO0336", quantity=10,
                           purchase_date=dt.date(2026, 3, 2)))
        db.commit()
        valuate(db, world["user_id"])

    body = _get(client, world["anna"], period="all")
    bond = next(s for s in body["sources"] if s["kind"] == "bond")

    assert bond["key"] == "b:EDO0336"
    assert Decimal("0") < Decimal(bond["gross_pln"]) < Decimal("40")  # ~6.25 % of 1000 zł for 7 months, not 1000


def test_pln_instrument_on_xtb_has_no_conversion_cost(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        cdr = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", category="stock", currency="PLN", price_symbol="CDR.WA")
        db.add(cdr)
        db.flush()
        db.add(Transaction(account_id=world["account_id"], instrument_id=cdr.id, type="buy", xtb_type="buy",
                           occurred_at=dt.datetime(2026, 9, 21, 10, tzinfo=dt.UTC), amount=Decimal("-810"),
                           currency="PLN", quantity=Decimal("3"), price=Decimal("270"), external_id="cdr", comment="",
                           raw={}))
        db.commit()

    assert _get(client, world["anna"], period="all")["costs"][0]["count"] == 1  # only the SXR8.DE purchase


def test_xtb_interest_and_fees(client: TestClient, world: dict, engine: Engine) -> None:
    def tx(external_id: str, type_: str, amount: str) -> Transaction:
        return Transaction(account_id=world["account_id"], type=type_, xtb_type=type_, amount=Decimal(amount),
                           occurred_at=dt.datetime(2026, 9, 10, 10, tzinfo=dt.UTC), currency="PLN",
                           external_id=external_id, comment="", raw={})

    with Session(engine) as db:
        db.add_all([tx("i", "interest", "5.00"), tx("t", "interest_tax", "-0.95"), tx("f", "fee", "-2.00")])
        db.commit()

    body = _get(client, world["anna"], period="all")
    september = body["months"][-1]

    assert (september["interest_pln"], september["taxes_pln"], september["fees_pln"]) == ("5.00", "0.95", "2.00")
    xtb = next(s for s in body["sources"] if s["kind"] == "xtb_interest")
    assert (xtb["name"], xtb["net_pln"]) == ("Odsetki od wolnych środków · XTB IKE", "4.05")
    assert (body["costs"][1]["amount_pln"], body["costs"][3]["count"]) == ("0.95", 1)


def test_account_filter_on_a_savings_account(client: TestClient, world: dict, engine: Engine) -> None:
    savings_id = _savings(engine, world)

    body = _get(client, world["anna"], period="all", account_id=savings_id)

    assert [s["kind"] for s in body["sources"]] == ["savings"]
    assert body["costs"][0]["amount_pln"] == "0.00"
    foreign = client.get(URL, params={"account_id": savings_id}, headers=world["bartek"])
    assert foreign.status_code == 404


def test_no_data_and_unknown_period(client: TestClient, world: dict) -> None:
    assert _get(client, world["bartek"]) == {
        "period": None, "totals": {"income_pln": "0.00", "costs_pln": "0.00", "balance_pln": "0.00"},
        "months": [], "sources": [], "costs": [], "recalculating": False}
    assert client.get(URL, params={"period": "5y"}, headers=world["anna"]).status_code == 422
```

- [ ] **Step 2:** `docker compose run --rm api pytest tests/test_income_api.py -q` must FAIL with an import error.

- [ ] **Step 3: Schemas.** Append to `api/app/analytics/schemas.py`:

```python
class IncomeTotalsOut(BaseModel):
    income_pln: Decimal
    costs_pln: Decimal
    balance_pln: Decimal


class IncomeMonthOut(IncomeTotalsOut):
    month: str  # "2026-09"
    interest_pln: Decimal
    dividends_pln: Decimal
    fx_pln: Decimal
    taxes_pln: Decimal
    fees_pln: Decimal


class IncomeSourceOut(BaseModel):
    key: str  # s:{savings account id} | b:{bond series} | x:{account id} | d:{instrument id}
    kind: str  # savings | bond | xtb_interest | dividend
    name: str
    gross_pln: Decimal
    tax_pln: Decimal
    net_pln: Decimal
    taxed: bool


class IncomeCostOut(BaseModel):
    key: str  # fx | interest_tax | withholding_tax | fees
    name: str
    amount_pln: Decimal
    count: int


class IncomeOut(BaseModel):
    period: PeriodRangeOut | None
    totals: IncomeTotalsOut
    months: list[IncomeMonthOut]
    sources: list[IncomeSourceOut]
    costs: list[IncomeCostOut]
    recalculating: bool
```

- [ ] **Step 4: Implement** `api/app/analytics/income.py`:

```python
"""Dochód i koszty (plan 7d): passive income against costs, month by month.

Income (gross): interest accrued on savings accounts and bonds (the day's change of the cached value less its flows;
the value is after the 19 % tax on regular accounts, so gross = net ÷ 0.81), XTB free-funds interest and dividends.
Costs: XTB's 0.5 % currency conversion inside purchases and sales, taxes (interest, withholding) and fees.
"""
import datetime as dt
from collections import defaultdict
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal
from typing import Literal

from sqlalchemy import func, or_, select

from app.analytics.schemas import (IncomeCostOut, IncomeMonthOut, IncomeOut, IncomeSourceOut, IncomeTotalsOut,
                                   PeriodRangeOut)
from app.models import BondHolding, DailyValuation, Instrument, Transaction, User
from app.portfolio.service import amount_pln
from app.scoping import UserScope
from app.valuation.engine import ONE_DAY, ZERO, money
from app.valuation.exit_costs import XTB_FX_FEE
from app.valuation.market_data import BASE_CURRENCY
from app.valuation.service import local_day, local_today

IncomePeriod = Literal["12m", "ytd", "all"]
CENT = Decimal("0.01")
NET_SHARE = Decimal("0.81")  # interest left after the 19 % tax
XTB = "xtb"
TYPES = ("buy", "sell", "dividend", "withholding_tax", "interest", "interest_tax", "fee")
COSTS = {"fx": "Przewalutowanie XTB", "interest_tax": "Podatek od odsetek", "withholding_tax": "Podatek u źródła",
         "fees": "Prowizje i opłaty"}


def fx_cost(amount: Decimal, fee: Decimal) -> Decimal:
    """XTB's fee inside a trade's PLN amount: a purchase pays converted × (1 + fee), a sale gets converted × (1 − fee)."""
    if not fee or not amount:
        return ZERO
    base = 1 + fee if amount < 0 else 1 - fee
    return (abs(amount) * fee / base).quantize(CENT, rounding=ROUND_HALF_UP)


def _month(day: dt.date) -> str:
    return f"{day.year}-{day.month:02d}"


def _months(start: dt.date, end: dt.date) -> list[str]:
    months, year, month = [], start.year, start.month
    while (year, month) <= (end.year, end.month):
        months.append(f"{year}-{month:02d}")
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    return months


def window(period: IncomePeriod, first: dt.date, today: dt.date) -> dt.date:
    """The period's first day, never before the month of the first data."""
    if period == "12m":
        months_back = today.year * 12 + today.month - 1 - 11
        start = dt.date(months_back // 12, months_back % 12 + 1, 1)
    elif period == "ytd":
        start = dt.date(today.year, 1, 1)
    else:
        start = first
    return max(start, first.replace(day=1))


@dataclass
class _Month:
    interest: Decimal = ZERO
    dividends: Decimal = ZERO
    fx: Decimal = ZERO
    taxes: Decimal = ZERO
    fees: Decimal = ZERO


@dataclass
class _Source:
    kind: str
    name: str
    taxed: bool
    gross: Decimal = ZERO
    tax: Decimal = ZERO


def _totals(income: Decimal, costs: Decimal) -> dict[str, Decimal]:
    return {"income_pln": money(income), "costs_pln": money(costs), "balance_pln": money(income - costs)}


def income(scope: UserScope, account_ids: frozenset[int] | None, period: IncomePeriod) -> IncomeOut:
    db = scope.db
    today = local_today()
    recalculating = db.scalar(select(User.valuations_stale_from).where(User.id == scope.user.id)) is not None
    accounts = {account.id: account for account in db.scalars(scope.accounts())}
    wanted = (lambda column: column.in_(account_ids)) if account_ids is not None else (lambda column: True)

    fixed = scope.daily_valuations().where(
        or_(DailyValuation.bond_holding_id.is_not(None), DailyValuation.savings_account_id.is_not(None)),
        wanted(DailyValuation.account_id))
    trades = scope.transactions().where(Transaction.type.in_(TYPES), wanted(Transaction.account_id))
    transactions = list(db.scalars(trades).unique())
    days = [local_day(t.occurred_at) for t in transactions]
    first_valued = db.scalar(fixed.with_only_columns(func.min(DailyValuation.date)))
    firsts = days + ([first_valued] if first_valued else [])
    if not firsts:
        return IncomeOut(period=None, totals=IncomeTotalsOut(**_totals(ZERO, ZERO)), months=[], sources=[], costs=[],
                         recalculating=recalculating)
    start = window(period, min(firsts), today)
    months: dict[str, _Month] = {month: _Month() for month in _months(start, today)}
    sources: dict[str, _Source] = {}
    costs = {key: [ZERO, 0] for key in COSTS}

    def source(key: str, kind: str, name: str, taxed: bool) -> _Source:
        return sources.setdefault(key, _Source(kind, name, taxed))

    series = dict(db.execute(scope.bond_holdings().with_only_columns(BondHolding.id, BondHolding.series)).all())
    previous: dict[tuple[int | None, int | None], tuple[dt.date, Decimal]] = {}
    for row in db.execute(fixed.with_only_columns(
        DailyValuation.date, DailyValuation.account_id, DailyValuation.bond_holding_id,
        DailyValuation.savings_account_id, DailyValuation.value_pln, DailyValuation.net_flow_pln,
    ).where(DailyValuation.date.between(start - ONE_DAY, today)).order_by(
        DailyValuation.bond_holding_id, DailyValuation.savings_account_id, DailyValuation.date,
    )):
        component = (row.bond_holding_id, row.savings_account_id)
        last = previous.get(component)
        previous[component] = (row.date, row.value_pln)
        if row.date < start:
            continue
        before = last[1] if last is not None and last[0] == row.date - ONE_DAY else ZERO
        net = row.value_pln - before - row.net_flow_pln
        if not net:
            continue
        taxed = accounts[row.account_id].wrapper == "regular"
        gross = net / NET_SHARE if taxed else net
        month = months[_month(row.date)]
        month.interest += gross
        month.taxes += gross - net
        costs["interest_tax"][0] += gross - net
        if row.bond_holding_id is not None:
            item = source(f"b:{series[row.bond_holding_id]}", "bond", series[row.bond_holding_id], taxed)
        else:
            item = source(f"s:{row.savings_account_id}", "savings", accounts[row.account_id].name, taxed)
        item.gross += gross
        item.tax += gross - net

    instruments = {i.id: i for i in db.scalars(select(Instrument).where(
        Instrument.id.in_({t.instrument_id for t in transactions if t.instrument_id is not None})))}
    for transaction, day in zip(transactions, days):
        if not start <= day <= today:
            continue
        month = months[_month(day)]
        account = accounts[transaction.account_id]
        amount = amount_pln(db, transaction)
        kind = transaction.type
        if kind in ("buy", "sell"):
            instrument = instruments.get(transaction.instrument_id)
            foreign = {instrument.currency if instrument else None, transaction.currency, account.currency} - {
                None, BASE_CURRENCY}
            cost = fx_cost(amount, XTB_FX_FEE if account.broker == XTB and foreign else ZERO)
            if cost:
                month.fx += cost
                costs["fx"][0] += cost
                costs["fx"][1] += 1
        elif kind in ("dividend", "withholding_tax"):
            instrument = instruments.get(transaction.instrument_id)
            name = f"{instrument.xtb_ticker} {instrument.name}" if instrument else "Dywidendy"
            item = source(f"d:{transaction.instrument_id}", "dividend", name, True)
            if kind == "dividend":
                month.dividends += amount
                item.gross += amount
            else:
                month.taxes -= amount
                item.tax -= amount
                costs["withholding_tax"][0] -= amount
                costs["withholding_tax"][1] += 1
        elif kind in ("interest", "interest_tax"):
            item = source(f"x:{account.id}", "xtb_interest", f"Odsetki od wolnych środków · {account.name}",
                          account.wrapper == "regular")
            if kind == "interest":
                month.interest += amount
                item.gross += amount
            else:
                month.taxes -= amount
                item.tax -= amount
                costs["interest_tax"][0] -= amount
                costs["interest_tax"][1] += 1
        else:  # fee
            month.fees -= amount
            costs["fees"][0] -= amount
            costs["fees"][1] += 1

    out_months = []
    for key, m in months.items():
        earned, spent = m.interest + m.dividends, m.fx + m.taxes + m.fees
        out_months.append(IncomeMonthOut(
            month=key, interest_pln=money(m.interest), dividends_pln=money(m.dividends), fx_pln=money(m.fx),
            taxes_pln=money(m.taxes), fees_pln=money(m.fees), **_totals(earned, spent)))
    earned = sum((m.interest + m.dividends for m in months.values()), ZERO)
    spent = sum((m.fx + m.taxes + m.fees for m in months.values()), ZERO)
    shown = sorted((s for s in sources.items() if s[1].gross or s[1].tax), key=lambda s: (-s[1].gross, s[1].name))
    return IncomeOut(
        period=PeriodRangeOut(start=start, end=today), totals=IncomeTotalsOut(**_totals(earned, spent)),
        months=out_months,
        sources=[IncomeSourceOut(key=key, kind=s.kind, name=s.name, gross_pln=money(s.gross), tax_pln=money(s.tax),
                                 net_pln=money(s.gross - s.tax), taxed=s.taxed) for key, s in shown],
        costs=[IncomeCostOut(key=key, name=COSTS[key], amount_pln=money(amount), count=count)
               for key, (amount, count) in costs.items()],
        recalculating=recalculating,
    )
```

  Route in `api/app/analytics/router.py`:

```python
@router.get("/analytics/income", response_model=IncomeOut)
def get_income(scope: UserScope = Depends(get_scope), account_ids: AccountIds = None,
               period: IncomePeriod = "ytd") -> IncomeOut:
    return income(scope, scope.account_filter(account_ids), period)
```

  - The `period.end` in the whole-history test is the patched `today` (Sat 09-26). The months run up to `today`'s month.
  - `local_today` must be imported into `income.py` by name so the test can patch it. If `app.valuation.service` has no `local_today`, use the helper the dashboard uses for "today".
  - Check `scope.bond_holdings()` exists (it is used by `holdings.py`).
- [ ] **Step 5:** Run the new tests until they pass, then the full suite `docker compose run --rm api pytest -q`.
  - When an expected figure in a test turns out wrong (e.g. the savings or bond ranges), check it against the engine's own numbers before changing the expectation. Never loosen an assertion only to make it pass.
- [ ] **Step 6:** Commit `feat(api): passive income and costs per month — accrued interest, dividends, XTB conversion, taxes, fees`.

### Task 2: Income chart and model

**Files:**
- Create `web/src/screens/income/model.ts`, `model.test.ts`, `IncomeChart.tsx`, `IncomeChart.test.tsx` and `Income.module.css`.
- Modify `web/src/api/types.ts`.

**Interfaces — Produces:**
- types `IncomePeriod`, `IncomeMonth`, `IncomeSource`, `IncomeCost`, `Income`;
- `PERIODS`;
- `buckets(months) -> Bucket[]` (`{ key, label, title, interest, dividends, fx, taxes, fees, income, costs, balance }`, numbers; months, or years when there are more than 24 months);
- `IncomeChart({ buckets, selected, onSelect })`.

- [ ] **Step 1: Types.** Append to `web/src/api/types.ts`:

```ts
export type IncomePeriod = "12m" | "ytd" | "all";

export interface IncomeTotals { income_pln: Money; costs_pln: Money; balance_pln: Money }

export interface IncomeMonth extends IncomeTotals {
  month: string; // "2026-09"
  interest_pln: Money;
  dividends_pln: Money;
  fx_pln: Money;
  taxes_pln: Money;
  fees_pln: Money;
}

export interface IncomeSource {
  key: string;
  kind: "savings" | "bond" | "xtb_interest" | "dividend";
  name: string;
  gross_pln: Money;
  tax_pln: Money;
  net_pln: Money;
  taxed: boolean;
}

export interface IncomeCost { key: "fx" | "interest_tax" | "withholding_tax" | "fees"; name: string; amount_pln: Money; count: number }

export interface Income {
  period: { start: IsoDate; end: IsoDate } | null;
  totals: IncomeTotals;
  months: IncomeMonth[];
  sources: IncomeSource[];
  costs: IncomeCost[];
  recalculating: boolean;
}
```

- [ ] **Step 2: Failing tests.**

  `model.test.ts`:
  - `buckets` of 3 months gives 3 month buckets labelled „sie”, „wrz”, „paź”, titled „wrz 2026”;
  - 30 months give 3 year buckets („2024”, „2025”, „2026”) with summed numbers (income 2024 = Σ of its months);
  - the numbers are `Number(...)` of the money strings.

  `IncomeChart.test.tsx`:
  - the chart is an `img` named „Dochód i koszty w miesiącach”;
  - there is a button per bucket, named „wrz 2026: dochód +63,80 zł, koszty −49,70 zł”;
  - a click calls `onSelect("2026-09")`;
  - a bucket with only costs draws a rect below the zero line, i.e. `y` ≥ the zero line's `y1`;
  - all-zero buckets render without NaN (no `NaN` in the SVG markup).

- [ ] **Step 3: Implement.**

  `model.ts`:

```ts
import type { IncomeMonth, IncomePeriod } from "../../api/types";
import { MONTHS } from "../analysis/model";

export const PERIODS: { value: IncomePeriod; label: string }[] = [
  { value: "12m", label: "12 mies." }, { value: "ytd", label: "Od pocz. roku" }, { value: "all", label: "Wszystko" },
];

export interface Bucket {
  key: string; label: string; title: string;
  interest: number; dividends: number; fx: number; taxes: number; fees: number;
  income: number; costs: number; balance: number;
}

const YEARS_FROM = 24;

function fromMonth(m: IncomeMonth): Bucket {
  const [year, month] = m.month.split("-");
  const name = MONTHS[Number(month) - 1]!;
  return {
    key: m.month, label: name, title: `${name} ${year}`,
    interest: Number(m.interest_pln), dividends: Number(m.dividends_pln), fx: Number(m.fx_pln),
    taxes: Number(m.taxes_pln), fees: Number(m.fees_pln), income: Number(m.income_pln), costs: Number(m.costs_pln),
    balance: Number(m.balance_pln),
  };
}

/** Months as chart buckets; years once there are more than 24 months (the bars would be too thin). */
export function buckets(months: IncomeMonth[]): Bucket[] {
  const all = months.map(fromMonth);
  if (all.length <= YEARS_FROM) return all;
  const years = new Map<string, Bucket>();
  for (const b of all) {
    const year = b.key.slice(0, 4);
    const sum = years.get(year) ?? { ...b, key: year, label: year, title: year, interest: 0, dividends: 0, fx: 0, taxes: 0, fees: 0, income: 0, costs: 0, balance: 0 };
    for (const field of ["interest", "dividends", "fx", "taxes", "fees", "income", "costs", "balance"] as const) sum[field] += b[field];
    years.set(year, sum);
  }
  return [...years.values()];
}
```

  `IncomeChart.tsx`:
  - an SVG of width from `useWidth` (default 340) and height 180;
  - the zero line sits at the share `maxIncome / (maxIncome + maxCosts)` of the plot height, falling back to the middle when both are 0;
  - per bucket, the income rects (interest green `#5DB98A`, dividends blue `#7FB6E6`) are stacked upwards from the zero line, and the costs (fx red `#E0676E`, taxes violet `#B07FE0`, fees amber `#F0A43A`) are stacked downwards;
  - month labels sit under the plot, every n-th label when they would overlap;
  - over the SVG, an absolutely positioned transparent `<button>` per column, `aria-pressed` for the selected bucket, named with `formatMoney(String(b.income.toFixed(2)), { sign: true })` and the costs as `formatMoney(-costs)`;
  - a legend under the chart.

- [ ] **Step 4:** `cd web && NO_COLOR=1 npx vitest run src/screens/income && npx tsc --noEmit` passes.
- [ ] **Step 5:** Commit `feat(web): income and costs chart — stacked bars over and under zero, months or years`.

### Task 3: Screen, card, routes, e2e

**Files:**
- Modify `web/src/api/endpoints.ts` (`income: (ids, period) => request<Income>("/api/analytics/income", { query: { account_id: ids, period } })`) and `web/src/api/queryKeys.ts` (`income: (ids, period) => ["portfolio", "income", ids, period]`).
- Create `web/src/screens/income/IncomeScreen.tsx`, `IncomeCard.tsx` and `income.test.tsx`.
- Modify `web/src/routes.tsx` (`/analiza/dochod`) and `web/src/screens/analysis/AnalysisScreen.tsx` (`<IncomeCard />` after `<HoldingsCard />`).
- Add the fixtures `INCOME` and `INCOME_EMPTY` in `web/src/test/fixtures.ts`, plus the e2e step and the roadmap entry.

- [ ] **Step 1: Failing tests** (`income.test.tsx`, `mockFetch` routes like `holdings.test.tsx`):
  - asks `period=ytd` by default and `period=12m` after a click on „12 mies.”;
  - the tiles „Dochód” +82,34 zł, „Koszty” −69,10 zł and „Bilans” +13,24 zł (groups by name);
  - „Skąd dochód”:
    - the Trade Republic row reads „brutto 58,10 zł − Belka 11,04 zł”, with net +47,06 zł;
    - the EDO row on IKE reads „bez podatku”;
    - the dividend row uses „podatek u źródła”;
    - with no dividend source, the row reads „Dywidendy · na razie brak”;
  - „Na co koszty”: four rows. Przewalutowanie reads „0,5 % przy zakupach i sprzedaży w obcej walucie · 12 transakcji”; Prowizje reads „XTB: 0 % do 100 tys. € obrotu” when 0;
  - a click on a month's button shows its details: dochód, koszty and bilans, plus the split of odsetki / dywidendy / przewalutowanie / podatki / opłaty;
  - the table „Miesiące” lists rows from the newest;
  - empty state: „Nie ma jeszcze danych do pokazania.”;
  - the Analiza card „Dochód i koszty” shows „Dochód od pocz. roku” and „Koszty od pocz. roku”; its link „Szczegóły” leads to the screen.
- [ ] **Step 2: Implement.**
  - **Screen:**
    - follows `HoldingsScreen`: `BackLink` „Analiza”, `AccountSelect`, `Segmented` „Okres”;
    - a query with `placeholderData`, a stale class and a recalculation poll;
    - tiles as in `AnalysisScreen` `Tile` (without InfoTip), the `IncomeChart`, the month details, the two lists using `ui.row` and the table;
    - on a period change, the selected month resets.
  - **Card:** follows `AnalyticsCard`, with a `ui.kv` list and `Link` „Szczegóły” to `/analiza/dochod` (aria-label „Szczegóły dochodu i kosztów”). It is hidden while there is no data or on error, and polls while recalculating.
- [ ] **Step 3:** e2e in `web/e2e/app.spec.ts`, after the Walory step:
  - on Analiza, click the link „Szczegóły dochodu i kosztów”;
  - expect the heading „Dochód i koszty” and the `img` „Dochód i koszty w miesiącach”;
  - take the screenshot `dochod.png`;
  - go back to Analiza.
- [ ] **Step 4:**
  - Full web suite, `tsc` and `npx playwright test`.
  - Roadmap: the 7d row goes ✅ and the row 7e–7f stays „później”.
  - Commit `feat(web): Dochód i koszty — tiles, monthly chart, sources, costs, months; card on Analiza`.
