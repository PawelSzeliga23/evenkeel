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
    expect(usageSummary({ transactions: 42, imports: 3, bond_holdings: 0, savings_entries: 0 })).toBe("42 operacje, 3 importy");
    expect(usageSummary({ transactions: 1, imports: 0, bond_holdings: 5, savings_entries: 2 }))
      .toBe("1 operacja, 5 zakupów obligacji, 2 wpisy konta oszczędnościowego");
    expect(usageSummary({ transactions: 0, imports: 0, bond_holdings: 0, savings_entries: 0 })).toBe("");
  });
});

describe("settings screen", () => {
  it("shows the profile, the accounts and the price sources summary", async () => {
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => ACCOUNTS },
      { path: "/api/instruments", respond: () => [instrument({}), BROKEN] },
    ]);
    renderApp("/ustawienia");

    expect(await screen.findByRole("heading", { name: "Ustawienia" })).toBeInTheDocument();
    expect(screen.getByText(USER.email)).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zmień hasło" })).toHaveAttribute("href", "/ustawienia/haslo");
    const accounts = screen.getByRole("region", { name: "Konta" });
    expect(await within(accounts).findByRole("link", { name: /IKE.*Rachunek maklerski/ })).toHaveAttribute("href", "/ustawienia/konta/1");
    expect(await screen.findByText("1 instrument wymaga uwagi.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zobacz źródła cen" })).toHaveAttribute("href", "/ustawienia/zrodla-cen");
    const about = screen.getByRole("region", { name: "O aplikacji" });
    expect(within(about).getByRole("img", { name: "Evenkeel" })).toBeInTheDocument();
    expect(within(about).getByText("Wersja 0.1.0")).toBeInTheDocument();
  });

  it("signs out to the login screen", async () => {
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => [] },
      { path: "/api/instruments", respond: () => [] },
      { method: "POST", path: "/api/auth/logout", respond: () => json(204, undefined) },
    ]);
    const { user } = renderApp("/ustawienia");

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
