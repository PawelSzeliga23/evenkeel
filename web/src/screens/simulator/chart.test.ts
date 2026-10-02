import { describe, expect, it } from "vitest";
import type { ScenarioResult } from "../../api/types";
import { scenarioResult } from "../../test/fixtures";
import { chartData } from "./chart";

describe("chartData", () => {
  it("chartData aligns lines by date", () => {
    const early: ScenarioResult = {
      ...scenarioResult("12044.20", "9.50"),
      points: [
        { date: "2026-09-23", portfolio_pln: null, scenario_pln: "500.00", invested_pln: null, scenario_invested_pln: "500.00" },
        ...scenarioResult("12044.20", "9.50").points,
      ],
    };
    const late = scenarioResult("9000.00", "1.00");

    const data = chartData([{ key: "1", label: "A", slot: 0, result: early }, { key: "2", label: "B", slot: 2, result: late }], true);

    expect(data.dates).toEqual(["2026-09-23", "2026-09-24", "2026-09-25", "2026-09-26"]);
    expect(data.lines.map((line) => [line.key, line.values])).toEqual([
      ["portfolio", [null, "10700.00", "10750.00", "10804.20"]],
      ["1", ["500.00", "10900.00", "11000.00", "12044.20"]],
      ["2", [null, "10900.00", "11000.00", "9000.00"]],
    ]);
    expect(data.lines[2]).toMatchObject({ color: "#9085e9", dashed: true });
    expect(data.invested).toEqual([null, "10000.00", "10000.00", "10000.00"]);
  });

  it("leaves the portfolio out when it is hidden", () => {
    const data = chartData([{ key: "1", label: "A", slot: 1, result: scenarioResult("1.00", "1.00") }], false);
    expect(data.lines.map((line) => line.key)).toEqual(["1"]);
  });
});
