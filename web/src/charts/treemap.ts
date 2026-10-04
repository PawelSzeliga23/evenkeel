import type { HoldingsPeriod, Money } from "../api/types";

export interface Rect { x: number; y: number; w: number; h: number }

/** The smallest share a value gets, so a tiny holding still has a tile to tap. */
const MIN_SHARE = 0.002;

/** The worst aspect ratio of a row of `areas` laid along a side of length `side`. */
function worst(areas: number[], side: number): number {
  if (areas.length === 0) return Infinity;
  const sum = areas.reduce((a, b) => a + b, 0);
  const max = Math.max(...areas);
  const min = Math.min(...areas);
  return Math.max((side * side * max) / (sum * sum), (sum * sum) / (side * side * min));
}

/**
 * Squarified treemap (Bruls, Huizing, van Wijk): rectangles with areas in proportion to `values`, as square as
 * possible, filling `width` × `height`. Returned in the input order.
 */
export function squarify(values: number[], width: number, height: number): Rect[] {
  if (values.length === 0) return [];
  const positive = values.map((v) => Math.max(v, 0));
  const floor = (positive.reduce((a, b) => a + b, 0) || 1) * MIN_SHARE;
  const kept = positive.map((v) => Math.max(v, floor));
  const scale = (width * height) / kept.reduce((a, b) => a + b, 0);
  const order = kept.map((_, i) => i).sort((a, b) => kept[b]! - kept[a]!);
  const out: Rect[] = new Array(values.length);
  let x = 0, y = 0, w = width, h = height;

  const place = (row: number[]) => {
    const areas = row.map((i) => kept[i]! * scale);
    const sum = areas.reduce((a, b) => a + b, 0);
    if (w >= h) {
      const columnWidth = sum / h;
      let top = y;
      row.forEach((i, k) => { const tall = areas[k]! / columnWidth; out[i] = { x, y: top, w: columnWidth, h: tall }; top += tall; });
      x += columnWidth;
      w -= columnWidth;
    } else {
      const rowHeight = sum / w;
      let left = x;
      row.forEach((i, k) => { const wide = areas[k]! / rowHeight; out[i] = { x: left, y, w: wide, h: rowHeight }; left += wide; });
      y += rowHeight;
      h -= rowHeight;
    }
  };

  let row: number[] = [];
  for (const i of order) {
    const side = Math.min(w, h);
    const current = row.map((k) => kept[k]! * scale);
    if (row.length === 0 || worst([...current, kept[i]! * scale], side) <= worst(current, side)) {
      row.push(i);
    } else {
      place(row);
      row = [i];
    }
  }
  place(row);
  return out;
}

/** Full colour at ± this gain % (owner's decision 7c). */
const SATURATION: Record<HoldingsPeriod, number> = { "1d": 3, "1w": 5, "1m": 10, "1y": 30, ytd: 30, all: 50 };
const MIN_ALPHA = 0.12;
const MAX_ALPHA = 0.7;

/** Green or red behind a tile, stronger with the size of the gain; the neutral slab at zero or without a percent. */
export function heatColor(pct: Money | null, period: HoldingsPeriod): string {
  const value = pct === null ? 0 : Number(pct);
  if (value === 0) return "var(--slab)";
  const strength = Math.min(Math.abs(value) / SATURATION[period], 1);
  const alpha = Math.round((MIN_ALPHA + strength * (MAX_ALPHA - MIN_ALPHA)) * 100) / 100;
  return `color-mix(in srgb, var(${value > 0 ? "--heat-gain" : "--heat-loss"}) ${Math.round(alpha * 100)}%, transparent)`;
}
