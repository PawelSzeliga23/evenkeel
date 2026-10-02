import type { Holding, HoldingsPeriod } from "../../api/types";
import { formatPercent } from "../../format";

export const PERIODS: { value: HoldingsPeriod; label: string }[] = [
  { value: "1d", label: "Dzień" }, { value: "1w", label: "Tydzień" }, { value: "1m", label: "Miesiąc" },
  { value: "1y", label: "Rok" }, { value: "ytd", label: "Od pocz. roku" }, { value: "all", label: "Wszystko" },
];

export const GAIN_LABEL: Record<HoldingsPeriod, string> = {
  "1d": "Zysk dnia", "1w": "Zysk tygodnia", "1m": "Zysk miesiąca", "1y": "Zysk roku", ytd: "Zysk od pocz. roku",
  all: "Zysk od początku",
};

export type Ranking = "pln" | "pct";

/** Bonds and savings accounts, hidden by „Bez oszczędności i obligacji”. */
export const isFixedIncome = (item: Holding) => item.kind !== "instrument";

export interface Shown { item: Holding; share: string; contribution: string | null }

const percentOf = (part: number, whole: number) => formatPercent((part * 100 / whole).toFixed(1), { places: 1, sign: false });

/**
 * The shown holdings with their share of the shown value and their part of the shown gain (or loss), computed here
 * because they depend on the toggle (owner's decision 7c).
 */
export function shown(items: Holding[], withoutFixedIncome: boolean): Shown[] {
  const kept = withoutFixedIncome ? items.filter((item) => !isFixedIncome(item)) : items;
  const value = kept.reduce((sum, item) => sum + Number(item.value_pln), 0);
  const gain = kept.reduce((sum, item) => sum + Number(item.gain_pln), 0);
  const word = gain > 0 ? "zysku" : "straty";
  return kept.map((item) => ({
    item,
    share: value > 0 ? `${percentOf(Number(item.value_pln), value)} portfela` : "",
    contribution: gain === 0 ? null : `${formatPercent((Number(item.gain_pln) * 100 / gain).toFixed(1), { places: 1, sign: false })} ${word}`,
  }));
}

export function ranked(rows: Shown[], by: Ranking): Shown[] {
  const key = (row: Shown) => (by === "pln" ? Number(row.item.gain_pln) : row.item.gain_pct === null ? -Infinity : Number(row.item.gain_pct));
  return [...rows].sort((a, b) => key(b) - key(a));
}
