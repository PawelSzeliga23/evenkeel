/** Pure geometry of the value chart. Numbers here only place pixels; money is formatted from the API strings. */
import type { HistoryPoint } from "../api/types";
import type { ChartWindow } from "./viewport";

export interface ChartPoint { date: string; value: number; invested: number; flow: number }
export interface Frame { width: number; height: number; left: number; right: number; top: number; bottom: number }
export interface Scales { x(i: number): number; y(v: number): number; min: number; max: number; ticks: number[] }

export const FRAME: Frame = { width: 350, height: 190, left: 0, right: 44, top: 8, bottom: 22 };

const f = (n: number) => n.toFixed(1);

export function toChartPoints(points: HistoryPoint[]): ChartPoint[] {
  return points.map((p) => ({
    date: p.date, value: Number(p.value_pln), invested: Number(p.invested_pln), flow: Number(p.net_flow_pln),
  }));
}

export function niceStep(span: number, count: number): number {
  const raw = span / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * magnitude >= raw - 1e-9) return m * magnitude;
  return 10 * magnitude;
}

export function yDomain(points: ChartPoint[]): { min: number; max: number; ticks: number[] } {
  let lo = Math.min(...points.map((p) => Math.min(p.value, p.invested)));
  let hi = Math.max(...points.map((p) => Math.max(p.value, p.invested)));
  if (hi === lo) {
    const pad = Math.max(Math.abs(lo) * 0.01, 1);
    lo -= pad;
    hi += pad;
  }
  const step = niceStep(hi - lo, 3);
  const min = Math.floor(lo / step + 1e-9) * step;
  const max = Math.ceil(hi / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let k = 1; min + k * step <= max + 1e-9; k++) ticks.push(Number((min + k * step).toFixed(6)));
  return { min, max, ticks };
}

export function frameFor(width: number): Frame {
  return { ...FRAME, width, height: Math.min(Math.max(Math.round(width * 0.45), 190), 300) };
}

/** `view` is in indices of `points`; points outside it land left or right of the plot. */
export function scales(points: ChartPoint[], frame: Frame, view?: ChartWindow): Scales {
  const { min, max, ticks } = yDomain(points);
  const plotWidth = frame.width - frame.left - frame.right;
  const plotHeight = frame.height - frame.top - frame.bottom;
  const from = view?.from ?? 0;
  const span = (view ? view.to - view.from : points.length - 1) || 1;
  return {
    x: (i) => frame.left + ((i - from) / span) * plotWidth,
    y: (v) => frame.top + (1 - (v - min) / (max - min)) * plotHeight,
    min, max, ticks,
  };
}

export function linePath(points: ChartPoint[], s: Scales): string {
  return points.map((p, i) => `${i ? "L" : "M"}${f(s.x(i))},${f(s.y(p.value))}`).join("");
}

/** Capital changes in one jump on the day of a deposit: across first, then up or down. */
export function stairPath(points: ChartPoint[], s: Scales): string {
  return points.map((p, i) => (i ? `H${f(s.x(i))}V${f(s.y(p.invested))}` : `M${f(s.x(0))},${f(s.y(p.invested))}`)).join("");
}

/** The field between the value line and the capital steps (gain where above, loss where below). */
export function gapPath(points: ChartPoint[], s: Scales): string {
  const last = points.length - 1;
  let path = `${linePath(points, s)}L${f(s.x(last))},${f(s.y(points[last]!.invested))}`;
  for (let i = last; i >= 1; i--) path += `V${f(s.y(points[i - 1]!.invested))}H${f(s.x(i - 1))}`;
  return `${path}Z`;
}

export function clipAbove(points: ChartPoint[], s: Scales, frame: Frame): string {
  return `${stairPath(points, s)}V${f(frame.top)}H${f(s.x(0))}Z`;
}

export function clipBelow(points: ChartPoint[], s: Scales, frame: Frame): string {
  return `${stairPath(points, s)}V${f(frame.height - frame.bottom)}H${f(s.x(0))}Z`;
}

export function depositMarks(points: ChartPoint[]): { index: number; large: boolean }[] {
  const deposits = points.map((p, index) => ({ index, flow: p.flow })).filter((d) => d.flow > 0);
  const sorted = deposits.map((d) => d.flow).sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 ? sorted[mid]! : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
  return deposits.map((d) => ({ index: d.index, large: d.flow > median }));
}

export function indexAt(px: number, view: ChartWindow, frame: Frame, count: number): number {
  const plotWidth = frame.width - frame.left - frame.right;
  const index = Math.round(view.from + ((px - frame.left) / plotWidth) * (view.to - view.from));
  return Math.min(Math.max(index, Math.ceil(view.from - 1e-9), 0), Math.floor(view.to + 1e-9), count - 1);
}

export function axisLabel(value: number): string {
  const decimal = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1).replace(".", ","));
  if (Math.abs(value) >= 1_000_000) return `${decimal(value / 1_000_000)} mln`;
  if (Math.abs(value) >= 1_000) return `${decimal(value / 1_000)} tys.`;
  return String(Math.round(value));
}
