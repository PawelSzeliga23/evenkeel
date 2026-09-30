import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

const base = { instrument_id: null, ticker: null, name: null, quantity: null, price: null, currency: "PLN", tax: null, note: "", delete: null };
const PAGE_1 = {
  items: [
    { ...base, id: "scap:5:2026-09", kind: "savings_interest", type: "savings_interest", date: "2026-09-30", account_id: 5, account_name: "Oszczędności", amount: "32.18", amount_pln: "32.18", tax: "7.55" },
    { ...base, id: "tx:2", kind: "transaction", type: "buy", date: "2026-09-26", account_id: 1, account_name: "IKE", instrument_id: 12, ticker: "CDR.PL", name: "CD Projekt", quantity: "2", price: "250", amount: "-500.0000", amount_pln: "-500.0000" },
  ],
  next_cursor: "2026-09-26|tx:2",
};
const PAGE_2 = {
  items: [{ ...base, id: "tx:1", kind: "transaction", type: "deposit", date: "2026-09-26", account_id: 2, account_name: "XTB", amount: "1000.0000", amount_pln: "1000.0000", note: "pensja", delete: { target: "transaction", id: 1 } }],
  next_cursor: null,
};

function routes(seen: URL[], deleted: string[]) {
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/history", respond: (url: URL) => { seen.push(url); return url.searchParams.get("cursor") ? PAGE_2 : PAGE_1; } },
    { method: "DELETE", path: "/api/transactions/1", respond: (url: URL) => { deleted.push(url.pathname); return json(204, undefined); } },
  ];
}

describe("history", () => {
  it("lists entries by day and loads more", async () => {
    const seen: URL[] = [];
    mockFetch(routes(seen, []));
    const { user } = renderApp("/historia");

    expect(await screen.findByText("Odsetki dopisane")).toBeInTheDocument();
    expect(screen.getByText("CD Projekt")).toBeInTheDocument();
    expect(screen.getByText("\u2212500,00 zł")).toHaveClass("down");
    await user.click(screen.getByRole("button", { name: "Pokaż więcej" }));

    expect(await screen.findByText("pensja", { exact: false })).toBeInTheDocument();
    expect(seen.at(-1)!.searchParams.get("cursor")).toBe("2026-09-26|tx:2");
    expect(screen.queryByRole("button", { name: "Pokaż więcej" })).not.toBeInTheDocument();
  });

  it("sends the filters and the search to the API", async () => {
    const seen: URL[] = [];
    mockFetch(routes(seen, []));
    const { user } = renderApp("/historia");

    await user.click(await screen.findByRole("button", { name: "IKE" }));
    await user.selectOptions(screen.getByLabelText("Rodzaj"), "buy");
    await user.type(screen.getByLabelText("Szukaj"), "projekt");

    await waitFor(() => {
      const last = seen.at(-1)!.searchParams;
      expect([last.get("account_id"), last.get("type"), last.get("q")]).toEqual(["1", "buy", "projekt"]);
    });
    const withQuery = seen.filter((u) => u.searchParams.get("q"));
    expect(withQuery).toHaveLength(1);
    expect(withQuery[0]!.searchParams.get("q")).toBe("projekt");
  });

  it("deletes a manual entry after a confirmation", async () => {
    const deleted: string[] = [];
    mockFetch(routes([], deleted));
    const { user } = renderApp("/historia");

    await user.click(await screen.findByRole("button", { name: "Pokaż więcej" }));
    const row = (await screen.findByText("pensja", { exact: false })).closest("li")!;
    await user.click(within(row).getByRole("button", { name: "Usuń" }));
    expect(screen.getByText("Usunąć: Wpłata 1 000,00 zł z 26.09.2026?")).toBeInTheDocument();
    await user.click(within(screen.getByRole("group", { name: "Potwierdzenie" })).getByRole("button", { name: "Usuń" }));

    await waitFor(() => expect(deleted).toEqual(["/api/transactions/1"]));
    await waitFor(() => expect(screen.queryByRole("group", { name: "Potwierdzenie" })).not.toBeInTheDocument());
  });

  it("shows a foreign currency code, not zł, in the row and the confirmation", async () => {
    const usd = { ...base, id: "tx:9", kind: "transaction", type: "fee", date: "2026-09-25", account_id: 2, account_name: "XTB", currency: "USD", amount: "-12.50", amount_pln: "-50.00", delete: { target: "transaction", id: 9 } };
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS }, { path: "/api/history", respond: () => ({ items: [usd], next_cursor: null }) }]);
    const { user } = renderApp("/historia");

    const amount = await screen.findByText("\u221212,50 USD");
    expect(amount).toHaveClass("down");
    expect(screen.queryByText(/d zł/)).not.toBeInTheDocument();
    await user.click(within(amount.closest("li")!).getByRole("button", { name: "Usuń" }));
    const group = screen.getByRole("group", { name: "Potwierdzenie" });
    expect(group).toHaveTextContent("12,50 USD");
    expect(group).not.toHaveTextContent("zł");
  });

  it.each([
    ["bond", { target: "bond", id: 7 }, "/api/bonds/7"],
    ["savings_flow", { target: "savings_flow", id: 4 }, "/api/savings-accounts/5/flows/4"],
  ])("deletes a %s entry through its own endpoint", async (_name, target, path) => {
    const deleted: string[] = [];
    const item = { ...base, id: "x:1", kind: "savings_flow", type: "savings_deposit", date: "2026-09-20", account_id: 5, account_name: "Oszczędności", amount: "100.00", amount_pln: "100.00", delete: target };
    mockFetch([
      ...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/history", respond: () => ({ items: [item], next_cursor: null }) },
      { method: "DELETE", path, respond: (url: URL) => { deleted.push(url.pathname); return json(204, undefined); } },
    ]);
    const { user } = renderApp("/historia");

    await user.click(await screen.findByRole("button", { name: "Usuń" }));
    await user.click(within(screen.getByRole("group", { name: "Potwierdzenie" })).getByRole("button", { name: "Usuń" }));
    await waitFor(() => expect(deleted).toEqual([path]));
  });

  it("shows a failed delete next to the entry and keeps it", async () => {
    const item = { ...base, id: "sf:4", kind: "savings_flow", type: "savings_deposit", date: "2026-09-20", account_id: 5, account_name: "Oszczędności", amount: "100.00", amount_pln: "100.00", note: "wpis", delete: { target: "savings_flow", id: 4 } };
    mockFetch([
      ...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/history", respond: () => ({ items: [item], next_cursor: null }) },
      { method: "DELETE", path: "/api/savings-accounts/5/flows/4", respond: () => json(409, { code: "flow_needed", message: "Bez tego wpisu saldo spadłoby poniżej zera.", details: {} }) },
    ]);
    const { user } = renderApp("/historia");

    await user.click(await screen.findByRole("button", { name: "Usuń" }));
    await user.click(within(screen.getByRole("group", { name: "Potwierdzenie" })).getByRole("button", { name: "Usuń" }));

    const alert = await screen.findByRole("alert");
    expect(alert).toHaveTextContent("Bez tego wpisu saldo spadłoby poniżej zera.");
    const row = screen.getByRole("listitem");
    expect(row).toContainElement(alert);
    expect(screen.queryByRole("group", { name: "Potwierdzenie" })).not.toBeInTheDocument();
  });

  it("shows a transaction's price with two decimals and its currency", async () => {
    const buy = { ...PAGE_1.items[1]!, quantity: "2", price: "250.0000", price_currency: "PLN" };
    mockFetch([
      ...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/history", respond: () => ({ items: [buy], next_cursor: null }) },
    ]);
    renderApp("/historia");

    expect(await screen.findByText(/2 szt. po 250,00 PLN/)).toBeInTheDocument();
  });
});
