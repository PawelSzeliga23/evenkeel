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
