import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import type { PositionDetail, Tag, TagOn } from "../api/types";
import { DETAIL, PRICE_CHART } from "../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp } from "../test/render";

const TAGS: Tag[] = [
  { id: 1, name: "USA", color: "#F0A43A", links: 1 },
  { id: 2, name: "emerytura", color: "#7FB6E6", links: 1 },
  { id: 3, name: "spekulacja", color: "#5DB98A", links: 0 },
];
const USA: TagOn = { id: 1, name: "USA", color: "#F0A43A", link_id: 41, own: false };
const EMERYTURA: TagOn = { id: 2, name: "emerytura", color: "#7FB6E6", link_id: 42, own: true };

type Call = { method: string; path: string; body?: unknown };

function tagRoutes(calls: Call[]) {
  const log = (method: string, answer: unknown, status = 200) => (url: URL, init: RequestInit) => {
    calls.push({ method, path: url.pathname, ...(init.body ? { body: JSON.parse(String(init.body)) } : {}) });
    return json(status, answer);
  };
  return [
    { path: "/api/tags", respond: () => TAGS },
    { method: "POST", path: "/api/tags", respond: log("POST", { id: 9, name: "nowy", color: "#E0C36A", links: 0 }, 201) },
    { method: "POST", path: /^\/api\/tags\/\d+\/links$/, respond: log("POST", { id: 50 }, 201) },
    { method: "DELETE", path: /^\/api\/tag-links\/\d+$/, respond: log("DELETE", undefined, 204) },
  ];
}

function openPosition(tags: TagOn[] = []) {
  const calls: Call[] = [];
  const detail: PositionDetail = { ...DETAIL, tags };
  mockFetch([
    ...SIGNED_IN,
    { path: "/api/positions/2/12", respond: () => detail },
    { path: "/api/positions/2/12/prices", respond: () => PRICE_CHART },
    ...tagRoutes(calls),
  ]);
  const { user } = renderApp("/pozycje/2/12");
  return { calls, user };
}

const section = async () => screen.findByRole("region", { name: "Tagi" });

describe("Tagi in the details", () => {
  it("shows the two levels with their chips, the own one dashed", async () => {
    openPosition([USA, EMERYTURA]);
    const box = await section();

    const everywhere = within(box).getByRole("group", { name: "Walor — na wszystkich kontach" });
    const own = within(box).getByRole("group", { name: "Tylko na tym koncie (XTB)" });
    expect(within(everywhere).getByText("USA")).toBeInTheDocument();
    expect(within(own).getByText("emerytura").closest("[data-own]")).toHaveAttribute("data-own", "true");
    expect(within(everywhere).getByText("USA").closest("[data-own]")).toHaveAttribute("data-own", "false");
  });

  it("removes a tag by its link", async () => {
    const { calls, user } = openPosition([USA]);

    await user.click(within(await section()).getByRole("button", { name: "Usuń tag USA" }));

    await waitFor(() => expect(calls).toEqual([{ method: "DELETE", path: "/api/tag-links/41" }]));
  });

  it("adds an existing tag to the holding, listing only tags not yet on that level", async () => {
    const { calls, user } = openPosition([USA]);
    const box = await section();

    await user.click(within(box).getByRole("button", { name: "+ Dodaj tag" }));
    expect(within(box).getByRole("button", { name: "Dla waloru" })).toHaveAttribute("aria-pressed", "true");
    const panel = within(box).getByRole("group", { name: "Dostępne tagi" });
    await within(panel).findByRole("button", { name: "spekulacja" });
    expect(within(panel).queryByRole("button", { name: "USA" })).toBeNull();
    await user.click(within(panel).getByRole("button", { name: "spekulacja" }));

    await waitFor(() => expect(calls).toEqual([{ method: "POST", path: "/api/tags/3/links", body: { instrument_id: 12 } }]));
  });

  it("adds a tag only on this account", async () => {
    const { calls, user } = openPosition();
    const box = await section();

    await user.click(within(box).getByRole("button", { name: "+ Dodaj tag" }));
    await user.click(within(box).getByRole("button", { name: "Tylko na tym koncie" }));
    await user.click(await within(box).findByRole("button", { name: "USA" }));

    await waitFor(() => expect(calls).toEqual([
      { method: "POST", path: "/api/tags/1/links", body: { instrument_id: 12, account_id: 2 } },
    ]));
  });

  it("creates a new tag with Enter and links it", async () => {
    const { calls, user } = openPosition();
    const box = await section();

    await user.click(within(box).getByRole("button", { name: "+ Dodaj tag" }));
    await user.type(within(box).getByPlaceholderText("Nowy tag…"), "nowy{Enter}");

    await waitFor(() => expect(calls).toEqual([
      { method: "POST", path: "/api/tags", body: { name: "nowy" } },
      { method: "POST", path: "/api/tags/9/links", body: { instrument_id: 12 } },
    ]));
  });

  it("shows the API's message when adding fails", async () => {
    const calls: Call[] = [];
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/positions/2/12", respond: () => ({ ...DETAIL, tags: [] }) },
      { path: "/api/positions/2/12/prices", respond: () => PRICE_CHART },
      { method: "POST", path: "/api/tags", respond: () => json(409, { code: "tag_exists", message: "Tag „USA” już jest.", details: {} }) },
      ...tagRoutes(calls),
    ]);
    const { user } = renderApp("/pozycje/2/12");
    const box = await section();

    await user.click(within(box).getByRole("button", { name: "+ Dodaj tag" }));
    await user.type(within(box).getByPlaceholderText("Nowy tag…"), "usa{Enter}");

    expect(await within(box).findByRole("alert")).toHaveTextContent("Tag „USA” już jest.");
  });

  it("has one row and no level switch on a savings account", async () => {
    const calls: Call[] = [];
    const account = { id: 5, name: "Konto w banku", kind: "savings", wrapper: "regular", broker: null,
      external_account_number: null, currency: "PLN", created_at: "2026-09-01T10:00:00" };
    const savings = {
      account_id: 5, capitalization: "monthly", rates: [], balances: [], flows: [],
      summary: { balance: "0.00", deposits: "0.00", interest_net: "0.00", tax: "0.00", accrued: "0.00", current_rate: null },
      capitalizations: [], tags: [],
    };
    mockFetch([
      ...SIGNED_IN,
      { path: "/api/accounts", respond: () => [account] },
      { path: "/api/savings-accounts/5", respond: () => savings },
      ...tagRoutes(calls),
    ]);
    const { user } = renderApp("/pozycje/oszczednosci/5");
    const box = await section();

    expect(within(box).queryByRole("group", { name: /Tylko na tym koncie/ })).toBeNull();
    await user.click(within(box).getByRole("button", { name: "+ Dodaj tag" }));
    expect(within(box).queryByRole("group", { name: "Poziom tagu" })).toBeNull();
    await user.click(await within(box).findByRole("button", { name: "emerytura" }));

    await waitFor(() => expect(calls).toEqual([{ method: "POST", path: "/api/tags/2/links", body: { account_id: 5 } }]));
  });
});
