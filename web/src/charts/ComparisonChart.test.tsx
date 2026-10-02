import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { describe, expect, it } from "vitest";
import { ComparisonChart, type ComparisonLine } from "./ComparisonChart";

const DATES = ["2026-01-01", "2026-01-02", "2026-01-03"];
const LINES: ComparisonLine[] = [
  { key: "portfolio", label: "Mój portfel", color: "#F0A43A", values: ["100.00", "110.00", "120.00"] },
  { key: "7", label: "NASDAQ", color: "#9085e9", dashed: true, values: [null, "105.00", "130.00"] },
];
const INVESTED = ["100.00", "100.00", "100.00"];

const path = (key: string) => document.querySelector(`path[data-line="${key}"]`)!;

describe("ComparisonChart", () => {
  it("draws a line per series in its colour, the invested capital thin", () => {
    render(<ComparisonChart dates={DATES} lines={LINES} invested={INVESTED} />);

    expect(screen.getByRole("img", { name: "Porównanie wartości: Mój portfel, NASDAQ" })).toBeInTheDocument();
    expect(path("portfolio")).toHaveAttribute("stroke", "#F0A43A");
    expect(path("7")).toHaveAttribute("stroke-dasharray", "6 4");
    expect(path("invested").getAttribute("d")).toMatch(/^M/);
  });

  it("draws a gap where a line has no value", () => {
    render(<ComparisonChart dates={[...DATES, "2026-01-04"]} invested={[...INVESTED, "100.00"]}
      lines={[{ key: "a", label: "A", color: "#3987e5", values: ["1.00", "2.00", null, "4.00"] }]} />);

    expect(path("a").getAttribute("d")!.match(/M/g)).toHaveLength(2);
  });

  it("reads out the last day and follows the arrow keys", async () => {
    const user = userEvent.setup();
    render(<ComparisonChart dates={DATES} lines={LINES} invested={INVESTED} />);

    expect(screen.getByText("03.01.2026")).toBeInTheDocument();
    expect(screen.getByText("130,00 zł")).toBeInTheDocument();
    screen.getByRole("img").focus();
    await user.keyboard("{ArrowLeft}{ArrowLeft}");
    expect(screen.getByText("01.01.2026")).toBeInTheDocument();
    expect(screen.getByText("—")).toBeInTheDocument(); // NASDAQ has no value on the first day
  });

  it("keeps one readout cell per line while moving", async () => {
    const user = userEvent.setup();
    render(<ComparisonChart dates={DATES} lines={LINES} invested={INVESTED} />);
    const cells = () => document.querySelectorAll("[data-readout-cell]").length;

    const before = cells();
    screen.getByRole("img").focus();
    await user.keyboard("{ArrowLeft}");
    expect(cells()).toBe(before);
    expect(before).toBe(4); // the day, two lines, the capital
    expect(screen.getByText("Wpłacono (portfel)")).toBeInTheDocument();
  });

  it("asks for at least two days", () => {
    render(<ComparisonChart dates={["2026-01-01"]} lines={[LINES[0]!]} invested={["100.00"]} />);
    expect(screen.getByText("Wykres pojawi się, gdy okres obejmie co najmniej dwa dni.")).toBeInTheDocument();
  });
});
