import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { Holding } from "../../api/types";
import { HeatMap } from "./HeatMap";

const holding = (key: string, ticker: string | null, name: string, value: string, pct: string | null): Holding => ({
  key, kind: ticker ? "instrument" : "savings", ticker, name, category: ticker ? "etf" : "savings",
  value_pln: value, gain_pln: "1.00", gain_pct: pct, accounts: [],
});

const ITEMS = [
  holding("i:1", "SXR8.DE", "Core S&P 500", "1500.00", "0.91"),
  holding("s:2", null, "Trade Republic", "10000.00", "0.01"),
  holding("i:3", "SNT.PL", "Synektik", "0.50", "-1.80"),
];

describe("HeatMap", () => {
  it("shows a tile per holding, named by the ticker or the name and the gain", () => {
    render(<HeatMap items={ITEMS} period="1d" selected={null} onSelect={() => {}} />);

    expect(screen.getByRole("button", { name: /^SXR8, \+0,91\s%$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^Trade Republic, \+0,01\s%$/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^SNT, −1,80\s%$/ })).toBeInTheDocument();
  });

  it("opens a holding's details on a tap, even a tile too small for a label", async () => {
    const onSelect = vi.fn();
    render(<HeatMap items={ITEMS} period="1d" selected="i:1" onSelect={onSelect} />);

    await userEvent.click(screen.getByRole("button", { name: /^SNT/ }));

    expect(onSelect).toHaveBeenCalledWith("i:3");
    expect(screen.getByRole("button", { name: /^SXR8/ })).toHaveAttribute("aria-pressed", "true");
  });

  it("leaves out holdings without a value", () => {
    render(<HeatMap items={[...ITEMS, holding("i:4", "VIE.FR", "Veolia", "0.00", null)]} period="1d"
      selected={null} onSelect={() => {}} />);

    expect(screen.queryByRole("button", { name: /^VIE/ })).toBeNull();
  });
});
