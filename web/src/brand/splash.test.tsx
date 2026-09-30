import { act, render, screen } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/endpoints";
import { AppProviders, createQueryClient } from "../providers";
import { SIGNED_IN, json, mockFetch, type MockRoute } from "../test/render";
import { firstBars, nextBars } from "./bars";
import { StartupSplash } from "./StartupSplash";

const NO_SESSION: MockRoute = {
  method: "POST", path: "/api/auth/refresh", status: 401,
  respond: () => ({ code: "invalid_refresh", message: "Zaloguj się ponownie.", details: {} }),
};
const SUMMARY: MockRoute = { path: "/api/portfolio/summary", respond: () => ({ as_of: null }) };

function SummaryProbe() {
  useQuery({ queryKey: ["portfolio", "summary", []], queryFn: () => api.summary([]) });
  return null;
}

function renderSplash(path = "/", probe = true) {
  window.history.replaceState(null, "", path);
  const client = createQueryClient({ test: true });
  render(<AppProviders client={client}><StartupSplash />{probe && <SummaryProbe />}</AppProviders>);
}

const splash = () => screen.queryByRole("status", { name: "Wczytuję Evenkeel" });
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

beforeEach(() => { vi.useFakeTimers({ shouldAdvanceTime: true }); });
afterEach(() => { vi.useRealTimers(); window.history.replaceState(null, "", "/"); });

describe("startup splash", () => {
  it("stays at least three seconds even when everything is ready at once, then leaves", async () => {
    mockFetch([...SIGNED_IN, SUMMARY]);
    renderSplash("/");
    await advance(2900);
    expect(splash()).toHaveAttribute("data-phase", "loading");
    await advance(200);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
    await advance(900);
    expect(splash()).not.toBeInTheDocument();
  });

  it("waits for the portfolio value when it starts on the dashboard", async () => {
    let answer: (response: Response) => void = () => {};
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/summary", respond: () => new Promise<Response>((resolve) => { answer = resolve; }) }]);
    renderSplash("/");
    await advance(3000);
    expect(splash()).toHaveAttribute("data-phase", "loading");
    answer(json(200, { as_of: null }));
    await advance(100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("needs only the session on other screens", async () => {
    mockFetch(SIGNED_IN);
    renderSplash("/pozycje", false);
    await advance(3100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("leaves for a signed-out visitor", async () => {
    mockFetch([NO_SESSION]);
    renderSplash("/");
    await advance(3100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("leaves when the portfolio value cannot be loaded", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/summary", status: 500, respond: () => ({ code: "x", message: "y", details: {} }) }]);
    renderSplash("/");
    await advance(3100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("leaves when there is no connection", async () => {
    const fetchMock = mockFetch([]);
    fetchMock.mockImplementation(() => Promise.reject(new TypeError("Failed to fetch")));
    renderSplash("/");
    await advance(3100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("stops catching clicks and stops being busy once it fades", async () => {
    mockFetch([NO_SESSION]);
    renderSplash("/");
    expect(splash()).toHaveAttribute("aria-busy", "true");
    await advance(3100);
    expect(splash()!.className).toMatch(/leaving/);
    expect(splash()).toHaveAttribute("aria-busy", "false");
  });

  it("keeps the bars still when the system asks for less motion", async () => {
    vi.stubGlobal("matchMedia", (query: string) => ({ matches: query.includes("reduce"), addEventListener() {}, removeEventListener() {} }));
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/summary", respond: () => new Promise(() => {}) }]);
    renderSplash("/");
    const before = document.querySelectorAll("[data-splash-bar]").length;
    await advance(5000);
    expect(document.querySelectorAll("[data-splash-bar]").length).toBe(before);
    expect(splash()).toHaveAttribute("data-motion", "reduced");
  });

  it("moves the bars while it waits", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/summary", respond: () => new Promise(() => {}) }]);
    renderSplash("/");
    const first = document.querySelector("[data-splash-bar]");
    await advance(1500);
    expect(document.querySelectorAll("[data-splash-bar]").length).toBe(5); // four + the one leaving
    await advance(1100);
    expect(document.querySelectorAll("[data-splash-bar]").length).toBe(4);
    expect(document.contains(first)).toBe(false);
  });
});

describe("rising bars", () => {
  it("starts with four bars, each higher than the one before", () => {
    const bars = firstBars(() => 0.5);
    expect(bars).toHaveLength(4);
    expect(bars.every((b, i) => i === 0 || b.value > bars[i - 1]!.value)).toBe(true);
    expect(bars.at(-1)!.value).toBe(1);
  });

  it("adds a higher bar, sends the oldest away and keeps the newest at 1", () => {
    const start = firstBars(() => 0.5);
    const next = nextBars(start, () => 0);
    const visible = next.filter((b) => !b.leaving);
    expect(visible).toHaveLength(4);
    expect(next.filter((b) => b.leaving).map((b) => b.id)).toEqual([start[0]!.id]);
    expect(visible.at(-1)!.value).toBe(1);
    expect(visible.every((b, i) => i === 0 || b.value > visible[i - 1]!.value)).toBe(true);
  });

  it("never grows without bound", () => {
    let bars = firstBars(() => 1);
    for (let i = 0; i < 5000; i++) bars = nextBars(bars.filter((b) => !b.leaving), () => 1);
    expect(bars.every((b) => Number.isFinite(b.value) && b.value > 0 && b.value <= 1)).toBe(true);
  });
});
