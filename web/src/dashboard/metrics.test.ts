import { describe, expect, it } from "vitest";
import { ANALYTICS, SUMMARY } from "../test/fixtures";
import { METRICS, METRIC_OPTIONS, metricValue } from "./metrics";

describe("dashboard metrics", () => {
  it("reads the summary's figures", () => {
    expect(metricValue("income", SUMMARY, undefined)).toEqual({ value: "3412.05", format: "money", tone: false });
    expect(metricValue("total_gain", SUMMARY, undefined)).toMatchObject({ value: "23118.40", format: "money", tone: true });
    expect(metricValue("twr_total", SUMMARY, undefined)).toMatchObject({ value: "14.20", format: "percent" });
    expect(metricValue("fees", SUMMARY, undefined)).toMatchObject({ value: "-45.10", format: "money" });
  });

  it("reads the analytics, with the span of a return", () => {
    expect(metricValue("xirr", SUMMARY, ANALYTICS)).toEqual({ value: "6.40", format: "percent", tone: true, note: "za okres" });
    expect(metricValue("sharpe", SUMMARY, ANALYTICS)).toMatchObject({ value: "0.62", format: "number" });
    expect(metricValue("max_drawdown", SUMMARY, ANALYTICS)).toMatchObject({ value: "-8.20", format: "percent" });
    expect(metricValue("best_day", SUMMARY, ANALYTICS)).toMatchObject({ value: "2.90", note: "05.08.2026" });
    expect(metricValue("xirr", SUMMARY, undefined).value).toBeNull();
  });

  it("lists every metric once, with its source", () => {
    expect(METRIC_OPTIONS).toHaveLength(16);
    expect(METRICS.sharpe.source).toBe("analytics");
    expect(METRICS.invested.source).toBe("summary");
    expect(METRICS.invested.label).toBe("Wpłacono");
  });
});
