import { describe, expect, it } from "vitest";
import {
  axisLabel, clipAbove, clipBelow, depositMarks, gapPath, linePath, monthTicks, nearestIndex, niceStep, scales,
  stairPath, toChartPoints, yDomain, type ChartPoint, type Frame,
} from "./geometry";

const BOX: Frame = { width: 100, height: 100, left: 0, right: 0, top: 0, bottom: 0 };
const POINTS: ChartPoint[] = [
  { date: "2026-01-01", value: 100, invested: 100, flow: 100 },
  { date: "2026-01-02", value: 110, invested: 100, flow: 0 },
  { date: "2026-01-03", value: 160, invested: 150, flow: 50 },
];

describe("scales", () => {
  it("reads the API's strings as numbers for drawing only", () => {
    expect(toChartPoints([{ date: "2026-01-01", value_pln: "1001.30", invested_pln: "1000.00", net_flow_pln: "1000.00", twr_pct: null }]))
      .toEqual([{ date: "2026-01-01", value: 1001.3, invested: 1000, flow: 1000 }]);
  });

  it("picks round steps", () => {
    expect([niceStep(60, 3), niceStep(80000, 3), niceStep(2, 3), niceStep(7, 3)]).toEqual([20, 50000, 1, 2.5]);
  });

  it("covers value and capital with round limits and ticks above the bottom", () => {
    expect(yDomain(POINTS)).toEqual({ min: 100, max: 160, ticks: [120, 140, 160] });
    const flat = [{ date: "2026-01-01", value: 100, invested: 100, flow: 0 }, { date: "2026-01-02", value: 100, invested: 100, flow: 0 }];
    expect(yDomain(flat)).toEqual({ min: 99, max: 101, ticks: [100, 101] });
  });
});

describe("paths", () => {
  const s = scales(POINTS, BOX);

  it("draws the value as a line and the capital as steps on deposit days", () => {
    expect(linePath(POINTS, s)).toBe("M0.0,100.0L50.0,83.3L100.0,0.0");
    expect(stairPath(POINTS, s)).toBe("M0.0,100.0H50.0V100.0H100.0V16.7");
  });

  it("closes the field between value and capital along the steps", () => {
    expect(gapPath(POINTS, s)).toBe("M0.0,100.0L50.0,83.3L100.0,0.0L100.0,16.7V100.0H50.0V100.0H0.0Z");
  });

  it("clips the field above and below the capital", () => {
    expect(clipAbove(POINTS, s, BOX)).toBe("M0.0,100.0H50.0V100.0H100.0V16.7V0.0H0.0Z");
    expect(clipBelow(POINTS, s, BOX)).toBe("M0.0,100.0H50.0V100.0H100.0V16.7V100.0H0.0Z");
  });
});

describe("marks and labels", () => {
  it("marks deposits, the larger ones taller", () => {
    expect(depositMarks(POINTS)).toEqual([{ index: 0, large: true }, { index: 2, large: false }]);
  });

  it("labels up to four month starts spread over the range", () => {
    const months = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"]
      .map((date) => ({ date, value: 1, invested: 1, flow: 0 }));
    expect(monthTicks(months)).toEqual([
      { index: 0, label: "sty" }, { index: 1, label: "lut" }, { index: 3, label: "kwi" }, { index: 4, label: "maj" },
    ]);
    expect(monthTicks(POINTS)).toEqual([{ index: 0, label: "sty" }]);
  });

  it("finds the day under the finger", () => {
    expect([nearestIndex(0, 3, BOX), nearestIndex(49, 3, BOX), nearestIndex(80, 3, BOX), nearestIndex(500, 3, BOX)])
      .toEqual([0, 1, 2, 2]);
  });

  it("writes axis values in thousands", () => {
    expect([axisLabel(150000), axisLabel(2500), axisLabel(800), axisLabel(1500000)])
      .toEqual(["150 tys.", "2,5 tys.", "800", "1,5 mln"]);
  });
});
