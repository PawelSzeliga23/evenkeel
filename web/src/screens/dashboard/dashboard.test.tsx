import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NETWORK_MESSAGE } from "../../api/client";
import { pluralPl } from "../../format";
import { ACCOUNTS, EXPOSURE, HISTORY, LIMITS, POSITIONS, SUMMARY, position } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp, type MockRoute } from "../../test/render";
import { allocationRows, dayMovers, rangeFrom } from "./model";

// Testing Library normalizes NBSP to a plain space in text matchers.
const M = "−";
const T = " ";

function routes(overrides: Partial<Record<string, MockRoute["respond"]>> = {}): MockRoute[] {
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: overrides.accounts ?? (() => ACCOUNTS) },
    { path: "/api/portfolio/summary", respond: overrides.summary ?? (() => SUMMARY) },
    { path: "/api/portfolio/history", respond: overrides.history ?? (() => HISTORY) },
    { path: "/api/portfolio/exposure", respond: overrides.exposure ?? (() => EXPOSURE) },
    { path: "/api/positions", respond: overrides.positions ?? (() => POSITIONS) },
    { path: "/api/portfolio/limits", respond: overrides.limits ?? (() => LIMITS) },
  ];
}

afterEach(() => vi.useRealTimers());

describe("dashboard model", () => {
  it("starts each range from the valuation day", () => {
    expect([rangeFrom("1M", "2026-09-26"), rangeFrom("3M", "2026-09-26"), rangeFrom("1R", "2026-09-26"), rangeFrom("ALL", "2026-09-26")])
      .toEqual(["2026-08-26", "2026-06-26", "2025-09-26", null]);
    expect(rangeFrom("1R", null)).toBeNull();
  });

  it("colours allocation rows by their order, the largest in amber", () => {
    const rows = allocationRows("kind", SUMMARY, undefined);
    expect(rows.map((r) => [r.name, r.color])).toEqual([
      ["ETF", "var(--amber)"], ["Konta oszczędnościowe", "#C9B48A"], ["Obligacje", "#7C8898"], ["Gotówka", "#4A5361"],
    ]);
    expect(allocationRows("currency", SUMMARY, EXPOSURE).map((r) => r.name)).toEqual(["EUR", "PLN"]);
    expect(allocationRows("currency", SUMMARY, undefined)).toEqual([]);
  });

  it("finds the biggest moves of the day among instruments", () => {
    expect(dayMovers(POSITIONS).map((m) => [m.position.name, Number(m.pct).toFixed(2)])).toEqual([
      ["CD Projekt", "3.84"], ["Orlen", "-2.07"], ["Core S&P 500", "1.05"],
    ]);
  });

  it("writes Polish plurals", () => {
    const f = (n: number) => pluralPl(n, "pozycja", "pozycje", "pozycji");
    expect([f(1), f(2), f(4), f(5), f(12), f(22), f(25)]).toEqual(["pozycja", "pozycje", "pozycje", "pozycji", "pozycji", "pozycje", "pozycji"]);
  });

  it("computes the day's percent from the payout value", () => {
    const p = position({ value_pln: "1005.00", payout_pln: "1000.00", day_change_pln: "100.00" });
    expect(dayMovers([p])[0]!.pct).toBe("11.1111"); // 100 / (1000 − 100)
  });
});

describe("dashboard screen", () => {
  it("shows the IKE/IKZE card with this year's contributions and links to the details", async () => {
    mockFetch(routes());
    renderApp("/");

    const card = await screen.findByRole("region", { name: "Limity IKE/IKZE" });
    expect(within(card).getByText(`IKE 2026: 12${T}000,00${T}zł z 28${T}260,00${T}zł`)).toBeInTheDocument();
    expect(within(card).getByText(`IKZE 2026: przekroczono limit o 696,00${T}zł`)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Szczegóły limitów" })).toHaveAttribute("href", "/limity");
  });

  it("hides the limits card without IKE or IKZE accounts", async () => {
    const fetchMock = mockFetch(routes({ limits: () => [] }));
    renderApp("/");
    expect(await screen.findByText("Wartość portfela")).toBeInTheDocument();
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).includes("/api/portfolio/limits"))).toBe(true));
    expect(screen.queryByRole("region", { name: "Limity IKE/IKZE" })).not.toBeInTheDocument();
  });

  it("shows the value, the day, the chart, allocation and the day's biggest moves", async () => {
    mockFetch(routes());
    renderApp("/");

    expect(await screen.findByText("Wartość portfela")).toBeInTheDocument();
    expect(screen.getByText("sob., 26 września")).toBeInTheDocument();
    expect(screen.getByText(`+1${T}204,50${T}zł`)).toHaveClass("up");
    expect(screen.getByText(`(+0,66${T}%)`)).toBeInTheDocument();
    expect(screen.getByText(`+14,2${T}%`)).toBeInTheDocument();
    expect(screen.getByText(`3${T}412,05${T}zł`)).toBeInTheDocument();
    expect(screen.getByText("1 pozycja wyceniona w przybliżeniu")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /Wykres wartości portfela/ })).toBeInTheDocument();
    expect(screen.getByText("Konta oszczędnościowe")).toBeInTheDocument();

    const movers = await screen.findByRole("region", { name: "Dziś najbardziej" });
    const rows = within(movers).getAllByRole("link").filter((l) => l.getAttribute("href")?.startsWith("/pozycje/"));
    expect(rows.map((l) => l.textContent)).toEqual([
      expect.stringContaining("CD Projekt"), expect.stringContaining("Orlen"), expect.stringContaining("Core S&P 500"),
    ]);
  });

  it("invites an empty portfolio to import", async () => {
    mockFetch(routes({ summary: () => ({ ...SUMMARY, as_of: null, by_kind: [], by_account: [] }) }));
    renderApp("/");
    expect(await screen.findByText("Wgraj eksport z XTB, żeby zobaczyć swój portfel.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wgraj pliki z XTB" })).toHaveAttribute("href", "/dodaj/xtb");
  });

  it("asks for one account and the currency allocation of the valuation day", async () => {
    const fetchMock = mockFetch(routes());
    const { user } = renderApp("/");

    await user.click(await screen.findByRole("button", { name: "Konta: Cały portfel" }));
    await user.click(screen.getByRole("checkbox", { name: "XTB" }));
    await user.keyboard("{Escape}");
    await user.click(screen.getByRole("button", { name: "Waluta" }));

    expect(await screen.findByText("EUR")).toBeInTheDocument();
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toContain("/api/portfolio/summary?account_id=1");
    expect(urls).toContain("/api/portfolio/exposure?account_id=1&from=2026-09-26&to=2026-09-26");
    expect(urls.some((u) => u.startsWith("/api/portfolio/history?account_id=1&from=2025-09-26"))).toBe(true);
  });

  it("keeps asking while the valuation is recalculated and then refreshes the chart", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let summaries = 0;
    let histories = 0;
    mockFetch(routes({
      summary: () => ({ ...SUMMARY, recalculating: ++summaries === 1 }),
      history: () => { histories += 1; return HISTORY; },
    }));
    renderApp("/");

    expect(await screen.findByText("Przeliczam wycenę…")).toBeInTheDocument();
    await waitFor(() => expect(histories).toBe(1));
    await vi.advanceTimersByTimeAsync(3000);

    await waitFor(() => expect(screen.queryByText("Przeliczam wycenę…")).not.toBeInTheDocument());
    await waitFor(() => expect(histories).toBe(2));
  });

  it("says when the API cannot be reached and lets the user try again", async () => {
    let calls = 0;
    const fetchMock = mockFetch(routes());
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation((input: string, init?: RequestInit) =>
      String(input).startsWith("/api/portfolio/summary") && ++calls === 1
        ? Promise.reject(new TypeError("Failed to fetch"))
        : original(input, init));
    const { user } = renderApp("/");

    expect(await screen.findByRole("alert")).toHaveTextContent(NETWORK_MESSAGE);
    await user.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(await screen.findByText("Wartość portfela")).toBeInTheDocument();
  });

  it("shows the market value and the exit costs under the payout value", async () => {
    mockFetch(routes());
    renderApp("/");

    expect(await screen.findByText(`Wartość rynkowa 184${T}327,67${T}zł · koszty wyjścia ${M}25,50${T}zł`)).toBeInTheDocument();
  });

  it("hides the exit costs line when there are none", async () => {
    mockFetch(routes({ summary: () => ({ ...SUMMARY, market_value_pln: SUMMARY.value_pln, exit_cost_pln: "0.00" }) }));
    renderApp("/");

    expect(await screen.findByText("Wartość portfela")).toBeInTheDocument();
    expect(screen.queryByText(/koszty wyjścia/)).not.toBeInTheDocument();
  });

  it("keeps the numbers on screen while another account loads", async () => {
    let release: () => void = () => {};
    const slow = new Promise<void>((resolve) => { release = resolve; });
    mockFetch(routes({ summary: async (url) => {
      if (url.searchParams.get("account_id") === "1") { await slow; return { ...SUMMARY, value_pln: "120000.00" }; }
      return SUMMARY;
    } }));
    const { user } = renderApp("/");

    expect(await screen.findByText("Wartość portfela")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Konta: Cały portfel" }));
    await user.click(screen.getByRole("checkbox", { name: "XTB" }));

    expect(screen.getByText("Wartość portfela")).toBeInTheDocument(); // no skeleton in between
    release();
    expect(await screen.findByText(/120/)).toBeInTheDocument();
  });
});
