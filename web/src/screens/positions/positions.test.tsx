import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, DETAIL, POSITIONS } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";
import { groupPositions, subtitleFor } from "./model";

const S = " ";
const M = "−";
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
    expect(within(accounts).queryByRole("link")).not.toBeInTheDocument();
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
});

describe("position detail", () => {
  it("shows the summary, the gain breakdown, lots, sales, income, operations and the XTB check", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/positions/2/12", respond: () => DETAIL }]);
    renderApp("/pozycje/2/12");

    expect(await screen.findByRole("heading", { name: "CD Projekt" })).toBeInTheDocument();
    expect(screen.getByText(`232,47${T}PLN`)).toBeInTheDocument();
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
