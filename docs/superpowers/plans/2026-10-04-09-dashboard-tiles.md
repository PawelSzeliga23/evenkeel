# Pulpit z kafelków — plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Pulpit złożony z kafelków, które właściciel układa, dodaje, usuwa i ustawia; jeden układ zapisany na koncie.

**Architecture:** Układ to uporządkowana lista kafelków `{id, kind, size, settings}` w `users.preferences.dashboard`
(walidowana w API). Web renderuje ją w siatce CSS (4/2/2 kolumny; S/M/L zajmują 1/2/4 kolumny), każdy rodzaj to
osobny komponent w `src/dashboard/tiles/`. Tryb edycji trzyma roboczą kopię układu, przeciąganie przez `@dnd-kit`,
zapis przy „Gotowe” przez `PATCH /api/me/preferences`.

**Tech Stack:** FastAPI + pydantic (unia po `kind`), React 19 + TanStack Query, `@dnd-kit/core` 6.3.1,
`@dnd-kit/sortable` 10.0.0, `@dnd-kit/utilities` 3.2.2, Vitest + Testing Library, Playwright.

**Spec:** `docs/superpowers/specs/2026-10-04-09-dashboard-tiles-design.md`

## Global Constraints

- Jeden wspólny układ dla telefonu i komputera; kolejność na telefonie = kolejność listy.
- Rozmiary: S = 1 kolumna, M = 2, L = 4 (komputer, ≥ 1100 px); średni ekran i telefon: 2 kolumny, M i L na całą szerokość.
- Najwyżej 40 kafelków; `id` 1–20 znaków `[A-Za-z0-9_-]`, unikalne.
- Bez zapisanego układu Pulpit wygląda jak przed planem 9 (układ domyślny ze specyfikacji).
- Kolory tylko z `theme.css` / `chart-colors.css` (test 8b pilnuje).
- Teksty po polsku; zależności wpisane dokładnymi wersjami (bez `^`), jak reszta `package.json`.
- Zmiany robocze do „Gotowe”; „Anuluj” wraca do zapisanego; „Przywróć domyślny” zapisuje się dopiero przy „Gotowe”.

## Review Focus

- Zapisany układ z nieznanym rodzajem lub złymi ustawieniami (np. po zmianie wersji) — reszta Pulpitu ma działać, zły kafelek pominięty (`normalize`, Task 2).
- Kafelek wykresu ceny dla waloru, którego już nie ma (sprzedany, konto usunięte) — komunikat „wybierz inny”, nie biały ekran (Task 3).
- Dwa kafelki tego samego rodzaju naraz — bez powtórzonych `id` w DOM i z osobnymi stanami (Task 3).
- Wejście w edycję z innego ekranu (`/?edycja`) i wyjście „Anuluj” po zmianach — zapisany układ nietknięty (Task 4).
- Przeciąganie palcem nie może blokować przewijania strony poza trybem edycji (czujniki tylko w edycji, Task 4).

---

### Task 1: API — układ Pulpitu w preferencjach

**Files:**
- Modify: `api/app/preferences/schemas.py`, `api/app/preferences/router.py`
- Test: `api/tests/test_preferences_api.py`

**Interfaces:**
- Produces: `PreferencesOut.dashboard: DashboardLayout | None`; `PATCH /api/me/preferences` przyjmuje `dashboard` (obiekt albo `null` = domyślny).

- [ ] **Step 1: Testy**

```python
LAYOUT = {"version": 1, "tiles": [
    {"id": "a1", "kind": "summary", "size": "L", "settings": {"fields": ["total_gain", "sharpe", "invested", "income"]}},
    {"id": "b2", "kind": "metric", "size": "S", "settings": {"metric": "xirr"}},
    {"id": "c3", "kind": "price_chart", "size": "M", "settings": {"account_id": 5, "instrument_id": 7, "range": "1y"}},
]}

def test_a_dashboard_layout_is_saved_and_reset(client, login_as):
    anna = login_as("anna@portfolio.dev")
    saved = client.patch("/api/me/preferences", json={"dashboard": LAYOUT}, headers=anna)
    assert saved.status_code == 200 and saved.json()["dashboard"] == LAYOUT
    assert client.get("/api/auth/me", headers=anna).json()["preferences"]["dashboard"] == LAYOUT
    reset = client.patch("/api/me/preferences", json={"dashboard": None}, headers=anna)
    assert reset.json()["dashboard"] is None

def test_a_bad_layout_is_refused(client, login_as):
    anna = login_as("anna@portfolio.dev")
    tile = LAYOUT["tiles"][1]
    bad = [
        {**LAYOUT, "version": 2},
        {"version": 1, "tiles": [{**tile, "kind": "weather"}]},
        {"version": 1, "tiles": [{**tile, "size": "L"}]},                      # metric is S only
        {"version": 1, "tiles": [{**tile, "settings": {"metric": "luck"}}]},
        {"version": 1, "tiles": [{**tile, "settings": {"metric": "xirr", "x": 1}}]},
        {"version": 1, "tiles": [tile, tile]},                                  # repeated id
        {"version": 1, "tiles": [{**tile, "id": f"t{i}"} for i in range(41)]},
    ]
    for layout in bad:
        assert client.patch("/api/me/preferences", json={"dashboard": layout}, headers=anna).status_code == 422
```

- [ ] **Step 2:** `docker compose exec -T api pytest -q tests/test_preferences_api.py` → FAIL.
- [ ] **Step 3: Schematy** — w `schemas.py`:

```python
Metric = Literal["total_gain", "twr_total", "invested", "income", "cash", "day_change", "fees", "profit", "twr", "xirr",
                 "volatility", "sharpe", "max_drawdown", "current_drawdown", "best_day", "worst_day"]
TileId = Annotated[str, Field(pattern=r"^[A-Za-z0-9_-]{1,20}$")]

class _Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")

class SummarySettings(_Settings):
    fields: list[Metric] = Field(min_length=1, max_length=4)
class MetricSettings(_Settings):
    metric: Metric
class ValueChartSettings(_Settings):
    range: ValueRange
class PriceChartSettings(_Settings):
    account_id: Id | None = None
    instrument_id: Id | None = None
    range: PriceRange
class AllocationSettings(_Settings):
    by: Literal["kind", "account", "currency"]
class AnalysisSettings(_Settings):
    metrics: list[Metric] = Field(min_length=1, max_length=6)
    period: AnalysisPeriod
class MoversSettings(_Settings):
    count: Literal[3, 5, 10]
class NoSettings(_Settings):
    pass

def _tile(kind: str, sizes: tuple[str, ...], settings: type[_Settings]) -> type[BaseModel]:
    return create_model(f"{kind.title().replace('_', '')}Tile", __config__=ConfigDict(extra="forbid"),
                        id=(TileId, ...), kind=(Literal[kind], ...), size=(Literal[sizes], ...), settings=(settings, ...))
```

Rodzaje i rozmiary: `summary` (M, L), `metric` (S), `value_chart` (M, L), `price_chart` (M, L), `allocation` (S, L),
`analysis` (M, L), `limits` (M), `movers` (M, L), `holdings`/`income`/`tags`/`simulator`/`review` (M, `NoSettings`).
`Tile = Annotated[Union[...], Field(discriminator="kind")]`;
`DashboardLayout(version: Literal[1], tiles: list[Tile] = Field(max_length=40))` z walidatorem unikalnych `id`.
`PreferencesOut.dashboard: DashboardLayout | None = None`, `PreferencesPatch.dashboard: DashboardLayout | None = None`.
`preferences_of`: zapisany układ, który przestał przechodzić walidację, daje `None` (jak brak).

- [ ] **Step 4: Router** — `null` usuwa klucz (dziś `exclude_none` pomija `None`):

```python
changes = body.model_dump(exclude_unset=True, exclude_none=True)
stored = dict(scope.user.preferences or {})
if "dashboard" in body.model_fields_set and body.dashboard is None:
    stored.pop("dashboard", None)
...
scope.user.preferences = {**stored, **changes}
```

- [ ] **Step 5:** testy zielone; cały `pytest` zielony. **Commit** `feat(api): dashboard layout in preferences`.

### Task 2: Web — model układu i miar

**Files:**
- Create: `web/src/dashboard/layout.ts`, `web/src/dashboard/metrics.ts`, `web/src/dashboard/layout.test.ts`, `web/src/dashboard/metrics.test.ts`
- Modify: `web/src/api/types.ts` (`Preferences.dashboard?: DashboardLayout | null`), `web/src/settings/preferences.ts` (domyślne `dashboard: null`)
- Move: `RANGES`, `rangeFrom`, `ALLOCATION_MODES`, `allocationRows`, `dayMovers` zostają w `screens/dashboard/model.ts` (używane przez kafelki).

**Interfaces:**
- Produces (`layout.ts`):
  - `type TileKind`, `type TileSize = "S" | "M" | "L"`, `interface Tile { id; kind; size; settings }`, `interface DashboardLayout { version: 1; tiles: Tile[] }`
  - `KINDS: Record<TileKind, { name: string; description: string; sizes: TileSize[]; defaults: () => settings }>`
  - `DEFAULT_LAYOUT: DashboardLayout`
  - `normalize(layout: unknown): DashboardLayout` — zły kafelek pominięty, `null`/brak → `DEFAULT_LAYOUT`
  - `addTile(layout, kind, newId = randomId)`: na początek; `removeTile(layout, id)`; `moveTile(layout, id, toIndex)`;
    `updateTile(layout, id, patch)`; `MAX_TILES = 40`
- Produces (`metrics.ts`):
  - `type MetricKey` (16 kluczy jak w API), `METRICS: Record<MetricKey, { label: string; help: string; source: "summary" | "analytics"; value: (s, a) => { value: string | null; kind: "money" | "percent"; note?: string } }>`
  - `METRIC_OPTIONS: { value: MetricKey; label: string }[]`

- [ ] **Step 1: Testy** (`layout.test.ts`):

```ts
it("falls back to the default layout and drops broken tiles", () => {
  expect(normalize(null)).toEqual(DEFAULT_LAYOUT);
  const broken = { version: 1, tiles: [{ id: "a", kind: "weather", size: "M", settings: {} },
    { id: "b", kind: "metric", size: "S", settings: { metric: "sharpe" } }] };
  expect(normalize(broken).tiles.map((t) => t.id)).toEqual(["b"]);
});
it("adds at the start, moves, updates and removes", () => {
  let layout = addTile(DEFAULT_LAYOUT, "metric", "new1");
  expect(layout.tiles[0]).toMatchObject({ id: "new1", kind: "metric", size: "S", settings: { metric: "xirr" } });
  layout = moveTile(layout, "new1", 2);
  expect(layout.tiles[2]!.id).toBe("new1");
  layout = updateTile(layout, "new1", { settings: { metric: "sharpe" } });
  expect(removeTile(layout, "new1").tiles).toEqual(DEFAULT_LAYOUT.tiles);
});
it("the default layout is today's Pulpit", () => {
  expect(DEFAULT_LAYOUT.tiles.map((t) => `${t.kind}:${t.size}`)).toEqual(
    ["summary:L", "value_chart:L", "allocation:L", "analysis:M", "limits:M", "movers:L"]);
});
```

`metrics.test.ts`: wartości z `SUMMARY`/`ANALYTICS` z `test/fixtures` (np. `income` = dywidendy + odsetki,
`xirr` z dopiskiem „rocznie” przy `annualized`, `sharpe` jako liczba bez %).

- [ ] **Step 2:** `npx vitest run src/dashboard` → FAIL. **Step 3:** implementacja. **Step 4:** zielone.
- [ ] **Step 5: Commit** `feat(web): dashboard layout and metrics model`.

### Task 3: Web — kafelki i Pulpit z układu

**Files:**
- Create: `web/src/dashboard/DashboardGrid.tsx` (siatka), `web/src/dashboard/TileFrame.tsx` (ramka, tytuł opcjonalny, stany), `web/src/dashboard/Dashboard.module.css`
  (siatka, ramka, rozmiary), `web/src/dashboard/tiles/{Summary,Metric,ValueChart,PriceChart,Allocation,Analysis,Movers,Cards}Tile.tsx`,
  `web/src/dashboard/tiles/index.tsx` (`TILE_VIEWS: Record<TileKind, (props) => JSX>`), `web/src/dashboard/tiles.test.tsx`
- Modify: `web/src/screens/dashboard/DashboardScreen.tsx` (nagłówek + siatka z `usePreferences().dashboard`),
  karty `AnalyticsCard` (zastąpiona kafelkiem Analizy na Pulpicie; zostaje na ekranie Analiza), `HoldingsCard`,
  `IncomeCard`, `TagsCard`, `SimulatorCard`, `ReviewCard`, `LimitsCard`: tytuł przez `useId()` zamiast stałego `id`;
  prop `fallback?: { loading?: ReactNode; empty?: ReactNode }` zwracany zamiast `null`.

**Interfaces:**
- Consumes: Task 2 (`Tile`, `normalize`, `METRICS`), istniejące `ValueChart`, `PriceSection` (dodać prop `compact?:
  boolean` = bez nagłówka, tytuł z kafelka; `firstBuy` z `positionPrices.first_buy` gdy brak), `allocationRows`, `dayMovers`.
- Produces: `TileView` props `{ tile: Tile; editing: boolean }`; `DashboardGrid({ layout, editing })`.

Dane: kafelki same pobierają przez React Query tymi samymi kluczami co dziś (`keys.summary(accountIds)`,
`keys.analytics(accountIds, period)`, `keys.history(accountIds, null)`, `keys.positions(accountIds)`,
`keys.exposure(...)`), więc kilka kafelków = jedno zapytanie. Kafelek wykresu ceny bez wyboru lub z walorem spoza
`/api/positions` pokazuje „Wybierz walor w ustawieniach kafelka” / „Tego waloru nie ma już w portfelu — wybierz inny”.

- [ ] **Step 1: Testy** (`tiles.test.tsx`, przez `renderApp("/")` z `mockFetch` jak w `dashboard.test.tsx`):
  - bez zapisanego układu Pulpit pokazuje te same sekcje co dziś (istniejący `dashboard.test.tsx` przechodzi bez zmian
    poza zastąpieniem karty Analizy kafelkiem z tymi samymi miarami);
  - układ z `summary.fields = ["total_gain","sharpe","invested","income"]` pokazuje „Sharpe” zamiast „Stopa zwrotu (TWR)”;
  - dwa kafelki `metric` (xirr, sharpe) robią jedno zapytanie `/api/analytics`;
  - `price_chart` z walorem spoza pozycji → komunikat „wybierz inny”; z walorem → wykres i link „Szczegóły”;
  - błąd `/api/analytics` w kafelku → „Ponów”, reszta Pulpitu działa;
  - siatka: kafelek ma `data-size` i `data-kind`.
- [ ] **Step 2:** FAIL. **Step 3:** implementacja (wydzielić z `DashboardScreen` treść sekcji do kafelków bez zmiany
  wyglądu; ramka: `border: 1px solid var(--rule); border-radius: 14px; padding: 16px`).
- [ ] **Step 4:** `npx vitest run` cały zielony, `npx tsc --noEmit` czysty.
- [ ] **Step 5: Commit** `feat(web): Pulpit built from tiles`.

### Task 4: Web — tryb edycji

**Files:**
- Create: `web/src/dashboard/EditBar.tsx`, `web/src/dashboard/AddTileSheet.tsx`, `web/src/dashboard/TileSettings.tsx`,
  `web/src/dashboard/edit.test.tsx`
- Modify: `web/src/dashboard/DashboardGrid.tsx` (`@dnd-kit` gdy `editing`), `DashboardScreen.tsx` (stan edycji,
  `?edycja`), `web/src/shell/Nav.tsx` (link „Edytuj pulpit” `to="/?edycja"` nad Ustawieniami, tylko komputer),
  `web/src/shell/icons.tsx` (`EditIcon`), `web/package.json` (+ `@dnd-kit/core@6.3.1`, `@dnd-kit/sortable@10.0.0`,
  `@dnd-kit/utilities@3.2.2`), `web/src/shell/shell.test.tsx`.

**Interfaces:**
- Consumes: Task 2 (`addTile`, `removeTile`, `moveTile`, `updateTile`, `KINDS`), Task 3 (`DashboardGrid`, `TILE_VIEWS`),
  `useSavePreferences()`.

Zachowanie (ze specyfikacji): telefon — ikonka „Edytuj pulpit” w górnym wierszu obok zębatki; komputer — link w pasku
bocznym. W edycji: pasek „+ Dodaj kafelek · Przywróć domyślny · Anuluj · Gotowe”; kafelek: X („Usuń kafelek <nazwa>”),
„Ustaw” (panel w miejscu: rozmiar gdy > 1, pola rodzaju, „Przesuń wcześniej / później”, „Gotowe”); treść kafelka
`inert`; drżenie wyłączone przy `prefers-reduced-motion`. Czujniki: `PointerSensor {distance: 5}`,
`TouchSensor {delay: 200, tolerance: 5}`, `KeyboardSensor` z `sortableKeyboardCoordinates`; strategia
`rectSortingStrategy`. „Gotowe” → `PATCH {dashboard}` (`null`, gdy układ równa się domyślnemu); błąd zapisu →
komunikat i zostajemy w edycji.

- [ ] **Step 1: Testy** (`edit.test.tsx`):
  - „Edytuj pulpit” → widać „Gotowe”, przy kafelkach „Usuń kafelek …”;
  - „+ Dodaj kafelek” → „Jedna miara” → nowy kafelek na początku; „Ustaw” → wybór „Sharpe” → „Gotowe” wysyła
    `PATCH /api/me/preferences` z `dashboard.tiles[0].settings.metric === "sharpe"`;
  - usunięcie kafelka i „Anuluj” → bez `PATCH`, kafelek wraca;
  - „Przesuń później” zmienia kolejność w wysłanym układzie;
  - wykres ceny dodany → od razu otwarte ustawienia z wyborem waloru z `/api/positions`;
  - `/?edycja` otwiera Pulpit w trybie edycji; link w pasku bocznym ma `href="/?edycja"` i stoi przed Ustawieniami.
- [ ] **Step 2:** FAIL. **Step 3:** `npm install --save-exact @dnd-kit/core@6.3.1 @dnd-kit/sortable@10.0.0 @dnd-kit/utilities@3.2.2`, implementacja.
- [ ] **Step 4:** cały `vitest` zielony, `tsc` czysty, `npm run build` przechodzi.
- [ ] **Step 5: Commit** `feat(web): edit the Pulpit — add, remove, move and set tiles`.

### Task 5: e2e, dokumentacja

**Files:**
- Modify: `web/e2e/*.spec.ts` (nowy test w istniejącym pliku Pulpitu albo `dashboard-tiles.spec.ts`),
  `docs/superpowers/plans/2026-09-26-00-roadmap.md` (wiersz 9), `README.md` (nic, chyba że opis Pulpitu).

- [ ] **Step 1:** e2e: zaloguj → „Edytuj pulpit” → „+ Dodaj kafelek” → „Jedna miara” → „Gotowe” → przeładuj → kafelek jest.
- [ ] **Step 2:** `npm run e2e` zielone (6 testów).
- [ ] **Step 3:** wiersz 9 w roadmapie; **Commit** `test(e2e): dashboard tiles; roadmap: 9 done`.
