import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import {
  ACCOUNTS, ANALYTICS, EXPOSURE, HISTORY, LIMITS, POSITIONS, PRICE_CHART, SUMMARY,
} from "../test/fixtures";
import { USER, json, mockFetch, renderApp, type MockRoute } from "../test/render";
import type { DashboardLayout } from "./layout";

const T = " ";

function routes(layout: DashboardLayout | null, overrides: Partial<Record<string, MockRoute["respond"]>> = {}): MockRoute[] {
  return [
    { method: "POST", path: "/api/auth/refresh", respond: () => ({ access_token: "token", token_type: "bearer" }) },
    { path: "/api/auth/me", respond: () => ({ ...USER, preferences: { dashboard: layout } }) },
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/portfolio/summary", respond: () => SUMMARY },
    { path: "/api/portfolio/history", respond: () => HISTORY },
    { path: "/api/portfolio/exposure", respond: () => EXPOSURE },
    { path: "/api/positions", respond: overrides.positions ?? (() => POSITIONS) },
    { path: "/api/portfolio/limits", respond: () => LIMITS },
    { path: "/api/analytics", respond: overrides.analytics ?? (() => ANALYTICS) },
    { path: "/api/positions/2/12/prices", respond: () => PRICE_CHART },
  ];
}

const layout = (...tiles: DashboardLayout["tiles"]): DashboardLayout => ({ version: 1, tiles });

describe("Pulpit from tiles", () => {
  it("shows the chosen fields under the value: Sharpe in place of TWR", async () => {
    mockFetch(routes(layout({ id: "s", kind: "summary", variant: "L",
      settings: { fields: ["total_gain", "sharpe", "invested", "income"] } })));
    renderApp("/");

    const tile = await screen.findByRole("region", { name: "Wartość portfela" });
    expect(await within(tile).findByText("0,62")).toBeInTheDocument();
    expect(within(tile).getByRole("button", { name: "Co to jest: Sharpe" })).toBeInTheDocument();
    expect(within(tile).queryByText("Stopa zwrotu (TWR)")).not.toBeInTheDocument();
  });

  it("asks the analytics once for several metric tiles and lays them out by width", async () => {
    const fetchMock = mockFetch(routes(layout(
      { id: "a", kind: "metric", variant: "S2", settings: { metric: "xirr" } },
      { id: "b", kind: "metric", variant: "S2", settings: { metric: "volatility" } },
    )));
    renderApp("/");

    const xirr = await screen.findByRole("region", { name: "XIRR" });
    expect(await within(xirr).findByText(`+6,4${T}%`)).toBeInTheDocument();
    expect(within(xirr).getByText("za okres")).toBeInTheDocument();
    expect(xirr.closest("[data-width]")).toHaveAttribute("data-width", "S");
    expect(screen.getByRole("region", { name: "Zmienność" })).toBeInTheDocument();
    const analytics = fetchMock.mock.calls.filter(([u]) => String(u).startsWith("/api/analytics"));
    expect(analytics).toHaveLength(1);
  });

  it("draws a price chart of the chosen holding with a link to its details", async () => {
    mockFetch(routes(layout({ id: "p", kind: "price_chart", variant: "L6",
      settings: { account_id: 2, instrument_id: 12, range: "max" } })));
    renderApp("/");

    const tile = await screen.findByRole("region", { name: "CD Projekt" });
    expect(await within(tile).findByRole("img", { name: /Wykres ceny/ })).toBeInTheDocument();
    expect(within(tile).getByRole("link", { name: "Szczegóły CD Projekt" })).toHaveAttribute("href", "/pozycje/2/12");
  });

  it("asks to pick another holding when the chosen one is gone", async () => {
    mockFetch(routes(layout({ id: "p", kind: "price_chart", variant: "M5",
      settings: { account_id: 9, instrument_id: 99, range: "buy" } })));
    renderApp("/");

    expect(await screen.findByText("Tego waloru nie ma już w portfelu — wybierz inny w ustawieniach kafelka.")).toBeInTheDocument();
  });

  it("keeps the rest of the Pulpit when one tile cannot load", async () => {
    mockFetch(routes(layout(
      { id: "m", kind: "metric", variant: "S2", settings: { metric: "sharpe" } },
      { id: "l", kind: "limits", variant: "M2", settings: {} },
    ), { analytics: () => json(500, { code: "internal_error", message: "Błąd.", details: {} }) }));
    const { user } = renderApp("/");

    const tile = await screen.findByRole("region", { name: "Sharpe" });
    expect(await within(tile).findByText("Nie udało się wczytać.")).toBeInTheDocument();
    expect(within(tile).getByRole("button", { name: "Ponów" })).toBeInTheDocument();
    expect(screen.getByRole("region", { name: "Limity IKE/IKZE" })).toBeInTheDocument();
    await user.click(within(tile).getByRole("button", { name: "Ponów" }));
  });

  it("shows the analysis tile's chosen metrics for its period", async () => {
    const fetchMock = mockFetch(routes(layout({ id: "a", kind: "analysis", variant: "M",
      settings: { metrics: ["sharpe", "best_day"], period: "1y" } })));
    renderApp("/");

    const tile = await screen.findByRole("region", { name: "Analiza" });
    expect(await within(tile).findByText("0,62")).toBeInTheDocument();
    expect(within(tile).getByText("05.08.2026")).toBeInTheDocument();
    expect(within(tile).queryByText("XIRR")).not.toBeInTheDocument();
    await waitFor(() => expect(fetchMock.mock.calls.map(([u]) => String(u))).toContain("/api/analytics?period=1y"));
  });

  it("shows a small allocation as a bar with the largest part", async () => {
    mockFetch(routes(layout({ id: "al", kind: "allocation", variant: "S2", settings: { by: "account" } })));
    renderApp("/");

    const tile = await screen.findByRole("region", { name: "Alokacja" });
    expect(within(tile).getByText("IKE")).toBeInTheDocument();
    expect(within(tile).getByText(`65,1${T}%`)).toBeInTheDocument();
    expect(within(tile).queryByText("XTB")).not.toBeInTheDocument();
  });

  it("drops a tile it cannot show and keeps the others", async () => {
    mockFetch(routes({ version: 1, tiles: [
      { id: "x", kind: "weather", size: "M", settings: {} },
      { id: "l", kind: "limits", size: "M", settings: {} },
    ] } as unknown as DashboardLayout));
    renderApp("/");

    expect(await screen.findByRole("region", { name: "Limity IKE/IKZE" })).toBeInTheDocument();
    expect(screen.queryByText("Wartość portfela")).not.toBeInTheDocument();
  });
});

describe("one metric twice under the value", () => {
  it("shows both, each with its own key", async () => {
    const errors = vi.spyOn(console, "error").mockImplementation(() => {});
    mockFetch(routes(layout({ id: "s", kind: "summary", variant: "L",
      settings: { fields: ["xirr", "invested", "xirr"] } })));
    renderApp("/");

    const tile = await screen.findByRole("region", { name: "Wartość portfela" });
    await waitFor(() => expect(within(tile).getAllByText(`+6,4${T}%`)).toHaveLength(2));
    expect(errors.mock.calls.flat().join(" ")).not.toMatch(/same key/);
  });
});
