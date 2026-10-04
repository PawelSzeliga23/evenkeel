import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { searchSettings } from "../../settings/registry";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";
import { contents } from "./BackupScreen";

const SUMMARY = {
  exported_at: "2026-10-04T12:30:00+00:00", app_version: "0.1.0",
  counts: { accounts: 4, transactions: 120, bond_holdings: 1, savings_accounts: 1, tags: 2, notes: 0, scenarios: 0, ai_reviews: 0 },
};
const SCHEDULE = { intraday_every_minutes: 30, intraday_from: "09:00", intraday_to: "22:30", daily_at: "23:00",
  timezone: "Europe/Warsaw", last_refreshed_at: null };
const file = () => new File(['{"format":"evenkeel-backup"}'], "evenkeel-kopia-2026-10-04.json", { type: "application/json" });

describe("Kopia portfela", () => {
  it("names only what the file holds", () => {
    expect(contents(SUMMARY.counts)).toEqual(["4 konta", "120 operacji", "1 zakup obligacji", "1 konto oszczędnościowe", "2 tagi"]);
  });

  it("downloads the backup as a dated file", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/backup", respond: () => new Response('{"format":"evenkeel-backup"}') }]);
    const created = vi.fn(() => "blob:kopia");
    vi.stubGlobal("URL", Object.assign(URL, { createObjectURL: created, revokeObjectURL: vi.fn() }));
    const clicked: string[] = [];
    vi.spyOn(HTMLAnchorElement.prototype, "click").mockImplementation(function (this: HTMLAnchorElement) { clicked.push(this.download); });
    const { user } = renderApp("/ustawienia/kopia");

    await user.click(await screen.findByRole("button", { name: "Pobierz kopię" }));

    await waitFor(() => expect(clicked).toHaveLength(1));
    expect(clicked[0]).toMatch(/^evenkeel-kopia-\d{4}-\d{2}-\d{2}\.json$/);
    vi.restoreAllMocks();
  });

  it("shows what the file holds and restores it only after ZASTĄP, then opens Pulpit", async () => {
    const restored: FormData[] = [];
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] },
      { method: "POST", path: "/api/backup/check", respond: () => SUMMARY },
      { method: "POST", path: "/api/backup/restore", respond: (_url, init) => { restored.push(init.body as FormData); return SUMMARY; } }]);
    const { user } = renderApp("/ustawienia/kopia");

    await user.upload(await screen.findByLabelText("Plik kopii"), file());

    const summary = await screen.findByRole("group", { name: "Zawartość kopii" });
    expect(within(summary).getByText(/4 konta · 120 operacji/)).toBeInTheDocument();
    expect(within(summary).getByText(/Zastąpi wszystkie Twoje obecne dane/)).toBeInTheDocument();
    const load = within(summary).getByRole("button", { name: "Wczytaj" });
    expect(load).toBeDisabled();
    await user.type(within(summary).getByLabelText("Wpisz ZASTĄP"), "ZASTĄP");
    await user.click(load);

    expect(await screen.findByText("Wczytano kopię. Przeliczam wycenę…")).toBeInTheDocument();
    expect(restored[0]!.get("confirm")).toBe("ZASTĄP");
  });

  it("says what is wrong with a file that is not a backup", async () => {
    mockFetch([...SIGNED_IN, { method: "POST", path: "/api/backup/check",
      respond: () => json(422, { code: "invalid_backup", message: "To nie jest plik kopii Evenkeel.", details: {} }) }]);
    const { user } = renderApp("/ustawienia/kopia");

    await user.upload(await screen.findByLabelText("Plik kopii"), file());

    expect(await screen.findByRole("alert")).toHaveTextContent("To nie jest plik kopii Evenkeel.");
    expect(screen.queryByRole("button", { name: "Wczytaj" })).not.toBeInTheDocument();
  });
});

describe("Odświeżanie cen", () => {
  it("describes the shared schedule and the last refresh", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/market/schedule", respond: () => ({ ...SCHEDULE, last_refreshed_at: "2026-10-04T12:30:00Z" }) }]);
    renderApp("/ustawienia/odswiezanie");

    expect(await screen.findByText("Co 30 minut w dni robocze, 9:00–22:30.")).toBeInTheDocument();
    expect(screen.getByText("Pełna aktualizacja codziennie o 23:00.")).toBeInTheDocument();
    expect(screen.getByText(/^Ostatnio: .*4 października/)).toBeInTheDocument();
  });

  it("is a row of Dane with its value, and both pages are found by the search", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/instruments", respond: () => [] },
      { path: "/api/tags", respond: () => [] }, { path: "/api/market/schedule", respond: () => SCHEDULE }]);
    renderApp("/ustawienia");

    const data = await screen.findByRole("region", { name: "Dane" });
    expect(within(data).getByRole("link", { name: /Kopia portfela/ })).toHaveAttribute("href", "/ustawienia/kopia");
    expect(await within(data).findByRole("link", { name: /Odświeżanie cen.*co 30 min/ })).toHaveAttribute("href", "/ustawienia/odswiezanie");
    expect(searchSettings("backup", [], []).map((h) => h.title)).toEqual(["Kopia portfela"]);
    expect(searchSettings("harmonogram", [], []).map((h) => h.title)).toEqual(["Odświeżanie cen"]);
  });
});
