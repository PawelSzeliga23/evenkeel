import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { HoldingNotes, NoteEntry, PositionDetail } from "../api/types";
import { todayIso } from "../format";
import { DETAIL, NO_NOTES, PRICE_CHART } from "../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp } from "../test/render";

type Call = { method: string; path: string; body?: unknown };

const entry = (id: number, day: string, body: string): NoteEntry =>
  ({ id, entry_date: day, body, created_at: `${day}T10:00:00Z`, updated_at: `${day}T10:00:00Z` });

function open(notes: HoldingNotes = NO_NOTES) {
  const calls: Call[] = [];
  const log = (method: string, answer: unknown, status = 200) => (url: URL, init: RequestInit) => {
    calls.push({ method, path: url.pathname, ...(init.body ? { body: JSON.parse(String(init.body)) } : {}) });
    return json(status, answer);
  };
  const detail: PositionDetail = { ...DETAIL, notes };
  mockFetch([
    ...SIGNED_IN,
    { path: "/api/positions/2/12", respond: () => detail },
    { path: "/api/positions/2/12/prices", respond: () => PRICE_CHART },
    { method: "PUT", path: "/api/theses", respond: log("PUT", { id: 1 }) },
    { method: "POST", path: "/api/journal", respond: log("POST", { id: 9 }, 201) },
    { method: "PATCH", path: /^\/api\/journal\/\d+$/, respond: log("PATCH", { id: 1 }) },
    { method: "DELETE", path: /^\/api\/journal\/\d+$/, respond: log("DELETE", undefined, 204) },
  ]);
  const { user } = renderApp("/pozycje/2/12");
  return { calls, user };
}

const section = async () => screen.findByRole("region", { name: "Notatki" });

describe("Notatki in the details", () => {
  it("says the notes are shared and invites a thesis and the first entry", async () => {
    open();
    const box = await section();

    expect(within(box).getByText("wspólne dla wszystkich kont")).toBeInTheDocument();
    expect(within(box).getByRole("button", { name: "+ Dodaj tezę" })).toBeInTheDocument();
    expect(within(box).getByText("Zapisuj, dlaczego kupujesz i sprzedajesz.")).toBeInTheDocument();
  });

  it("adds a thesis for the instrument", async () => {
    const { calls, user } = open();
    const box = await section();

    await user.click(within(box).getByRole("button", { name: "+ Dodaj tezę" }));
    await user.type(within(box).getByLabelText("Treść tezy"), "Rdzeń portfela.");
    await user.click(within(box).getByRole("button", { name: "Zapisz" }));

    await waitFor(() => expect(calls).toContainEqual(
      { method: "PUT", path: "/api/theses", body: { instrument_id: 12, body: "Rdzeń portfela." } }));
  });

  it("shows the thesis and edits it; an empty text removes it", async () => {
    const { calls, user } = open({ ...NO_NOTES, thesis: { body: "Stara teza", updated_at: "2026-08-14T10:00:00Z" } });
    const box = await section();

    expect(within(box).getByText("Stara teza")).toBeInTheDocument();
    expect(within(box).getByText("zaktualizowano 14.08.2026")).toBeInTheDocument();
    await user.click(within(box).getByRole("button", { name: "Edytuj" }));
    await user.clear(within(box).getByLabelText("Treść tezy"));
    await user.click(within(box).getByRole("button", { name: "Zapisz" }));

    await waitFor(() => expect(calls).toContainEqual(
      { method: "PUT", path: "/api/theses", body: { instrument_id: 12, body: "" } }));
  });

  it("adds an entry dated today", async () => {
    const { calls, user } = open();
    const box = await section();

    await user.click(within(box).getByRole("button", { name: "+ Wpis" }));
    expect(within(box).getByLabelText("Data")).toHaveValue(todayIso());
    await user.type(within(box).getByLabelText("Treść"), "Dokupiłem po spadku.");
    await user.click(within(box).getByRole("button", { name: "Zapisz" }));

    await waitFor(() => expect(calls).toContainEqual({ method: "POST", path: "/api/journal",
      body: { instrument_id: 12, entry_date: todayIso(), body: "Dokupiłem po spadku." } }));
  });

  it("shows the newest entries with a link to all of them", async () => {
    open({ thesis: null, count: 5, recent: [entry(3, "2026-10-03", "Trzeci"), entry(2, "2026-09-22", "Drugi"), entry(1, "2026-08-14", "Pierwszy")] });
    const box = await section();

    expect(within(box).getAllByRole("listitem").map((li) => li.textContent)).toEqual(
      ["03.10.2026Trzeci", "22.09.2026Drugi", "14.08.2026Pierwszy"]);
    expect(within(box).getByRole("link", { name: "Wszystkie wpisy (5) ›" }))
      .toHaveAttribute("href", "/ustawienia/dziennik?target=i%3A12");
  });

  it("edits an entry and deletes one after a confirmation", async () => {
    const { calls, user } = open({ thesis: null, count: 1, recent: [entry(4, "2026-09-22", "Do zmiany")] });
    const box = await section();

    await user.click(within(box).getByRole("button", { name: "Do zmiany" }));
    await user.clear(within(box).getByLabelText("Treść"));
    await user.type(within(box).getByLabelText("Treść"), "Zmieniony");
    await user.click(within(box).getByRole("button", { name: "Zapisz" }));
    await waitFor(() => expect(calls).toContainEqual(
      { method: "PATCH", path: "/api/journal/4", body: { entry_date: "2026-09-22", body: "Zmieniony" } }));

    await user.click(within(box).getByRole("button", { name: "Do zmiany" }));
    await user.click(within(box).getByRole("button", { name: "Usuń" }));
    const confirm = within(box).getByRole("group", { name: "Potwierdzenie" });
    expect(confirm).toHaveTextContent("Usunąć wpis z 22.09.2026?");
    await user.click(within(confirm).getByRole("button", { name: "Usuń" }));
    await waitFor(() => expect(calls).toContainEqual({ method: "DELETE", path: "/api/journal/4" }));
  });

  it("is in the bond and savings details too, on the series and on the account", async () => {
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/bonds/7", respond: () => ({
        bond: { id: 7, account_id: 3, account_name: "Obligacje", bond_type: "EDO", series: "EDO0936", quantity: 10,
          purchase_date: "2026-09-15", redeemed_at: null, maturity_date: "2036-09-15", note: "", status: "active",
          value_pln: "1001.30", flags: [] },
        value_per_bond: "100.16", redemption_today_pln: "998.87", periods: [], tags: [],
        notes: { ...NO_NOTES, thesis: { body: "Teza serii", updated_at: "2026-09-15T10:00:00Z" } },
      }) },
    ]);
    renderApp("/pozycje/obligacje/7");

    const box = await section();
    expect(within(box).getByText("Teza serii")).toBeInTheDocument();
  });
});
