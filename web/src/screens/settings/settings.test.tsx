import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, BROKEN, instrument } from "../../test/fixtures";
import { SIGNED_IN, USER, json, mockFetch, renderApp } from "../../test/render";
import { problemsFirst, problemsSummary, usageSummary } from "./model";

describe("settings model", () => {
  it("puts instruments with a price problem first, then by ticker", () => {
    const list = [instrument({ id: 1, xtb_ticker: "VIE.FR" }), BROKEN, instrument({ id: 2, xtb_ticker: "AAA.US" })];
    expect(problemsFirst(list).map((i) => i.xtb_ticker)).toEqual(["EIMI.UK", "AAA.US", "VIE.FR"]);
  });

  it("says how many instruments need attention", () => {
    expect(problemsSummary([])).toBe("Nie masz jeszcze instrumentów.");
    expect(problemsSummary([instrument({})])).toBe("Wszystkie instrumenty mają ceny.");
    expect(problemsSummary([BROKEN])).toBe("1 instrument wymaga uwagi.");
    expect(problemsSummary([BROKEN, { ...BROKEN, id: 12 }])).toBe("2 instrumenty wymagają uwagi.");
    expect(problemsSummary(Array.from({ length: 5 }, (_, id) => ({ ...BROKEN, id })))).toBe("5 instrumentów wymaga uwagi.");
  });

  it("describes what deleting an account removes", () => {
    expect(usageSummary({ transactions: 42, imports: 3, bond_holdings: 0, savings_entries: 0, notes: 0 })).toBe("42 operacje, 3 importy");
    expect(usageSummary({ transactions: 1, imports: 0, bond_holdings: 5, savings_entries: 2, notes: 0 }))
      .toBe("1 operacja, 5 zakupów obligacji, 2 wpisy konta oszczędnościowego");
    expect(usageSummary({ transactions: 0, imports: 0, bond_holdings: 0, savings_entries: 0, notes: 0 })).toBe("");
    expect(usageSummary({ transactions: 0, imports: 0, bond_holdings: 0, savings_entries: 2, notes: 3 }))
      .toBe("2 wpisy konta oszczędnościowego, 3 notatki");
  });
});

describe("settings screen", () => {
  it("lists the settings in groups with their values", async () => {
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/instruments", respond: () => [instrument({}), BROKEN] },
      { path: "/api/tags", respond: () => [{ id: 3, name: "Emerytura", color: "#5DB98A", links: 1 }] },
    ]);
    renderApp("/ustawienia");

    expect(await screen.findByRole("heading", { name: "Ustawienia" })).toBeInTheDocument();
    const account = screen.getByRole("region", { name: "Konto" });
    expect(within(account).getByRole("link", { name: /Profil.*anna@portfolio\.dev/ })).toHaveAttribute("href", "/ustawienia/profil");
    const portfolio = screen.getByRole("region", { name: "Portfel" });
    expect(await within(portfolio).findByRole("link", { name: new RegExp(`Konta.*${ACCOUNTS.length}`) })).toHaveAttribute("href", "/ustawienia/konta");
    expect(await within(portfolio).findByRole("link", { name: /Źródła cen.*1 do sprawdzenia/ })).toHaveAttribute("href", "/ustawienia/zrodla-cen");
    expect(await within(portfolio).findByRole("link", { name: /Tagi walorów.*1/ })).toHaveAttribute("href", "/ustawienia/tagi");
    expect(within(portfolio).getByRole("link", { name: /Dziennik/ })).toHaveAttribute("href", "/ustawienia/dziennik");
    expect(screen.getByRole("link", { name: /Ukrywanie kwot.*wył\./ })).toHaveAttribute("href", "/ustawienia/wyglad");
    expect(screen.getByRole("link", { name: /O aplikacji.*0\.1\.0/ })).toHaveAttribute("href", "/ustawienia/o-aplikacji");
  });

  it("searches the settings, the accounts and the tags", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS }, { path: "/api/instruments", respond: () => [] },
      { path: "/api/tags", respond: () => [] }]);
    const { user } = renderApp("/ustawienia");

    await user.type(await screen.findByRole("searchbox", { name: "Szukaj w ustawieniach" }), "hasło");
    expect(screen.getByRole("link", { name: /Zmień hasło.*Profil/ })).toHaveAttribute("href", "/ustawienia/haslo");
    expect(screen.queryByRole("region", { name: "Portfel" })).not.toBeInTheDocument();
    await user.clear(screen.getByRole("searchbox"));
    await user.type(screen.getByRole("searchbox"), "qwerty");
    expect(screen.getByText("Brak wyników dla „qwerty”.")).toBeInTheDocument();
  });

  it("has the profile with the password and sign-out, and the about page", async () => {
    mockFetch([...SIGNED_IN]);
    renderApp("/ustawienia/profil");

    expect(await screen.findByText(USER.email)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zmień hasło" })).toHaveAttribute("href", "/ustawienia/haslo");
    expect(screen.getByRole("button", { name: "Wyloguj" })).toBeInTheDocument();
  });

  it("lists the accounts on their own page", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => ACCOUNTS }]);
    renderApp("/ustawienia/konta");

    expect(await screen.findByRole("link", { name: /IKE.*Rachunek maklerski/ })).toHaveAttribute("href", "/ustawienia/konta/1");
    expect(screen.getAllByRole("link", { name: "Ustawienia" }).find((l) => !l.closest("nav"))).toHaveAttribute("href", "/ustawienia");
  });

  it("signs out to the login screen", async () => {
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => [] },
      { path: "/api/instruments", respond: () => [] },
      { method: "POST", path: "/api/auth/logout", respond: () => json(204, undefined) },
    ]);
    const { user } = renderApp("/ustawienia/profil");

    await user.click(await screen.findByRole("button", { name: "Wyloguj" }));
    expect(await screen.findByRole("button", { name: "Zaloguj się" })).toBeInTheDocument();
  });

  it("sends the old address to the settings", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/instruments", respond: () => [] }]);
    const { router } = renderApp("/wiecej");

    expect(await screen.findByRole("heading", { name: "Ustawienia" })).toBeInTheDocument();
    expect(router.state.location.pathname).toBe("/ustawienia");
  });
});
