import { screen, waitFor, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { SIGNED_IN, mockFetch, renderApp } from "../test/render";

describe("app shell", () => {
  it("shows the navigation with the current screen marked", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/instruments", respond: () => [] }]);
    renderApp("/ustawienia");

    const nav = await screen.findByRole("navigation", { name: "Główna" });
    expect(within(nav).getByRole("link", { name: "Ustawienia" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("img", { name: "Evenkeel", hidden: true })).toBeInTheDocument(); // shown from 900 px
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

describe("Analiza in the bar", () => {
  it("has Analiza, marked on its sub-pages, and keeps Ustawienia for the desktop only", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/scenarios", respond: () => [] }]);
    renderApp("/analiza/symulator");

    const nav = await screen.findByRole("navigation", { name: "Główna" });
    expect(within(nav).getByRole("link", { name: "Analiza" })).toHaveAttribute("aria-current", "page");
    expect(within(nav).getByRole("link", { name: "Analiza" })).toHaveAttribute("href", "/analiza");
    expect(within(nav).getByRole("link", { name: "Ustawienia" }).className).toMatch(/desktopOnly/);
  });

  it("puts a gear to Ustawienia on Pulpit and a way back on Ustawienia", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/instruments", respond: () => [] }]);
    const { user } = renderApp("/");

    const outsideNav = async (name: string) => {
      await waitFor(() => expect(screen.getAllByRole("link", { name }).some((link) => !link.closest("nav"))).toBe(true));
      return screen.getAllByRole("link", { name }).find((link) => !link.closest("nav"))!;
    };
    const gear = await outsideNav("Ustawienia");
    expect(gear).toHaveAttribute("href", "/ustawienia");
    await user.click(gear);
    expect(await outsideNav("Pulpit")).toHaveAttribute("href", "/");
    expect(screen.getAllByRole("link", { name: "Pulpit" }).some((link) => !link.closest("nav") && link.getAttribute("href") === "/")).toBe(true);
  });
});
