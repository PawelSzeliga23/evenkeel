import type { AnalyticsPeriod, Money, PeriodReturn } from "../../api/types";
import { formatPercent } from "../../format";

export const PERIODS: { value: AnalyticsPeriod; label: string }[] = [
  { value: "1m", label: "1M" }, { value: "3m", label: "3M" }, { value: "1y", label: "1R" },
  { value: "ytd", label: "Od pocz. roku" }, { value: "all", label: "Wszystko" },
];

export const MONTHS = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];

/** Returns are for the period below a year and annual from a year on (owner's decision 7a). */
export function shownReturn(value: PeriodReturn, annualized: boolean): { value: Money | null; caption: string } {
  if (!annualized) return { value: value.period_pct, caption: "za okres" };
  return { value: value.annual_pct, caption: `rocznie · za okres ${formatPercent(value.period_pct, { places: 1 })}` };
}

const SATURATION_PCT = 5;
const MAX_ALPHA = 0.55;

/** Green or red behind a month, stronger with the size of the return, full at ±5 %. */
export function cellBackground(pct: Money | null): string {
  const value = pct === null ? 0 : Number(pct);
  if (value === 0) return "transparent";
  const alpha = Math.round(Math.min(Math.abs(value) / SATURATION_PCT, 1) * MAX_ALPHA * 100) / 100;
  return `color-mix(in srgb, var(${value > 0 ? "--heat-gain" : "--heat-loss"}) ${Math.round(alpha * 100)}%, transparent)`;
}
