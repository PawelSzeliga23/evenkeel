import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { LIMITS } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";
import { byWrapper, filled, overBy } from "./model";

// Testing Library normalizes NBSP to a plain space in text matchers.
const T = " ";

describe("limits model", () => {
  it("groups by wrapper with the newest year as current", () => {
    expect(byWrapper(LIMITS).map((g) => [g.wrapper, g.current.year, g.earlier.map((l) => l.year)])).toEqual([
      ["ike", 2026, [2025]], ["ikze", 2026, [2022]],
    ]);
  });

  it("fills the bar up to the limit and says by how much it was exceeded", () => {
    expect(filled(LIMITS[0]!)!.toFixed(4)).toBe("0.4246");
    expect(filled(LIMITS[2]!)).toBe(1);
    expect(filled(LIMITS[3]!)).toBeNull();
    expect(overBy(LIMITS[2]!)).toBe("696.00");
    expect(overBy(LIMITS[0]!)).toBeNull();
  });
});

describe("limits screen", () => {
  it("shows each wrapper's year by account, the excess and earlier years", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/limits", respond: () => LIMITS }]);
    renderApp("/limity");

    const ike = await screen.findByRole("region", { name: "IKE" });
    expect(within(ike).getByText(`Wpłacono 12${T}000,00${T}zł z 28${T}260,00${T}zł w 2026`)).toBeInTheDocument();
    expect(within(ike).getByText(`Zostało 16${T}260,00${T}zł`)).toBeInTheDocument();
    expect(within(ike).getByText("2025")).toBeInTheDocument();
    const ikze = screen.getByRole("region", { name: "IKZE" });
    expect(within(ikze).getByText(`Przekroczono limit o 696,00${T}zł`)).toBeInTheDocument();
    expect(within(ikze).getByText("brak limitu w danych")).toBeInTheDocument();
  });

  it("says when there is no IKE or IKZE account", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/limits", respond: () => [] }]);
    renderApp("/limity");
    expect(await screen.findByText("Nie masz konta IKE ani IKZE.")).toBeInTheDocument();
  });
});
