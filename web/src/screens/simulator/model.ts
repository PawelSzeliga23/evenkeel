/** The simulator's pure pieces: the editor's draft and the API body, line colours, and the difference text. */
import type {
  Money, Scenario, ScenarioBase, ScenarioIn, ScenarioResult, ScenarioShare, ScenarioStep, ScenarioTarget,
} from "../../api/types";
import { formatMoney, formatPercent, fromCents, isPositive, parseAmount, toCents } from "../../format";
import { AMOUNT_HINT } from "../../ui/forms";
import { shownReturn } from "../analysis/model";

export const EDO = "edo";
export const BASE_CONFLICT = "Podmiana działa tylko na punkcie wyjścia „Mój portfel”.";
export const FIRST_MONTH = "2016-01"; // the catalog's prices, NBP rates and EDO issues start here (plan 7b-1)
export const MAX_LINES = 3;
const MAX_TOP_UP_CENTS = 100_000_000n; // 1 000 000 zł, the API's limit
export const PORTFOLIO_COLOR = "var(--series-1)";
/** Validated on the dark surface: blue, magenta, violet; violet is dashed (close to blue for protan readers). */
export const SLOTS: { color: string; dashed: boolean }[] = [
  { color: "var(--series-2)", dashed: false }, { color: "var(--series-3)", dashed: false }, { color: "var(--series-4)", dashed: true },
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
      if (draft.base === "deposits") fail("from", BASE_CONFLICT);
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
    else if (toCents(amount) > MAX_TOP_UP_CENTS) { fail("amount", "Najwyżej 1 000 000 zł miesięcznie."); ok = false; }
    if (!/^\d{4}-\d{2}$/.test(step.start) || step.start < FIRST_MONTH) {
      fail("start", "Dopłaty mogą zaczynać się najwcześniej w 01.2016."); ok = false;
    } else if (step.end && step.end < step.start) { fail("end", "Koniec nie może być przed początkiem."); ok = false; }
    if (ok && amount !== null) {
      steps.push({ kind: "recurring", amount_pln: amount, day_of_month: Number(step.day), start: step.start,
                   end: step.end || null, target: targetOf(step.target), ike: step.target === EDO && step.ike });
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
