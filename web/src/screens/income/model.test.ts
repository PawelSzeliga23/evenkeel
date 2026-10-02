import { describe, expect, it } from "vitest";
import type { IncomeMonth } from "../../api/types";
import { buckets } from "./model";

const month = (key: string, income: string, costs = "0.00"): IncomeMonth => ({
  month: key, interest_pln: income, dividends_pln: "0.00", fx_pln: costs, taxes_pln: "0.00", fees_pln: "0.00",
  income_pln: income, costs_pln: costs, balance_pln: (Number(income) - Number(costs)).toFixed(2),
});

describe("buckets", () => {
  it("keeps months as they are", () => {
    const result = buckets([month("2026-08", "4.40"), month("2026-09", "63.80", "49.70"), month("2026-10", "3.10")]);

    expect(result.map((b) => [b.key, b.label, b.title])).toEqual([
      ["2026-08", "sie", "sie 2026"], ["2026-09", "wrz", "wrz 2026"], ["2026-10", "paź", "paź 2026"]]);
    expect(result[1]).toMatchObject({ income: 63.8, costs: 49.7, interest: 63.8, fx: 49.7 });
  });

  it("sums years once there are more than 24 months", () => {
    const months = Array.from({ length: 30 }, (_, i) => {
      const n = 2024 * 12 + 6 + i;
      return month(`${Math.floor(n / 12)}-${String((n % 12) + 1).padStart(2, "0")}`, "1.00");
    });

    const result = buckets(months);

    expect(result.map((b) => [b.key, b.label, b.title])).toEqual([["2024", "2024", "2024"], ["2025", "2025", "2025"], ["2026", "2026", "2026"]]);
    expect(result.map((b) => b.income)).toEqual([6, 12, 12]);
  });
});
