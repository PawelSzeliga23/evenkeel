import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ACCOUNTS, ANALYTICS } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp, type MockRoute } from "../../test/render";

const SAVED = { id: 7, created_at: "2026-10-02T12:30:00Z", account_label: "Cały portfel", sections: 9 };
const PACKAGE = "# Przegląd portfela — polecenie dla Claude\n\nDane…";

function routes(extra: MockRoute[] = []) {
  return mockFetch([
    ...SIGNED_IN,
    ...extra,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/analytics", respond: () => ANALYTICS },
    { path: "/api/reviews", respond: () => [SAVED] },
    { path: "/api/reviews/package", respond: () => new Response(PACKAGE, { headers: { "Content-Type": "text/markdown" } }) },
    { method: "POST", path: "/api/reviews", status: 201, respond: (_url, init) => ({ ...SAVED, id: 8, content: JSON.parse(String(init.body)).content }) },
    { path: "/api/reviews/8", respond: () => ({ ...SAVED, id: 8, content: "## Ryzyka\n\nTreść." }) },
  ]);
}

afterEach(() => vi.unstubAllGlobals());

describe("Przegląd portfela", () => {
  it("shows the latest review on Analiza", async () => {
    routes();
    renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Przegląd AI" });
    expect(await within(card).findByText(/2 października/)).toBeInTheDocument();
    expect(within(card).getByRole("link", { name: "Przegląd portfela" })).toHaveAttribute("href", "/analiza/przeglad");
  });

  it("copies the package to the clipboard", async () => {
    routes();
    const writeText = vi.fn().mockResolvedValue(undefined);
    const { user } = renderApp("/analiza/przeglad");
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });

    await user.click(await screen.findByRole("button", { name: "Kopiuj do schowka" }));

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(PACKAGE));
    expect(screen.getByRole("status")).toHaveTextContent("Skopiowano.");
  });

  it("says to download the file when the clipboard refuses", async () => {
    routes();
    const { user } = renderApp("/analiza/przeglad");
    Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn().mockRejectedValue(new Error("no")) }, configurable: true });

    await user.click(await screen.findByRole("button", { name: "Kopiuj do schowka" }));

    expect(await screen.findByText("Nie udało się skopiować — użyj „Pobierz plik”.")).toBeInTheDocument();
  });

  it("saves a pasted answer and opens it", async () => {
    const fetchMock = routes();
    const { user } = renderApp("/analiza/przeglad");

    await user.type(await screen.findByLabelText("Wklej odpowiedź Claude"), "## Ryzyka{enter}{enter}Treść.");
    await user.click(screen.getByRole("button", { name: "Zapisz przegląd" }));

    expect(await screen.findByRole("heading", { name: /Przegląd z/ })).toBeInTheDocument();
    const post = fetchMock.mock.calls.find(([url, init]) => String(url) === "/api/reviews" && init?.method === "POST")!;
    expect(JSON.parse(String(post[1]!.body))).toEqual({ content: "## Ryzyka\n\nTreść.", account_ids: [] });
  });

  it("lists the saved reviews with their sections", async () => {
    routes();
    renderApp("/analiza/przeglad");

    const row = await screen.findByRole("link", { name: /Cały portfel/ });
    expect(row).toHaveAttribute("href", "/analiza/przeglad/7");
    expect(within(row).getByText("9/9 sekcji")).toBeInTheDocument();
  });
});
