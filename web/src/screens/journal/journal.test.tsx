import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { JournalEntry, NoteHolding } from "../../api/types";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

type Call = { method: string; path: string; search?: string; body?: unknown };

const SXR8: NoteHolding = { key: "i:12", label: "SXR8.DE", sublabel: "Core S&P 500", closed: false,
  link: { kind: "position", account_id: 2, instrument_id: 12, bond_holding_id: null } };
const CDR: NoteHolding = { key: "i:14", label: "CDR.PL", sublabel: "CD Projekt", closed: true, link: null };
const at = (day: string) => `${day}T10:00:00Z`;
const ENTRIES: JournalEntry[] = [
  { id: 3, entry_date: "2026-10-03", body: "Dokupiłem po spadku.", created_at: at("2026-10-03"), updated_at: at("2026-10-03"), target: SXR8 },
  { id: 2, entry_date: "2026-10-01", body: "Zmieniam podział na 80/20.", created_at: at("2026-10-01"), updated_at: at("2026-10-01"), target: null },
  { id: 1, entry_date: "2026-09-05", body: "Sprzedałem całość.", created_at: at("2026-09-05"), updated_at: at("2026-09-05"), target: CDR },
];

function open(path = "/ustawienia/dziennik", entries: JournalEntry[] = ENTRIES) {
  const calls: Call[] = [];
  const log = (method: string, answer: unknown, status = 200) => (url: URL, init: RequestInit) => {
    calls.push({ method, path: url.pathname, ...(init.body ? { body: JSON.parse(String(init.body)) } : {}) });
    return json(status, answer);
  };
  mockFetch([
    ...SIGNED_IN,
    { path: "/api/journal", respond: (url) => {
      calls.push({ method: "GET", path: url.pathname, search: url.search });
      return { entries, count: entries.length };
    } },
    { path: "/api/journal/targets", respond: () => [SXR8, CDR] },
    { method: "POST", path: "/api/journal", respond: log("POST", ENTRIES[0], 201) },
    { method: "PATCH", path: /^\/api\/journal\/\d+$/, respond: log("PATCH", ENTRIES[0]) },
    { method: "DELETE", path: /^\/api\/journal\/\d+$/, respond: log("DELETE", undefined, 204) },
  ]);
  const { user } = renderApp(path);
  return { calls, user };
}

describe("Dziennik", () => {
  it("groups the entries by month with their holdings", async () => {
    open();

    const october = await screen.findByRole("region", { name: "październik 2026" });
    const items = within(october).getAllByRole("listitem");
    expect(within(items[0]!).getByRole("link", { name: "SXR8.DE" })).toHaveAttribute("href", "/pozycje/2/12");
    expect(within(items[1]!).getByText("Portfel")).toBeInTheDocument();
    const september = screen.getByRole("region", { name: "wrzesień 2026" });
    expect(within(september).getByText("CDR.PL")).not.toHaveAttribute("href");
    expect(within(september).getByText("zamknięty")).toBeInTheDocument();
  });

  it("filters by the holding in the address", async () => {
    const { calls, user } = open("/ustawienia/dziennik?target=i%3A12");

    expect(await screen.findByLabelText("Pokaż")).toHaveValue("i:12");
    await waitFor(() => expect(calls).toContainEqual({ method: "GET", path: "/api/journal", search: "?target=i%3A12" }));
    await user.selectOptions(screen.getByLabelText("Pokaż"), "portfolio");
    await waitFor(() => expect(calls).toContainEqual({ method: "GET", path: "/api/journal", search: "?target=portfolio" }));
  });

  it("adds an entry about a chosen holding", async () => {
    const { calls, user } = open();

    await user.click(await screen.findByRole("button", { name: "+ Wpis" }));
    const form = screen.getByRole("form", { name: "Wpis" });
    expect(within(form).getByLabelText("Dotyczy")).toHaveValue("portfolio");
    await user.selectOptions(within(form).getByLabelText("Dotyczy"), "i:12");
    await user.type(within(form).getByLabelText("Treść"), "Nowy wpis");
    await user.click(within(form).getByRole("button", { name: "Zapisz" }));

    await waitFor(() => expect(calls).toContainEqual({ method: "POST", path: "/api/journal",
      body: expect.objectContaining({ instrument_id: 12, body: "Nowy wpis" }) }));
  });

  it("edits an entry without resending its holding, and moves one to the portfolio", async () => {
    const { calls, user } = open();

    await user.click(await screen.findByRole("button", { name: "Sprzedałem całość." }));
    let form = screen.getByRole("form", { name: "Wpis" });
    expect(within(form).getByLabelText("Dotyczy")).toHaveValue("i:14");
    await user.type(within(form).getByLabelText("Treść"), "!");
    await user.click(within(form).getByRole("button", { name: "Zapisz" }));
    await waitFor(() => expect(calls).toContainEqual(
      { method: "PATCH", path: "/api/journal/1", body: { entry_date: "2026-09-05", body: "Sprzedałem całość.!" } }));

    await user.click(screen.getByRole("button", { name: "Dokupiłem po spadku." }));
    form = screen.getByRole("form", { name: "Wpis" });
    await user.selectOptions(within(form).getByLabelText("Dotyczy"), "portfolio");
    await user.click(within(form).getByRole("button", { name: "Zapisz" }));
    await waitFor(() => expect(calls).toContainEqual({ method: "PATCH", path: "/api/journal/3",
      body: { entry_date: "2026-10-03", body: "Dokupiłem po spadku.", portfolio: true } }));
  });

  it("invites the first entry when there is none", async () => {
    open("/ustawienia/dziennik", []);

    expect(await screen.findByText("Zapisuj, dlaczego kupujesz i sprzedajesz — za rok to bezcenne.")).toBeInTheDocument();
  });
});
