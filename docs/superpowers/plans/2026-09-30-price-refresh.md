# Price Refresh Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: superpowers:executing-plans (the owner chose inline execution). Steps use checkbox (`- [ ]`) syntax.

**Goal:** Prices and NBP rates refresh during the trading day, automatically every 30 minutes and on demand from a button on Pulpit that shows the date and time of the last refresh.

**Architecture:**
- The worker gets an `IntradaySchedule` next to `DailySchedule`. `tick` runs the evening job first, then the intraday job (prices + FX), then the backfill.
- The API gets `POST /api/portfolio/refresh`. It reuses `_update_prices` / `update_fx` / `mark_market_changes` with injected providers, then starts `recompute_in_background`.
- `SummaryOut.prices_refreshed_at` is the latest `price_checked_at` of the user's instruments.
- The web Dashboard shows it with a refresh button.

**Tech Stack:** FastAPI, SQLAlchemy, pytest in docker (`docker compose run --rm api pytest …` from the repo root); React + TanStack Query, Vitest (`npx vitest run` in `web/`).

**Spec:** `docs/superpowers/specs/2026-09-30-price-refresh-design.md`

## Global Constraints

- Intraday window: Mon–Fri, 09:00–22:30 in `market_timezone`, every 30 min. The evening run counts as fresh.
- Manual refresh throttle: 60 s since the latest `price_checked_at` of the user's instruments.
- Response: `{ "refreshed_at": datetime | null, "fetched": bool }`.
- Pulpit label: `formatDayLong(date) + ", " + HH:MM` in local time. The button's name is "Odśwież ceny". Error text: "Nie udało się odświeżyć cen. Spróbuj ponownie."

## Review Focus

- A refresh while the evening run holds instrument row locks must wait, not fail. `update_instrument_prices` already takes `with_for_update`.
- Weekend and after 22:30: no intraday run. Tests use a Saturday and 22:45.
- Double click: the button is disabled while pending, and the server throttle covers other tabs.
- A user without instruments: no button, and the endpoint returns null without fetching.
- Provider down: 200 with `price_error` on the instrument, not a 500.

---

### Task 1: Worker intraday refresh

**Files:** `api/app/config.py`, `api/app/worker.py`, `api/tests/test_worker.py`

- [ ] Tests (fail first):
  - `IntradaySchedule(from 09:00, to 22:30, every 30 min, zone Warsaw).is_due(now, last)`:
    - due on a weekday at 10:00 with `last=None`;
    - not due 20 min after `last`, due 31 min after;
    - not due on Saturday 12:00;
    - not due at 22:45 or at 08:50.
  - `tick` with both schedules:
    - the first tick at 10:00 is "daily" and sets `state.last_intraday`;
    - at 10:05 it is "backfill";
    - at 10:31 it is "intraday": prices are refetched (the fake counts `history` calls) and no CPI is fetched;
    - at 23:00 it is "daily".
- [ ] Implement:
  - `Settings.market_intraday_minutes: int = Field(default=30, ge=5)`, plus `market_intraday_from = "09:00"` and `market_intraday_to = "22:30"` (same pattern as `market_daily_at`).
  - In `worker.py`: an `IntradaySchedule` dataclass (`start`, `end`, `every: timedelta`, `zone`) with `is_due(now, last)`. It is true when the local weekday is < 5, `start <= local time <= end` and (`last is None` or `now - last >= every`).
  - `WorkerState.last_intraday: datetime | None`. The daily branch sets it to `now`.
  - The new branch: `update_all_prices` + `update_fx` → `mark_market_changes` → commit → log → `"intraday"`.
  - `tick(db, providers, schedule, state, now, intraday=None)`: an optional parameter keeps the existing tests.
  - `main` passes an `IntradaySchedule` built from the settings.
- [ ] `docker compose run --rm api pytest tests/test_worker.py -q` → pass. Commit `feat(worker): refresh prices and NBP rates every 30 minutes during the trading day`.

### Task 2: API manual refresh and `prices_refreshed_at`

**Files:** `api/app/market/deps.py` (new), `api/app/portfolio/router.py`, `api/app/portfolio/schemas.py`, `api/app/portfolio/service.py`, `api/tests/test_price_refresh_api.py` (new)

- [ ] Tests (fail first), with `app.dependency_overrides[get_market_providers] = lambda: fake_providers(...)` and the valuation seed (`seed_market`, `seed_holdings`):
  - the refresh returns `fetched: true` and a `refreshed_at`; it fetched only the user's instrument, not another user's instrument; the user is marked stale (`User.valuations_stale_from` not null) or recomputed;
  - a second refresh within 60 s returns `fetched: false` and the same time, without a provider call;
  - a user without instruments gets `refreshed_at: null, fetched: false`;
  - a failing price provider gives 200 and `Instrument.price_error` is set;
  - the summary's `prices_refreshed_at` equals the latest `price_checked_at`.
- [ ] Implement:
  - `app/market/deps.py`: `get_market_providers()` is a generator that yields `build_providers(client)` inside `with make_client() as client`. Move `build_providers` from `worker.py` to `app/market/update.py` (the worker imports it from there).
  - `RefreshOut(BaseModel)`: `refreshed_at: dt.datetime | None; fetched: bool`.
  - `service.prices_refreshed_at(scope) -> datetime | None`: `max(Instrument.price_checked_at)` over `scope.instruments()`. Add it to `portfolio_summary` (both return paths).
  - Router `POST /portfolio/refresh`:
    - load the user's instruments; if there are none → `(None, False)`;
    - if the latest check is less than 60 s ago → `(latest, False)`;
    - else `now = utcnow`, `changed = {}`, `fx_changed = {}`, then `_update_prices(db, providers.prices, instruments, now, changed)` and `update_fx(db, providers.fx, local_today(), fx_changed)`;
    - then `mark_market_changes(db, changed, fx_changed)`, `db.commit()`, `background.add_task(recompute_in_background, sessions, user.id)`, and return `(now, True)`.
  - Rename `_update_prices` to `update_prices` (public now), keeping `update_all_prices` and `backfill_new_instruments` on it.
- [ ] `docker compose run --rm api pytest -q` → all pass. Commit `feat(api): refresh prices on demand and report when they were last refreshed`.

### Task 3: Pulpit refresh button

**Files:** `web/src/api/types.ts`, `web/src/api/endpoints.ts`, `web/src/format/dates.ts`, `web/src/format/format.test.ts`, `web/src/screens/dashboard/DashboardScreen.tsx`, `web/src/screens/dashboard/Dashboard.module.css`, `web/src/shell/icons.tsx`, `web/src/test/fixtures.ts`, `web/src/screens/dashboard/dashboard.test.tsx`

- [ ] Tests (fail first):
  - `formatRefreshed("2026-09-30T12:32:00Z")` gives `formatDayLong` + ", 14:32" (tests run in the TZ Vitest uses; build the expected value from `new Date(iso).getHours()`, not a hard-coded 14);
  - the Dashboard shows the label and a button "Odśwież ceny";
  - clicking POSTs `/api/portfolio/refresh` and refetches the summary;
  - a failed POST shows the alert;
  - with `prices_refreshed_at: null` there is no button and only the date.
- [ ] Implement:
  - `Summary.prices_refreshed_at: string | null` (fixture `SUMMARY` gets `"2026-09-26T20:05:00Z"`);
  - `api.refreshPrices = () => request<{ refreshed_at: string | null; fetched: boolean }>("/api/portfolio/refresh", { method: "POST" })`;
  - `formatRefreshed(iso)` in `dates.ts`;
  - a `RefreshIcon` (circular arrow, 18 px, `currentColor`);
  - in the Dashboard header: `useMutation({ mutationFn: api.refreshPrices, onSuccess: () => queryClient.invalidateQueries({ queryKey: keys.portfolio }) })`, a spinning class while `refresh.isPending || recalculating`, and `role="alert"` on error;
  - CSS: `.refresh` is a 44 px round button with `@keyframes spin`, and `@media (prefers-reduced-motion: reduce) { animation: none }`.
- [ ] `npx tsc -b && npx vitest run` → pass. Check it live. Commit `feat(web): show when prices were refreshed and refresh them from Pulpit`.
- [ ] Roadmap line under "Zgłoszenia właściciela 2026-09-30": "**Zrobione 2026-09-30 — odświeżanie cen:** co 30 min w godzinach sesji i ręcznie z Pulpitu." Commit.
