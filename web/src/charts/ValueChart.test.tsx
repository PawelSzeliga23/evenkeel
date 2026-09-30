import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HistoryPoint } from "../api/types";
import { ValueChart } from "./ValueChart";

// Testing Library normalizes NBSP to a plain space in text matchers; production output keeps NBSP.
const S = " ";
const point = (date: string, value: string, invested: string, flow = "0.00"): HistoryPoint =>
  ({ date, value_pln: value, invested_pln: invested, net_flow_pln: flow, twr_pct: null });
const MONTH = Array.from({ length: 30 }, (_, i) =>
  point(`2026-09-${String(i + 1).padStart(2, "0")}`, `${1000 + i * 10}.00`, "1000.00", i === 0 ? "1000.00" : "0.00"));
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

  it("draws only the visible window and names it", () => {
    render(<ValueChart points={MONTH} view={{ from: 23, to: 29 }} />);
    expect(screen.getByRole("img", { name: "Wykres wartości portfela od 24.09.2026 do 30.09.2026" })).toBeInTheDocument();
    expect(screen.getByText("24 wrz")).toBeInTheDocument();
    expect(screen.getByText("30")).toBeInTheDocument();
  });

  it("clamps a window that no longer fits the history", () => {
    render(<ValueChart points={TWO} view={{ from: 20, to: 29 }} />);
    expect(screen.getByRole("img", { name: "Wykres wartości portfela od 01.09.2026 do 26.09.2026" })).toBeInTheDocument();
  });

  const rect = { left: 0, width: 350, top: 0, height: 190 } as DOMRect;

  it("zooms with Ctrl and the wheel around the pointer", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={MONTH} onViewChange={onViewChange} />);
    const svg = screen.getByRole("img");
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue(rect);

    fireEvent.wheel(svg, { ctrlKey: true, deltaY: -200, clientX: 153 });

    const view = onViewChange.mock.calls[0]![0] as { from: number; to: number };
    expect(view.to - view.from).toBeLessThan(29);
    expect(view.from).toBeGreaterThan(0);
    expect(view.to).toBeLessThan(29);
  });

  it("scrolls the page on a plain wheel and says how to zoom", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={MONTH} onViewChange={onViewChange} />);

    fireEvent.wheel(screen.getByRole("img"), { deltaY: 100 });

    expect(onViewChange).not.toHaveBeenCalled();
    expect(screen.getByText("Ctrl + kółko przybliża")).toBeInTheDocument();
  });

  it("goes back to the range on a double click", () => {
    const onReset = vi.fn();
    render(<ValueChart points={MONTH} view={{ from: 10, to: 20 }} onReset={onReset} />);

    fireEvent.doubleClick(screen.getByRole("img"));

    expect(onReset).toHaveBeenCalledOnce();
  });

  it("pans when the mouse drags, but a plain click does not change the window", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={MONTH} view={{ from: 10, to: 20 }} onViewChange={onViewChange} />);
    const svg = screen.getByRole("img");
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue(rect);

    fireEvent.pointerDown(svg, { pointerId: 1, pointerType: "mouse", button: 0, clientX: 150 });
    fireEvent.pointerMove(svg, { pointerId: 1, pointerType: "mouse", clientX: 151 });
    fireEvent.pointerUp(svg, { pointerId: 1, pointerType: "mouse", clientX: 151 });
    expect(onViewChange).not.toHaveBeenCalled();

    fireEvent.pointerDown(svg, { pointerId: 1, pointerType: "mouse", button: 0, clientX: 150 });
    fireEvent.pointerMove(svg, { pointerId: 1, pointerType: "mouse", clientX: 200 });
    const view = onViewChange.mock.calls.at(-1)![0] as { from: number; to: number };
    expect(view.from).toBeLessThan(10);
  });

  it("does nothing on a history shorter than a week", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={TWO} onViewChange={onViewChange} />);
    fireEvent.wheel(screen.getByRole("img"), { ctrlKey: true, deltaY: -200, clientX: 150 });
    expect(onViewChange).not.toHaveBeenCalled();
  });

  it("does not report a zoom out past the whole history as a change", () => {
    const onViewChange = vi.fn();
    render(<ValueChart points={MONTH} onViewChange={onViewChange} />);
    const svg = screen.getByRole("img");
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue(rect);
    fireEvent.wheel(svg, { ctrlKey: true, deltaY: 400, clientX: 150 });
    expect(onViewChange).not.toHaveBeenCalled();
  });
});
