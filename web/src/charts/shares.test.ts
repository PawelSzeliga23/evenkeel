import { describe, expect, it } from "vitest";
import type { Exposure } from "../api/types";
import { EXPOSURE_HISTORY } from "../test/fixtures";
import { bands, colorOf, monthlyRows, shareSeries, sharePoints, thin } from "./shares";

describe("currency shares", () => {
  it("orders series by today's value, keeps colours with the currency and adds currencies seen only earlier", () => {
    expect(shareSeries(EXPOSURE_HISTORY)).toEqual([
      { key: "EUR", label: "EUR", color: "#F0A43A" },
      { key: "PLN", label: "PLN", color: "#3987e5" },
      { key: "USD", label: "USD", color: "#d55181" },
    ]);
  });

  it("folds a fifth currency and beyond into Inne", () => {
    const five: Exposure = {
      as_of: "2026-09-26",
      current: ["EUR", "PLN", "USD", "GBP", "CHF"].map((currency, i) => ({ currency, value_pln: String(50 - i), share_pct: null })),
      history: [{ date: "2026-09-26", values: { EUR: "50", PLN: "49", USD: "48", GBP: "47", CHF: "46" } }],
    };
    const series = shareSeries(five);
    expect(series.map((s) => s.label)).toEqual(["EUR", "PLN", "USD", "Inne"]);
    const [point] = sharePoints(five, series);
    expect(point!.shares.map((s) => s.toFixed(4))).toEqual(["0.2083", "0.2042", "0.2000", "0.3875"]);
    expect([colorOf(series, "USD"), colorOf(series, "CHF")]).toEqual(["#d55181", "#9085e9"]);
  });

  it("gives each day's shares summing to one, negative values counting as zero", () => {
    const series = shareSeries(EXPOSURE_HISTORY);
    const points = sharePoints(EXPOSURE_HISTORY, series);
    expect(points.map((p) => p.shares)).toEqual([[0, 1, 0], [0.5, 0.5, 0], [0.6, 0.4, 0]]);
  });

  it("skips days with nothing to share and names unknown currencies", () => {
    const exposure: Exposure = {
      as_of: "2026-09-26", current: [{ currency: "unknown", value_pln: "10", share_pct: "100" }],
      history: [{ date: "2026-09-25", values: {} }, { date: "2026-09-26", values: { unknown: "10" } }],
    };
    const series = shareSeries(exposure);
    expect(series.map((s) => s.label)).toEqual(["Nieznana"]);
    expect(sharePoints(exposure, series).map((p) => p.date)).toEqual(["2026-09-26"]);
  });

  it("thins long histories evenly and always keeps the last day", () => {
    const points = Array.from({ length: 500 }, (_, i) => ({ date: `d${i}`, shares: [1] }));
    const thinned = thin(points, 100);
    expect(thinned.length).toBeLessThanOrEqual(101);
    expect(thinned[0]!.date).toBe("d0");
    expect(thinned.at(-1)!.date).toBe("d499");
    expect(thin(points.slice(0, 3), 100)).toHaveLength(3);
  });

  it("draws stacked bands from the bottom, each closing on the one below", () => {
    const [first, second] = bands([{ date: "a", shares: [0.5, 0.5] }, { date: "b", shares: [1, 0] }], 100, 50);
    expect(first).toBe("M0.0,50.0L100.0,50.0L100.0,0.0L0.0,25.0Z");
    expect(second).toBe("M0.0,25.0L100.0,0.0L100.0,0.0L0.0,0.0Z");
  });

  it("keeps the last day of each month for the table", () => {
    const rows = monthlyRows([
      { date: "2026-08-30", shares: [1] }, { date: "2026-08-31", shares: [0.9] }, { date: "2026-09-26", shares: [0.8] },
    ]);
    expect(rows.map((r) => r.date)).toEqual(["2026-08-31", "2026-09-26"]);
  });
});
