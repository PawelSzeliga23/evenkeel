# Plan 7e — Wykres ceny waloru Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** In the position details, a price chart in the instrument's currency (as in XTB), with markers for the owner's purchases, sales and dividends, the average purchase price line, ranges and gestures.

**Architecture:**
- **API:** `app/portfolio/price_chart.py` reads the closes from `prices` and thins the series to ≤ 800 points. It builds markers from the position's transactions, adjusted by splits; `price_with_fx` is the PLN paid ÷ quantity ÷ NBP rate, the same as the lots' `open_price_with_fx`. `GET /api/positions/{account_id}/{instrument_id}/prices?from=` serves it.
- **Web:**
  - `charts/PriceChart.tsx` draws the chart, reusing `useChartGestures` and `viewport.ts` (windows over point indices) and placing markers by date between points;
  - `screens/positions/PriceSection.tsx` holds the section: ranges, the header change and the operation panel;
  - the section sits in `PositionDetailScreen` under the head.

**Tech Stack:** FastAPI, SQLAlchemy, pytest; React, TanStack Query, Vitest, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-02-07e-price-chart-design.md`

## Global Constraints

- Prices are in the instrument's quote currency, never converted to PLN.
- **Ranges:** „Od zakupu” (default; from 14 days before the first purchase, 1R when there is none) · 6M · 1R · 5L · Maks.
- **Colours:**
  - price line `var(--ink)`;
  - purchase ▲ `#5DB98A`, sale ▼ `#E0676E`, dividend „D” `#7FB6E6`;
  - average dashed `#F0A43A` with the label „średnia {cena}”.
- At most 800 points from the API; the first and last point are always kept.
- **Markers:** a split after the operation's day divides its price and multiplies its quantity, so the marker lies on the split-adjusted closes.
- Commands:
  - `docker compose run --rm api pytest -q`;
  - `cd web && NO_COLOR=1 npx vitest run && npx tsc --noEmit`;
  - `npx playwright test`.

## Review Focus

1. **A split after a purchase:** the marker sits on the adjusted price line, not 4× above it. Pinned in Task 1.
2. **A PLN instrument on a PLN account:** no „z przewalutowaniem” line in the panel (`price_with_fx` null). Pinned in Task 1 and Task 3.
3. **Two operations on the same day:** two separate, tappable markers. Pinned in Task 2.
4. **An instrument without closes** (a fresh ticker): „Brak notowań dla tego instrumentu.” and no crash. Pinned in Task 2.
5. **A marker outside the chosen range** (e.g. 6M with a purchase from last year): it is not drawn and does not stretch the axis. Pinned in Task 2.

---

### Task 1: API

**Files:**
- Create `api/app/portfolio/price_chart.py` and `api/tests/test_price_chart_api.py`.
- Modify `api/app/portfolio/schemas.py` and `api/app/portfolio/router.py`.

**Interfaces — Produces:**
- `PricePointOut {date, close}`;
- `PriceMarkerOut {date, kind, price, price_with_fx, quantity, amount_pln}`;
- `PriceChartOut {currency, points, markers, first_buy}`;
- `price_chart(scope, account, instrument, start: date | None) -> PriceChartOut`;
- `thin(points, limit=800)`;
- route `GET /api/positions/{account_id}/{instrument_id}/prices?from=YYYY-MM-DD`.

- [ ] **Step 1: Failing tests** `api/tests/test_price_chart_api.py`. The valuation seed has SXR8.DE (EUR) closes 500 on 03-02 and 600 on 09-25, EUR 4.30, then 4.25 from 09-25. The XTB IKE account (PLN) has buy −4304.30, 2 units, price 500.5 on 03-02, and a dividend of 40 on 06-15.

```python
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, CorporateAction, Instrument, Price, Transaction, User
from app.portfolio.price_chart import thin
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        sxr8 = seed_market(db)
        account_id = seed_holdings(db, user_id, sxr8)
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "user_id": user_id, "account_id": account_id, "sxr8": sxr8}


def _url(world: dict, instrument: int | None = None) -> str:
    return f"/api/positions/{world['account_id']}/{instrument or world['sxr8']}/prices"


def _get(client: TestClient, world: dict, **params: object) -> dict:
    response = client.get(_url(world), params=params, headers=world["anna"])
    assert response.status_code == 200, response.text
    return response.json()


def test_closes_markers_and_first_buy(client: TestClient, world: dict) -> None:
    body = _get(client, world)

    assert body["currency"] == "EUR" and body["first_buy"] == "2026-03-02"
    assert body["points"] == [{"date": "2026-03-02", "close": "500.00"}, {"date": "2026-09-25", "close": "600.00"}]
    buy, dividend = body["markers"]
    assert (buy["date"], buy["kind"], buy["price"], buy["quantity"], buy["amount_pln"]) == (
        "2026-03-02", "buy", "500.5", "2", "-4304.30")
    assert buy["price_with_fx"] == "500.50"  # 4304.30 zł ÷ 2 ÷ 4.30
    assert (dividend["kind"], dividend["amount_pln"], dividend["price"]) == ("dividend", "40.00", None)


def test_from_limits_the_closes(client: TestClient, world: dict) -> None:
    assert [p["date"] for p in _get(client, world, **{"from": "2026-06-01"})["points"]] == ["2026-09-25"]


def test_thin_keeps_both_ends() -> None:
    points = [(dt.date(2020, 1, 1) + dt.timedelta(days=i), Decimal(i)) for i in range(2001)]

    kept = thin(points, 800)

    assert len(kept) <= 800 and kept[0] == points[0] and kept[-1] == points[-1]


def test_a_split_adjusts_the_marker(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.add(CorporateAction(instrument_id=world["sxr8"], type="split", effective_date=dt.date(2026, 6, 1),
                               ratio_from=Decimal(1), ratio_to=Decimal(4), source="provider"))
        db.commit()

    buy = _get(client, world)["markers"][0]

    assert (Decimal(buy["price"]), Decimal(buy["quantity"])) == (Decimal("125.125"), Decimal("8"))


def test_a_pln_instrument_has_no_price_with_fx_and_a_missing_price_takes_the_close(
    client: TestClient, world: dict, engine: Engine,
) -> None:
    with Session(engine) as db:
        cdr = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", category="stock", currency="PLN", price_symbol="CDR.WA")
        db.add(cdr)
        db.flush()
        db.add_all([Price(instrument_id=cdr.id, date=dt.date(2026, 9, 21), close=Decimal("270"), source="yahoo"),
                    Transaction(account_id=world["account_id"], instrument_id=cdr.id, type="buy", xtb_type="buy",
                                occurred_at=dt.datetime(2026, 9, 21, 10, tzinfo=dt.UTC), amount=Decimal("-810"),
                                currency="PLN", quantity=Decimal("3"), price=None, external_id="cdr", comment="",
                                raw={})])
        db.commit()
        cdr_id = cdr.id

    body = client.get(_url(world, cdr_id), headers=world["anna"]).json()

    assert body["currency"] == "PLN"
    assert (body["markers"][0]["price"], body["markers"][0]["price_with_fx"]) == ("270.00", None)


def test_foreign_account_is_404(client: TestClient, world: dict) -> None:
    assert client.get(_url(world), headers=world["bartek"]).status_code == 404
```

- [ ] **Step 2:** Run `docker compose run --rm api pytest tests/test_price_chart_api.py -q`. Expect FAIL (no module).
- [ ] **Step 3: Schemas.** Append to `api/app/portfolio/schemas.py`:

```python
class PricePointOut(BaseModel):
    date: dt.date
    close: Decimal


class PriceMarkerOut(BaseModel):
    date: dt.date
    kind: Literal["buy", "sell", "dividend"]
    price: Decimal | None  # quote currency, after later splits
    price_with_fx: Decimal | None  # PLN paid ÷ quantity ÷ NBP rate (XTB's conversion inside), foreign only
    quantity: Decimal | None  # after later splits
    amount_pln: Decimal


class PriceChartOut(BaseModel):
    currency: str | None
    points: list[PricePointOut]
    markers: list[PriceMarkerOut]
    first_buy: dt.date | None
```

- [ ] **Step 4: Implement** `api/app/portfolio/price_chart.py`:

```python
"""Wykres ceny (plan 7e): the instrument's closes in its own currency, with the position's operations on them."""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import select

from app.models import Account, Instrument, Price, Transaction
from app.portfolio.schemas import PriceChartOut, PriceMarkerOut, PricePointOut
from app.portfolio.service import amount_pln
from app.scoping import UserScope
from app.valuation.actions import resolve
from app.valuation.engine import ONE, Split
from app.valuation.market_data import fx_on
from app.valuation.service import _actions, local_day

LIMIT = 800
KINDS = ("buy", "sell", "dividend")
PRICE = Decimal("0.01")


def thin(points: list[tuple[dt.date, Decimal]], limit: int = LIMIT) -> list[tuple[dt.date, Decimal]]:
    """Every n-th point so that at most `limit` remain, always with the first and the last."""
    if len(points) <= limit:
        return points
    step = -(-(len(points) - 1) // (limit - 1))
    kept = points[::step]
    return kept if kept[-1] == points[-1] else [*kept[:limit - 1], points[-1]]


def _factor(splits: list[Split], day: dt.date) -> Decimal:
    result = ONE
    for split in splits:
        if split.effective_date > day:
            result *= split.factor
    return result


def price_chart(scope: UserScope, account: Account, instrument: Instrument, start: dt.date | None) -> PriceChartOut:
    db = scope.db
    query = select(Price.date, Price.close).where(Price.instrument_id == instrument.id).order_by(Price.date)
    closes = [(day, close) for day, close in db.execute(query)]
    shown = [(day, close) for day, close in closes if start is None or day >= start]
    by_day = dict(closes)

    splits, _ = resolve(_actions(db, scope.user.id, {instrument.id}))
    own = [s for s in splits if s.instrument_id == instrument.id]
    transactions = list(db.scalars(scope.transactions().where(
        Transaction.account_id == account.id, Transaction.instrument_id == instrument.id,
        Transaction.type.in_(KINDS))).unique())
    foreign = instrument.currency not in (None, account.currency)
    markers = []
    for t in sorted(transactions, key=lambda t: t.occurred_at):
        day = local_day(t.occurred_at)
        amount = amount_pln(db, t).quantize(PRICE, rounding=ROUND_HALF_UP)
        if t.type == "dividend":
            markers.append(PriceMarkerOut(date=day, kind="dividend", price=None, price_with_fx=None, quantity=None,
                                          amount_pln=amount))
            continue
        factor = _factor(own, day)
        quantity = abs(t.quantity) * factor if t.quantity else None
        price = t.price / factor if t.price is not None else _close_on(closes, day)
        with_fx = None
        if foreign and quantity:
            rate = fx_on(db, instrument.currency, day)
            with_fx = (abs(amount) / quantity / rate).quantize(PRICE, rounding=ROUND_HALF_UP) if rate else None
        markers.append(PriceMarkerOut(date=day, kind=t.type, price=price, price_with_fx=with_fx, quantity=quantity,
                                      amount_pln=amount))
    buys = [m.date for m in markers if m.kind == "buy"]
    return PriceChartOut(currency=instrument.currency, points=[PricePointOut(date=d, close=c) for d, c in thin(shown)],
                         markers=markers, first_buy=min(buys) if buys else None)


def _close_on(closes: list[tuple[dt.date, Decimal]], day: dt.date) -> Decimal | None:
    """The close of `day` or the last one before it."""
    before = [close for d, close in closes if d <= day]
    return before[-1].quantize(PRICE, rounding=ROUND_HALF_UP) if before else None
```

  Notes for the implementer:
  - **`fx_on`:** check where `fx_on` lives (`amount_pln` uses it in `app/portfolio/service.py`) and import it from there.
  - **Seed price check:** in the seed, 4304.30 ÷ 2 ÷ 4.30 = 500.50, which is the expected `price_with_fx`.

  Route in `api/app/portfolio/router.py`:

```python
@router.get("/positions/{account_id}/{instrument_id}/prices", response_model=PriceChartOut)
def get_position_prices(
    account_id: DbId, instrument_id: DbId, scope: UserScope = Depends(get_scope),
    start: dt.date | None = Query(None, alias="from"),
) -> PriceChartOut:
    account, instrument = scope.get_account(account_id), scope.get_instrument(instrument_id)
    return price_chart(scope, account, instrument, start)
```

- [ ] **Step 5:** Run the new tests and the full suite. Never loosen an expectation without checking the numbers.
- [ ] **Step 6:** Commit `feat(api): price chart of a position — closes in its currency, operations as markers, splits applied`.

### Task 2: Price chart component

**Files:**
- Create `web/src/charts/PriceChart.tsx`, `PriceChart.module.css` and `PriceChart.test.tsx`.
- Create `web/src/screens/positions/priceModel.ts` and `priceModel.test.ts`.
- Modify `web/src/api/types.ts`.

**Interfaces — Produces:**
- types `PricePoint {date, close}`, `PriceMarker {date, kind, price, price_with_fx, quantity, amount_pln}` and `PriceChartData {currency, points, markers, first_buy}`;
- `PRICE_RANGES: {value: PriceRange; label}[]` with `PriceRange = "buy" | "6m" | "1y" | "5y" | "max"`;
- `rangeFrom(range, firstBuy, today) -> string | null` (ISO, `null` = Maks);
- `markerLabel(marker, currency) -> string`;
- `PriceChart({ data, average, selected, onSelect })`, where `selected` is a marker index.

- [ ] **Step 1: Tests.**
  - **`priceModel.test.ts`:**
    - `rangeFrom("buy", "2026-03-02", "2026-10-02")` is `"2026-02-16"`;
    - `rangeFrom("buy", null, …)` falls back to a year: `"2025-10-02"`;
    - `"6m"` gives `"2026-04-02"`, `"5y"` gives `"2021-10-02"` and `"max"` gives `null`;
    - `markerLabel` reads „Zakup 02.03.2026, 2 szt. po 500,50 €”, „Sprzedaż …” and „Dywidenda 15.06.2026, +40,00 zł”.
  - **`PriceChart.test.tsx`:**
    - an `img` named „Wykres ceny”;
    - a button per marker named with `markerLabel`; a click calls `onSelect(index)`;
    - two markers on the same day give two buttons with different `left`;
    - the average line has the text „średnia 593,40 €”, and there is no average line when `average` is null;
    - a marker before the first point is not rendered;
    - fewer than 2 points renders the text „Brak notowań dla tego instrumentu.”.
- [ ] **Step 2: Implement.**
  - **`priceModel.ts`:** labels „Od zakupu”, „6M”, „1R”, „5L”, „Maks”. Dates are computed with `addMonths` from `format`, and `todayIso` is used for today. `markerLabel` uses `formatDecimal(quantity, 8)`, `formatDecimal(price, 4)`, the currency symbol (`€` for EUR, `$` for USD, `zł` for PLN, otherwise the code) and `formatDate`.
  - **`PriceChart`:**
    - the frame follows `geometry.FRAME` (axis on the right). The y range is the min and max of the visible closes and visible marker prices, padded 5 %; it uses `geometry`'s tick helper if one fits, otherwise 3 ticks;
    - the x position of a date is found from the index of the first point ≥ date, interpolated between that point and the one before;
    - gestures come from `useChartGestures` with `view` and `count = points.length`; a double tap resets to the full window;
    - each marker is a triangle ▲ below the price (buy) or ▼ above it (sell), or a „D” circle on the bottom axis;
    - over each marker there is an absolutely positioned `<button>` of 28 × 28 px with `aria-pressed`. Markers on the same date are shifted by 10 px each.
- [ ] **Step 3:** Run `cd web && NO_COLOR=1 npx vitest run src/charts/PriceChart.test.tsx src/screens/positions/priceModel.test.ts && npx tsc --noEmit`.
- [ ] **Step 4:** Commit `feat(web): price chart with operation markers, average line and gestures`.

### Task 3: Section in the position details, e2e

**Files:**
- Modify `web/src/api/endpoints.ts` (`positionPrices(accountId, instrumentId, from: string | null)`) and `web/src/api/queryKeys.ts` (`positionPrices: (a, i, from) => ["portfolio", "position-prices", a, i, from]`).
- Create `web/src/screens/positions/PriceSection.tsx` and `priceSection.test.tsx`.
- Modify `web/src/screens/positions/PositionDetailScreen.tsx` (the section after the head), the fixtures (`PRICE_CHART`), the e2e step and the roadmap.

- [ ] **Step 1: Tests** (`priceSection.test.tsx`, rendering `/pozycje/2/10` like the existing position detail tests, with a route for `/api/positions/2/10/prices`):
  - **„Od zakupu” by default:** the section asks `/api/positions/2/10/prices` once without `from`; the shown window starts 14 days before `first_buy`.
  - The header shows the last close in the quote currency and the change „od 1. zakupu”; „1R” asks again and shows „w zakresie”.
  - A click on a marker shows the panel:
    - date and kind;
    - „{qty} szt. po {price} · zapłacone {amount}”;
    - „z przewalutowaniem XTB {price_with_fx}” only when it is not null;
    - „dziś {change %}” against the last close.
  - Without closes, the message „Brak notowań dla tego instrumentu.” is shown.
- [ ] **Step 2: Implement `PriceSection`.**
  - **Data:** one request without `from` (the API thins to ≤ 800, enough for every range). The range only moves the chart window (`windowForRange(dates, rangeFrom(...))`), so switching ranges is instant and the gestures work across the whole history.
  - **Window:** reset the window on a range change and on a double tap.
  - **Average:** `detail.average_price` when the quantity is > 0.
  - **Update** the spec's API note: the client asks once, without `from`. `from` stays in the API for later use.
- [ ] **Step 3:** e2e:
  - in the existing position detail step, expect `img` „Wykres ceny” and at least one button whose name starts with „Zakup”;
  - take the screenshot `wykres-ceny.png`.
- [ ] **Step 4:**
  - Run the full web suite, `tsc` and Playwright.
  - Roadmap: 7e ✅; 7f stays „później”.
  - Commit `feat(web): Wykres ceny in the position details — ranges, markers, average, operation panel`.
