# Chart Zoom and Readable Axes Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The Pulpit value chart zooms (Ctrl + wheel, drag, two fingers, double click resets), its X axis labels adapt to the visible period down to single days, and axis text keeps a fixed pixel size.

**Architecture:** The dashboard fetches the whole history once; range buttons only choose a visible window `{from, to}` in fractional point indices. Pure modules compute the window (`viewport.ts`) and the X labels (`timeTicks.ts`); a hook (`useChartGestures.ts`) turns wheel/pointer input into new windows; `ValueChart` measures its width and draws in real pixels.

**Tech Stack:** React 19, TypeScript, Vitest + Testing Library (jsdom), CSS modules, inline SVG.

**Spec:** `docs/superpowers/specs/2026-09-30-chart-zoom-design.md`

## Global Constraints

- Only `web/` changes; the API stays as is.
- Zoom on desktop only with Ctrl + wheel; plain wheel scrolls the page and shows „Ctrl + kółko przybliża” for 1.5 s.
- Phone: two fingers zoom and pan; one finger keeps the day readout and vertical page scroll (`touch-action: pan-y` stays).
- The window is at least 7 days (or the whole history when shorter) and never leaves the history.
- History points are daily (checked on the owner's data 2026-09-30: 36 days → 36 points per series), so one index = one day.
- Axis text 11 px on every screen; the SVG `viewBox` width equals the measured width.
- UI copy in Polish; code, comments and commits in English, as in the rest of `web/`.
- Commits end with `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.

## Review Focus

- A click without moving the mouse must not count as a zoom (range button must stay highlighted) — test in Task 4.
- History shorter than 7 days (e.g. 2 points): window = whole history, no crash, zoom does nothing — tests in Tasks 1 and 4.
- Switching accounts while zoomed: the stale window must be clamped to the new history and the zoom reset — clamp in Task 3, reset in Task 5.
- The last X label at the right edge must not be dropped when it fits under the Y labels (the “30” in a 7-day window) — test in Task 2.
- Range buttons must not trigger a new history request — test in Task 5.

---

### Task 1: Visible window model (`viewport.ts`)

**Files:**
- Create: `web/src/charts/viewport.ts`
- Test: `web/src/charts/viewport.test.ts`

**Interfaces:**
- Produces:
  - `interface ChartWindow { from: number; to: number }` (fractional point indices, `to` included)
  - `const MIN_DAYS = 7`
  - `fullWindow(count: number): ChartWindow`
  - `clampWindow(view: ChartWindow, count: number): ChartWindow`
  - `windowForRange(dates: string[], fromDate: string | null): ChartWindow`
  - `moveWindow(view: ChartWindow, fromFrac: number, toFrac: number, factor: number, count: number): ChartWindow` — the day at `fromFrac` of the plot width moves under `toFrac`, the span is multiplied by `factor` (wheel: same frac; drag: factor 1; pinch: both)
  - `drawnRange(view: ChartWindow, count: number): { start: number; end: number }` — visible indices plus one on each side

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import { clampWindow, drawnRange, fullWindow, moveWindow, windowForRange, type ChartWindow } from "./viewport";

const days = (count: number, start = "2026-09-01") =>
  Array.from({ length: count }, (_, i) => new Date(Date.parse(`${start}T00:00:00Z`) + i * 86_400_000).toISOString().slice(0, 10));
const near = (view: ChartWindow) => ({ from: Number(view.from.toFixed(6)), to: Number(view.to.toFixed(6)) });

describe("chart window", () => {
  it("shows a range from its first day to the last day", () => {
    expect(windowForRange(days(30), "2026-09-10")).toEqual({ from: 9, to: 29 });
    expect(windowForRange(days(30), null)).toEqual({ from: 0, to: 29 });
  });

  it("keeps at least seven days, or the whole history when it is shorter", () => {
    expect(windowForRange(days(30), "2026-09-28")).toEqual({ from: 23, to: 29 });
    expect(windowForRange(days(3), null)).toEqual({ from: 0, to: 2 });
    expect(clampWindow({ from: 0.5, to: 0.7 }, 2)).toEqual({ from: 0, to: 1 });
    expect(fullWindow(30)).toEqual({ from: 0, to: 29 });
  });

  it("zooms around the day under the pointer", () => {
    expect(near(moveWindow({ from: 0, to: 29 }, 0.5, 0.5, 0.5, 30))).toEqual({ from: 7.25, to: 21.75 });
    expect(near(moveWindow({ from: 0, to: 29 }, 0.5, 0.5, 0.01, 30))).toEqual({ from: 11.5, to: 17.5 });
    expect(near(moveWindow({ from: 10, to: 20 }, 0.5, 0.5, 10, 30))).toEqual({ from: 0, to: 29 });
  });

  it("pans without leaving the history", () => {
    expect(near(moveWindow({ from: 10, to: 20 }, 0.5, 0.6, 1, 30))).toEqual({ from: 9, to: 19 });
    expect(near(moveWindow({ from: 0, to: 10 }, 0.2, 0.9, 1, 30))).toEqual({ from: 0, to: 10 });
    expect(near(moveWindow({ from: 19, to: 29 }, 0.8, 0.1, 1, 30))).toEqual({ from: 19, to: 29 });
  });

  it("draws one point beyond each edge", () => {
    expect(drawnRange({ from: 7.25, to: 21.75 }, 30)).toEqual({ start: 7, end: 22 });
    expect(drawnRange({ from: 0, to: 29 }, 30)).toEqual({ start: 0, end: 29 });
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run (in `web/`): `npx vitest run src/charts/viewport.test.ts`
Expected: FAIL — cannot resolve `./viewport`.

- [ ] **Step 3: Write the implementation**

```ts
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
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/charts/viewport.test.ts`
Expected: PASS (5 tests).

- [ ] **Step 5: Commit**

```bash
git add web/src/charts/viewport.ts web/src/charts/viewport.test.ts
git commit -m "feat(web): chart window model for zoom and pan"
```

---

### Task 2: X axis labels (`timeTicks.ts`)

**Files:**
- Create: `web/src/charts/timeTicks.ts`
- Test: `web/src/charts/timeTicks.test.ts`

**Interfaces:**
- Consumes: `ChartWindow` (Task 1), `ChartPoint` from `./geometry` (`{ date: string; value: number; invested: number; flow: number }`), `monthShort(iso)` from `../format` (e.g. `"wrz"`).
- Produces: `interface TimeTick { index: number; label: string; strong: boolean }`, `timeTicks(points: ChartPoint[], view: ChartWindow, plotWidth: number): TimeTick[]`, `const OVERHANG_PX = 40`.

Rules (spec section 2): steps from finest — 1 day, 2 days, week (Mondays), 1/2/3/6 months, 1/2/5 years — pick the first whose shortest period in px fits its widest label (`chars × 6.5 px + 8 px`). A tick sits on the first visible point of each new period. Day/week labels: day number, with the month when it differs from the previous label (`1 paź`, strong) and on the first label (`22 wrz`, not strong). Month labels: January → year (strong), first label → `lip 2025`, others `kwi`. Year labels: `2025`. A label may reach `OVERHANG_PX` past the plot's right edge (the free space under the Y labels).

- [ ] **Step 1: Write the failing test**

```ts
import { describe, expect, it } from "vitest";
import type { ChartPoint } from "./geometry";
import { timeTicks } from "./timeTicks";

function daily(from: string, to: string): ChartPoint[] {
  const points: ChartPoint[] = [];
  for (let t = Date.parse(`${from}T00:00:00Z`); t <= Date.parse(`${to}T00:00:00Z`); t += 86_400_000) {
    points.push({ date: new Date(t).toISOString().slice(0, 10), value: 1, invested: 1, flow: 0 });
  }
  return points;
}
const labels = (ticks: { label: string }[]) => ticks.map((t) => t.label);

describe("timeTicks", () => {
  it("labels every day of a week, with the month where it changes", () => {
    const points = daily("2026-09-01", "2026-10-10");
    const ticks = timeTicks(points, { from: 27, to: 33 }, 306);
    expect(labels(ticks)).toEqual(["28 wrz", "29", "30", "1 paź", "2", "3", "4"]);
    expect(ticks.filter((t) => t.strong).map((t) => t.label)).toEqual(["1 paź"]);
  });

  it("keeps the last day at the right edge", () => {
    const points = daily("2026-09-01", "2026-09-30");
    expect(labels(timeTicks(points, { from: 23, to: 29 }, 306)).at(-1)).toBe("30");
  });

  it("labels Mondays across a month", () => {
    const points = daily("2026-09-01", "2026-09-30");
    const ticks = timeTicks(points, { from: 0, to: 29 }, 306);
    expect(labels(ticks)).toEqual(["7 wrz", "14", "21", "28"]);
    expect(ticks.map((t) => t.index)).toEqual([6, 13, 20, 27]);
  });

  it("labels quarters over a year, the new year in bold", () => {
    const points = daily("2025-07-01", "2026-06-30");
    const ticks = timeTicks(points, { from: 0, to: points.length - 1 }, 306);
    expect(labels(ticks)).toEqual(["lip 2025", "paź", "2026", "kwi"]);
    expect(ticks.map((t) => t.strong)).toEqual([false, false, true, false]);
  });

  it("labels only years over several years", () => {
    const points = daily("2022-01-01", "2026-09-30");
    expect(labels(timeTicks(points, { from: 0, to: points.length - 1 }, 306))).toEqual(["2022", "2023", "2024", "2025", "2026"]);
  });

  it("takes a longer step when the chart is narrow", () => {
    const points = daily("2026-09-01", "2026-09-30");
    expect(labels(timeTicks(points, { from: 0, to: 29 }, 150))).toEqual(["wrz 2026"]);
  });

  it("gives more labels on a wide chart", () => {
    const points = daily("2026-09-01", "2026-09-30");
    expect(timeTicks(points, { from: 0, to: 29 }, 1400)).toHaveLength(30);
  });
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npx vitest run src/charts/timeTicks.test.ts`
Expected: FAIL — cannot resolve `./timeTicks`.

- [ ] **Step 3: Write the implementation**

```ts
/** Calendar labels for the value chart's X axis, chosen for the visible window and the plot width. */
import { monthShort } from "../format";
import type { ChartPoint } from "./geometry";
import type { ChartWindow } from "./viewport";

export interface TimeTick { index: number; label: string; strong: boolean }

const CHAR_PX = 6.5;
const GAP_PX = 8;
/** Labels may run past the plot into the free space under the Y axis labels. */
export const OVERHANG_PX = 40;
const DAY_MS = 86_400_000;

type Unit = "day" | "week" | "month" | "year";
interface Step { unit: Unit; every: number; minDays: number; chars: number }

const STEPS: Step[] = [
  { unit: "day", every: 1, minDays: 1, chars: 6 },
  { unit: "day", every: 2, minDays: 2, chars: 6 },
  { unit: "week", every: 1, minDays: 7, chars: 6 },
  { unit: "month", every: 1, minDays: 28, chars: 8 },
  { unit: "month", every: 2, minDays: 59, chars: 8 },
  { unit: "month", every: 3, minDays: 90, chars: 8 },
  { unit: "month", every: 6, minDays: 181, chars: 8 },
  { unit: "year", every: 1, minDays: 365, chars: 4 },
  { unit: "year", every: 2, minDays: 730, chars: 4 },
  { unit: "year", every: 5, minDays: 1826, chars: 4 },
];

const dayNumber = (iso: string) => Math.round(Date.parse(`${iso.slice(0, 10)}T00:00:00Z`) / DAY_MS);

function periodKey(step: Step, day: number): number {
  if (step.unit === "day") return Math.floor(day / step.every);
  if (step.unit === "week") return Math.floor((day + 3) / 7); // day 0 (1970-01-01) was a Thursday; weeks start on Monday
  const date = new Date(day * DAY_MS);
  if (step.unit === "month") return Math.floor((date.getUTCFullYear() * 12 + date.getUTCMonth()) / step.every);
  return Math.floor(date.getUTCFullYear() / step.every);
}

function labelFor(step: Step, iso: string, previous: string | null): { label: string; strong: boolean } {
  const year = iso.slice(0, 4);
  if (step.unit === "day" || step.unit === "week") {
    const newMonth = previous === null || previous.slice(0, 7) !== iso.slice(0, 7);
    const day = String(Number(iso.slice(8, 10)));
    return { label: newMonth ? `${day} ${monthShort(iso)}` : day, strong: newMonth && previous !== null };
  }
  if (step.unit === "month") {
    if (iso.slice(5, 7) === "01") return { label: year, strong: true };
    return { label: previous === null ? `${monthShort(iso)} ${year}` : monthShort(iso), strong: false };
  }
  return { label: year, strong: false };
}

export function timeTicks(points: ChartPoint[], view: ChartWindow, plotWidth: number): TimeTick[] {
  const span = view.to - view.from;
  if (points.length < 2 || span <= 0) return [];
  const pxPerDay = plotWidth / span;
  const step = STEPS.find((s) => s.minDays * pxPerDay >= s.chars * CHAR_PX + GAP_PX) ?? STEPS[STEPS.length - 1]!;
  const first = Math.max(Math.ceil(view.from - 1e-9), 0);
  const last = Math.min(Math.floor(view.to + 1e-9), points.length - 1);
  const ticks: TimeTick[] = [];
  let previous: string | null = null;
  for (let i = first; i <= last; i++) {
    const date = points[i]!.date;
    const day = dayNumber(date);
    const before = i === 0 ? day - 1 : dayNumber(points[i - 1]!.date);
    if (periodKey(step, day) === periodKey(step, before)) continue;
    const text = labelFor(step, date, previous);
    if ((i - view.from) * pxPerDay + 3 + text.label.length * CHAR_PX > plotWidth + OVERHANG_PX) continue;
    ticks.push({ index: i, ...text });
    previous = date;
  }
  return ticks;
}
```

- [ ] **Step 4: Run test to verify it passes**

Run: `npx vitest run src/charts/timeTicks.test.ts`
Expected: PASS (7 tests). If an expectation fails, check the arithmetic in the test comment against the rule before changing code: 7 days at 306 px → 51 px/day ≥ 47 (1-day step); 30 days at 306 px → 10.6 px/day, week 73.9 ≥ 47; 1 year → quarter 75.7 ≥ 60 while 2 months 49.6 < 60; 30 days at 150 px → week 36 < 47, month 145 ≥ 60; 30 days at 1400 px → 48 px/day ≥ 47.

- [ ] **Step 5: Commit**

```bash
git add web/src/charts/timeTicks.ts web/src/charts/timeTicks.test.ts
git commit -m "feat(web): calendar X axis labels that follow the visible period"
```

---

### Task 3: Chart draws a window at real pixel size

**Files:**
- Modify: `web/src/charts/geometry.ts` (`scales`, replace `nearestIndex` with `indexAt`, remove `monthTicks`, add `frameFor`)
- Modify: `web/src/charts/ValueChart.tsx`, `web/src/charts/ValueChart.module.css`
- Test: `web/src/charts/geometry.test.ts`, `web/src/charts/ValueChart.test.tsx`

**Interfaces:**
- Consumes: `ChartWindow`, `clampWindow`, `fullWindow`, `drawnRange` (Task 1); `timeTicks` (Task 2).
- Produces:
  - `scales(points: ChartPoint[], frame: Frame, view?: ChartWindow): Scales` — `view` in indices of `points` (default whole array).
  - `frameFor(width: number): Frame` — `FRAME` with the given width and height `clamp(round(width × 0.45), 190, 300)`.
  - `indexAt(px: number, view: ChartWindow, frame: Frame, count: number): number`
  - `ValueChart` props: `{ points: HistoryPoint[]; view?: ChartWindow; onViewChange?: (view: ChartWindow) => void; onReset?: () => void }` (the two callbacks are used from Task 4).

- [ ] **Step 1: Update the geometry tests (failing)**

In `web/src/charts/geometry.test.ts`: import `frameFor, indexAt` instead of `monthTicks, nearestIndex`; delete the test "labels up to four month starts spread over the range"; replace "finds the day under the finger" and add a window test:

```ts
  it("finds the day under the finger in the visible window", () => {
    expect([0, 49, 80, 500].map((px) => indexAt(px, { from: 0, to: 2 }, BOX, 3))).toEqual([0, 1, 2, 2]);
    expect([0, 50, 100].map((px) => indexAt(px, { from: 10, to: 20 }, BOX, 30))).toEqual([10, 15, 20]);
  });

  it("sizes the frame to the measured width", () => {
    expect([frameFor(350), frameFor(700), frameFor(1200)].map((f) => [f.width, f.height])).toEqual([[350, 190], [700, 300], [1200, 300]]);
  });
```

and in `describe("paths")` add:

```ts
  it("stretches the visible window over the whole plot", () => {
    const zoomed = scales(POINTS, BOX, { from: 1, to: 2 });
    expect([zoomed.x(0), zoomed.x(1), zoomed.x(2)]).toEqual([-100, 0, 100]);
  });
```

Run: `npx vitest run src/charts/geometry.test.ts` — Expected: FAIL (`indexAt`/`frameFor` not exported).

- [ ] **Step 2: Change `geometry.ts`**

Replace `scales`, `monthTicks` and `nearestIndex` (keep everything else) with:

```ts
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

export function indexAt(px: number, view: ChartWindow, frame: Frame, count: number): number {
  const plotWidth = frame.width - frame.left - frame.right;
  const index = Math.round(view.from + ((px - frame.left) / plotWidth) * (view.to - view.from));
  return Math.min(Math.max(index, Math.ceil(view.from - 1e-9), 0), Math.floor(view.to + 1e-9), count - 1);
}
```

Add `import type { ChartWindow } from "./viewport";` and remove the now unused `monthShort` import. `|| 1` keeps the old guard against dividing by zero for a one-point array.

Run: `npx vitest run src/charts/geometry.test.ts` — Expected: PASS.

- [ ] **Step 3: Update the ValueChart tests (failing)**

In `web/src/charts/ValueChart.test.tsx` add a 30-day fixture and two tests:

```ts
const MONTH = Array.from({ length: 30 }, (_, i) =>
  point(`2026-09-${String(i + 1).padStart(2, "0")}`, `${1000 + i * 10}.00`, "1000.00", i === 0 ? "1000.00" : "0.00"));

  it("draws only the visible window and names it", () => {
    render(<ValueChart points={MONTH} view={{ from: 23, to: 29 }} />);
    expect(screen.getByRole("img", { name: "Wykres wartości portfela od 24.09.2026 do 30.09.2026" })).toBeInTheDocument();
    expect(screen.getByText("24 wrz")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
  });

  it("clamps a window that no longer fits the history", () => {
    render(<ValueChart points={TWO} view={{ from: 20, to: 29 }} />);
    expect(screen.getByRole("img", { name: "Wykres wartości portfela od 01.09.2026 do 26.09.2026" })).toBeInTheDocument();
  });
```

Run: `npx vitest run src/charts/ValueChart.test.tsx` — Expected: FAIL (no `view` prop, no day labels).

- [ ] **Step 4: Rewrite `ValueChart.tsx`**

```tsx
import { useEffect, useId, useMemo, useState, type PointerEvent } from "react";
import type { HistoryPoint } from "../api/types";
import { formatDate, formatMoney } from "../format";
import {
  FRAME, axisLabel, clipAbove, clipBelow, depositMarks, frameFor, gapPath, indexAt, linePath, scales, stairPath,
  toChartPoints,
} from "./geometry";
import { timeTicks } from "./timeTicks";
import { clampWindow, drawnRange, fullWindow, type ChartWindow } from "./viewport";
import styles from "./ValueChart.module.css";

/** Follows the element's width; jsdom has no ResizeObserver, so tests draw at FRAME.width. */
function useWidth(element: HTMLElement | null): number {
  const [width, setWidth] = useState(FRAME.width);
  useEffect(() => {
    if (!element || typeof ResizeObserver === "undefined") return;
    const observer = new ResizeObserver(([entry]) => {
      const measured = Math.round(entry!.contentRect.width);
      if (measured > 0) setWidth(measured);
    });
    observer.observe(element);
    return () => observer.disconnect();
  }, [element]);
  return width;
}

export function ValueChart({ points, view: requested, onViewChange, onReset }: {
  points: HistoryPoint[];
  view?: ChartWindow;
  onViewChange?: (view: ChartWindow) => void;
  onReset?: () => void;
}) {
  const data = useMemo(() => toChartPoints(points), [points]);
  const marks = useMemo(() => depositMarks(data), [data]);
  const [active, setActive] = useState<number | null>(null);
  const [figure, setFigure] = useState<HTMLElement | null>(null);
  const width = useWidth(figure);
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");

  if (data.length < 2) {
    return <p className={styles.note}>Wykres pojawi się, gdy wycena obejmie co najmniej dwa dni.</p>;
  }

  const frame = frameFor(width);
  const view = clampWindow(requested ?? fullWindow(data.length), data.length);
  const { start, end } = drawnRange(view, data.length);
  const drawn = data.slice(start, end + 1);
  const s = scales(drawn, frame, { from: view.from - start, to: view.to - start });
  const x = (index: number) => s.x(index - start);
  const last = data.length - 1;
  const firstShown = Math.ceil(view.from - 1e-9);
  const lastShown = Math.floor(view.to + 1e-9);
  const baseline = frame.height - frame.bottom;
  const plotRight = frame.width - frame.right;
  const shown = active === null ? null : points[active]!;
  const gap = gapPath(drawn, s);
  const ticks = timeTicks(data, view, plotRight - frame.left);

  function track(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    setActive(indexAt(((event.clientX - rect.left) / rect.width) * frame.width, view, frame, data.length));
  }

  return (
    <figure className={styles.chart} ref={setFigure}>
      <div className={styles.readout} aria-live="polite">
        {shown ? (
          <>
            <span className={styles.day}>{formatDate(shown.date)}</span>
            <span className="num">Wartość {formatMoney(shown.value_pln)}</span>
            <span className="num">Wpłacono {formatMoney(shown.invested_pln)}</span>
          </>
        ) : (
          <>
            <span className={styles.key}><i className={styles.swValue} />Wartość</span>
            <span className={styles.key}><i className={styles.swCapital} />Wpłacony kapitał</span>
            <span className={styles.key}><i className={styles.swDeposit} />Wpłata</span>
          </>
        )}
      </div>
      <svg
        className={styles.svg}
        viewBox={`0 0 ${frame.width} ${frame.height}`}
        role="img"
        aria-label={`Wykres wartości portfela od ${formatDate(points[firstShown]!.date)} do ${formatDate(points[lastShown]!.date)}`}
        onPointerMove={track}
        onPointerDown={track}
        onPointerLeave={() => setActive(null)}
      >
        <defs>
          <clipPath id={`plot-${id}`}><rect x={frame.left} y={0} width={plotRight - frame.left} height={frame.height} /></clipPath>
          <clipPath id={`above-${id}`}><path d={clipAbove(drawn, s, frame)} /></clipPath>
          <clipPath id={`below-${id}`}><path d={clipBelow(drawn, s, frame)} /></clipPath>
        </defs>
        {s.ticks.map((tick) => (
          <g key={tick}>
            <line x1={frame.left} x2={plotRight} y1={s.y(tick)} y2={s.y(tick)} className={styles.grid} />
            <text x={plotRight + 6} y={s.y(tick) + 4} className={styles.axis}>{axisLabel(tick)}</text>
          </g>
        ))}
        {ticks.map((tick) => (
          <g key={tick.index}>
            <line x1={x(tick.index)} x2={x(tick.index)} y1={frame.top} y2={baseline} className={styles.grid} />
            <text x={x(tick.index) + 3} y={frame.height - 4} className={tick.strong ? styles.axisStrong : styles.axis}>{tick.label}</text>
          </g>
        ))}
        <g clipPath={`url(#plot-${id})`}>
          {marks.filter((mark) => mark.index >= start && mark.index <= end).map((mark) => (
            <line key={mark.index} x1={x(mark.index)} x2={x(mark.index)} y1={baseline + 2}
              y2={baseline + (mark.large ? 12 : 7)} className={styles.deposit} />
          ))}
          <path d={gap} fill="var(--amber-soft)" clipPath={`url(#above-${id})`} />
          <path d={gap} fill="var(--loss-soft)" clipPath={`url(#below-${id})`} />
          <path d={stairPath(drawn, s)} className={styles.capital} />
          <path d={linePath(drawn, s)} className={styles.value} pathLength={1} />
        </g>
        {active !== null && <line x1={x(active)} x2={x(active)} y1={frame.top} y2={baseline} className={styles.cursor} />}
        {lastShown === last && (
          <>
            <circle cx={x(last)} cy={s.y(data[last]!.value)} r={4} fill="var(--amber)" />
            <circle cx={x(last)} cy={s.y(data[last]!.value)} r={8} fill="var(--amber)" opacity={0.18} />
          </>
        )}
      </svg>
    </figure>
  );
}
```

`onViewChange` and `onReset` are used from Task 4; in this task leave them out of the destructuring (`{ points, view: requested }`) so `noUnusedLocals` does not complain — they stay in the props type.

Note: the `.value` draw animation runs when the path element is created, so it plays once on first display and not on zoom (the element is reused).

- [ ] **Step 5: CSS — fixed text size and strong labels**

In `web/src/charts/ValueChart.module.css` change `.axis` to 11px and add `.axisStrong`:

```css
.axis { fill: var(--dim); font-size: 11px; font-variant-numeric: tabular-nums; }
.axisStrong { fill: var(--ink); font-size: 11px; font-weight: 600; font-variant-numeric: tabular-nums; }
```

- [ ] **Step 6: Run the chart tests and the type check**

Run: `npx vitest run src/charts` then `npx tsc --noEmit`
Expected: all PASS, no type errors. The existing test "shows the day under the pointer" still passes (width 350 → pointer 300 px → index 1 of 2 points).

- [ ] **Step 7: Commit**

```bash
git add web/src/charts
git commit -m "feat(web): value chart draws a window at real pixel size with calendar labels"
```

---

### Task 4: Gestures (`useChartGestures.ts`)

**Files:**
- Create: `web/src/charts/useChartGestures.ts`
- Modify: `web/src/charts/ValueChart.tsx`, `web/src/charts/ValueChart.module.css`
- Test: `web/src/charts/ValueChart.test.tsx`

**Interfaces:**
- Consumes: `moveWindow`, `ChartWindow` (Task 1); `Frame` (geometry).
- Produces: `useChartGestures(options: { view: ChartWindow; count: number; frame: Frame; onChange(view: ChartWindow): void; onReset(): void })` returning `{ ref: (svg: SVGSVGElement | null) => void; hint: boolean; onPointerDown(e): boolean; onPointerMove(e): boolean; onPointerUp(e): void; onDoubleClick(): void }`. `onPointerDown/Move` return `true` when the event belongs to a drag or pinch (then the chart does not update the day readout).

- [ ] **Step 1: Write the failing tests**

Add to `web/src/charts/ValueChart.test.tsx`:

```ts
  const rect = { left: 0, width: 350, top: 0, height: 190 } as DOMRect;

  it("zooms with Ctrl and the wheel around the pointer", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={MONTH} onViewChange={onViewChange} />);
    const svg = screen.getByRole("img");
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue(rect);

    fireEvent.wheel(svg, { ctrlKey: true, deltaY: -200, clientX: 153 });

    const view = onViewChange.mock.calls[0]![0] as { from: number; to: number };
    expect(view.to - view.from).toBeLessThan(29);
    expect(view.from).toBeGreaterThan(0);
    expect(view.to).toBeLessThan(29);
  });

  it("scrolls the page on a plain wheel and says how to zoom", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={MONTH} onViewChange={onViewChange} />);

    fireEvent.wheel(screen.getByRole("img"), { deltaY: 100 });

    expect(onViewChange).not.toHaveBeenCalled();
    expect(screen.getByText("Ctrl + kółko przybliża")).toBeInTheDocument();
  });

  it("goes back to the range on a double click", () => {
    const onReset = vi.fn();
    render(<ValueChart points={MONTH} view={{ from: 10, to: 20 }} onReset={onReset} />);

    fireEvent.doubleClick(screen.getByRole("img"));

    expect(onReset).toHaveBeenCalledOnce();
  });

  it("pans when the mouse drags, but a plain click does not change the window", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={MONTH} view={{ from: 10, to: 20 }} onViewChange={onViewChange} />);
    const svg = screen.getByRole("img");
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue(rect);

    fireEvent.pointerDown(svg, { pointerId: 1, pointerType: "mouse", button: 0, clientX: 150 });
    fireEvent.pointerMove(svg, { pointerId: 1, pointerType: "mouse", clientX: 151 });
    fireEvent.pointerUp(svg, { pointerId: 1, pointerType: "mouse", clientX: 151 });
    expect(onViewChange).not.toHaveBeenCalled();

    fireEvent.pointerDown(svg, { pointerId: 1, pointerType: "mouse", button: 0, clientX: 150 });
    fireEvent.pointerMove(svg, { pointerId: 1, pointerType: "mouse", clientX: 200 });
    const view = onViewChange.mock.calls.at(-1)![0] as { from: number; to: number };
    expect(view.from).toBeLessThan(10);
  });

  it("does nothing on a history shorter than a week", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={TWO} onViewChange={onViewChange} />);
    fireEvent.wheel(screen.getByRole("img"), { ctrlKey: true, deltaY: -200, clientX: 150 });
    expect(onViewChange.mock.calls.every(([view]) => view.from === 0 && view.to === 1)).toBe(true);
  });
```

If jsdom drops `pointerId`/`pointerType` from `fireEvent.pointerDown` (older jsdom without `PointerEvent`), add at the top of the test file:

```ts
if (!("PointerEvent" in window)) {
  class PointerEventPolyfill extends MouseEvent {
    pointerId: number; pointerType: string;
    constructor(type: string, init: PointerEventInit = {}) { super(type, init); this.pointerId = init.pointerId ?? 0; this.pointerType = init.pointerType ?? "mouse"; }
  }
  (window as unknown as { PointerEvent: unknown }).PointerEvent = PointerEventPolyfill;
}
```

Run: `npx vitest run src/charts/ValueChart.test.tsx` — Expected: FAIL (no zoom, no hint).

- [ ] **Step 2: Write the hook**

```ts
import { useEffect, useRef, useState, type PointerEvent } from "react";
import type { Frame } from "./geometry";
import { moveWindow, type ChartWindow } from "./viewport";

const HINT_MS = 1500;
const WHEEL_SPEED = 0.0015;
const DRAG_START_PX = 3;
const TAP_MS = 300;
const TAP_MOVE_PX = 10;

interface Options { view: ChartWindow; count: number; frame: Frame; onChange(view: ChartWindow): void; onReset(): void }
interface Gesture { kind: "drag" | "pinch"; view: ChartWindow; frac: number; dist: number; startX: number; moved: boolean }
interface Touch { time: number; x: number; y: number }

/** Share of the plot width under `clientX`, 0 at the left edge, 1 at the right. */
function fracAt(target: Element, clientX: number, frame: Frame): number {
  const rect = target.getBoundingClientRect();
  if (!rect.width) return 0.5;
  const px = ((clientX - rect.left) / rect.width) * frame.width;
  return Math.min(Math.max((px - frame.left) / (frame.width - frame.left - frame.right), 0), 1);
}

/** Ctrl + wheel and pinch zoom, mouse drag and two-finger pan, double click or tap resets. */
export function useChartGestures(options: Options) {
  const latest = useRef(options);
  latest.current = options;
  const [svg, setSvg] = useState<SVGSVGElement | null>(null);
  const [hint, setHint] = useState(false);
  const pointers = useRef(new Map<number, { x: number; y: number }>());
  const gesture = useRef<Gesture | null>(null);
  const down = useRef<Touch | null>(null);
  const lastTap = useRef<Touch | null>(null);

  // React's onWheel is passive, so preventDefault (stop the page scrolling while zooming) needs a native listener.
  useEffect(() => {
    if (!svg) return;
    let timer: number | undefined;
    function onWheel(event: WheelEvent) {
      if (!event.ctrlKey) {
        setHint(true);
        window.clearTimeout(timer);
        timer = window.setTimeout(() => setHint(false), HINT_MS);
        return;
      }
      event.preventDefault();
      const { view, count, frame, onChange } = latest.current;
      const delta = event.deltaY * (event.deltaMode === 1 ? 16 : 1);
      const frac = fracAt(svg!, event.clientX, frame);
      onChange(moveWindow(view, frac, frac, Math.exp(delta * WHEEL_SPEED), count));
    }
    svg.addEventListener("wheel", onWheel, { passive: false });
    return () => {
      svg.removeEventListener("wheel", onWheel);
      window.clearTimeout(timer);
    };
  }, [svg]);

  function onPointerDown(event: PointerEvent<SVGSVGElement>): boolean {
    const { view, frame } = latest.current;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    if (event.pointerType === "mouse") {
      if (event.button !== 0) return false;
      event.currentTarget.setPointerCapture?.(event.pointerId);
      gesture.current = { kind: "drag", view, frac: fracAt(event.currentTarget, event.clientX, frame), dist: 1, startX: event.clientX, moved: false };
      return false;
    }
    if (pointers.current.size === 2) {
      const [a, b] = [...pointers.current.values()] as [{ x: number; y: number }, { x: number; y: number }];
      gesture.current = {
        kind: "pinch", view, frac: fracAt(event.currentTarget, (a.x + b.x) / 2, frame),
        dist: Math.max(Math.hypot(a.x - b.x, a.y - b.y), 1), startX: (a.x + b.x) / 2, moved: true,
      };
      down.current = null;
      return true;
    }
    down.current = { time: event.timeStamp, x: event.clientX, y: event.clientY };
    return false;
  }

  function onPointerMove(event: PointerEvent<SVGSVGElement>): boolean {
    if (!pointers.current.has(event.pointerId)) return false;
    pointers.current.set(event.pointerId, { x: event.clientX, y: event.clientY });
    const current = gesture.current;
    if (!current) return false;
    const { count, frame, onChange } = latest.current;
    if (current.kind === "drag") {
      if (!current.moved && Math.abs(event.clientX - current.startX) < DRAG_START_PX) return false;
      current.moved = true;
      onChange(moveWindow(current.view, current.frac, fracAt(event.currentTarget, event.clientX, frame), 1, count));
      return true;
    }
    if (pointers.current.size < 2) return true;
    const [a, b] = [...pointers.current.values()] as [{ x: number; y: number }, { x: number; y: number }];
    const dist = Math.max(Math.hypot(a.x - b.x, a.y - b.y), 1);
    onChange(moveWindow(current.view, current.frac, fracAt(event.currentTarget, (a.x + b.x) / 2, frame), current.dist / dist, count));
    return true;
  }

  function onPointerUp(event: PointerEvent<SVGSVGElement>): void {
    pointers.current.delete(event.pointerId);
    gesture.current = null;
    const start = down.current;
    down.current = null;
    if (event.pointerType === "mouse" || event.type !== "pointerup" || !start) return;
    const isTap = event.timeStamp - start.time < TAP_MS && Math.hypot(event.clientX - start.x, event.clientY - start.y) < TAP_MOVE_PX;
    const previous = lastTap.current;
    if (isTap && previous && event.timeStamp - previous.time < TAP_MS && Math.hypot(event.clientX - previous.x, event.clientY - previous.y) < 30) {
      lastTap.current = null;
      latest.current.onReset();
      return;
    }
    lastTap.current = isTap ? { time: event.timeStamp, x: event.clientX, y: event.clientY } : null;
  }

  return { ref: setSvg, hint, onPointerDown, onPointerMove, onPointerUp, onDoubleClick: () => latest.current.onReset() };
}
```

- [ ] **Step 3: Wire it into `ValueChart.tsx`**

Add the import `import { useChartGestures } from "./useChartGestures";`. Call the hook **before** the `data.length < 2` early return (hooks must not be conditional), which means `frame` and `view` move above it too:

```tsx
  const frame = frameFor(width);
  const view = clampWindow(requested ?? fullWindow(data.length), data.length);
  const gestures = useChartGestures({
    view, count: data.length, frame,
    onChange: (next) => { setActive(null); onViewChange?.(next); },
    onReset: () => onReset?.(),
  });

  if (data.length < 2) { /* unchanged */ }
```

(delete the later `const frame`/`const view` lines). Change the `<figure>` and `<svg>`:

```tsx
    <figure className={styles.chart} ref={setFigure}>
      {gestures.hint && <p className={styles.hint} role="status">Ctrl + kółko przybliża</p>}
      ...
      <svg
        ref={gestures.ref}
        ...
        onPointerDown={(event) => { if (!gestures.onPointerDown(event)) track(event); }}
        onPointerMove={(event) => { if (!gestures.onPointerMove(event)) track(event); }}
        onPointerUp={gestures.onPointerUp}
        onPointerCancel={gestures.onPointerUp}
        onPointerLeave={() => setActive(null)}
        onDoubleClick={gestures.onDoubleClick}
      >
```

- [ ] **Step 4: CSS for the hint**

In `ValueChart.module.css`, `.chart` gets `position: relative;` and add:

```css
.hint {
  position: absolute; top: 56px; left: 50%; transform: translateX(-50%); z-index: 1; margin: 0; pointer-events: none;
  padding: 6px 12px; border-radius: var(--r-control); background: var(--slab); border: 1px solid var(--rule);
  color: var(--ink); font-size: 13px; white-space: nowrap;
}
```

- [ ] **Step 5: Run the tests and the type check**

Run: `npx vitest run src/charts` then `npx tsc --noEmit`
Expected: PASS, no type errors.

- [ ] **Step 6: Commit**

```bash
git add web/src/charts
git commit -m "feat(web): zoom the value chart with Ctrl + wheel, drag and two fingers"
```

---

### Task 5: Dashboard — history once, buttons set the window

**Files:**
- Modify: `web/src/screens/dashboard/DashboardScreen.tsx`
- Modify: `web/src/ui/Segmented.tsx` (`value: T | null`)
- Test: `web/src/screens/dashboard/dashboard.test.tsx`
- Modify: `docs/superpowers/plans/2026-09-26-00-roadmap.md`

**Interfaces:**
- Consumes: `ValueChart` props `view`, `onViewChange`, `onReset` (Tasks 3–4); `windowForRange`, `ChartWindow` (Task 1); `rangeFrom(range, asOf)` from `./model`.

- [ ] **Step 1: Write the failing tests**

In `dashboard.test.tsx` change the expectation in the account-selection test

```ts
    expect(urls.some((u) => u.startsWith("/api/portfolio/history?account_id=1&from=2025-09-26"))).toBe(true);
```

to

```ts
    expect(urls).toContain("/api/portfolio/history?account_id=1");
```

and add:

```ts
  it("changes the chart range without asking the API again", async () => {
    let histories = 0;
    mockFetch(routes({ history: () => { histories += 1; return HISTORY; } }));
    const { user } = renderApp("/");

    await screen.findByRole("img", { name: /Wykres wartości portfela/ });
    await user.click(screen.getByRole("button", { name: "1M" }));

    expect(screen.getByRole("button", { name: "1M" })).toHaveAttribute("aria-pressed", "true");
    expect(histories).toBe(1);
  });
```

Run: `npx vitest run src/screens/dashboard` — Expected: FAIL (URL has `from`, a second request is made).

- [ ] **Step 2: `Segmented` accepts no selection**

In `web/src/ui/Segmented.tsx` change the prop type `value: T` to `value: T | null` (no other change; `aria-pressed` is then false for every option).

- [ ] **Step 3: Dashboard state and query**

In `DashboardScreen.tsx`:

```tsx
import { useEffect, useMemo, useRef, useState } from "react";
import { windowForRange, type ChartWindow } from "../../charts/viewport";
```

After `const [mode, setMode] = ...` add `const [zoom, setZoom] = useState<ChartWindow | null>(null);`.

Replace the `from`/`history` lines with:

```tsx
  const history = useQuery({ queryKey: keys.history(accountIds, null), queryFn: () => api.history(accountIds, null), enabled: ready && asOf !== null, placeholderData: (previous) => previous });
  const dates = useMemo(() => (history.data?.points ?? []).map((p) => p.date), [history.data]);
  const rangeView = windowForRange(dates, rangeFrom(range, dates[dates.length - 1] ?? null));
  // Another account selection brings another history; a zoom into the old one means nothing there.
  const selectionKey = accountIds.join(",");
  useEffect(() => setZoom(null), [selectionKey]);
```

Replace the chart and the buttons:

```tsx
            : <ValueChart points={history.data.points} view={zoom ?? rangeView} onViewChange={setZoom} onReset={() => setZoom(null)} />}
        <Segmented label="Zakres wykresu" options={RANGES} value={zoom ? null : range}
          onChange={(next) => { setRange(next); setZoom(null); }} />
```

If `rangeFrom` is no longer imported elsewhere in the file it stays imported (it is used here). Remove nothing else.

- [ ] **Step 4: Run all web tests and the type check**

Run (in `web/`): `npm test` then `npx tsc --noEmit`
Expected: all PASS (before this plan: 217 tests).

- [ ] **Step 5: Roadmap**

In `docs/superpowers/plans/2026-09-26-00-roadmap.md` replace the bullet block „**Na później — wykres wartości: przybliżanie i czytelne osie …**” with:

```markdown
- **Zrobione 2026-09-30 — wykres wartości: przybliżanie i czytelne osie:** Ctrl + kółko (i szczypanie touchpada), przeciąganie myszą, dwa palce na telefonie, podwójne kliknięcie wraca do zakresu; minimum 7 dni; historia pobierana raz, przyciski ustawiają widoczne okno; oś X od dni po lata, tekst osi 11 px. Spec `specs/2026-09-30-chart-zoom-design.md`, plan `2026-09-30-chart-zoom.md`.
```

- [ ] **Step 6: Commit**

```bash
git add web/src docs/superpowers/plans/2026-09-26-00-roadmap.md
git commit -m "feat(web): Pulpit fetches the history once and range buttons set the chart window"
```

- [ ] **Step 7: Check in the browser**

With the dev server (http://localhost:5173) and the owner's account:
- desktop width: Ctrl + wheel zooms around the cursor, plain wheel scrolls and shows the hint, drag pans, double click returns to 1R, buttons highlight again, labels 11 px;
- 375 px width with touch emulation: one finger shows the day, the page scrolls vertically; 1M shows day labels; 7-day zoom labels every day;
- no horizontal page overflow at 320 px.
Report what was seen; fix and commit anything that is off.
