import { fireEvent, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { todayIso } from "../../format";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";

const CASH = { id: 4, name: "Portfel domowy", kind: "cash", wrapper: "regular", broker: null,
  external_account_number: null, currency: "PLN", created_at: "2026-09-01T10:00:00" };

function routes(accounts: unknown[], sent: { path: string; body: unknown }[], answer?: () => unknown): MockRoute[] {
  const created: unknown[] = [];
  const record = (path: string) => (_url: URL, init: RequestInit) => {
    sent.push({ path, body: JSON.parse(String(init.body)) });
    return undefined;
  };
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => [...accounts, ...created] },
    { method: "POST", path: "/api/accounts", respond: (u, i) => { record("accounts")(u, i); created.push({ ...CASH, id: 9 }); return json(201, { ...CASH, id: 9 }); } },
    { method: "POST", path: "/api/transactions", respond: (u, i) => { record("transactions")(u, i); return answer ? answer() : json(201, { id: 1 }); } },
  ];
}

describe("cash operation form", () => {
  it("creates the first cash account and saves a withdrawal on it", async () => {
    const sent: { path: string; body: unknown }[] = [];
    mockFetch(routes([], sent));
    const { user } = renderApp("/dodaj/operacja");

    await user.type(await screen.findByLabelText("Nazwa nowego konta"), "Portfel domowy");
    await user.click(screen.getByRole("button", { name: "Wypłata" }));
    await user.type(screen.getByLabelText("Kwota"), "1 234,5");
    await user.type(screen.getByLabelText("Opis"), "remont");
    await user.click(screen.getByRole("button", { name: "Zapisz operację" }));

    expect(await screen.findByText("Operacja zapisana.")).toBeInTheDocument();
    expect(sent).toEqual([
      { path: "accounts", body: { name: "Portfel domowy", kind: "cash", wrapper: "regular" } },
      { path: "transactions", body: { account_id: 9, type: "withdrawal", amount: "1234.5", date: todayIso(), comment: "remont" } },
    ]);
  });

  it("checks the amount before asking the API", async () => {
    const sent: { path: string; body: unknown }[] = [];
    mockFetch(routes([CASH], sent));
    const { user } = renderApp("/dodaj/operacja");

    await user.type(await screen.findByLabelText("Kwota"), "12,345");
    await user.click(screen.getByRole("button", { name: "Zapisz operację" }));

    expect(await screen.findByText("Podaj kwotę, np. 1 250,50.")).toBeInTheDocument();
    expect(sent).toEqual([]);
  });

  it("shows the API's answer next to the field it is about and keeps what was typed", async () => {
    const sent: { path: string; body: unknown }[] = [];
    mockFetch(routes([CASH], sent, () => json(422, { code: "date_in_future", message: "Data operacji nie może być z przyszłości.", details: {} })));
    const { user } = renderApp("/dodaj/operacja");

    await user.type(await screen.findByLabelText("Kwota"), "50");
    fireEvent.change(screen.getByLabelText("Data"), { target: { value: "2026-09-01" } });
    await user.click(screen.getByRole("button", { name: "Zapisz operację" }));

    expect(await screen.findByText("Data operacji nie może być z przyszłości.")).toBeInTheDocument();
    expect(screen.getByLabelText("Kwota")).toHaveValue("50");
    expect(sent[0]).toMatchObject({ path: "transactions", body: { account_id: 4, date: "2026-09-01" } });
  });

  it("keeps saving on the account it just created", async () => {
    const sent: { path: string; body: unknown }[] = [];
    mockFetch(routes([], sent));
    const { user } = renderApp("/dodaj/operacja");

    await user.type(await screen.findByLabelText("Nazwa nowego konta"), "Portfel domowy");
    await user.type(screen.getByLabelText("Kwota"), "10");
    await user.click(screen.getByRole("button", { name: "Zapisz operację" }));
    await user.click(await screen.findByRole("button", { name: "Dodaj kolejną" }));
    await user.type(await screen.findByLabelText("Kwota"), "20");
    await user.click(screen.getByRole("button", { name: "Zapisz operację" }));
    expect(await screen.findByText("Operacja zapisana.")).toBeInTheDocument();

    expect(sent.filter((s) => s.path === "accounts")).toHaveLength(1);
    const transactions = sent.filter((s) => s.path === "transactions");
    expect(transactions).toHaveLength(2);
    expect(transactions.map((t) => (t.body as { account_id: number }).account_id)).toEqual([9, 9]);
  });

  it("does not create the account twice when the operation failed and is sent again", async () => {
    const sent: { path: string; body: unknown }[] = [];
    let calls = 0;
    mockFetch(routes([], sent, () => (++calls === 1
      ? json(422, { code: "date_in_future", message: "Data operacji nie może być z przyszłości.", details: {} })
      : json(201, { id: 1 }))));
    const { user } = renderApp("/dodaj/operacja");

    await user.type(await screen.findByLabelText("Nazwa nowego konta"), "Portfel domowy");
    await user.type(screen.getByLabelText("Kwota"), "10");
    await user.click(screen.getByRole("button", { name: "Zapisz operację" }));
    expect(await screen.findByText("Data operacji nie może być z przyszłości.")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Zapisz operację" }));
    expect(await screen.findByText("Operacja zapisana.")).toBeInTheDocument();

    expect(sent.filter((s) => s.path === "accounts")).toHaveLength(1);
    expect(sent.filter((s) => s.path === "transactions")).toHaveLength(2);
  });

  it("names the account's currency in the amount hint and offers Dodaj and Historia after saving", async () => {
    const sent: { path: string; body: unknown }[] = [];
    mockFetch(routes([{ ...CASH, id: 5, name: "Gotówka EUR", currency: "EUR" }], sent));
    const { user } = renderApp("/dodaj/operacja");

    expect(await screen.findByText("W walucie konta (EUR), bez znaku minus.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Kwota"), "10");
    await user.click(screen.getByRole("button", { name: "Zapisz operację" }));

    expect(await screen.findByRole("link", { name: "Wróć do Dodaj" })).toHaveAttribute("href", "/dodaj");
    expect(screen.getByRole("link", { name: "Zobacz historię" })).toHaveAttribute("href", "/historia");
  });
});
