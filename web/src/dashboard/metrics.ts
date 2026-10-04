/** Plan 9: the figures a tile can show — from the summary (the whole history) or the analytics (a period). */
import type { Analytics, Money, Summary } from "../api/types";
import { formatDate, sumMoney } from "../format";
import { shownReturn } from "../screens/analysis/model";
import { HELP, type Help } from "../ui/help";

export const METRIC_KEYS = [
  "total_gain", "twr_total", "invested", "income", "cash", "day_change", "fees",
  "profit", "twr", "xirr", "volatility", "sharpe", "max_drawdown", "current_drawdown", "best_day", "worst_day",
] as const;
export type MetricKey = (typeof METRIC_KEYS)[number];

export interface MetricValue {
  value: Money | null;
  format: "money" | "percent" | "number";
  /** Green or red by sign. */
  tone: boolean;
  /** A short caption, e.g. „rocznie” or the day. */
  note?: string;
}

interface MetricInfo {
  label: string;
  help: Help | null;
  source: "summary" | "analytics";
  read: (summary: Summary, analytics: Analytics) => MetricValue;
}

const money = (value: Money | null, tone = true): MetricValue => ({ value, format: "money", tone });
const percent = (value: Money | null, tone = true, note?: string): MetricValue =>
  (note === undefined ? { value, format: "percent", tone } : { value, format: "percent", tone, note });

function periodReturn(a: Analytics, which: "twr" | "xirr"): MetricValue {
  const annualized = a.period?.annualized ?? false;
  return percent(shownReturn(a[which], annualized).value, true, annualized ? "rocznie" : "za okres");
}

export const METRICS: Record<MetricKey, MetricInfo> = {
  total_gain: { label: "Zysk łącznie", help: HELP["Zysk łącznie"]!, source: "summary", read: (s) => money(s.total_gain_pln) },
  twr_total: { label: "Stopa zwrotu (TWR)", help: HELP["Stopa zwrotu (TWR)"]!, source: "summary", read: (s) => percent(s.twr_pct) },
  invested: { label: "Wpłacono", help: HELP["Wpłacono"]!, source: "summary", read: (s) => money(s.invested_pln, false) },
  income: {
    label: "Dywidendy i odsetki", help: HELP["Dywidendy i odsetki"]!, source: "summary",
    read: (s) => money(sumMoney([s.dividends_net_pln, s.interest_net_pln]), false),
  },
  cash: { label: "Gotówka", help: null, source: "summary", read: (s) => money(s.cash_pln, false) },
  day_change: { label: "Zmiana dziś", help: null, source: "summary", read: (s) => money(s.day_change_pln) },
  fees: { label: "Opłaty", help: null, source: "summary", read: (s) => money(s.fees_pln, false) },
  profit: { label: "Zysk w okresie", help: HELP["Zysk"]!, source: "analytics", read: (_, a) => money(a.profit_pln) },
  twr: { label: "TWR", help: HELP.TWR!, source: "analytics", read: (_, a) => periodReturn(a, "twr") },
  xirr: { label: "XIRR", help: HELP.XIRR!, source: "analytics", read: (_, a) => periodReturn(a, "xirr") },
  volatility: { label: "Zmienność", help: HELP["Zmienność"]!, source: "analytics", read: (_, a) => percent(a.volatility_pct, false) },
  sharpe: {
    label: "Sharpe", help: HELP.Sharpe!, source: "analytics",
    read: (_, a) => ({ value: a.sharpe, format: "number", tone: true }),
  },
  max_drawdown: {
    label: "Maks. obsunięcie", help: HELP["Maks. obsunięcie"]!, source: "analytics",
    read: (_, a) => percent(a.max_drawdown?.pct ?? null),
  },
  current_drawdown: {
    label: "Obecne obsunięcie", help: HELP["Obecne obsunięcie"]!, source: "analytics",
    read: (_, a) => percent(a.current_drawdown_pct),
  },
  best_day: {
    label: "Najlepszy dzień", help: HELP["Najlepszy dzień"]!, source: "analytics",
    read: (_, a) => (a.best_day ? percent(a.best_day.pct, true, formatDate(a.best_day.date)) : percent(null)),
  },
  worst_day: {
    label: "Najgorszy dzień", help: HELP["Najgorszy dzień"]!, source: "analytics",
    read: (_, a) => (a.worst_day ? percent(a.worst_day.pct, true, formatDate(a.worst_day.date)) : percent(null)),
  },
};

export const METRIC_OPTIONS = METRIC_KEYS.map((value) => ({ value, label: METRICS[value].label }));

/** The metric's figure; an analytics one is null until its data arrives. */
export function metricValue(key: MetricKey, summary: Summary, analytics: Analytics | undefined): MetricValue {
  const info = METRICS[key];
  if (info.source === "analytics" && analytics === undefined) return { ...info.read(summary, EMPTY), value: null };
  return info.read(summary, analytics ?? EMPTY);
}

const EMPTY: Analytics = {
  period: null, profit_pln: "0.00", twr: { period_pct: null, annual_pct: null }, xirr: { period_pct: null, annual_pct: null },
  volatility_pct: null, sharpe: null, short_sample: false, max_drawdown: null, current_drawdown_pct: null,
  best_day: null, worst_day: null, drawdown_series: [], monthly: [], recalculating: false,
};
