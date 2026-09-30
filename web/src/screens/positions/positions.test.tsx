import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, DETAIL, POSITIONS, position } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";
import { groupPositions, subtitleFor } from "./model";

const S = "\u00a0";
const M = "\u2212";
const T = " ";

const LIST: MockRoute[] = [
  ...SIGNED_IN,
  { path: "/api/accounts", respond: () => ACCOUNTS },
  { path: "/api/positions", respond: () => POSITIONS },
];

describe("positions model", () => {
  it("groups instruments, bonds and accounts with exact totals", () => {
    expect(groupPositions(POSITIONS).map((g) => [g.title, g.total, g.items.length])).toEqual([
      ["Akcje i ETF-y", "115848.89", 4], ["Obligacje", "10013.00", 1], ["Konta i gotówka", "44265.67", 2],
    ]);
    expect(groupPositions([])).toEqual([]);
  });

  it("describes each row by what it is", () => {
    expect(POSITIONS.map(subtitleFor)).toEqual([
      `IKE, 42 szt., udział 35,8${S}%`, `XTB, 42 szt., udział 17,1${S}%`, `XTB, 48 szt., udział 6,1${S}%`,
      `XTB, 110 szt., udział 3,9${S}%`, "Obligacje, 100 szt.", "Konto oszczędnościowe", "XTB, PLN",
    ]);
  });

  it("totals and lists the payout value, not the market value", () => {
    const groups = groupPositions([
      position({ value_pln: "1000.00", exit_cost_pln: "5.00", payout_pln: "995.00" }),
      position({ instrument_id: 11, value_pln: "500.00", payout_pln: "500.00" }),
    ]);
    expect(groups[0]!.total).toBe("1495.00");
  });
});

describe("positions screen", () => {
  it("lists groups with totals, flags and links to instrument details", async () => {
    mockFetch(LIST);
    renderApp("/pozycje");

    const stocks = await screen.findByRole("region", { name: "Akcje i ETF-y" });
    expect(within(stocks).getByText(`115${T}848,89${T}zł`)).toBeInTheDocument();
    expect(within(stocks).getByRole("link", { name: /CD Projekt/ })).toHaveAttribute("href", "/pozycje/2/12");
    expect(within(stocks).getByText("cena z XTB")).toBeInTheDocument();
    expect(within(stocks).getByText(`${M}612,50${T}zł`)).toHaveClass("down");
    const accounts = screen.getByRole("region", { name: "Konta i gotówka" });
    expect(within(accounts).getByRole("link", { name: /Konto oszczędnościowe/ })).toHaveAttribute("href", "/pozycje/oszczednosci/4");
    expect(within(accounts).getAllByRole("link")).toHaveLength(1);
    expect(within(screen.getByRole("region", { name: "Obligacje" })).getByRole("link", { name: /EDO0936/ }))
      .toHaveAttribute("href", "/pozycje/obligacje/7");
    expect(within(accounts).getByText("Gotówka")).toBeInTheDocument();
  });

  it("filters by account", async () => {
    const fetchMock = mockFetch(LIST);
    const { user } = renderApp("/pozycje");
    await user.click(await screen.findByRole("button", { name: "IKE" }));
    await screen.findByRole("region", { name: "Akcje i ETF-y" });
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain("/api/positions?account_id=1");
  });

  it("invites an empty portfolio to import", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/positions", respond: () => [] }]);
    renderApp("/pozycje");
    expect(await screen.findByText("Nie masz jeszcze pozycji. Wgraj eksport z XTB, żeby je zobaczyć.")).toBeInTheDocument();
  });

  it("shows each row's payout value", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/positions", respond: () => [position({ value_pln: "1000.00", exit_cost_pln: "5.00", payout_pln: "995.00" })] }]);
    renderApp("/pozycje");

    const group = await screen.findByRole("region", { name: "Akcje i ETF-y" });
    expect(within(group).getAllByText(`995,00${T}zł`).length).toBe(2); // the group total and the row
    expect(within(group).queryByText(`1${T}000,00${T}zł`)).not.toBeInTheDocument();
  });
});

describe("position detail", () => {
  it("shows the price in the currency the API gives and lots without an open price without 'po'", async () => {
    const detail = {
      ...DETAIL,
      position: { ...DETAIL.position, currency: "EUR", price: "2152.1500", price_currency: "PLN" },
      lots: [{ ...DETAIL.lots[0]!, open_price: null }],
      average_price: null,
    };
    mockFetch([...SIGNED_IN, { path: "/api/positions/2/12", respond: () => detail }]);
    renderApp("/pozycje/2/12");

    expect(await screen.findByText(`2${T}152,15${T}PLN`)).toBeInTheDocument();
    expect(screen.queryByText("Średnia cena")).not.toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Partie" })).getByText("30 szt.")).toBeInTheDocument();
  });

  it("shows the summary, the gain breakdown, lots, sales, income, operations and the XTB check", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/positions/2/12", respond: () => DETAIL }]);
    renderApp("/pozycje/2/12");

    expect(await screen.findByRole("heading", { name: "CD Projekt" })).toBeInTheDocument();
    expect(screen.getByText(`232,47${T}PLN`)).toBeInTheDocument();
    expect(screen.getByText("Ilość").nextElementSibling).toHaveTextContent("48 szt.");
    expect(screen.getByText("Ilość").nextElementSibling!.textContent).not.toContain("\\u00a0");
    expect(screen.getByText("Średnia cena").nextElementSibling).toHaveTextContent(`192,2338${T}PLN`);
    expect(screen.getByText("z XTB, 26.09.2026")).toBeInTheDocument();

    const gain = screen.getByRole("region", { name: "Zysk" });
    expect(within(gain).getByText("Dywidendy")).toBeInTheDocument();
    expect(within(gain).getByText(`${M}12,00${T}zł`)).toBeInTheDocument();

    const lots = screen.getByRole("region", { name: "Partie" });
    expect(within(lots).getByText(`30 szt. po 180,2${T}PLN`)).toBeInTheDocument();
    expect(within(lots).getByText("502 dni, SL 150")).toBeInTheDocument();
    expect(within(lots).getByText("1 dzień")).toBeInTheDocument();

    expect(screen.getByRole("region", { name: "Sprzedaże" })).toHaveTextContent("333 dni");
    expect(screen.getByRole("region", { name: "Dywidendy i odsetki" })).toHaveTextContent("Dywidenda");
    expect(screen.getByRole("region", { name: "Operacje" })).toHaveTextContent("Kupno");
    expect(screen.getByText("Niezgodność z XTB")).toBeInTheDocument();
    expect(screen.getByText("XTB: 50 szt., wyliczone: 48 szt., stan z 26.09.2026, 12:00")).toBeInTheDocument();
  });

  it("says when the position is not there", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/positions/2/99", respond: () => json(404, { code: "not_found", message: "Nie znaleziono.", details: {} }) }]);
    renderApp("/pozycje/2/99");
    expect(await screen.findByRole("alert")).toHaveTextContent("Nie znaleziono.");
    expect(within(screen.getByRole("main")).getByRole("link", { name: "Pozycje" })).toHaveAttribute("href", "/pozycje");
  });
});
