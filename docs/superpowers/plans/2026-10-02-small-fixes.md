# Small fixes batch (after 7b) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the small issues carried in the roadmap's „Carried from …” sections (plans 6a–7b-3) that a person using the app can notice, and drop the dead code. Each one is pinned by a test.

**Architecture:** There is no new feature, only local fixes: in the API's scenario and analytics services and the catalog add, and on the web in the simulator editor and screen, InfoTip, Analiza headings, Pulpit, closed investments, the hero amount, form layout and e2e setup.

**Tech Stack:** FastAPI + pytest (docker), React + Vitest + Playwright.

**Spec:** none (review findings). The authority for each item is the roadmap line it comes from (`docs/superpowers/plans/2026-09-26-00-roadmap.md`), quoted in the task.

## Global Constraints

- The copy is Polish, like the surrounding screens.
- Out of scope, staying in the roadmap: deployment items (real client IP, `Settings` on `app.state`), the iPhone and PWA test, performance at a larger scale (history rebuilt in memory, EDO row caching), replace edge cases with conversions (7b-2 M3, M4), and migrations reading data files. The tooling items stay too: Node engine warnings and the Vite extension warning.
- Commands:
  - API: `docker compose run --rm api pytest -q`
  - web: `cd web && npx vitest run` and `npx tsc --noEmit`
  - e2e: `cd web && npx playwright test`

## Review Focus

1. **Measures over a period:** after the change, „Wpłacono w okresie” and „Zysk” must use the same flows; at „Wszystko” it must equal the lifetime sum. This is pinned in Task 1 `test_invested_follows_the_period`.
2. **The catalog-add race:** it must return the existing instrument without leaving the session broken for the rest of the request. This is pinned in Task 1 `test_add_racing_another_add_returns_the_existing`.
3. **A tooltip tapped inside** must stay open, and a tap outside must still close it. This is pinned in Task 3 `keeps the bubble open when it is tapped`.
4. **320 px phones:** the forms with two fields in a row must not scroll sideways. This is pinned in Task 3's e2e step.

---

### Task 1: API

**Files:** `api/app/scenarios/service.py`, `api/app/scenarios/schemas.py`? (no change), `api/app/analytics/metrics.py`, `api/app/catalog/service.py`, `api/app/transactions/schemas.py`
**Tests:** `api/tests/test_scenario_result_api.py`, `api/tests/test_analytics_metrics.py`, `api/tests/test_catalog_api.py`

Items:
- (7b-2 M1) `MeasuresOut.invested_pln` is the money put in **within the analysed period** (`day >= result.start`), like `profit_pln`.
- (7b-2 M2) The „Dywidendy…” note also fires for instruments whose dividend policy is unknown: `accumulating is None`, not a stock, and not a curated catalog row (curated rows with `None` are gold ETCs). In code: `dividends = category == "stock" or accumulating is False or (accumulating is None and catalog_group in (None, ADDED_GROUP))`.
- (7a) Best and worst day amounts round half up, like every other amount: `quantize(PLACES, rounding=ROUND_HALF_UP)`.
- (7a) A flat series (cash only) gives `max_drawdown` dates on the first day of the period, not on the day before the history.
- (7a, test only) An XIRR flow on the end day is counted. Pin it with a test, and change the code only if it fails.
- (7b-1) Two concurrent adds of one new ticker: the second insert hits the unique `xtb_ticker` and gives 500. Catch `IntegrityError` at the flush, roll back and return the instrument that won, with 200.
- (6b) Remove the unused `MANUAL_TYPES` from `api/app/transactions/schemas.py`, after checking that nothing imports it.

- [ ] **Step 1: Failing tests**

`api/tests/test_scenario_result_api.py`:

```python
def test_invested_follows_the_period(client: TestClient, world: dict) -> None:
    month = preview(client, world["anna"], {"base": "portfolio"}, period="1m").json()
    whole = preview(client, world["anna"], {"base": "portfolio"}).json()

    assert month["portfolio"]["invested_pln"] == "0.00"  # the only deposit was on 2026-03-01
    assert whole["portfolio"]["invested_pln"] == "10000.00"


def test_unknown_dividend_policy_gets_the_note(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.get(Instrument, world["nasdaq"]).accumulating = None
        db.get(Instrument, world["nasdaq"]).catalog_group = "Dodane przez Ciebie"
        db.commit()
    step = {"kind": "replace", "from_instrument_id": world["sxr8"], "to_instrument_id": world["nasdaq"]}

    body = preview(client, world["anna"], {"base": "portfolio", "steps": [step]}).json()

    assert body["notes"] == ["Dywidendy udawanych instrumentów nie są liczone."]
```

`api/tests/test_analytics_metrics.py`. Read the file first for its helpers and imports, then add:

```python
def test_day_amounts_round_half_up() -> None:
    days = [(dt.date(2026, 1, 1), Decimal("1000"), Decimal("1000")), (dt.date(2026, 1, 2), Decimal("1000.005"), ZERO)]
    result = analyze(days, [], "all")
    assert result.best_day.pln == Decimal("0.01")


def test_a_flat_series_has_its_drawdown_inside_the_history() -> None:
    days = [(dt.date(2026, 1, 1), Decimal("100"), Decimal("100")), (dt.date(2026, 1, 2), Decimal("100"), ZERO)]
    fall = analyze(days, [], "all").max_drawdown
    assert (fall.pct, fall.peak_date, fall.trough_date) == (Decimal("0.00"), dt.date(2026, 1, 2), dt.date(2026, 1, 2))


def test_a_flow_on_the_last_day_counts_in_xirr() -> None:
    days = [(dt.date(2025, 1, 1), Decimal("1000"), Decimal("1000")), (dt.date(2026, 1, 1), Decimal("2100"), Decimal("1000"))]
    # 1000 grows to 1100 in a year and 1000 more is paid in on the last day: about +10 % a year
    assert analyze(days, [], "all").xirr_annual_pct == Decimal("10.00")
```

(`ZERO` comes from `app.analytics.metrics`. With `days[0]` as the start and `annualized` from 365 days on, a span of 2025-01-01..2026-01-01 is 366 days. If the expected rounding of XIRR differs, compute it with `pyxirr.xirr` in the test instead of hard-coding it.)

`api/tests/test_catalog_api.py`:

```python
def test_add_racing_another_add_returns_the_existing(client: TestClient, anna: dict, engine: Engine) -> None:
    class Racing(FakePrices):
        def history(self, symbol, since):  # another request saves the same ticker while ours fetches
            with Session(engine) as db:
                db.add(Instrument(xtb_ticker="VWCE.DE", name="Vanguard", currency="EUR", price_symbol="VWCE.DE",
                                  in_catalog=True, catalog_group="Dodane przez Ciebie"))
                db.commit()
            return super().history(symbol, since)
    fake = Racing({"VWCE.DE": VWCE})
    client.app.dependency_overrides[get_market_providers] = lambda: fake_providers(prices=fake)

    response = client.post("/api/catalog", json={"ticker": "VWCE.DE"}, headers=anna)

    assert (response.status_code, response.json()["ticker"]) == (200, "VWCE.DE")
    assert client.get("/api/catalog", headers=anna).status_code == 200
```

(Check `FakePrices.history`'s signature in `tests/market_fakes.py` and match it.)

- [ ] **Step 2: Run them, expect FAIL** (`docker compose run --rm api pytest tests/test_scenario_result_api.py tests/test_analytics_metrics.py tests/test_catalog_api.py -q`). The XIRR test may pass already, which is fine: it is a pin.

- [ ] **Step 3: Implement**
  - `scenarios/service.py` `_measures`: `invested_pln=money(sum((flow for day, _, flow in days if day >= result.start), ZERO))`.
  - In `_instruments`, select `Instrument.catalog_group` too, and use the dividends rule above (import `ADDED_GROUP` from `app.catalog.seed`).
  - `metrics.py` `_extreme`: `frame.at[at, "gain"].quantize(PLACES, rounding=ROUND_HALF_UP)`.
  - In `_drawdown`'s flat branch: `record = (wealth.iloc[1:] if len(wealth) > 1 else wealth).idxmax().date()`.
  - `catalog/service.py`: wrap `db.add(instrument); db.flush()` in `try/except IntegrityError`. On error, `db.rollback()`, re-select by `xtb_ticker` and return `(_item(found, …), False)`. Import from `sqlalchemy.exc`.
  - Delete `MANUAL_TYPES` (run `grep -rn MANUAL_TYPES api` first).

- [ ] **Step 4: Full API suite PASS. Commit** `fix(api): small fixes — period capital, dividend note for unknown ETFs, half-up day amounts, flat drawdown dates, catalog add race`.

---

### Task 2: Simulator screens (7b-3 review)

**Files:** `web/src/screens/simulator/{ScenarioEditor.tsx, TargetSelect.tsx, model.ts, SimulatorScreen.tsx, SimulatorCard.tsx, Measures.tsx}`, `web/src/ui/help.ts`
**Tests:** `web/src/screens/simulator/{editor.test.tsx, simulator.test.tsx, model.test.ts}`

Items and their tests:
1. **A non-integer id** (`/analiza/symulator/abc`) shows „Nie znaleziono scenariusza.” plus a link back, and sends no request.
   - Test `an unknown address shows not found`: render `/analiza/symulator/abc`, expect the text, and expect no fetch path containing `NaN`.
2. **A saved instrument missing from the catalog** shows as „Instrument niedostępny (id N)” in the select, instead of silently showing another option.
   - Test `keeps an instrument that left the catalog visible`: a saved scenario replacing 10 → 99, with 99 not in CATALOG. Expect `getByLabelText("Kupuj")` to have value "99" and the option text „Instrument niedostępny (id 99)”.
   - Implementation: `TargetSelect` adds `<option value={value}>Instrument niedostępny (id {value})</option>` when `value` is neither "", EDO nor in `shown`.
3. **„Na IKE (obligacje bez podatku)”** shows only when the top-up target is EDO.
   - Test `offers IKE only for bonds`: add a top-up block. The checkbox is present for EDO; choose "20" and it is gone.
4. **Amounts above 1 000 000 zł** are refused locally with „Najwyżej 1 000 000 zł miesięcznie.”
   - `model.test.ts`: `toBody` of amount "1 000 000,01" gives the error at `steps.0.amount`.
   - Implementation: `toCents(amount) > 100_000_000n`.
5. **Zapisz is disabled while a delete is pending:** `disabled={save.isPending || remove.isPending}`.
   - Test `blocks saving while deleting`: DELETE answers with a never-resolving promise. After confirming, expect „Zapisz scenariusz” to be disabled.
6. **Legend buttons over the cap** use `aria-disabled="true"`, not `disabled`. They stay focusable and are described by the hint (`id="lines-hint"`, `aria-describedby`). A click does nothing.
   - Update the existing test `lists the scenarios…`: `expect(D).toHaveAttribute("aria-disabled", "true")` and `toHaveAccessibleDescription(/mieszczą się 3 scenariusze/)`.
   - Clicking D keeps it unpressed.
   - CSS: `.legend button[aria-disabled="true"] { opacity: .45; cursor: default; }`.
7. **The Analiza card** says the differences are over the whole history: a dim line „Różnica względem portfela za cały okres.” under the title.
   - Test: extend `shows the three latest scenarios on Analiza` with `getByText("Różnica względem portfela za cały okres.")`.
8. **(Task 1 follow-up)** The measures row „Wpłacono” becomes „Wpłacono w okresie”, with a new HELP entry: what „Ile wpłaciłeś w wybranym okresie (minus wypłaty).”, how „suma wpłat i wypłat od początku okresu do jego końca, w złotych.”
   - Update the test `compares the measures line by line` with `getByText("Wpłacono w okresie")`.

- [ ] Steps: write or adjust the tests, run them (FAIL), implement, then `npx vitest run` and `npx tsc --noEmit` (PASS). Commit `fix(web): simulator small fixes — unknown address, missing instrument, IKE only for bonds, amount cap, legend over the cap`.

---

### Task 3: Other web items

**Files:** `web/src/ui/InfoTip.tsx`, `web/src/screens/analysis/AnalysisScreen.tsx` (+ any other `h2` holding an `InfoTip`; find them with `grep -n "InfoTip" -r web/src/screens` and check whether the tip sits inside the heading), `web/src/ui/ui.module.css`, `web/src/screens/positions/ClosedView.tsx`, `web/src/ui/Amount.tsx`, `web/src/screens/dashboard/DashboardScreen.tsx`, `web/src/ui/forms.module.css`, `web/e2e/global-setup.ts`, `web/e2e/app.spec.ts`
**Tests:** `web/src/ui/InfoTip.test.tsx`, `web/src/screens/analysis/analysis.test.tsx`, `web/src/screens/dashboard/dashboard.test.tsx`, `web/src/ui/ui.test.tsx`, e2e

Items:
1. **(7a) A tap inside the tooltip bubble** keeps it open. In `onDown`, ignore targets inside `bubble.current` too.
   - Test `keeps the bubble open when it is tapped`: click the "?" to pin it, `user.click(screen.getByRole("tooltip"))`, and the tooltip is still there. A click on `document.body` closes it.
2. **(7a) A "?" inside a section heading** no longer joins the heading's name. Render `<div className={ui.titleRow}><h2 …>Title</h2><InfoTip …/></div>` with `.titleRow { display: flex; align-items: center; gap: 4px; }`.
   - Test: `getByRole("heading", { name: "Obsunięcie w czasie" })` matches exactly, and the same for „Zwrot w miesiącach”.
3. **(6c) Closed sale rows** get a stable key, ``key={`${sale.closed_on}-${sale.quantity}-${sale.proceeds_pln}-${i}`}``. React warns on duplicates only, so the test is the absence of a console error. No new test is needed beyond the existing closed tests passing.
4. **(6a) The hero amount** has a real space before „zł” for screen readers and copying: `<span className={styles.currency}>{" "}zł</span>`, with `margin-left` reduced to 2px.
   - Test in `ui.test.tsx`: `HeroAmount` with "1234.50" has `textContent` "1 234,50 zł".
5. **(6a) A selected account without any valuation** shows „Wybrane konta nie mają jeszcze wyceny.” with a link „Pokaż cały portfel”, which clears the selection. The import invitation shows only when the whole portfolio is empty.
   - Test in `dashboard.test.tsx`: the selection is stored for account 2 and the summary has `as_of: null`. Expect the new text and no „Wgraj eksport…”. Read how the existing dashboard tests set the stored selection, which is `localStorage` per user in `accounts/selection.ts`.
6. **(owner 2026-09-30) 320 px phones:** a row of two fields with a date input overflowed by 20 px. Add `min-width: 0` to `.field input, .field select`.
   - e2e: at the end of the savings test, `await page.setViewportSize({ width: 320, height: 700 }); await page.goto("/dodaj/konto-oszczednosciowe");` then `expect(await page.evaluate(() => document.documentElement.scrollWidth)).toBeLessThanOrEqual(320)`. Repeat for `/dodaj/obligacja` and `/dodaj/operacja`.
7. **(6a) e2e setup** removes leftover e2e containers before `up`: `run("docker compose --profile e2e rm -sf db-e2e api-e2e")` first.

- [ ] Steps: tests first (FAIL), implement, `npx vitest run`, `npx tsc --noEmit`, `npx playwright test` (PASS). Commit `fix(web): small fixes — tooltip taps, heading names, hero amount space, empty selected accounts, 320 px forms, e2e cleanup`.

---

### Task 4: Roadmap

- [ ] In `docs/superpowers/plans/2026-09-26-00-roadmap.md`, remove the items fixed here from each „Carried from …” section, plus the ones already done before (refresh-token pruning exists in `auth/maintenance.py`; the foreign `account_id` test on `/api/analytics` exists).
- [ ] Add a short section „Paczka poprawek 2026-10-02 — zrobiona” listing what was fixed. Keep everything else, marked as left for later on purpose (deployment, iPhone, scale, edge cases).
- [ ] Commit `docs(roadmap): small fixes batch done`.
