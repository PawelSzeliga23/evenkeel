import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

const ACCOUNT = { id: 5, name: "Konto w banku", kind: "savings", wrapper: "regular", broker: null,
  external_account_number: null, currency: "PLN", created_at: "2026-09-01T10:00:00" };
const SAVINGS = {
  account_id: 5, capitalization: "monthly",
  rates: [{ id: 1, valid_from: "2026-09-01", annual_rate: "5.0000" }],
  balances: [],
  flows: [{ id: 11, date: "2026-09-01", amount: "10000.0000", note: "" }, { id: 12, date: "2026-09-20", amount: "-500.0000", note: "wakacje" }],
  summary: { balance: "9532.18", deposits: "9500.00", interest_net: "32.18", tax: "7.55", accrued: "12.40", current_rate: "5.0000" },
  capitalizations: [{ period_end: "2026-09-30", gross: "39.73", tax: "7.55", net: "32.18" }],
};

function routes(calls: { method: string; path: string; body?: unknown }[], deleteAnswer?: () => unknown) {
  const log = (method: string) => (url: URL, init: RequestInit) => {
    calls.push({ method, path: url.pathname, ...(init.body ? { body: JSON.parse(String(init.body)) } : {}) });
  };
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => [ACCOUNT] },
    { path: "/api/savings-accounts/5", respond: () => SAVINGS },
    { method: "POST", path: "/api/savings-accounts/5/flows", respond: (u: URL, i: RequestInit) => { log("POST")(u, i); return json(201, { id: 13 }); } },
    { method: "POST", path: "/api/savings-accounts/5/rates", respond: (u: URL, i: RequestInit) => { log("POST")(u, i); return json(201, { id: 2 }); } },
    { method: "DELETE", path: /^\/api\/savings-accounts\/5\/flows\/\d+$/, respond: (u: URL, i: RequestInit) => { log("DELETE")(u, i); return deleteAnswer ? deleteAnswer() : json(204, undefined); } },
  ];
}

describe("savings account detail", () => {
  it("shows the balance, the interest so far and the interest by month", async () => {
    mockFetch(routes([]));
    renderApp("/pozycje/oszczednosci/5");

    expect(await screen.findByRole("heading", { name: "Konto w banku" })).toBeInTheDocument();
    expect(screen.getByText("Odsetki narosłe od ostatniej kapitalizacji: 12,40 zł")).toBeInTheDocument();
    expect(screen.getByText("Odsetki dopisane (netto)").nextElementSibling).toHaveTextContent("32,18 zł");
    expect(within(screen.getByRole("region", { name: "Odsetki" })).getByText("wrzesień 2026")).toBeInTheDocument();
    expect(within(screen.getByRole("region", { name: "Wpłaty i wypłaty" })).getByText("wakacje")).toBeInTheDocument();
  });

  it("adds a withdrawal and changes the rate", async () => {
    const calls: { method: string; path: string; body?: unknown }[] = [];
    mockFetch(routes(calls));
    const { user } = renderApp("/pozycje/oszczednosci/5");

    await user.click(await screen.findByRole("button", { name: "Wpłata lub wypłata" }));
    await user.click(screen.getByRole("button", { name: "Wypłata" }));
    await user.type(screen.getByLabelText("Kwota"), "500");
    fireEvent.change(screen.getByLabelText("Data"), { target: { value: "2026-09-25" } });
    await user.click(screen.getByRole("button", { name: "Zapisz" }));
    await user.click(await screen.findByRole("button", { name: "Zmień oprocentowanie" }));
    await user.type(screen.getByLabelText("Nowe oprocentowanie (%)"), "4,5");
    fireEvent.change(screen.getByLabelText("Obowiązuje od"), { target: { value: "2026-10-01" } });
    await user.click(screen.getByRole("button", { name: "Zapisz oprocentowanie" }));

    await waitFor(() => expect(calls).toEqual([
      { method: "POST", path: "/api/savings-accounts/5/flows", body: { date: "2026-09-25", amount: "-500", note: "" } },
      { method: "POST", path: "/api/savings-accounts/5/rates", body: { valid_from: "2026-10-01", annual_rate: "4.5" } },
    ]));
  });

  it("says why a needed deposit cannot be deleted", async () => {
    const calls: { method: string; path: string }[] = [];
    mockFetch(routes(calls, () => json(409, { code: "flow_needed", message: "Bez tego wpisu saldo spadłoby poniżej zera.", details: {} })));
    const { user } = renderApp("/pozycje/oszczednosci/5");

    const flows = await screen.findByRole("region", { name: "Wpłaty i wypłaty" });
    await user.click(within(flows).getAllByRole("button", { name: "Usuń" })[1]!);
    expect(screen.getByText("Usunąć wpłatę 10 000,00 zł z 01.09.2026?")).toBeInTheDocument();
    await user.click(within(screen.getByRole("group", { name: "Potwierdzenie" })).getByRole("button", { name: "Usuń" }));

    expect(await screen.findByText("Bez tego wpisu saldo spadłoby poniżej zera.")).toBeInTheDocument();
    expect(calls.map((c) => c.path)).toEqual(["/api/savings-accounts/5/flows/11"]);
  });
});
