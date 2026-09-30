# Evenkeel Identity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. The owner chose inline execution (executing-plans) for this plan.

**Goal:** Rename the app to Evenkeel, add its bar-chart mark and wordmark, regenerate the icons, show the logo on login/register, the desktop sidebar and a Settings footer, and add an animated startup splash.

**Architecture:** A new `web/src/brand/` module holds `Mark`, `Wordmark`, `Logo` and `StartupSplash`. `StartupSplash` is mounted once in `App.tsx`, next to the router, inside the providers. It reads the session and the query cache and leaves after at least 2 s, once the session is resolved and, when starting signed in on `/`, once the first summary query has settled. Screen tests (`renderApp`) do not mount it.

**Tech Stack:** React 19 + TS + Vite, TanStack Query, CSS modules, Vitest + Testing Library (from `web/`: `npx vitest run <file>`, `npx tsc -b`), `@vite-pwa/assets-generator` (`npm run icons`).

**Spec:** `docs/superpowers/specs/2026-09-30-evenkeel-identity-design.md`

## Global Constraints

- The name is "Evenkeel". The wordmark is "Even" in `--ink` and "keel" in `--amber`, font weight 600.
- Mark (64×64 grid):
  - Tile: `rx 15`, gradient `#1C2129`→`#0E1116` (diagonal), border `#242A33`.
  - Bars: 8 wide, `rx 1.5`, vertical gradient `#8A5A1C`→`#FFC266`, opacity .55/.7/.85/1.
  - Bar heights 12/19/25/38 at x 11/22/33/44. Bar bottoms sit at y 52.
  - Base line: x 8–56 at y 52, `#3A424E`, width 1.5.
- Splash:
  - Visible ≥ 2000 ms. It leaves when the session is not "loading" and, if signed in and the start path is `/`, the first `["portfolio","summary",…]` query is not pending.
  - Exit: the bars slide under the base (~0.9 s), then the screen fades (~0.5 s), then it unmounts.
  - Reduced motion: static mark, fade only.
  - `aria-busy="true"` and the label "Wczytuję Evenkeel" while loading.
- Bars animation:
  - 4 visible bars, each higher than the one before. Next value = previous × (1.12 + random × 0.33).
  - Heights are shown relative to the newest bar, max 46 px of a 50 px area.
  - A new bar every 2200 ms rises from under the base, and the oldest sinks under it on the left. Moves take 1.2 s.
- Settings footer: `Logo` inline and "Wersja 0.1.0", with the version from `web/package.json` through Vite `define`.
- All UI text is Polish.

## Review Focus

- The splash must never get stuck. With no connection, a server error, a summary error or a signed-out user, it leaves after 2 s. Pinned in Task 3's tests.
- The splash must not block clicks while it fades (`pointer-events: none` once leaving). Pinned by a class check in Task 3.
- Values in the endless bar animation must not overflow after a long wait. They are renormalized every tick (max = 1). Pinned by `nextBars` unit tests in Task 3.
- On mobile the bottom nav keeps exactly its 5 items. The sidebar logo is hidden below 900 px, so the grid does not get a 6th cell. CSS in Task 2, no test (jsdom has no layout).
- The maskable icon must keep the bars inside the safe zone. The generator's maskable padding is used. Task 2 checks the output visually.

---

### Task 1: Brand components (`Mark`, `Wordmark`, `Logo`)

**Files:**
- Create: `web/src/brand/Mark.tsx`, `web/src/brand/Logo.tsx`, `web/src/brand/brand.module.css`, `web/src/brand/brand.test.tsx`

- [ ] **Step 1: Failing tests** — `web/src/brand/brand.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { Logo, Wordmark } from "./Logo";
import { Mark } from "./Mark";

describe("brand", () => {
  it("names the logo Evenkeel and hides the drawing from screen readers", () => {
    const { container } = render(<Logo layout="stacked" />);
    expect(screen.getByRole("img", { name: "Evenkeel" })).toBeInTheDocument();
    expect(container.querySelector("svg")).toHaveAttribute("aria-hidden", "true");
  });

  it("writes Even and keel in two colours", () => {
    const { container } = render(<Wordmark />);
    expect(container.textContent).toBe("Evenkeel");
    expect(container.querySelector("[data-part=keel]")).toHaveTextContent("keel");
  });

  it("draws four rising bars on a base line", () => {
    const { container } = render(<Mark size={64} />);
    const heights = [...container.querySelectorAll("[data-bar]")].map((b) => Number(b.getAttribute("height")));
    expect(heights).toEqual([12, 19, 25, 38]);
    expect(container.querySelector("svg")).toHaveAttribute("width", "64");
  });

  it("lays the name under or next to the mark", () => {
    const { rerender } = render(<Logo layout="stacked" />);
    expect(screen.getByRole("img", { name: "Evenkeel" })).toHaveAttribute("data-layout", "stacked");
    rerender(<Logo layout="inline" />);
    expect(screen.getByRole("img", { name: "Evenkeel" })).toHaveAttribute("data-layout", "inline");
  });
});
```

- [ ] **Step 2:** `npx vitest run src/brand/brand.test.tsx` → FAIL (modules missing).

- [ ] **Step 3: `web/src/brand/Mark.tsx`**

```tsx
import { useId } from "react";

export const BARS = [
  { x: 11, height: 12, opacity: 0.55 },
  { x: 22, height: 19, opacity: 0.7 },
  { x: 33, height: 25, opacity: 0.85 },
  { x: 44, height: 38, opacity: 1 },
] as const;
const BASE_Y = 52;

/** The Evenkeel mark: four rising amber bars on a dark tile. */
export function Mark({ size, className }: { size: number; className?: string }) {
  const id = useId();
  return (
    <svg className={className} width={size} height={size} viewBox="0 0 64 64" aria-hidden="true" focusable="false">
      <defs>
        <linearGradient id={`${id}t`} x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#1C2129" /><stop offset="1" stopColor="#0E1116" /></linearGradient>
        <linearGradient id={`${id}b`} x1="0" y1="1" x2="0" y2="0"><stop offset="0" stopColor="#8A5A1C" /><stop offset="1" stopColor="#FFC266" /></linearGradient>
      </defs>
      <rect x="0.5" y="0.5" width="63" height="63" rx="15" fill={`url(#${id}t)`} stroke="#242A33" />
      {BARS.map((bar) => (
        <rect key={bar.x} data-bar="" x={bar.x} y={BASE_Y - bar.height} width="8" height={bar.height} rx="1.5"
          fill={`url(#${id}b)`} opacity={bar.opacity} />
      ))}
      <line x1="8" y1={BASE_Y} x2="56" y2={BASE_Y} stroke="#3A424E" strokeWidth="1.5" />
    </svg>
  );
}
```

- [ ] **Step 4: `web/src/brand/Logo.tsx`**

```tsx
import styles from "./brand.module.css";
import { Mark } from "./Mark";

export const APP_NAME = "Evenkeel";

export function Wordmark({ className }: { className?: string }) {
  return <span className={`${styles.word} ${className ?? ""}`}>Even<span data-part="keel" className={styles.keel}>keel</span></span>;
}

/** Mark with the name under it (stacked) or next to it (inline). */
export function Logo({ layout, markSize = layout === "stacked" ? 72 : 28 }: { layout: "stacked" | "inline"; markSize?: number }) {
  return (
    <span role="img" aria-label={APP_NAME} data-layout={layout} className={styles[layout]}>
      <Mark size={markSize} />
      <Wordmark className={layout === "inline" ? styles.small : undefined} />
    </span>
  );
}
```

`web/src/brand/brand.module.css`:

```css
.word { font-weight: 600; font-size: 26px; line-height: 1; letter-spacing: -.01em; color: var(--ink); }
.keel { color: var(--amber); }
.small { font-size: 17px; }
.stacked { display: inline-grid; justify-items: center; gap: 14px; }
.inline { display: inline-flex; align-items: center; gap: 10px; }
```

- [ ] **Step 5:** `npx vitest run src/brand/brand.test.tsx` → PASS; `npx tsc -b` clean.
- [ ] **Step 6: Commit** `feat(web): Evenkeel mark, wordmark and logo`.

---

### Task 2: Name, icons and logo placements

**Files:**
- Modify: `web/pwa.config.ts`, `web/pwa.config.test.ts`, `web/index.html`, `web/public/icon.svg` (+ regenerated PNGs/ICO in `web/public/`)
- Modify: `web/src/auth/LoginScreen.tsx`, `web/src/auth/RegisterScreen.tsx`, `web/src/auth/auth.test.tsx`
- Modify: `web/src/shell/Nav.tsx`, `web/src/shell/shell.module.css`, `web/src/shell/shell.test.tsx`
- Modify: `web/src/screens/settings/SettingsScreen.tsx`, `web/src/screens/settings/Settings.module.css`, `web/src/screens/settings/settings.test.tsx` (or the test file that renders `/ustawienia`)
- Modify: `web/vite.config.ts`; Create: `web/src/globals.d.ts`

- [ ] **Step 1: Failing tests.**
  - `pwa.config.test.ts`: the first test expects `name: "Evenkeel", short_name: "Evenkeel"` (rename the test "installs as a standalone dark app named Evenkeel").
  - `auth.test.tsx`: the first test expects `findByRole("heading", { name: "Evenkeel" })`. Change any other "Portfel" heading lookup the same way.
  - `shell.test.tsx`, first test: `expect(within(nav).getByRole("img", { name: "Evenkeel" })).toBeInTheDocument();`.
  - Settings: add a test rendering `/ustawienia` that expects `within(screen.getByRole("contentinfo", { name: "O aplikacji" })).getByRole("img", { name: "Evenkeel" })` and the text "Wersja 0.1.0". Use the mock routes of the existing settings screen test.
- [ ] **Step 2:** Run those four files → FAIL.
- [ ] **Step 3: Name.**
  - In `pwa.config.ts` set `name: "Evenkeel", short_name: "Evenkeel"`.
  - In `index.html` set `<title>Evenkeel</title>` and `apple-mobile-web-app-title` to "Evenkeel".
- [ ] **Step 4: Version.**
  - `vite.config.ts`: add `import pkg from "./package.json";` and `define: { __APP_VERSION__: JSON.stringify(pkg.version) },` in the config object.
  - `src/globals.d.ts`: `declare const __APP_VERSION__: string;`
- [ ] **Step 5: Login and register.**
  - `LoginScreen`: `<h1 className={styles.title}><Logo layout="stacked" /></h1>`. The heading's name then comes from the logo's `aria-label`.
  - `RegisterScreen`: add `<Logo layout="stacked" />` inside a `<div className={styles.brand}>` above the existing `<h1>Załóż konto</h1>`.
  - `AuthScreens.module.css`: `.brand { justify-self: center; margin-bottom: 8px; }` and add `justify-self: center;` to `.title`.
- [ ] **Step 6: Sidebar.**
  - In `Nav.tsx`, as the first child of `<nav>`: `<div className={styles.brand}><Logo layout="inline" /></div>`.
  - In `shell.module.css`, outside the media query: `.brand { display: none; }`. Inside `@media (min-width: 900px)`: `.brand { display: block; padding: 0 10px 20px; }`.
- [ ] **Step 7: Settings footer.** At the end of the page in `SettingsScreen.tsx`:

```tsx
      <footer className={styles.about} aria-label="O aplikacji">
        <Logo layout="inline" />
        <small className="dim">Wersja {__APP_VERSION__}</small>
      </footer>
```

  Add to `Settings.module.css`: `.about { display: grid; justify-items: center; gap: 8px; padding: 28px 0 8px; border-top: 1px solid var(--rule); }`.
- [ ] **Step 8: Icon source.** Replace `web/public/icon.svg` with the mark, as a static SVG with the same geometry as `Mark`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 64 64">
  <defs>
    <linearGradient id="t" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stop-color="#1C2129"/><stop offset="1" stop-color="#0E1116"/></linearGradient>
    <linearGradient id="b" x1="0" y1="1" x2="0" y2="0"><stop offset="0" stop-color="#8A5A1C"/><stop offset="1" stop-color="#FFC266"/></linearGradient>
  </defs>
  <rect x="0.5" y="0.5" width="63" height="63" rx="15" fill="url(#t)" stroke="#242A33"/>
  <rect x="11" y="40" width="8" height="12" rx="1.5" fill="url(#b)" opacity=".55"/>
  <rect x="22" y="33" width="8" height="19" rx="1.5" fill="url(#b)" opacity=".7"/>
  <rect x="33" y="27" width="8" height="25" rx="1.5" fill="url(#b)" opacity=".85"/>
  <rect x="44" y="14" width="8" height="38" rx="1.5" fill="url(#b)"/>
  <line x1="8" y1="52" x2="56" y2="52" stroke="#3A424E" stroke-width="1.5"/>
</svg>
```

  Run `npm run icons` in `web/` and confirm that `favicon.ico`, `pwa-64x64.png`, `pwa-192x192.png`, `pwa-512x512.png`, `maskable-icon-512x512.png` and `apple-touch-icon-180x180.png` were rewritten. Look at `maskable-icon-512x512.png` and `pwa-192x192.png` with the Read tool: the bars must sit well inside the edges.
- [ ] **Step 9:** `npx tsc -b && npx vitest run` → all pass.
- [ ] **Step 10: Commit** `feat(web): the app is Evenkeel — name, icons, logo on login, sidebar and settings`.

---

### Task 3: `StartupSplash`

**Files:**
- Create: `web/src/brand/bars.ts`, `web/src/brand/StartupSplash.tsx`, `web/src/brand/splash.module.css`, `web/src/brand/splash.test.tsx`
- Modify: `web/src/App.tsx`

- [ ] **Step 1: Failing tests** — `web/src/brand/splash.test.tsx`:

```tsx
import { act, render, screen } from "@testing-library/react";
import { useQuery } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { api } from "../api/endpoints";
import { AppProviders, createQueryClient } from "../providers";
import { SIGNED_IN, json, mockFetch, type MockRoute } from "../test/render";
import { firstBars, nextBars } from "./bars";
import { StartupSplash } from "./StartupSplash";

const NO_SESSION: MockRoute = { method: "POST", path: "/api/auth/refresh", status: 401,
  respond: () => ({ code: "invalid_refresh", message: "Zaloguj się ponownie.", details: {} }) };

function SummaryProbe() {
  useQuery({ queryKey: ["portfolio", "summary", []], queryFn: () => api.summary([]) });
  return null;
}

function renderSplash(path = "/", probe = true) {
  window.history.replaceState(null, "", path);
  const client = createQueryClient({ test: true });
  render(<AppProviders client={client}><StartupSplash />{probe && <SummaryProbe />}</AppProviders>);
}

const splash = () => screen.queryByLabelText("Wczytuję Evenkeel");
const advance = (ms: number) => act(async () => { await vi.advanceTimersByTimeAsync(ms); });

beforeEach(() => vi.useFakeTimers({ shouldAdvanceTime: true }));
afterEach(() => { vi.useRealTimers(); window.history.replaceState(null, "", "/"); });

describe("startup splash", () => {
  it("stays at least two seconds even when everything is ready at once, then leaves", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/summary", respond: () => ({ as_of: null }) }]);
    renderSplash("/");
    await advance(1900);
    expect(splash()).toBeInTheDocument();
    await advance(200);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
    await advance(1500);
    expect(splash()).not.toBeInTheDocument();
  });

  it("waits for the portfolio value on the dashboard", async () => {
    let answer: (r: Response) => void = () => {};
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/summary", respond: () => new Promise<Response>((r) => { answer = r; }) }]);
    renderSplash("/");
    await advance(3000);
    expect(splash()).toHaveAttribute("data-phase", "loading");
    answer(json(200, { as_of: null }));
    await advance(100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("leaves after the session alone on other screens, when signed out and when the value fails", async () => {
    mockFetch([...SIGNED_IN]);
    renderSplash("/pozycje", false);
    await advance(2100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("leaves for a signed-out visitor", async () => {
    mockFetch([NO_SESSION]);
    renderSplash("/");
    await advance(2100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("leaves when the portfolio value cannot be loaded", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/summary", status: 500, respond: () => ({ code: "x", message: "y", details: {} }) }]);
    renderSplash("/");
    await advance(2100);
    expect(splash()).toHaveAttribute("data-phase", "leaving");
  });

  it("does not catch clicks while it fades", async () => {
    mockFetch([NO_SESSION]);
    renderSplash("/");
    await advance(2100);
    expect(splash()!.className).toMatch(/leaving/);
    expect(splash()).toHaveAttribute("aria-busy", "false");
  });

  it("keeps the bars still when the system asks for less motion", async () => {
    vi.stubGlobal("matchMedia", (q: string) => ({ matches: q.includes("reduce"), addEventListener() {}, removeEventListener() {} }));
    mockFetch([...SIGNED_IN, { path: "/api/portfolio/summary", respond: () => ({ as_of: null }) }]);
    renderSplash("/");
    const before = document.querySelectorAll("[data-splash-bar]").length;
    await advance(1500);
    expect(document.querySelectorAll("[data-splash-bar]").length).toBe(before);
    expect(splash()).toHaveAttribute("data-motion", "reduced");
  });
});

describe("rising bars", () => {
  it("starts with four rising bars", () => {
    const bars = firstBars(() => 0.5);
    expect(bars).toHaveLength(4);
    expect(bars.every((b, i) => i === 0 || b.value > bars[i - 1]!.value)).toBe(true);
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
    expect(bars.every((b) => Number.isFinite(b.value) && b.value <= 1)).toBe(true);
  });
});
```

- [ ] **Step 2:** `npx vitest run src/brand/splash.test.tsx` → FAIL.

- [ ] **Step 3: `web/src/brand/bars.ts`**

```ts
/** The splash's endless rising chart: values relative to the newest bar (always 1), each higher than the last. */
export interface SplashBar { id: number; value: number; leaving: boolean }

export const VISIBLE_BARS = 4;
const step = (random: () => number) => 1.12 + random() * 0.33;
let lastId = 0;

export function firstBars(random: () => number = Math.random): SplashBar[] {
  const values = [1];
  while (values.length < VISIBLE_BARS) values.unshift(values[0]! / step(random));
  return values.map((value) => ({ id: ++lastId, value, leaving: false }));
}

/** The oldest visible bar starts leaving, a higher one arrives, everything is renormalized to the newest. */
export function nextBars(bars: readonly SplashBar[], random: () => number = Math.random): SplashBar[] {
  const visible = bars.filter((b) => !b.leaving);
  const growth = step(random);
  const scale = 1 / growth; // the new bar is `growth` × the current newest (1) → renormalize so it is 1 again
  const kept = bars.map((b, i) => ({ ...b, value: b.value * scale, leaving: b.leaving || b.id === visible[0]?.id }));
  void i;
  return [...kept, { id: ++lastId, value: 1, leaving: false }];
}
```

  (Remove the stray `void i` and the unused `i` parameter when writing it: `bars.map((b) => …)`.)

- [ ] **Step 4: `web/src/brand/StartupSplash.tsx`**

```tsx
import { useQueryClient } from "@tanstack/react-query";
import { useEffect, useState, useSyncExternalStore } from "react";
import { useSession } from "../auth/session";
import { firstBars, nextBars, type SplashBar } from "./bars";
import { Wordmark } from "./Logo";
import styles from "./splash.module.css";

const SUMMARY = ["portfolio", "summary"];
const SLOT = 16;
const TOP = 46;

function prefersReducedMotion(): boolean {
  return typeof window.matchMedia === "function" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

/** True once any portfolio summary query has an answer (data or error). */
function useSummarySettled(): boolean {
  const cache = useQueryClient().getQueryCache();
  const settled = () => cache.findAll({ queryKey: SUMMARY }).some((q) => q.state.status !== "pending");
  return useSyncExternalStore((notify) => cache.subscribe(notify), settled);
}

function Bars({ still }: { still: boolean }) {
  const [bars, setBars] = useState<SplashBar[]>(() => firstBars());
  useEffect(() => {
    if (still) return;
    const timer = setInterval(() => setBars((current) => nextBars(current.filter((b) => !b.leaving))), 2200);
    return () => clearInterval(timer);
  }, [still]);
  const visible = bars.filter((b) => !b.leaving);
  return (
    <div className={styles.bars} aria-hidden="true">
      {bars.map((bar) => (
        <span key={bar.id} data-splash-bar="" className={`${styles.bar} ${bar.leaving ? styles.gone : ""}`}
          style={{ left: bar.leaving ? -SLOT : visible.indexOf(bar) * SLOT, height: `${(bar.value * TOP).toFixed(2)}px` }} />
      ))}
    </div>
  );
}

/** The animated Evenkeel screen shown once at start-up, until the first screen has something to show. */
export function StartupSplash({ minMs = 2000 }: { minMs?: number }) {
  const { state } = useSession();
  const [startPath] = useState(() => window.location.pathname);
  const [still] = useState(prefersReducedMotion);
  const [minDone, setMinDone] = useState(false);
  const [phase, setPhase] = useState<"loading" | "leaving" | "gone">("loading");
  const summarySettled = useSummarySettled();

  useEffect(() => {
    const timer = setTimeout(() => setMinDone(true), minMs);
    return () => clearTimeout(timer);
  }, [minMs]);

  const needsSummary = state.status === "signedIn" && startPath === "/";
  const ready = minDone && state.status !== "loading" && (!needsSummary || summarySettled);

  useEffect(() => {
    if (ready && phase === "loading") setPhase("leaving");
  }, [ready, phase]);
  useEffect(() => {
    if (phase !== "leaving") return;
    const timer = setTimeout(() => setPhase("gone"), still ? 500 : 1400);
    return () => clearTimeout(timer);
  }, [phase, still]);

  if (phase === "gone") return null;
  return (
    <div className={`${styles.splash} ${phase === "leaving" ? styles.leaving : ""}`} data-phase={phase}
      data-motion={still ? "reduced" : "full"} aria-busy={phase === "loading"} aria-label="Wczytuję Evenkeel" role="status">
      <div className={styles.stack}>
        <div className={styles.mark}>
          <Bars still={still} />
          <span className={styles.base} />
        </div>
        <Wordmark />
      </div>
    </div>
  );
}
```

  If `Wordmark` needs a size for the splash, pass `className` with `font-size: 24px`, defined in `splash.module.css` as `.word`.

- [ ] **Step 5: `web/src/brand/splash.module.css`**

```css
.splash {
  position: fixed; inset: 0; z-index: 100; display: grid; place-items: center; background: var(--night);
  transition: opacity .5s ease .9s;
}
.leaving { opacity: 0; pointer-events: none; }
.stack { display: grid; justify-items: center; gap: 18px; }
.mark {
  position: relative; width: 84px; height: 84px; border-radius: 20px; overflow: hidden;
  background: linear-gradient(135deg, #1C2129, #0E1116); border: 1px solid #242A33;
}
.bars { position: absolute; left: 11px; width: 62px; bottom: 15px; height: 50px; overflow: hidden; }
.bar {
  position: absolute; bottom: 0; width: 10px; border-radius: 2px 2px 0 0;
  background: linear-gradient(0deg, #8A5A1C, #FFC266);
  animation: rise 1.2s cubic-bezier(.45, 0, .2, 1) both;
  transition: height 1.2s cubic-bezier(.45, 0, .2, 1), left 1.2s cubic-bezier(.45, 0, .2, 1), transform 1.2s cubic-bezier(.45, 0, .2, 1);
}
.gone, .leaving .bar { transform: translateY(105%); }
.leaving .bar { transition-duration: .9s; }
.base { position: absolute; left: 9px; right: 9px; bottom: 14px; height: 1px; background: #3A424E; }
@keyframes rise { from { transform: translateY(105%); } to { transform: translateY(0); } }
@media (prefers-reduced-motion: reduce) {
  .bar { animation: none; transition: none; }
  .splash { transition: opacity .5s ease; }
}
```

  (The bar opacity rises from left to right, .55 → 1. Set it inline in `Bars` as `opacity: 0.55 + 0.15 * index` for visible bars.)

- [ ] **Step 6: Mount it** in `App.tsx`, inside `AppProviders` and before `RouterProvider`: `<StartupSplash />`.
- [ ] **Step 7:** `npx vitest run src/brand` → PASS, then `npx tsc -b && npx vitest run` → all pass.
- [ ] **Step 8:** Check it by eye in the running dev app (http://localhost:5173): reload, see the animation for ≥ 2 s, then the exit. Also check the login screen, the sidebar and the Settings footer.
- [ ] **Step 9: Commit** `feat(web): animated Evenkeel start-up splash`.

---

### Task 4: Roadmap

- [ ] In `docs/superpowers/plans/2026-09-26-00-roadmap.md`, replace the "Na później — tożsamość aplikacji" bullet (under "Zgłoszenia właściciela 2026-09-30") with "**Zrobione 2026-09-30 — tożsamość aplikacji:** nazwa Evenkeel, znak ze słupkami, ikony, animowany ekran ładowania; spec `specs/2026-09-30-evenkeel-identity-design.md`, plan `2026-09-30-evenkeel-identity.md`."
- [ ] Commit `docs(roadmap): Evenkeel identity done`.
