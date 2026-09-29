import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, USER, json, mockFetch, renderApp } from "../test/render";

describe("app shell", () => {
  it("shows the navigation with the current screen marked and history not yet available", async () => {
    mockFetch(SIGNED_IN);
    renderApp("/wiecej");

    const nav = await screen.findByRole("navigation", { name: "Główna" });
    expect(within(nav).getByRole("link", { name: "Więcej" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Dodaj" })).toHaveAttribute("href", "/dodaj");
    expect(within(nav).getByText("Historia")).toHaveAttribute("aria-disabled", "true");
  });

  it("shows who is signed in and signs out to the login screen", async () => {
    mockFetch([...SIGNED_IN, { method: "POST", path: "/api/auth/logout", respond: () => json(204, undefined) }]);
    const { user } = renderApp("/wiecej");

    expect(await screen.findByText(USER.email)).toBeInTheDocument();
    expect(screen.getByText("Zamknięte inwestycje")).toBeInTheDocument();
    await user.click(screen.getByRole("button", { name: "Wyloguj" }));
    expect(await screen.findByRole("button", { name: "Zaloguj się" })).toBeInTheDocument();
  });

  it("sends unknown addresses to the dashboard", async () => {
    mockFetch(SIGNED_IN);
    const { router } = renderApp("/nie-ma-takiej-strony");
    await screen.findByRole("navigation", { name: "Główna" });
    expect(router.state.location.pathname).toBe("/");
  });
});
