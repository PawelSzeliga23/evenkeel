import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Logo, Wordmark } from "./Logo";
import { Mark } from "./Mark";

describe("brand", () => {
  it("names the logo Evenkeel and hides the drawing from screen readers", () => {
    const { container } = render(<Logo layout="stacked" />);
    expect(screen.getByRole("img", { name: "Evenkeel" })).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("writes Even and keel in two colours", () => {
    const { container } = render(<Wordmark />);
    expect(container.textContent).toBe("Evenkeel");
    expect(container.querySelector("[data-part=keel]")).toHaveTextContent("keel");
  });

  it("draws four rising bars on a base line", () => {
    const { container } = render(<Mark size={64} />);
    const heights = [...container.querySelectorAll("[data-bar]")].map((b) => Number(b.getAttribute("height")));
    expect(heights).toEqual([12, 19, 25, 38]);
    expect(container.querySelector("svg")).toHaveAttribute("width", "64");
  });

  it("lays the name under or next to the mark", () => {
    const { rerender } = render(<Logo layout="stacked" />);
    expect(screen.getByRole("img", { name: "Evenkeel" })).toHaveAttribute("data-layout", "stacked");
    rerender(<Logo layout="inline" />);
    expect(screen.getByRole("img", { name: "Evenkeel" })).toHaveAttribute("data-layout", "inline");
  });
});
