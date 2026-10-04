/** Pure geometry of the currency-share chart. Shares are display proportions (Number), never money. */
import type { Exposure } from "../api/types";

/** The series colours of chart-colors.css, validated with the dataviz palette checker in both themes. */
export const SHARE_COLORS = ["var(--series-1)", "var(--series-2)", "var(--series-3)", "var(--series-4)"] as const;
const MAX_SERIES = SHARE_COLORS.length;
const OTHER = "other";

export interface ShareSeries { key: string; label: string; color: string }
export interface SharePoint { date: string; shares: number[] }

const label = (currency: string) => (currency === "unknown" ? "Nieznana" : currency);
const positive = (value: string | undefined) => Math.max(Number(value ?? 0), 0);

/** Today's order first (largest value), then currencies seen only in the past by their largest value. */
export function shareSeries(exposure: Exposure): ShareSeries[] {
  // by today's value here, not by the order the API happens to send
  const order = [...exposure.current].sort((a, b) => Number(b.value_pln) - Number(a.value_pln)).map((c) => c.currency);
  const past = new Map<string, number>();
  for (const point of exposure.history) {
    for (const [currency, value] of Object.entries(point.values)) {
      if (!order.includes(currency)) past.set(currency, Math.max(past.get(currency) ?? 0, positive(value)));
    }
  }
  order.push(...[...past.entries()].sort((a, b) => b[1] - a[1]).map(([currency]) => currency));
  const kept = order.length > MAX_SERIES ? order.slice(0, MAX_SERIES - 1) : order;
  const series = kept.map((currency, i) => ({ key: currency, label: label(currency), color: SHARE_COLORS[i]! }));
  if (order.length > MAX_SERIES) series.push({ key: OTHER, label: "Inne", color: SHARE_COLORS[MAX_SERIES - 1]! });
  return series;
}

/** The colour of a currency's series, or of "Inne" when it was folded into it. */
export function colorOf(series: ShareSeries[], currency: string): string | undefined {
  return (series.find((s) => s.key === currency) ?? series.find((s) => s.key === OTHER))?.color;
}

export function sharePoints(exposure: Exposure, series: ShareSeries[]): SharePoint[] {
  const named = new Set(series.filter((s) => s.key !== OTHER).map((s) => s.key));
  return exposure.history.flatMap((point) => {
    const entries = Object.entries(point.values);
    const total = entries.reduce((sum, [, value]) => sum + positive(value), 0);
    if (total <= 0) return [];
    const shares = series.map((s) =>
      (s.key === OTHER
        ? entries.filter(([currency]) => !named.has(currency)).reduce((sum, [, value]) => sum + positive(value), 0)
        : positive(point.values[s.key])) / total);
    return [{ date: point.date, shares }];
  });
}

export function thin(points: SharePoint[], max: number): SharePoint[] {
  if (points.length <= max) return points;
  const step = Math.ceil(points.length / max);
  const kept = points.filter((_, i) => i % step === 0);
  if (kept.at(-1) !== points.at(-1)) kept.push(points.at(-1)!);
  return kept;
}

const f = (n: number) => n.toFixed(1);

/** One closed path per series: from the bottom-left along the edge of the series below, back along its own top. */
export function bands(points: SharePoint[], width: number, height: number): string[] {
  const last = Math.max(points.length - 1, 1);
  const x = (i: number) => f((i / last) * width);
  const y = (share: number) => f(height * (1 - share));
  const count = points[0]?.shares.length ?? 0;
  let below = points.map(() => 0);
  const paths: string[] = [];
  for (let k = 0; k < count; k++) {
    const top = points.map((p, i) => below[i]! + p.shares[k]!);
    const bottomEdge = below.map((v, i) => `${i ? "L" : "M"}${x(i)},${y(v)}`).join("");
    const topEdge = top.map((v, i) => [i, v] as const).reverse().map(([i, v]) => `L${x(i)},${y(v)}`).join("");
    paths.push(`${bottomEdge}${topEdge}Z`);
    below = top;
  }
  return paths;
}

/** The last day of each calendar month, for the table view. */
export function monthlyRows(points: SharePoint[]): SharePoint[] {
  return points.filter((p, i) => i === points.length - 1 || points[i + 1]!.date.slice(0, 7) !== p.date.slice(0, 7));
}
