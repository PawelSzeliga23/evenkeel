import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { Tag } from "../../api/types";
import { ACCOUNTS } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

const TAGS: Tag[] = [
  { id: 2, name: "emerytura", color: "#7FB6E6", links: 4 },
  { id: 1, name: "USA", color: "#F0A43A", links: 1 },
];
type Call = { method: string; path: string; body?: unknown };

function routes(tags: Tag[] = TAGS, patch: () => unknown = () => TAGS[1]) {
  const calls: Call[] = [];
  const log = (method: string, answer: () => unknown) => (url: URL, init: RequestInit) => {
    calls.push({ method, path: url.pathname, ...(init.body ? { body: JSON.parse(String(init.body)) } : {}) });
    return answer();
  };
  const fetchMock = mockFetch([
    ...SIGNED_IN,
    { path: "/api/accounts", respond: () => ACCOUNTS },
    { path: "/api/instruments", respond: () => [] },
    { path: "/api/tags", respond: () => tags },
    { method: "PATCH", path: /^\/api\/tags\/\d+$/, respond: log("PATCH", patch) },
    { method: "DELETE", path: /^\/api\/tags\/\d+$/, respond: log("DELETE", () => json(204, undefined)) },
  ]);
  const tagFetches = () => fetchMock.mock.calls.filter(([input, init]) =>
    new URL(String(input), "http://localhost").pathname === "/api/tags" && (init?.method ?? "GET") === "GET").length;
  return { calls, tagFetches };
}

const item = (name: string) => screen.getByRole("listitem", { name });

describe("Więcej → Tagi", () => {
  it("is linked from the settings", async () => {
    routes();
    renderApp("/ustawienia");

    expect(await screen.findByRole("link", { name: /Tagi walorów/ })).toHaveAttribute("href", "/ustawienia/tagi");
  });

  it("lists the tags with how many holdings each is on", async () => {
    routes();
    renderApp("/ustawienia/tagi");

    await screen.findByRole("listitem", { name: "USA" });
    expect(item("emerytura")).toHaveTextContent("4 walory");
    expect(item("USA")).toHaveTextContent("1 walor");
  });

  it("renames a tag and shows a clash", async () => {
    const { calls } = routes(TAGS, () => json(409, { code: "tag_exists", message: "Tag „emerytura” już jest.", details: {} }));
    const { user } = renderApp("/ustawienia/tagi");

    await user.click(await screen.findByRole("button", { name: "Zmień nazwę USA" }));
    const input = within(item("USA")).getByLabelText("Nazwa tagu");
    await user.clear(input);
    await user.type(input, "emerytura");
    await user.click(within(item("USA")).getByRole("button", { name: "Zapisz" }));

    expect(await within(item("USA")).findByRole("alert")).toHaveTextContent("Tag „emerytura” już jest.");
    expect(calls).toEqual([{ method: "PATCH", path: "/api/tags/1", body: { name: "emerytura" } }]);
  });

  it("recolours a tag from the palette", async () => {
    const { calls } = routes();
    const { user } = renderApp("/ustawienia/tagi");

    await user.click(await screen.findByRole("button", { name: "Zmień nazwę USA" }));
    expect(within(item("USA")).getByRole("button", { name: "Kolor #F0A43A" })).toHaveAttribute("aria-pressed", "true");
    await user.click(within(item("USA")).getByRole("button", { name: "Kolor #5DB98A" }));

    await waitFor(() => expect(calls).toEqual([{ method: "PATCH", path: "/api/tags/1", body: { color: "#5DB98A" } }]));
  });

  it("deletes a tag after an in-page confirmation and refreshes the tags", async () => {
    const { calls, tagFetches } = routes();
    const { user } = renderApp("/ustawienia/tagi");

    await user.click(await screen.findByRole("button", { name: "Usuń emerytura" }));
    expect(screen.getByText("Usunąć tag emerytura? Zniknie z 4 walorów.")).toBeInTheDocument();
    const before = tagFetches();
    await user.click(within(screen.getByRole("group", { name: "Potwierdzenie" })).getByRole("button", { name: "Usuń" }));

    await waitFor(() => expect(calls).toEqual([{ method: "DELETE", path: "/api/tags/2" }]));
    await waitFor(() => expect(tagFetches()).toBeGreaterThan(before));
  });

  it("says when there are no tags", async () => {
    routes([]);
    renderApp("/ustawienia/tagi");

    expect(await screen.findByText("Nie masz jeszcze tagów. Dodasz je w szczegółach pozycji.")).toBeInTheDocument();
  });
});
