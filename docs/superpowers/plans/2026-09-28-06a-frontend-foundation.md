# Plan 6a: Frontend — fundament, pulpit, pozycje, import — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplikacja webowa `web/` (React + TS + Vite, PWA) z logowaniem, pulpitem (wartość, wykres ze schodkami wpłaconego kapitału, alokacja, zmiany dnia), listą i szczegółami pozycji oraz importem XTB z podglądem — w kierunku wizualnym z zaakceptowanej makiety.

**Architecture:** Jedna aplikacja SPA w `web/` rozmawiająca z istniejącym API przez proxy Vite (`/api` → `localhost:8000`, jedno źródło dla ciasteczka odświeżającego). Warstwy: `format/` i `charts/` (czyste funkcje, testowane), `api/` (jedyny punkt kontaktu z HTTP), `auth/` (sesja), `ui/` + `shell/` (wspólne elementy i nawigacja), `screens/` (ekrany składające dane z TanStack Query). Style: CSS Modules na tokenach z makiety.

**Tech Stack:** Node ≥ 22, React 19.3, React Router 8.4, TanStack Query 5.104, Vite 8.3 (+ `@vitejs/plugin-react` 6.1, `vite-plugin-pwa` 1.3), TypeScript 7.0, Vitest 5.0 + jsdom + Testing Library, Playwright 1.63, font `@fontsource-variable/instrument-sans` 5.3.

**Spec:** `docs/superpowers/specs/2026-09-28-06a-frontend-foundation-design.md` (decyzje planu 6a — wiążące) oraz `docs/superpowers/specs/2026-09-26-portfolio-tracker-design.md` §3, §5 „Przepływ w UI”, §7, §9, §10. Makieta: https://claude.ai/artifact/NBPYQ1danFfjZsfnybjyrg.

## Global Constraints

- Testy frontendu: `npm test` (z katalogu `web/`, Vitest, bez sieci); e2e: `npm run e2e` (Playwright, osobna baza i instancja API w dockerze). Testy API bez zmian: `docker compose run --rm api pytest` (z katalogu repozytorium). Każdy commit kończy się linią `Co-Authored-By: <model, który napisał commit> <noreply@anthropic.com>`.
- Wersje (dokładne, `--save-exact`): react 19.3.0, react-dom 19.3.0, react-router 8.4.0, @tanstack/react-query 5.104.0, @fontsource-variable/instrument-sans 5.3.0; dev: vite 8.3.1, @vitejs/plugin-react 6.1.1, typescript 7.0.2, vite-plugin-pwa 1.3.0, @vite-pwa/assets-generator 1.0.4, workbox-window 7.4.1, vitest 5.0.2, jsdom 30.1.1, @testing-library/react 16.3.3, @testing-library/dom 10.4.2, @testing-library/jest-dom 7.0.1, @testing-library/user-event 14.6.7, @playwright/test 1.63.0, @types/react 19.3.0, @types/react-dom 19.3.0, @types/node 24.19.0. Bez innych zależności. **Bez Tailwinda i bibliotek komponentów/wykresów.**
- Tokeny kolorów dokładnie: `--night #0E1116`, `--slab #161A21`, `--rule #242A33`, `--ink #E7E9EC`, `--dim #8B94A1`, `--amber #F0A43A`, `--amber-soft rgba(240,164,58,.14)`, `--gain #5DB98A`, `--loss #E0676E`. Tylko ciemny motyw. Bursztyn to jedyny akcent (linia wartości, aktywne elementy, przycisk „Dodaj”, fokus).
- Kwoty z API to `string` i **nie są zamieniane na float do wyświetlania ani sumowania** (sumy przez `BigInt` groszy w `format/decimal.ts`); `Number(...)` wolno tylko do skal wykresu, proporcji paska alokacji i procentu zmiany dnia pozycji w „Dziś najbardziej” (API podaje tylko kwotę zmiany). Zapis polski: spacja tysięcy zawsze (` `), przecinek dziesiętny, „zł” po kwocie, minus `−` (U+2212), `+` przy zysku, „+0,66 %”. Wszystkie kwoty `tabular-nums`.
- Teksty interfejsu po polsku, zdania od wielkiej litery, bez wersalików w etykietach i bez kropek środkowych „·” jako separatorów; przyciski nazywają akcję („Zaloguj się”, „Załóż konto”, „Wgraj pliki z XTB”, „Zapisz import”); błędy mówią, co się stało i co zrobić, bez przepraszania.
- Access token tylko w pamięci JS; refresh wyłącznie ciasteczkiem `httpOnly` ustawianym przez API. Każde zapytanie `fetch` z `credentials: "same-origin"`.
- API (`api/app/…`) bez zmian; wolno tylko dodać usługi e2e w `docker-compose.yml` i skrypt `api/tests/e2e_fixture.py` (Task 11).
- Dostępność: widoczny fokus (obrys `--amber`), cele dotyku ≥ 44 px, `prefers-reduced-motion` wyłącza animację linii, safe-area (`env(safe-area-inset-*)`) w pasku nawigacji i nagłówku.

## Doprecyzowania względem dokumentu decyzji

- **Kolory alokacji wg kolejności**: wiersze alokacji przychodzą z API posortowane malejąco; pierwszy (największy) dostaje `--amber`, kolejne `#C9B48A`, `#7C8898`, `#4A5361`, `#39414C` (w kółko). Dla typowego portfela to akcje i ETF-y, jak w makiecie, a kod nie zgaduje kluczy kategorii.
- **Ekspozycja do alokacji wg waluty** pobierana z `from = to = summary.as_of` (tylko bieżąca część, bez całej historii).
- **Zapis importu** jest nieaktywny, gdy podgląd ma błędy plików (API odrzuca wtedy całość — `422 import_invalid_files`) albo gdy nie ma nic nowego (0 nowych operacji we wszystkich plikach).
- **Podgląd dnia na wykresie**: dotknięcie/najechanie pokazuje nad wykresem datę, wartość i wpłacony kapitał najbliższego dnia; bez dotyku w tym miejscu jest legenda.
- **Ścieżki w aplikacji po polsku**: `/` (Pulpit), `/pozycje`, `/pozycje/:accountId/:instrumentId`, `/dodaj` (import), `/wiecej`, `/logowanie`, `/rejestracja`. Historia w nawigacji wyłączona („wkrótce”), bez trasy.
- **Hasło przy rejestracji** sprawdzane także w przeglądarce (co najmniej 10 znaków, jak w API).
- **„Dziś najbardziej”**: procent zmiany pozycji = `day_change_pln / (value_pln − day_change_pln)`, liczony tylko do wyświetlenia; pozycje z zerową zmianą i niedodatnią wartością z poprzedniego dnia są pomijane.
- **Test e2e** używa spółki notowanej w PLN (CD Projekt), żeby wycena nie zależała od kursów walut, których na świeżej bazie nie ma (worker nie działa w e2e).

## Review Focus

- Kilka zapytań naraz dostaje 401 (wygasły token) → **jedno** odświeżenie `/api/auth/refresh`, wszystkie zapytania powtórzone z nowym tokenem; nieudane odświeżenie → ekran logowania z „Sesja wygasła…”. *(Task 3, Task 4)*
- API nie działa (błąd sieci) przy starcie albo w trakcie → komunikat „Brak połączenia z serwerem…” w miejscu sekcji z „Spróbuj ponownie”, a nie pętla wylogowań czy biały ekran. *(Task 3, Task 7)*
- Kwoty spoza „ładnego” formatu: `"-0.00"`, `"0.004"`, `"10000.0000"`, `"-1234567.891"` → „0,00 zł” bez znaku, „10 000,00 zł”, „−1 234 567,89 zł” (zaokrąglenie połówkowe w górę na tekście). *(Task 2)*
- Po imporcie wycena liczy się w tle (`recalculating: true`) → pulpit sam odpytuje co 3 s i po zakończeniu odświeża wykres, alokację i pozycje, bez przeładowania strony. *(Task 7)*
- Import z jednym nieczytelnym plikiem → podgląd pokazuje błąd przy tym pliku i dane pozostałych, a „Zapisz import” jest nieaktywny z wyjaśnieniem; historia z jednym punktem → zamiast wykresu zdanie, a nie pusty/zepsuty SVG. *(Task 9, Task 6)*

---

## Mapa plików

```
.gitignore                                  + web/e2e/screens/, web/test-results/, web/playwright-report/, api/.e2e/
docker-compose.yml                          + db-e2e, api-e2e (profil e2e)                      (Task 11)
README.md                                   + sekcja „Frontend” (uruchomienie, testy, e2e)      (Task 11)
docs/superpowers/plans/2026-09-26-00-roadmap.md   wiersz 6a → zrobiony                            (Task 11)
api/tests/e2e_fixture.py                    syntetyczny eksport XTB dla e2e                     (Task 11)
web/
  package.json, package-lock.json, tsconfig.json, vite.config.ts, index.html
  pwa.config.ts, pwa.config.test.ts, pwa-assets.config.ts, public/icon.svg (+ wygenerowane ikony)   (Task 10)
  playwright.config.ts, e2e/global-setup.ts, e2e/global-teardown.ts, e2e/app.spec.ts                (Task 11)
  src/
    main.tsx, App.tsx, routes.tsx
    styles/tokens.css, styles/global.css, styles/tokens.test.ts
    test/setup.ts, test/render.tsx, test/fixtures.ts
    format/decimal.ts, format/money.ts, format/dates.ts, format/index.ts, format/format.test.ts
    api/types.ts, api/client.ts, api/endpoints.ts, api/queryKeys.ts, api/client.test.ts
    auth/session.tsx, auth/RequireAuth.tsx, auth/LoginScreen.tsx, auth/RegisterScreen.tsx,
      auth/AuthScreens.module.css, auth/auth.test.tsx
    ui/Amount.tsx, ui/Segmented.tsx, ui/AccountPicker.tsx, ui/States.tsx, ui/ListRow.tsx, ui/ui.module.css, ui/ui.test.tsx
    shell/AppShell.tsx, shell/Nav.tsx, shell/icons.tsx, shell/MoreScreen.tsx, shell/shell.module.css, shell/shell.test.tsx
    charts/geometry.ts, charts/ValueChart.tsx, charts/ValueChart.module.css, charts/geometry.test.ts
    screens/dashboard/model.ts, DashboardScreen.tsx, Dashboard.module.css, dashboard.test.tsx
    screens/positions/model.ts, PositionsScreen.tsx, PositionDetailScreen.tsx, Positions.module.css, positions.test.tsx
    screens/import/ImportScreen.tsx, Import.module.css, import.test.tsx
```

---

### Task 1: Szkielet `web/` — Vite, TypeScript, Vitest, tokeny i style bazowe

**Files:**
- Create: `web/package.json`, `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`, `web/src/main.tsx`, `web/src/styles/tokens.css`, `web/src/styles/global.css`, `web/src/test/setup.ts`, `web/src/styles/tokens.test.ts`
- Modify: `.gitignore`
- Test: `web/src/styles/tokens.test.ts`

**Interfaces:**
- Consumes: nic.
- Produces: projekt `web/` z komendami `npm run dev` (port 5173, proxy `/api` → `process.env.API_TARGET ?? "http://localhost:8000"`), `npm test`, `npm run typecheck`, `npm run build`; tokeny CSS (`--night`, `--slab`, `--rule`, `--ink`, `--dim`, `--amber`, `--amber-soft`, `--gain`, `--loss`, `--loss-soft`, `--font`, `--r-control`, `--r-sheet`, `--nav-h`) i klasy globalne `.num` (tabular-nums), `.up`, `.down`, `.dim`, `.flag`; konfiguracja Vitest (jsdom, `src/test/setup.ts`, CSS Modules z nazwami niescopowanymi).

- [ ] **Step 1: `web/package.json`**

```json
{
  "name": "portfel-web",
  "private": true,
  "version": "0.1.0",
  "type": "module",
  "engines": { "node": ">=22" },
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview",
    "typecheck": "tsc --noEmit",
    "test": "vitest run",
    "test:watch": "vitest",
    "icons": "pwa-assets-generator",
    "e2e": "playwright test"
  },
  "dependencies": {
    "@fontsource-variable/instrument-sans": "5.3.0",
    "@tanstack/react-query": "5.104.0",
    "react": "19.3.0",
    "react-dom": "19.3.0",
    "react-router": "8.4.0"
  },
  "devDependencies": {
    "@playwright/test": "1.63.0",
    "@testing-library/dom": "10.4.2",
    "@testing-library/jest-dom": "7.0.1",
    "@testing-library/react": "16.3.3",
    "@testing-library/user-event": "14.6.7",
    "@types/node": "24.19.0",
    "@types/react": "19.3.0",
    "@types/react-dom": "19.3.0",
    "@vite-pwa/assets-generator": "1.0.4",
    "@vitejs/plugin-react": "6.1.1",
    "jsdom": "30.1.1",
    "typescript": "7.0.2",
    "vite": "8.3.1",
    "vite-plugin-pwa": "1.3.0",
    "vitest": "5.0.2",
    "workbox-window": "7.4.1"
  }
}
```

Run (z `web/`): `npm install`
Expected: powstaje `package-lock.json`, bez błędów rozwiązywania zależności (ostrzeżenia `deprecated` z zależności przechodnich są dopuszczalne).

- [ ] **Step 2: `web/tsconfig.json`, `web/vite.config.ts`, `web/index.html`**

`web/tsconfig.json`:

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "noUnusedLocals": true,
    "noUnusedParameters": true,
    "noFallthroughCasesInSwitch": true,
    "verbatimModuleSyntax": true,
    "isolatedModules": true,
    "resolveJsonModule": true,
    "skipLibCheck": true,
    "noEmit": true,
    "types": ["vite/client", "node"]
  },
  "include": ["src", "e2e", "vite.config.ts", "pwa.config.ts", "pwa.config.test.ts", "pwa-assets.config.ts", "playwright.config.ts"]
}
```

`web/vite.config.ts`:

```ts
/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";

// The API runs in docker on :8000 (e2e: its own instance, API_TARGET=http://localhost:8001). Proxying /api keeps the
// browser on one origin, so the httpOnly refresh cookie works without CORS.
const apiTarget = process.env.API_TARGET ?? "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: { port: 5173, proxy: { "/api": { target: apiTarget } } },
  preview: { proxy: { "/api": { target: apiTarget } } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "*.test.ts"],
    css: { modules: { classNameStrategy: "non-scoped" } },
    restoreMocks: true,
  },
});
```

`web/index.html`:

```html
<!doctype html>
<html lang="pl">
  <head>
    <meta charset="UTF-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover" />
    <meta name="theme-color" content="#0E1116" />
    <meta name="color-scheme" content="dark" />
    <title>Portfel</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

- [ ] **Step 3: Test tokenów (kontrakt z makietą)**

`web/src/styles/tokens.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import tokens from "./tokens.css?raw";

describe("design tokens", () => {
  it.each([
    ["--night", "#0E1116"],
    ["--slab", "#161A21"],
    ["--rule", "#242A33"],
    ["--ink", "#E7E9EC"],
    ["--dim", "#8B94A1"],
    ["--amber", "#F0A43A"],
    ["--gain", "#5DB98A"],
    ["--loss", "#E0676E"],
  ])("%s is %s", (name, value) => {
    expect(tokens).toMatch(new RegExp(`${name}:\\s*${value};`, "i"));
  });

  it("uses Instrument Sans with a system fallback", () => {
    expect(tokens).toMatch(/--font:\s*"Instrument Sans Variable",[^;]*system-ui/);
  });
});
```

`web/src/test/setup.ts`:

```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach } from "vitest";

afterEach(() => cleanup());
```

- [ ] **Step 4: Uruchom test — ma nie przejść**

Run (z `web/`): `npm test -- src/styles/tokens.test.ts`
Expected: FAIL — nie można rozwiązać `./tokens.css?raw`.

- [ ] **Step 5: Tokeny i style globalne**

`web/src/styles/tokens.css`:

```css
/* Design tokens from the accepted mockup (plan 6a): one dark theme, one amber accent. */
:root {
  color-scheme: dark;
  --night: #0E1116;
  --slab: #161A21;
  --rule: #242A33;
  --ink: #E7E9EC;
  --dim: #8B94A1;
  --amber: #F0A43A;
  --amber-soft: rgba(240, 164, 58, .14);
  --gain: #5DB98A;
  --loss: #E0676E;
  --loss-soft: rgba(224, 103, 110, .14);
  --font: "Instrument Sans Variable", "Segoe UI", system-ui, -apple-system, sans-serif;
  --r-control: 10px;
  --r-sheet: 14px;
  --nav-h: 64px;
}
```

`web/src/styles/global.css`:

```css
@import "@fontsource-variable/instrument-sans/wdth.css";
@import "./tokens.css";

*, *::before, *::after { box-sizing: border-box; }
html { -webkit-text-size-adjust: 100%; }
body {
  margin: 0;
  min-height: 100dvh;
  background: var(--night);
  color: var(--ink);
  font-family: var(--font);
  font-size: 15px;
  line-height: 1.4;
  -webkit-font-smoothing: antialiased;
}
h1, h2, h3, p { margin: 0; }
h1, h2 { text-wrap: balance; letter-spacing: -.01em; }
button, input, select { font: inherit; color: inherit; }
a { color: inherit; text-decoration: none; }
:focus-visible { outline: 2px solid var(--amber); outline-offset: 2px; border-radius: 4px; }

.num { font-variant-numeric: tabular-nums; }
.up { color: var(--gain); }
.down { color: var(--loss); }
.dim { color: var(--dim); }
.flag { color: var(--amber); font-size: 12.5px; }

@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after { animation: none !important; transition: none !important; }
}
```

`web/src/main.tsx` (tymczasowy; Task 5 zastępuje go aplikacją):

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <p style={{ padding: 24 }}>Portfel</p>
  </StrictMode>,
);
```

`.gitignore` — dopisz na końcu:

```
# Web
web/e2e/screens/
web/test-results/
web/playwright-report/
api/.e2e/
```

- [ ] **Step 6: Uruchom testy i typecheck**

Run (z `web/`): `npm test` → Expected: PASS (9 testów).
Run: `npm run typecheck` → Expected: brak błędów.
Run: `npm run build` → Expected: `dist/` powstaje bez błędów.

- [ ] **Step 7: Commit**

```bash
git add .gitignore web/package.json web/package-lock.json web/tsconfig.json web/vite.config.ts web/index.html \
  web/src/main.tsx web/src/styles web/src/test/setup.ts
git commit -m "feat(web): Vite + React + TypeScript skeleton with the mockup's design tokens

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 2: Formatowanie kwot, procentów i dat (czyste funkcje)

**Files:**
- Create: `web/src/format/decimal.ts`, `web/src/format/money.ts`, `web/src/format/dates.ts`, `web/src/format/index.ts`, `web/src/format/format.test.ts`

**Interfaces:**
- Consumes: nic.
- Produces (`import { … } from "../format"`):
  - `toCents(value: string): bigint`, `fromCents(cents: bigint): string` („1234.50”), `sumMoney(values: string[]): string`, `signOf(value: string | null): -1 | 0 | 1`.
  - `MINUS = "−"`, `NBSP = " "`; `moneyParts(value: string, options?: { sign?: boolean }): { sign: "" | "+" | "−"; whole: string; grosze: string }`; `formatMoney(value: string, options?: { sign?: boolean; currency?: string | null }): string` (domyślnie „zł”, `null` = bez waluty); `formatDecimal(value: string, maxPlaces: number): string` (bez zbędnych zer, np. ilości); `formatPercent(value: string | null, options?: { sign?: boolean; places?: number }): string` (`null` → „—”).
  - `formatDate(iso: string): string` („26.09.2026”), `formatDayLong(iso: string): string` („sob., 26 września”), `monthShort(iso: string): string` („wrz”), `formatDateTime(iso: string): string` („02.03.2026, 09:30”), `formatDays(days: number): string` („1 dzień”, „412 dni”), `todayIso(now?: Date): string` („2026-09-28”, data lokalna), `addMonths(iso: string, months: number): string`.

- [ ] **Step 1: Testy**

`web/src/format/format.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  addMonths, formatDate, formatDateTime, formatDayLong, formatDays, formatDecimal, formatMoney, formatPercent,
  fromCents, moneyParts, monthShort, signOf, sumMoney, toCents, todayIso,
} from ".";

const S = " ";
const M = "−";

describe("decimal", () => {
  it("rounds half up to the grosz on the text, never through a float", () => {
    expect(toCents("1001.30")).toBe(100130n);
    expect(toCents("0.004")).toBe(0n);
    expect(toCents("0.005")).toBe(1n);
    expect(toCents("-1234567.891")).toBe(-123456789n);
    expect(toCents("10000.0000")).toBe(1000000n);
    expect(toCents("0.1")).toBe(10n);
    expect(toCents("99.995")).toBe(10000n);
    expect(toCents("7")).toBe(700n);
  });

  it("sums money exactly", () => {
    expect(sumMoney(["0.10", "0.20", "1001.30"])).toBe("1001.60");
    expect(sumMoney(["-5.00", "2.50"])).toBe("-2.50");
    expect(sumMoney([])).toBe("0.00");
    expect(fromCents(-5n)).toBe("-0.05");
  });

  it("tells the sign", () => {
    expect([signOf("12.30"), signOf("-0.01"), signOf("-0.00"), signOf("0.004"), signOf(null)]).toEqual([1, -1, 0, 0, 0]);
  });
});

describe("money", () => {
  it("writes Polish amounts with a space in every thousand", () => {
    expect(formatMoney("184302.17")).toBe(`184${S}302,17${S}zł`);
    expect(formatMoney("1204.5")).toBe(`1${S}204,50${S}zł`);
    expect(formatMoney("10000.0000")).toBe(`10${S}000,00${S}zł`);
    expect(formatMoney("-1234567.891")).toBe(`${M}1${S}234${S}567,89${S}zł`);
    expect(formatMoney("0.5", { currency: "EUR" })).toBe(`0,50${S}EUR`);
    expect(formatMoney("12", { currency: null })).toBe("12,00");
  });

  it("shows the sign of a change and none for zero", () => {
    expect(formatMoney("1204.50", { sign: true })).toBe(`+1${S}204,50${S}zł`);
    expect(formatMoney("-151.2", { sign: true })).toBe(`${M}151,20${S}zł`);
    expect(formatMoney("-0.00", { sign: true })).toBe(`0,00${S}zł`);
    expect(formatMoney("-0.004")).toBe(`0,00${S}zł`);
  });

  it("splits a big amount into its parts", () => {
    expect(moneyParts("184302.17")).toEqual({ sign: "", whole: `184${S}302`, grosze: "17" });
    expect(moneyParts("-3.1", { sign: true })).toEqual({ sign: M, whole: "3", grosze: "10" });
    expect(moneyParts("3.1", { sign: true })).toEqual({ sign: "+", whole: "3", grosze: "10" });
  });

  it("writes quantities without trailing zeros", () => {
    expect(formatDecimal("42.00000000", 8)).toBe("42");
    expect(formatDecimal("0.12345678", 4)).toBe("0,1235");
    expect(formatDecimal("1234.5", 8)).toBe(`1${S}234,5`);
  });

  it("writes percents with a space before the sign", () => {
    expect(formatPercent("0.66")).toBe(`+0,66${S}%`);
    expect(formatPercent("-2.071")).toBe(`${M}2,07${S}%`);
    expect(formatPercent("14.2", { places: 1 })).toBe(`+14,2${S}%`);
    expect(formatPercent("33.4", { sign: false, places: 1 })).toBe(`33,4${S}%`);
    expect(formatPercent(null)).toBe("—");
  });
});

describe("dates", () => {
  it("formats days without time-zone shifts", () => {
    expect(formatDate("2026-09-26")).toBe("26.09.2026");
    expect(formatDayLong("2026-09-26")).toBe("sob., 26 września");
    expect(formatDayLong("2026-03-01")).toBe("niedz., 1 marca");
    expect(monthShort("2026-10-01")).toBe("paź");
    expect(formatDateTime("2026-03-02T09:30:00")).toBe("02.03.2026, 09:30");
    expect(formatDateTime("2026-03-02T09:30:00+00:00")).toBe("02.03.2026, 09:30");
  });

  it("counts days in Polish", () => {
    expect([formatDays(1), formatDays(2), formatDays(412)]).toEqual(["1 dzień", "2 dni", "412 dni"]);
  });

  it("moves by months and clamps the day", () => {
    expect(addMonths("2026-09-26", -1)).toBe("2026-08-26");
    expect(addMonths("2026-03-31", -1)).toBe("2026-02-28");
    expect(addMonths("2026-01-15", -12)).toBe("2025-01-15");
    expect(todayIso(new Date(2026, 8, 28, 23, 59))).toBe("2026-09-28");
  });
});
```

- [ ] **Step 2: Uruchom — mają nie przejść**

Run (z `web/`): `npm test -- src/format`
Expected: FAIL — `Failed to resolve import "."`.

- [ ] **Step 3: `decimal.ts`**

`web/src/format/decimal.ts`:

```ts
/** Exact money arithmetic on the API's decimal strings: grosze as BigInt, rounding half up on the digits. */

function increment(digits: string): string {
  const out = digits.split("");
  for (let i = out.length - 1; i >= 0; i--) {
    if (out[i] === "9") {
      out[i] = "0";
    } else {
      out[i] = String(Number(out[i]) + 1);
      return out.join("");
    }
  }
  return `1${out.join("")}`;
}

/** Splits "-1234.5678" into sign and digits rounded half up to `places` decimals: ["-", "123457"] for places=2. */
export function roundDigits(value: string, places: number): { negative: boolean; digits: string } {
  const text = value.trim();
  const negative = text.startsWith("-");
  const [whole = "0", fraction = ""] = text.replace(/^[-+]/, "").split(".");
  const padded = (fraction + "0".repeat(places + 1)).slice(0, places + 1);
  let digits = (whole || "0") + padded.slice(0, places);
  if (Number(padded[places]) >= 5) digits = increment(digits);
  digits = digits.replace(/^0+(?=\d)/, "");
  return { negative: negative && /[1-9]/.test(digits), digits };
}

export function toCents(value: string): bigint {
  const { negative, digits } = roundDigits(value, 2);
  const cents = BigInt(digits);
  return negative ? -cents : cents;
}

export function fromCents(cents: bigint): string {
  const negative = cents < 0n;
  const text = (negative ? -cents : cents).toString().padStart(3, "0");
  return `${negative ? "-" : ""}${text.slice(0, -2)}.${text.slice(-2)}`;
}

export function sumMoney(values: string[]): string {
  return fromCents(values.reduce((total, value) => total + toCents(value), 0n));
}

export function signOf(value: string | null): -1 | 0 | 1 {
  if (value === null) return 0;
  const cents = toCents(value);
  return cents > 0n ? 1 : cents < 0n ? -1 : 0;
}
```

- [ ] **Step 4: `money.ts`, `dates.ts`, `index.ts`**

`web/src/format/money.ts`:

```ts
import { roundDigits } from "./decimal";

export const NBSP = " ";
export const MINUS = "−";

type Sign = "" | "+" | "−";

function group(whole: string): string {
  return whole.replace(/\B(?=(\d{3})+(?!\d))/g, NBSP);
}

function split(value: string, places: number): { negative: boolean; whole: string; fraction: string } {
  const { negative, digits } = roundDigits(value, places);
  const padded = digits.padStart(places + 1, "0");
  return { negative, whole: padded.slice(0, padded.length - places), fraction: padded.slice(padded.length - places) };
}

function signFor(negative: boolean, isZero: boolean, withPlus: boolean): Sign {
  if (negative) return MINUS;
  return withPlus && !isZero ? "+" : "";
}

export function moneyParts(value: string, { sign = false }: { sign?: boolean } = {}) {
  const { negative, whole, fraction } = split(value, 2);
  const isZero = !/[1-9]/.test(whole + fraction);
  return { sign: signFor(negative, isZero, sign), whole: group(whole), grosze: fraction };
}

export function formatMoney(
  value: string, { sign = false, currency = "zł" }: { sign?: boolean; currency?: string | null } = {},
): string {
  const parts = moneyParts(value, { sign });
  const amount = `${parts.sign}${parts.whole},${parts.grosze}`;
  return currency === null ? amount : `${amount}${NBSP}${currency}`;
}

/** Quantities and prices: up to `maxPlaces` decimals, trailing zeros dropped. */
export function formatDecimal(value: string, maxPlaces: number): string {
  const { negative, whole, fraction } = split(value, maxPlaces);
  const kept = fraction.replace(/0+$/, "");
  const isZero = !/[1-9]/.test(whole + kept);
  return `${negative && !isZero ? MINUS : ""}${group(whole)}${kept ? `,${kept}` : ""}`;
}

export function formatPercent(
  value: string | null, { sign = true, places = 2 }: { sign?: boolean; places?: number } = {},
): string {
  if (value === null) return "—";
  const { negative, whole, fraction } = split(value, places);
  const isZero = !/[1-9]/.test(whole + fraction);
  return `${signFor(negative, isZero, sign)}${group(whole)}${places ? `,${fraction}` : ""}${NBSP}%`;
}
```

`web/src/format/dates.ts`:

```ts
const MONTHS_GENITIVE = [
  "stycznia", "lutego", "marca", "kwietnia", "maja", "czerwca",
  "lipca", "sierpnia", "września", "października", "listopada", "grudnia",
];
const MONTHS_SHORT = ["sty", "lut", "mar", "kwi", "maj", "cze", "lip", "sie", "wrz", "paź", "lis", "gru"];
const WEEKDAYS = ["niedz.", "pon.", "wt.", "śr.", "czw.", "pt.", "sob."];

function parts(iso: string): { year: number; month: number; day: number } {
  const [year, month, day] = iso.slice(0, 10).split("-").map(Number);
  return { year: year!, month: month!, day: day! };
}

const pad = (n: number) => String(n).padStart(2, "0");

export function formatDate(iso: string): string {
  const { year, month, day } = parts(iso);
  return `${pad(day)}.${pad(month)}.${year}`;
}

export function formatDayLong(iso: string): string {
  const { year, month, day } = parts(iso);
  const weekday = new Date(Date.UTC(year, month - 1, day)).getUTCDay();
  return `${WEEKDAYS[weekday]}, ${day} ${MONTHS_GENITIVE[month - 1]}`;
}

export function monthShort(iso: string): string {
  return MONTHS_SHORT[parts(iso).month - 1]!;
}

/** "2026-03-02T09:30:00(+00:00)" → "02.03.2026, 09:30" — the time as the API wrote it. */
export function formatDateTime(iso: string): string {
  return `${formatDate(iso)}, ${iso.slice(11, 16)}`;
}

export function formatDays(days: number): string {
  return days === 1 ? "1 dzień" : `${days} dni`;
}

export function todayIso(now: Date = new Date()): string {
  return `${now.getFullYear()}-${pad(now.getMonth() + 1)}-${pad(now.getDate())}`;
}

export function addMonths(iso: string, months: number): string {
  const { year, month, day } = parts(iso);
  const index = year * 12 + (month - 1) + months;
  const targetYear = Math.floor(index / 12);
  const targetMonth = (index % 12) + 1;
  const lastDay = new Date(Date.UTC(targetYear, targetMonth, 0)).getUTCDate();
  return `${targetYear}-${pad(targetMonth)}-${pad(Math.min(day, lastDay))}`;
}
```

`web/src/format/index.ts`:

```ts
export { fromCents, signOf, sumMoney, toCents } from "./decimal";
export { MINUS, NBSP, formatDecimal, formatMoney, formatPercent, moneyParts } from "./money";
export { addMonths, formatDate, formatDateTime, formatDayLong, formatDays, monthShort, todayIso } from "./dates";
```

- [ ] **Step 5: Uruchom testy**

Run (z `web/`): `npm test -- src/format` → Expected: PASS.
Run: `npm run typecheck` → Expected: brak błędów.

- [ ] **Step 6: Commit**

```bash
git add web/src/format
git commit -m "feat(web): Polish money, percent and date formatting on decimal strings

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 3: Klient API — typy, `request()`, odświeżanie sesji, endpointy

**Files:**
- Create: `web/src/api/types.ts`, `web/src/api/client.ts`, `web/src/api/endpoints.ts`, `web/src/api/queryKeys.ts`, `web/src/api/client.test.ts`

**Interfaces:**
- Consumes: nic.
- Produces:
  - `client.ts`: `class ApiError extends Error { status: number; code: string; details: Record<string, unknown> }`; `NETWORK_MESSAGE`; `setAccessToken(token: string | null)`, `getAccessToken()`; `setSessionExpiredHandler(handler: () => void)`; `refreshSession(): Promise<boolean>` (jedno odświeżenie naraz; błąd sieci → `ApiError` z `code "network"`); `request<T>(path: string, options?: { method?: string; query?: Record<string, string | number | null | undefined>; json?: unknown; form?: FormData; auth?: boolean }): Promise<T>`.
  - `types.ts`: typy odpowiedzi (poniżej) — kwoty jako `Money = string`.
  - `endpoints.ts`: obiekt `api` z metodami `login`, `register`, `logout`, `me`, `accounts`, `summary`, `history`, `exposure`, `positions`, `position`, `previewImport`, `commitImport` (sygnatury w kodzie).
  - `queryKeys.ts`: `keys` — `accounts`, `summary(accountId)`, `history(accountId, from)`, `exposure(accountId, day)`, `positions(accountId)`, `position(accountId, instrumentId)`; wszystkie oprócz `accounts` zaczynają się od `"portfolio"` (unieważnianie po imporcie i po przeliczeniu jednym `["portfolio"]`).

- [ ] **Step 1: Testy**

`web/src/api/client.test.ts`:

```ts
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ApiError, NETWORK_MESSAGE, getAccessToken, refreshSession, request, setAccessToken, setSessionExpiredHandler } from "./client";

type Handler = (url: string, init: RequestInit) => Response | Promise<Response>;

function json(status: number, body: unknown): Response {
  return new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });
}

let handler: Handler;
const calls: { url: string; init: RequestInit }[] = [];

beforeEach(() => {
  calls.length = 0;
  setAccessToken("old");
  setSessionExpiredHandler(() => {});
  vi.stubGlobal("fetch", vi.fn(async (url: string, init: RequestInit) => {
    calls.push({ url, init });
    return handler(url, init);
  }));
});

afterEach(() => vi.unstubAllGlobals());

const auth = (init: RequestInit) => new Headers(init.headers).get("Authorization");

describe("request", () => {
  it("sends the token, same-origin credentials and the query without empty values", async () => {
    handler = () => json(200, { ok: true });

    await expect(request("/api/positions", { query: { account_id: 3, date: null } })).resolves.toEqual({ ok: true });

    expect(calls[0]!.url).toBe("/api/positions?account_id=3");
    expect(calls[0]!.init.credentials).toBe("same-origin");
    expect(auth(calls[0]!.init)).toBe("Bearer old");
  });

  it("turns the API error format into an ApiError with the Polish message", async () => {
    handler = () => json(404, { code: "not_found", message: "Nie znaleziono.", details: { id: 7 } });

    const error = await request("/api/positions/1/2").catch((e: unknown) => e);

    expect(error).toBeInstanceOf(ApiError);
    expect(error).toMatchObject({ status: 404, code: "not_found", message: "Nie znaleziono.", details: { id: 7 } });
  });

  it("reports a network failure in words, not as a crash", async () => {
    handler = () => Promise.reject(new TypeError("Failed to fetch"));

    await expect(request("/api/portfolio/summary")).rejects.toMatchObject({ code: "network", message: NETWORK_MESSAGE });
  });

  it("refreshes once for many parallel 401s and repeats each request with the new token", async () => {
    let refreshes = 0;
    handler = async (url, init) => {
      if (url === "/api/auth/refresh") {
        refreshes += 1;
        await new Promise((resolve) => setTimeout(resolve, 5));
        return json(200, { access_token: "new", token_type: "bearer" });
      }
      return auth(init) === "Bearer new" ? json(200, { url }) : json(401, { code: "unauthorized", message: "x", details: {} });
    };

    const results = await Promise.all(["/api/a", "/api/b", "/api/c"].map((path) => request<{ url: string }>(path)));

    expect(results.map((r) => r.url)).toEqual(["/api/a", "/api/b", "/api/c"]);
    expect(refreshes).toBe(1);
    expect(getAccessToken()).toBe("new");
  });

  it("calls the expiry handler when the refresh is refused", async () => {
    const expired = vi.fn();
    setSessionExpiredHandler(expired);
    handler = () => json(401, { code: "invalid_refresh", message: "Sesja wygasła.", details: {} });

    await expect(request("/api/portfolio/summary")).rejects.toMatchObject({ status: 401 });
    expect(expired).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });

  it("does not refresh for requests that do not use the session", async () => {
    handler = () => json(401, { code: "invalid_credentials", message: "Nieprawidłowy e-mail lub hasło.", details: {} });

    await expect(request("/api/auth/login", { method: "POST", json: {}, auth: false })).rejects.toMatchObject({
      code: "invalid_credentials",
    });
    expect(calls).toHaveLength(1);
  });

  it("sends JSON and multipart bodies and returns nothing for 204", async () => {
    handler = () => new Response(null, { status: 204 });
    const form = new FormData();
    form.append("files", new Blob(["x"]), "a.xlsx");

    await request("/api/x", { method: "POST", json: { a: 1 } });
    await request("/api/y", { method: "POST", form });

    expect(new Headers(calls[0]!.init.headers).get("Content-Type")).toBe("application/json");
    expect(calls[0]!.init.body).toBe('{"a":1}');
    expect(new Headers(calls[1]!.init.headers).get("Content-Type")).toBeNull();
    expect(calls[1]!.init.body).toBe(form);
  });
});

describe("refreshSession", () => {
  it("returns false and clears the token when there is no session", async () => {
    handler = () => json(401, { code: "invalid_refresh", message: "x", details: {} });
    await expect(refreshSession()).resolves.toBe(false);
    expect(getAccessToken()).toBeNull();
  });

  it("throws a network ApiError when the API cannot be reached", async () => {
    handler = () => Promise.reject(new TypeError("Failed to fetch"));
    await expect(refreshSession()).rejects.toMatchObject({ code: "network" });
  });
});
```

- [ ] **Step 2: Uruchom — mają nie przejść**

Run (z `web/`): `npm test -- src/api`
Expected: FAIL — `Failed to resolve import "./client"`.

- [ ] **Step 3: `client.ts`**

`web/src/api/client.ts`:

```ts
/** The only place that talks HTTP: bearer token in memory, one refresh at a time, API errors as ApiError. */

export const NETWORK_MESSAGE = "Brak połączenia z serwerem. Sprawdź, czy API działa, i spróbuj ponownie.";

export class ApiError extends Error {
  readonly status: number;
  readonly code: string;
  readonly details: Record<string, unknown>;

  constructor(status: number, code: string, message: string, details: Record<string, unknown> = {}) {
    super(message);
    this.name = "ApiError";
    this.status = status;
    this.code = code;
    this.details = details;
  }
}

let accessToken: string | null = null;
let onSessionExpired: () => void = () => {};
let refreshing: Promise<boolean> | null = null;

export function setAccessToken(token: string | null): void {
  accessToken = token;
}

export function getAccessToken(): string | null {
  return accessToken;
}

export function setSessionExpiredHandler(handler: () => void): void {
  onSessionExpired = handler;
}

const networkError = () => new ApiError(0, "network", NETWORK_MESSAGE);

async function toApiError(response: Response): Promise<ApiError> {
  try {
    const body = (await response.json()) as { code?: string; message?: string; details?: Record<string, unknown> };
    if (body.code && body.message) return new ApiError(response.status, body.code, body.message, body.details ?? {});
  } catch {
    // not the API's JSON error format
  }
  return new ApiError(response.status, "http_error", `Serwer odpowiedział błędem ${response.status}. Spróbuj ponownie.`);
}

/** Exchanges the httpOnly refresh cookie for a new access token. Concurrent callers share one request. */
export function refreshSession(): Promise<boolean> {
  refreshing ??= (async () => {
    try {
      let response: Response;
      try {
        response = await fetch("/api/auth/refresh", { method: "POST", credentials: "same-origin" });
      } catch {
        throw networkError();
      }
      if (!response.ok) {
        accessToken = null;
        return false;
      }
      accessToken = ((await response.json()) as { access_token: string }).access_token;
      return true;
    } finally {
      refreshing = null;
    }
  })();
  return refreshing;
}

type Query = Record<string, string | number | null | undefined>;

export interface RequestOptions {
  method?: string;
  query?: Query;
  json?: unknown;
  form?: FormData;
  /** false for login, register and logout: a 401 there is an answer, not an expired session */
  auth?: boolean;
}

function withQuery(path: string, query: Query | undefined): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}

export async function request<T>(path: string, options: RequestOptions = {}): Promise<T> {
  const url = withQuery(path, options.query);
  const useSession = options.auth !== false;
  let sentWith: string | null = null;
  const send = async () => {
    const headers = new Headers();
    if (options.json !== undefined) headers.set("Content-Type", "application/json");
    sentWith = accessToken;
    if (useSession && accessToken) headers.set("Authorization", `Bearer ${accessToken}`);
    try {
      return await fetch(url, {
        method: options.method ?? "GET",
        credentials: "same-origin",
        headers,
        body: options.form ?? (options.json !== undefined ? JSON.stringify(options.json) : undefined),
      });
    } catch {
      throw networkError();
    }
  };

  let response = await send();
  if (response.status === 401 && useSession) {
    if (accessToken !== null && accessToken !== sentWith) {
      response = await send(); // another request refreshed the session meanwhile
    } else if (await refreshSession()) {
      response = await send();
    } else {
      onSessionExpired();
      throw await toApiError(response);
    }
  }
  if (!response.ok) throw await toApiError(response);
  if (response.status === 204) return undefined as T;
  return (await response.json()) as T;
}
```

- [ ] **Step 4: `types.ts`, `endpoints.ts`, `queryKeys.ts`**

`web/src/api/types.ts`:

```ts
/** Response shapes of the API (api/app/*/schemas.py). Decimals arrive as strings and stay strings. */
export type Money = string;
export type IsoDate = string; // "2026-09-26"
export type IsoDateTime = string; // "2026-03-02T09:30:00"

export interface TokenOut { access_token: string; token_type: string }
export interface UserOut { id: number; email: string; base_currency: string }
export interface RegisterIn { email: string; password: string; invite_code?: string }

export interface Account {
  id: number;
  name: string;
  kind: "broker" | "bonds" | "savings" | "cash";
  wrapper: "regular" | "ike" | "ikze";
  broker: string | null;
  external_account_number: string | null;
  currency: string;
  created_at: IsoDateTime;
}

export interface Allocation { key: string; name: string; value_pln: Money; share_pct: Money | null }

export interface Summary {
  as_of: IsoDate | null;
  value_pln: Money;
  cash_pln: Money;
  invested_pln: Money;
  total_gain_pln: Money;
  total_gain_pct: Money | null;
  day_change_pln: Money | null;
  day_change_pct: Money | null;
  twr_pct: Money | null;
  dividends_net_pln: Money;
  interest_net_pln: Money;
  fees_pln: Money;
  by_account: Allocation[];
  by_kind: Allocation[];
  approximate_positions: number;
  recalculating: boolean;
}

export interface HistoryPoint { date: IsoDate; value_pln: Money; invested_pln: Money; net_flow_pln: Money; twr_pct: Money | null }
export interface HistoryEvent { date: IsoDate; type: string; amount_pln: Money }
export interface History { points: HistoryPoint[]; events: HistoryEvent[] }

export interface ExposureItem { currency: string; value_pln: Money; share_pct: Money | null }
export interface Exposure { as_of: IsoDate | null; current: ExposureItem[]; history: { date: IsoDate; values: Record<string, Money> }[] }

export interface Position {
  kind: "instrument" | "cash" | "bond" | "savings";
  account_id: number;
  account_name: string;
  instrument_id: number | null;
  ticker: string | null;
  name: string;
  category: string | null;
  currency: string | null;
  quantity: Money;
  price: Money | null;
  price_date: IsoDate | null;
  price_source: "provider" | "xtb" | null;
  value_pln: Money;
  cost_pln: Money;
  unrealized_pln: Money;
  unrealized_pct: Money | null;
  price_effect_pln: Money;
  fx_effect_pln: Money;
  dividends_net_pln: Money;
  fees_pln: Money;
  realized_pln: Money;
  day_change_pln: Money;
  share_pct: Money | null;
  flags: string[];
  bond_holding_id: number | null;
  savings_account_id: number | null;
}

export interface Lot {
  position_id: string | null;
  opened_on: IsoDate;
  quantity: Money;
  open_price: Money | null;
  cost_pln: Money;
  value_pln: Money;
  gain_pln: Money;
  price_effect_pln: Money;
  fx_effect_pln: Money;
  holding_days: number;
  stop_loss: Money | null;
  take_profit: Money | null;
}

export interface Sale {
  date: IsoDate;
  opened_on: IsoDate;
  holding_days: number;
  quantity: Money;
  proceeds_pln: Money;
  cost_pln: Money;
  realized_pln: Money;
  price_effect_pln: Money;
  fx_effect_pln: Money;
  position_id: string | null;
  matched: boolean;
}

export interface Income { date: IsoDate; type: string; amount: Money; currency: string; amount_pln: Money }

export interface Transaction {
  id: number;
  account_id: number;
  ticker: string | null;
  type: string;
  xtb_type: string;
  occurred_at: IsoDateTime;
  amount: Money;
  currency: string;
  quantity: Money | null;
  price: Money | null;
  implied_fx_rate: Money | null;
  xtb_position_id: string | null;
  external_id: string;
  comment: string;
  transfer_pair_id: number | null;
}

export interface Reconciliation {
  status: "ok" | "mismatch" | "no_snapshot";
  taken_at: IsoDateTime | null;
  xtb_quantity: Money | null;
  calculated_quantity: Money | null;
}

export interface PositionDetail {
  position: Position;
  lots: Lot[];
  sales: Sale[];
  income: Income[];
  transactions: Transaction[];
  reconciliation: Reconciliation;
}

export interface ImportWarning { code: string; message: string; details: Record<string, unknown> }
export interface ImportFile {
  filename: string;
  account_number: string;
  wrapper: string;
  currency: string;
  account_id: number | null;
  account_name: string;
  new_account: boolean;
  report_from: IsoDateTime | null;
  report_to: IsoDateTime | null;
  new_transactions: number;
  duplicate_transactions: number;
  unknown_transactions: number;
  open_lots: number;
  closed_lots: number;
  warnings: ImportWarning[];
  import_id: number | null;
}
export interface ImportFileError { filename: string; code: string; message: string }
export interface ImportResult { files: ImportFile[]; errors: ImportFileError[]; skipped: string[] }
```

`web/src/api/endpoints.ts`:

```ts
import { request } from "./client";
import type {
  Account, Exposure, History, ImportResult, IsoDate, Position, PositionDetail, RegisterIn, Summary, TokenOut, UserOut,
} from "./types";

function filesForm(files: File[]): FormData {
  const form = new FormData();
  for (const file of files) form.append("files", file, file.name);
  return form;
}

export const api = {
  login: (email: string, password: string) =>
    request<TokenOut>("/api/auth/login", { method: "POST", json: { email, password }, auth: false }),
  register: (body: RegisterIn) => request<UserOut>("/api/auth/register", { method: "POST", json: body, auth: false }),
  logout: () => request<void>("/api/auth/logout", { method: "POST", auth: false }),
  me: () => request<UserOut>("/api/auth/me"),
  accounts: () => request<Account[]>("/api/accounts"),
  summary: (accountId: number | null) => request<Summary>("/api/portfolio/summary", { query: { account_id: accountId } }),
  history: (accountId: number | null, from: IsoDate | null) =>
    request<History>("/api/portfolio/history", { query: { account_id: accountId, from } }),
  exposure: (accountId: number | null, day: IsoDate) =>
    request<Exposure>("/api/portfolio/exposure", { query: { account_id: accountId, from: day, to: day } }),
  positions: (accountId: number | null) => request<Position[]>("/api/positions", { query: { account_id: accountId } }),
  position: (accountId: number, instrumentId: number) =>
    request<PositionDetail>(`/api/positions/${accountId}/${instrumentId}`),
  previewImport: (files: File[]) => request<ImportResult>("/api/imports/preview", { method: "POST", form: filesForm(files) }),
  commitImport: (files: File[]) => request<ImportResult>("/api/imports", { method: "POST", form: filesForm(files) }),
};
```

`web/src/api/queryKeys.ts`:

```ts
/** TanStack Query keys. Everything valued starts with "portfolio", so one invalidation refreshes it all. */
export const keys = {
  accounts: ["accounts"] as const,
  portfolio: ["portfolio"] as const,
  summary: (accountId: number | null) => ["portfolio", "summary", accountId] as const,
  history: (accountId: number | null, from: string | null) => ["portfolio", "history", accountId, from] as const,
  exposure: (accountId: number | null, day: string) => ["portfolio", "exposure", accountId, day] as const,
  positions: (accountId: number | null) => ["portfolio", "positions", accountId] as const,
  position: (accountId: number, instrumentId: number) => ["portfolio", "position", accountId, instrumentId] as const,
};
```

- [ ] **Step 5: Uruchom testy**

Run (z `web/`): `npm test -- src/api` → Expected: PASS.
Run: `npm run typecheck` → Expected: brak błędów.

- [ ] **Step 6: Commit**

```bash
git add web/src/api
git commit -m "feat(web): API client with in-memory token, single-flight refresh and typed endpoints

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 4: Sesja, logowanie i rejestracja

**Files:**
- Create: `web/src/api/messages.ts`, `web/src/providers.tsx`, `web/src/auth/session.tsx`, `web/src/auth/RequireAuth.tsx`, `web/src/auth/LoginScreen.tsx`, `web/src/auth/RegisterScreen.tsx`, `web/src/auth/AuthScreens.module.css`, `web/src/test/render.tsx`, `web/src/auth/auth.test.tsx`
- Modify: `web/src/test/setup.ts`

**Interfaces:**
- Consumes: `api`, `ApiError`, `NETWORK_MESSAGE`, `refreshSession`, `setAccessToken`, `setSessionExpiredHandler` (Task 3).
- Produces:
  - `messages.ts`: `errorMessage(error: unknown): string` (ApiError → jego `message`, inaczej „Coś poszło nie tak. Spróbuj ponownie.”).
  - `providers.tsx`: `createQueryClient(options?: { test?: boolean }): QueryClient`; `AppProviders({ client, children })` (QueryClientProvider + SessionProvider).
  - `session.tsx`: `SessionProvider`, `useSession(): { state: SessionState; signIn(email, password): Promise<void>; register(body: RegisterIn): Promise<void>; signOut(): Promise<void> }`, `type SessionState = { status: "loading" } | { status: "anonymous"; expired: boolean } | { status: "signedIn"; user: UserOut }`.
  - `RequireAuth.tsx`: `RequireAuth` (trasa-układ: zalogowany → `<Outlet/>`, inaczej `<Navigate to="/logowanie" state={{ from, expired }}/>`), `GuestOnly` (zalogowany → przekierowanie na `state.from ?? "/"`), `Splash`.
  - `LoginScreen`, `RegisterScreen`.
  - `test/render.tsx`: `mockFetch(routes: MockRoute[])` (zwraca `vi.fn`), `json(status, body): Response`, `USER`, `SIGNED_IN: MockRoute[]` (refresh + me), `renderRoutes(routes: RouteObject[], path?: string): { user, router, client }`; `MockRoute = { method?: string; path: string | RegExp; respond: (url: URL, init: RequestInit) => unknown; status?: number }`.

- [ ] **Step 1: Pomocnicze testowe**

`web/src/test/setup.ts` (zastąp):

```ts
import "@testing-library/jest-dom/vitest";
import { cleanup } from "@testing-library/react";
import { afterEach, vi } from "vitest";
import { setAccessToken } from "../api/client";

afterEach(() => {
  cleanup();
  vi.unstubAllGlobals();
  setAccessToken(null);
});
```

`web/src/test/render.tsx`:

```tsx
import { render } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouterProvider, createMemoryRouter, type RouteObject } from "react-router";
import { vi } from "vitest";
import { AppProviders, createQueryClient } from "../providers";

export interface MockRoute {
  method?: string;
  path: string | RegExp;
  respond: (url: URL, init: RequestInit) => unknown;
  status?: number;
}

export function json(status: number, body: unknown): Response {
  return new Response(body === undefined ? null : JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
}

/** Stubs fetch with a routing table; an unmatched request answers 404 in the API's error format. */
export function mockFetch(routes: MockRoute[]) {
  const fetchMock = vi.fn(async (input: string, init: RequestInit = {}): Promise<Response> => {
    const url = new URL(input, "http://localhost");
    const method = init.method ?? "GET";
    const route = routes.find(
      (r) => (r.method ?? "GET") === method && (typeof r.path === "string" ? url.pathname === r.path : r.path.test(url.pathname)),
    );
    if (!route) return json(404, { code: "not_found", message: "Nie znaleziono.", details: {} });
    const out = await route.respond(url, init);
    return out instanceof Response ? out : json(route.status ?? 200, out);
  });
  vi.stubGlobal("fetch", fetchMock);
  return fetchMock;
}

export const USER = { id: 1, email: "anna@portfolio.dev", base_currency: "PLN" };

/** A signed-in session: the refresh cookie is valid and /me answers. */
export const SIGNED_IN: MockRoute[] = [
  { method: "POST", path: "/api/auth/refresh", respond: () => ({ access_token: "token", token_type: "bearer" }) },
  { path: "/api/auth/me", respond: () => USER },
];

export function renderRoutes(routes: RouteObject[], path = "/") {
  const client = createQueryClient({ test: true });
  const router = createMemoryRouter(routes, { initialEntries: [path] });
  const user = userEvent.setup();
  render(
    <AppProviders client={client}>
      <RouterProvider router={router} />
    </AppProviders>,
  );
  return { user, router, client };
}
```

- [ ] **Step 2: Testy**

`web/src/auth/auth.test.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { screen, waitFor } from "@testing-library/react";
import type { RouteObject } from "react-router";
import { describe, expect, it } from "vitest";
import { NETWORK_MESSAGE } from "../api/client";
import { api } from "../api/endpoints";
import { SIGNED_IN, USER, json, mockFetch, renderRoutes, type MockRoute } from "../test/render";
import { LoginScreen } from "./LoginScreen";
import { RegisterScreen } from "./RegisterScreen";
import { GuestOnly, RequireAuth } from "./RequireAuth";
import { useSession } from "./session";

function Protected() {
  const { state } = useSession();
  const summary = useQuery({ queryKey: ["summary"], queryFn: () => api.summary(null) });
  return <p>Witaj {state.status === "signedIn" ? state.user.email : ""} {summary.data ? "z danymi" : ""}</p>;
}

const ROUTES: RouteObject[] = [
  { element: <GuestOnly />, children: [{ path: "/logowanie", element: <LoginScreen /> }, { path: "/rejestracja", element: <RegisterScreen /> }] },
  { element: <RequireAuth />, children: [{ path: "/", element: <Protected /> }] },
];

const NO_SESSION: MockRoute = {
  method: "POST", path: "/api/auth/refresh", status: 401,
  respond: () => ({ code: "invalid_refresh", message: "Zaloguj się ponownie.", details: {} }),
};
const SUMMARY: MockRoute = { path: "/api/portfolio/summary", respond: () => ({ as_of: null }) };
const WELCOME = `Witaj ${USER.email} z danymi`;

describe("session", () => {
  it("sends a visitor without a session to the login screen", async () => {
    mockFetch([NO_SESSION]);
    renderRoutes(ROUTES, "/");
    expect(await screen.findByRole("heading", { name: "Portfel" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zaloguj się" })).toBeInTheDocument();
  });

  it("restores the session from the refresh cookie", async () => {
    mockFetch([...SIGNED_IN, SUMMARY]);
    renderRoutes(ROUTES, "/");
    expect(await screen.findByText(WELCOME)).toBeInTheDocument();
  });

  it("logs in, shows the API's message on a wrong password and returns to the page asked for", async () => {
    let attempts = 0;
    mockFetch([
      NO_SESSION,
      {
        method: "POST", path: "/api/auth/login",
        respond: () => (++attempts === 1
          ? json(401, { code: "invalid_credentials", message: "Nieprawidłowy e-mail lub hasło.", details: {} })
          : { access_token: "token", token_type: "bearer" }),
      },
      { path: "/api/auth/me", respond: () => USER },
      SUMMARY,
    ]);
    const { user } = renderRoutes(ROUTES, "/");

    await user.type(await screen.findByLabelText("E-mail"), "anna@portfolio.dev");
    await user.type(screen.getByLabelText("Hasło"), "zle-haslo-123");
    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByRole("alert")).toHaveTextContent("Nieprawidłowy e-mail lub hasło.");

    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByText(WELCOME)).toBeInTheDocument();
  });

  it("returns to the login screen with a note when the session expires", async () => {
    let refreshes = 0;
    mockFetch([
      {
        method: "POST", path: "/api/auth/refresh",
        respond: () => (++refreshes === 1
          ? { access_token: "token", token_type: "bearer" }
          : json(401, { code: "invalid_refresh", message: "x", details: {} })),
      },
      { path: "/api/auth/me", respond: () => USER },
      { path: "/api/portfolio/summary", status: 401, respond: () => ({ code: "unauthorized", message: "x", details: {} }) },
    ]);
    renderRoutes(ROUTES, "/");
    expect(await screen.findByText("Sesja wygasła, zaloguj się ponownie.")).toBeInTheDocument();
  });

  it("shows the connection problem instead of failing silently when the API is down", async () => {
    const fetchMock = mockFetch([]);
    fetchMock.mockImplementation(() => Promise.reject(new TypeError("Failed to fetch")));
    const { user } = renderRoutes(ROUTES, "/");

    await user.type(await screen.findByLabelText("E-mail"), "anna@portfolio.dev");
    await user.type(screen.getByLabelText("Hasło"), "haslo-123456");
    await user.click(screen.getByRole("button", { name: "Zaloguj się" }));
    expect(await screen.findByRole("alert")).toHaveTextContent(NETWORK_MESSAGE);
  });
});

describe("registration", () => {
  it("checks the password length before asking the API", async () => {
    const fetchMock = mockFetch([NO_SESSION]);
    const { user } = renderRoutes(ROUTES, "/rejestracja");

    await user.type(await screen.findByLabelText("E-mail"), "nowy@portfolio.dev");
    await user.type(screen.getByLabelText("Hasło"), "krotkie");
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Hasło musi mieć co najmniej 10 znaków.");
    expect(fetchMock.mock.calls.some(([url]) => String(url).includes("/register"))).toBe(false);
  });

  it("asks for an invite code only when the API requires one, then signs in", async () => {
    const bodies: Record<string, unknown>[] = [];
    mockFetch([
      NO_SESSION,
      {
        method: "POST", path: "/api/auth/register",
        respond: (_url, init) => {
          const body = JSON.parse(String(init.body)) as Record<string, unknown>;
          bodies.push(body);
          return body.invite_code === "ZAPROSZENIE"
            ? json(201, USER)
            : json(403, { code: "invite_required", message: "Rejestracja wymaga ważnego kodu zaproszenia.", details: {} });
        },
      },
      { method: "POST", path: "/api/auth/login", respond: () => ({ access_token: "token", token_type: "bearer" }) },
      { path: "/api/auth/me", respond: () => USER },
      SUMMARY,
    ]);
    const { user } = renderRoutes(ROUTES, "/rejestracja");

    await user.type(await screen.findByLabelText("E-mail"), USER.email);
    expect(screen.queryByLabelText("Kod zaproszenia")).not.toBeInTheDocument();
    await user.type(screen.getByLabelText("Hasło"), "dlugie-haslo-1");
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    expect(await screen.findByRole("alert")).toHaveTextContent("Rejestracja wymaga ważnego kodu zaproszenia.");
    await user.type(screen.getByLabelText("Kod zaproszenia"), "ZAPROSZENIE");
    await user.click(screen.getByRole("button", { name: "Załóż konto" }));

    expect(await screen.findByText(WELCOME)).toBeInTheDocument();
    await waitFor(() => expect(bodies.at(-1)).toMatchObject({ email: USER.email, invite_code: "ZAPROSZENIE" }));
    expect(bodies[0]).not.toHaveProperty("invite_code");
  });
});
```

- [ ] **Step 3: Uruchom — mają nie przejść**

Run (z `web/`): `npm test -- src/auth`
Expected: FAIL — `Failed to resolve import "../providers"`.

- [ ] **Step 4: `messages.ts`, `providers.tsx`, `session.tsx`**

`web/src/api/messages.ts`:

```ts
import { ApiError } from "./client";

export function errorMessage(error: unknown): string {
  return error instanceof ApiError ? error.message : "Coś poszło nie tak. Spróbuj ponownie.";
}
```

`web/src/providers.tsx`:

```tsx
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { ApiError } from "./api/client";
import { SessionProvider } from "./auth/session";

/** Retries only what may heal by itself (no connection, server errors); never 4xx. */
export function createQueryClient({ test = false }: { test?: boolean } = {}): QueryClient {
  return new QueryClient({
    defaultOptions: {
      queries: {
        staleTime: 30_000,
        refetchOnWindowFocus: !test,
        retry: test ? false : (count, error) => error instanceof ApiError && (error.status === 0 || error.status >= 500) && count < 2,
      },
      mutations: { retry: false },
    },
  });
}

export function AppProviders({ client, children }: { client: QueryClient; children: ReactNode }) {
  return (
    <QueryClientProvider client={client}>
      <SessionProvider>{children}</SessionProvider>
    </QueryClientProvider>
  );
}
```

`web/src/auth/session.tsx`:

```tsx
import { useQueryClient } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";
import { refreshSession, setAccessToken, setSessionExpiredHandler } from "../api/client";
import { api } from "../api/endpoints";
import type { RegisterIn, UserOut } from "../api/types";

export type SessionState =
  | { status: "loading" }
  | { status: "anonymous"; expired: boolean }
  | { status: "signedIn"; user: UserOut };

interface Session {
  state: SessionState;
  signIn(email: string, password: string): Promise<void>;
  register(body: RegisterIn): Promise<void>;
  signOut(): Promise<void>;
}

const SessionContext = createContext<Session | null>(null);

export function SessionProvider({ children }: { children: ReactNode }) {
  const queryClient = useQueryClient();
  const [state, setState] = useState<SessionState>({ status: "loading" });

  useEffect(() => {
    setSessionExpiredHandler(() => {
      setAccessToken(null);
      queryClient.clear();
      setState({ status: "anonymous", expired: true });
    });
    let cancelled = false;
    (async () => {
      try {
        if (await refreshSession()) {
          const user = await api.me();
          if (!cancelled) setState({ status: "signedIn", user });
          return;
        }
      } catch {
        // no connection: the login screen says so on the first attempt
      }
      if (!cancelled) setState({ status: "anonymous", expired: false });
    })();
    return () => {
      cancelled = true;
    };
  }, [queryClient]);

  const signIn = useCallback(async (email: string, password: string) => {
    const token = await api.login(email, password);
    setAccessToken(token.access_token);
    const user = await api.me();
    setState({ status: "signedIn", user });
  }, []);

  const register = useCallback(async (body: RegisterIn) => {
    await api.register(body);
    await signIn(body.email, body.password);
  }, [signIn]);

  const signOut = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      setAccessToken(null);
      queryClient.clear();
      setState({ status: "anonymous", expired: false });
    }
  }, [queryClient]);

  const value = useMemo(() => ({ state, signIn, register, signOut }), [state, signIn, register, signOut]);
  return <SessionContext.Provider value={value}>{children}</SessionContext.Provider>;
}

export function useSession(): Session {
  const session = useContext(SessionContext);
  if (!session) throw new Error("useSession outside SessionProvider");
  return session;
}
```

- [ ] **Step 5: Ochrona tras i ekrany**

`web/src/auth/RequireAuth.tsx`:

```tsx
import { Navigate, Outlet, useLocation } from "react-router";
import styles from "./AuthScreens.module.css";
import { useSession } from "./session";

export function Splash() {
  return <div className={styles.splash} aria-busy="true" aria-label="Wczytuję" />;
}

export function RequireAuth() {
  const { state } = useSession();
  const location = useLocation();
  if (state.status === "loading") return <Splash />;
  if (state.status === "anonymous") {
    return <Navigate to="/logowanie" replace state={{ from: location.pathname, expired: state.expired }} />;
  }
  return <Outlet />;
}

export function GuestOnly() {
  const { state } = useSession();
  const location = useLocation();
  if (state.status === "loading") return <Splash />;
  if (state.status === "signedIn") {
    const from = (location.state as { from?: string } | null)?.from;
    return <Navigate to={from && from !== "/logowanie" ? from : "/"} replace />;
  }
  return <Outlet />;
}
```

`web/src/auth/LoginScreen.tsx`:

```tsx
import { useState, type FormEvent } from "react";
import { Link, useLocation } from "react-router";
import { errorMessage } from "../api/messages";
import styles from "./AuthScreens.module.css";
import { useSession } from "./session";

export function LoginScreen() {
  const { signIn } = useSession();
  const location = useLocation();
  const expired = (location.state as { expired?: boolean } | null)?.expired === true;
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError(null);
    try {
      await signIn(email.trim(), password); // GuestOnly then moves on to the page asked for
    } catch (err) {
      setError(errorMessage(err));
      setBusy(false);
    }
  }

  return (
    <main className={styles.screen}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <h1 className={styles.title}>Portfel</h1>
        <p className={styles.lead}>Zaloguj się, żeby zobaczyć swój portfel.</p>
        {expired && <p className={styles.notice} role="status">Sesja wygasła, zaloguj się ponownie.</p>}
        <div className={styles.field}>
          <label htmlFor="login-email">E-mail</label>
          <input id="login-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className={styles.field}>
          <label htmlFor="login-password">Hasło</label>
          <input id="login-password" type="password" autoComplete="current-password" value={password}
            onChange={(e) => setPassword(e.target.value)} required />
        </div>
        {error && <p className={styles.error} role="alert">{error}</p>}
        <button className={styles.primary} type="submit" disabled={busy}>Zaloguj się</button>
        <p className={styles.switch}>Nie masz konta? <Link to="/rejestracja">Załóż konto</Link></p>
      </form>
    </main>
  );
}
```

`web/src/auth/RegisterScreen.tsx`:

```tsx
import { useState, type FormEvent } from "react";
import { Link } from "react-router";
import { ApiError } from "../api/client";
import { errorMessage } from "../api/messages";
import styles from "./AuthScreens.module.css";
import { useSession } from "./session";

const MIN_PASSWORD = 10;
const PASSWORD_TOO_SHORT = `Hasło musi mieć co najmniej ${MIN_PASSWORD} znaków.`;

function registrationError(error: unknown): string {
  if (error instanceof ApiError && error.code === "validation_error") {
    const fields = ((error.details.errors as { loc: string[] }[] | undefined) ?? []).flatMap((e) => e.loc);
    if (fields.includes("password")) return PASSWORD_TOO_SHORT;
    if (fields.includes("email")) return "Podaj poprawny adres e-mail.";
  }
  return errorMessage(error);
}

export function RegisterScreen() {
  const { register } = useSession();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [inviteCode, setInviteCode] = useState("");
  const [needsInvite, setNeedsInvite] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    if (password.length < MIN_PASSWORD) {
      setError(PASSWORD_TOO_SHORT);
      return;
    }
    setBusy(true);
    try {
      await register({ email: email.trim(), password, ...(needsInvite ? { invite_code: inviteCode.trim() } : {}) });
    } catch (err) {
      if (err instanceof ApiError && err.code === "invite_required") setNeedsInvite(true);
      setError(registrationError(err));
      setBusy(false);
    }
  }

  return (
    <main className={styles.screen}>
      <form className={styles.form} onSubmit={submit} noValidate>
        <h1 className={styles.title}>Załóż konto</h1>
        <p className={styles.lead}>Twoje dane widzisz tylko ty.</p>
        <div className={styles.field}>
          <label htmlFor="register-email">E-mail</label>
          <input id="register-email" type="email" autoComplete="email" value={email} onChange={(e) => setEmail(e.target.value)} required />
        </div>
        <div className={styles.field}>
          <label htmlFor="register-password">Hasło</label>
          <input id="register-password" type="password" autoComplete="new-password" value={password}
            onChange={(e) => setPassword(e.target.value)} aria-describedby="register-password-hint" required />
          <small id="register-password-hint" className={styles.hint}>Co najmniej {MIN_PASSWORD} znaków.</small>
        </div>
        {needsInvite && (
          <div className={styles.field}>
            <label htmlFor="register-invite">Kod zaproszenia</label>
            <input id="register-invite" autoComplete="off" value={inviteCode} onChange={(e) => setInviteCode(e.target.value)} />
          </div>
        )}
        {error && <p className={styles.error} role="alert">{error}</p>}
        <button className={styles.primary} type="submit" disabled={busy}>Załóż konto</button>
        <p className={styles.switch}>Masz już konto? <Link to="/logowanie">Zaloguj się</Link></p>
      </form>
    </main>
  );
}
```

`web/src/auth/AuthScreens.module.css`:

```css
.splash { min-height: 100dvh; background: var(--night); }
.screen {
  min-height: 100dvh;
  display: grid;
  place-items: center;
  padding: calc(24px + env(safe-area-inset-top)) 20px calc(24px + env(safe-area-inset-bottom));
}
.form { width: min(100%, 380px); display: grid; gap: 16px; }
.title { font-size: 30px; font-weight: 600; letter-spacing: -.02em; }
.lead { color: var(--dim); margin-top: -8px; }
.field { display: grid; gap: 6px; font-size: 14px; color: var(--dim); }
.field input {
  height: 46px;
  padding: 0 14px;
  background: var(--slab);
  border: 1px solid var(--rule);
  border-radius: var(--r-control);
  color: var(--ink);
  font-size: 16px;
}
.hint { font-size: 12.5px; }
.notice { color: var(--amber); font-size: 14px; }
.error { color: var(--loss); font-size: 14px; }
.primary {
  height: 48px;
  border: 0;
  border-radius: var(--r-control);
  background: var(--amber);
  color: var(--night);
  font-weight: 600;
  font-size: 16px;
  cursor: pointer;
}
.primary:disabled { opacity: .6; cursor: default; }
.switch { color: var(--dim); font-size: 14px; }
.switch a { color: var(--amber); }
```

- [ ] **Step 6: Uruchom testy**

Run (z `web/`): `npm test -- src/auth` → Expected: PASS (7 testów).
Run: `npm test` → Expected: PASS wszystko. Run: `npm run typecheck` → Expected: brak błędów.

- [ ] **Step 7: Commit**

```bash
git add web/src/api/messages.ts web/src/providers.tsx web/src/auth web/src/test
git commit -m "feat(web): session from the refresh cookie, login and registration screens

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 5: Elementy wspólne, nawigacja, trasy i ekran „Więcej”

**Files:**
- Create: `web/src/ui/Amount.tsx`, `web/src/ui/Segmented.tsx`, `web/src/ui/AccountPicker.tsx`, `web/src/ui/States.tsx`, `web/src/ui/ListRow.tsx`, `web/src/ui/ui.module.css`, `web/src/ui/ui.test.tsx`, `web/src/shell/icons.tsx`, `web/src/shell/Nav.tsx`, `web/src/shell/AppShell.tsx`, `web/src/shell/MoreScreen.tsx`, `web/src/shell/shell.module.css`, `web/src/shell/shell.test.tsx`, `web/src/routes.tsx`, `web/src/App.tsx`
- Modify: `web/src/main.tsx`, `web/src/test/render.tsx`

**Interfaces:**
- Consumes: `formatMoney`, `moneyParts`, `signOf` (Task 2); `errorMessage`, `useSession`, `RequireAuth`, `GuestOnly`, `LoginScreen`, `RegisterScreen`, `AppProviders`, `createQueryClient`, `renderRoutes` (Task 4); `Account` (Task 3).
- Produces:
  - `ui/Amount.tsx`: `HeroAmount({ value: string; size?: "l" | "m" })` (duża kwota, grosze w `[data-part=grosze]`, mniejsze „zł”), `Money({ value: string; sign?: boolean; tone?: boolean; currency?: string | null })` (`<span class="num">`, `tone` → `up`/`down` wg znaku).
  - `ui/Segmented.tsx`: `Segmented<T extends string>({ label; options: { value: T; label: string }[]; value: T; onChange(value: T) })`.
  - `ui/AccountPicker.tsx`: `AccountPicker({ accounts: Account[]; value: number | null; onChange(id: number | null); allLabel?: string })` (natywny `<select aria-label="Konto">` w kształcie pigułki), `AccountChips({ accounts; value; onChange })` (przyciski z `aria-pressed`, pierwszy „Wszystkie”).
  - `ui/States.tsx`: `Skeleton({ rows?: number; chart?: boolean })`, `EmptyState({ title: string; action?: ReactNode })`, `ErrorState({ error: unknown; onRetry?: () => void })` (tekst `errorMessage` w `role="alert"`, przycisk „Spróbuj ponownie”), `Recalculating()` („Przeliczam wycenę…”).
  - `ui/ListRow.tsx`: `ListRow({ lead; title; subtitle?; value; detail?; to? })` — z `to` cały wiersz jest linkiem.
  - `ui/ui.module.css`: klasy `page`, `pageTitle`, `section`, `sectionHead`, `sectionTitle`, `sectionMore`, `kv` (siatka etykieta–wartość), `secondary`, `primaryButton` używane przez ekrany.
  - `shell/AppShell.tsx`: `AppShell`; `shell/Nav.tsx`: `Nav` (`<nav aria-label="Główna">`); `shell/MoreScreen.tsx`: `MoreScreen`.
  - `routes.tsx`: `appRoutes: RouteObject[]`, `Placeholder({ title })` dla ekranów z kolejnych zadań (`/` Pulpit, `/pozycje`, `/pozycje/:accountId/:instrumentId`, `/dodaj`); ścieżka nieznana → `/`.
  - `test/render.tsx`: + `renderApp(path?: string)` = `renderRoutes(appRoutes, path)`.

- [ ] **Step 1: Testy**

`web/src/ui/ui.test.tsx`:

```tsx
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { MemoryRouter } from "react-router";
import { describe, expect, it, vi } from "vitest";
import { ApiError } from "../api/client";
import type { Account } from "../api/types";
import { AccountChips, AccountPicker } from "./AccountPicker";
import { HeroAmount, Money } from "./Amount";
import { ListRow } from "./ListRow";
import { Segmented } from "./Segmented";
import { ErrorState } from "./States";

const S = " ";
const ACCOUNTS = [{ id: 1, name: "IKE" }, { id: 2, name: "XTB" }] as Account[];

describe("amounts", () => {
  it("draws the grosze and the currency smaller in a hero amount", () => {
    const { container } = render(<HeroAmount value="184302.17" />);
    expect(container.textContent).toBe(`184${S}302,17zł`);
    expect(container.querySelector("[data-part=grosze]")).toHaveTextContent(",17");
  });

  it("colours a change by its sign", () => {
    render(<><Money value="12.5" sign tone /><Money value="-3" sign tone /><Money value="0" sign tone /></>);
    expect(screen.getByText(`+12,50${S}zł`)).toHaveClass("num", "up");
    expect(screen.getByText(`−3,00${S}zł`)).toHaveClass("down");
    expect(screen.getByText(`0,00${S}zł`)).not.toHaveClass("up");
  });
});

describe("controls", () => {
  it("marks the chosen segment and reports a change", async () => {
    const onChange = vi.fn();
    render(<Segmented label="Zakres" value="1R" onChange={onChange}
      options={[{ value: "1M", label: "1M" }, { value: "1R", label: "1R" }]} />);
    expect(screen.getByRole("button", { name: "1R" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "1M" }));
    expect(onChange).toHaveBeenCalledWith("1M");
  });

  it("chooses the whole portfolio or one account", async () => {
    const onChange = vi.fn();
    render(<AccountPicker accounts={ACCOUNTS} value={null} onChange={onChange} />);
    await userEvent.selectOptions(screen.getByRole("combobox", { name: "Konto" }), "2");
    expect(onChange).toHaveBeenLastCalledWith(2);
    expect(screen.getByRole("option", { name: "Cały portfel" })).toBeInTheDocument();
  });

  it("filters by account with chips", async () => {
    const onChange = vi.fn();
    render(<AccountChips accounts={ACCOUNTS} value={1} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "IKE" })).toHaveAttribute("aria-pressed", "true");
    await userEvent.click(screen.getByRole("button", { name: "Wszystkie" }));
    expect(onChange).toHaveBeenCalledWith(null);
  });
});

describe("states and rows", () => {
  it("says what went wrong and offers a retry", async () => {
    const onRetry = vi.fn();
    render(<ErrorState error={new ApiError(500, "x", "Serwer ma problem.")} onRetry={onRetry} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Serwer ma problem.");
    await userEvent.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(onRetry).toHaveBeenCalled();
  });

  it("makes a whole row a link when it leads somewhere", () => {
    render(<MemoryRouter><ListRow lead="CDR" title="CD Projekt" value="1 zł" to="/pozycje/1/2" /></MemoryRouter>);
    expect(screen.getByRole("link", { name: /CD Projekt/ })).toHaveAttribute("href", "/pozycje/1/2");
  });
});
```

`web/src/shell/shell.test.tsx`:

```tsx
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
```

- [ ] **Step 2: Uruchom — mają nie przejść**

Run (z `web/`): `npm test -- src/ui src/shell`
Expected: FAIL — brak modułów `./AccountPicker` itd. i `renderApp`.

- [ ] **Step 3: Elementy `ui/`**

`web/src/ui/Amount.tsx`:

```tsx
import { formatMoney, moneyParts, signOf } from "../format";
import styles from "./ui.module.css";

export function HeroAmount({ value, size = "l" }: { value: string; size?: "l" | "m" }) {
  const parts = moneyParts(value);
  return (
    <span className={`num ${styles.hero} ${size === "m" ? styles.heroM : ""}`}>
      {parts.sign}{parts.whole}
      <span className={styles.grosze} data-part="grosze">,{parts.grosze}</span>
      <span className={styles.currency}>zł</span>
    </span>
  );
}

export function Money({
  value, sign = false, tone = false, currency,
}: { value: string; sign?: boolean; tone?: boolean; currency?: string | null }) {
  const direction = tone ? signOf(value) : 0;
  const toneClass = direction > 0 ? "up" : direction < 0 ? "down" : "";
  return <span className={`num ${toneClass}`.trim()}>{formatMoney(value, { sign, currency })}</span>;
}
```

`web/src/ui/Segmented.tsx`:

```tsx
import styles from "./ui.module.css";

export function Segmented<T extends string>({
  label, options, value, onChange,
}: { label: string; options: { value: T; label: string }[]; value: T; onChange: (value: T) => void }) {
  return (
    <div className={styles.segmented} role="group" aria-label={label}>
      {options.map((option) => (
        <button key={option.value} type="button" aria-pressed={option.value === value} onClick={() => onChange(option.value)}>
          {option.label}
        </button>
      ))}
    </div>
  );
}
```

`web/src/ui/AccountPicker.tsx`:

```tsx
import type { Account } from "../api/types";
import styles from "./ui.module.css";

export function AccountPicker({
  accounts, value, onChange, allLabel = "Cały portfel",
}: { accounts: Account[]; value: number | null; onChange: (id: number | null) => void; allLabel?: string }) {
  return (
    <span className={styles.picker}>
      <select aria-label="Konto" value={value ?? ""} onChange={(e) => onChange(e.target.value ? Number(e.target.value) : null)}>
        <option value="">{allLabel}</option>
        {accounts.map((account) => <option key={account.id} value={account.id}>{account.name}</option>)}
      </select>
      <svg viewBox="0 0 12 12" aria-hidden="true">
        <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
      </svg>
    </span>
  );
}

export function AccountChips({
  accounts, value, onChange,
}: { accounts: Account[]; value: number | null; onChange: (id: number | null) => void }) {
  return (
    <div className={styles.chips} role="group" aria-label="Filtr kont">
      <button type="button" aria-pressed={value === null} onClick={() => onChange(null)}>Wszystkie</button>
      {accounts.map((account) => (
        <button key={account.id} type="button" aria-pressed={value === account.id} onClick={() => onChange(account.id)}>
          {account.name}
        </button>
      ))}
    </div>
  );
}
```

`web/src/ui/States.tsx`:

```tsx
import type { ReactNode } from "react";
import { errorMessage } from "../api/messages";
import styles from "./ui.module.css";

export function Skeleton({ rows = 3, chart = false }: { rows?: number; chart?: boolean }) {
  return (
    <div className={styles.skeleton} aria-busy="true" aria-label="Wczytuję">
      {chart && <div className={styles.skeletonChart} />}
      {Array.from({ length: rows }, (_, i) => <div key={i} className={styles.skeletonRow} />)}
    </div>
  );
}

export function EmptyState({ title, action }: { title: string; action?: ReactNode }) {
  return (
    <div className={styles.empty}>
      <p>{title}</p>
      {action}
    </div>
  );
}

export function ErrorState({ error, onRetry }: { error: unknown; onRetry?: () => void }) {
  return (
    <div className={styles.errorBox}>
      <p role="alert">{errorMessage(error)}</p>
      {onRetry && <button type="button" className={styles.secondary} onClick={onRetry}>Spróbuj ponownie</button>}
    </div>
  );
}

export function Recalculating() {
  return <p className={styles.recalculating} role="status">Przeliczam wycenę…</p>;
}
```

`web/src/ui/ListRow.tsx`:

```tsx
import type { ReactNode } from "react";
import { Link } from "react-router";
import styles from "./ui.module.css";

export function ListRow({
  lead, title, subtitle, value, detail, to,
}: { lead: ReactNode; title: ReactNode; subtitle?: ReactNode; value: ReactNode; detail?: ReactNode; to?: string }) {
  const body = (
    <>
      <span className={styles.lead}>{lead}</span>
      <span className={styles.rowName}>
        <b>{title}</b>
        {subtitle && <small>{subtitle}</small>}
      </span>
      <span className={styles.rowAmount}>
        <span>{value}</span>
        {detail && <small>{detail}</small>}
      </span>
    </>
  );
  return to ? <Link className={styles.row} to={to}>{body}</Link> : <div className={styles.row}>{body}</div>;
}
```

`web/src/ui/ui.module.css`:

```css
.hero { font-size: 46px; font-weight: 600; letter-spacing: -.035em; line-height: 1; font-stretch: 88%; }
.heroM { font-size: 38px; }
.grosze { font-size: .57em; color: var(--dim); font-weight: 500; letter-spacing: -.01em; }
.currency { font-size: .43em; color: var(--dim); font-weight: 500; margin-left: 6px; letter-spacing: 0; }

.page { display: grid; gap: 24px; }
.pageTitle { font-size: 26px; font-weight: 600; letter-spacing: -.02em; }
.section { display: grid; gap: 12px; }
.sectionHead { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }
.sectionTitle { font-size: 17px; font-weight: 600; }
.sectionMore { color: var(--dim); font-size: 13px; }
.kv { display: grid; grid-template-columns: 1fr auto; gap: 8px 16px; margin: 0; }
.kv dt { color: var(--dim); }
.kv dd { margin: 0; text-align: right; font-variant-numeric: tabular-nums; }

.segmented {
  display: grid; grid-auto-flow: column; grid-auto-columns: 1fr;
  background: var(--slab); border: 1px solid var(--rule); border-radius: var(--r-control); padding: 3px;
}
.segmented button {
  min-height: 38px; background: none; border: 0; color: var(--dim);
  font-weight: 500; font-size: 13.5px; border-radius: 7px; cursor: pointer;
}
.segmented button[aria-pressed="true"] { background: var(--amber-soft); color: var(--amber); }

.picker {
  position: relative; display: inline-flex; align-items: center;
  background: var(--slab); border: 1px solid var(--rule); border-radius: 999px;
}
.picker select {
  appearance: none; background: none; border: 0; color: var(--ink);
  font-weight: 500; font-size: 14px; padding: 0 32px 0 14px; min-height: 44px; cursor: pointer;
}
.picker select option { background: var(--slab); }
.picker svg { position: absolute; right: 12px; width: 12px; height: 12px; pointer-events: none; }

.chips { display: flex; gap: 8px; overflow-x: auto; scrollbar-width: none; margin-inline: -20px; padding-inline: 20px; }
.chips button {
  flex: none; min-height: 40px; background: var(--slab); border: 1px solid var(--rule); color: var(--dim);
  font-weight: 500; font-size: 13.5px; padding: 0 14px; border-radius: 999px; cursor: pointer;
}
.chips button[aria-pressed="true"] { color: var(--amber); border-color: rgba(240, 164, 58, .45); background: var(--amber-soft); }

.row {
  display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 12px;
  padding: 11px 0; border-top: 1px solid var(--rule); min-height: 60px;
}
.row:first-child { border-top: 0; }
a.row:hover b { color: var(--amber); }
.lead {
  font-size: 12px; font-weight: 600; color: var(--dim); background: var(--slab); border: 1px solid var(--rule);
  border-radius: 8px; width: 40px; height: 40px; display: grid; place-items: center; letter-spacing: -.02em; overflow: hidden;
}
.rowName { display: grid; min-width: 0; }
.rowName b { font-weight: 500; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }
.rowName small { color: var(--dim); font-size: 12.5px; }
.rowAmount { text-align: right; display: grid; font-variant-numeric: tabular-nums; }
.rowAmount small { font-size: 12.5px; }

.skeleton { display: grid; gap: 10px; }
.skeletonRow, .skeletonChart { background: var(--slab); border-radius: 8px; height: 44px; }
.skeletonChart { height: 190px; }
.empty { display: grid; gap: 14px; justify-items: start; padding: 24px 0; }
.empty p { font-size: 17px; max-width: 32ch; }
.errorBox { display: grid; gap: 10px; justify-items: start; padding: 12px 0; }
.errorBox p { color: var(--loss); }
.secondary, .primaryButton {
  display: inline-grid; place-items: center; min-height: 44px; padding: 0 16px;
  border-radius: var(--r-control); cursor: pointer; font-weight: 500;
}
.secondary { background: var(--slab); border: 1px solid var(--rule); color: var(--ink); }
.primaryButton { background: var(--amber); border: 0; color: var(--night); font-weight: 600; }
.primaryButton:disabled { opacity: .5; cursor: default; }
.recalculating { color: var(--dim); font-size: 13px; }
```

- [ ] **Step 4: Nawigacja, układ, „Więcej”**

`web/src/shell/icons.tsx`:

```tsx
const box = { width: 23, height: 23, viewBox: "0 0 24 24", "aria-hidden": true } as const;
const line = { fill: "none", stroke: "currentColor", strokeWidth: 1.6, strokeLinecap: "round", strokeLinejoin: "round" } as const;

export const DashboardIcon = () => <svg {...box}><path {...line} d="M3 13h4v7H3zM10 8h4v12h-4zM17 4h4v16h-4z" /></svg>;
export const PositionsIcon = () => <svg {...box}><path {...line} d="M4 6h16M4 12h16M4 18h10" /></svg>;
export const AddIcon = () => <svg {...box} width={20} height={20}><path {...line} strokeWidth={2} d="M12 5v14M5 12h14" /></svg>;
export const HistoryIcon = () => <svg {...box}><circle {...line} cx="12" cy="12" r="8" /><path {...line} d="M12 8v4l3 2" /></svg>;
export const MoreIcon = () => (
  <svg {...box}>
    <circle cx="6" cy="12" r="1.6" fill="currentColor" />
    <circle cx="12" cy="12" r="1.6" fill="currentColor" />
    <circle cx="18" cy="12" r="1.6" fill="currentColor" />
  </svg>
);
```

`web/src/shell/Nav.tsx`:

```tsx
import { NavLink } from "react-router";
import { AddIcon, DashboardIcon, HistoryIcon, MoreIcon, PositionsIcon } from "./icons";
import styles from "./shell.module.css";

export function Nav() {
  return (
    <nav className={styles.nav} aria-label="Główna">
      <NavLink to="/" end className={styles.item}><DashboardIcon />Pulpit</NavLink>
      <NavLink to="/pozycje" className={styles.item}><PositionsIcon />Pozycje</NavLink>
      <NavLink to="/dodaj" className={`${styles.item} ${styles.add}`}>
        <span className={styles.plus}><AddIcon /></span>Dodaj
      </NavLink>
      <span className={`${styles.item} ${styles.disabled}`} aria-disabled="true" title="Wkrótce">
        <HistoryIcon />Historia
      </span>
      <NavLink to="/wiecej" className={styles.item}><MoreIcon />Więcej</NavLink>
    </nav>
  );
}
```

`web/src/shell/AppShell.tsx`:

```tsx
import { Outlet } from "react-router";
import { Nav } from "./Nav";
import styles from "./shell.module.css";

export function AppShell() {
  return (
    <div className={styles.shell}>
      <main className={styles.main}><Outlet /></main>
      <Nav />
    </div>
  );
}
```

`web/src/shell/MoreScreen.tsx`:

```tsx
import { useSession } from "../auth/session";
import ui from "../ui/ui.module.css";
import styles from "./shell.module.css";

const COMING = [
  "Historia operacji", "Obligacje i konta oszczędnościowe", "Zamknięte inwestycje", "Ekspozycja walutowa",
  "Limity IKE i IKZE", "Ustawienia kont i tickerów",
];

export function MoreScreen() {
  const { state, signOut } = useSession();
  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Więcej</h1>
      <section className={ui.section}>
        <p className="dim">Zalogowano jako</p>
        <p>{state.status === "signedIn" ? state.user.email : ""}</p>
        <button type="button" className={`${ui.secondary} ${styles.signOut}`} onClick={() => void signOut()}>Wyloguj</button>
      </section>
      <section className={ui.section}>
        <h2 className={ui.sectionTitle}>Wkrótce</h2>
        <ul className={styles.coming}>
          {COMING.map((item) => <li key={item}><span>{item}</span><span className="dim">wkrótce</span></li>)}
        </ul>
      </section>
    </div>
  );
}
```

`web/src/shell/shell.module.css`:

```css
.shell { min-height: 100dvh; }
.main {
  padding: calc(16px + env(safe-area-inset-top)) 20px calc(var(--nav-h) + 24px + env(safe-area-inset-bottom));
  max-width: 720px;
  margin: 0 auto;
}
.nav {
  position: fixed; left: 0; right: 0; bottom: 0; z-index: 10;
  display: grid; grid-template-columns: repeat(5, 1fr);
  padding: 8px 6px calc(10px + env(safe-area-inset-bottom));
  background: rgba(14, 17, 22, .92); backdrop-filter: blur(12px);
  border-top: 1px solid var(--rule);
}
.item {
  display: grid; justify-items: center; align-content: center; gap: 3px; min-height: 48px;
  color: var(--dim); font-size: 11px; font-weight: 500;
}
.item[aria-current="page"] { color: var(--amber); }
.disabled { opacity: .45; cursor: default; }
.plus {
  width: 42px; height: 30px; border-radius: 10px; background: var(--amber); color: var(--night);
  display: grid; place-items: center;
}
.signOut { justify-self: start; margin-top: 4px; }
.coming { list-style: none; padding: 0; margin: 0; }
.coming li { display: flex; justify-content: space-between; gap: 12px; padding: 12px 0; border-top: 1px solid var(--rule); }
.coming li:first-child { border-top: 0; }

@media (min-width: 900px) {
  .shell { display: grid; grid-template-columns: 220px 1fr; }
  .nav {
    position: sticky; top: 0; order: -1; height: 100dvh;
    grid-template-columns: none; grid-auto-rows: min-content; align-content: start; gap: 4px;
    padding: 28px 16px; border-top: 0; border-right: 1px solid var(--rule); background: var(--night);
  }
  .item { grid-auto-flow: column; justify-content: start; gap: 12px; font-size: 14px; padding: 0 10px; border-radius: var(--r-control); }
  .item[aria-current="page"] { background: var(--amber-soft); }
  .plus { width: 30px; height: 26px; }
  .main { padding-top: 32px; padding-bottom: 48px; }
}
```

- [ ] **Step 5: Trasy, aplikacja, `renderApp`**

`web/src/routes.tsx`:

```tsx
import { Navigate, type RouteObject } from "react-router";
import { LoginScreen } from "./auth/LoginScreen";
import { RegisterScreen } from "./auth/RegisterScreen";
import { GuestOnly, RequireAuth } from "./auth/RequireAuth";
import { AppShell } from "./shell/AppShell";
import { MoreScreen } from "./shell/MoreScreen";

/** Stand-in for the screens built in Tasks 7–9. */
export function Placeholder({ title }: { title: string }) {
  return <h1>{title}</h1>;
}

export const appRoutes: RouteObject[] = [
  {
    element: <GuestOnly />,
    children: [
      { path: "/logowanie", element: <LoginScreen /> },
      { path: "/rejestracja", element: <RegisterScreen /> },
    ],
  },
  {
    element: <RequireAuth />,
    children: [
      {
        element: <AppShell />,
        children: [
          { path: "/", element: <Placeholder title="Pulpit" /> },
          { path: "/pozycje", element: <Placeholder title="Pozycje" /> },
          { path: "/pozycje/:accountId/:instrumentId", element: <Placeholder title="Pozycja" /> },
          { path: "/dodaj", element: <Placeholder title="Dodaj" /> },
          { path: "/wiecej", element: <MoreScreen /> },
          { path: "*", element: <Navigate to="/" replace /> },
        ],
      },
    ],
  },
];
```

`web/src/App.tsx`:

```tsx
import { useState } from "react";
import { RouterProvider, createBrowserRouter } from "react-router";
import { AppProviders, createQueryClient } from "./providers";
import { appRoutes } from "./routes";

export function App() {
  const [client] = useState(() => createQueryClient());
  const [router] = useState(() => createBrowserRouter(appRoutes));
  return (
    <AppProviders client={client}>
      <RouterProvider router={router} />
    </AppProviders>
  );
}
```

`web/src/main.tsx` (zastąp):

```tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import "./styles/global.css";

createRoot(document.getElementById("root")!).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
```

`web/src/test/render.tsx` — dopisz na górze `import { appRoutes } from "../routes";`, a na końcu:

```tsx
export function renderApp(path = "/") {
  return renderRoutes(appRoutes, path);
}
```

- [ ] **Step 6: Uruchom testy**

Run (z `web/`): `npm test` → Expected: PASS wszystko.
Run: `npm run typecheck` → Expected: brak błędów.

- [ ] **Step 7: Commit**

```bash
git add web/src/ui web/src/shell web/src/routes.tsx web/src/App.tsx web/src/main.tsx web/src/test/render.tsx
git commit -m "feat(web): shared UI pieces, bottom/side navigation, routes and the More screen

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 6: Wykres wartości ze schodkami wpłaconego kapitału

**Files:**
- Create: `web/src/charts/geometry.ts`, `web/src/charts/geometry.test.ts`, `web/src/charts/ValueChart.tsx`, `web/src/charts/ValueChart.module.css`, `web/src/charts/ValueChart.test.tsx`

**Interfaces:**
- Consumes: `HistoryPoint` (Task 3); `formatDate`, `formatMoney`, `monthShort` (Task 2).
- Produces:
  - `geometry.ts`: `ChartPoint { date; value; invested; flow }` (liczby tylko do rysowania), `Frame { width; height; left; right; top; bottom }`, `Scales { x(i); y(v); min; max; ticks }`, `FRAME` (350 × 190; prawa 44, dół 22, góra 8), `toChartPoints(points: HistoryPoint[])`, `niceStep(span, count)`, `yDomain(points)`, `scales(points, frame)`, `linePath(points, s)`, `stairPath(points, s)`, `gapPath(points, s)`, `clipAbove(points, s, frame)`, `clipBelow(points, s, frame)`, `depositMarks(points): { index; large }[]`, `monthTicks(points, count = 4): { index; label }[]`, `nearestIndex(px, count, frame)`, `axisLabel(value)`.
  - `ValueChart.tsx`: `ValueChart({ points: HistoryPoint[] })` — SVG `role="img"` z `aria-label` „Wykres wartości portfela od DD.MM.RRRR do DD.MM.RRRR”; przy mniej niż 2 punktach zdanie „Wykres pojawi się, gdy wycena obejmie co najmniej dwa dni.”

- [ ] **Step 1: Testy**

`web/src/charts/geometry.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import {
  axisLabel, clipAbove, clipBelow, depositMarks, gapPath, linePath, monthTicks, nearestIndex, niceStep, scales,
  stairPath, toChartPoints, yDomain, type ChartPoint, type Frame,
} from "./geometry";

const BOX: Frame = { width: 100, height: 100, left: 0, right: 0, top: 0, bottom: 0 };
const POINTS: ChartPoint[] = [
  { date: "2026-01-01", value: 100, invested: 100, flow: 100 },
  { date: "2026-01-02", value: 110, invested: 100, flow: 0 },
  { date: "2026-01-03", value: 160, invested: 150, flow: 50 },
];

describe("scales", () => {
  it("reads the API's strings as numbers for drawing only", () => {
    expect(toChartPoints([{ date: "2026-01-01", value_pln: "1001.30", invested_pln: "1000.00", net_flow_pln: "1000.00", twr_pct: null }]))
      .toEqual([{ date: "2026-01-01", value: 1001.3, invested: 1000, flow: 1000 }]);
  });

  it("picks round steps", () => {
    expect([niceStep(60, 3), niceStep(80000, 3), niceStep(2, 3), niceStep(7, 3)]).toEqual([20, 50000, 1, 2.5]);
  });

  it("covers value and capital with round limits and ticks above the bottom", () => {
    expect(yDomain(POINTS)).toEqual({ min: 100, max: 160, ticks: [120, 140, 160] });
    const flat = [{ date: "2026-01-01", value: 100, invested: 100, flow: 0 }, { date: "2026-01-02", value: 100, invested: 100, flow: 0 }];
    expect(yDomain(flat)).toEqual({ min: 99, max: 101, ticks: [100, 101] });
  });
});

describe("paths", () => {
  const s = scales(POINTS, BOX);

  it("draws the value as a line and the capital as steps on deposit days", () => {
    expect(linePath(POINTS, s)).toBe("M0.0,100.0L50.0,83.3L100.0,0.0");
    expect(stairPath(POINTS, s)).toBe("M0.0,100.0H50.0V100.0H100.0V16.7");
  });

  it("closes the field between value and capital along the steps", () => {
    expect(gapPath(POINTS, s)).toBe("M0.0,100.0L50.0,83.3L100.0,0.0L100.0,16.7V100.0H50.0V100.0H0.0Z");
  });

  it("clips the field above and below the capital", () => {
    expect(clipAbove(POINTS, s, BOX)).toBe("M0.0,100.0H50.0V100.0H100.0V16.7V0.0H0.0Z");
    expect(clipBelow(POINTS, s, BOX)).toBe("M0.0,100.0H50.0V100.0H100.0V16.7V100.0H0.0Z");
  });
});

describe("marks and labels", () => {
  it("marks deposits, the larger ones taller", () => {
    expect(depositMarks(POINTS)).toEqual([{ index: 0, large: true }, { index: 2, large: false }]);
  });

  it("labels up to four month starts spread over the range", () => {
    const months = ["2026-01-01", "2026-02-01", "2026-03-01", "2026-04-01", "2026-05-01"]
      .map((date) => ({ date, value: 1, invested: 1, flow: 0 }));
    expect(monthTicks(months)).toEqual([
      { index: 0, label: "sty" }, { index: 1, label: "lut" }, { index: 3, label: "kwi" }, { index: 4, label: "maj" },
    ]);
    expect(monthTicks(POINTS)).toEqual([{ index: 0, label: "sty" }]);
  });

  it("finds the day under the finger", () => {
    expect([nearestIndex(0, 3, BOX), nearestIndex(49, 3, BOX), nearestIndex(80, 3, BOX), nearestIndex(500, 3, BOX)])
      .toEqual([0, 1, 2, 2]);
  });

  it("writes axis values in thousands", () => {
    expect([axisLabel(150000), axisLabel(2500), axisLabel(800), axisLabel(1500000)])
      .toEqual(["150 tys.", "2,5 tys.", "800", "1,5 mln"]);
  });
});
```

`web/src/charts/ValueChart.test.tsx`:

```tsx
import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import type { HistoryPoint } from "../api/types";
import { ValueChart } from "./ValueChart";

const S = " ";
const point = (date: string, value: string, invested: string, flow = "0.00"): HistoryPoint =>
  ({ date, value_pln: value, invested_pln: invested, net_flow_pln: flow, twr_pct: null });
const TWO = [point("2026-09-01", "1000.00", "1000.00", "1000.00"), point("2026-09-26", "1100.00", "1000.00")];

describe("ValueChart", () => {
  it("says when there is not enough history for a chart", () => {
    render(<ValueChart points={[point("2026-09-26", "1000.00", "1000.00", "1000.00")]} />);
    expect(screen.getByText("Wykres pojawi się, gdy wycena obejmie co najmniej dwa dni.")).toBeInTheDocument();
    expect(screen.queryByRole("img")).not.toBeInTheDocument();
  });

  it("draws the value, the capital steps and the legend", () => {
    render(<ValueChart points={TWO} />);
    expect(screen.getByRole("img", { name: "Wykres wartości portfela od 01.09.2026 do 26.09.2026" })).toBeInTheDocument();
    expect(screen.getByText("Wpłacony kapitał")).toBeInTheDocument();
  });

  it("shows the day under the pointer", () => {
    render(<ValueChart points={TWO} />);
    const svg = screen.getByRole("img");
    vi.spyOn(svg, "getBoundingClientRect").mockReturnValue({ left: 0, width: 350, top: 0, height: 190 } as DOMRect);

    fireEvent.pointerMove(svg, { clientX: 300, clientY: 50 });

    expect(screen.getByText("26.09.2026")).toBeInTheDocument();
    expect(screen.getByText(`Wartość 1${S}100,00${S}zł`)).toBeInTheDocument();
    expect(screen.getByText(`Wpłacono 1${S}000,00${S}zł`)).toBeInTheDocument();
  });
});
```

- [ ] **Step 2: Uruchom — mają nie przejść**

Run (z `web/`): `npm test -- src/charts`
Expected: FAIL — `Failed to resolve import "./geometry"`.

- [ ] **Step 3: `geometry.ts`**

`web/src/charts/geometry.ts`:

```ts
/** Pure geometry of the value chart. Numbers here only place pixels; money is formatted from the API strings. */
import type { HistoryPoint } from "../api/types";
import { monthShort } from "../format";

export interface ChartPoint { date: string; value: number; invested: number; flow: number }
export interface Frame { width: number; height: number; left: number; right: number; top: number; bottom: number }
export interface Scales { x(i: number): number; y(v: number): number; min: number; max: number; ticks: number[] }

export const FRAME: Frame = { width: 350, height: 190, left: 0, right: 44, top: 8, bottom: 22 };

const f = (n: number) => n.toFixed(1);

export function toChartPoints(points: HistoryPoint[]): ChartPoint[] {
  return points.map((p) => ({
    date: p.date, value: Number(p.value_pln), invested: Number(p.invested_pln), flow: Number(p.net_flow_pln),
  }));
}

export function niceStep(span: number, count: number): number {
  const raw = span / count;
  const magnitude = 10 ** Math.floor(Math.log10(raw));
  for (const m of [1, 2, 2.5, 5, 10]) if (m * magnitude >= raw - 1e-9) return m * magnitude;
  return 10 * magnitude;
}

export function yDomain(points: ChartPoint[]): { min: number; max: number; ticks: number[] } {
  let lo = Math.min(...points.map((p) => Math.min(p.value, p.invested)));
  let hi = Math.max(...points.map((p) => Math.max(p.value, p.invested)));
  if (hi === lo) {
    const pad = Math.max(Math.abs(lo) * 0.01, 1);
    lo -= pad;
    hi += pad;
  }
  const step = niceStep(hi - lo, 3);
  const min = Math.floor(lo / step + 1e-9) * step;
  const max = Math.ceil(hi / step - 1e-9) * step;
  const ticks: number[] = [];
  for (let k = 1; min + k * step <= max + 1e-9; k++) ticks.push(Number((min + k * step).toFixed(6)));
  return { min, max, ticks };
}

export function scales(points: ChartPoint[], frame: Frame): Scales {
  const { min, max, ticks } = yDomain(points);
  const plotWidth = frame.width - frame.left - frame.right;
  const plotHeight = frame.height - frame.top - frame.bottom;
  const last = Math.max(points.length - 1, 1);
  return {
    x: (i) => frame.left + (i / last) * plotWidth,
    y: (v) => frame.top + (1 - (v - min) / (max - min)) * plotHeight,
    min, max, ticks,
  };
}

export function linePath(points: ChartPoint[], s: Scales): string {
  return points.map((p, i) => `${i ? "L" : "M"}${f(s.x(i))},${f(s.y(p.value))}`).join("");
}

/** Capital changes in one jump on the day of a deposit: across first, then up or down. */
export function stairPath(points: ChartPoint[], s: Scales): string {
  return points.map((p, i) => (i ? `H${f(s.x(i))}V${f(s.y(p.invested))}` : `M${f(s.x(0))},${f(s.y(p.invested))}`)).join("");
}

/** The field between the value line and the capital steps (gain where above, loss where below). */
export function gapPath(points: ChartPoint[], s: Scales): string {
  const last = points.length - 1;
  let path = `${linePath(points, s)}L${f(s.x(last))},${f(s.y(points[last]!.invested))}`;
  for (let i = last; i >= 1; i--) path += `V${f(s.y(points[i - 1]!.invested))}H${f(s.x(i - 1))}`;
  return `${path}Z`;
}

export function clipAbove(points: ChartPoint[], s: Scales, frame: Frame): string {
  return `${stairPath(points, s)}V${f(frame.top)}H${f(s.x(0))}Z`;
}

export function clipBelow(points: ChartPoint[], s: Scales, frame: Frame): string {
  return `${stairPath(points, s)}V${f(frame.height - frame.bottom)}H${f(s.x(0))}Z`;
}

export function depositMarks(points: ChartPoint[]): { index: number; large: boolean }[] {
  const deposits = points.map((p, index) => ({ index, flow: p.flow })).filter((d) => d.flow > 0);
  const sorted = deposits.map((d) => d.flow).sort((a, b) => a - b);
  const mid = Math.floor(sorted.length / 2);
  const median = sorted.length % 2 ? sorted[mid]! : ((sorted[mid - 1] ?? 0) + (sorted[mid] ?? 0)) / 2;
  return deposits.map((d) => ({ index: d.index, large: d.flow > median }));
}

export function monthTicks(points: ChartPoint[], count = 4): { index: number; label: string }[] {
  const starts = points
    .map((p, index) => ({ index, month: p.date.slice(0, 7) }))
    .filter((p, i, all) => i === 0 || p.month !== all[i - 1]!.month)
    .map((p) => p.index);
  const chosen = starts.length <= count
    ? starts
    : Array.from({ length: count }, (_, k) => starts[Math.round((k * (starts.length - 1)) / (count - 1))]!);
  return [...new Set(chosen)].map((index) => ({ index, label: monthShort(points[index]!.date) }));
}

export function nearestIndex(px: number, count: number, frame: Frame): number {
  const plotWidth = frame.width - frame.left - frame.right;
  const index = Math.round(((px - frame.left) / plotWidth) * (count - 1));
  return Math.min(Math.max(index, 0), count - 1);
}

export function axisLabel(value: number): string {
  const decimal = (n: number) => (Number.isInteger(n) ? String(n) : n.toFixed(1).replace(".", ","));
  if (Math.abs(value) >= 1_000_000) return `${decimal(value / 1_000_000)} mln`;
  if (Math.abs(value) >= 1_000) return `${decimal(value / 1_000)} tys.`;
  return String(Math.round(value));
}
```

- [ ] **Step 4: Komponent**

`web/src/charts/ValueChart.tsx`:

```tsx
import { useId, useMemo, useState, type PointerEvent } from "react";
import type { HistoryPoint } from "../api/types";
import { formatDate, formatMoney } from "../format";
import {
  FRAME, axisLabel, clipAbove, clipBelow, depositMarks, gapPath, linePath, monthTicks, nearestIndex, scales, stairPath,
  toChartPoints,
} from "./geometry";
import styles from "./ValueChart.module.css";

export function ValueChart({ points }: { points: HistoryPoint[] }) {
  const data = useMemo(() => toChartPoints(points), [points]);
  const [active, setActive] = useState<number | null>(null);
  const id = useId().replace(/[^a-zA-Z0-9_-]/g, "");

  if (data.length < 2) {
    return <p className={styles.note}>Wykres pojawi się, gdy wycena obejmie co najmniej dwa dni.</p>;
  }

  const s = scales(data, FRAME);
  const last = data.length - 1;
  const baseline = FRAME.height - FRAME.bottom;
  const plotRight = FRAME.width - FRAME.right;
  const shown = active === null ? null : points[active]!;
  const gap = gapPath(data, s);

  function track(event: PointerEvent<SVGSVGElement>) {
    const rect = event.currentTarget.getBoundingClientRect();
    if (!rect.width) return;
    setActive(nearestIndex(((event.clientX - rect.left) / rect.width) * FRAME.width, data.length, FRAME));
  }

  return (
    <figure className={styles.chart}>
      <div className={styles.readout} aria-live="polite">
        {shown ? (
          <>
            <span className={styles.day}>{formatDate(shown.date)}</span>
            <span className="num">Wartość {formatMoney(shown.value_pln)}</span>
            <span className="num">Wpłacono {formatMoney(shown.invested_pln)}</span>
          </>
        ) : (
          <>
            <span className={styles.key}><i className={styles.swValue} />Wartość</span>
            <span className={styles.key}><i className={styles.swCapital} />Wpłacony kapitał</span>
            <span className={styles.key}><i className={styles.swDeposit} />Wpłata</span>
          </>
        )}
      </div>
      <svg
        className={styles.svg}
        viewBox={`0 0 ${FRAME.width} ${FRAME.height}`}
        role="img"
        aria-label={`Wykres wartości portfela od ${formatDate(points[0]!.date)} do ${formatDate(points[last]!.date)}`}
        onPointerMove={track}
        onPointerDown={track}
        onPointerLeave={() => setActive(null)}
      >
        <defs>
          <clipPath id={`above-${id}`}><path d={clipAbove(data, s, FRAME)} /></clipPath>
          <clipPath id={`below-${id}`}><path d={clipBelow(data, s, FRAME)} /></clipPath>
        </defs>
        {s.ticks.map((tick) => (
          <g key={tick}>
            <line x1={FRAME.left} x2={plotRight} y1={s.y(tick)} y2={s.y(tick)} className={styles.grid} />
            <text x={plotRight + 6} y={s.y(tick) + 4} className={styles.axis}>{axisLabel(tick)}</text>
          </g>
        ))}
        {monthTicks(data).map((tick) => (
          <text key={tick.index} x={s.x(tick.index)} y={FRAME.height - 4} className={styles.axis}>{tick.label}</text>
        ))}
        {depositMarks(data).map((mark) => (
          <line key={mark.index} x1={s.x(mark.index)} x2={s.x(mark.index)} y1={baseline + 2}
            y2={baseline + (mark.large ? 12 : 7)} className={styles.deposit} />
        ))}
        <path d={gap} fill="var(--amber-soft)" clipPath={`url(#above-${id})`} />
        <path d={gap} fill="var(--loss-soft)" clipPath={`url(#below-${id})`} />
        <path d={stairPath(data, s)} className={styles.capital} />
        <path d={linePath(data, s)} className={styles.value} pathLength={1} />
        {active !== null && <line x1={s.x(active)} x2={s.x(active)} y1={FRAME.top} y2={baseline} className={styles.cursor} />}
        <circle cx={s.x(last)} cy={s.y(data[last]!.value)} r={4} fill="var(--amber)" />
        <circle cx={s.x(last)} cy={s.y(data[last]!.value)} r={8} fill="var(--amber)" opacity={0.18} />
      </svg>
    </figure>
  );
}
```

`web/src/charts/ValueChart.module.css`:

```css
.chart { margin: 0; display: grid; gap: 8px; }
.svg { width: 100%; height: auto; display: block; overflow: visible; touch-action: pan-y; }
.readout { display: flex; flex-wrap: wrap; gap: 6px 16px; min-height: 20px; font-size: 12.5px; color: var(--dim); }
.day { color: var(--ink); }
.key { display: inline-flex; align-items: center; gap: 6px; }
.swValue, .swCapital { width: 14px; height: 2px; border-radius: 2px; background: var(--amber); }
.swCapital { background: var(--dim); }
.swDeposit { width: 2px; height: 8px; background: var(--dim); }
.grid { stroke: var(--rule); stroke-width: 1; }
.axis { fill: var(--dim); font-size: 10.5px; font-variant-numeric: tabular-nums; }
.deposit { stroke: var(--dim); stroke-width: 1.4; }
.capital { fill: none; stroke: var(--dim); stroke-width: 1.3; stroke-linejoin: round; }
.value {
  fill: none; stroke: var(--amber); stroke-width: 2; stroke-linejoin: round; stroke-linecap: round;
  stroke-dasharray: 1; stroke-dashoffset: 0;
}
.cursor { stroke: var(--ink); stroke-opacity: .35; stroke-width: 1; }
.note { color: var(--dim); font-size: 14px; padding: 24px 0; }

@media (prefers-reduced-motion: no-preference) {
  .value { animation: draw 1.1s cubic-bezier(.3, .7, .2, 1) .15s both; }
  @keyframes draw { from { stroke-dashoffset: 1; } to { stroke-dashoffset: 0; } }
}
```

- [ ] **Step 5: Uruchom testy**

Run (z `web/`): `npm test -- src/charts` → Expected: PASS.
Run: `npm test` → Expected: PASS wszystko. Run: `npm run typecheck` → Expected: brak błędów.

- [ ] **Step 6: Commit**

```bash
git add web/src/charts
git commit -m "feat(web): value chart with the paid-in capital steps, deposit marks and a day readout

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 7: Pulpit

**Files:**
- Create: `web/src/format/plural.ts`, `web/src/ui/ticker.ts`, `web/src/test/fixtures.ts`, `web/src/screens/dashboard/model.ts`, `web/src/screens/dashboard/DashboardScreen.tsx`, `web/src/screens/dashboard/Dashboard.module.css`, `web/src/screens/dashboard/dashboard.test.tsx`
- Modify: `web/src/format/index.ts`, `web/src/routes.tsx`

**Interfaces:**
- Consumes: `api`, `keys` (Task 3); `formatDayLong`, `formatPercent`, `sumMoney`, `toCents`, `addMonths` (Task 2); `HeroAmount`, `Money`, `Segmented`, `AccountPicker`, `ListRow`, `Skeleton`, `EmptyState`, `ErrorState`, `Recalculating`, `ui.module.css` (Task 5); `ValueChart` (Task 6); `renderApp`, `mockFetch`, `SIGNED_IN` (Task 4–5).
- Produces:
  - `format/plural.ts`: `pluralPl(n: number, one: string, few: string, many: string): string` (1 → one; 2–4 poza 12–14 → few; reszta → many), eksport z `format/index.ts`.
  - `ui/ticker.ts`: `shortTicker(ticker: string): string` („SXR8.DE” → „SXR8”, najwyżej 5 znaków).
  - `test/fixtures.ts`: `ACCOUNTS`, `SUMMARY`, `HISTORY`, `EXPOSURE`, `POSITIONS`, `position(overrides): Position`.
  - `dashboard/model.ts`: `type Range = "1M" | "3M" | "1R" | "ALL"`, `RANGES`, `rangeFrom(range, asOf): string | null`, `type AllocationMode = "kind" | "account" | "currency"`, `ALLOCATION_MODES`, `ALLOCATION_COLORS`, `allocationRows(mode, summary, exposure): AllocationRow[]`, `dayMovers(positions, count = 3): { position: Position; pct: string }[]`, `RECALC_POLL_MS = 3000`.
  - `DashboardScreen` pod `/` w `routes.tsx`.

- [ ] **Step 1: Dane testowe**

`web/src/test/fixtures.ts`:

```ts
import type { Account, Exposure, History, Position, Summary } from "../api/types";

export const ACCOUNTS: Account[] = [
  { id: 1, name: "IKE", kind: "broker", wrapper: "ike", broker: "xtb", external_account_number: "56216965",
    currency: "PLN", created_at: "2026-09-01T10:00:00" },
  { id: 2, name: "XTB", kind: "broker", wrapper: "regular", broker: "xtb", external_account_number: "56204082",
    currency: "PLN", created_at: "2026-09-01T10:00:00" },
];

export const SUMMARY: Summary = {
  as_of: "2026-09-26",
  value_pln: "184302.17",
  cash_pln: "4133.49",
  invested_pln: "161183.77",
  total_gain_pln: "23118.40",
  total_gain_pct: "14.34",
  day_change_pln: "1204.50",
  day_change_pct: "0.66",
  twr_pct: "14.20",
  dividends_net_pln: "3212.05",
  interest_net_pln: "200.00",
  fees_pln: "-45.10",
  by_account: [
    { key: "1", name: "IKE", value_pln: "120000.00", share_pct: "65.11" },
    { key: "2", name: "XTB", value_pln: "64302.17", share_pct: "34.89" },
  ],
  by_kind: [
    { key: "ETF", name: "ETF", value_pln: "119556.50", share_pct: "64.87" },
    { key: "savings", name: "Konta oszczędnościowe", value_pln: "40132.18", share_pct: "21.78" },
    { key: "bonds", name: "Obligacje", value_pln: "20480.00", share_pct: "11.11" },
    { key: "cash", name: "Gotówka", value_pln: "4133.49", share_pct: "2.24" },
  ],
  approximate_positions: 1,
  recalculating: false,
};

export const HISTORY: History = {
  points: [
    { date: "2026-09-24", value_pln: "182000.00", invested_pln: "161183.77", net_flow_pln: "0.00", twr_pct: "13.10" },
    { date: "2026-09-25", value_pln: "183097.67", invested_pln: "161183.77", net_flow_pln: "0.00", twr_pct: "13.60" },
    { date: "2026-09-26", value_pln: "184302.17", invested_pln: "161183.77", net_flow_pln: "0.00", twr_pct: "14.20" },
  ],
  events: [],
};

export const EXPOSURE: Exposure = {
  as_of: "2026-09-26",
  current: [
    { currency: "EUR", value_pln: "98000.00", share_pct: "53.17" },
    { currency: "PLN", value_pln: "86302.17", share_pct: "46.83" },
  ],
  history: [],
};

export function position(overrides: Partial<Position>): Position {
  return {
    kind: "instrument", account_id: 2, account_name: "XTB", instrument_id: 10, ticker: "SXR8.DE",
    name: "Core S&P 500", category: "ETF", currency: "EUR", quantity: "42.00000000", price: "612.3400",
    price_date: "2026-09-26", price_source: "provider", value_pln: "1000.00", cost_pln: "900.00",
    unrealized_pln: "100.00", unrealized_pct: "11.11", price_effect_pln: "80.00", fx_effect_pln: "20.00",
    dividends_net_pln: "0.00", fees_pln: "0.00", realized_pln: "0.00", day_change_pln: "0.00", share_pct: "10.00",
    flags: [], bond_holding_id: null, savings_account_id: null,
    ...overrides,
  };
}

export const POSITIONS: Position[] = [
  position({ instrument_id: 10, account_id: 1, account_name: "IKE", value_pln: "66024.73", day_change_pln: "688.14",
    unrealized_pln: "10354.51", share_pct: "35.82" }),
  position({ instrument_id: 11, ticker: "IWDA.NL", name: "Core MSCI World", value_pln: "31518.90", share_pct: "17.10" }),
  position({ instrument_id: 12, ticker: "CDR.PL", name: "CD Projekt", currency: "PLN", quantity: "48",
    value_pln: "11158.56", day_change_pln: "412.80", unrealized_pln: "1931.04", share_pct: "6.05" }),
  position({ instrument_id: 13, ticker: "PKN.PL", name: "Orlen", currency: "PLN", quantity: "110",
    value_pln: "7146.70", day_change_pln: "-151.20", unrealized_pln: "-612.50", share_pct: "3.88", flags: ["xtb_price"] }),
  position({ kind: "bond", instrument_id: null, ticker: null, name: "EDO0936", category: "bonds", currency: "PLN",
    account_id: 3, account_name: "Obligacje", quantity: "100", value_pln: "10013.00", cost_pln: "10000.00",
    unrealized_pln: "13.00", bond_holding_id: 7, share_pct: "5.43" }),
  position({ kind: "savings", instrument_id: null, ticker: null, name: "Konto oszczędnościowe", category: "savings",
    currency: "PLN", account_id: 4, account_name: "Konto oszczędnościowe", quantity: "40132.18",
    value_pln: "40132.18", cost_pln: "40000.00", unrealized_pln: "132.18", savings_account_id: 4, share_pct: "21.78" }),
  position({ kind: "cash", instrument_id: null, ticker: null, name: "Gotówka", category: null, currency: "PLN",
    account_id: 2, account_name: "XTB", quantity: "4133.49", value_pln: "4133.49", cost_pln: "4133.49",
    unrealized_pln: "0.00", share_pct: "2.24" }),
];
```

- [ ] **Step 2: Testy**

`web/src/screens/dashboard/dashboard.test.tsx`:

```tsx
import { screen, waitFor, within } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { NETWORK_MESSAGE } from "../../api/client";
import { pluralPl } from "../../format";
import { ACCOUNTS, EXPOSURE, HISTORY, POSITIONS, SUMMARY } from "../../test/fixtures";
import { SIGNED_IN, mockFetch, renderApp, type MockRoute } from "../../test/render";
import { allocationRows, dayMovers, rangeFrom } from "./model";

const S = " ";

function routes(overrides: Partial<Record<string, MockRoute["respond"]>> = {}): MockRoute[] {
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: overrides.accounts ?? (() => ACCOUNTS) },
    { path: "/api/portfolio/summary", respond: overrides.summary ?? (() => SUMMARY) },
    { path: "/api/portfolio/history", respond: overrides.history ?? (() => HISTORY) },
    { path: "/api/portfolio/exposure", respond: overrides.exposure ?? (() => EXPOSURE) },
    { path: "/api/positions", respond: overrides.positions ?? (() => POSITIONS) },
  ];
}

afterEach(() => vi.useRealTimers());

describe("dashboard model", () => {
  it("starts each range from the valuation day", () => {
    expect([rangeFrom("1M", "2026-09-26"), rangeFrom("3M", "2026-09-26"), rangeFrom("1R", "2026-09-26"), rangeFrom("ALL", "2026-09-26")])
      .toEqual(["2026-08-26", "2026-06-26", "2025-09-26", null]);
    expect(rangeFrom("1R", null)).toBeNull();
  });

  it("colours allocation rows by their order, the largest in amber", () => {
    const rows = allocationRows("kind", SUMMARY, undefined);
    expect(rows.map((r) => [r.name, r.color])).toEqual([
      ["ETF", "var(--amber)"], ["Konta oszczędnościowe", "#C9B48A"], ["Obligacje", "#7C8898"], ["Gotówka", "#4A5361"],
    ]);
    expect(allocationRows("currency", SUMMARY, EXPOSURE).map((r) => r.name)).toEqual(["EUR", "PLN"]);
    expect(allocationRows("currency", SUMMARY, undefined)).toEqual([]);
  });

  it("finds the biggest moves of the day among instruments", () => {
    expect(dayMovers(POSITIONS).map((m) => [m.position.name, Number(m.pct).toFixed(2)])).toEqual([
      ["CD Projekt", "3.84"], ["Orlen", "-2.07"], ["Core S&P 500", "1.05"],
    ]);
  });

  it("writes Polish plurals", () => {
    const f = (n: number) => pluralPl(n, "pozycja", "pozycje", "pozycji");
    expect([f(1), f(2), f(4), f(5), f(12), f(22), f(25)]).toEqual(["pozycja", "pozycje", "pozycje", "pozycji", "pozycji", "pozycje", "pozycji"]);
  });
});

describe("dashboard screen", () => {
  it("shows the value, the day, the chart, allocation and the day's biggest moves", async () => {
    mockFetch(routes());
    renderApp("/");

    expect(await screen.findByText("Wartość portfela")).toBeInTheDocument();
    expect(screen.getByText("sob., 26 września")).toBeInTheDocument();
    expect(screen.getByText(`+1${S}204,50${S}zł`)).toHaveClass("up");
    expect(screen.getByText(`(+0,66${S}%)`)).toBeInTheDocument();
    expect(screen.getByText(`+14,2${S}%`)).toBeInTheDocument();
    expect(screen.getByText(`3${S}412,05${S}zł`)).toBeInTheDocument();
    expect(screen.getByText("1 pozycja wyceniona w przybliżeniu")).toBeInTheDocument();
    expect(await screen.findByRole("img", { name: /Wykres wartości portfela/ })).toBeInTheDocument();
    expect(screen.getByText("Konta oszczędnościowe")).toBeInTheDocument();

    const movers = await screen.findByRole("region", { name: "Dziś najbardziej" });
    const rows = within(movers).getAllByRole("link").filter((l) => l.getAttribute("href")?.startsWith("/pozycje/"));
    expect(rows.map((l) => l.textContent)).toEqual([
      expect.stringContaining("CD Projekt"), expect.stringContaining("Orlen"), expect.stringContaining("Core S&P 500"),
    ]);
  });

  it("invites an empty portfolio to import", async () => {
    mockFetch(routes({ summary: () => ({ ...SUMMARY, as_of: null, by_kind: [], by_account: [] }) }));
    renderApp("/");
    expect(await screen.findByText("Wgraj eksport z XTB, żeby zobaczyć swój portfel.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Wgraj pliki z XTB" })).toHaveAttribute("href", "/dodaj");
  });

  it("asks for one account and the currency allocation of the valuation day", async () => {
    const fetchMock = mockFetch(routes());
    const { user } = renderApp("/");

    await user.selectOptions(await screen.findByRole("combobox", { name: "Konto" }), "1");
    await user.click(screen.getByRole("button", { name: "Waluta" }));

    expect(await screen.findByText("EUR")).toBeInTheDocument();
    const urls = fetchMock.mock.calls.map(([url]) => String(url));
    expect(urls).toContain("/api/portfolio/summary?account_id=1");
    expect(urls).toContain("/api/portfolio/exposure?account_id=1&from=2026-09-26&to=2026-09-26");
    expect(urls.some((u) => u.startsWith("/api/portfolio/history?account_id=1&from=2025-09-26"))).toBe(true);
  });

  it("keeps asking while the valuation is recalculated and then refreshes the chart", async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true });
    let summaries = 0;
    let histories = 0;
    mockFetch(routes({
      summary: () => ({ ...SUMMARY, recalculating: ++summaries === 1 }),
      history: () => { histories += 1; return HISTORY; },
    }));
    renderApp("/");

    expect(await screen.findByText("Przeliczam wycenę…")).toBeInTheDocument();
    await waitFor(() => expect(histories).toBe(1));
    await vi.advanceTimersByTimeAsync(3000);

    await waitFor(() => expect(screen.queryByText("Przeliczam wycenę…")).not.toBeInTheDocument());
    await waitFor(() => expect(histories).toBe(2));
  });

  it("says when the API cannot be reached and lets the user try again", async () => {
    let calls = 0;
    const fetchMock = mockFetch(routes());
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation((input: string, init?: RequestInit) =>
      String(input).startsWith("/api/portfolio/summary") && ++calls === 1
        ? Promise.reject(new TypeError("Failed to fetch"))
        : original(input, init));
    const { user } = renderApp("/");

    expect(await screen.findByRole("alert")).toHaveTextContent(NETWORK_MESSAGE);
    await user.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(await screen.findByText("Wartość portfela")).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Uruchom — mają nie przejść**

Run (z `web/`): `npm test -- src/screens/dashboard`
Expected: FAIL — `Failed to resolve import "./model"`.

- [ ] **Step 4: `plural.ts`, `ticker.ts`, model**

`web/src/format/plural.ts`:

```ts
/** Polish plural: 1 pozycja, 2–4 pozycje (but 12–14 pozycji), 5+ pozycji. */
export function pluralPl(n: number, one: string, few: string, many: string): string {
  if (n === 1) return one;
  const tens = n % 100;
  const units = n % 10;
  return units >= 2 && units <= 4 && (tens < 12 || tens > 14) ? few : many;
}
```

`web/src/format/index.ts` — dopisz linię:

```ts
export { pluralPl } from "./plural";
```

`web/src/ui/ticker.ts`:

```ts
/** "SXR8.DE" → "SXR8": the exchange suffix does not fit the 40 px badge. */
export function shortTicker(ticker: string): string {
  return (ticker.split(".")[0] ?? ticker).slice(0, 5);
}
```

`web/src/screens/dashboard/model.ts`:

```ts
import type { Exposure, Position, Summary } from "../../api/types";
import { addMonths, toCents } from "../../format";

export const RECALC_POLL_MS = 3000;

export type Range = "1M" | "3M" | "1R" | "ALL";
export const RANGES: { value: Range; label: string }[] = [
  { value: "1M", label: "1M" }, { value: "3M", label: "3M" }, { value: "1R", label: "1R" }, { value: "ALL", label: "Wszystko" },
];
const RANGE_MONTHS: Record<Exclude<Range, "ALL">, number> = { "1M": 1, "3M": 3, "1R": 12 };

export function rangeFrom(range: Range, asOf: string | null): string | null {
  if (asOf === null || range === "ALL") return null;
  return addMonths(asOf, -RANGE_MONTHS[range]);
}

export type AllocationMode = "kind" | "account" | "currency";
export const ALLOCATION_MODES: { value: AllocationMode; label: string }[] = [
  { value: "kind", label: "Typ" }, { value: "account", label: "Konto" }, { value: "currency", label: "Waluta" },
];
export const ALLOCATION_COLORS = ["var(--amber)", "#C9B48A", "#7C8898", "#4A5361", "#39414C"];

export interface AllocationRow { key: string; name: string; value: string; share: string | null; color: string }

/** Rows arrive sorted from the largest; the first gets the accent. */
export function allocationRows(mode: AllocationMode, summary: Summary, exposure: Exposure | undefined): AllocationRow[] {
  const items = mode === "kind"
    ? summary.by_kind
    : mode === "account"
      ? summary.by_account
      : (exposure?.current ?? []).map((c) => ({
        key: c.currency, name: c.currency === "unknown" ? "Nieznana" : c.currency, value_pln: c.value_pln, share_pct: c.share_pct,
      }));
  return items.map((item, i) => ({
    key: item.key, name: item.name, value: item.value_pln, share: item.share_pct,
    color: ALLOCATION_COLORS[i % ALLOCATION_COLORS.length]!,
  }));
}

/** The API gives each position's change in zł; its percent is a display-only ratio of two amounts. */
export function dayMovers(positions: Position[], count = 3): { position: Position; pct: string }[] {
  return positions
    .filter((p) => p.kind === "instrument" && toCents(p.day_change_pln) !== 0n)
    .flatMap((p) => {
      const before = Number(p.value_pln) - Number(p.day_change_pln);
      return before > 0 ? [{ position: p, pct: ((Number(p.day_change_pln) / before) * 100).toFixed(4) }] : [];
    })
    .sort((a, b) => Math.abs(Number(b.pct)) - Math.abs(Number(a.pct)))
    .slice(0, count);
}
```

- [ ] **Step 5: Ekran**

`web/src/screens/dashboard/DashboardScreen.tsx`:

```tsx
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { Summary } from "../../api/types";
import { ValueChart } from "../../charts/ValueChart";
import { formatDayLong, formatPercent, pluralPl, signOf, sumMoney } from "../../format";
import { AccountPicker } from "../../ui/AccountPicker";
import { HeroAmount, Money } from "../../ui/Amount";
import { ListRow } from "../../ui/ListRow";
import { Segmented } from "../../ui/Segmented";
import { EmptyState, ErrorState, Recalculating, Skeleton } from "../../ui/States";
import { shortTicker } from "../../ui/ticker";
import ui from "../../ui/ui.module.css";
import styles from "./Dashboard.module.css";
import {
  ALLOCATION_MODES, RANGES, RECALC_POLL_MS, allocationRows, dayMovers, rangeFrom, type AllocationMode, type Range,
} from "./model";

const tone = (value: string | null) => (signOf(value) > 0 ? "up" : signOf(value) < 0 ? "down" : "");

export function DashboardScreen() {
  const queryClient = useQueryClient();
  const [accountId, setAccountId] = useState<number | null>(null);
  const [range, setRange] = useState<Range>("1R");
  const [mode, setMode] = useState<AllocationMode>("kind");

  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const summary = useQuery({
    queryKey: keys.summary(accountId),
    queryFn: () => api.summary(accountId),
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
  });
  const asOf = summary.data?.as_of ?? null;
  const from = rangeFrom(range, asOf);
  const history = useQuery({ queryKey: keys.history(accountId, from), queryFn: () => api.history(accountId, from), enabled: asOf !== null });
  const exposure = useQuery({
    queryKey: keys.exposure(accountId, asOf ?? ""),
    queryFn: () => api.exposure(accountId, asOf!),
    enabled: asOf !== null && mode === "currency",
  });
  const positions = useQuery({ queryKey: keys.positions(accountId), queryFn: () => api.positions(accountId), enabled: asOf !== null });

  // When the background recalculation ends, everything valued may have changed.
  const recalculating = summary.data?.recalculating ?? false;
  const wasRecalculating = useRef(false);
  useEffect(() => {
    if (wasRecalculating.current && !recalculating) {
      void queryClient.invalidateQueries({ queryKey: keys.portfolio, predicate: (q) => q.queryKey[1] !== "summary" });
    }
    wasRecalculating.current = recalculating;
  }, [recalculating, queryClient]);

  const header = (
    <div className={styles.bar}>
      <AccountPicker accounts={accounts.data ?? []} value={accountId} onChange={setAccountId} />
      {asOf && <span className="dim">{formatDayLong(asOf)}</span>}
    </div>
  );

  if (summary.isPending) return <div className={ui.page}>{header}<Skeleton chart rows={4} /></div>;
  if (summary.isError) return <div className={ui.page}>{header}<ErrorState error={summary.error} onRetry={() => void summary.refetch()} /></div>;

  const data: Summary = summary.data;
  if (asOf === null) {
    return (
      <div className={ui.page}>
        {header}
        {recalculating ? <><Recalculating /><Skeleton chart rows={3} /></> : (
          <EmptyState
            title="Wgraj eksport z XTB, żeby zobaczyć swój portfel."
            action={<Link className={ui.primaryButton} to="/dodaj">Wgraj pliki z XTB</Link>}
          />
        )}
      </div>
    );
  }

  const rows = allocationRows(mode, data, exposure.data);
  const movers = positions.data ? dayMovers(positions.data) : [];
  const approximate = data.approximate_positions;

  return (
    <div className={ui.page}>
      {header}
      <section className={styles.hero} aria-label="Podsumowanie">
        <span className="dim">Wartość portfela</span>
        <HeroAmount value={data.value_pln} />
        {data.day_change_pln !== null && (
          <p className={styles.today}>
            <Money value={data.day_change_pln} sign tone />{" "}
            <span className={`num ${tone(data.day_change_pct)}`}>({formatPercent(data.day_change_pct)})</span>{" "}
            <span className="dim">dziś</span>
          </p>
        )}
        <dl className={styles.stats}>
          <div><dt>Zysk łącznie</dt><dd><Money value={data.total_gain_pln} sign tone /></dd></div>
          <div><dt>Stopa zwrotu (TWR)</dt><dd className={`num ${tone(data.twr_pct)}`}>{formatPercent(data.twr_pct, { places: 1 })}</dd></div>
          <div><dt>Wpłacono</dt><dd><Money value={data.invested_pln} /></dd></div>
          <div><dt>Dywidendy i odsetki</dt><dd><Money value={sumMoney([data.dividends_net_pln, data.interest_net_pln])} /></dd></div>
        </dl>
        {approximate > 0 && (
          <p className="flag">
            {approximate} {pluralPl(approximate, "pozycja wyceniona", "pozycje wycenione", "pozycji wycenionych")} w przybliżeniu
          </p>
        )}
        {recalculating && <Recalculating />}
      </section>

      <section className={ui.section} aria-label="Wartość w czasie">
        {history.isPending ? <Skeleton chart rows={0} />
          : history.isError ? <ErrorState error={history.error} onRetry={() => void history.refetch()} />
            : <ValueChart points={history.data.points} />}
        <Segmented label="Zakres wykresu" options={RANGES} value={range} onChange={setRange} />
      </section>

      <section className={ui.section} aria-labelledby="allocation-title">
        <div className={ui.sectionHead}>
          <h2 id="allocation-title" className={ui.sectionTitle}>Alokacja</h2>
        </div>
        <Segmented label="Alokacja według" options={ALLOCATION_MODES} value={mode} onChange={setMode} />
        {mode === "currency" && exposure.isPending ? <Skeleton rows={2} />
          : mode === "currency" && exposure.isError ? <ErrorState error={exposure.error} onRetry={() => void exposure.refetch()} />
            : (
              <>
                <div className={styles.allocBar} aria-hidden="true">
                  {rows.map((row) => <i key={row.key} style={{ flex: Math.max(Number(row.value), 0), background: row.color }} />)}
                </div>
                <div>
                  {rows.map((row) => (
                    <div key={row.key} className={styles.allocRow}>
                      <span className={styles.dot} style={{ background: row.color }} />
                      <span>{row.name}</span>
                      <span className={styles.allocAmount}>
                        <Money value={row.value} />
                        <small className="num dim">{formatPercent(row.share, { sign: false, places: 1 })}</small>
                      </span>
                    </div>
                  ))}
                </div>
              </>
            )}
      </section>

      {movers.length > 0 && (
        <section className={ui.section} aria-labelledby="movers-title">
          <div className={ui.sectionHead}>
            <h2 id="movers-title" className={ui.sectionTitle}>Dziś najbardziej</h2>
            <Link className={ui.sectionMore} to="/pozycje">Wszystkie pozycje</Link>
          </div>
          <div>
            {movers.map(({ position, pct }) => (
              <ListRow
                key={`${position.account_id}-${position.instrument_id}`}
                to={`/pozycje/${position.account_id}/${position.instrument_id}`}
                lead={shortTicker(position.ticker ?? position.name)}
                title={position.name}
                subtitle={position.account_name}
                value={<span className={`num ${tone(pct)}`}>{formatPercent(pct)}</span>}
                detail={<Money value={position.day_change_pln} sign />}
              />
            ))}
          </div>
        </section>
      )}
    </div>
  );
}
```

`web/src/screens/dashboard/Dashboard.module.css`:

```css
.bar { display: flex; justify-content: space-between; align-items: center; gap: 12px; font-size: 13px; }
.hero { display: grid; gap: 8px; }
.today { font-size: 15px; }
.stats { display: grid; grid-template-columns: 1fr 1fr; gap: 12px 16px; margin: 6px 0 0; }
.stats div { display: grid; gap: 2px; }
.stats dt { color: var(--dim); font-size: 13px; }
.stats dd { margin: 0; font-size: 16px; font-weight: 500; }
.allocBar { display: flex; height: 10px; border-radius: 5px; overflow: hidden; gap: 2px; }
.allocBar i { display: block; height: 100%; min-width: 2px; }
.allocRow {
  display: grid; grid-template-columns: auto 1fr auto; align-items: center; gap: 12px;
  padding: 11px 0; border-top: 1px solid var(--rule);
}
.allocRow:first-child { border-top: 0; }
.dot { width: 9px; height: 9px; border-radius: 3px; }
.allocAmount { display: grid; text-align: right; }
.allocAmount small { font-size: 12.5px; }
```

`web/src/routes.tsx` — dodaj import `import { DashboardScreen } from "./screens/dashboard/DashboardScreen";` i zamień wiersz ścieżki `/`:

```tsx
          { path: "/", element: <DashboardScreen /> },
```

- [ ] **Step 6: Uruchom testy**

Run (z `web/`): `npm test -- src/screens/dashboard` → Expected: PASS.
Run: `npm test` → Expected: PASS wszystko (test „unknown addresses” z Task 5 trafia teraz na Pulpit — `SIGNED_IN` bez `/api/accounts` i `/api/portfolio/summary` odpowiada 404, co pokazuje ErrorState; asercja dotyczy tylko nawigacji i ścieżki, więc dalej przechodzi). Run: `npm run typecheck` → Expected: brak błędów.

- [ ] **Step 7: Commit**

```bash
git add web/src/format web/src/ui/ticker.ts web/src/test/fixtures.ts web/src/screens/dashboard web/src/routes.tsx
git commit -m "feat(web): dashboard with value, chart, allocation, the day's moves and recalculation polling

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 8: Pozycje i szczegóły pozycji

**Files:**
- Create: `web/src/screens/positions/model.ts`, `web/src/screens/positions/PositionsScreen.tsx`, `web/src/screens/positions/PositionDetailScreen.tsx`, `web/src/screens/positions/Positions.module.css`, `web/src/screens/positions/positions.test.tsx`
- Modify: `web/src/routes.tsx`, `web/src/test/fixtures.ts`

**Interfaces:**
- Consumes: `api`, `keys`, `Position`, `PositionDetail` (Task 3); `formatDate`, `formatDateTime`, `formatDays`, `formatDecimal`, `formatPercent`, `sumMoney` (Task 2); `AccountChips`, `HeroAmount`, `Money`, `ListRow`, `Skeleton`, `EmptyState`, `ErrorState`, `ui.module.css` (Task 5); `shortTicker` (Task 7); `POSITIONS`, `ACCOUNTS`, `position` (Task 7).
- Produces:
  - `positions/model.ts`: `groupPositions(positions): { key: "instruments" | "bonds" | "accounts"; title: string; total: string; items: Position[] }[]`, `flagLabel(flag: string): string`, `leadFor(p): string`, `subtitleFor(p): string`, `positionLink(p): string | undefined`, `transactionLabel(type: string): string`.
  - `PositionsScreen` pod `/pozycje`, `PositionDetailScreen` pod `/pozycje/:accountId/:instrumentId`.
  - `test/fixtures.ts`: + `DETAIL: PositionDetail`.

- [ ] **Step 1: Dane testowe szczegółów**

`web/src/test/fixtures.ts` — dopisz import typu `PositionDetail` do istniejącego importu z `../api/types` i na końcu pliku:

```ts
export const DETAIL: PositionDetail = {
  position: position({ instrument_id: 12, ticker: "CDR.PL", name: "CD Projekt", currency: "PLN", quantity: "48",
    price: "232.4700", price_source: "xtb", value_pln: "11158.56", cost_pln: "9227.52", unrealized_pln: "1931.04",
    unrealized_pct: "20.93", price_effect_pln: "1931.04", fx_effect_pln: "0.00", dividends_net_pln: "48.60",
    fees_pln: "-12.00", realized_pln: "215.30", share_pct: "6.05" }),
  lots: [
    { position_id: "777", opened_on: "2025-05-12", quantity: "30", open_price: "180.2000", cost_pln: "5406.00",
      value_pln: "6974.10", gain_pln: "1568.10", price_effect_pln: "1568.10", fx_effect_pln: "0.00", holding_days: 502,
      stop_loss: "150.0000", take_profit: null },
    { position_id: "778", opened_on: "2026-02-03", quantity: "18", open_price: "212.2900", cost_pln: "3821.52",
      value_pln: "4184.46", gain_pln: "362.94", price_effect_pln: "362.94", fx_effect_pln: "0.00", holding_days: 1,
      stop_loss: null, take_profit: null },
  ],
  sales: [
    { date: "2026-04-10", opened_on: "2025-05-12", holding_days: 333, quantity: "5", proceeds_pln: "1116.30",
      cost_pln: "901.00", realized_pln: "215.30", price_effect_pln: "215.30", fx_effect_pln: "0.00", position_id: "777", matched: true },
  ],
  income: [{ date: "2026-06-20", type: "dividend", amount: "60.00", currency: "PLN", amount_pln: "60.00" }],
  transactions: [
    { id: 1, account_id: 2, ticker: "CDR.PL", type: "buy", xtb_type: "Stock purchase", occurred_at: "2025-05-12T09:30:00",
      amount: "-5406.00", currency: "PLN", quantity: "30", price: "180.2", implied_fx_rate: null, xtb_position_id: "777",
      external_id: "1", comment: "", transfer_pair_id: null },
  ],
  reconciliation: { status: "mismatch", taken_at: "2026-09-26T12:00:00", xtb_quantity: "50", calculated_quantity: "48" },
};
```

- [ ] **Step 2: Testy**

`web/src/screens/positions/positions.test.tsx`:

```tsx
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ACCOUNTS, DETAIL, POSITIONS } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp, type MockRoute } from "../../test/render";
import { groupPositions, subtitleFor } from "./model";

const S = " ";
const M = "−";

const LIST: MockRoute[] = [
  ...SIGNED_IN,
  { path: "/api/accounts", respond: () => ACCOUNTS },
  { path: "/api/positions", respond: () => POSITIONS },
];

describe("positions model", () => {
  it("groups instruments, bonds and accounts with exact totals", () => {
    expect(groupPositions(POSITIONS).map((g) => [g.title, g.total, g.items.length])).toEqual([
      ["Akcje i ETF-y", "115848.89", 4], ["Obligacje", "10013.00", 1], ["Konta i gotówka", "44265.67", 2],
    ]);
    expect(groupPositions([])).toEqual([]);
  });

  it("describes each row by what it is", () => {
    expect(POSITIONS.map(subtitleFor)).toEqual([
      `IKE, 42 szt., udział 35,8${S}%`, `XTB, 42 szt., udział 17,1${S}%`, `XTB, 48 szt., udział 6,1${S}%`,
      `XTB, 110 szt., udział 3,9${S}%`, "Obligacje, 100 szt.", "Konto oszczędnościowe", "XTB, PLN",
    ]);
  });
});

describe("positions screen", () => {
  it("lists groups with totals, flags and links to instrument details", async () => {
    mockFetch(LIST);
    renderApp("/pozycje");

    const stocks = await screen.findByRole("region", { name: "Akcje i ETF-y" });
    expect(within(stocks).getByText(`115${S}848,89${S}zł`)).toBeInTheDocument();
    expect(within(stocks).getByRole("link", { name: /CD Projekt/ })).toHaveAttribute("href", "/pozycje/2/12");
    expect(within(stocks).getByText("cena z XTB")).toBeInTheDocument();
    expect(within(stocks).getByText(`${M}612,50${S}zł`)).toHaveClass("down");
    const accounts = screen.getByRole("region", { name: "Konta i gotówka" });
    expect(within(accounts).queryByRole("link")).not.toBeInTheDocument();
    expect(within(accounts).getByText("Gotówka")).toBeInTheDocument();
  });

  it("filters by account", async () => {
    const fetchMock = mockFetch(LIST);
    const { user } = renderApp("/pozycje");
    await user.click(await screen.findByRole("button", { name: "IKE" }));
    await screen.findByRole("region", { name: "Akcje i ETF-y" });
    expect(fetchMock.mock.calls.map(([url]) => String(url))).toContain("/api/positions?account_id=1");
  });

  it("invites an empty portfolio to import", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/accounts", respond: () => [] }, { path: "/api/positions", respond: () => [] }]);
    renderApp("/pozycje");
    expect(await screen.findByText("Nie masz jeszcze pozycji. Wgraj eksport z XTB, żeby je zobaczyć.")).toBeInTheDocument();
  });
});

describe("position detail", () => {
  it("shows the summary, the gain breakdown, lots, sales, income, operations and the XTB check", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/positions/2/12", respond: () => DETAIL }]);
    renderApp("/pozycje/2/12");

    expect(await screen.findByRole("heading", { name: "CD Projekt" })).toBeInTheDocument();
    expect(screen.getByText(`232,47${S}PLN`)).toBeInTheDocument();
    expect(screen.getByText("z XTB, 26.09.2026")).toBeInTheDocument();

    const gain = screen.getByRole("region", { name: "Zysk" });
    expect(within(gain).getByText("Dywidendy")).toBeInTheDocument();
    expect(within(gain).getByText(`${M}12,00${S}zł`)).toBeInTheDocument();

    const lots = screen.getByRole("region", { name: "Partie" });
    expect(within(lots).getByText(`30 szt. po 180,2${S}PLN`)).toBeInTheDocument();
    expect(within(lots).getByText("502 dni, SL 150")).toBeInTheDocument();
    expect(within(lots).getByText("1 dzień")).toBeInTheDocument();

    expect(screen.getByRole("region", { name: "Sprzedaże" })).toHaveTextContent("333 dni");
    expect(screen.getByRole("region", { name: "Dywidendy i odsetki" })).toHaveTextContent("Dywidenda");
    expect(screen.getByRole("region", { name: "Operacje" })).toHaveTextContent("Kupno");
    expect(screen.getByText("Niezgodność z XTB")).toBeInTheDocument();
    expect(screen.getByText("XTB: 50 szt., wyliczone: 48 szt., stan z 26.09.2026, 12:00")).toBeInTheDocument();
  });

  it("says when the position is not there", async () => {
    mockFetch([...SIGNED_IN, { path: "/api/positions/2/99", respond: () => json(404, { code: "not_found", message: "Nie znaleziono.", details: {} }) }]);
    renderApp("/pozycje/2/99");
    expect(await screen.findByRole("alert")).toHaveTextContent("Nie znaleziono.");
    expect(within(screen.getByRole("main")).getByRole("link", { name: "Pozycje" })).toHaveAttribute("href", "/pozycje");
  });
});
```

(Suma akcji: 66 024,73 + 31 518,90 + 11 158,56 + 7 146,70 = 115 848,89; konta: 40 132,18 + 4 133,49 = 44 265,67.)

- [ ] **Step 3: Uruchom — mają nie przejść**

Run (z `web/`): `npm test -- src/screens/positions`
Expected: FAIL — `Failed to resolve import "./model"`.

- [ ] **Step 4: Model**

`web/src/screens/positions/model.ts`:

```ts
import type { Position } from "../../api/types";
import { formatDecimal, formatPercent, sumMoney } from "../../format";
import { shortTicker } from "../../ui/ticker";

const GROUPS = [
  { key: "instruments", title: "Akcje i ETF-y", kinds: ["instrument"] },
  { key: "bonds", title: "Obligacje", kinds: ["bond"] },
  { key: "accounts", title: "Konta i gotówka", kinds: ["savings", "cash"] },
] as const;

export interface PositionGroup { key: (typeof GROUPS)[number]["key"]; title: string; total: string; items: Position[] }

export function groupPositions(positions: Position[]): PositionGroup[] {
  return GROUPS.flatMap((group) => {
    const items = positions.filter((p) => (group.kinds as readonly string[]).includes(p.kind));
    return items.length ? [{ key: group.key, title: group.title, total: sumMoney(items.map((p) => p.value_pln)), items }] : [];
  });
}

const FLAG_LABELS: Record<string, string> = {
  xtb_price: "cena z XTB",
  fx_missing: "brak kursu waluty",
  rate_estimated: "stopa szacunkowa",
};

export function flagLabel(flag: string): string {
  return FLAG_LABELS[flag] ?? "wycena przybliżona";
}

export function leadFor(p: Position): string {
  if (p.kind === "bond") return "EDO";
  if (p.kind === "savings") return "%";
  if (p.kind === "cash") return "zł";
  return shortTicker(p.ticker ?? p.name);
}

export function subtitleFor(p: Position): string {
  const quantity = `${formatDecimal(p.quantity, 8)} szt.`;
  if (p.kind === "instrument") {
    const share = p.share_pct === null ? "" : `, udział ${formatPercent(p.share_pct, { sign: false, places: 1 })}`;
    return `${p.account_name}, ${quantity}${share}`;
  }
  if (p.kind === "bond") return `${p.account_name}, ${quantity}`;
  if (p.kind === "savings") return p.account_name;
  return `${p.account_name}, ${p.currency ?? "PLN"}`;
}

export function positionLink(p: Position): string | undefined {
  return p.kind === "instrument" && p.instrument_id !== null ? `/pozycje/${p.account_id}/${p.instrument_id}` : undefined;
}

const TRANSACTION_LABELS: Record<string, string> = {
  buy: "Kupno", sell: "Sprzedaż", dividend: "Dywidenda", withholding_tax: "Podatek u źródła", interest: "Odsetki",
  interest_tax: "Podatek od odsetek", deposit: "Wpłata", withdrawal: "Wypłata", transfer_in: "Przelew przychodzący",
  transfer_out: "Przelew wychodzący", fee: "Opłata", unknown: "Nierozpoznana operacja",
};

export function transactionLabel(type: string): string {
  return TRANSACTION_LABELS[type] ?? type;
}
```

- [ ] **Step 5: Ekrany**

`web/src/screens/positions/PositionsScreen.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import { AccountChips } from "../../ui/AccountPicker";
import { Money } from "../../ui/Amount";
import { ListRow } from "../../ui/ListRow";
import { EmptyState, ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { flagLabel, groupPositions, leadFor, positionLink, subtitleFor } from "./model";
import styles from "./Positions.module.css";

export function PositionsScreen() {
  const [accountId, setAccountId] = useState<number | null>(null);
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const positions = useQuery({ queryKey: keys.positions(accountId), queryFn: () => api.positions(accountId) });

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Pozycje</h1>
      {(accounts.data?.length ?? 0) > 0 && <AccountChips accounts={accounts.data!} value={accountId} onChange={setAccountId} />}
      {positions.isPending ? <Skeleton rows={6} />
        : positions.isError ? <ErrorState error={positions.error} onRetry={() => void positions.refetch()} />
          : positions.data.length === 0 ? (
            <EmptyState
              title="Nie masz jeszcze pozycji. Wgraj eksport z XTB, żeby je zobaczyć."
              action={<Link className={ui.primaryButton} to="/dodaj">Wgraj pliki z XTB</Link>}
            />
          ) : groupPositions(positions.data).map((group) => (
            <section key={group.key} className={ui.section} aria-labelledby={`group-${group.key}`}>
              <div className={styles.groupHead}>
                <h2 id={`group-${group.key}`} className={styles.groupTitle}>{group.title}</h2>
                <Money value={group.total} />
              </div>
              <div>
                {group.items.map((p) => (
                  <ListRow
                    key={`${p.kind}-${p.account_id}-${p.instrument_id ?? p.bond_holding_id ?? p.savings_account_id ?? p.currency}`}
                    to={positionLink(p)}
                    lead={leadFor(p)}
                    title={p.name}
                    subtitle={
                      <>
                        {subtitleFor(p)}
                        {p.flags.length > 0 && <span className={`flag ${styles.flags}`}>{p.flags.map(flagLabel).join(", ")}</span>}
                      </>
                    }
                    value={<Money value={p.value_pln} />}
                    detail={p.kind === "cash" ? <span className="dim">—</span> : <Money value={p.unrealized_pln} sign tone />}
                  />
                ))}
              </div>
            </section>
          ))}
    </div>
  );
}
```

`web/src/screens/positions/PositionDetailScreen.tsx`:

```tsx
import { useQuery } from "@tanstack/react-query";
import type { ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { PositionDetail, Reconciliation } from "../../api/types";
import { formatDate, formatDateTime, formatDays, formatDecimal, formatPercent, signOf } from "../../format";
import { HeroAmount, Money } from "../../ui/Amount";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import { transactionLabel } from "./model";
import styles from "./Positions.module.css";

function Back() {
  return (
    <Link className={styles.back} to="/pozycje">
      <svg width="10" height="14" viewBox="0 0 10 14" aria-hidden="true">
        <path d="M8 1 2 7l6 6" fill="none" stroke="currentColor" strokeWidth="1.6" strokeLinecap="round" />
      </svg>
      Pozycje
    </Link>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  const id = `section-${title.replace(/\s+/g, "-")}`;
  return (
    <section className={ui.section} aria-labelledby={id}>
      <h2 id={id} className={ui.sectionTitle}>{title}</h2>
      {children}
    </section>
  );
}

function Entry({ title, subtitle, value, detail }: { title: ReactNode; subtitle?: ReactNode; value: ReactNode; detail?: ReactNode }) {
  return (
    <li className={styles.entry}>
      <span className={styles.entryName}><b>{title}</b>{subtitle && <small>{subtitle}</small>}</span>
      <span className={styles.entryAmount}><span>{value}</span>{detail && <small>{detail}</small>}</span>
    </li>
  );
}

const price = (value: string | null, currency: string | null) =>
  value === null ? "—" : `${formatDecimal(value, 4)} ${currency ?? ""}`.trim();

function reconciliationText(r: Reconciliation): { title: string; subtitle: string; tone: string } {
  const when = r.taken_at ? `stan z ${formatDateTime(r.taken_at)}` : "";
  if (r.status === "ok") return { title: "Zgodne z XTB", subtitle: when, tone: "up" };
  if (r.status === "mismatch") {
    const xtb = r.xtb_quantity === null ? "—" : formatDecimal(r.xtb_quantity, 8);
    const calculated = r.calculated_quantity === null ? "—" : formatDecimal(r.calculated_quantity, 8);
    return { title: "Niezgodność z XTB", subtitle: `XTB: ${xtb} szt., wyliczone: ${calculated} szt., ${when}`, tone: "down" };
  }
  return { title: "Brak stanu z XTB do porównania", subtitle: "Wgraj eksport z zakładką Open Positions.", tone: "dim" };
}

function Detail({ detail }: { detail: PositionDetail }) {
  const p = detail.position;
  const check = reconciliationText(detail.reconciliation);
  const gainTone = signOf(p.unrealized_pln) > 0 ? "up" : signOf(p.unrealized_pln) < 0 ? "down" : "";
  const source = p.price_source === "xtb" ? "z XTB" : "od dostawcy";
  return (
    <>
      <section className={styles.head} aria-label="Podsumowanie pozycji">
        <span className="dim">{[p.ticker, p.account_name].filter(Boolean).join(", ")}</span>
        <h1 className={styles.name}>{p.name}</h1>
        <HeroAmount value={p.value_pln} size="m" />
        <p className={`num ${gainTone}`}>
          <Money value={p.unrealized_pln} sign /> ({formatPercent(p.unrealized_pct)})
        </p>
      </section>

      <Section title="Podsumowanie">
        <dl className={ui.kv}>
          <dt>Ilość</dt><dd>{formatDecimal(p.quantity, 8)} szt.</dd>
          <dt>Cena</dt><dd>{price(p.price, p.currency)}</dd>
          {p.price_date && <><dt>Źródło ceny</dt><dd>{`${source}, ${formatDate(p.price_date)}`}</dd></>}
          <dt>Koszt</dt><dd><Money value={p.cost_pln} /></dd>
          {p.share_pct !== null && <><dt>Udział w portfelu</dt><dd>{formatPercent(p.share_pct, { sign: false, places: 1 })}</dd></>}
        </dl>
      </Section>

      <Section title="Zysk">
        <dl className={ui.kv}>
          <dt>Zmiana ceny</dt><dd><Money value={p.price_effect_pln} sign tone /></dd>
          <dt>Kurs waluty</dt><dd><Money value={p.fx_effect_pln} sign tone /></dd>
          <dt>Dywidendy</dt><dd><Money value={p.dividends_net_pln} sign tone /></dd>
          <dt>Koszty</dt><dd><Money value={p.fees_pln} sign tone /></dd>
          <dt>Zrealizowany</dt><dd><Money value={p.realized_pln} sign tone /></dd>
        </dl>
      </Section>

      <Section title="Partie">
        <ul className={styles.list}>
          {detail.lots.map((lot, i) => (
            <Entry
              key={lot.position_id ?? i}
              title={formatDate(lot.opened_on)}
              subtitle={`${formatDecimal(lot.quantity, 8)} szt. po ${price(lot.open_price, p.currency)}`}
              value={<Money value={lot.gain_pln} sign tone />}
              detail={[
                formatDays(lot.holding_days),
                lot.stop_loss ? `SL ${formatDecimal(lot.stop_loss, 4)}` : "",
                lot.take_profit ? `TP ${formatDecimal(lot.take_profit, 4)}` : "",
              ].filter(Boolean).join(", ")}
            />
          ))}
        </ul>
      </Section>

      {detail.sales.length > 0 && (
        <Section title="Sprzedaże">
          <ul className={styles.list}>
            {detail.sales.map((sale, i) => (
              <Entry key={i} title={formatDate(sale.date)} subtitle={`${formatDecimal(sale.quantity, 8)} szt., ${formatDays(sale.holding_days)}`}
                value={<Money value={sale.realized_pln} sign tone />} detail={<Money value={sale.proceeds_pln} />} />
            ))}
          </ul>
        </Section>
      )}

      {detail.income.length > 0 && (
        <Section title="Dywidendy i odsetki">
          <ul className={styles.list}>
            {detail.income.map((item, i) => (
              <Entry key={i} title={formatDate(item.date)} subtitle={transactionLabel(item.type)}
                value={<Money value={item.amount_pln} sign tone />} />
            ))}
          </ul>
        </Section>
      )}

      <Section title="Operacje">
        <ul className={styles.list}>
          {detail.transactions.map((t) => (
            <Entry key={t.id} title={transactionLabel(t.type)} subtitle={formatDateTime(t.occurred_at)}
              value={<Money value={t.amount} sign currency={t.currency} />}
              detail={t.quantity ? `${formatDecimal(t.quantity, 8)} szt.` : undefined} />
          ))}
        </ul>
      </Section>

      <Section title="Zgodność z XTB">
        <p className={check.tone}>{check.title}</p>
        {check.subtitle && <p className="dim">{check.subtitle}</p>}
      </Section>
    </>
  );
}

export function PositionDetailScreen() {
  const params = useParams();
  const accountId = Number(params.accountId);
  const instrumentId = Number(params.instrumentId);
  const valid = Number.isInteger(accountId) && Number.isInteger(instrumentId);
  const detail = useQuery({
    queryKey: keys.position(accountId, instrumentId),
    queryFn: () => api.position(accountId, instrumentId),
    enabled: valid,
  });
  if (!valid) return <Navigate to="/pozycje" replace />;

  return (
    <div className={ui.page}>
      <Back />
      {detail.isPending ? <Skeleton rows={6} />
        : detail.isError ? <ErrorState error={detail.error} onRetry={() => void detail.refetch()} />
          : <Detail detail={detail.data} />}
    </div>
  );
}
```

`web/src/screens/positions/Positions.module.css`:

```css
.groupHead { display: flex; justify-content: space-between; align-items: baseline; gap: 12px; color: var(--dim); font-size: 13px; }
.groupTitle { font-size: 13px; font-weight: 500; color: var(--dim); }
.flags { display: block; }
.back { display: inline-flex; align-items: center; gap: 6px; color: var(--dim); font-size: 14px; min-height: 44px; }
.head { display: grid; gap: 6px; }
.name { font-size: 24px; font-weight: 600; letter-spacing: -.02em; }
.list { list-style: none; margin: 0; padding: 0; }
.entry {
  display: grid; grid-template-columns: 1fr auto; gap: 12px; align-items: center;
  padding: 11px 0; border-top: 1px solid var(--rule);
}
.entry:first-child { border-top: 0; }
.entryName { display: grid; min-width: 0; }
.entryName b { font-weight: 500; }
.entryName small, .entryAmount small { color: var(--dim); font-size: 12.5px; }
.entryAmount { display: grid; text-align: right; font-variant-numeric: tabular-nums; }
```

`web/src/routes.tsx` — dodaj importy `PositionsScreen` i `PositionDetailScreen` z `./screens/positions/…` i zamień dwa wiersze:

```tsx
          { path: "/pozycje", element: <PositionsScreen /> },
          { path: "/pozycje/:accountId/:instrumentId", element: <PositionDetailScreen /> },
```

- [ ] **Step 6: Uruchom testy**

Run (z `web/`): `npm test -- src/screens/positions` → Expected: PASS.
Run: `npm test` → Expected: PASS wszystko. Run: `npm run typecheck` → Expected: brak błędów.

- [ ] **Step 7: Commit**

```bash
git add web/src/screens/positions web/src/routes.tsx web/src/test/fixtures.ts
git commit -m "feat(web): positions grouped by kind and the position detail with lots, income and the XTB check

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 9: Import XTB z podglądem

**Files:**
- Create: `web/src/screens/import/ImportScreen.tsx`, `web/src/screens/import/Import.module.css`, `web/src/screens/import/import.test.tsx`
- Modify: `web/src/routes.tsx`, `web/src/test/fixtures.ts`

**Interfaces:**
- Consumes: `api.previewImport`, `api.commitImport`, `keys`, `ImportResult`, `ImportFile` (Task 3); `formatDate`, `pluralPl` (Task 2, Task 7); `ErrorState`, `Skeleton`, `ui.module.css` (Task 5).
- Produces: `ImportScreen` pod `/dodaj`; `test/fixtures.ts`: + `IMPORT_FILE: ImportFile`, `PREVIEW: ImportResult`.
- Zachowanie: wybór plików (`<input type="file" multiple accept=".xlsx,.zip" aria-label="Wybierz pliki">`, na komputerze także upuszczenie) od razu wysyła podgląd; „Zapisz import” wysyła te same pliki; po zapisie unieważnia `["portfolio"]` i `["accounts"]` i pokazuje „Import zapisany” z linkiem „Zobacz pulpit”.

- [ ] **Step 1: Dane testowe**

`web/src/test/fixtures.ts` — dopisz `ImportFile`, `ImportResult` do importu typów i na końcu:

```ts
export const IMPORT_FILE: ImportFile = {
  filename: "IKE_56216965_2006-01-01_2026-09-26.xlsx", account_number: "56216965", wrapper: "ike", currency: "PLN",
  account_id: null, account_name: "IKE 56216965", new_account: true, report_from: "2006-01-01T00:00:00",
  report_to: "2026-09-26T00:00:00", new_transactions: 42, duplicate_transactions: 3, unknown_transactions: 1,
  open_lots: 5, closed_lots: 2, warnings: [{ code: "quantity_mismatch", message: "Ilość SXR8.DE różni się od XTB.", details: {} }],
  import_id: null,
};

export const PREVIEW: ImportResult = { files: [IMPORT_FILE], errors: [], skipped: [] };
```

- [ ] **Step 2: Testy**

`web/src/screens/import/import.test.tsx`:

```tsx
import { screen, within } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { NETWORK_MESSAGE } from "../../api/client";
import { IMPORT_FILE, PREVIEW } from "../../test/fixtures";
import { SIGNED_IN, json, mockFetch, renderApp } from "../../test/render";

const xlsx = (name = IMPORT_FILE.filename) => new File(["xlsx"], name, { type: "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" });

function sentNames(init: RequestInit | undefined): string[] {
  return (init!.body as FormData).getAll("files").map((f) => (f as File).name);
}

describe("import screen", () => {
  it("previews the files, then saves the same files and leads to the dashboard", async () => {
    const sent: string[][] = [];
    mockFetch([
      ...SIGNED_IN,
      { method: "POST", path: "/api/imports/preview", respond: (_u, init) => { sent.push(sentNames(init)); return PREVIEW; } },
      {
        method: "POST", path: "/api/imports",
        respond: (_u, init) => { sent.push(sentNames(init)); return json(201, { ...PREVIEW, files: [{ ...IMPORT_FILE, import_id: 9, account_id: 5 }] }); },
      },
    ]);
    const { user } = renderApp("/dodaj");

    await user.upload(await screen.findByLabelText("Wybierz pliki"), [xlsx(), xlsx("XTB_56204082.xlsx")]);

    const card = await screen.findByRole("region", { name: IMPORT_FILE.filename });
    expect(within(card).getByText("Zostanie założone konto: IKE 56216965")).toBeInTheDocument();
    expect(within(card).getByText("01.01.2006 – 26.09.2026")).toBeInTheDocument();
    expect(within(card).getByText("Nowe operacje").nextSibling).toHaveTextContent("42");
    expect(within(card).getByText("Ilość SXR8.DE różni się od XTB.")).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Zapisz import" }));

    expect(await screen.findByRole("heading", { name: "Import zapisany" })).toBeInTheDocument();
    expect(screen.getByText("Dodano 42 nowe operacje. Wycena przelicza się w tle.")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: "Zobacz pulpit" })).toHaveAttribute("href", "/");
    expect(sent).toEqual([[IMPORT_FILE.filename, "XTB_56204082.xlsx"], [IMPORT_FILE.filename, "XTB_56204082.xlsx"]]);
  });

  it("shows an unreadable file next to the others and does not offer to save", async () => {
    mockFetch([
      ...SIGNED_IN,
      {
        method: "POST", path: "/api/imports/preview",
        respond: () => ({ ...PREVIEW, errors: [{ filename: "zepsuty.xlsx", code: "bad_workbook", message: "Plik nie jest eksportem XTB." }], skipped: ["notatki.txt"] }),
      },
    ]);
    const { user } = renderApp("/dodaj");

    await user.upload(await screen.findByLabelText("Wybierz pliki"), [xlsx(), xlsx("zepsuty.xlsx")]);

    expect(await screen.findByText("zepsuty.xlsx: Plik nie jest eksportem XTB.")).toBeInTheDocument();
    expect(screen.getByText("Pominięto plik notatki.txt, bo nie jest plikiem XLSX.")).toBeInTheDocument();
    expect(screen.getByRole("region", { name: IMPORT_FILE.filename })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zapisz import" })).toBeDisabled();
    expect(screen.getByText("Niektórych plików nie da się odczytać. Wybierz pliki bez nich, żeby zapisać import.")).toBeInTheDocument();
  });

  it("explains that there is nothing new to save", async () => {
    mockFetch([
      ...SIGNED_IN,
      { method: "POST", path: "/api/imports/preview", respond: () => ({ ...PREVIEW, files: [{ ...IMPORT_FILE, new_account: false, account_id: 5, new_transactions: 0 }] }) },
    ]);
    const { user } = renderApp("/dodaj");

    await user.upload(await screen.findByLabelText("Wybierz pliki"), [xlsx()]);

    expect(await screen.findByText("Nic nowego do zapisania. Wszystkie operacje są już w aplikacji.")).toBeInTheDocument();
    expect(screen.getByText("Konto: IKE 56216965")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Zapisz import" })).toBeDisabled();
  });

  it("keeps the chosen files when the preview fails and tries again", async () => {
    let attempts = 0;
    const fetchMock = mockFetch([...SIGNED_IN, { method: "POST", path: "/api/imports/preview", respond: () => PREVIEW }]);
    const original = fetchMock.getMockImplementation()!;
    fetchMock.mockImplementation((input: string, init?: RequestInit) =>
      String(input) === "/api/imports/preview" && ++attempts === 1 ? Promise.reject(new TypeError("Failed to fetch")) : original(input, init));
    const { user } = renderApp("/dodaj");

    await user.upload(await screen.findByLabelText("Wybierz pliki"), [xlsx()]);
    expect(await screen.findByRole("alert")).toHaveTextContent(NETWORK_MESSAGE);
    expect(screen.getByText(IMPORT_FILE.filename)).toBeInTheDocument();

    await user.click(screen.getByRole("button", { name: "Spróbuj ponownie" }));
    expect(await screen.findByRole("region", { name: IMPORT_FILE.filename })).toBeInTheDocument();
  });
});
```

- [ ] **Step 3: Uruchom — mają nie przejść**

Run (z `web/`): `npm test -- src/screens/import`
Expected: FAIL — `Unable to find a label with the text of: Wybierz pliki` (pod `/dodaj` jest jeszcze `Placeholder`).

- [ ] **Step 4: Ekran**

`web/src/screens/import/ImportScreen.tsx`:

```tsx
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState, type DragEvent } from "react";
import { Link } from "react-router";
import { api } from "../../api/endpoints";
import { keys } from "../../api/queryKeys";
import type { ImportFile, ImportResult } from "../../api/types";
import { formatDate, pluralPl } from "../../format";
import { ErrorState, Skeleton } from "../../ui/States";
import ui from "../../ui/ui.module.css";
import styles from "./Import.module.css";

const ACCEPT = ".xlsx,.zip";

function period(file: ImportFile): string | null {
  if (!file.report_from || !file.report_to) return null;
  return `${formatDate(file.report_from)} – ${formatDate(file.report_to)}`;
}

function FileCard({ file }: { file: ImportFile }) {
  const id = `import-${file.filename.replace(/[^a-zA-Z0-9_-]/g, "-")}`;
  return (
    <section className={styles.card} aria-labelledby={id}>
      <h2 id={id} className={styles.cardTitle}>{file.filename}</h2>
      <p>{file.new_account ? `Zostanie założone konto: ${file.account_name}` : `Konto: ${file.account_name}`}</p>
      {period(file) && <p className="dim num">{period(file)}</p>}
      <dl className={ui.kv}>
        <dt>Nowe operacje</dt><dd>{file.new_transactions}</dd>
        <dt>Już zaimportowane</dt><dd>{file.duplicate_transactions}</dd>
        <dt>Nierozpoznane</dt><dd>{file.unknown_transactions}</dd>
        <dt>Partie otwarte</dt><dd>{file.open_lots}</dd>
        <dt>Partie zamknięte</dt><dd>{file.closed_lots}</dd>
      </dl>
      {file.warnings.length > 0 && (
        <ul className={styles.warnings}>
          {file.warnings.map((w, i) => <li key={i} className="flag">{w.message}</li>)}
        </ul>
      )}
    </section>
  );
}

function blocker(result: ImportResult): string | null {
  if (result.errors.length > 0) return "Niektórych plików nie da się odczytać. Wybierz pliki bez nich, żeby zapisać import.";
  if (result.files.length === 0) return "Wśród wybranych plików nie ma eksportu z XTB.";
  if (result.files.every((f) => f.new_transactions === 0 && !f.new_account)) {
    return "Nic nowego do zapisania. Wszystkie operacje są już w aplikacji.";
  }
  return null;
}

export function ImportScreen() {
  const queryClient = useQueryClient();
  const [files, setFiles] = useState<File[]>([]);
  const [dragging, setDragging] = useState(false);
  const preview = useMutation({ mutationFn: api.previewImport });
  const commit = useMutation({
    mutationFn: api.commitImport,
    onSuccess: () => {
      void queryClient.invalidateQueries({ queryKey: keys.portfolio });
      void queryClient.invalidateQueries({ queryKey: keys.accounts });
    },
  });

  function choose(list: FileList | null) {
    const chosen = Array.from(list ?? []);
    if (chosen.length === 0) return;
    setFiles(chosen);
    commit.reset();
    preview.mutate(chosen);
  }

  function drop(event: DragEvent) {
    event.preventDefault();
    setDragging(false);
    choose(event.dataTransfer.files);
  }

  function restart() {
    setFiles([]);
    preview.reset();
    commit.reset();
  }

  if (commit.isSuccess) {
    const added = commit.data.files.reduce((total, f) => total + f.new_transactions, 0);
    return (
      <div className={ui.page}>
        <h1 className={ui.pageTitle}>Import zapisany</h1>
        <p>
          Dodano {added} {pluralPl(added, "nową operację", "nowe operacje", "nowych operacji")}. Wycena przelicza się w tle.
        </p>
        <div className={styles.actions}>
          <Link className={ui.primaryButton} to="/">Zobacz pulpit</Link>
          <button type="button" className={ui.secondary} onClick={restart}>Wgraj kolejne pliki</button>
        </div>
      </div>
    );
  }

  const result = preview.data;
  const reason = result ? blocker(result) : null;

  return (
    <div className={ui.page}>
      <h1 className={ui.pageTitle}>Wgraj eksport z XTB</h1>
      <p className="dim">
        Wybierz pliki XLSX z historią rachunku albo ZIP z kilkoma plikami. Przed zapisem zobaczysz, co zostanie dodane.
      </p>

      <label
        className={`${styles.drop} ${dragging ? styles.dragging : ""}`}
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={drop}
      >
        <input
          className={styles.input}
          type="file"
          multiple
          accept={ACCEPT}
          aria-label="Wybierz pliki"
          onChange={(e) => { choose(e.target.files); e.target.value = ""; }}
        />
        <span className={ui.secondary}>Wybierz pliki</span>
        <span className="dim">albo przeciągnij je tutaj</span>
      </label>

      {files.length > 0 && (
        <ul className={styles.chosen} aria-label="Wybrane pliki">
          {files.map((f) => <li key={f.name}>{f.name}</li>)}
        </ul>
      )}

      {preview.isPending && <Skeleton rows={4} />}
      {preview.isError && <ErrorState error={preview.error} onRetry={() => preview.mutate(files)} />}

      {result && (
        <>
          {result.errors.map((e) => <p key={e.filename} className="down">{`${e.filename}: ${e.message}`}</p>)}
          {result.skipped.map((name) => <p key={name} className="dim">{`Pominięto plik ${name}, bo nie jest plikiem XLSX.`}</p>)}
          {result.files.map((file) => <FileCard key={`${file.filename}-${file.account_number}`} file={file} />)}
          <div className={styles.commit}>
            {reason && <p className="dim">{reason}</p>}
            {commit.isError && <ErrorState error={commit.error} />}
            <button
              type="button"
              className={ui.primaryButton}
              disabled={reason !== null || commit.isPending}
              aria-busy={commit.isPending}
              onClick={() => commit.mutate(files)}
            >
              Zapisz import
            </button>
          </div>
        </>
      )}
    </div>
  );
}
```

`web/src/screens/import/Import.module.css`:

```css
.drop {
  position: relative; display: grid; justify-items: center; gap: 10px; padding: 28px 16px;
  border: 1px dashed var(--rule); border-radius: var(--r-sheet); text-align: center; cursor: pointer;
}
.drop:focus-within { outline: 2px solid var(--amber); outline-offset: 2px; }
.dragging { border-color: var(--amber); background: var(--amber-soft); }
.input { position: absolute; inset: 0; opacity: 0; cursor: pointer; }
.chosen { list-style: none; margin: 0; padding: 0; color: var(--dim); font-size: 13px; display: grid; gap: 4px; }
.card { display: grid; gap: 8px; padding: 16px; border: 1px solid var(--rule); border-radius: var(--r-sheet); background: var(--slab); }
.cardTitle { font-size: 15px; font-weight: 600; word-break: break-all; }
.warnings { margin: 0; padding-left: 18px; display: grid; gap: 4px; }
.commit { display: grid; gap: 10px; justify-items: start; }
.actions { display: flex; flex-wrap: wrap; gap: 10px; }
```

`web/src/routes.tsx` — dodaj import `ImportScreen` z `./screens/import/ImportScreen` i zamień wiersz:

```tsx
          { path: "/dodaj", element: <ImportScreen /> },
```

Usuń z `routes.tsx` nieużywaną już funkcję `Placeholder`.

- [ ] **Step 5: Uruchom testy**

Run (z `web/`): `npm test -- src/screens/import` → Expected: PASS.
Run: `npm test` → Expected: PASS wszystko. Run: `npm run typecheck` → Expected: brak błędów.

- [ ] **Step 6: Commit**

```bash
git add web/src/screens/import web/src/routes.tsx web/src/test/fixtures.ts
git commit -m "feat(web): XTB import with a per-file preview and a guarded save

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 10: PWA — manifest, ikony, service worker

**Files:**
- Create: `web/pwa.config.ts`, `web/pwa.config.test.ts`, `web/pwa-assets.config.ts`, `web/public/icon.svg`, wygenerowane `web/public/pwa-64x64.png`, `web/public/pwa-192x192.png`, `web/public/pwa-512x512.png`, `web/public/maskable-icon-512x512.png`, `web/public/apple-touch-icon-180x180.png`, `web/public/favicon.ico`
- Modify: `web/vite.config.ts`, `web/index.html`

**Interfaces:**
- Consumes: projekt z Task 1.
- Produces: `pwaOptions` (`web/pwa.config.ts`) podpięte w `vite.config.ts` poza trybem testów; `npm run build` tworzy `dist/manifest.webmanifest` i `dist/sw.js`. Service worker zapamiętuje tylko pliki aplikacji; `/api/**` zawsze idzie do sieci.

- [ ] **Step 1: Test konfiguracji**

`web/pwa.config.test.ts`:

```ts
import { describe, expect, it } from "vitest";
import { pwaOptions } from "./pwa.config";

describe("PWA", () => {
  const manifest = pwaOptions.manifest as Record<string, unknown> & { icons: { sizes: string; purpose?: string }[] };

  it("installs as a standalone dark app named Portfel", () => {
    expect(manifest).toMatchObject({
      name: "Portfel", short_name: "Portfel", lang: "pl", display: "standalone", start_url: "/",
      background_color: "#0E1116", theme_color: "#0E1116",
    });
  });

  it("ships the icons phones ask for, including a maskable one", () => {
    expect(manifest.icons.map((i) => i.sizes)).toEqual(expect.arrayContaining(["192x192", "512x512"]));
    expect(manifest.icons.some((i) => i.purpose === "maskable")).toBe(true);
  });

  it("never serves API answers from the cache", () => {
    const workbox = pwaOptions.workbox!;
    expect(workbox.runtimeCaching ?? []).toEqual([]);
    expect(workbox.navigateFallbackDenylist!.some((pattern) => pattern.test("/api/portfolio/summary"))).toBe(true);
  });
});
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run (z `web/`): `npm test -- pwa.config.test.ts`
Expected: FAIL — `Failed to resolve import "./pwa.config"`.

- [ ] **Step 3: Konfiguracja PWA i ikony**

`web/pwa.config.ts`:

```ts
import type { VitePWAOptions } from "vite-plugin-pwa";

/** The service worker keeps only the app's own files: money always comes fresh from the API. */
export const pwaOptions: Partial<VitePWAOptions> = {
  registerType: "autoUpdate",
  injectRegister: "auto",
  includeAssets: ["favicon.ico", "apple-touch-icon-180x180.png", "icon.svg"],
  manifest: {
    name: "Portfel",
    short_name: "Portfel",
    description: "Cały portfel inwestycyjny w jednym miejscu.",
    lang: "pl",
    start_url: "/",
    scope: "/",
    display: "standalone",
    background_color: "#0E1116",
    theme_color: "#0E1116",
    icons: [
      { src: "pwa-64x64.png", sizes: "64x64", type: "image/png" },
      { src: "pwa-192x192.png", sizes: "192x192", type: "image/png" },
      { src: "pwa-512x512.png", sizes: "512x512", type: "image/png" },
      { src: "maskable-icon-512x512.png", sizes: "512x512", type: "image/png", purpose: "maskable" },
    ],
  },
  workbox: {
    globPatterns: ["**/*.{js,css,html,svg,png,ico,woff2}"],
    navigateFallback: "/index.html",
    navigateFallbackDenylist: [/^\/api\//],
    runtimeCaching: [],
  },
  devOptions: { enabled: false },
};
```

`web/vite.config.ts` (zastąp):

```ts
/// <reference types="vitest/config" />
import react from "@vitejs/plugin-react";
import { defineConfig } from "vite";
import { VitePWA } from "vite-plugin-pwa";
import { pwaOptions } from "./pwa.config";

// The API runs in docker on :8000 (e2e: its own instance, API_TARGET=http://localhost:8001). Proxying /api keeps the
// browser on one origin, so the httpOnly refresh cookie works without CORS.
const apiTarget = process.env.API_TARGET ?? "http://localhost:8000";

export default defineConfig(({ mode }) => ({
  plugins: [react(), ...(mode === "test" ? [] : [VitePWA(pwaOptions)])],
  server: { port: 5173, proxy: { "/api": { target: apiTarget } } },
  preview: { proxy: { "/api": { target: apiTarget } } },
  test: {
    environment: "jsdom",
    setupFiles: ["./src/test/setup.ts"],
    include: ["src/**/*.test.{ts,tsx}", "*.test.ts"],
    css: { modules: { classNameStrategy: "non-scoped" } },
    restoreMocks: true,
  },
}));
```

`web/public/icon.svg`:

```svg
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" rx="112" fill="#0E1116"/>
  <path d="M120 372H208V316H300V252H392" fill="none" stroke="#8B94A1" stroke-width="18" stroke-linecap="round" stroke-linejoin="round"/>
  <path d="M120 344C172 330 196 282 240 270S316 206 392 160" fill="none" stroke="#F0A43A" stroke-width="30" stroke-linecap="round"/>
  <circle cx="392" cy="160" r="24" fill="#F0A43A"/>
</svg>
```

`web/pwa-assets.config.ts`:

```ts
import { defineConfig, minimal2023Preset as preset } from "@vite-pwa/assets-generator/config";

const background = { background: "#0E1116" };

export default defineConfig({
  headLinkOptions: { preset: "2023" },
  preset: {
    ...preset,
    maskable: { ...preset.maskable, resizeOptions: background },
    apple: { ...preset.apple, resizeOptions: background },
  },
  images: ["public/icon.svg"],
});
```

Run (z `web/`): `npm run icons`
Expected: w `web/public/` powstają `pwa-64x64.png`, `pwa-192x192.png`, `pwa-512x512.png`, `maskable-icon-512x512.png`, `apple-touch-icon-180x180.png`, `favicon.ico`.

`web/index.html` — w `<head>` po `<meta name="color-scheme" …>` dopisz:

```html
    <link rel="icon" href="/favicon.ico" sizes="48x48" />
    <link rel="icon" href="/icon.svg" type="image/svg+xml" />
    <link rel="apple-touch-icon" href="/apple-touch-icon-180x180.png" />
    <meta name="mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-capable" content="yes" />
    <meta name="apple-mobile-web-app-status-bar-style" content="black-translucent" />
    <meta name="apple-mobile-web-app-title" content="Portfel" />
```

- [ ] **Step 4: Uruchom testy i build**

Run (z `web/`): `npm test` → Expected: PASS wszystko.
Run: `npm run build` → Expected: sukces; w `dist/` są `manifest.webmanifest`, `sw.js`, ikony.
Run: `node -e "const m=JSON.parse(require('fs').readFileSync('dist/manifest.webmanifest','utf8'));console.log(m.display,m.theme_color,m.icons.length)"`
Expected: `standalone #0E1116 4`.

- [ ] **Step 5: Commit**

```bash
git add web/pwa.config.ts web/pwa.config.test.ts web/pwa-assets.config.ts web/public web/vite.config.ts web/index.html
git commit -m "feat(web): installable PWA with icons and an app-shell-only service worker

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 11: Test e2e na osobnej bazie; README i roadmapa

**Files:**
- Create: `api/tests/e2e_fixture.py`, `web/playwright.config.ts`, `web/e2e/global-setup.ts`, `web/e2e/global-teardown.ts`, `web/e2e/app.spec.ts`
- Modify: `docker-compose.yml`, `README.md`, `docs/superpowers/plans/2026-09-26-00-roadmap.md`

**Interfaces:**
- Consumes: `api/tests/xtb_factory.py` (`build_report`, `cash_row`, `buy_row`, `summary_row`, `lot_row`, `filename`); wszystkie ekrany (Task 4–9).
- Produces: usługi `db-e2e` (Postgres na tmpfs, port 5434) i `api-e2e` (port 8001) w profilu `e2e`; `python -m tests.e2e_fixture` zapisuje `api/.e2e/IKE_56216965_2006-01-01_2026-09-26.xlsx`; `npm run e2e` — rejestracja → import → pulpit → pozycje → szczegóły, zrzuty 390 px w `web/e2e/screens/`.

- [ ] **Step 1: Usługi e2e w `docker-compose.yml`**

Dopisz w sekcji `services:` (przed `volumes:`):

```yaml
  db-e2e:
    image: postgres:16
    profiles: ["e2e"]
    environment:
      POSTGRES_USER: portfolio
      POSTGRES_PASSWORD: portfolio
      POSTGRES_DB: portfolio_e2e
    ports:
      - "5434:5432"
    tmpfs:
      - /var/lib/postgresql/data
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U portfolio -d portfolio_e2e"]
      interval: 2s
      timeout: 3s
      retries: 20

  api-e2e:
    build: ./api
    profiles: ["e2e"]
    command: sh -c "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"
    environment:
      DATABASE_URL: postgresql+psycopg://portfolio:portfolio@db-e2e:5432/portfolio_e2e
      JWT_SECRET: e2e-secret-that-is-at-least-32-bytes-long
      COOKIE_SECURE: "false"
      REGISTRATION_MODE: open
      PYTHONPATH: /app
    ports:
      - "8001:8000"
    volumes:
      - ./api:/app
    depends_on:
      db-e2e:
        condition: service_healthy
```

(Bez workera: e2e nie pobiera danych rynkowych z sieci; wycena bierze ceny z migawki XTB.)

- [ ] **Step 2: Syntetyczny eksport**

`api/tests/e2e_fixture.py`:

```python
"""Writes a synthetic XTB export for the web e2e test: `python -m tests.e2e_fixture` (inside the api-e2e container).

A PLN stock bought twice after two deposits, so the dashboard has a staircase of paid-in capital and the position
detail has two lots that agree with the Open Positions snapshot. Values are made up."""
from datetime import datetime
from pathlib import Path

from tests import xtb_factory as xf

OUT = Path(__file__).resolve().parents[1] / ".e2e"
NAME = xf.filename("IKE", "56216965")
FIRST = datetime(2026, 1, 6, 9, 30)
SECOND = datetime(2026, 3, 3, 9, 30)


def build() -> bytes:
    stock = {"instrument": "CD Projekt", "category": "STOCK"}
    return xf.build_report(
        cash=[
            xf.cash_row("IKE deposit", 5000.0, "2001", datetime(2026, 1, 5, 8, 0)),
            xf.buy_row("CDR.PL", "2", "250", -500.0, "2002", FIRST, "881", **stock),
            xf.cash_row("IKE deposit", 3000.0, "2003", datetime(2026, 3, 2, 8, 0)),
            xf.buy_row("CDR.PL", "1", "270", -270.0, "2004", SECOND, "882", **stock),
        ],
        open_rows=[
            xf.summary_row("CDR.PL", "CD Projekt", 3.0, 810.0, 256.67, 40.0, category="STOCK"),
            xf.lot_row("CDR.PL", "881", 2.0, 250.0, FIRST, 270.0, 540.0, 40.0),
            xf.lot_row("CDR.PL", "882", 1.0, 270.0, SECOND, 270.0, 270.0, 0.0),
        ],
    )


def main() -> None:
    OUT.mkdir(exist_ok=True)
    (OUT / NAME).write_bytes(build())
    print(OUT / NAME)


if __name__ == "__main__":
    main()
```

Run (z katalogu repozytorium): `docker compose run --rm api python -m tests.e2e_fixture`
Expected: wypisuje `/app/.e2e/IKE_56216965_2006-01-01_2026-09-26.xlsx`; plik jest w `api/.e2e/` (ignorowany przez git).

Run: `docker compose run --rm api pytest -q`
Expected: PASS jak przed zmianą, jedno istniejące ostrzeżenie (plik nie zaczyna się od `test_`, więc pytest go nie zbiera).

- [ ] **Step 3: Playwright**

`web/playwright.config.ts`:

```ts
import { defineConfig } from "@playwright/test";

export default defineConfig({
  testDir: "./e2e",
  timeout: 90_000,
  expect: { timeout: 15_000 },
  workers: 1,
  reporter: "list",
  globalSetup: "./e2e/global-setup.ts",
  globalTeardown: "./e2e/global-teardown.ts",
  use: {
    baseURL: "http://localhost:5174",
    browserName: "chromium",
    viewport: { width: 390, height: 844 },
    deviceScaleFactor: 2,
    isMobile: true,
    hasTouch: true,
    locale: "pl-PL",
  },
  webServer: {
    command: "npm run dev -- --port 5174 --strictPort",
    url: "http://localhost:5174",
    reuseExistingServer: false,
    env: { API_TARGET: "http://localhost:8001" },
    timeout: 60_000,
  },
});
```

`web/e2e/global-setup.ts`:

```ts
import { execSync } from "node:child_process";
import { resolve } from "node:path";

const REPO = resolve(import.meta.dirname, "../..");
const HEALTH = "http://localhost:8001/api/health";

function run(command: string): void {
  execSync(command, { cwd: REPO, stdio: "inherit" });
}

async function waitForApi(timeoutMs: number): Promise<void> {
  const deadline = Date.now() + timeoutMs;
  while (Date.now() < deadline) {
    try {
      if ((await fetch(HEALTH)).ok) return;
    } catch {
      // not up yet
    }
    await new Promise((r) => setTimeout(r, 1000));
  }
  throw new Error(`API do testów e2e nie odpowiada pod ${HEALTH}.`);
}

/** A fresh database (tmpfs) and API instance for every run, and the synthetic XTB export. */
export default async function globalSetup(): Promise<void> {
  run("docker compose --profile e2e up -d --build db-e2e api-e2e");
  await waitForApi(120_000);
  run("docker compose --profile e2e exec -T api-e2e python -m tests.e2e_fixture");
}
```

`web/e2e/global-teardown.ts`:

```ts
import { execSync } from "node:child_process";
import { resolve } from "node:path";

export default function globalTeardown(): void {
  execSync("docker compose --profile e2e rm -sf db-e2e api-e2e", { cwd: resolve(import.meta.dirname, "../.."), stdio: "inherit" });
}
```

`web/e2e/app.spec.ts`:

```ts
import { expect, test } from "@playwright/test";
import { resolve } from "node:path";

const EXPORT = resolve(import.meta.dirname, "../../api/.e2e/IKE_56216965_2006-01-01_2026-09-26.xlsx");
const SCREENS = resolve(import.meta.dirname, "screens");

test("rejestracja, import eksportu XTB, pulpit, pozycje i szczegóły pozycji", async ({ page }) => {
  await page.goto("/rejestracja");
  await page.getByLabel("E-mail").fill(`e2e-${Date.now()}@portfolio.dev`);
  await page.getByLabel("Hasło").fill("e2e-haslo-12345");
  await page.getByRole("button", { name: "Załóż konto" }).click();

  await expect(page.getByText("Wgraj eksport z XTB, żeby zobaczyć swój portfel.")).toBeVisible();
  await page.getByRole("link", { name: "Wgraj pliki z XTB" }).click();

  await page.getByLabel("Wybierz pliki").setInputFiles(EXPORT);
  await expect(page.getByText(/Zostanie założone konto/)).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/import.png`, fullPage: true });
  await page.getByRole("button", { name: "Zapisz import" }).click();

  await expect(page.getByRole("heading", { name: "Import zapisany" })).toBeVisible();
  await page.getByRole("link", { name: "Zobacz pulpit" }).click();

  await expect(page.getByText("Wartość portfela")).toBeVisible();
  await expect(page.getByRole("img", { name: /Wykres wartości portfela/ })).toBeVisible({ timeout: 45_000 });
  await expect(page.getByText("Przeliczam wycenę…")).toBeHidden({ timeout: 45_000 });
  await page.screenshot({ path: `${SCREENS}/pulpit.png`, fullPage: true });

  await page.getByRole("navigation", { name: "Główna" }).getByRole("link", { name: "Pozycje" }).click();
  await expect(page.getByRole("heading", { name: "Akcje i ETF-y" })).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/pozycje.png`, fullPage: true });

  await page.getByRole("link", { name: /CD Projekt/ }).click();
  await expect(page.getByRole("heading", { name: "CD Projekt" })).toBeVisible();
  await expect(page.getByText("Zgodne z XTB")).toBeVisible();
  await page.screenshot({ path: `${SCREENS}/pozycja.png`, fullPage: true });
});
```

Run (z `web/`, przy istniejącym `.env` w katalogu repozytorium): `npx playwright install chromium` (jednorazowo), potem `npm run e2e`
Expected: `1 passed`; w `web/e2e/screens/` cztery zrzuty (import, pulpit, pozycje, pozycja) w szerokości 390 px. Obejrzyj je i porównaj z makietą (kolory, krój, kwoty, dolny pasek) — rozbieżność wyglądu to błąd do poprawienia w tym zadaniu.

- [ ] **Step 4: README i roadmapa**

`README.md` — dopisz sekcję (po sekcji o uruchomieniu API):

````markdown
## Frontend (`web/`)

Wymaga Node.js 22+ i działającego API (`docker compose up`).

```bash
cd web
npm install
npm run dev        # http://localhost:5173, /api przekierowane do API na :8000
npm test           # testy Vitest
npm run build      # wersja produkcyjna z PWA w web/dist
```

Test e2e (rejestracja → import → pulpit) na osobnej bazie i instancji API (`docker compose --profile e2e`, port 8001),
bez dotykania twoich danych. Wymaga Dockera i pliku `.env`:

```bash
cd web
npx playwright install chromium   # jednorazowo
npm run e2e                       # zrzuty ekranów trafiają do web/e2e/screens/
```

Ikony PWA generuje `npm run icons` z `web/public/icon.svg`. Aplikację na iPhonie (ekran początkowy, service worker
przez HTTPS) sprawdzimy osobno — patrz otwarty punkt w roadmapie.
````

`docs/superpowers/plans/2026-09-26-00-roadmap.md` — w wierszu `| 6a |` zmień kolumnę „Status” na
`✅ zrobiony (`2026-09-28-06a-frontend-foundation.md`)`. Otwarty punkt o teście PWA na iPhonie zostaje bez zmian.

- [ ] **Step 5: Pełna weryfikacja**

Run (z `web/`): `npm test` → Expected: PASS wszystko.
Run: `npm run typecheck && npm run build` → Expected: bez błędów.
Run: `npm run e2e` → Expected: `1 passed`.
Run (z katalogu repozytorium): `docker compose run --rm api pytest -q` → Expected: PASS, jedno istniejące ostrzeżenie.

- [ ] **Step 6: Commit**

```bash
git add docker-compose.yml api/tests/e2e_fixture.py web/playwright.config.ts web/e2e/global-setup.ts \
  web/e2e/global-teardown.ts web/e2e/app.spec.ts README.md docs/superpowers/plans/2026-09-26-00-roadmap.md
git commit -m "test(web): end-to-end registration, XTB import and dashboard on a separate database; docs

Co-Authored-By: <model> <noreply@anthropic.com>"
```
