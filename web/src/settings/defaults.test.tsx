import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, EXPOSURE, HISTORY, LIMITS, POSITIONS, SUMMARY } from "../test/fixtures";
import { SIGNED_IN, USER, mockFetch, renderApp, type MockRoute } from "../test/render";

function signedInWith(preferences: object, extra: MockRoute[] = []) {
  return mockFetch([
    ...SIGNED_IN.filter((r) => r.path !== "/api/auth/me"),
    { path: "/api/auth/me", respond: () => ({ ...USER, preferences }) },
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/portfolio/summary", respond: () => SUMMARY }, { path: "/api/portfolio/history", respond: () => HISTORY },
    { path: "/api/portfolio/exposure", respond: () => EXPOSURE }, { path: "/api/positions", respond: () => POSITIONS },
    { path: "/api/portfolio/limits", respond: () => LIMITS },
    ...extra,
  ]);
}

const pressed = async (group: string, name: string) => {
  const box = await screen.findByRole("group", { name: group });
  await waitFor(() => expect(within(box).getByRole("button", { name })).toHaveAttribute("aria-pressed", "true"));
};

describe("default views", () => {
  it("open Analiza with the chosen period", async () => {
    signedInWith({ analysis_period: "1y" });
    renderApp("/analiza");
    await pressed("Okres", "1R");
  });

  it("open Walory with the chosen period and without savings", async () => {
    signedInWith({ holdings_period: "1m", holdings_without_fixed_income: true });
    renderApp("/analiza/walory");
    await pressed("Okres", "Miesiąc");
    expect(screen.getByRole("checkbox", { name: "Bez oszczędności i obligacji" })).toBeChecked();
  });

  it("open Pulpit's chart with the chosen range", async () => {
    signedInWith({ value_range: "ALL" });
    renderApp("/");
    await pressed("Zakres wykresu", "Wszystko");
  });

  it("start with the whole portfolio, or with fixed accounts, whatever was chosen last", async () => {
    localStorage.setItem(`portfolio.accounts.${USER.id}`, JSON.stringify([ACCOUNTS[0]!.id]));
    const fetchMock = signedInWith({ accounts_start: "all" });
    renderApp("/");
    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).startsWith("/api/portfolio/summary")
      && !String(u).includes("account_id"))).toBe(true));
  });

  it("are saved on their page", async () => {
    signedInWith({}, [{ method: "PATCH", path: "/api/me/preferences",
      respond: (_u, init) => JSON.parse(String(init.body)) }]);
    const { user } = renderApp("/ustawienia/domyslne");

    await user.selectOptions(await screen.findByLabelText("Okres w Analizie i Symulatorze"), "ytd");
    expect(await screen.findByRole("status")).toHaveTextContent("Zapisano.");
  });
});

describe("fixed accounts on start", () => {
  it("start with the chosen accounts", async () => {
    const fetchMock = signedInWith({ accounts_start: "fixed", accounts_fixed: [ACCOUNTS[1]!.id] });
    renderApp("/");

    await waitFor(() => expect(fetchMock.mock.calls.some(([u]) => String(u).startsWith("/api/portfolio/summary")
      && String(u).includes(`account_id=${ACCOUNTS[1]!.id}`))).toBe(true));
  });
});

describe("saving default views", () => {
  it("says when saving failed", async () => {
    signedInWith({}, [{ method: "PATCH", path: "/api/me/preferences",
      respond: () => new Response(JSON.stringify({ code: "server_error", message: "Serwer ma problem.", details: {} }), { status: 500 }) }]);
    const { user } = renderApp("/ustawienia/domyslne");

    await user.selectOptions(await screen.findByLabelText("Okres w Analizie i Symulatorze"), "ytd");
    expect(await screen.findByRole("alert")).toHaveTextContent("Serwer ma problem.");
  });

  it("leaves a deleted account out of the fixed accounts it sends", async () => {
    const calls: unknown[] = [];
    signedInWith({ accounts_start: "fixed", accounts_fixed: [ACCOUNTS[0]!.id, 999] }, [{ method: "PATCH", path: "/api/me/preferences",
      respond: (_u, init) => { const body = JSON.parse(String(init.body)); calls.push(body); return { accounts_start: "fixed", ...body }; } }]);
    const { user } = renderApp("/ustawienia/domyslne");

    await user.click(await screen.findByRole("checkbox", { name: ACCOUNTS[1]!.name }));
    await waitFor(() => expect(calls).toContainEqual({ accounts_fixed: [ACCOUNTS[0]!.id, ACCOUNTS[1]!.id] }));
  });

  it("does not take another tick while one is being saved", async () => {
    signedInWith({ accounts_start: "fixed", accounts_fixed: [] }, [{ method: "PATCH", path: "/api/me/preferences",
      respond: () => new Promise<Response>(() => {}) }]);
    const { user } = renderApp("/ustawienia/domyslne");

    await user.click(await screen.findByRole("checkbox", { name: ACCOUNTS[0]!.name }));
    expect(screen.getByRole("checkbox", { name: ACCOUNTS[1]!.name })).toBeDisabled();
  });
});
