import { describe, expect, it } from "vitest";
import {
  axisLabel, clipAbove, clipBelow, depositMarks, frameFor, gapPath, indexAt, linePath, niceStep, scales,
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

  it("stretches the visible window over the whole plot", () => {
    const zoomed = scales(POINTS, BOX, { from: 1, to: 2 });
    expect([zoomed.x(0), zoomed.x(1), zoomed.x(2)]).toEqual([-100, 0, 100]);
  });

  it("uses a fixed amount range with round ticks inside it", () => {
    const fixed = scales(POINTS, BOX, undefined, { min: 100, max: 200 });
    expect([fixed.y(100), fixed.y(150), fixed.y(200), fixed.min, fixed.max]).toEqual([100, 50, 0, 100, 200]);
    expect(fixed.ticks).toEqual([125, 150, 175, 200]);
    for (const span of [2001, 2600, 3100, 5100]) expect(scales(POINTS, BOX, undefined, { min: 9000, max: 9000 + span }).ticks.length).toBeGreaterThanOrEqual(2);
    expect(scales(POINTS, BOX, undefined, { min: 103, max: 157 }).ticks).toEqual([120, 140]);
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

  it("finds the day under the finger in the visible window", () => {
    expect([0, 49, 80, 500].map((px) => indexAt(px, { from: 0, to: 2 }, BOX, 3))).toEqual([0, 1, 2, 2]);
    expect([0, 50, 100].map((px) => indexAt(px, { from: 10, to: 20 }, BOX, 30))).toEqual([10, 15, 20]);
  });

  it("sizes the frame to the measured width", () => {
    expect([frameFor(350), frameFor(700), frameFor(1200)].map((f) => [f.width, f.height])).toEqual([[350, 190], [700, 300], [1200, 300]]);
  });

  it("writes axis values in thousands", () => {
    expect([axisLabel(150000), axisLabel(2500), axisLabel(800), axisLabel(1500000)])
      .toEqual(["150 tys.", "2,5 tys.", "800", "1,5 mln"]);
  });

  it("writes whole amounts when the ticks are closer than 100 zł", () => {
    expect([axisLabel(11020, 20), axisLabel(11040, 20), axisLabel(184300, 50), axisLabel(900, 20)])
      .toEqual(["11 020", "11 040", "184 300", "900"]);
  });
});
