import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, mockFetch, renderApp } from "../test/render";

describe("app shell", () => {
  it("shows the navigation with the current screen marked", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/instruments", respond: () => [] }]);
    renderApp("/ustawienia");

    const nav = await screen.findByRole("navigation", { name: "Główna" });
    expect(within(nav).getByRole("link", { name: "Ustawienia" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Dodaj" })).toHaveAttribute("href", "/dodaj");
    expect(within(nav).getByRole("link", { name: "Historia" })).toHaveAttribute("href", "/historia");
    expect(within(nav).queryByRole("link", { name: "Więcej" })).not.toBeInTheDocument();
  });

  it("sends unknown addresses to the dashboard", async () => {
    mockFetch(SIGNED_IN);
    const { router } = renderApp("/nie-ma-takiej-strony");
    await screen.findByRole("navigation", { name: "Główna" });
    await waitFor(() => expect(router.state.location.pathname).toBe("/"));
  });
});
