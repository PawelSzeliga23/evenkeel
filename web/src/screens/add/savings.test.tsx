import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

describe("new savings account form", () => {
  it("creates the account with its rate, capitalization and first deposit in one request", async () => {
    const bodies: unknown[] = [];
    mockFetch([
      ...SIGNED_IN,
      { method: "POST", path: "/api/savings-accounts", respond: (_u, init) => { bodies.push(JSON.parse(String(init.body))); return json(201, { account_id: 5 }); } },
    ]);
    const { user, router } = renderApp("/dodaj/konto-oszczednosciowe");

    await user.type(await screen.findByLabelText("Nazwa konta"), "Konto w banku");
    await user.click(screen.getByRole("button", { name: "IKE" }));
    await user.type(screen.getByLabelText("Oprocentowanie roczne (%)"), "5,5");
    fireEvent.change(screen.getByLabelText("Obowiązuje od"), { target: { value: "2026-09-01" } });
    await user.click(screen.getByRole("button", { name: "Dzienna" }));
    await user.type(screen.getByLabelText("Pierwsza wpłata"), "10 000");
    fireEvent.change(screen.getByLabelText("Data wpłaty"), { target: { value: "2026-09-02" } });
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/pozycje"));
    expect(bodies).toEqual([{
      name: "Konto w banku", wrapper: "ike", capitalization: "daily", annual_rate: "5.5", rate_valid_from: "2026-09-01",
      first_deposit: { date: "2026-09-02", amount: "10000", note: "" },
    }]);
  });

  it("points at every missing field before sending", async () => {
    const fetchMock = mockFetch(SIGNED_IN);
    const { user } = renderApp("/dodaj/konto-oszczednosciowe");

    await user.click(await screen.findByRole("button", { name: "Załóż konto" }));

    expect(screen.getByText("Podaj nazwę konta.")).toBeInTheDocument();
    expect(screen.getByText("Podaj oprocentowanie, np. 5,35.")).toBeInTheDocument();
    expect(screen.getByText("Podaj kwotę, np. 1 250,50.")).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/api/savings-accounts"))).toBe(false);
  });
});
