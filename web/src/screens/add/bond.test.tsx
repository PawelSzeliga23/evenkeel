import { fireEvent, screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

const BONDS = { id: 3, name: "Obligacje", kind: "bonds", wrapper: "regular", broker: null,
  external_account_number: null, currency: "PLN", created_at: "2026-09-01T10:00:00" };

describe("bond purchase form", () => {
  it("asks for the rates of a series the app does not know and saves them with the purchase", async () => {
    const bodies: Record<string, unknown>[] = [];
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => [BONDS] },
      {
        method: "POST", path: "/api/bonds",
        respond: (_u, init) => {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          bodies.push(body);
          return body.first_period_rate
            ? json(201, { id: 7, series: "EDO0126" })
            : json(422, { code: "series_unknown", message: "Seria EDO0126 nie jest jeszcze w aplikacji. Podaj jej oprocentowanie.", details: {} });
        },
      },
    ]);
    const { user, router } = renderApp("/dodaj/obligacja");

    await user.type(await screen.findByLabelText("Liczba obligacji"), "10");
    expect(screen.getByText("Wartość nominalna 1 000,00 zł")).toBeInTheDocument();
    fireEvent.change(screen.getByLabelText("Data zakupu"), { target: { value: "2026-01-15" } });
    await user.click(screen.getByRole("button", { name: "Zapisz zakup" }));

    expect(await screen.findByText("Seria EDO0126 nie jest jeszcze w aplikacji. Podaj jej oprocentowanie.")).toBeInTheDocument();
    await user.type(screen.getByLabelText("Oprocentowanie w pierwszym roku (%)"), "6,00");
    await user.type(screen.getByLabelText("Marża (p.p.)"), "2");
    expect(screen.getByLabelText("Liczba obligacji")).toHaveValue("10");
    await user.click(screen.getByRole("button", { name: "Zapisz zakup" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/pozycje/obligacje/7"));
    expect(bodies).toEqual([
      { account_id: 3, bond_type: "EDO", quantity: 10, purchase_date: "2026-01-15" },
      { account_id: 3, bond_type: "EDO", quantity: 10, purchase_date: "2026-01-15", first_period_rate: "6.00", margin: "2" },
    ]);
  });

  it("creates a new bonds account only once when the first save asks for series rates", async () => {
    const created: Record<string, unknown>[] = [];
    const bondBodies: Record<string, unknown>[] = [];
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => (created.length ? [{ ...BONDS, id: 9 }] : []) },
      {
        method: "POST", path: "/api/accounts",
        respond: (_u, init) => { created.push(JSON.parse(String(init.body))); return json(201, { ...BONDS, id: 9 }); },
      },
      {
        method: "POST", path: "/api/bonds",
        respond: (_u, init) => {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          bondBodies.push(body);
          return body.first_period_rate
            ? json(201, { id: 7, series: "EDO0126" })
            : json(422, { code: "series_unknown", message: "Seria EDO0126 nie jest jeszcze w aplikacji. Podaj jej oprocentowanie.", details: {} });
        },
      },
    ]);
    const { user, router } = renderApp("/dodaj/obligacja");

    await user.type(await screen.findByLabelText("Liczba obligacji"), "10");
    fireEvent.change(screen.getByLabelText("Data zakupu"), { target: { value: "2026-01-15" } });
    await user.click(screen.getByRole("button", { name: "Zapisz zakup" }));

    await screen.findByText("Seria EDO0126 nie jest jeszcze w aplikacji. Podaj jej oprocentowanie.");
    await user.type(screen.getByLabelText("Oprocentowanie w pierwszym roku (%)"), "6,00");
    await user.type(screen.getByLabelText("Marża (p.p.)"), "2");
    await user.click(screen.getByRole("button", { name: "Zapisz zakup" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/pozycje/obligacje/7"));
    expect(created).toHaveLength(1);
    expect(bondBodies.map((b) => b.account_id)).toEqual([9, 9]);
  });

  it("wants a whole number of bonds", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [BONDS] }]);
    const { user } = renderApp("/dodaj/obligacja");

    await user.type(await screen.findByLabelText("Liczba obligacji"), "2,5");
    await user.click(screen.getByRole("button", { name: "Zapisz zakup" }));

    expect(await screen.findByText("Podaj liczbę całkowitą, co najmniej 1.")).toBeInTheDocument();
  });
});
