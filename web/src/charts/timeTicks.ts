/** Calendar labels for the value chart's X axis, chosen for the visible window and the plot width. */
import { monthShort } from "../format";
import type { ChartPoint } from "./geometry";
import type { ChartWindow } from "./viewport";

export interface TimeTick { index: number; label: string; strong: boolean }

/** Measured in the app's font at 11 px: about 6.6 px per character. */
const CHAR_PX = 6.6;
const GAP_PX = 8;
/** Labels may run past the plot into the free space under the Y axis labels. */
export const OVERHANG_PX = 40;
const DAY_MS = 86_400_000;

type Unit = "day" | "week" | "month" | "year";
/** `chars`: a typical label of the step ("18", "kwi", "2026"); longer ones that would overlap are skipped. */
interface Step { unit: Unit; every: number; minDays: number; chars: number }

const STEPS: Step[] = [
  { unit: "day", every: 1, minDays: 1, chars: 2 },
  { unit: "day", every: 2, minDays: 2, chars: 2 },
  { unit: "week", every: 1, minDays: 7, chars: 2 },
  { unit: "month", every: 1, minDays: 28, chars: 3 },
  { unit: "month", every: 2, minDays: 59, chars: 3 },
  { unit: "month", every: 3, minDays: 90, chars: 3 },
  { unit: "month", every: 6, minDays: 181, chars: 3 },
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
  let free = -Infinity; // first x where the next label may start
  for (let i = first; i <= last; i++) {
    const date = points[i]!.date;
    const day = dayNumber(date);
    const before = i === 0 ? day - 1 : dayNumber(points[i - 1]!.date);
    if (periodKey(step, day) === periodKey(step, before)) continue;
    const text = labelFor(step, date, previous);
    const x = (i - view.from) * pxPerDay;
    const width = text.label.length * CHAR_PX;
    if (x < free || x + 3 + width > plotWidth + OVERHANG_PX) continue;
    ticks.push({ index: i, ...text });
    previous = date;
    free = x + width + GAP_PX;
  }
  return ticks;
}
