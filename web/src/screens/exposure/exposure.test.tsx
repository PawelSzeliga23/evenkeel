import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, EXPOSURE, EXPOSURE_HISTORY, HISTORY, POSITIONS, SUMMARY } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";

describe("currency exposure over time", () => {
  it("shows today's shares, the chart with its legend and a table", async () => {
    const fetchMock = mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/portfolio/exposure", respond: () => EXPOSURE_HISTORY },
    ]);
    const { user } = renderApp("/ekspozycja");

    expect(await screen.findByRole("heading", { name: "Ekspozycja walutowa" })).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /Udział walut w czasie/ })).toBeInTheDocument();
    const legend = screen.getByRole("list", { name: "Legenda" });
    expect(within(legend).getAllByRole("listitem").map((li) => li.textContent)).toEqual(["EUR", "PLN", "USD"]);
    expect(screen.getByText("waluta notowania, nie waluta aktywów bazowych", { exact: false })).toBeInTheDocument();

    await user.click(screen.getByText("Pokaż tabelę"));
    const table = screen.getByRole("table");
    expect(within(table).getByText("26.09.2026")).toBeInTheDocument();
    expect(within(table).getAllByText("60,0 %").length).toBeGreaterThan(0);

    await user.click(screen.getByRole("button", { name: "3M" }));
    expect(fetchMock.mock.calls.map(([url]) => String(url)).some((u) => u.includes("/api/portfolio/exposure?from="))).toBe(true);
  });

  it("is reached from the dashboard's currency allocation", async () => {
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/portfolio/summary", respond: () => SUMMARY },
      { path: "/api/portfolio/history", respond: () => HISTORY },
      { path: "/api/portfolio/exposure", respond: () => EXPOSURE },
      { path: "/api/positions", respond: () => POSITIONS },
      { path: "/api/portfolio/limits", respond: () => [] },
    ]);
    const { user } = renderApp("/");

    await user.click(await screen.findByRole("button", { name: "Waluta" }));
    expect(await screen.findByRole("link", { name: "Zobacz w czasie" })).toHaveAttribute("href", "/ekspozycja");
  });
});
