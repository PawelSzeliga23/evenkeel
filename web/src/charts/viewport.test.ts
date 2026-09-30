import { describe, expect, it } from "vitest";
import { clampWindow, drawnRange, fullWindow, moveWindow, scaleRange, shiftRange, windowForRange, type ChartWindow } from "./viewport";

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

describe("amount range", () => {
  it("stretches or squeezes around its middle", () => {
    expect(scaleRange({ min: 100, max: 200 }, 2)).toEqual({ min: 50, max: 250 });
    expect(scaleRange({ min: 100, max: 200 }, 0.5)).toEqual({ min: 125, max: 175 });
  });

  it("never collapses below one złoty", () => {
    expect(scaleRange({ min: 100, max: 200 }, 0.0001)).toEqual({ min: 149.5, max: 150.5 });
  });

  it("moves up and down", () => {
    expect(shiftRange({ min: 100, max: 200 }, 10)).toEqual({ min: 110, max: 210 });
  });
});
