import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import { IncomeChart } from "./IncomeChart";
import type { Bucket } from "./model";

const bucket = (key: string, income: number, costs: number): Bucket => ({
  key, label: key.slice(5), title: `${key}`, interest: income, dividends: 0, fx: costs, taxes: 0, fees: 0,
  income, costs, balance: income - costs,
});

describe("IncomeChart", () => {
  it("names each month with its income and costs and selects it on a tap", async () => {
    const onSelect = vi.fn();
    render(<IncomeChart buckets={[{ ...bucket("2026-09", 63.8, 49.7), title: "wrz 2026" }]} selected={null} onSelect={onSelect} />);

    expect(screen.getByRole("img", { name: "Dochód i koszty w miesiącach" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^wrz 2026: dochód \+63,80\szł, koszty −49,70\szł$/ }));

    expect(onSelect).toHaveBeenCalledWith("2026-09");
  });

  it("draws costs under the zero line", () => {
    const { container } = render(<IncomeChart buckets={[bucket("2026-08", 0, 20), bucket("2026-09", 10, 0)]} selected="2026-08" onSelect={() => {}} />);

    const zero = Number(container.querySelector("[data-zero]")!.getAttribute("y1"));
    const cost = container.querySelector("[data-part='fx']")!;
    expect(Number(cost.getAttribute("y"))).toBeGreaterThanOrEqual(zero);
    expect(screen.getByRole("button", { name: /^2026-08/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("draws an empty period without broken numbers", () => {
    const { container } = render(<IncomeChart buckets={[bucket("2026-08", 0, 0)]} selected={null} onSelect={() => {}} />);

    expect(container.innerHTML).not.toContain("NaN");
  });
});
