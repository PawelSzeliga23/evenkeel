import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { storageKey, writeSelection } from "../accounts/selection";
import { ACCOUNTS, EXPOSURE, HISTORY, LIMITS, POSITIONS, SUMMARY } from "../test/fixtures";
import { SIGNED_IN, USER, mockFetch, renderApp, type MockRoute } from "../test/render";

const THREE = [...ACCOUNTS, { ...ACCOUNTS[0]!, id: 4, name: "Oszczędności", kind: "savings" as const, broker: null, external_account_number: null }];

function routes(accounts: () => unknown = () => THREE): MockRoute[] {
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: accounts },
    { path: "/api/portfolio/summary", respond: () => SUMMARY },
    { path: "/api/portfolio/history", respond: () => HISTORY },
    { path: "/api/portfolio/exposure", respond: () => EXPOSURE },
    { path: "/api/positions", respond: () => POSITIONS },
    { path: "/api/portfolio/limits", respond: () => LIMITS },
  ];
}

const urls = (fetchMock: { mock: { calls: unknown[][] } }) => fetchMock.mock.calls.map(([url]) => String(url));

describe("one account selection for the whole app", () => {
  it("asks the API for the ticked accounts and keeps them from Pulpit to Pozycje", async () => {
    const fetchMock = mockFetch(routes());
    const { user } = renderApp("/");

    await user.click(await screen.findByRole("button", { name: "Konta: Cały portfel" }));
    await user.click(screen.getByRole("checkbox", { name: "XTB" }));
    await waitFor(() => expect(urls(fetchMock)).toContain("/api/portfolio/summary?account_id=1&account_id=4"));
    expect(localStorage.getItem(storageKey(USER.id))).toBe("[1,4]");

    await user.keyboard("{Escape}");
    await user.click(screen.getAllByRole("link", { name: "Pozycje" })[0]!);
    expect(await screen.findByRole("button", { name: "Konta: IKE, Oszczędności" })).toBeInTheDocument();
    await waitFor(() => expect(urls(fetchMock)).toContain("/api/positions?account_id=1&account_id=4"));
  });

  it("starts with the remembered choice", async () => {
    writeSelection(USER.id, [2]);
    const fetchMock = mockFetch(routes());
    renderApp("/");

    expect(await screen.findByRole("button", { name: "Konta: XTB" })).toBeInTheDocument();
    await waitFor(() => expect(urls(fetchMock)).toContain("/api/portfolio/summary?account_id=2"));
    expect(urls(fetchMock).filter((u) => u.startsWith("/api/portfolio/summary"))).toEqual(["/api/portfolio/summary?account_id=2"]);
  });

  it("drops a deleted account without asking the API about it", async () => {
    writeSelection(USER.id, [1, 9]);
    const fetchMock = mockFetch(routes());
    renderApp("/");

    expect(await screen.findByRole("button", { name: "Konta: IKE" })).toBeInTheDocument();
    await waitFor(() => expect(urls(fetchMock)).toContain("/api/portfolio/summary?account_id=1"));
    expect(urls(fetchMock).some((u) => u.includes("account_id=9"))).toBe(false);
  });
});
