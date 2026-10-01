import { render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { DrawdownChart } from "./DrawdownChart";

const POINTS = [{ date: "2026-08-01", pct: "0.00" }, { date: "2026-08-15", pct: "-4.00" }, { date: "2026-09-01", pct: "-1.00" }];

afterEach(() => vi.unstubAllGlobals());

describe("DrawdownChart", () => {
  it("draws at its real width so labels keep their size on a wide screen", () => {
    vi.stubGlobal("ResizeObserver", class {
      constructor(private readonly callback: ResizeObserverCallback) {}
      observe() { this.callback([{ contentRect: { width: 700 } } as ResizeObserverEntry], this as unknown as ResizeObserver); }
      disconnect() {}
    });
    render(<DrawdownChart points={POINTS} />);

    expect(screen.getByRole("img")).toHaveAttribute("viewBox", "0 0 700 150");
  });
});
