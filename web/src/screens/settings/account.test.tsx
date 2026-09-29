import { screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";

function routes(calls: { method: string; body?: unknown }[]): MockRoute[] {
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/instruments", respond: () => [] },
    { path: "/api/accounts/1/usage", respond: () => ({ transactions: 42, imports: 3, bond_holdings: 0, savings_entries: 0 }) },
    { method: "PATCH", path: "/api/accounts/1", respond: (_u, init) => {
      const body = JSON.parse(String(init.body));
      calls.push({ method: "PATCH", body });
      return { ...ACCOUNTS[0], ...body };
    } },
    { method: "DELETE", path: "/api/accounts/1", respond: () => { calls.push({ method: "DELETE" }); return json(204, undefined); } },
  ];
}

describe("account settings", () => {
  it("renames the account and changes its type", async () => {
    const calls: { method: string; body?: unknown }[] = [];
    mockFetch(routes(calls));
    const { user } = renderApp("/ustawienia/konta/1");

    const name = await screen.findByLabelText("Nazwa");
    await user.clear(name);
    await user.type(name, "XTB IKE");
    await user.click(screen.getByRole("button", { name: "IKZE" }));
    await user.click(screen.getByRole("button", { name: "Zapisz zmiany" }));

    expect(await screen.findByText("Zapisano.")).toBeInTheDocument();
    expect(calls).toEqual([{ method: "PATCH", body: { name: "XTB IKE", wrapper: "ikze" } }]);
  });

  it("deletes only after the account's name is typed, and says what goes with it", async () => {
    const calls: { method: string; body?: unknown }[] = [];
    mockFetch(routes(calls));
    const { user, router } = renderApp("/ustawienia/konta/1");

    await user.click(await screen.findByRole("button", { name: "Usuń konto" }));
    expect(await screen.findByText(/42 operacje, 3 importy/)).toBeInTheDocument();
    const confirm = screen.getByRole("button", { name: "Usuń na zawsze" });
    expect(confirm).toBeDisabled();
    await user.type(screen.getByLabelText("Wpisz nazwę konta, aby potwierdzić"), "ike");
    expect(confirm).toBeDisabled();
    await user.clear(screen.getByLabelText("Wpisz nazwę konta, aby potwierdzić"));
    await user.type(screen.getByLabelText("Wpisz nazwę konta, aby potwierdzić"), " IKE ");
    await user.click(confirm);

    expect(await screen.findByText("Konto usunięte.")).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/ustawienia");
    expect(calls).toEqual([{ method: "DELETE" }]);
  });

  it("says when the account does not exist", async () => {
    mockFetch(routes([]));
    renderApp("/ustawienia/konta/999");

    expect(await screen.findByText("Nie znaleziono konta.")).toBeInTheDocument();
    for (const link of screen.getAllByRole("link", { name: "Ustawienia" })) expect(link).toHaveAttribute("href", "/ustawienia");
    expect(screen.queryByLabelText("Nazwa")).not.toBeInTheDocument();
  });
});
