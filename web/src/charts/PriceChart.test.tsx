import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it, vi } from "vitest";
import type { PriceChartData, PriceMarker } from "../api/types";
import { PriceChart } from "./PriceChart";

const S = " ";
const BUY: PriceMarker = {
  date: "2026-03-04", kind: "buy", price: "590", price_with_fx: "591.00", quantity: "2", amount_pln: "-5082.60",
};
const DATA: PriceChartData = {
  currency: "EUR",
  points: [
    { date: "2026-03-02", close: "580.00" }, { date: "2026-03-03", close: "585.00" },
    { date: "2026-03-05", close: "595.00" }, { date: "2026-03-06", close: "600.00" },
  ],
  markers: [
    BUY,
    { ...BUY, kind: "sell", quantity: "1", price: "598", amount_pln: "2560.00" },
    { date: "2026-03-05", kind: "dividend", price: null, price_with_fx: null, quantity: null, amount_pln: "40.00" },
  ],
  notes: [],
  first_buy: "2026-03-04",
};

const draw = (data: PriceChartData = DATA, average: string | null = "593.40", onSelect = vi.fn()) =>
  render(<PriceChart data={data} average={average} selected={null} onSelect={onSelect} />);

describe("PriceChart", () => {
  it("draws the price as an image", () => {
    draw();
    expect(screen.getByRole("img", { name: /^Wykres ceny/ })).toBeInTheDocument();
  });

  it("makes every operation a named button that selects it", async () => {
    const onSelect = vi.fn();
    draw(DATA, "593.40", onSelect);

    await userEvent.click(screen.getByRole("button", { name: `Sprzedaż 04.03.2026, 1 szt. po 598,00${S}€` }));

    expect(screen.getByRole("button", { name: `Zakup 04.03.2026, 2 szt. po 590,00${S}€` })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: `Dywidenda 05.03.2026, +40,00${S}zł` })).toBeInTheDocument();
    expect(onSelect).toHaveBeenCalledWith(1);
  });

  it("keeps two operations of one day apart", () => {
    draw();
    const [buy, sell] = [/^Zakup/, /^Sprzedaż/].map((name) => screen.getByRole("button", { name }));
    const px = (button: HTMLElement) => (parseFloat(button.style.left) / 100) * 350; // drawn at 350 in jsdom
    expect(Math.abs(px(buy!) - px(sell!))).toBeGreaterThanOrEqual(16);
  });

  it("marks the selected operation as pressed", () => {
    render(<PriceChart data={DATA} average={null} selected={0} onSelect={vi.fn()} />);
    expect(screen.getByRole("button", { name: /^Zakup/ })).toHaveAttribute("aria-pressed", "true");
    expect(screen.getByRole("button", { name: /^Sprzedaż/ })).toHaveAttribute("aria-pressed", "false");
  });

  it("draws the average purchase price line with its label, none without an average", () => {
    const { unmount } = draw();
    expect(screen.getByText("średnia 593,40 €")).toBeInTheDocument();
    unmount();

    draw(DATA, null);
    expect(screen.queryByText(/^średnia/)).not.toBeInTheDocument();
  });

  it("points to the average at the edge when it lies outside the prices shown", () => {
    const { unmount } = draw(DATA, "100.00");
    expect(screen.getByText("średnia 100,00 € ↓")).toBeInTheDocument();
    unmount();

    draw(DATA, "900.00");
    expect(screen.getByText("średnia 900,00 € ↑")).toBeInTheDocument();
  });

  it("leaves out an operation before the first close", () => {
    draw({ ...DATA, markers: [{ ...BUY, date: "2026-02-20" }, BUY] });
    expect(screen.getAllByRole("button", { name: /^Zakup/ })).toHaveLength(1);
  });

  it("neither draws nor scales for an operation outside the window", () => {
    const points = Array.from({ length: 20 }, (_, i) => ({ date: `2026-01-${String(i + 1).padStart(2, "0")}`, close: "100.00" }));
    const far = { ...BUY, date: "2026-01-01", price: "9000" };
    render(<PriceChart data={{ ...DATA, points, markers: [far] }} average={null} selected={null} onSelect={vi.fn()}
      view={{ from: 10, to: 19 }} />);

    expect(screen.queryByRole("button", { name: /^Zakup/ })).not.toBeInTheDocument();
    const labels = [...document.querySelectorAll("text")].map((t) => Number(t.textContent!.replace(",", ".")));
    expect(Math.max(...labels.filter((n) => !Number.isNaN(n)))).toBeLessThan(200);
  });

  it("says so when there are not enough closes", () => {
    draw({ ...DATA, points: DATA.points.slice(0, 1) });
    expect(screen.getByText("Brak notowań dla tego instrumentu.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("draws one „N” per day of journal entries, after the operations", async () => {
    const onSelect = vi.fn();
    const notes = [{ date: "2026-03-05", entries: [{ id: 1, entry_date: "2026-03-04", body: "a" }, { id: 2, entry_date: "2026-03-05", body: "b" }] }];
    render(<PriceChart data={{ ...DATA, notes }} average={null} selected={null} onSelect={onSelect} />);

    const note = screen.getByRole("button", { name: `Notatka 05.03.2026` });
    expect(document.querySelectorAll('[data-mark="note"]')).toHaveLength(1);
    await userEvent.click(note);
    expect(onSelect).toHaveBeenCalledWith(DATA.markers.length);
  });
});
