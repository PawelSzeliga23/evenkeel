import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { BondOut, Journal, SavingsAccountOut } from "../api/types";
import { ACCOUNTS, ANALYTICS, EXPOSURE, HISTORY, HOLDINGS, LIMITS, POSITIONS, SUMMARY } from "../test/fixtures";
import { USER, mockFetch, renderApp, type MockRoute } from "../test/render";

const T = " ";
const base = { instrument_id: null, ticker: null, name: null, quantity: null, price: null, price_currency: null, currency: "PLN", tax: null, note: "", delete: null };
const OPERATIONS = { items: [
  { ...base, id: "tx:3", kind: "transaction", type: "dividend", date: "2026-09-26", account_id: 1, account_name: "IKE", ticker: "CDR.PL", name: "CD Projekt", amount: "12.00", amount_pln: "12.00" },
  { ...base, id: "tx:2", kind: "transaction", type: "buy", date: "2026-09-25", account_id: 1, account_name: "IKE", ticker: "CDR.PL", name: "CD Projekt", amount: "-500.00", amount_pln: "-500.00" },
  { ...base, id: "tx:1", kind: "transaction", type: "deposit", date: "2026-09-24", account_id: 2, account_name: "XTB", amount: "1000.00", amount_pln: "1000.00" },
], next_cursor: null };
const BONDS: BondOut[] = [
  { id: 7, account_id: 3, account_name: "Obligacje", bond_type: "EDO", series: "EDO0936", quantity: 100, purchase_date: "2026-09-01",
    redeemed_at: null, maturity_date: "2036-09-01", note: "", status: "active", value_pln: "10013.00", flags: [] },
  { id: 8, account_id: 3, account_name: "Obligacje", bond_type: "COI", series: "COI0930", quantity: 10, purchase_date: "2026-09-01",
    redeemed_at: null, maturity_date: "2030-09-01", note: "", status: "active", value_pln: "1000.00", flags: [] },
];
const SAVINGS = { account_id: 4, summary: { balance: "40132.18", deposits: "40000.00", interest_net: "132.18", tax: "31.00", accrued: "0", current_rate: "5.20" } } as unknown as SavingsAccountOut;
const JOURNAL: Journal = { count: 2, entries: [
  { id: 2, entry_date: "2026-09-26", body: "Dokupiłem CD Projekt po wynikach.", created_at: "", updated_at: "", target: null },
  { id: 1, entry_date: "2026-09-20", body: "Plan na jesień.", created_at: "", updated_at: "", target: null },
] };

function routes(tiles: unknown[], overrides: Record<string, MockRoute["respond"]> = {}): MockRoute[] {
  return [
    { method: "POST", path: "/api/auth/refresh", respond: () => ({ access_token: "token", token_type: "bearer" }) },
    { path: "/api/auth/me", respond: () => ({ ...USER, preferences: { dashboard: { version: 1, tiles } } }) },
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/portfolio/summary", respond: () => SUMMARY },
    { path: "/api/portfolio/history", respond: () => HISTORY },
    { path: "/api/portfolio/exposure", respond: () => EXPOSURE },
    { path: "/api/positions", respond: () => POSITIONS },
    { path: "/api/portfolio/limits", respond: () => LIMITS },
    { path: "/api/analytics/holdings", respond: () => HOLDINGS },
    { path: "/api/analytics", respond: () => ANALYTICS },
    { path: "/api/history", respond: overrides.history ?? (() => OPERATIONS) },
    { path: "/api/bonds", respond: overrides.bonds ?? (() => BONDS) },
    { path: "/api/savings-accounts/4", respond: () => SAVINGS },
    { path: "/api/journal", respond: overrides.journal ?? (() => JOURNAL) },
  ];
}

describe("small variants show the one thing that matters", () => {
  it("the value with today's change, a metric in one row, a line of the value", async () => {
    mockFetch(routes([
      { id: "s", kind: "summary", variant: "S2", settings: { fields: ["xirr"] } },
      { id: "m", kind: "metric", variant: "S1", settings: { metric: "xirr" } },
      { id: "v", kind: "value_chart", variant: "S2", settings: { range: "1R" } },
    ]));
    renderApp("/");

    const value = await screen.findByRole("region", { name: "Wartość portfela" });
    expect(within(value).getByText(/dziś/)).toBeInTheDocument();
    expect(within(value).queryByText("XIRR")).not.toBeInTheDocument();
    expect(screen.getByRole("region", { name: "XIRR" }).closest("[data-variant]")).toHaveAttribute("data-variant", "S1");
    const chart = screen.getByRole("region", { name: "Wykres wartości" });
    expect(await within(chart).findByRole("img", { name: "Wartość portfela, 1 rok" })).toBeInTheDocument();
    expect(within(chart).getByText(`+0,97${T}%`)).toBeInTheDocument(); // TWR 13.10 → 14.20 over the range
  });

  it("today's biggest rise and fall", async () => {
    mockFetch(routes([{ id: "d", kind: "movers", variant: "S2", settings: { count: 5 } }]));
    renderApp("/");

    const tile = await screen.findByRole("region", { name: "Dziś najbardziej" });
    expect(await within(tile).findByText("CDR")).toBeInTheDocument();
    expect(within(tile).getByText("PKN")).toBeInTheDocument();
  });
});

describe("the new kinds", () => {
  it("currency exposure: the largest foreign currency, or the bar and list", async () => {
    mockFetch(routes([
      { id: "e1", kind: "exposure", variant: "S2", settings: {} },
      { id: "e2", kind: "exposure", variant: "M3", settings: {} },
    ]));
    renderApp("/");

    await screen.findByText("w EUR"); // the small tile replaces its loading section
    const [small, medium] = screen.getAllByRole("region", { name: "Ekspozycja walutowa" });
    expect(within(small!).getByText(`53,2${T}%`)).toBeInTheDocument();
    expect(within(small!).getByText("w EUR")).toBeInTheDocument();
    expect(await within(medium!).findByText("PLN")).toBeInTheDocument();
  });

  it("the latest operations, as many as chosen", async () => {
    mockFetch(routes([{ id: "o", kind: "operations", variant: "M", settings: { count: 3 } }]));
    renderApp("/");

    const tile = await screen.findByRole("region", { name: "Ostatnie operacje" });
    expect(await within(tile).findAllByText("CD Projekt")).toHaveLength(2);
    expect(within(tile).getByRole("link", { name: "Cała historia" })).toHaveAttribute("href", "/historia");
  });

  it("the best and the worst holdings of the period", async () => {
    mockFetch(routes([{ id: "x", kind: "extremes", variant: "M", settings: { count: 2, period: "1d" } }]));
    renderApp("/");

    const tile = await screen.findByRole("region", { name: "Najlepsze i najgorsze" });
    const best = await within(tile).findByRole("list", { name: "Najlepsze" });
    expect(within(best).getByText("Veolia")).toBeInTheDocument();
    expect(within(within(tile).getByRole("list", { name: "Najgorsze" })).getByText("Synektik")).toBeInTheDocument();
  });

  it("cash per account, bonds with the nearest maturity, savings with their rate", async () => {
    mockFetch(routes([
      { id: "c", kind: "cash", variant: "M3", settings: {} },
      { id: "b", kind: "bonds", variant: "S2", settings: {} },
      { id: "s", kind: "savings", variant: "M3", settings: {} },
    ]));
    renderApp("/");

    const cash = await screen.findByRole("region", { name: "Gotówka na kontach" });
    expect(await within(cash).findByText("XTB")).toBeInTheDocument();
    const bonds = screen.getByRole("region", { name: "Obligacje" });
    expect(await within(bonds).findByText("wykup COI0930: 01.09.2030")).toBeInTheDocument();
    const savings = screen.getByRole("region", { name: "Konta oszczędnościowe" });
    expect(await within(savings).findByText(`5,20${T}% rocznie`)).toBeInTheDocument();
  });

  it("the journal's latest entry, or why it is empty", async () => {
    mockFetch(routes([{ id: "j", kind: "journal", variant: "S2", settings: {} }]));
    renderApp("/");

    expect(await screen.findByText("Dokupiłem CD Projekt po wynikach.")).toBeInTheDocument();
    const tile = screen.getByRole("region", { name: "Dziennik" });
    expect(within(tile).getByText("26.09.2026")).toBeInTheDocument();
    expect(within(tile).getByRole("link", { name: "Dziennik" })).toHaveAttribute("href", "/ustawienia/dziennik");
  });

  it("says why a tile without data is empty", async () => {
    mockFetch(routes([
      { id: "j", kind: "journal", variant: "M3", settings: {} },
      { id: "b", kind: "bonds", variant: "M3", settings: {} },
    ], { journal: () => ({ count: 0, entries: [] }), bonds: () => [] }));
    renderApp("/");

    expect(await screen.findByText("Nie ma jeszcze wpisów w dzienniku.")).toBeInTheDocument();
    expect(await screen.findByText("Nie masz obligacji w wybranych kontach.")).toBeInTheDocument();
  });
});
