import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, CLOSED, POSITIONS } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp, type MockRoute } from "../../test/render";
import { salesOf } from "./closedModel";

const T = " ";
const M = "−";

function routes(closed: unknown = CLOSED): MockRoute[] {
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/positions", respond: () => POSITIONS },
    { path: "/api/portfolio/closed", respond: () => closed },
  ];
}

describe("closed investments model", () => {
  it("takes the sales of one instrument on one account only", () => {
    expect(salesOf(CLOSED, CLOSED.investments[0]!).map((s) => s.account_name)).toEqual(["XTB"]);
    expect(salesOf(CLOSED, CLOSED.investments[1]!).map((s) => s.account_name)).toEqual(["IKE"]);
  });
});

describe("closed investments", () => {
  it("switches Pozycje to the closed view with totals and one row per instrument and account", async () => {
    const { user, router } = (mockFetch(routes()), renderApp("/pozycje"));

    await user.click(await screen.findByRole("button", { name: "Zamknięte" }));

    expect(router.state.location.search).toBe("?widok=zamkniete");
    const totals = await screen.findByRole("region", { name: "Wynik zamkniętych" });
    expect(within(totals).getByText("Razem").nextElementSibling).toHaveTextContent(`+301,00${T}zł`);
    expect(within(totals).getByText(/20,1/)).toBeInTheDocument();
    const rows = screen.getAllByRole("button", { expanded: false });
    expect(rows.map((r) => r.textContent)).toEqual([
      expect.stringMatching(/Orlen.*XTB, sprzedane/), expect.stringMatching(/Orlen.*IKE, częściowo/),
    ]);
    expect(within(rows[1]!).getByText(`${M}20,00${T}zł`)).toHaveClass("down");
  });

  it("shows the sales of an investment when its row is opened", async () => {
    mockFetch(routes());
    const { user } = renderApp("/pozycje?widok=zamkniete");

    await user.click(await screen.findByRole("button", { name: /Orlen.*XTB/ }));

    const sales = screen.getByRole("list", { name: "Sprzedaże Orlen, XTB" });
    expect(within(sales).getByText("05.03.2026")).toBeInTheDocument();
    expect(within(sales).getByText("20 szt., 419 dni")).toBeInTheDocument();
    expect(within(sales).queryByText("01.04.2026")).not.toBeInTheDocument();
  });

  it("filters the closed view by account and says when there is nothing closed", async () => {
    const empty = { sales: [], investments: [], totals: { sold_cost_pln: "0.00", realized_pln: "0.00",
      dividends_net_pln: "0.00", fees_pln: "0.00", total_pln: "0.00", return_pct: null } };
    const fetchMock = mockFetch(routes(empty));
    const { user } = renderApp("/pozycje?widok=zamkniete");

    expect(await screen.findByText("Nie masz jeszcze zamkniętych inwestycji.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "IKE" }));
    await screen.findByText("Nie masz jeszcze zamkniętych inwestycji.");
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain("/api/portfolio/closed?account_id=1");
  });
});
