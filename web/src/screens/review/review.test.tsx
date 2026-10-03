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

  it("adds the notes by default and remembers leaving them out", async () => {
    const fetchMock = routes();
    const writeText = vi.fn().mockResolvedValue(undefined);
    const { user } = renderApp("/analiza/przeglad");
    Object.defineProperty(navigator, "clipboard", { value: { writeText }, configurable: true });
    const packageUrls = () => fetchMock.mock.calls.map(([input]) => new URL(input, "http://localhost"))
      .filter((url) => url.pathname === "/api/reviews/package");

    const toggle = await screen.findByRole("switch", { name: /Dołącz notatki/ });
    expect(toggle).toBeChecked();
    await user.click(toggle);
    await user.click(screen.getByRole("button", { name: "Kopiuj do schowka" }));

    await waitFor(() => expect(packageUrls().at(-1)?.searchParams.get("notes")).toBe("false"));
    expect(localStorage.getItem("evenkeel.review.notes")).toBe("false");
    localStorage.removeItem("evenkeel.review.notes");
  });
});

const CONTENT = [
  "## Ocena ogólna", "", "Dobrze.", "", "## Ryzyka", "", "| Ryzyko | Skala |", "|---|---|", "| USD | duże |", "",
  "## Źródła", "", "- [Analiza](https://example.com/a)", "", "<script>alert(1)</script> <b>x</b>",
].join("\n");

function viewRoutes(review: object) {
  return mockFetch([
    ...SIGNED_IN,
    { path: "/api/reviews/5", respond: () => review },
    { method: "DELETE", path: "/api/reviews/5", respond: () => new Response(null, { status: 204 }) },
    { path: "/api/reviews", respond: () => [] },
    { path: "/api/accounts", respond: () => ACCOUNTS },
  ]);
}

describe("Reading a review", () => {
  it("renders the answer like a README with marked sections, tables and outside links", async () => {
    viewRoutes({ ...SAVED, id: 5, content: CONTENT });
    renderApp("/analiza/przeglad/5");

    const risks = await screen.findByRole("heading", { name: "Ryzyka", level: 2 });
    expect(risks).toHaveAttribute("data-section", "Ryzyka");
    expect(screen.getByRole("table").parentElement).toHaveAttribute("data-scroll", "x");
    const source = screen.getAllByRole("link", { name: "Analiza" }).find((a) => a.getAttribute("href") === "https://example.com/a")!;
    expect(source).toHaveAttribute("target", "_blank");
    expect(source).toHaveAttribute("rel", "noopener noreferrer");
  });

  it("shows pasted HTML as text, never runs it", async () => {
    viewRoutes({ ...SAVED, id: 5, content: CONTENT });
    renderApp("/analiza/przeglad/5");

    await screen.findByRole("heading", { name: "Ryzyka" });
    expect(document.querySelector("article script, article b")).toBeNull();
  });

  it("warns when no section was recognised", async () => {
    viewRoutes({ ...SAVED, id: 5, sections: 0, content: "zwykły tekst" });
    renderApp("/analiza/przeglad/5");

    expect(await screen.findByText("Nie rozpoznano sekcji przeglądu. Czy to na pewno odpowiedź na pakiet?")).toBeInTheDocument();
  });

  it("deletes a review after a confirmation", async () => {
    const fetchMock = viewRoutes({ ...SAVED, id: 5, content: CONTENT });
    const { user } = renderApp("/analiza/przeglad/5");

    await user.click(await screen.findByRole("button", { name: "Usuń przegląd" }));
    await user.click(screen.getByRole("button", { name: "Usuń" }));

    expect(await screen.findByRole("heading", { name: "Przegląd portfela" })).toBeInTheDocument();
    expect(fetchMock.mock.calls.some(([url, init]) => String(url) === "/api/reviews/5" && init?.method === "DELETE")).toBe(true);
  });
});

describe("Copying on Safari", () => {
  it("copies through ClipboardItem when the browser has it, keeping the click's permission", async () => {
    routes();
    const write = vi.fn().mockResolvedValue(undefined);
    class FakeItem { constructor(readonly items: Record<string, Promise<Blob>>) {} }
    vi.stubGlobal("ClipboardItem", FakeItem);
    const { user } = renderApp("/analiza/przeglad");
    Object.defineProperty(navigator, "clipboard", { value: { write, writeText: vi.fn() }, configurable: true });

    await user.click(await screen.findByRole("button", { name: "Kopiuj do schowka" }));

    await waitFor(() => expect(write).toHaveBeenCalledTimes(1));
    const item = write.mock.calls[0]![0][0] as FakeItem;
    expect(await (await item.items["text/plain"]!).text()).toBe(PACKAGE);
  });

  it("offers the package to select by hand when the clipboard refuses", async () => {
    routes();
    const { user } = renderApp("/analiza/przeglad");
    Object.defineProperty(navigator, "clipboard", { value: { writeText: vi.fn().mockRejectedValue(new Error("no")) }, configurable: true });

    await user.click(await screen.findByRole("button", { name: "Kopiuj do schowka" }));

    expect(await screen.findByLabelText("Zaznacz i skopiuj ręcznie")).toHaveValue(PACKAGE);
  });
});
