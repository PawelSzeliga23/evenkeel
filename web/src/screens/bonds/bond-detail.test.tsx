import { fireEvent, screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

const DETAIL = {
  bond: { id: 7, account_id: 3, account_name: "Obligacje", bond_type: "EDO", series: "EDO0936", quantity: 10,
    purchase_date: "2026-09-15", redeemed_at: null, maturity_date: "2036-09-15", note: "", status: "active",
    value_pln: "1001.30", flags: ["rate_estimated"] },
  value_per_bond: "100.16", redemption_today_pln: "998.87",
  periods: [
    { number: 1, start: "2026-09-15", end: "2027-09-15", rate: "5.3500", estimated: false },
    { number: 2, start: "2027-09-15", end: "2028-09-15", rate: "4.5000", estimated: true },
  ],
};

describe("bond detail", () => {
  it("shows the values and the periods with their rates", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/bonds/7", respond: () => DETAIL }]);
    renderApp("/pozycje/obligacje/7");

    expect(await screen.findByRole("heading", { name: "EDO0936" })).toBeInTheDocument();
    expect(screen.getByText("Wartość przy wykupie dziś").nextElementSibling).toHaveTextContent("998,87 zł");
    const periods = screen.getByRole("region", { name: "Okresy odsetkowe" });
    expect(within(periods).getByText("5,35 %")).toBeInTheDocument();
    expect(within(periods).getByText("4,50 %, szacunkowa")).toBeInTheDocument();
  });

  it("redeems early after a confirmation and deletes a purchase", async () => {
    const calls: { method: string; body?: unknown }[] = [];
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/bonds/7", respond: () => DETAIL },
      { method: "PATCH", path: "/api/bonds/7", respond: (_u, init) => { calls.push({ method: "PATCH", body: JSON.parse(String(init.body)) }); return DETAIL.bond; } },
      { method: "DELETE", path: "/api/bonds/7", respond: () => { calls.push({ method: "DELETE" }); return json(204, undefined); } },
    ]);
    const { user, router } = renderApp("/pozycje/obligacje/7");

    await user.click(await screen.findByRole("button", { name: "Wykup przed terminem" }));
    fireEvent.change(screen.getByLabelText("Data wykupu"), { target: { value: "2026-09-20" } });
    await user.click(screen.getByRole("button", { name: "Zapisz wykup" }));
    await user.click(screen.getByRole("button", { name: "Usuń zakup" }));
    expect(screen.getByText("Usunąć zakup 10 obligacji EDO0936 z 15.09.2026?")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Usuń" }));

    await waitFor(() => expect(router.state.location.pathname).toBe("/pozycje"));
    expect(calls).toEqual([{ method: "PATCH", body: { redeemed_at: "2026-09-20" } }, { method: "DELETE" }]);
  });
});
