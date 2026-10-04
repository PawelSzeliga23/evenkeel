# Plan 9b — kafelki w jednostkach U: plan wykonania

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (właściciel zwolnił z akceptacji planu —
> wykonanie od razu, pytanie dopiero o scalenie). Kroki w formie `- [ ]`.

**Goal:** Kafelki Pulpitu mają na komputerze wysokość w jednostkach U (72 px) wynikającą z rodzaju i wariantu, więc
układają się bez przerw; dochodzą warianty S i siedem nowych rodzajów kafelków.

**Architecture:** `Tile.size` (S/M/L) zastępuje `Tile.variant` (np. `"S2"`, `"M4"`, `"L"`): pierwsza litera to
szerokość, cyfra to stała wysokość w U; wariant bez cyfry ma wysokość liczoną z liczby pól (`heightOf`). Stary zapis
z `size` jest czytany jak nowy (mapowanie w API i w `normalize`), bez migracji bazy. Siatka od 1100 px:
`grid-auto-rows: 72px`, kafelek `grid-row: span var(--u)`.

**Tech Stack:** FastAPI + Pydantic 2 (api), React 19 + TanStack Query + CSS Modules + Vitest + Playwright (web).

**Spec:** `docs/superpowers/specs/2026-10-04-09b-tile-heights-design.md`

## Global Constraints

- 1U = 72 px, odstęp 16 px; kafelek n·U = `n × 72 + (n − 1) × 16` px; tylko od 1100 px (4 kolumny).
- Szerokość: S = 1 kolumna, M = 2, L = 4; poniżej 1100 px dwie kolumny i wysokość z treści.
- Kafelki płyną w kolejności z listy (bez `dense`); nadmiar treści przewija się w kafelku.
- Wysokość rośnie z liczbą pól tylko tam, gdzie właściciel wybiera ich liczbę (tabela „Zasada” w specu).
- Teksty po polsku; liczby jak w XTB (istniejące formatery `formatMoney`, `formatPercent`).
- Bez migracji bazy: układ w `users.preferences.dashboard`, `version: 1`.

## Warianty (jedno źródło prawdy, ten sam zbiór w API i w web)

| kind | warianty | stary `size` → wariant |
|---|---|---|
| summary | S2, M, L | M→M, L→L |
| metric | S1, S2 | S→S2 |
| value_chart | S2, M4, L4, L6 | M→M4, L→L6 |
| price_chart | S2, M5, L6 | M→M5, L→L6 |
| allocation | S2, M4, L4 | S→S2, L→L4 |
| analysis | S, M, L, Lc | M→M, L→Lc |
| limits | S2, M2 | M→M2 |
| movers | S2, M, L | M→M, L→L |
| holdings | S3, M3, L5 | M→M3 |
| income | S2, M2 | M→M2 |
| tags | S2, M3 | M→M3 |
| simulator | S2, M4 | M→M4 |
| review | S2, M4, L4 | M→M4 |
| exposure ★ | S2, M3 | — |
| operations ★ | S2, M, L | — |
| extremes ★ | S2, M, L | — |
| cash ★ | S2, M3 | — |
| bonds ★ | S2, M3 | — |
| savings ★ | S2, M3 | — |
| journal ★ | S2, M3 | — |

Wysokość wariantów bez cyfry (`heightOf`): summary M `2+⌈n/2⌉`, L `2+⌈n/4⌉` (n pól 1–8); analysis S `1+min(n,3)`,
M `1+⌈n/2⌉`, L `1+⌈n/4⌉`, Lc `4+⌈n/4⌉`; movers/operations M `1+⌈n/2⌉`, L `1+⌈n/4⌉` (n = 3/5/10);
extremes M `1+n`, L `1+⌈n/2⌉` (n = 2/3/5 z każdej strony).

Nowe ustawienia: summary.fields 1–8 (dotąd 4); operations `{count: 3|5|10}`; extremes
`{count: 2|3|5, period: "1d"|"1w"|"1m"|"1y"|"ytd"|"all"}`; pozostałe nowe bez ustawień.

## Review Focus

- Zapisany układ z planu 9 (`size`) — po wdrożeniu Pulpit wygląda tak samo, a pierwszy zapis zapisuje już `variant`.
- Analiza S z 4–6 miarami (zmiana wariantu z M na S) — pokazuje pierwsze 3 i ma wysokość 4U, nie gubi zapisu.
- Kafelek w ustawieniach (pełna szerokość) na komputerze — rośnie do treści, nie jest ucięty do 1U.
- Kafelek bez danych (brak obligacji / kont oszczędnościowych / wpisów) — mówi dlaczego, nie stoi pusty.
- Telefon — dwa kafelki S obok siebie, wysokość z treści, bez pustych pasów.

---

### Task 1: API — warianty, stary `size`, nowe rodzaje

**Files:** Modify `api/app/preferences/schemas.py`; Test `api/tests/test_preferences_api.py`.

- [ ] Testy: `LAYOUT` z `variant`; zapis starego układu (`size`) wraca jako `variant` (M→M5 dla price_chart itd.);
  odrzucony zły wariant (`metric` `"M4"`), `size` i `variant` naraz, `summary` z 9 polami; przyjęte nowe rodzaje z
  ustawieniami (`operations` count 5, `extremes` count 3 period "1y", `cash` …).
- [ ] Implementacja: `VARIANTS` i `LEGACY` jak w tabeli; `_Tile` z `model_validator(mode="before")`, który zamienia
  `size` na `variant` (nieznany `size` → zostawia, walidacja odrzuci); `_tile(kind, settings)` bierze warianty z
  `VARIANTS[kind]`; `SummarySettings.fields` max 8; `OperationsSettings`, `ExtremesSettings`.
- [ ] `pytest tests/test_preferences_api.py` zielone; commit `feat(api): 9b tile variants`.

### Task 2: Web — model wariantów

**Files:** Modify `web/src/dashboard/layout.ts`, `web/src/dashboard/layout.test.ts`.

**Produces:** `type TileVariant = string`; `Tile = { id, kind, variant, settings }`; `KINDS[kind].variants:
readonly string[]`; `widthOf(variant): "S"|"M"|"L"`; `heightOf(tile): number`; `dimensionOf(tile): string`
(„M · 4U”); `normalize` mapuje `size` przez `LEGACY`; `addTile(layout, kind, variant?, id?)`;
`updateTile(…, { variant?, settings? })`; `DEFAULT_LAYOUT`: summary L (3U), value_chart L6, allocation M4,
analysis M (2 miary → 2U), limits M2, movers L (5 → 3U) — sumy U w parach się zgadzają.

- [ ] Testy: domyślny układ (`kind:variant`), wysokości z tabeli (Analiza M 2→2U 4→3U 6→4U, L+wykres 4→5U 6→6U,
  summary M 4→4U 8→6U, L 4→3U 8→4U, movers M 3→3U 10→6U, L 10→4U, extremes M 3→4U, L 3→3U, analysis S 6→4U),
  mapowanie starego `size`, odrzucenie złego wariantu, nowe rodzaje z domyślnymi ustawieniami.
- [ ] Implementacja; `npx vitest run src/dashboard/layout.test.ts`; commit.

### Task 3: Siatka w U, ustawienia i dodawanie z wariantami

**Files:** Modify `web/src/dashboard/DashboardGrid.tsx`, `Dashboard.module.css`, `TileSettings.tsx`,
`AddTileSheet.tsx`, `web/src/screens/dashboard/DashboardScreen.tsx`, `web/src/dashboard/edit.test.tsx`.

- [ ] `tileBox` dostaje `data-width`, `data-variant`, `style={{"--u": heightOf(tile)}}`; od 1100 px:
  `.tileGrid { grid-auto-rows: 72px; align-items: stretch }`, `.tileBox { grid-row: span var(--u); overflow: auto }`;
  w edycji tło siatki z liniami co 88 px; kafelek w ustawieniach `grid-row: auto` i siatka z
  `grid-auto-rows: minmax(72px, auto)` (rośnie do treści).
- [ ] Uchwyt: `⠿` + `<span>M · 4U</span>` (wymiar, `aria-hidden`, widoczny od 1100 px).
- [ ] `TileSettings`: wybór wariantu (radio z etykietą „M · 4U” liczoną dla bieżących ustawień, legenda „Wariant (na
  komputerze)”); Analiza S przycina miary do 3 i `MetricChoice max=3`; Wartość portfela: pola 1–8 z „Usuń pole” i
  „+ Dodaj pole”; nowe ustawienia `operations` (Ile operacji) i `extremes` (Ile z każdej strony, Okres).
- [ ] `AddTileSheet`: przy każdym rodzaju przyciski wariantów („Jedna miara S · 1U”); `onAdd(kind, variant)`.
- [ ] Testy edycji zaktualizowane + nowe: dodanie wariantu z arkusza, zmiana wariantu, dodanie pola w Wartości
  portfela zmienia wymiar z „M · 4U” na „M · 5U”. Commit.

### Task 4: Istniejące kafelki dopasowane do wariantów

**Files:** Modify `tiles/FigureTiles.tsx`, `tiles/ChartTiles.tsx`, `tiles/CardTiles.tsx`, `charts/ValueChart.tsx`
(`maxHeight`), `charts/PriceChart.tsx` (`maxHeight`), `screens/positions/PriceSection.tsx` (`compact`, `maxHeight`),
`screens/holdings/HoldingsCard.tsx` (`height`, `labels`), `Dashboard.module.css`, `tiles.test.tsx`.

- [ ] Wartość portfela S2 (kwota + dziś), M (pola po 2), L (pola po 4); Jedna miara S1 (w jednym wierszu);
  Wykres wartości S2 (wartość, zmiana w zakresie, mała linia SVG bez osi) i M4/L4 `maxHeight 190`, L6 `300`;
  Wykres ceny S2 (cena, zmiana od 1. zakupu, mała linia) i M5 `compact`; Alokacja M4 (do 5 pozycji), L4 (2 kolumny);
  Analiza S (1 kolumna, do 3), M (2), L (4), Lc (4 + obsunięcie); Limity S2 (tylko %); Dziś najbardziej S2 (największy
  wzrost i spadek), L (2 kolumny), wiersze zwarte 44 px; Walory S3 (mapa bez podpisów), L5 (duża); Dochód S2 (bilans);
  Tagi S2 (największy tag); Symulator S2 (najlepszy scenariusz i różnica); Przegląd AI S2 (data i liczba sekcji).
- [ ] Testy kafelków: stary `size` w zapisie działa, S-warianty pokazują swoje jedno. Commit.

### Task 5: Nowe rodzaje kafelków

**Files:** Create `web/src/dashboard/tiles/ListTiles.tsx`; Modify `DashboardGrid.tsx` (`TileView`),
`api/endpoints.ts` (`bonds()`), `api/queryKeys.ts` (`bonds`), `tiles.test.tsx`.

- [ ] Ekspozycja walutowa (S2 udział największej waluty obcej; M3 pasek + lista, link `/ekspozycja`);
  Ostatnie operacje (S2 ostatnia; M/L lista n, link `/historia`); Najlepsze i najgorsze (S2 po jednym; M pod sobą,
  L obok siebie; okres z ustawień; link `/analiza/walory`); Gotówka (S2 razem; M3 per konto); Obligacje (S2 wartość
  i najbliższy wykup; M3 lista serii); Konta oszczędnościowe (S2 saldo i stawka; M3 lista z saldem, stawką i
  odsetkami); Dziennik (S2 data i początek ostatniego wpisu; M3 trzy ostatnie, link `/dziennik`). Bez danych —
  `TileNote` z powodem.
- [ ] Testy: każdy nowy rodzaj renderuje dane z fixture i komunikat bez danych. Commit.

### Task 6: Weryfikacja całości

- [ ] e2e: dodanie miary S1, Alokacji S2; zrzut komputera bez przerw; `npx playwright test`.
- [ ] `npm run lint`, `npx tsc -b`, `npx vitest run`, `pytest`, `ruff`, `mypy` zielone; przegląd końcowy (Opus),
  poprawki, pytanie właściciela o scalenie.
