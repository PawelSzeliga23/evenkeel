# Plan 7b-3 — Simulator screens Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The owner builds, saves and compares "what if" scenarios in the web app: a Symulator section on Analiza, a comparison screen (chart, measures, list), and an editor with a live preview.

**Architecture:** The API from plan 7b-2 (`/api/catalog`, `/api/scenarios…`) gets typed endpoints and query keys. A pure `screens/simulator/model.ts` converts between the editor's draft and the API body, validates locally, picks line colours and writes the difference text. A new `charts/ComparisonChart.tsx` draws several value lines (gaps allowed), the invested capital and a hover or arrow-key readout. There are three screens: `SimulatorCard` (on Analiza), `SimulatorScreen` (`/analiza/symulator`) and `ScenarioEditor` (`/analiza/symulator/nowy`, `/analiza/symulator/:scenarioId`).

**Tech Stack:** React 19, TypeScript, TanStack Query 5, React Router 8, CSS modules, Vitest + Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-01-07b-catalog-and-simulator-design.md` (§5 „Ekrany”; the API is §4, built in plan 7b-2)

## Global Constraints

- The copy is Polish and uses the spec's words:
  - „Symulator”, „Nowy scenariusz”, „Wszystkie scenariusze”;
  - „Mój portfel” / „Moje wpłaty”;
  - „Podmień instrument” / „Dopłacaj co miesiąc”;
  - „Dodaj ticker”.
- Line colours (validated with the dataviz validator on the dark surface `#0E1116`):
  - the portfolio is amber `#F0A43A`, the brand accent, kept even though it sits just above the validator's lightness band;
  - scenario slots are blue `#3987e5`, magenta `#d55181` and violet `#9085e9`. Violet is dashed, because it is close to blue for protan readers.
  - At most **3 scenarios** are on the chart at once. Colour follows the scenario: a slot is kept while it is shown, and a newly shown scenario takes the free slot.
- Difference text, against the real portfolio:
  - `{scenario value − portfolio value, money with sign} · {XIRR difference, 1 place, „pkt”} XIRR`, e.g. „+1 240,00 zł · +3,1 pkt XIRR”;
  - money only when either XIRR is missing, or when one line is annualized and the other is not.
- The account choice is the shared `useAccountSelection`. The period buttons are 7a's `PERIODS`, with the same two-row phone layout.
- Phones get no horizontal scroll. The measures render once in the DOM: a card per line, stacked on a phone and side by side from 900 px.
- The editor validates before sending:
  - name 1–80;
  - `deposits` needs shares > 0 summing to 100;
  - replace only at `portfolio`, `from ≠ to`, each `from` once;
  - amount > 0;
  - day 1–28 (a select);
  - start month ≥ 2016-01, end ≥ start.
  - Errors show after the first save attempt.
- The preview asks `POST /api/scenarios/preview` (period `all`, the chosen accounts) 500 ms after the last change. While the name is empty, the name „Podgląd” is used.
- Commands:
  - web tests: `cd web && npm test -- --run <path>`
  - the whole suite and types: `cd web && npm test` and `cd web && npm run typecheck`
  - e2e: see `web/e2e/global-setup.ts`; run `cd web && npm run e2e`

## Review Focus

1. **A scenario's line starting before the real portfolio's** (top-ups from 2016) must draw the scenario from its own first day and the portfolio only from its own. The two lines must not be shifted against each other. This is pinned in Task 2 `draws a gap where a line has no value` and Task 3 `chartData aligns lines by date`.
2. **Hiding a scenario and showing another** must keep the colours of the ones still shown. This is pinned in Task 1 `toggleShown keeps the slots of the others` and Task 3 `a newly shown scenario takes the freed colour`.
3. **Switching the base to „Moje wpłaty” with a replace block in place** must explain that the block does not apply. It must not send a body the API rejects. This is pinned in Task 1 `toBody refuses a replace block at deposits`.
4. **Saving fails on the server** (unknown instrument, network) must show the message and keep what was typed. This is pinned in Task 4 `shows the API's message when saving fails`.
5. **A hover readout** must not change the page height while moving across the chart (an earlier complaint about the value chart). The readout is a fixed grid of cells; this is pinned in Task 2 `keeps one readout cell per line while moving`.

---

## File Structure

- Modify `web/src/api/types.ts`, `web/src/api/endpoints.ts` and `web/src/api/queryKeys.ts`.
- Create `web/src/screens/simulator/model.ts` and `web/src/screens/simulator/model.test.ts`.
- Create `web/src/charts/ComparisonChart.tsx`, `ComparisonChart.module.css` and `ComparisonChart.test.tsx`.
- Create in `web/src/screens/simulator/`:
  - `Simulator.module.css`, `Measures.tsx`, `SimulatorScreen.tsx`, `SimulatorCard.tsx`, `simulator.test.tsx`;
  - `useDebounced.ts`, `TargetSelect.tsx`, `ScenarioEditor.tsx`, `editor.test.tsx`.
- Modify `web/src/routes.tsx`, `web/src/screens/analysis/AnalysisScreen.tsx`, `web/src/ui/help.ts` and `web/src/test/fixtures.ts`.
- Modify `web/e2e/app.spec.ts` and `docs/superpowers/plans/2026-09-26-00-roadmap.md`.

---

### Task 1: API types, endpoints and the scenario model

**Files:**
- Modify: `web/src/api/types.ts`, `web/src/api/endpoints.ts`, `web/src/api/queryKeys.ts`
- Create: `web/src/screens/simulator/model.ts`
- Test: `web/src/screens/simulator/model.test.ts`

**Interfaces:**
- Produces:
  - types `CatalogItem`, `CatalogGroup`, `ScenarioBase`, `ScenarioTarget`, `ScenarioShare`, `ScenarioStep`, `ScenarioIn`, `Scenario`, `ScenarioPoint`, `ScenarioMeasures`, `ScenarioResult`;
  - `api.catalog`, `api.addTicker`, `api.scenarios`, `api.scenario`, `api.createScenario`, `api.updateScenario`, `api.deleteScenario`, `api.scenarioResult`, `api.previewScenario`;
  - `keys.catalog`, `keys.scenarios`, `keys.scenario(id)`, `keys.scenarioResult(id, ids, period)`, `keys.scenarioResults(id)`, `keys.scenarioPreview(body, ids)`;
  - from the model: `EDO`, `FIRST_MONTH`, `MAX_LINES`, `PORTFOLIO_COLOR`, `SLOTS`, `BASES`, `Draft`, `ShareDraft`, `StepDraft`, `Shown`, `NEW_DRAFT`, `newShare()`, `newReplace()`, `newRecurring(month)`, `draftOf(scenario)`, `toBody(draft)`, `difference(result)`, `defaultShown(ids)`, `toggleShown(shown, id)`.

- [ ] **Step 1: Write the failing tests** — `web/src/screens/simulator/model.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { Scenario } from "../../api/types";
import { scenarioResult } from "../../test/fixtures";
import {
  EDO, NEW_DRAFT, defaultShown, difference, draftOf, newRecurring, newReplace, newShare, toBody, toggleShown,
  type Draft,
} from "./model";

const named = (draft: Partial<Draft>): Draft => ({ ...NEW_DRAFT, name: "Test", ...draft });

describe("toBody", () => {
  it("builds the API body of a deposits scenario", () => {
    const draft = named({ base: "deposits", allocation: [{ target: "20", pct: "60" }, { target: EDO, pct: "40" }] });

    expect(toBody(draft)).toEqual({
      errors: {},
      body: {
        name: "Test", base: "deposits", steps: [],
        allocation: [
          { target: { instrument_id: 20, bond: null }, share_pct: "60" },
          { target: { instrument_id: null, bond: "EDO" }, share_pct: "40" },
        ],
      },
    });
  });

  it("builds replace and top-up blocks", () => {
    const draft = named({ steps: [
      { kind: "replace", from: "10", to: "20" },
      { kind: "recurring", amount: "1 000,50", day: "10", start: "2024-01", end: "", target: EDO, ike: true },
    ] });

    expect(toBody(draft).body?.steps).toEqual([
      { kind: "replace", from_instrument_id: 10, to_instrument_id: 20 },
      { kind: "recurring", amount_pln: "1000.50", day_of_month: 10, start: "2024-01", end: null,
        target: { instrument_id: null, bond: "EDO" }, ike: true },
    ]);
  });

  it("says what is wrong, field by field", () => {
    const draft: Draft = {
      name: "  ", base: "deposits", allocation: [{ target: EDO, pct: "90" }],
      steps: [{ kind: "recurring", amount: "abc", day: "10", start: "2015-12", end: "", target: EDO, ike: false }],
    };

    expect(toBody(draft)).toEqual({
      body: null,
      errors: {
        name: "Podaj nazwę scenariusza.",
        allocation: "Udziały muszą dawać razem 100 %.",
        "steps.0.amount": "Podaj kwotę, np. 1 250,50.",
        "steps.0.start": "Dopłaty mogą zaczynać się najwcześniej w 01.2016.",
      },
    });
  });

  it("refuses a replace block at deposits", () => {
    const draft = named({ base: "deposits", allocation: [newShare()], steps: [{ kind: "replace", from: "10", to: "20" }] });

    expect(toBody(draft).errors).toEqual({ "steps.0.from": "Podmiana działa tylko na punkcie wyjścia „Mój portfel”." });
  });

  it("refuses an unfinished or doubled replace and an end before the start", () => {
    const draft = named({ steps: [
      { kind: "replace", from: "10", to: "" },
      { kind: "replace", from: "10", to: "10" },
      { kind: "recurring", amount: "100", day: "1", start: "2024-05", end: "2024-01", target: EDO, ike: false },
    ] });

    expect(toBody(draft).errors).toEqual({
      "steps.0.to": "Wybierz instrument, który kupujesz w zamian.",
      "steps.1.to": "Wybierz inny instrument niż podmieniany.",
      "steps.2.end": "Koniec nie może być przed początkiem.",
    });
  });

  it("refuses the same instrument replaced twice", () => {
    const draft = named({ steps: [{ kind: "replace", from: "10", to: "20" }, { kind: "replace", from: "10", to: "30" }] });

    expect(toBody(draft).errors).toEqual({ "steps.1.from": "Ten instrument jest już podmieniony." });
  });
});

describe("draftOf", () => {
  it("turns a saved scenario back into the editor's draft", () => {
    const saved: Scenario = {
      id: 5, name: "Mix", base: "deposits", created_at: "", updated_at: "",
      allocation: [{ target: { instrument_id: 20, bond: null }, share_pct: "62.5" }, { target: { instrument_id: null, bond: "EDO" }, share_pct: "37.5" }],
      steps: [{ kind: "recurring", amount_pln: "1000", day_of_month: 3, start: "2024-01", end: null,
                target: { instrument_id: null, bond: "EDO" }, ike: false }],
    };

    expect(draftOf(saved)).toEqual({
      name: "Mix", base: "deposits",
      allocation: [{ target: "20", pct: "62,5" }, { target: EDO, pct: "37,5" }],
      steps: [{ kind: "recurring", amount: "1000", day: "3", start: "2024-01", end: "", target: EDO, ike: false }],
    });
    expect(toBody(draftOf(saved)).body?.allocation[0]?.share_pct).toBe("62.5");
  });

  it("has sensible new blocks", () => {
    expect(newShare()).toEqual({ target: EDO, pct: "100" });
    expect(newReplace()).toEqual({ kind: "replace", from: "", to: "" });
    expect(newRecurring("2025-10")).toEqual(
      { kind: "recurring", amount: "1000", day: "10", start: "2025-10", end: "", target: EDO, ike: false });
  });
});

describe("difference", () => {
  it("is the value and XIRR against the portfolio", () => {
    expect(difference(scenarioResult("12044.20", "9.50"))).toBe("+1 240,00 zł · +3,1 pkt XIRR");
    expect(difference(scenarioResult("9804.20", "5.00"))).toBe("−1 000,00 zł · −1,4 pkt XIRR");
  });

  it("is the value alone when an XIRR is missing or counted over a different span", () => {
    const result = scenarioResult("12044.20", "9.50");
    expect(difference({ ...result, scenario: { ...result.scenario!, xirr: { period_pct: null, annual_pct: null } } }))
      .toBe("+1 240,00 zł");
    const yearly = { ...result.scenario!, period: { ...result.scenario!.period, annualized: true },
      xirr: { period_pct: "20.00", annual_pct: "9.00" } };
    expect(difference({ ...result, scenario: yearly })).toBe("+1 240,00 zł");
    expect(difference({ ...result, scenario: null })).toBeNull();
  });
});

describe("shown scenarios", () => {
  it("shows the first three by default", () => {
    expect(defaultShown([4, 3, 2, 1])).toEqual([{ id: 4, slot: 0 }, { id: 3, slot: 1 }, { id: 2, slot: 2 }]);
  });

  it("toggleShown keeps the slots of the others", () => {
    const shown = defaultShown([4, 3, 2, 1]);
    const hidden = toggleShown(shown, 4);
    expect(hidden).toEqual([{ id: 3, slot: 1 }, { id: 2, slot: 2 }]);
    expect(toggleShown(hidden, 1)).toEqual([{ id: 3, slot: 1 }, { id: 2, slot: 2 }, { id: 1, slot: 0 }]);
    expect(toggleShown(shown, 1)).toBe(shown); // a fourth waits for a free slot
  });
});
```

Also add to `web/src/test/fixtures.ts` (they are used by this test and by Tasks 3–4):

```ts
// at the top: extend the type import with CatalogGroup, Money, Scenario, ScenarioMeasures, ScenarioResult;
// and add: import { fromCents, toCents } from "../format";

export const CATALOG: CatalogGroup[] = [
  { group: "Twój portfel", items: [{ id: 10, ticker: "SXR8.DE", name: "Core S&P 500", currency: "EUR",
    group: "Twój portfel", accumulating: true, prices_from: "2016-01-04" }] },
  { group: "ETF: USA", items: [{ id: 20, ticker: "SXRV.DE", name: "iShares NASDAQ 100", currency: "EUR",
    group: "ETF: USA", accumulating: true, prices_from: "2016-01-04" }] },
];

function measures(value: Money, xirr: Money): ScenarioMeasures {
  return {
    period: { start: "2026-03-01", end: "2026-09-26", days: 210, annualized: false },
    value_pln: value, invested_pln: "10000.00", profit_pln: fromCents(toCents(value) - 1_000_000n),
    twr: { period_pct: "8.04", annual_pct: null }, xirr: { period_pct: xirr, annual_pct: null },
    volatility_pct: "14.80", sharpe: "0.62", short_sample: true,
    max_drawdown: { pct: "-8.20", peak_date: "2026-08-12", trough_date: "2026-08-22", recovered_on: null },
    current_drawdown_pct: "-1.30", best_day: null, worst_day: null,
  };
}

/** The real portfolio ends at 10 804,20 zł with XIRR 6,40 %; the scenario at `value` with `xirr`. */
export function scenarioResult(value: Money, xirr: Money, notes: string[] = []): ScenarioResult {
  return {
    points: [
      { date: "2026-09-24", portfolio_pln: "10700.00", scenario_pln: "10900.00", invested_pln: "10000.00",
        scenario_invested_pln: "10000.00" },
      { date: "2026-09-25", portfolio_pln: "10750.00", scenario_pln: "11000.00", invested_pln: "10000.00",
        scenario_invested_pln: "10000.00" },
      { date: "2026-09-26", portfolio_pln: "10804.20", scenario_pln: value, invested_pln: "10000.00",
        scenario_invested_pln: "10000.00" },
    ],
    portfolio: measures("10804.20", "6.40"), scenario: measures(value, xirr), notes, recalculating: false,
  };
}

export function scenario(id: number, name: string, overrides: Partial<Scenario> = {}): Scenario {
  return {
    id, name, base: "portfolio", allocation: [],
    steps: [{ kind: "replace", from_instrument_id: 10, to_instrument_id: 20 }],
    created_at: "2026-10-01T10:00:00Z", updated_at: "2026-10-01T10:00:00Z", ...overrides,
  };
}
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd web && npm test -- --run src/screens/simulator/model.test.ts`
Expected: FAIL (the module `./model` is missing, and the fixtures' types are missing).

- [ ] **Step 3: Types, endpoints and keys**

Append to `web/src/api/types.ts`:

```ts
export interface CatalogItem {
  id: number; ticker: string; name: string; currency: string | null; group: string; accumulating: boolean | null;
  prices_from: IsoDate | null;
}
export interface CatalogGroup { group: string; items: CatalogItem[] }

export type ScenarioBase = "portfolio" | "deposits";
export interface ScenarioTarget { instrument_id: number | null; bond: "EDO" | null }
export interface ScenarioShare { target: ScenarioTarget; share_pct: Money }
export interface ReplaceStep { kind: "replace"; from_instrument_id: number; to_instrument_id: number }
export interface RecurringStep {
  kind: "recurring"; amount_pln: Money; day_of_month: number; start: string; end: string | null; target: ScenarioTarget;
  ike: boolean;
}
export type ScenarioStep = ReplaceStep | RecurringStep;
export interface ScenarioIn { name: string; base: ScenarioBase; allocation: ScenarioShare[]; steps: ScenarioStep[] }
export interface Scenario extends ScenarioIn { id: number; created_at: IsoDateTime; updated_at: IsoDateTime }
export interface ScenarioPoint {
  date: IsoDate; portfolio_pln: Money | null; scenario_pln: Money | null; invested_pln: Money | null;
  scenario_invested_pln: Money | null;
}
export interface ScenarioMeasures {
  period: { start: IsoDate; end: IsoDate; days: number; annualized: boolean };
  value_pln: Money;
  invested_pln: Money;
  profit_pln: Money;
  twr: PeriodReturn;
  xirr: PeriodReturn;
  volatility_pct: Money | null;
  sharpe: Money | null;
  short_sample: boolean;
  max_drawdown: Analytics["max_drawdown"];
  current_drawdown_pct: Money | null;
  best_day: DayExtreme | null;
  worst_day: DayExtreme | null;
}
export interface ScenarioResult {
  points: ScenarioPoint[]; portfolio: ScenarioMeasures | null; scenario: ScenarioMeasures | null; notes: string[];
  recalculating: boolean;
}
```

In `web/src/api/endpoints.ts` extend the type import with `CatalogGroup, CatalogItem, Scenario, ScenarioIn, ScenarioResult` and add to `api`:

```ts
  catalog: () => request<CatalogGroup[]>("/api/catalog"),
  addTicker: (ticker: string) => request<CatalogItem>("/api/catalog", { method: "POST", json: { ticker } }),
  scenarios: () => request<Scenario[]>("/api/scenarios"),
  scenario: (id: number) => request<Scenario>(`/api/scenarios/${id}`),
  createScenario: (body: ScenarioIn) => request<Scenario>("/api/scenarios", { method: "POST", json: body }),
  updateScenario: (id: number, body: ScenarioIn) =>
    request<Scenario>(`/api/scenarios/${id}`, { method: "PATCH", json: body }),
  deleteScenario: (id: number) => request<void>(`/api/scenarios/${id}`, { method: "DELETE" }),
  scenarioResult: (id: number, ids: readonly number[], period: AnalyticsPeriod) =>
    request<ScenarioResult>(`/api/scenarios/${id}/result`, { query: { account_id: ids, period } }),
  previewScenario: (body: ScenarioIn, ids: readonly number[]) =>
    request<ScenarioResult>("/api/scenarios/preview", { method: "POST", json: body, query: { account_id: ids, period: "all" } }),
```

In `web/src/api/queryKeys.ts` add:

```ts
  catalog: ["catalog"] as const,
  scenarios: ["scenarios"] as const,
  scenario: (id: number) => ["scenarios", id] as const,
  scenarioResults: (id: number) => ["portfolio", "scenario-result", id] as const,
  scenarioResult: (id: number, ids: readonly number[], period: string) =>
    ["portfolio", "scenario-result", id, ids, period] as const,
  scenarioPreview: (body: object, ids: readonly number[]) => ["portfolio", "scenario-preview", body, ids] as const,
```

(The results start with "portfolio", so an import or a new bond refreshes them too.)

- [ ] **Step 4: The model** — `web/src/screens/simulator/model.ts`:

```ts
/** The simulator's pure pieces: the editor's draft and the API body, line colours, and the difference text. */
import type { Money, Scenario, ScenarioBase, ScenarioIn, ScenarioResult, ScenarioShare, ScenarioStep, ScenarioTarget } from "../../api/types";
import { formatMoney, formatPercent, fromCents, isPositive, parseAmount, toCents } from "../../format";
import { AMOUNT_HINT } from "../../ui/forms";
import { shownReturn } from "../analysis/model";

export const EDO = "edo";
export const FIRST_MONTH = "2016-01"; // the catalog's prices, NBP rates and EDO issues start here (plan 7b-1)
export const MAX_LINES = 3;
export const PORTFOLIO_COLOR = "#F0A43A";
/** Validated on the dark surface: blue, magenta, violet; violet is dashed (close to blue for protan readers). */
export const SLOTS: { color: string; dashed: boolean }[] = [
  { color: "#3987e5", dashed: false }, { color: "#d55181", dashed: false }, { color: "#9085e9", dashed: true },
];
export const BASES: { value: ScenarioBase; label: string }[] = [
  { value: "portfolio", label: "Mój portfel" }, { value: "deposits", label: "Moje wpłaty" },
];

export interface ShareDraft { target: string; pct: string }
export type StepDraft =
  | { kind: "replace"; from: string; to: string }
  | { kind: "recurring"; amount: string; day: string; start: string; end: string; target: string; ike: boolean };
export interface Draft { name: string; base: ScenarioBase; allocation: ShareDraft[]; steps: StepDraft[] }

export const NEW_DRAFT: Draft = { name: "", base: "portfolio", allocation: [], steps: [] };
export const newShare = (): ShareDraft => ({ target: EDO, pct: "100" });
export const newReplace = (): StepDraft => ({ kind: "replace", from: "", to: "" });
export const newRecurring = (month: string): StepDraft =>
  ({ kind: "recurring", amount: "1000", day: "10", start: month, end: "", target: EDO, ike: false });

const targetOf = (value: string): ScenarioTarget =>
  value === EDO ? { instrument_id: null, bond: "EDO" } : { instrument_id: Number(value), bond: null };
const valueOf = (target: ScenarioTarget): string => (target.bond ? EDO : String(target.instrument_id));
const typed = (decimal: string) => decimal.replace(".", ",");

export function draftOf(scenario: Scenario): Draft {
  return {
    name: scenario.name, base: scenario.base,
    allocation: scenario.allocation.map((share) => ({ target: valueOf(share.target), pct: typed(share.share_pct) })),
    steps: scenario.steps.map((step): StepDraft => step.kind === "replace"
      ? { kind: "replace", from: String(step.from_instrument_id), to: String(step.to_instrument_id) }
      : { kind: "recurring", amount: typed(step.amount_pln), day: String(step.day_of_month), start: step.start,
          end: step.end ?? "", target: valueOf(step.target), ike: step.ike }),
  };
}

/** The API body, or the messages per field (`name`, `allocation`, `allocation.0.pct`, `steps.1.amount` …). */
export function toBody(draft: Draft): { body: ScenarioIn | null; errors: Record<string, string> } {
  const errors: Record<string, string> = {};
  const name = draft.name.trim();
  if (!name) errors.name = "Podaj nazwę scenariusza.";
  else if (name.length > 80) errors.name = "Nazwa może mieć najwyżej 80 znaków.";

  const allocation: ScenarioShare[] = [];
  if (draft.base === "deposits") {
    let cents = 0n;
    draft.allocation.forEach((share, i) => {
      const pct = parseAmount(share.pct);
      if (pct === null || !isPositive(pct)) errors[`allocation.${i}.pct`] = "Podaj udział, np. 60.";
      else {
        cents += toCents(pct);
        allocation.push({ target: targetOf(share.target), share_pct: pct });
      }
    });
    if (draft.allocation.length === 0) errors.allocation = "Dodaj co najmniej jeden cel wpłat.";
    else if (allocation.length === draft.allocation.length && cents !== 10_000n) {
      errors.allocation = "Udziały muszą dawać razem 100 %.";
    }
  }

  const steps: ScenarioStep[] = [];
  const replaced = new Set<string>();
  draft.steps.forEach((step, i) => {
    const fail = (field: string, message: string) => { errors[`steps.${i}.${field}`] = message; };
    if (step.kind === "replace") {
      if (draft.base === "deposits") fail("from", "Podmiana działa tylko na punkcie wyjścia „Mój portfel”.");
      else if (!step.from) fail("from", "Wybierz instrument z portfela.");
      else if (replaced.has(step.from)) fail("from", "Ten instrument jest już podmieniony.");
      else if (!step.to) fail("to", "Wybierz instrument, który kupujesz w zamian.");
      else if (step.to === step.from) fail("to", "Wybierz inny instrument niż podmieniany.");
      else steps.push({ kind: "replace", from_instrument_id: Number(step.from), to_instrument_id: Number(step.to) });
      if (step.from) replaced.add(step.from);
      return;
    }
    const amount = parseAmount(step.amount);
    let ok = true;
    if (amount === null || !isPositive(amount)) { fail("amount", AMOUNT_HINT); ok = false; }
    if (!/^\d{4}-\d{2}$/.test(step.start) || step.start < FIRST_MONTH) {
      fail("start", "Dopłaty mogą zaczynać się najwcześniej w 01.2016."); ok = false;
    } else if (step.end && step.end < step.start) { fail("end", "Koniec nie może być przed początkiem."); ok = false; }
    if (ok && amount !== null) {
      steps.push({ kind: "recurring", amount_pln: amount, day_of_month: Number(step.day), start: step.start,
                   end: step.end || null, target: targetOf(step.target), ike: step.ike });
    }
  });
  if (Object.keys(errors).length > 0) return { body: null, errors };
  return { body: { name, base: draft.base, allocation, steps }, errors };
}

const minus = (a: Money, b: Money) => fromCents(toCents(a) - toCents(b));

/** „+1 240,00 zł · +3,1 pkt XIRR” against the real portfolio; null without both lines. */
export function difference(result: ScenarioResult): string | null {
  const { portfolio, scenario } = result;
  if (!portfolio || !scenario) return null;
  const money = formatMoney(minus(scenario.value_pln, portfolio.value_pln), { sign: true });
  if (portfolio.period.annualized !== scenario.period.annualized) return money;
  const ours = shownReturn(portfolio.xirr, portfolio.period.annualized).value;
  const theirs = shownReturn(scenario.xirr, scenario.period.annualized).value;
  if (ours === null || theirs === null) return money;
  return `${money} · ${formatPercent(minus(theirs, ours), { places: 1 }).replace("%", "pkt")} XIRR`;
}

/** A scenario on the chart and its colour slot (kept while it stays shown). */
export interface Shown { id: number; slot: number }

export function defaultShown(ids: number[]): Shown[] {
  return ids.slice(0, MAX_LINES).map((id, slot) => ({ id, slot }));
}

export function toggleShown(shown: Shown[], id: number): Shown[] {
  if (shown.some((item) => item.id === id)) return shown.filter((item) => item.id !== id);
  if (shown.length >= MAX_LINES) return shown;
  const used = new Set(shown.map((item) => item.slot));
  const slot = SLOTS.findIndex((_, index) => !used.has(index));
  return [...shown, { id, slot }];
}
```

- [ ] **Step 5: Run the tests and the type check**

Run: `cd web && npm test -- --run src/screens/simulator/model.test.ts && npm run typecheck`
Expected: PASS

- [ ] **Step 6: Commit**

```bash
git add web/src/api web/src/screens/simulator/model.ts web/src/screens/simulator/model.test.ts web/src/test/fixtures.ts
git commit -m "feat(web): scenario API, editor draft model, line colours and the difference text"
```

---

### Task 2: ComparisonChart

**Files:**
- Create: `web/src/charts/ComparisonChart.tsx`, `web/src/charts/ComparisonChart.module.css`
- Test: `web/src/charts/ComparisonChart.test.tsx`

**Interfaces:**
- Consumes: `yDomain`, `niceStep`, `axisLabel` (`./geometry`), `timeTicks`, `useWidth`, `fullWindow`.
- Produces: `ComparisonChart({ dates, lines, invested })`, `ComparisonLine { key, label, color, dashed?, values: (Money | null)[] }`, `swatchStyle(color, dashed?)`.

- [ ] **Step 1: Write the failing tests** — `web/src/charts/ComparisonChart.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ComparisonChart, type ComparisonLine } from "./ComparisonChart";

const DATES = ["2026-01-01", "2026-01-02", "2026-01-03"];
const LINES: ComparisonLine[] = [
  { key: "portfolio", label: "Mój portfel", color: "#F0A43A", values: ["100.00", "110.00", "120.00"] },
  { key: "7", label: "NASDAQ", color: "#9085e9", dashed: true, values: [null, "105.00", "130.00"] },
];
const INVESTED = ["100.00", "100.00", "100.00"];

const path = (key: string) => document.querySelector(`path[data-line="${key}"]`)!;

describe("ComparisonChart", () => {
  it("draws a line per series in its colour, the invested capital thin", () => {
    render(<ComparisonChart dates={DATES} lines={LINES} invested={INVESTED} />);

    expect(screen.getByRole("img", { name: "Porównanie wartości: Mój portfel, NASDAQ" })).toBeInTheDocument();
    expect(path("portfolio")).toHaveAttribute("stroke", "#F0A43A");
    expect(path("7")).toHaveAttribute("stroke-dasharray", "6 4");
    expect(path("invested").getAttribute("d")).toMatch(/^M/);
  });

  it("draws a gap where a line has no value", () => {
    render(<ComparisonChart dates={[...DATES, "2026-01-04"]} invested={[...INVESTED, "100.00"]}
      lines={[{ key: "a", label: "A", color: "#3987e5", values: ["1.00", "2.00", null, "4.00"] }]} />);

    expect(path("a").getAttribute("d")!.match(/M/g)).toHaveLength(2);
  });

  it("reads out the last day and follows the arrow keys", async () => {
    const user = userEvent.setup();
    render(<ComparisonChart dates={DATES} lines={LINES} invested={INVESTED} />);

    expect(screen.getByText("03.01.2026")).toBeInTheDocument();
    expect(screen.getByText("130,00 zł")).toBeInTheDocument();
    screen.getByRole("img").focus();
    await user.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(screen.getByText("01.01.2026")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument(); // NASDAQ has no value on the first day
  });

  it("keeps one readout cell per line while moving", async () => {
    const user = userEvent.setup();
    render(<ComparisonChart dates={DATES} lines={LINES} invested={INVESTED} />);
    const cells = () => document.querySelectorAll("[data-readout-cell]").length;

    const before = cells();
    screen.getByRole("img").focus();
    await user.keyboard("{ArrowLeft}");
    expect(cells()).toBe(before);
    expect(before).toBe(4); // the day, two lines, the capital
  });

  it("asks for at least two days", () => {
    render(<ComparisonChart dates={["2026-01-01"]} lines={[LINES[0]!]} invested={["100.00"]} />);
    expect(screen.getByText("Wykres pojawi się, gdy okres obejmie co najmniej dwa dni.")).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Run to verify it fails**

Run: `cd web && npm test -- --run src/charts/ComparisonChart.test.tsx`
Expected: FAIL (module missing).

- [ ] **Step 3: Implement** — `web/src/charts/ComparisonChart.module.css`:

```css
.chart { margin: 0; display: grid; gap: 8px; }
.svg { width: 100%; height: auto; display: block; overflow: visible; touch-action: pan-y; user-select: none; -webkit-user-select: none; }
.svg:focus-visible { outline: 2px solid var(--amber); outline-offset: 4px; border-radius: 4px; }
/* Fixed cells: moving across the chart never reflows the readout or shifts the page. */
.readout { display: grid; grid-template-columns: repeat(auto-fill, minmax(150px, 1fr)); gap: 2px 16px; font-size: 12.5px; color: var(--dim); }
.cell { display: inline-flex; align-items: center; gap: 6px; min-width: 0; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.cell b { color: var(--ink); font-weight: 500; font-variant-numeric: tabular-nums; }
.day { color: var(--ink); }
.swatch { width: 14px; height: 3px; border-radius: 2px; flex: none; }
.grid { stroke: var(--rule); stroke-width: 1; }
.axis { fill: var(--dim); font-size: 11px; font-variant-numeric: tabular-nums; }
.line { fill: none; stroke-width: 2; stroke-linejoin: round; stroke-linecap: round; }
.capital { fill: none; stroke: var(--dim); stroke-width: 1.2; stroke-opacity: .7; }
.cursor { stroke: var(--ink); stroke-opacity: .35; stroke-width: 1; }
.note { color: var(--dim); font-size: 14px; padding: 24px 0; }
```

`web/src/charts/ComparisonChart.tsx`:

```tsx
import { useState, type CSSProperties, type KeyboardEvent, type PointerEvent } from "react";
import type { IsoDate, Money } from "../api/types";
import { formatDate, formatMoney } from "../format";
import styles from "./ComparisonChart.module.css";
import { axisLabel, niceStep, yDomain } from "./geometry";
import { timeTicks } from "./timeTicks";
import { useWidth } from "./useWidth";
import { fullWindow } from "./viewport";

/** One line: a value per date of the chart (null where it has none, e.g. before its first day). */
export interface ComparisonLine { key: string; label: string; color: string; dashed?: boolean; values: (Money | null)[] }

const DEFAULT_W = 350;
const H = 220;
const RIGHT = 48;
const TOP = 8;
const BOTTOM = 22;
const DASH = "6 4";

export function swatchStyle(color: string, dashed = false): CSSProperties {
  return { background: dashed ? `repeating-linear-gradient(90deg, ${color} 0 5px, transparent 5px 8px)` : color };
}

const toNumber = (value: Money | null) => (value === null ? null : Number(value));

function linePath(values: (number | null)[], x: (i: number) => number, y: (v: number) => number): string {
  let d = "";
  let pen = false;
  values.forEach((value, i) => {
    if (value === null) { pen = false; return; }
    d += `${pen ? "L" : "M"}${x(i).toFixed(1)} ${y(value).toFixed(1)}`;
    pen = true;
  });
  return d;
}

/** Several value lines over the same days, without zoom (spec 7b §5); hover or ←/→ reads one day out. */
export function ComparisonChart({ dates, lines, invested }: {
  dates: IsoDate[]; lines: ComparisonLine[]; invested: (Money | null)[];
}) {
  const [figure, setFigure] = useState<HTMLElement | null>(null);
  const width = useWidth(figure, DEFAULT_W);
  const [hover, setHover] = useState<number | null>(null);
  const numbers = [...lines.flatMap((line) => line.values), ...invested]
    .filter((value): value is Money => value !== null).map(Number);
  if (dates.length < 2 || numbers.length === 0) {
    return <p className={styles.note}>Wykres pojawi się, gdy okres obejmie co najmniej dwa dni.</p>;
  }

  const last = dates.length - 1;
  const plotW = width - RIGHT;
  const plotH = H - TOP - BOTTOM;
  const domain = yDomain(numbers.map((value) => ({ date: "", value, invested: value, flow: 0 })));
  const step = domain.ticks.length > 1 ? domain.ticks[1]! - domain.ticks[0]! : niceStep(domain.max - domain.min, 3);
  const x = (i: number) => (i / last) * plotW;
  const y = (v: number) => TOP + (1 - (v - domain.min) / (domain.max - domain.min)) * plotH;
  const ticks = timeTicks(dates.map((date) => ({ date, value: 0, invested: 0, flow: 0 })), fullWindow(dates.length), plotW);
  const at = Math.min(hover ?? last, last);

  const move = (event: PointerEvent<SVGSVGElement>) => {
    const box = event.currentTarget.getBoundingClientRect();
    if (box.width <= 0) return;
    const px = ((event.clientX - box.left) / box.width) * width;
    setHover(Math.min(Math.max(Math.round((px / plotW) * last), 0), last));
  };
  const key = (event: KeyboardEvent<SVGSVGElement>) => {
    if (event.key !== "ArrowLeft" && event.key !== "ArrowRight") return;
    event.preventDefault();
    setHover(Math.min(Math.max(at + (event.key === "ArrowLeft" ? -1 : 1), 0), last));
  };
  const money = (value: Money | null | undefined) => (value == null ? "—" : formatMoney(value));

  return (
    <figure ref={setFigure} className={styles.chart}>
      <div className={styles.readout}>
        <span className={`${styles.cell} ${styles.day}`} data-readout-cell>{formatDate(dates[at]!)}</span>
        {lines.map((line) => (
          <span key={line.key} className={styles.cell} data-readout-cell>
            <i className={styles.swatch} style={swatchStyle(line.color, line.dashed)} />
            {line.label} <b>{money(line.values[at])}</b>
          </span>
        ))}
        <span className={styles.cell} data-readout-cell>
          <i className={styles.swatch} style={swatchStyle("var(--dim)")} />Wpłacono <b>{money(invested[at])}</b>
        </span>
      </div>
      <svg className={styles.svg} viewBox={`0 0 ${width} ${H}`} role="img" tabIndex={0}
        aria-label={`Porównanie wartości: ${lines.map((line) => line.label).join(", ")}`}
        onPointerMove={move} onPointerLeave={() => setHover(null)} onKeyDown={key} onBlur={() => setHover(null)}>
        {domain.ticks.map((tick) => (
          <g key={tick}>
            <line className={styles.grid} x1={0} x2={plotW} y1={y(tick)} y2={y(tick)} />
            <text className={styles.axis} x={plotW + 6} y={y(tick) + 4}>{axisLabel(tick, step)}</text>
          </g>
        ))}
        <path className={styles.capital} d={linePath(invested.map(toNumber), x, y)} data-line="invested" />
        {lines.map((line) => (
          <path key={line.key} className={styles.line} d={linePath(line.values.map(toNumber), x, y)} stroke={line.color}
            strokeDasharray={line.dashed ? DASH : undefined} data-line={line.key} />
        ))}
        {hover !== null && <line className={styles.cursor} x1={x(at)} x2={x(at)} y1={TOP} y2={TOP + plotH} />}
        {ticks.map((tick) => (
          <text key={tick.index} className={styles.axis} x={x(tick.index)} y={H - 4} textAnchor="middle">{tick.label}</text>
        ))}
      </svg>
    </figure>
  );
}
```

- [ ] **Step 4: Run the tests**

Run: `cd web && npm test -- --run src/charts/ComparisonChart.test.tsx`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add web/src/charts/ComparisonChart.tsx web/src/charts/ComparisonChart.module.css web/src/charts/ComparisonChart.test.tsx
git commit -m "feat(web): comparison chart of several value lines with a fixed readout"
```

---

### Task 3: The Symulator screen and the card on Analiza

**Files:**
- Create: `web/src/screens/simulator/Simulator.module.css`, `Measures.tsx`, `SimulatorScreen.tsx`, `SimulatorCard.tsx`, `chart.ts`
- Modify: `web/src/routes.tsx`, `web/src/screens/analysis/AnalysisScreen.tsx`, `web/src/ui/help.ts`
- Test: `web/src/screens/simulator/simulator.test.tsx`, `web/src/screens/simulator/chart.test.ts`

**Interfaces:**
- Consumes: Task 1's API and model, and Task 2's chart.
- Produces:
  - routes `/analiza/symulator`;
  - `chartData(base, scenarios, showPortfolio)`;
  - `Measures({ columns })`;
  - `SimulatorCard()`.

- [ ] **Step 1: Write the failing tests**

`web/src/screens/simulator/chart.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import type { ScenarioResult } from "../../api/types";
import { scenarioResult } from "../../test/fixtures";
import { chartData } from "./chart";

describe("chartData", () => {
  it("chartData aligns lines by date", () => {
    const early: ScenarioResult = {
      ...scenarioResult("12044.20", "9.50"),
      points: [
        { date: "2026-09-23", portfolio_pln: null, scenario_pln: "500.00", invested_pln: null, scenario_invested_pln: "500.00" },
        ...scenarioResult("12044.20", "9.50").points,
      ],
    };
    const late = scenarioResult("9000.00", "1.00");

    const data = chartData([{ key: "1", label: "A", slot: 0, result: early }, { key: "2", label: "B", slot: 2, result: late }], true);

    expect(data.dates).toEqual(["2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26"]);
    expect(data.lines.map((line) => [line.key, line.values])).toEqual([
      ["portfolio", [null, "10700.00", "10750.00", "10804.20"]],
      ["1", ["500.00", "10900.00", "11000.00", "12044.20"]],
      ["2", [null, "10900.00", "11000.00", "9000.00"]],
    ]);
    expect(data.lines[2]).toMatchObject({ color: "#9085e9", dashed: true });
    expect(data.invested).toEqual([null, "10000.00", "10000.00", "10000.00"]);
  });

  it("leaves the portfolio out when it is hidden", () => {
    const data = chartData([{ key: "1", label: "A", slot: 1, result: scenarioResult("1.00", "1.00") }], false);
    expect(data.lines.map((line) => line.key)).toEqual(["1"]);
  });
});
```

`web/src/screens/simulator/simulator.test.tsx`:

```tsx
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, ANALYTICS, scenario, scenarioResult } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";

const FOUR = [scenario(1, "A"), scenario(2, "B"), scenario(3, "C"), scenario(4, "D")];
const VALUES: Record<string, string> = { 1: "12044.20", 2: "11000.00", 3: "10000.00", 4: "9000.00" };

function routes(scenarios = FOUR) {
  return mockFetch([
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/analytics", respond: () => ANALYTICS },
    { path: "/api/scenarios", respond: () => scenarios },
    { path: /^\/api\/scenarios\/\d+\/result$/, respond: (url) => scenarioResult(VALUES[url.pathname.split("/")[3]!]!, "9.50") },
  ]);
}

const legend = () => screen.getByRole("group", { name: "Linie na wykresie" });
const stroke = (key: string) => document.querySelector(`path[data-line="${key}"]`)?.getAttribute("stroke");

describe("Symulator", () => {
  it("lists the scenarios with their difference and draws the first three", async () => {
    routes();
    renderApp("/analiza/symulator");

    expect(await screen.findByRole("heading", { name: "Symulator" })).toBeInTheDocument();
    expect(await screen.findByRole("link", { name: /^A .*\+1 240,00 zł · \+3,1 pkt XIRR/ })).toHaveAttribute(
      "href", "/analiza/symulator/1");
    for (const name of ["Mój portfel", "A", "B", "C"]) {
      expect(within(legend()).getByRole("button", { name })).toHaveAttribute("aria-pressed", "true");
    }
    expect(within(legend()).getByRole("button", { name: "D" })).toBeDisabled();
    expect(await screen.findByRole("img", { name: "Porównanie wartości: Mój portfel, A, B, C" })).toBeInTheDocument();
  });

  it("a newly shown scenario takes the freed colour", async () => {
    routes();
    const { user } = renderApp("/analiza/symulator");
    await screen.findByRole("img", { name: /Porównanie wartości/ });

    expect(stroke("1")).toBe("#3987e5");
    await user.click(within(legend()).getByRole("button", { name: "A" }));
    await user.click(within(legend()).getByRole("button", { name: "D" }));

    expect(stroke("4")).toBe("#3987e5");
    expect(stroke("2")).toBe("#d55181");
    expect(stroke("1")).toBeUndefined();
  });

  it("compares the measures line by line", async () => {
    routes();
    renderApp("/analiza/symulator");

    const ours = await screen.findByRole("group", { name: "Mój portfel" });
    expect(within(ours).getByText("10 804,20 zł")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "A" })).getByText("12 044,20 zł")).toBeInTheDocument();
    expect(within(screen.getByRole("group", { name: "A" })).getByText("+9,5 %")).toBeInTheDocument();
    expect(within(ours).getByRole("button", { name: "Co to jest: XIRR" })).toBeInTheDocument();
  });

  it("asks for the chosen period", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator");
    await screen.findByRole("img", { name: /Porównanie wartości/ });

    await user.click(screen.getByRole("button", { name: "1R" }));
    expect(fetchMock.mock.calls.map(([url]) => String(url)).some((u) => u.includes("/result") && u.includes("period=1y")))
      .toBe(true);
  });

  it("invites to the first scenario", async () => {
    routes([]);
    renderApp("/analiza/symulator");

    expect(await screen.findByText("Nie masz jeszcze scenariuszy.")).toBeInTheDocument();
    expect(screen.getAllByRole("link", { name: "Nowy scenariusz" })[0]).toHaveAttribute("href", "/analiza/symulator/nowy");
  });

  it("shows the three latest scenarios on Analiza", async () => {
    routes();
    renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Symulator" });
    expect(await within(card).findByRole("link", { name: /^A / })).toBeInTheDocument();
    expect(within(card).queryByRole("link", { name: /^D / })).not.toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Wszystkie scenariusze" })).toHaveAttribute("href", "/analiza/symulator");
    expect(within(card).getByRole("link", { name: "Nowy scenariusz" })).toHaveAttribute("href", "/analiza/symulator/nowy");
  });
});
```

- [ ] **Step 2: Run to verify they fail**

Run: `cd web && npm test -- --run src/screens/simulator`
Expected: the new tests FAIL (modules and routes missing). The model tests still pass.

- [ ] **Step 3: Chart data** — `web/src/screens/simulator/chart.ts`:

```ts
import type { IsoDate, Money, ScenarioResult } from "../../api/types";
import type { ComparisonLine } from "../../charts/ComparisonChart";
import { PORTFOLIO_COLOR, SLOTS } from "./model";

export interface ShownResult { key: string; label: string; slot: number; result: ScenarioResult }

/** The lines on one date axis (the union of every result's days); the real portfolio and its capital come from the
 * results too: every result carries the same real line. */
export function chartData(shown: ShownResult[], showPortfolio: boolean): {
  dates: IsoDate[]; lines: ComparisonLine[]; invested: (Money | null)[];
} {
  const dates = [...new Set(shown.flatMap(({ result }) => result.points.map((point) => point.date)))].sort();
  const real = new Map<IsoDate, { value: Money | null; invested: Money | null }>();
  for (const { result } of shown) {
    for (const point of result.points) {
      if (point.portfolio_pln !== null) real.set(point.date, { value: point.portfolio_pln, invested: point.invested_pln });
    }
  }
  const lines: ComparisonLine[] = [];
  if (showPortfolio) {
    lines.push({ key: "portfolio", label: "Mój portfel", color: PORTFOLIO_COLOR,
                 values: dates.map((date) => real.get(date)?.value ?? null) });
  }
  for (const { key, label, slot, result } of shown) {
    const byDate = new Map(result.points.map((point) => [point.date, point.scenario_pln]));
    lines.push({ key, label, ...SLOTS[slot]!, values: dates.map((date) => byDate.get(date) ?? null) });
  }
  return { dates, lines, invested: dates.map((date) => real.get(date)?.invested ?? null) };
}
```

- [ ] **Step 4: Styles, measures, help**

`web/src/screens/simulator/Simulator.module.css`:

```css
.head { display: flex; flex-wrap: wrap; justify-content: space-between; align-items: center; gap: 12px; }
.legend { display: flex; flex-wrap: wrap; gap: 8px; }
.legend button {
  display: inline-flex; align-items: center; gap: 8px; min-height: 44px; max-width: 100%; padding: 0 12px;
  background: var(--slab); border: 1px solid var(--rule); border-radius: 999px; color: var(--dim);
  font: inherit; font-size: 13.5px; cursor: pointer;
}
.legend button span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.legend button[aria-pressed="true"] { color: var(--ink); border-color: var(--dim); }
.legend button:disabled { opacity: .45; cursor: default; }
.swatch { width: 14px; height: 3px; border-radius: 2px; flex: none; }
.hint { color: var(--dim); font-size: 12.5px; }
/* One DOM: a card per line, stacked on a phone, side by side from 900 px (reads as a table of measures × lines). */
.columns { display: grid; gap: 8px; }
@media (min-width: 900px) { .columns { grid-auto-flow: column; grid-auto-columns: minmax(0, 1fr); } }
.column { background: var(--slab); border: 1px solid var(--rule); border-radius: var(--r-sheet); padding: 12px; display: grid; gap: 10px; align-content: start; min-width: 0; }
.columnHead { display: flex; align-items: center; gap: 8px; font-weight: 600; min-width: 0; }
.columnHead span { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.label { display: inline-flex; align-items: center; gap: 2px; }
.diff { color: var(--dim); font-size: 12.5px; }
.notes { margin: 0; padding-left: 18px; color: var(--dim); font-size: 13px; display: grid; gap: 4px; }
.block { border: 1px solid var(--rule); border-radius: var(--r-sheet); padding: 12px 14px; display: grid; gap: 14px; margin: 0; min-width: 0; }
.block legend { padding: 0 6px; font-weight: 600; color: var(--ink); }
.shareRow { display: grid; grid-template-columns: minmax(0, 1fr) 96px; gap: 10px; align-items: start; }
.check { display: flex; align-items: center; gap: 10px; min-height: 44px; color: var(--ink); font-size: 14px; }
.check input { width: 18px; height: 18px; accent-color: var(--amber); }
.addTicker { display: grid; grid-template-columns: minmax(0, 1fr) auto; gap: 10px; align-items: start; }
.addTicker button { margin-top: 26px; }
```

In `web/src/ui/help.ts` add before the closing `};`:

```ts
  "Wartość": {
    what: "Ile byłoby do wypłaty na koniec okresu.",
    how: "wartość do wypłaty ostatniego dnia: po kosztach sprzedaży i przewalutowania, tak jak na Pulpicie.",
  },
```

`web/src/screens/simulator/Measures.tsx`:

```tsx
import type { ReactNode } from "react";
import type { ScenarioMeasures } from "../../api/types";
import { formatPercent, signOf } from "../../format";
import { Money } from "../../ui/Amount";
import { HELP } from "../../ui/help";
import { InfoTip } from "../../ui/InfoTip";
import ui from "../../ui/ui.module.css";
import { shownReturn } from "../analysis/model";
import { swatchStyle } from "../../charts/ComparisonChart";
import styles from "./Simulator.module.css";

export interface Column { key: string; label: string; color: string; dashed?: boolean; measures: ScenarioMeasures | null }

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");
const percent = (value: string | null, sign = true) =>
  <span className={`num ${sign ? tone(value) : ""}`}>{formatPercent(value, { places: 1, sign })}</span>;

const ROWS: { label: string; value: (m: ScenarioMeasures) => ReactNode }[] = [
  { label: "Wartość", value: (m) => <Money value={m.value_pln} /> },
  { label: "Wpłacono", value: (m) => <Money value={m.invested_pln} /> },
  { label: "Zysk", value: (m) => <Money value={m.profit_pln} sign tone /> },
  { label: "XIRR", value: (m) => percent(shownReturn(m.xirr, m.period.annualized).value) },
  { label: "TWR", value: (m) => percent(shownReturn(m.twr, m.period.annualized).value) },
  { label: "Maks. obsunięcie", value: (m) => percent(m.max_drawdown?.pct ?? null) },
  { label: "Zmienność", value: (m) => percent(m.volatility_pct, false) },
];

/** A card per line; the "?" explanations sit in the first card only. */
export function Measures({ columns }: { columns: Column[] }) {
  return (
    <div className={styles.columns}>
      {columns.map((column, index) => (
        <section key={column.key} className={styles.column} role="group" aria-label={column.label}>
          <div className={styles.columnHead}>
            <i className={styles.swatch} style={swatchStyle(column.color, column.dashed)} />
            <span>{column.label}</span>
          </div>
          {column.measures ? (
            <dl className={ui.kv}>
              {ROWS.map((row) => [
                <dt key={`${row.label}-t`} className={styles.label}>
                  {row.label}{index === 0 && <InfoTip label={row.label} help={HELP[row.label]!} />}
                </dt>,
                <dd key={`${row.label}-d`}>{row.value(column.measures!)}</dd>,
              ])}
            </dl>
          ) : <p className={styles.hint}>Brak wyceny w tym okresie.</p>}
        </section>
      ))}
    </div>
  );
}
```

- [ ] **Step 5: The screen** — `web/src/screens/simulator/SimulatorScreen.tsx`:

```tsx
import { useQueries, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { AnalyticsPeriod, Scenario, ScenarioResult } from "../../api/types";
import { ComparisonChart, swatchStyle } from "../../charts/ComparisonChart";
import { AccountSelect } from "../../ui/AccountPicker";
import { BackLink } from "../../ui/BackLink";
import { ListRow } from "../../ui/ListRow";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import analysis from "../analysis/Analysis.module.css";
import { PERIODS } from "../analysis/model";
import { RECALC_POLL_MS } from "../dashboard/model";
import { chartData, type ShownResult } from "./chart";
import { Measures, type Column } from "./Measures";
import { BASES, MAX_LINES, PORTFOLIO_COLOR, SLOTS, defaultShown, difference, toggleShown, type Shown } from "./model";
import styles from "./Simulator.module.css";

export const NEW_PATH = "/analiza/symulator/nowy";
const baseLabel = (scenario: Scenario) => BASES.find((base) => base.value === scenario.base)!.label;

/** Each scenario's result for the chosen accounts and period, in the order of `scenarios`. */
export function useScenarioResults(scenarios: Scenario[], period: AnalyticsPeriod) {
  const [accountIds, , ready] = useAccountSelection();
  return useQueries({
    queries: scenarios.map((scenario) => ({
      queryKey: keys.scenarioResult(scenario.id, accountIds, period),
      queryFn: () => api.scenarioResult(scenario.id, accountIds, period),
      enabled: ready,
      placeholderData: (previous: ScenarioResult | undefined) => previous,
      refetchInterval: (query: { state: { data?: ScenarioResult } }) =>
        (query.state.data?.recalculating ? RECALC_POLL_MS : false),
    })),
  });
}

/** A row per scenario: its name, starting point and difference against the portfolio. */
export function ScenarioRow({ scenario, result }: { scenario: Scenario; result: ScenarioResult | undefined }) {
  const text = result ? difference(result) ?? "brak wyceny" : "liczę…";
  return (
    <ListRow to={`/analiza/symulator/${scenario.id}`} lead="?" name={scenario.name} detail={baseLabel(scenario)}
      amount={<small className="dim">{text}</small>} />
  );
}

export function SimulatorScreen() {
  const [accountIds, setAccountIds] = useAccountSelection();
  const [period, setPeriod] = useState<AnalyticsPeriod>("all");
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const scenarios = useQuery({ queryKey: keys.scenarios, queryFn: api.scenarios });
  const list = scenarios.data ?? [];
  const results = useScenarioResults(list, period);
  const [picked, setPicked] = useState<Shown[] | null>(null);
  const [showPortfolio, setShowPortfolio] = useState(true);
  const known = new Set(list.map((scenario) => scenario.id));
  const shown = (picked ?? defaultShown(list.map((scenario) => scenario.id))).filter((item) => known.has(item.id));
  const resultOf = (id: number) => results[list.findIndex((scenario) => scenario.id === id)]?.data;

  const visible: ShownResult[] = shown.flatMap(({ id, slot }) => {
    const result = resultOf(id);
    const scenario = list.find((item) => item.id === id)!;
    return result ? [{ key: String(id), label: scenario.name, slot, result }] : [];
  });
  const data = chartData(visible, showPortfolio);
  const base = visible[0]?.result ?? results.find((query) => query.data)?.data;
  const columns: Column[] = [
    { key: "portfolio", label: "Mój portfel", color: PORTFOLIO_COLOR, measures: base?.portfolio ?? null },
    ...visible.map(({ key, label, slot, result }) => ({ key, label, ...SLOTS[slot]!, measures: result.scenario })),
  ];

  return (
    <div className={ui.page}>
      <BackLink to="/analiza" label="Analiza" />
      <div className={styles.head}>
        <h1 className={ui.pageTitle}>Symulator</h1>
        <Link className={ui.primaryButton} to={NEW_PATH}>Nowy scenariusz</Link>
      </div>
      {accounts.data && <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />}
      <Segmented label="Okres" options={PERIODS} value={period} onChange={setPeriod} className={analysis.periods} />
      {scenarios.isPending ? <Skeleton rows={4} chart />
        : scenarios.isError ? <ErrorState error={scenarios.error} onRetry={() => void scenarios.refetch()} />
        : list.length === 0 ? (
          <EmptyState title="Nie masz jeszcze scenariuszy."
            action={<Link className={ui.primaryButton} to={NEW_PATH}>Nowy scenariusz</Link>} />
        ) : (
          <>
            {results.some((query) => query.data?.recalculating) && <Recalculating />}
            <section className={ui.section} aria-label="Porównanie">
              <div className={styles.legend} role="group" aria-label="Linie na wykresie">
                <button type="button" aria-pressed={showPortfolio} onClick={() => setShowPortfolio((was) => !was)}>
                  <i className={styles.swatch} style={swatchStyle(PORTFOLIO_COLOR)} /><span>Mój portfel</span>
                </button>
                {list.map((scenario) => {
                  const item = shown.find((entry) => entry.id === scenario.id);
                  const slot = item ? SLOTS[item.slot]! : null;
                  return (
                    <button key={scenario.id} type="button" aria-pressed={Boolean(item)}
                      disabled={!item && shown.length >= MAX_LINES}
                      onClick={() => setPicked(toggleShown(shown, scenario.id))}>
                      <i className={styles.swatch} style={slot ? swatchStyle(slot.color, slot.dashed) : swatchStyle("var(--rule)")} />
                      <span>{scenario.name}</span>
                    </button>
                  );
                })}
              </div>
              {shown.length >= MAX_LINES && list.length > MAX_LINES && (
                <p className={styles.hint}>Na wykresie mieszczą się {MAX_LINES} scenariusze naraz — ukryj jeden, żeby pokazać inny.</p>
              )}
              {base ? <ComparisonChart {...data} /> : <Skeleton rows={0} chart />}
            </section>
            <section className={ui.section} aria-labelledby="measures-title">
              <h2 id="measures-title" className={ui.sectionTitle}>Miary</h2>
              <Measures columns={columns} />
            </section>
            <section className={ui.section} aria-labelledby="scenarios-title">
              <h2 id="scenarios-title" className={ui.sectionTitle}>Twoje scenariusze</h2>
              <div>
                {list.map((scenario, index) => <ScenarioRow key={scenario.id} scenario={scenario} result={results[index]?.data} />)}
              </div>
            </section>
          </>
        )}
    </div>
  );
}
```

Before writing `ScenarioRow`, check `web/src/ui/ListRow.tsx` for its props. If they differ from `{ to, lead, name, detail, amount }`, adapt `ScenarioRow` to them. Keep the link's accessible name starting with the scenario name and containing the difference text, which the tests match with `/^A .*…/`. If `ListRow` cannot carry the text, use a plain `<Link className={ui.row}>` with the same three parts: a lead, `ui.rowName` (`<b>` name, `<small>` base) and `ui.rowAmount`.

- [ ] **Step 6: The card on Analiza** — `web/src/screens/simulator/SimulatorCard.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import ui from "../../ui/ui.module.css";
import { NEW_PATH, ScenarioRow, useScenarioResults } from "./SimulatorScreen";
import styles from "./Simulator.module.css";

const LATEST = 3;

/** The latest three scenarios on Analiza; nothing while the list cannot be read. */
export function SimulatorCard() {
  const scenarios = useQuery({ queryKey: keys.scenarios, queryFn: api.scenarios });
  const latest = (scenarios.data ?? []).slice(0, LATEST);
  const results = useScenarioResults(latest, "all");
  if (!scenarios.data) return null;
  return (
    <section className={ui.section} aria-labelledby="simulator-title">
      <div className={ui.sectionHead}>
        <h2 id="simulator-title" className={ui.sectionTitle}>Symulator</h2>
        <Link className={ui.sectionMore} to="/analiza/symulator">Wszystkie scenariusze</Link>
      </div>
      {latest.length === 0
        ? <p className={styles.hint}>Sprawdź, jak wyglądałby Twój portfel przy innych decyzjach.</p>
        : <div>{latest.map((scenario, index) => <ScenarioRow key={scenario.id} scenario={scenario} result={results[index]?.data} />)}</div>}
      <Link className={ui.secondary} to={NEW_PATH}>Nowy scenariusz</Link>
    </section>
  );
}
```

`aria-labelledby` gives the section the role `region` named „Symulator”, which the test uses.

In `web/src/screens/analysis/AnalysisScreen.tsx` import `SimulatorCard` and render `<SimulatorCard />` as the last child of the page `div`, after the conditional block, so it shows whatever the analytics state.

In `web/src/routes.tsx` import `SimulatorScreen` and add `{ path: "/analiza/symulator", element: <SimulatorScreen /> }` after `/analiza`.

- [ ] **Step 7: Run the tests, the whole suite and the types**

Run: `cd web && npm test -- --run src/screens/simulator src/screens/analysis && npm run typecheck`
Expected: PASS (the Analiza tests still pass; their mock answers 404 for `/api/scenarios`, so the card renders nothing).

- [ ] **Step 8: Commit**

```bash
git add web/src/screens/simulator web/src/routes.tsx web/src/screens/analysis/AnalysisScreen.tsx web/src/ui/help.ts
git commit -m "feat(web): Symulator screen — comparison chart, measures per line, scenario list; card on Analiza"
```

---

### Task 4: The scenario editor with a live preview

**Files:**
- Create: `web/src/screens/simulator/useDebounced.ts`, `TargetSelect.tsx`, `ScenarioEditor.tsx`
- Modify: `web/src/routes.tsx`
- Test: `web/src/screens/simulator/editor.test.tsx`

**Interfaces:**
- Consumes: the Task 1 model (`toBody`, `draftOf`, `NEW_DRAFT`, `newShare`, `newReplace`, `newRecurring`, `difference`, `BASES`, `EDO`), Task 2 `ComparisonChart`, Task 3 `chartData`, `NEW_PATH`.
- Produces: routes `/analiza/symulator/nowy` and `/analiza/symulator/:scenarioId`.

- [ ] **Step 1: Write the failing tests** — `web/src/screens/simulator/editor.test.tsx`:

```tsx
import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, CATALOG, scenario, scenarioResult } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";

const NOTE = "Dywidendy udawanych instrumentów nie są liczone.";
const SAVED = scenario(5, "NASDAQ zamiast S&P");

function routes(extra: MockRoute[] = []) {
  return mockFetch([
    ...SIGNED_IN,
    ...extra,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/catalog", respond: () => CATALOG },
    { method: "POST", path: "/api/scenarios/preview", respond: () => scenarioResult("12044.20", "9.50", [NOTE]) },
    { method: "POST", path: "/api/scenarios", status: 201, respond: (_url, init) => ({ ...SAVED, ...JSON.parse(String(init.body)), id: 6 }) },
    { path: "/api/scenarios", respond: () => [SAVED] },
    { path: "/api/scenarios/5", respond: () => SAVED },
    { method: "PATCH", path: "/api/scenarios/5", respond: (_url, init) => ({ ...SAVED, ...JSON.parse(String(init.body)) }) },
    { method: "DELETE", path: "/api/scenarios/5", respond: () => new Response(null, { status: 204 }) },
    { path: /^\/api\/scenarios\/\d+\/result$/, respond: () => scenarioResult("12044.20", "9.50") },
  ]);
}

const bodyOf = (fetchMock: ReturnType<typeof routes>, method: string, path: string) => {
  const call = fetchMock.mock.calls.find(([url, init]) =>
    new URL(String(url), "http://localhost").pathname === path && (init?.method ?? "GET") === method);
  return call ? JSON.parse(String(call[1]!.body)) : undefined;
};

describe("Scenario editor", () => {
  it("creates a deposits scenario", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.type(await screen.findByLabelText("Nazwa"), "Wszystko w EDO");
    await user.click(screen.getByRole("button", { name: "Moje wpłaty" }));
    expect(screen.getByLabelText("Cel")).toHaveValue("edo");
    await user.click(screen.getByRole("button", { name: "Zapisz scenariusz" }));

    expect(await screen.findByRole("heading", { name: "Symulator" })).toBeInTheDocument();
    expect(bodyOf(fetchMock, "POST", "/api/scenarios")).toEqual({
      name: "Wszystko w EDO", base: "deposits", steps: [],
      allocation: [{ target: { instrument_id: null, bond: "EDO" }, share_pct: "100" }],
    });
  });

  it("says what is missing before saving", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.click(await screen.findByRole("button", { name: "Zapisz scenariusz" }));

    expect(screen.getByText("Podaj nazwę scenariusza.")).toBeInTheDocument();
    expect(bodyOf(fetchMock, "POST", "/api/scenarios")).toBeUndefined();
  });

  it("previews a top-up block with its notes", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.click(await screen.findByRole("button", { name: "Dopłacaj co miesiąc" }));
    await user.selectOptions(screen.getByLabelText("Na co"), "20");
    fireEvent.change(screen.getByLabelText("Od miesiąca"), { target: { value: "2024-01" } });

    expect(await screen.findByText(NOTE, {}, { timeout: 2000 })).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Porównanie wartości: Mój portfel, Podgląd" })).toBeInTheDocument();
    const preview = fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/scenarios/preview")).at(-1)!;
    expect(JSON.parse(String(preview[1]!.body)).steps).toEqual([{
      kind: "recurring", amount_pln: "1000", day_of_month: 10, start: "2024-01", end: null,
      target: { instrument_id: 20, bond: null }, ike: false,
    }]);
  });

  it("edits a saved scenario", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/5");

    const name = await screen.findByLabelText("Nazwa");
    expect(name).toHaveValue("NASDAQ zamiast S&P");
    expect(screen.getByLabelText("Zamiast")).toHaveValue("10");
    expect(screen.getByLabelText("Kupuj")).toHaveValue("20");
    await user.clear(name);
    await user.type(name, "NASDAQ");
    await user.click(screen.getByRole("button", { name: "Zapisz scenariusz" }));

    expect(await screen.findByRole("heading", { name: "Symulator" })).toBeInTheDocument();
    expect(bodyOf(fetchMock, "PATCH", "/api/scenarios/5")).toMatchObject({ name: "NASDAQ", base: "portfolio" });
  });

  it("deletes a saved scenario after a confirmation", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/5");

    await user.click(await screen.findByRole("button", { name: "Usuń scenariusz" }));
    await user.click(screen.getByRole("button", { name: "Usuń" }));

    expect(await screen.findByRole("heading", { name: "Symulator" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/api/scenarios/5") && init?.method === "DELETE"))
      .toBe(true);
  });

  it("adds a ticker to the catalog", async () => {
    const added = { id: 30, ticker: "VWCE.DE", name: "Vanguard FTSE All-World", currency: "EUR",
                    group: "Dodane przez Ciebie", accumulating: null, prices_from: "2019-07-25" };
    const fetchMock = routes([{ method: "POST", path: "/api/catalog", status: 201, respond: () => added }]);
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.type(await screen.findByLabelText("Brakuje instrumentu? Dodaj ticker z Yahoo"), "vwce.de");
    await user.click(screen.getByRole("button", { name: "Dodaj ticker" }));

    expect(await screen.findByText("Dodano: Vanguard FTSE All-World")).toBeInTheDocument();
    expect(bodyOf(fetchMock, "POST", "/api/catalog")).toEqual({ ticker: "vwce.de" });
  });

  it("shows the API's message when saving fails", async () => {
    routes([{ method: "POST", path: "/api/scenarios", respond: () => json(422, {
      code: "unknown_instrument", message: "Nie ma takiego instrumentu w katalogu ani w portfelu.", details: {} }) }]);
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.type(await screen.findByLabelText("Nazwa"), "Test");
    await user.click(screen.getByRole("button", { name: "Zapisz scenariusz" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Nie ma takiego instrumentu w katalogu ani w portfelu.");
    expect(screen.getByLabelText("Nazwa")).toHaveValue("Test");
  });
});
```

(The routes in `extra` come first, so they win over the defaults with the same path and method.)

- [ ] **Step 2: Run to verify they fail**

Run: `cd web && npm test -- --run src/screens/simulator/editor.test.tsx`
Expected: FAIL (the route `/analiza/symulator/nowy` falls to `*` and redirects to `/`).

- [ ] **Step 3: Implement**

`web/src/screens/simulator/useDebounced.ts`:

```ts
import { useEffect, useState } from "react";

/** `value` once it has stayed the same (by its JSON) for `ms`; the first value at once. */
export function useDebounced<T>(value: T, ms: number): T {
  const [settled, setSettled] = useState(value);
  const key = JSON.stringify(value);
  useEffect(() => {
    const timer = setTimeout(() => setSettled(value), ms);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps -- `key` stands for `value`
  }, [key, ms]);
  return settled;
}
```

`web/src/screens/simulator/TargetSelect.tsx`:

```tsx
import type { CatalogGroup } from "../../api/types";
import { Field } from "../../ui/forms";
import { EDO } from "./model";

/** An instrument from the catalog (in its groups), or EDO bonds when `bonds`. */
export function TargetSelect({ id, label, catalog, value, onChange, bonds = false, groups, error }: {
  id: string; label: string; catalog: CatalogGroup[]; value: string; onChange: (value: string) => void;
  bonds?: boolean; groups?: string[]; error?: string;
}) {
  const shown = groups ? catalog.filter((group) => groups.includes(group.group)) : catalog;
  return (
    <Field id={id} label={label} error={error}>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)} aria-invalid={Boolean(error)}>
        {value === "" && <option value="">Wybierz…</option>}
        {bonds && <option value={EDO}>Obligacje EDO</option>}
        {shown.map((group) => (
          <optgroup key={group.group} label={group.group}>
            {group.items.map((item) => (
              <option key={`${group.group}-${item.id}`} value={String(item.id)}>{item.name} ({item.ticker})</option>
            ))}
          </optgroup>
        ))}
      </select>
    </Field>
  );
}
```

`web/src/screens/simulator/ScenarioEditor.tsx`:

```tsx
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState, type FormEvent } from "react";
import { useNavigate, useParams } from "react-router";
import { useAccountSelection } from "../../accounts/AccountSelection";
import { errorMessage } from "../../api/messages";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { CatalogGroup, ScenarioIn } from "../../api/types";
import { ComparisonChart } from "../../charts/ComparisonChart";
import { addMonths, todayIso } from "../../format";
import { Confirm, Field, FormError } from "../../ui/forms";
import forms from "../../ui/forms.module.css";
import { BackLink } from "../../ui/BackLink";
import { Segmented } from "../../ui/Segmented";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { chartData } from "./chart";
import {
  BASES, NEW_DRAFT, difference, draftOf, newRecurring, newReplace, newShare, toBody, type Draft, type StepDraft,
} from "./model";
import styles from "./Simulator.module.css";
import { TargetSelect } from "./TargetSelect";
import { useDebounced } from "./useDebounced";

const PREVIEW_DELAY_MS = 500;
const HELD = "Twój portfel";
const LIST = "/analiza/symulator";
const DAYS = Array.from({ length: 28 }, (_, i) => String(i + 1));
const BASE_HINT: Record<Draft["base"], string> = {
  portfolio: "Twoje prawdziwe transakcje; klocki zmieniają je albo dokładają nowe pieniądze.",
  deposits: "Tylko Twoje wpłaty i wypłaty, z tymi samymi datami i kwotami; każda wpłata idzie według podziału.",
};

export function ScenarioEditor() {
  const { scenarioId } = useParams();
  const id = scenarioId ? Number(scenarioId) : null;
  const stored = useQuery({ queryKey: keys.scenario(id ?? 0), queryFn: () => api.scenario(id!), enabled: id !== null });
  const catalog = useQuery({ queryKey: keys.catalog, queryFn: api.catalog });
  const failed = (id !== null && stored.isError) ? stored : catalog.isError ? catalog : null;
  if (failed) return <div className={ui.page}><ErrorState error={failed.error} onRetry={() => void failed.refetch()} /></div>;
  if ((id !== null && !stored.data) || !catalog.data) return <div className={ui.page}><Skeleton rows={6} /></div>;
  return <EditorForm key={id ?? "new"} id={id} initial={stored.data ? draftOf(stored.data) : NEW_DRAFT} catalog={catalog.data} />;
}

function EditorForm({ id, initial, catalog }: { id: number | null; initial: Draft; catalog: CatalogGroup[] }) {
  const navigate = useNavigate();
  const queryClient = useQueryClient();
  const [accountIds, , ready] = useAccountSelection();
  const [draft, setDraft] = useState<Draft>(initial);
  const [tried, setTried] = useState(false);
  const [confirming, setConfirming] = useState(false);
  const { body, errors } = toBody(draft);
  const shownErrors = tried ? errors : {};
  const previewBody = useDebounced(toBody({ ...draft, name: draft.name.trim() || "Podgląd" }).body, PREVIEW_DELAY_MS);
  const preview = useQuery({
    queryKey: keys.scenarioPreview(previewBody ?? {}, accountIds),
    queryFn: () => api.previewScenario(previewBody!, accountIds),
    enabled: ready && previewBody !== null,
    placeholderData: (previous) => previous,
  });

  const done = async (savedId: number) => {
    await Promise.all([
      queryClient.invalidateQueries({ queryKey: keys.scenarios }),
      queryClient.invalidateQueries({ queryKey: keys.scenarioResults(savedId) }),
    ]);
    navigate(LIST);
  };
  const save = useMutation({
    mutationFn: (scenario: ScenarioIn) => (id === null ? api.createScenario(scenario) : api.updateScenario(id, scenario)),
    onSuccess: (saved) => done(saved.id),
  });
  const remove = useMutation({ mutationFn: () => api.deleteScenario(id!), onSuccess: () => done(id!) });

  const set = (change: Partial<Draft>) => setDraft((was) => ({ ...was, ...change }));
  const setShare = (index: number, change: Partial<Draft["allocation"][number]>) =>
    set({ allocation: draft.allocation.map((share, i) => (i === index ? { ...share, ...change } : share)) });
  const setStep = (index: number, change: Partial<StepDraft>) =>
    set({ steps: draft.steps.map((step, i) => (i === index ? ({ ...step, ...change } as StepDraft) : step)) });
  const chooseBase = (base: Draft["base"]) =>
    set({ base, allocation: base === "deposits" && draft.allocation.length === 0 ? [newShare()] : draft.allocation });

  function submit(event: FormEvent) {
    event.preventDefault();
    setTried(true);
    if (body) save.mutate(body);
  }

  const result = preview.data;
  const lines = result ? chartData([{ key: "preview", label: draft.name.trim() || "Podgląd", slot: 0, result }], true) : null;

  return (
    <div className={ui.page}>
      <BackLink to={LIST} label="Symulator" />
      <h1 className={ui.pageTitle}>{id === null ? "Nowy scenariusz" : "Scenariusz"}</h1>
      <form className={forms.form} onSubmit={submit} noValidate>
        <Field id="scenario-name" label="Nazwa" error={shownErrors.name}>
          <input id="scenario-name" value={draft.name} maxLength={80} onChange={(e) => set({ name: e.target.value })}
            aria-invalid={Boolean(shownErrors.name)} />
        </Field>
        <div className={forms.field}>
          <Segmented label="Punkt wyjścia" options={BASES} value={draft.base} onChange={chooseBase} />
          <small className={forms.hint}>{BASE_HINT[draft.base]}</small>
        </div>

        {draft.base === "deposits" && (
          <fieldset className={styles.block}>
            <legend>Na co idą wpłaty</legend>
            {draft.allocation.map((share, index) => (
              <div key={index} className={styles.shareRow}>
                <TargetSelect id={`share-${index}-target`} label="Cel" catalog={catalog} bonds value={share.target}
                  onChange={(target) => setShare(index, { target })} />
                <Field id={`share-${index}-pct`} label="Udział (%)" error={shownErrors[`allocation.${index}.pct`]}>
                  <input id={`share-${index}-pct`} inputMode="decimal" value={share.pct}
                    onChange={(e) => setShare(index, { pct: e.target.value })} />
                </Field>
                {draft.allocation.length > 1 && (
                  <button type="button" className={forms.link}
                    onClick={() => set({ allocation: draft.allocation.filter((_, i) => i !== index) })}>Usuń cel</button>
                )}
              </div>
            ))}
            {shownErrors.allocation && <small className={forms.error}>{shownErrors.allocation}</small>}
            <button type="button" className={forms.link}
              onClick={() => set({ allocation: [...draft.allocation, { ...newShare(), pct: "" }] })}>Dodaj cel</button>
          </fieldset>
        )}

        {draft.steps.map((step, index) => (
          <fieldset key={index} className={styles.block}>
            <legend>{step.kind === "replace" ? "Podmień instrument" : "Dopłacaj co miesiąc"}</legend>
            {step.kind === "replace" ? (
              <>
                <TargetSelect id={`step-${index}-from`} label="Zamiast" catalog={catalog} groups={[HELD]} value={step.from}
                  onChange={(from) => setStep(index, { from })} error={shownErrors[`steps.${index}.from`]} />
                <TargetSelect id={`step-${index}-to`} label="Kupuj" catalog={catalog} value={step.to}
                  onChange={(to) => setStep(index, { to })} error={shownErrors[`steps.${index}.to`]} />
              </>
            ) : (
              <>
                <div className={forms.row}>
                  <Field id={`step-${index}-amount`} label="Kwota co miesiąc (zł)" error={shownErrors[`steps.${index}.amount`]}>
                    <input id={`step-${index}-amount`} inputMode="decimal" value={step.amount}
                      onChange={(e) => setStep(index, { amount: e.target.value })} />
                  </Field>
                  <Field id={`step-${index}-day`} label="Dzień miesiąca">
                    <select id={`step-${index}-day`} value={step.day} onChange={(e) => setStep(index, { day: e.target.value })}>
                      {DAYS.map((day) => <option key={day} value={day}>{day}</option>)}
                    </select>
                  </Field>
                </div>
                <div className={forms.row}>
                  <Field id={`step-${index}-start`} label="Od miesiąca" error={shownErrors[`steps.${index}.start`]}>
                    <input id={`step-${index}-start`} type="month" min="2016-01" placeholder="RRRR-MM" value={step.start}
                      onChange={(e) => setStep(index, { start: e.target.value })} />
                  </Field>
                  <Field id={`step-${index}-end`} label="Do miesiąca" hint="puste: do dziś" error={shownErrors[`steps.${index}.end`]}>
                    <input id={`step-${index}-end`} type="month" min="2016-01" placeholder="RRRR-MM" value={step.end}
                      onChange={(e) => setStep(index, { end: e.target.value })} />
                  </Field>
                </div>
                <TargetSelect id={`step-${index}-target`} label="Na co" catalog={catalog} bonds value={step.target}
                  onChange={(target) => setStep(index, { target })} />
                <label className={styles.check}>
                  <input type="checkbox" checked={step.ike} onChange={(e) => setStep(index, { ike: e.target.checked })} />
                  Na IKE (obligacje bez podatku)
                </label>
              </>
            )}
            <button type="button" className={forms.link}
              onClick={() => set({ steps: draft.steps.filter((_, i) => i !== index) })}>Usuń klocek</button>
          </fieldset>
        ))}
        <div className={forms.actions}>
          {draft.base === "portfolio" && (
            <button type="button" className={ui.secondary} onClick={() => set({ steps: [...draft.steps, newReplace()] })}>
              Podmień instrument
            </button>
          )}
          <button type="button" className={ui.secondary}
            onClick={() => set({ steps: [...draft.steps, newRecurring(addMonths(todayIso(), -12).slice(0, 7))] })}>
            Dopłacaj co miesiąc
          </button>
        </div>
        <AddTicker />

        <section className={ui.section} aria-labelledby="preview-title">
          <h2 id="preview-title" className={ui.sectionTitle}>Podgląd</h2>
          {previewBody === null ? <p className={styles.hint}>Uzupełnij scenariusz, żeby zobaczyć podgląd.</p>
            : preview.isError ? <ErrorState error={preview.error} onRetry={() => void preview.refetch()} />
            : !result || !lines ? <Skeleton rows={0} chart />
            : (
              <>
                {difference(result) && <p className={styles.diff}>Względem portfela: {difference(result)}</p>}
                <ComparisonChart {...lines} />
                {result.notes.length > 0 && <ul className={styles.notes}>{result.notes.map((note) => <li key={note}>{note}</li>)}</ul>}
              </>
            )}
        </section>

        <FormError message={save.isError ? errorMessage(save.error) : remove.isError ? errorMessage(remove.error) : null} />
        <div className={forms.actions}>
          <button type="submit" className={ui.primaryButton} disabled={save.isPending}>Zapisz scenariusz</button>
          {id !== null && !confirming && (
            <button type="button" className={forms.danger} onClick={() => setConfirming(true)}>Usuń scenariusz</button>
          )}
        </div>
        {confirming && (
          <Confirm question={`Usunąć scenariusz „${initial.name}”?`} confirmLabel="Usuń" busy={remove.isPending}
            onConfirm={() => remove.mutate()} onCancel={() => setConfirming(false)} />
        )}
      </form>
    </div>
  );
}

function AddTicker() {
  const queryClient = useQueryClient();
  const [ticker, setTicker] = useState("");
  const add = useMutation({
    mutationFn: () => api.addTicker(ticker.trim()),
    onSuccess: async () => {
      setTicker("");
      await queryClient.invalidateQueries({ queryKey: keys.catalog });
    },
  });
  return (
    <div className={styles.addTicker}>
      <Field id="add-ticker" label="Brakuje instrumentu? Dodaj ticker z Yahoo"
        error={add.isError ? errorMessage(add.error) : undefined}
        hint={add.data ? `Dodano: ${add.data.name}` : "np. VWCE.DE albo AAPL.US"}>
        <input id="add-ticker" value={ticker} onChange={(e) => setTicker(e.target.value)} />
      </Field>
      <button type="button" className={ui.secondary} disabled={!ticker.trim() || add.isPending} onClick={() => add.mutate()}>
        Dodaj ticker
      </button>
    </div>
  );
}
```

In `web/src/routes.tsx` import `ScenarioEditor` and add, after `/analiza/symulator`:

```tsx
          { path: "/analiza/symulator/nowy", element: <ScenarioEditor /> },
          { path: "/analiza/symulator/:scenarioId", element: <ScenarioEditor /> },
```

Note: the `Segmented` of the base sits inside `forms.field` only for the hint underneath it; it has its own `aria-label`, so no `<label>` is needed. The `FormError` renders `role="alert"`; the preview's `ErrorState` also uses `role="alert"`. The failing-save test mocks a working preview, so only one alert is present.

- [ ] **Step 4: Run the tests, the whole suite and the types**

Run: `cd web && npm test -- --run src/screens/simulator && npm test && npm run typecheck`
Expected: PASS everywhere.

- [ ] **Step 5: Commit**

```bash
git add web/src/screens/simulator web/src/routes.tsx
git commit -m "feat(web): scenario editor — starting point, blocks, catalog picker with Dodaj ticker, live preview"
```

---

### Task 5: e2e and the roadmap

**Files:**
- Modify: `web/e2e/app.spec.ts`, `docs/superpowers/plans/2026-09-26-00-roadmap.md`

- [ ] **Step 1: The e2e step** — in the first test of `web/e2e/app.spec.ts`, after the Analiza check (`await expect(page.getByRole("group", { name: "TWR" })).toBeVisible();`), add:

```ts
  await page.getByRole("link", { name: "Nowy scenariusz" }).click();
  await expect(page.getByRole("heading", { name: "Nowy scenariusz" })).toBeVisible();
  await page.getByLabel("Nazwa").fill("Wszystko w EDO");
  await page.getByRole("button", { name: "Moje wpłaty" }).click();
  await expect(page.getByRole("img", { name: /Porównanie wartości: Mój portfel, Wszystko w EDO/ })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/scenariusz.png`, fullPage: true });
  await page.getByRole("button", { name: "Zapisz scenariusz" }).click();
  await expect(page.getByRole("heading", { name: "Symulator" })).toBeVisible();
  await expect(page.getByRole("group", { name: "Linie na wykresie" }).getByRole("button", { name: "Wszystko w EDO" }))
    .toHaveAttribute("aria-pressed", "true");
  await expect(page.getByRole("img", { name: /Porównanie wartości: Mój portfel, Wszystko w EDO/ })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/symulator.png`, fullPage: true });
```

The e2e database is migrated to head, so EDO issues 01.2026 and 03.2026 (the sample's deposit months) are seeded by migration 0011.

- [ ] **Step 2: Run e2e**

Run: `cd web && npm run e2e`
Expected: 3 passed. If the e2e stack needs starting, follow `web/e2e/global-setup.ts`, which brings up `db-e2e` and `api-e2e` through docker compose's `e2e` profile.

- [ ] **Step 3: Roadmap** — in `docs/superpowers/plans/2026-09-26-00-roadmap.md`:
  - mark row 7b ✅ zrobiony with the three plan files;
  - extend the „Plan 7b-2” paragraph, or add „Plan 7b-3 (2026-10-02)”, with the screens: Symulator card on Analiza, `/analiza/symulator`, the editor, the 3-line cap and colours;
  - say the next step is the batch of all small fixes from the „Carried from …” sections (the owner's decision of 2026-10-02).

- [ ] **Step 4: Commit**

```bash
git add web/e2e/app.spec.ts docs/superpowers/plans/2026-09-26-00-roadmap.md
git commit -m "test(e2e): a deposits scenario saved and drawn in the simulator; roadmap 7b done"
```
