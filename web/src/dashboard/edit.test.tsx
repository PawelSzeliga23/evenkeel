import { act, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, ANALYTICS, EXPOSURE, HISTORY, LIMITS, POSITIONS, SUMMARY } from "../test/fixtures";
import { USER, mockFetch, renderApp, type MockRoute } from "../test/render";
import type { DashboardLayout } from "./layout";

const SAVED: DashboardLayout = { version: 1, tiles: [
  { id: "lim", kind: "limits", size: "M", settings: {} },
  { id: "xirr", kind: "metric", size: "S", settings: { metric: "xirr" } },
] };

function routes(layout: DashboardLayout | null, extra: Record<string, unknown> = {}): MockRoute[] {
  return [
    { method: "POST", path: "/api/auth/refresh", respond: () => ({ access_token: "token", token_type: "bearer" }) },
    { path: "/api/auth/me", respond: () => ({ ...USER, preferences: { dashboard: layout, ...extra } }) },
    { method: "PATCH", path: "/api/me/preferences", respond: async (_url, init) => ({
      dashboard: (JSON.parse(String(init?.body)) as { dashboard: unknown }).dashboard,
    }) },
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/portfolio/summary", respond: () => SUMMARY },
    { path: "/api/portfolio/history", respond: () => HISTORY },
    { path: "/api/portfolio/exposure", respond: () => EXPOSURE },
    { path: "/api/positions", respond: () => POSITIONS },
    { path: "/api/portfolio/limits", respond: () => LIMITS },
    { path: "/api/analytics", respond: () => ANALYTICS },
  ];
}

function sentLayouts(fetchMock: ReturnType<typeof mockFetch>): DashboardLayout[] {
  return fetchMock.mock.calls
    .filter(([url, init]) => String(url) === "/api/me/preferences" && init?.method === "PATCH")
    .map(([, init]) => (JSON.parse(String(init!.body)) as { dashboard: DashboardLayout }).dashboard);
}

async function startEditing(user: ReturnType<typeof renderApp>["user"]) {
  await screen.findByRole("region", { name: "Limity IKE/IKZE" });
  await user.click(screen.getByRole("button", { name: "Edytuj pulpit" }));
  expect(await screen.findByRole("button", { name: "Gotowe" })).toBeInTheDocument();
}

describe("editing the Pulpit", () => {
  it("adds a metric tile at the start, sets it to Sharpe and saves the layout", async () => {
    const fetchMock = mockFetch(routes(SAVED));
    const { user } = renderApp("/");
    await startEditing(user);

    await user.click(screen.getByRole("button", { name: "+ Dodaj kafelek" }));
    await user.click(screen.getByRole("button", { name: /^Jedna miara/ }));
    const first = screen.getAllByRole("group", { name: /^Kafelek / })[0]!;
    expect(first).toHaveAccessibleName("Kafelek Jedna miara");
    await user.click(within(first).getByRole("button", { name: "Ustaw kafelek Jedna miara" }));
    await user.selectOptions(within(first).getByRole("combobox", { name: "Miara" }), "sharpe");
    await user.click(within(first).getByRole("button", { name: "Zamknij ustawienia" }));
    await user.click(screen.getByRole("button", { name: "Gotowe" }));

    await waitFor(() => expect(sentLayouts(fetchMock)).toHaveLength(1));
    const sent = sentLayouts(fetchMock)[0]!;
    expect(sent.tiles.map((t) => t.kind)).toEqual(["metric", "limits", "metric"]);
    expect(sent.tiles[0]!.settings).toEqual({ metric: "sharpe" });
    await waitFor(() => expect(screen.queryByRole("button", { name: "Gotowe" })).not.toBeInTheDocument());
  });

  it("removes a tile and brings it back with Anuluj, without saving", async () => {
    const fetchMock = mockFetch(routes(SAVED));
    const { user } = renderApp("/");
    await startEditing(user);

    await user.click(screen.getByRole("button", { name: "Usuń kafelek Limity IKE/IKZE" }));
    expect(screen.queryByRole("group", { name: "Kafelek Limity IKE/IKZE" })).not.toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Anuluj" }));

    expect(await screen.findByRole("region", { name: "Limity IKE/IKZE" })).toBeInTheDocument();
    expect(sentLayouts(fetchMock)).toEqual([]);
  });

  it("moves a tile later without dragging", async () => {
    const fetchMock = mockFetch(routes(SAVED));
    const { user } = renderApp("/");
    await startEditing(user);

    const limits = screen.getByRole("group", { name: "Kafelek Limity IKE/IKZE" });
    await user.click(within(limits).getByRole("button", { name: "Ustaw kafelek Limity IKE/IKZE" }));
    await user.click(within(limits).getByRole("button", { name: "Przesuń później" }));
    await user.click(screen.getByRole("button", { name: "Gotowe" }));

    await waitFor(() => expect(sentLayouts(fetchMock)[0]?.tiles.map((t) => t.id)).toEqual(["xirr", "lim"]));
  });

  it("opens the settings of a new price chart to pick a holding", async () => {
    mockFetch(routes(SAVED));
    const { user } = renderApp("/");
    await startEditing(user);

    await user.click(screen.getByRole("button", { name: "+ Dodaj kafelek" }));
    await user.click(screen.getByRole("button", { name: /^Wykres ceny/ }));

    const tile = screen.getAllByRole("group", { name: /^Kafelek / })[0]!;
    const holding = within(tile).getByRole("combobox", { name: "Walor" });
    expect(within(holding).getByRole("option", { name: "CD Projekt · XTB" })).toBeInTheDocument();
    expect(within(tile).getByRole("radio", { name: "L" })).toBeChecked();
  });

  it("saves no layout when it is back to the default one", async () => {
    const fetchMock = mockFetch(routes(SAVED));
    const { user } = renderApp("/");
    await startEditing(user);

    await user.click(screen.getByRole("button", { name: "Przywróć domyślny" }));
    expect(screen.getByRole("group", { name: "Kafelek Wartość portfela" })).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Gotowe" }));

    await waitFor(() => expect(sentLayouts(fetchMock)).toEqual([null]));
  });

  it("starts editing from the sidebar link", async () => {
    mockFetch(routes(SAVED));
    renderApp("/?edycja");

    expect(await screen.findByRole("button", { name: "Gotowe" })).toBeInTheDocument();
    const nav = screen.getByRole("navigation", { name: "Główna" });
    const links = within(nav).getAllByRole("link", { hidden: true }).map((l) => l.getAttribute("href"));
    expect(links.slice(-2)).toEqual(["/?edycja", "/ustawienia"]);
  });
});

describe("the default layout with the owner's chart range", () => {
  async function editDefault(user: ReturnType<typeof renderApp>["user"]) {
    await screen.findByRole("region", { name: "Limity IKE/IKZE" });
    await user.click(screen.getByRole("button", { name: "Edytuj pulpit" }));
    await screen.findByRole("button", { name: "Gotowe" });
  }

  it("saves nothing when the default layout keeps the range from Ustawienia", async () => {
    const fetchMock = mockFetch(routes(null, { value_range: "3M" }));
    const { user } = renderApp("/");
    await editDefault(user);

    await user.click(screen.getByRole("button", { name: "Gotowe" }));

    await waitFor(() => expect(sentLayouts(fetchMock)).toEqual([null]));
  });

  it("saves the layout when the chart range differs from Ustawienia", async () => {
    const fetchMock = mockFetch(routes(null, { value_range: "3M" }));
    const { user } = renderApp("/");
    await editDefault(user);

    const chart = screen.getByRole("group", { name: "Kafelek Wykres wartości" });
    await user.click(within(chart).getByRole("button", { name: "Ustaw kafelek Wykres wartości" }));
    expect(within(chart).getByRole("combobox", { name: "Zakres" })).toHaveValue("3M");
    await user.selectOptions(within(chart).getByRole("combobox", { name: "Zakres" }), "1R");
    await user.click(screen.getByRole("button", { name: "Gotowe" }));

    await waitFor(() => expect(sentLayouts(fetchMock)[0]?.tiles[1]?.settings).toEqual({ range: "1R" }));
  });

  it("restores the default with the owner's range", async () => {
    mockFetch(routes(SAVED, { value_range: "3M" }));
    const { user } = renderApp("/");
    await startEditing(user);

    await user.click(screen.getByRole("button", { name: "Przywróć domyślny" }));
    const chart = screen.getByRole("group", { name: "Kafelek Wykres wartości" });
    await user.click(within(chart).getByRole("button", { name: "Ustaw kafelek Wykres wartości" }));

    expect(within(chart).getByRole("combobox", { name: "Zakres" })).toHaveValue("3M");
  });
});

describe("leaving the editing with the browser's Back", () => {
  it("drops the unsaved changes", async () => {
    mockFetch(routes(SAVED));
    const { user, router } = renderApp("/");
    await startEditing(user);
    await user.click(screen.getByRole("button", { name: "Usuń kafelek Limity IKE/IKZE" }));

    await act(() => router.navigate(-1));
    await waitFor(() => expect(screen.queryByRole("button", { name: "Gotowe" })).not.toBeInTheDocument());
    await user.click(screen.getByRole("button", { name: "Edytuj pulpit" }));

    expect(await screen.findByRole("group", { name: "Kafelek Limity IKE/IKZE" })).toBeInTheDocument();
  });
});
