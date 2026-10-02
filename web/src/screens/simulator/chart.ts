import type { IsoDate, Money, ScenarioResult } from "../../api/types";
import type { ComparisonLine } from "../../charts/ComparisonChart";
import { PORTFOLIO_COLOR, SLOTS } from "./model";

export interface ShownResult { key: string; label: string; slot: number; result: ScenarioResult }

/** The lines on one date axis (the union of every result's days); the real portfolio and its capital come from the
 * results too: every result carries the same real line. With no scenario shown, `fallback` gives the real line. */
export function chartData(shown: ShownResult[], showPortfolio: boolean, fallback?: ScenarioResult): {
  dates: IsoDate[]; lines: ComparisonLine[]; invested: (Money | null)[];
} {
  const sources = shown.length > 0 ? shown.map(({ result }) => result) : fallback ? [fallback] : [];
  const dates = [...new Set(sources.flatMap((result) =>
    result.points.filter((point) => shown.length > 0 || point.portfolio_pln !== null).map((point) => point.date)))].sort();
  const real = new Map<IsoDate, { value: Money | null; invested: Money | null }>();
  for (const result of sources) {
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
