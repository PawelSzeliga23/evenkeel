import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, ANALYTICS, INCOME, INCOME_EMPTY } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp } from "../../test/render";

function routes(answer: (url: URL) => unknown = () => INCOME) {
  return mockFetch([
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/analytics", respond: () => ANALYTICS },
    { path: "/api/analytics/income", respond: answer },
  ]);
}

const group = (name: string) => screen.getByRole("group", { name });
const list = (name: string) => within(screen.getByRole("list", { name })).getAllByRole("listitem");

describe("Dochód i koszty", () => {
  it("asks for the year so far by default and for the chosen period", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/dochod");

    expect(await screen.findByRole("heading", { name: "Dochód i koszty", level: 1 })).toBeInTheDocument();
    await screen.findByRole("group", { name: "Dochód" });
    expect(screen.getByRole("button", { name: "Od pocz. roku" })).toHaveAttribute("aria-pressed", "true");
    await user.click(screen.getByRole("button", { name: "12 mies." }));
    const urls = fetchMock.mock.calls.map(([url]) => String(url)).filter((u) => u.includes("/api/analytics/income"));
    expect(urls.some((u) => u.includes("period=ytd"))).toBe(true);
    expect(urls.some((u) => u.includes("period=12m"))).toBe(true);
  });

  it("shows income, costs and the balance", async () => {
    routes();
    renderApp("/analiza/dochod");

    expect(await screen.findByRole("group", { name: "Dochód" })).toHaveTextContent("+82,34 zł");
    expect(group("Koszty")).toHaveTextContent("−69,10 zł");
    expect(group("Bilans")).toHaveTextContent("+13,24 zł");
  });

  it("lists where the income comes from, gross less tax", async () => {
    routes();
    renderApp("/analiza/dochod");

    await screen.findByRole("list", { name: "Skąd dochód" });
    const [savings, bond, dividends] = list("Skąd dochód");
    expect(savings).toHaveTextContent("brutto 58,10 zł − Belka 11,04 zł");
    expect(savings).toHaveTextContent("+47,06 zł");
    expect(bond).toHaveTextContent("bez podatku");
    expect(dividends).toHaveTextContent("Dywidendy");
    expect(dividends).toHaveTextContent("na razie brak");
  });

  it("lists what the costs are", async () => {
    routes();
    renderApp("/analiza/dochod");

    await screen.findByRole("list", { name: "Na co koszty" });
    const rows = list("Na co koszty");
    expect(rows).toHaveLength(4);
    expect(rows[0]).toHaveTextContent("0,5 % przy zakupach i sprzedaży w obcej walucie · 12 transakcji");
    expect(rows[0]).toHaveTextContent("−58,06 zł");
    expect(rows[3]).toHaveTextContent("XTB: 0 % do 100 tys. € obrotu");
  });

  it("shows a month's split after a tap on its column, and the months from the newest", async () => {
    routes();
    const { user } = renderApp("/analiza/dochod");

    await user.click(await screen.findByRole("button", { name: /^wrz 2026: / }));
    const details = screen.getByRole("region", { name: "wrz 2026" });
    expect(details).toHaveTextContent("odsetki +74,84 zł");
    expect(details).toHaveTextContent("podatki −11,04 zł");
    expect(details).toHaveTextContent("bilans +25,14 zł");
    const rows = within(screen.getByRole("table", { name: "Miesiące" })).getAllByRole("row").slice(1);
    expect(rows.map((row) => (row as HTMLTableRowElement).cells[0]!.textContent)).toEqual(["paź 2026", "wrz 2026", "sie 2026"]);
  });

  it("says when there is nothing yet", async () => {
    routes(() => INCOME_EMPTY);
    renderApp("/analiza/dochod");

    expect(await screen.findByText("Nie ma jeszcze danych do pokazania.")).toBeInTheDocument();
  });

  it("shows the year so far on Analiza with a way to the details", async () => {
    routes();
    const { user } = renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Dochód i koszty" });
    expect(await within(card).findByText("+82,34 zł")).toBeInTheDocument();
    expect(within(card).getByText("−69,10 zł")).toBeInTheDocument();
    await user.click(within(card).getByRole("link", { name: "Szczegóły dochodu i kosztów" }));
    expect(await screen.findByRole("heading", { name: "Dochód i koszty", level: 1 })).toBeInTheDocument();
  });
});
