import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, CATALOG, scenario, scenarioResult } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";

const NOTE = "Dywidendy udawanych instrumentów nie są liczone.";
const SAVED = scenario(5, "NASDAQ zamiast S&P");

function routes(extra: MockRoute[] = []) {
  return mockFetch([
    ...SIGNED_IN,
    ...extra,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/catalog", respond: () => CATALOG },
    { method: "POST", path: "/api/scenarios/preview", respond: () => scenarioResult("12044.20", "9.50", [NOTE]) },
    { method: "POST", path: "/api/scenarios", status: 201, respond: (_url, init) => ({ ...SAVED, ...JSON.parse(String(init.body)), id: 6 }) },
    { path: "/api/scenarios", respond: () => [SAVED] },
    { path: "/api/scenarios/5", respond: () => SAVED },
    { method: "PATCH", path: "/api/scenarios/5", respond: (_url, init) => ({ ...SAVED, ...JSON.parse(String(init.body)) }) },
    { method: "DELETE", path: "/api/scenarios/5", respond: () => new Response(null, { status: 204 }) },
    { path: /^\/api\/scenarios\/\d+\/result$/, respond: () => scenarioResult("12044.20", "9.50") },
  ]);
}

const bodyOf = (fetchMock: ReturnType<typeof routes>, method: string, path: string) => {
  const call = fetchMock.mock.calls.find(([url, init]) =>
    new URL(String(url), "http://localhost").pathname === path && (init?.method ?? "GET") === method);
  return call ? JSON.parse(String(call[1]!.body)) : undefined;
};

describe("Scenario editor", () => {
  it("creates a deposits scenario", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.type(await screen.findByLabelText("Nazwa"), "Wszystko w EDO");
    await user.click(screen.getByRole("button", { name: "Moje wpłaty" }));
    expect(screen.getByLabelText("Cel")).toHaveValue("edo");
    await user.click(screen.getByRole("button", { name: "Zapisz scenariusz" }));

    expect(await screen.findByRole("heading", { name: "Symulator" })).toBeInTheDocument();
    expect(bodyOf(fetchMock, "POST", "/api/scenarios")).toEqual({
      name: "Wszystko w EDO", base: "deposits", steps: [],
      allocation: [{ target: { instrument_id: null, bond: "EDO" }, share_pct: "100" }],
    });
  });

  it("says what is missing before saving", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.click(await screen.findByRole("button", { name: "Zapisz scenariusz" }));

    expect(screen.getByText("Podaj nazwę scenariusza.")).toBeInTheDocument();
    expect(bodyOf(fetchMock, "POST", "/api/scenarios")).toBeUndefined();
  });

  it("previews a top-up block with its notes", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.click(await screen.findByRole("button", { name: "Dopłacaj co miesiąc" }));
    await user.selectOptions(screen.getByLabelText("Na co"), "20");
    fireEvent.change(screen.getByLabelText("Od miesiąca"), { target: { value: "2024-01" } });

    const lastSteps = () => {
      const preview = fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/scenarios/preview")).at(-1);
      return preview ? JSON.parse(String(preview[1]!.body)).steps : undefined;
    };
    await waitFor(() => expect(lastSteps()).toEqual([{
      kind: "recurring", amount_pln: "1000", day_of_month: 10, start: "2024-01", end: null,
      target: { instrument_id: 20, bond: null }, ike: false,
    }]), { timeout: 2000 });
    expect(await screen.findByText(NOTE)).toBeInTheDocument();
    expect(screen.getByRole("img", { name: "Porównanie wartości: Mój portfel, Podgląd" })).toBeInTheDocument();
  });

  it("edits a saved scenario", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/5");

    const name = await screen.findByLabelText("Nazwa");
    expect(name).toHaveValue("NASDAQ zamiast S&P");
    expect(screen.getByLabelText("Zamiast")).toHaveValue("10");
    expect(screen.getByLabelText("Kupuj")).toHaveValue("20");
    await user.clear(name);
    await user.type(name, "NASDAQ");
    await user.click(screen.getByRole("button", { name: "Zapisz scenariusz" }));

    expect(await screen.findByRole("heading", { name: "Symulator" })).toBeInTheDocument();
    expect(bodyOf(fetchMock, "PATCH", "/api/scenarios/5")).toMatchObject({ name: "NASDAQ", base: "portfolio" });
  });

  it("deletes a saved scenario after a confirmation", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/5");

    await user.click(await screen.findByRole("button", { name: "Usuń scenariusz" }));
    await user.click(screen.getByRole("button", { name: "Usuń" }));

    expect(await screen.findByRole("heading", { name: "Symulator" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => String(url).endsWith("/api/scenarios/5") && init?.method === "DELETE"))
      .toBe(true);
  });

  it("adds a ticker to the catalog", async () => {
    const added = { id: 30, ticker: "VWCE.DE", name: "Vanguard FTSE All-World", currency: "EUR",
                    group: "Dodane przez Ciebie", accumulating: null, prices_from: "2019-07-25" };
    const fetchMock = routes([{ method: "POST", path: "/api/catalog", status: 201, respond: () => added }]);
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.type(await screen.findByLabelText("Brakuje instrumentu? Dodaj ticker z Yahoo"), "vwce.de");
    await user.click(screen.getByRole("button", { name: "Dodaj ticker" }));

    expect(await screen.findByText("Dodano: Vanguard FTSE All-World")).toBeInTheDocument();
    expect(bodyOf(fetchMock, "POST", "/api/catalog")).toEqual({ ticker: "vwce.de" });
  });

  it("shows the API's message when saving fails", async () => {
    routes([{ method: "POST", path: "/api/scenarios", respond: () => json(422, {
      code: "unknown_instrument", message: "Nie ma takiego instrumentu w katalogu ani w portfelu.", details: {} }) }]);
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.type(await screen.findByLabelText("Nazwa"), "Test");
    await user.click(screen.getByRole("button", { name: "Zapisz scenariusz" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Nie ma takiego instrumentu w katalogu ani w portfelu.");
    expect(screen.getByLabelText("Nazwa")).toHaveValue("Test");
  });
});

describe("Scenario editor preview", () => {
  const previewCalls = (fetchMock: ReturnType<typeof routes>) =>
    fetchMock.mock.calls.filter(([url]) => String(url).includes("/api/scenarios/preview")).length;

  it("says the preview is being counted instead of showing the old one as current", async () => {
    let release: (value: unknown) => void = () => {};
    let calls = 0;
    const fetchMock = routes([{ method: "POST", path: "/api/scenarios/preview", respond: () => {
      calls += 1;
      return calls === 1 ? scenarioResult("10804.20", "6.40") : new Promise((resolve) => { release = resolve; });
    } }]);
    const { user } = renderApp("/analiza/symulator/nowy");
    expect(await screen.findByText(/Względem portfela/)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Moje wpłaty" }));

    expect(await screen.findByText("Liczę podgląd…", {}, { timeout: 2000 })).toBeInTheDocument();
    expect(screen.queryByText(/Względem portfela/)).not.toBeInTheDocument();
    await waitFor(() => expect(calls).toBe(2), { timeout: 2000 });
    expect(screen.getByText("Liczę podgląd…")).toBeInTheDocument();
    release(scenarioResult("12044.20", "9.50"));
    expect(await screen.findByText(/Względem portfela: \+1\s240,00\szł/)).toBeInTheDocument();
    expect(previewCalls(fetchMock)).toBe(2);
  });

  it("explains at once why a replace block does not fit „Moje wpłaty”", async () => {
    routes();
    const { user } = renderApp("/analiza/symulator/nowy");

    await user.click(await screen.findByRole("button", { name: "Podmień instrument" }));
    await user.click(screen.getByRole("button", { name: "Moje wpłaty" }));

    expect(screen.getByText("Podmiana działa tylko na punkcie wyjścia „Mój portfel”.")).toBeInTheDocument();
    expect(screen.getByText(/Podgląd pojawi się po poprawce: Podmiana działa tylko/)).toBeInTheDocument();
  });

  it("does not rerun the preview while the name is typed", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/symulator/nowy");
    await screen.findByText(/Względem portfela/);
    const before = previewCalls(fetchMock);

    await user.type(screen.getByLabelText("Nazwa"), "Nowa nazwa");
    await new Promise((resolve) => setTimeout(resolve, 700));

    expect(previewCalls(fetchMock)).toBe(before);
  });
});
