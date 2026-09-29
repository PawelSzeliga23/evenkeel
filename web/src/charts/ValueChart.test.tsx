import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HistoryPoint } from "../api/types";
import { ValueChart } from "./ValueChart";

// Testing Library normalizes NBSP to a plain space in text matchers; production output keeps NBSP.
const S = " ";
const point = (date: string, value: string, invested: string, flow = "0.00"): HistoryPoint =>
  ({ date, value_pln: value, invested_pln: invested, net_flow_pln: flow, twr_pct: null });
const TWO = [point("2026-09-01", "1000.00", "1000.00", "1000.00"), point("2026-09-26", "1100.00", "1000.00")];

describe("ValueChart", () => {
  it("says when there is not enough history for a chart", () => {
    render(<ValueChart points={[point("2026-09-26", "1000.00", "1000.00", "1000.00")]} />);
    expect(screen.getByText("Wykres pojawi się, gdy wycena obejmie co najmniej dwa dni.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("draws the value, the capital steps and the legend", () => {
    render(<ValueChart points={TWO} />);
    expect(screen.getByRole("img", { name: "Wykres wartości portfela od 01.09.2026 do 26.09.2026" })).toBeInTheDocument();
    expect(screen.getByText("Wpłacony kapitał")).toBeInTheDocument();
  });

  it("shows the day under the pointer", () => {
    render(<ValueChart points={TWO} />);
    const svg = screen.getByRole("img");
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({ left: 0, width: 350, top: 0, height: 190 } as DOMRect);

    fireEvent.pointerMove(svg, { clientX: 300, clientY: 50 });

    expect(screen.getByText("26.09.2026")).toBeInTheDocument();
    expect(screen.getByText(`Wartość 1${S}100,00${S}zł`)).toBeInTheDocument();
    expect(screen.getByText(`Wpłacono 1${S}000,00${S}zł`)).toBeInTheDocument();
  });
});
