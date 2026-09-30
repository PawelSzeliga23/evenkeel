/** The visible part of the value chart, in fractional point indices (`to` included). One point is one day. */
export interface ChartWindow { from: number; to: number }

export const MIN_DAYS = 7;

const minSpan = (count: number) => Math.min(MIN_DAYS - 1, count - 1);

export function fullWindow(count: number): ChartWindow {
  return { from: 0, to: Math.max(count - 1, 0) };
}

/** At least MIN_DAYS wide (or the whole history), never outside the history. */
export function clampWindow(view: ChartWindow, count: number): ChartWindow {
  const last = Math.max(count - 1, 0);
  const span = Math.min(Math.max(view.to - view.from, minSpan(count), 0), last);
  const from = Math.min(Math.max(view.from, 0), last - span);
  return { from, to: from + span };
}

/** A range button's window: from the first day on or after `fromDate` to the last day. */
export function windowForRange(dates: string[], fromDate: string | null): ChartWindow {
  const start = fromDate === null ? 0 : dates.findIndex((date) => date >= fromDate);
  return clampWindow({ from: Math.max(start, 0), to: dates.length - 1 }, dates.length);
}

/** The day at `fromFrac` of the plot ends up under `toFrac`, and the window is `factor` times as wide. */
export function moveWindow(view: ChartWindow, fromFrac: number, toFrac: number, factor: number, count: number): ChartWindow {
  const span = view.to - view.from;
  const anchor = view.from + fromFrac * span;
  const next = Math.min(Math.max(span * factor, minSpan(count)), Math.max(count - 1, 0));
  const from = anchor - toFrac * next;
  return clampWindow({ from, to: from + next }, count);
}

/** Indices to draw: the visible ones plus one on each side, so the lines reach the plot edges. */
export function drawnRange(view: ChartWindow, count: number): { start: number; end: number } {
  return { start: Math.max(Math.ceil(view.from - 1e-9) - 1, 0), end: Math.min(Math.floor(view.to + 1e-9) + 1, count - 1) };
}
