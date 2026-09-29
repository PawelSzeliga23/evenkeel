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
    expect(seen.filter((u) => u.searchParams.get("q") === "p")).toHaveLength(0);
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
});
