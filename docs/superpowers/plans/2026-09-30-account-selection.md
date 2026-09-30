# Wybór kilku kont — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The account filter becomes a multi-select with checkboxes, shared and remembered across Pulpit, Ekspozycja, Pozycje (Otwarte, Zamknięte) and Historia, backed by a repeatable `account_id` query parameter in the API.

**Architecture:** The API accepts `?account_id=1&account_id=4` on six endpoints. One `UserScope.account_filter()` checks ownership and turns the list into `frozenset[int] | None`, and the services filter with `in` instead of `==`. The web app keeps one selection in a React context (`AccountSelectionProvider`, mounted inside `RequireAuth`) that is stored in `localStorage` per user. A new `AccountSelect` button with a checkbox panel replaces both `AccountPicker` (select) and `AccountChips`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2, pytest (in docker: `docker compose run --rm api pytest ...` from the repository root). React 19 + TS + Vite, TanStack Query, Vitest + Testing Library (from `web/`: `npx vitest run <file>`; type check `npx tsc -b`), CSS modules.

**Spec:** `docs/superpowers/specs/2026-09-30-account-selection-design.md`

## Global Constraints

- The query parameter keeps the name `account_id` and may repeat. One occurrence works as today; no parameter means the whole portfolio.
- Allowed ids: 1…2³¹−1. Outside that range → 422 `validation_error` (as today).
- Any id not owned by the user → `404 not_found` with the message "Nie znaleziono." (as today). A repeated id counts once.
- Unchanged: position detail (`/api/positions/{account_id}/{instrument_id}`), IKE/IKZE limits, all calculations.
- Service functions take `account_ids: frozenset[int] | None` (`None` = whole portfolio).
- Button label: "Cały portfel" when nothing (or every account) is chosen. Names joined with ", " for 1–2 accounts. `N konta` / `N kont` for 3 and more (via `pluralPl`).
- Panel: "Cały portfel" on top, then the accounts in the `/api/accounts` order. Real `input type="checkbox"` with labels. The button has `aria-expanded`. Esc and a click outside close the panel. A change applies immediately.
- Choosing "Cały portfel", unticking the last account or ticking every account → an empty selection ("Cały portfel").
- Stored under `localStorage` key `portfolio.accounts.<userId>`, as a JSON array. Every read and write sits in `try/catch`. Ids missing from `/api/accounts` are dropped.
- Query keys and API calls take a sorted id list; the request sends a repeated `account_id`.
- All UI text is Polish.

## Review Focus

- A stored selection with an account deleted meanwhile (for example on another tab) must not send that id to the API. Queries wait until `/api/accounts` has answered (`ready`), then the id is dropped. Pinned in Task 4's "drops a deleted account" test.
- Garbage in `localStorage` (not JSON, not an array, strings, zeros, negative numbers) → an empty selection, not a crash. Pinned in Task 2's `readSelection` test.
- `localStorage` that throws (private mode) → the selection still works in memory. Pinned in Task 2's test.
- The same set chosen in a different order must hit the same cache entry (`[4,1]` and `[1,4]` → one key). Pinned in Task 2's `normalizeSelection` test.
- Another user signing in on the same browser must not inherit the first user's selection. The storage key carries the user id and the provider is keyed by the user id. Pinned in Task 2's provider test.

---

### Task 1: API — several accounts in the six filtered endpoints

**Files:**
- Modify: `api/app/scoping.py`
- Modify: `api/app/portfolio/router.py`
- Modify: `api/app/history/router.py`
- Modify: `api/app/portfolio/service.py`
- Modify: `api/app/portfolio/exposure.py`
- Modify: `api/app/portfolio/closed.py`
- Create: `api/tests/test_account_selection_api.py`

**Interfaces:**
- Produces: `AccountIds` (query type) and `UserScope.account_filter(ids: list[int] | None) -> frozenset[int] | None` in `app/scoping.py`. `portfolio_summary(scope, account_ids)`, `portfolio_history(scope, account_ids, start, end)`, `list_positions(scope, account_ids, day)`, `build_positions(scope, inputs, day, account_ids)`, `closed_investments(scope, account_ids, day)`, `currency_exposure(scope, account_ids, start, end)`, each with `account_ids: frozenset[int] | None`.

- [ ] **Step 1: Write the failing tests**

Create `api/tests/test_account_selection_api.py`:

```python
"""Several accounts at once: `?account_id=a&account_id=b` gives the sum (or the union) of the single accounts."""
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Transaction, User
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
ON = {"date": "2026-09-26"}
MONEY = ("value_pln", "market_value_pln", "exit_cost_pln", "cash_pln", "invested_pln")


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        ids = [seed_holdings(db, user_id, instrument_id, number=n) for n in ("1", "2", "3")]
        # the first account sells one of its two units, so it differs from the third one
        db.add(Transaction(account_id=ids[0], instrument_id=instrument_id, type="sell", xtb_type="sell",
                           occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC), amount=Decimal("2550.00"),
                           currency="PLN", external_id="5", comment="", raw={}, quantity=Decimal("1"),
                           price=Decimal("600"), xtb_position_id="777"))
        db.commit()
        valuate(db, user_id)
    foreign = client.post("/api/accounts", json={"name": "Bartka", "kind": "cash"}, headers=bartek).json()["id"]
    return {"anna": anna, "ids": ids, "foreign": foreign}


def _get(client: TestClient, world: dict, url: str, ids: list[int] | None, **params: object) -> dict | list:
    query = {**params, **({"account_id": ids} if ids is not None else {})}
    response = client.get(url, params=query, headers=world["anna"])
    assert response.status_code == 200, response.json()
    return response.json()


def test_summary_of_two_accounts_is_the_sum_of_each(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/portfolio/summary", ids) for ids in ([a], [c], [a, c]))

    for field in MONEY:
        assert Decimal(both[field]) == Decimal(one[field]) + Decimal(other[field]), field
    assert {item["key"] for item in both["by_account"]} == {str(a), str(c)}


def test_no_filter_is_the_whole_portfolio_and_a_repeated_id_counts_once(client: TestClient, world: dict) -> None:
    a, b, c = world["ids"]
    singles = [_get(client, world, "/api/portfolio/summary", [i]) for i in (a, b, c)]
    whole = _get(client, world, "/api/portfolio/summary", None)
    repeated = _get(client, world, "/api/portfolio/summary", [a, a])

    assert Decimal(whole["value_pln"]) == sum(Decimal(s["value_pln"]) for s in singles)
    assert repeated == singles[0]


def test_value_history_of_two_accounts_is_the_daily_sum(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/portfolio/history", ids, **{"from": "2026-09-24"})
                        for ids in ([a], [c], [a, c]))

    summed = {p["date"]: Decimal(p["value_pln"]) for p in one["points"]}
    for point in other["points"]:
        summed[point["date"]] += Decimal(point["value_pln"])
    assert {p["date"]: Decimal(p["value_pln"]) for p in both["points"]} == summed


def test_positions_of_two_accounts_are_both_lists(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/positions", ids, **ON) for ids in ([a], [c], [a, c]))

    def keys(items: list[dict]) -> set[tuple]:
        return {(i["kind"], i["account_id"], i["instrument_id"]) for i in items}

    assert keys(both) == keys(one) | keys(other)
    assert abs(sum(Decimal(i["share_pct"]) for i in both) - 100) <= Decimal("0.05")


def test_exposure_of_two_accounts_adds_up_per_currency(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/portfolio/exposure", ids) for ids in ([a], [c], [a, c]))

    def by_currency(body: dict) -> dict[str, Decimal]:
        return {item["currency"]: Decimal(item["value_pln"]) for item in body["current"]}

    expected = by_currency(one)
    for code, value in by_currency(other).items():
        expected[code] = expected.get(code, Decimal(0)) + value
    assert by_currency(both) == expected


def test_closed_of_two_accounts_lists_the_sales_of_both(client: TestClient, world: dict) -> None:
    a, b, c = world["ids"]
    with_sale, without = _get(client, world, "/api/portfolio/closed", [a]), _get(client, world, "/api/portfolio/closed", [c])
    both = _get(client, world, "/api/portfolio/closed", [a, c])

    assert (len(with_sale["sales"]), len(without["sales"]), len(both["sales"])) == (1, 0, 1)
    assert both["totals"] == with_sale["totals"]
    assert _get(client, world, "/api/portfolio/closed", [b, c])["sales"] == []


def test_operation_history_of_two_accounts_is_both_lists(client: TestClient, world: dict) -> None:
    a, _, c = world["ids"]
    one, other, both = (_get(client, world, "/api/history", ids, limit=200) for ids in ([a], [c], [a, c]))

    assert {i["id"] for i in both["items"]} == {i["id"] for i in one["items"]} | {i["id"] for i in other["items"]}
    assert {i["account_id"] for i in both["items"]} == {a, c}


@pytest.mark.parametrize("url", [
    "/api/portfolio/summary", "/api/portfolio/history", "/api/positions", "/api/portfolio/exposure",
    "/api/portfolio/closed", "/api/history",
])
def test_someone_elses_account_in_the_list_is_404(client: TestClient, world: dict, url: str) -> None:
    response = client.get(url, params={"account_id": [world["ids"][0], world["foreign"]]}, headers=world["anna"])
    assert (response.status_code, response.json()["code"]) == (404, "not_found")


@pytest.mark.parametrize("bad", ["0", str(2**31)])
def test_an_id_out_of_range_is_a_validation_error(client: TestClient, world: dict, bad: str) -> None:
    response = client.get("/api/portfolio/summary", params={"account_id": [world["ids"][0], bad]},
                          headers=world["anna"])
    assert (response.status_code, response.json()["code"]) == (422, "validation_error")
```

- [ ] **Step 2: Run the tests to see them fail**

Run: `docker compose run --rm api pytest tests/test_account_selection_api.py -q`
Expected: FAIL. The two-account tests see only the last id (FastAPI takes one value for an `int` parameter), and the foreign-account tests return 200.

- [ ] **Step 3: Add the shared filter to `app/scoping.py`**

Add the imports `from fastapi import Depends, Path, Query` and `from pydantic import Field`, then below `DbId`:

```python
# Query parameter `account_id`, repeatable: ?account_id=1&account_id=4. Absent = the whole portfolio.
AccountIds = Annotated[list[Annotated[int, Field(ge=1, le=2**31 - 1)]] | None, Query(alias="account_id")]
```

Add the method to `UserScope`, right after `get_account`:

```python
    def account_filter(self, ids: list[int] | None) -> frozenset[int] | None:
        """Several of the user's accounts, each counted once; None for no filter. Someone else's (or a missing)
        account is a 404, like the account itself."""
        if not ids:
            return None
        wanted = frozenset(ids)
        owned = set(self.db.scalars(
            select(Account.id).where(Account.user_id == self.user.id, Account.id.in_(wanted))))
        if owned != wanted:
            raise not_found()
        return wanted
```

- [ ] **Step 4: Use it in the routers**

In `api/app/portfolio/router.py`, delete `AccountFilter` and `_account`, import `AccountIds` from `app.scoping`, and change the five filtered endpoints like this (the others stay as they are):

```python
@router.get("/portfolio/summary", response_model=SummaryOut)
def get_summary(scope: UserScope = Depends(get_scope), account_ids: AccountIds = None) -> SummaryOut:
    return portfolio_summary(scope, scope.account_filter(account_ids))


@router.get("/portfolio/history", response_model=HistoryOut)
def get_history(
    scope: UserScope = Depends(get_scope),
    account_ids: AccountIds = None,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> HistoryOut:
    return portfolio_history(scope, scope.account_filter(account_ids), start, end)


@router.get("/positions", response_model=list[PositionOut])
def get_positions(
    scope: UserScope = Depends(get_scope), account_ids: AccountIds = None, day: DayQuery = None
) -> list[PositionOut]:
    return list_positions(scope, scope.account_filter(account_ids), day or local_today())


@router.get("/portfolio/closed", response_model=ClosedOut)
def get_closed(scope: UserScope = Depends(get_scope), account_ids: AccountIds = None) -> ClosedOut:
    return closed_investments(scope, scope.account_filter(account_ids), local_today())


@router.get("/portfolio/exposure", response_model=ExposureOut)
def get_exposure(
    scope: UserScope = Depends(get_scope),
    account_ids: AccountIds = None,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> ExposureOut:
    return currency_exposure(scope, scope.account_filter(account_ids), start, end)
```

In `api/app/history/router.py`, import `AccountIds` from `app.scoping` and change the account part of `get_history`:

```python
def get_history(
    scope: UserScope = Depends(get_scope),
    account_ids: AccountIds = None,
    type: Annotated[str | None, Query(max_length=30)] = None,  # noqa: A002 — public query name
    ...  # the other parameters unchanged
) -> HistoryPage:
    after = _cursor(cursor) if cursor else None
    accounts = scope.account_filter(account_ids)
    if instrument_id is not None:
        scope.get_instrument(instrument_id)
    items = [
        item for item in history_items(scope, local_today())
        if (accounts is None or item.account_id in accounts)
        and ...  # the other conditions unchanged
    ]
```

- [ ] **Step 5: Filter by a set in the services**

`api/app/portfolio/service.py`:

```python
def _transactions(scope: UserScope, account_ids: frozenset[int] | None, types: tuple[str, ...]) -> list[Transaction]:
    query = scope.transactions().where(Transaction.type.in_(types))
    if account_ids is not None:
        query = query.where(Transaction.account_id.in_(account_ids))
    return list(scope.db.scalars(query).unique())


def _valuations(scope: UserScope, account_ids: frozenset[int] | None) -> Select[tuple[DailyValuation]]:
    query = scope.daily_valuations()
    return query if account_ids is None else query.where(DailyValuation.account_id.in_(account_ids))
```

Then rename the parameter `account_id: int | None` → `account_ids: frozenset[int] | None` in `_daily_totals`, `portfolio_summary`, `portfolio_history`, `_fixed_items`, `build_positions` and `list_positions`, passing it on unchanged. Change the in-memory checks:
- in `_fixed_items`: `(account_ids is None or holding.account_id in account_ids)` and `(account_ids is None or savings.account_id in account_ids)`;
- in `build_positions`: `if account_ids is not None and owner not in account_ids: continue` and `if account_ids is None or owner in account_ids:`.

`position_detail` keeps calling `build_positions(scope, inputs, day, None)`.

`api/app/portfolio/exposure.py`: `currency_exposure(scope, account_ids: frozenset[int] | None, start, end)` and `_valuations(scope, account_ids)`.

`api/app/portfolio/closed.py`: `closed_investments(scope, account_ids: frozenset[int] | None, day)` and `if account_ids is None or sale.account_id in account_ids:`.

Check that nothing else still passes a single id: `grep -rn "account_id: int | None" api/app` should list no portfolio or history function.

- [ ] **Step 6: Run the new and the existing tests**

Run: `docker compose run --rm api pytest tests/test_account_selection_api.py tests/test_portfolio_api.py tests/test_positions_api.py tests/test_exposure_api.py tests/test_closed_api.py tests/test_history_api.py -q`
Expected: PASS. The old single-account tests pass unchanged, because one `account_id` still works. `tests/test_closed_api.py` calls `closed_investments(..., None, ...)`, which is still valid.

Then the full suite: `docker compose run --rm api pytest -q`. Expected: all pass (568 before this task, plus the new ones).

- [ ] **Step 7: Commit**

```bash
git add api/app/scoping.py api/app/portfolio api/app/history/router.py api/tests/test_account_selection_api.py
git commit -m "feat(api): filter the portfolio, positions, exposure, closed and history by several accounts"
```

---

### Task 2: Web — repeated query values and the shared, remembered selection

**Files:**
- Modify: `web/src/api/client.ts` (the `Query` type and `withQuery`)
- Modify: `web/src/api/client.test.ts`
- Create: `web/src/accounts/selection.ts` (pure helpers and storage)
- Create: `web/src/accounts/AccountSelection.tsx` (provider and hook)
- Create: `web/src/accounts/selection.test.tsx`
- Modify: `web/src/auth/RequireAuth.tsx` (mount the provider)
- Modify: `web/src/test/setup.ts` (clear `localStorage` after each test)

**Interfaces:**
- Produces:
  - `request()` accepts `query` values of type `readonly number[]`, sent as one `key=value` pair per element.
  - From `web/src/accounts/selection.ts`:
    - `normalizeSelection(ids: readonly number[], known: readonly number[] | null): number[]`
    - `toggleAccount(value: readonly number[], id: number, known: readonly number[]): number[]`
    - `selectionLabel(value: readonly number[], accounts: readonly Account[]): string`
    - `storageKey(userId: number): string`
    - `readSelection(userId: number): number[]`
    - `writeSelection(userId: number, ids: readonly number[]): void`
  - From `web/src/accounts/AccountSelection.tsx`:
    - `AccountSelectionProvider({ userId, children })`
    - `useAccountSelection(): [ids: number[], setIds: (ids: readonly number[]) => void, ready: boolean]`
    - `ids` is sorted and holds known accounts only. `ready` is false only while a non-empty stored selection waits for `/api/accounts`.

- [ ] **Step 1: Write the failing client test**

Add to `describe("request", ...)` in `web/src/api/client.test.ts`:

```ts
  it("repeats a parameter for each value of a list and leaves out an empty list", async () => {
    handler = () => json(200, { ok: true });

    await request("/api/positions", { query: { account_id: [1, 4], date: "2026-09-26" } });
    await request("/api/positions", { query: { account_id: [] } });

    expect(calls[0]!.url).toBe("/api/positions?account_id=1&account_id=4&date=2026-09-26");
    expect(calls[1]!.url).toBe("/api/positions");
  });
```

- [ ] **Step 2: Run it to see it fail**

Run (from `web/`): `npx vitest run src/api/client.test.ts`
Expected: FAIL. The URL has `account_id=1%2C4`.

- [ ] **Step 3: Support lists in `withQuery`**

In `web/src/api/client.ts`:

```ts
type Query = Record<string, string | number | readonly number[] | null | undefined>;
```

```ts
function withQuery(path: string, query: Query | undefined): string {
  const params = new URLSearchParams();
  for (const [key, value] of Object.entries(query ?? {})) {
    if (Array.isArray(value)) for (const item of value) params.append(key, String(item));
    else if (value !== null && value !== undefined && value !== "") params.set(key, String(value));
  }
  const text = params.toString();
  return text ? `${path}?${text}` : path;
}
```

Run `npx vitest run src/api/client.test.ts`. Expected: PASS.

- [ ] **Step 4: Write the failing selection tests**

Add to `web/src/test/setup.ts`, inside the existing `afterEach`:

```ts
  try { localStorage.clear(); } catch { /* storage unavailable */ }
```

Create `web/src/accounts/selection.test.tsx`:

```tsx
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import type { Account } from "../api/types";
import { createQueryClient } from "../providers";
import { ACCOUNTS } from "../test/fixtures";
import { mockFetch } from "../test/render";
import { AccountSelectionProvider, useAccountSelection } from "./AccountSelection";
import { normalizeSelection, readSelection, selectionLabel, storageKey, toggleAccount, writeSelection } from "./selection";

const THREE = [{ id: 1, name: "IKE" }, { id: 2, name: "XTB" }, { id: 4, name: "Oszczędności" }] as Account[];
const FIVE = [1, 2, 3, 4, 5].map((id) => ({ id, name: `K${id}` })) as Account[];

describe("selection helpers", () => {
  it("sorts, removes repeats and unknown accounts, and treats every account as none", () => {
    expect(normalizeSelection([4, 1, 4], [1, 2, 4])).toEqual([1, 4]);
    expect(normalizeSelection([1, 9], [1, 2, 4])).toEqual([1]);
    expect(normalizeSelection([4, 2, 1], [1, 2, 4])).toEqual([]);
    expect(normalizeSelection([9], [1, 2])).toEqual([]);
    expect(normalizeSelection([4, 1], null)).toEqual([1, 4]); // accounts not known yet: keep what is stored
  });

  it("ticks and unticks accounts; the last one off or the last one on is the whole portfolio", () => {
    expect(toggleAccount([], 2, [1, 2, 4])).toEqual([2]);
    expect(toggleAccount([2], 1, [1, 2, 4])).toEqual([1, 2]);
    expect(toggleAccount([1, 2], 4, [1, 2, 4])).toEqual([]);
    expect(toggleAccount([2], 2, [1, 2, 4])).toEqual([]);
  });

  it("describes the choice on the button", () => {
    expect(selectionLabel([], THREE)).toBe("Cały portfel");
    expect(selectionLabel([4], THREE)).toBe("Oszczędności");
    expect(selectionLabel([1, 4], THREE)).toBe("IKE, Oszczędności");
    expect(selectionLabel([1, 2, 3], FIVE)).toBe("3 konta");
    expect(selectionLabel([1, 2, 3, 4], [...FIVE, { id: 6, name: "K6" } as Account])).toBe("4 konta");
    expect(selectionLabel([1, 2, 3, 4, 5], [...FIVE, { id: 6, name: "K6" } as Account])).toBe("5 kont");
  });

  it("remembers the choice per user and ignores anything that is not a list of ids", () => {
    writeSelection(7, [1, 4]);
    expect(localStorage.getItem(storageKey(7))).toBe("[1,4]");
    expect(readSelection(7)).toEqual([1, 4]);
    expect(readSelection(8)).toEqual([]);
    for (const junk of ["nie json", "{\"a\":1}", "[\"1\",2]", "[0,-3,1.5]", "null"]) {
      localStorage.setItem(storageKey(7), junk);
      expect(readSelection(7)).toEqual([]);
    }
  });

  it("works without storage (private mode)", () => {
    vi.spyOn(Storage.prototype, "getItem").mockImplementation(() => { throw new Error("blocked"); });
    vi.spyOn(Storage.prototype, "setItem").mockImplementation(() => { throw new Error("blocked"); });
    expect(readSelection(7)).toEqual([]);
    expect(() => writeSelection(7, [1])).not.toThrow();
    vi.restoreAllMocks();
  });
});

function Probe() {
  const [ids, setIds, ready] = useAccountSelection();
  return (
    <>
      <output>{ready ? `ready:${ids.join(",")}` : "waiting"}</output>
      <button type="button" onClick={() => setIds([2, 1, 1])}>wybierz</button>
    </>
  );
}

function renderProbe(userId: number, accounts: () => unknown = () => ACCOUNTS) {
  mockFetch([{ path: "/api/accounts", respond: accounts }]);
  const client = createQueryClient({ test: true });
  const view = (id: number) => (
    <QueryClientProvider client={client}>
      <AccountSelectionProvider key={id} userId={id}><Probe /></AccountSelectionProvider>
    </QueryClientProvider>
  );
  const utils = render(view(userId));
  return { ...utils, rerenderFor: (id: number) => utils.rerender(view(id)) };
}

describe("shared selection", () => {
  it("starts with the whole portfolio and is ready at once", () => {
    renderProbe(7);
    expect(screen.getByRole("status")).toHaveTextContent("ready:");
  });

  it("stores a normalized choice and restores it for the same user only", async () => {
    const { rerenderFor, unmount } = renderProbe(7, () => [...ACCOUNTS, { ...ACCOUNTS[0]!, id: 3, name: "Trzecie" }]);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("ready:"));
    await userEvent.click(screen.getByRole("button", { name: "wybierz" }));
    expect(screen.getByRole("status")).toHaveTextContent("ready:1,2");
    expect(localStorage.getItem(storageKey(7))).toBe("[1,2]");

    rerenderFor(8);
    expect(screen.getByRole("status")).toHaveTextContent("ready:");
    unmount();

    renderProbe(7, () => [...ACCOUNTS, { ...ACCOUNTS[0]!, id: 3, name: "Trzecie" }]);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("ready:1,2"));
  });

  it("waits for the account list before using a stored choice and drops a deleted account", async () => {
    writeSelection(7, [1, 9]);
    let answer: (value: unknown) => void = () => {};
    renderProbe(7, () => new Promise((resolve) => { answer = resolve; }));
    expect(screen.getByRole("status")).toHaveTextContent("waiting");
    answer(ACCOUNTS);
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("ready:1"));
  });

  it("uses the stored choice when the account list cannot be loaded", async () => {
    writeSelection(7, [1]);
    renderProbe(7, () => new Response(null, { status: 500 }));
    await waitFor(() => expect(screen.getByRole("status")).toHaveTextContent("ready:1"));
  });
});
```

(`<output>` has the implicit ARIA role `status`.)

- [ ] **Step 5: Run them to see them fail**

Run: `npx vitest run src/accounts/selection.test.tsx`
Expected: FAIL. The modules `./selection` and `./AccountSelection` do not exist.

- [ ] **Step 6: Write `web/src/accounts/selection.ts`**

```ts
/** The account filter shared by every screen: a sorted list of account ids, [] = the whole portfolio. */
import type { Account } from "../api/types";
import { pluralPl } from "../format/plural";

export const ALL_LABEL = "Cały portfel";

const isId = (value: unknown): value is number => Number.isInteger(value) && (value as number) > 0;

/** Sorted, without repeats, only accounts that still exist; choosing every account is the same as none. */
export function normalizeSelection(ids: readonly number[], known: readonly number[] | null): number[] {
  const unique = [...new Set(ids)].filter(isId);
  const kept = known === null ? unique : unique.filter((id) => known.includes(id));
  kept.sort((a, b) => a - b);
  return known !== null && known.length > 0 && kept.length === known.length ? [] : kept;
}

export function toggleAccount(value: readonly number[], id: number, known: readonly number[]): number[] {
  const next = value.includes(id) ? value.filter((v) => v !== id) : [...value, id];
  return normalizeSelection(next, known);
}

export function selectionLabel(value: readonly number[], accounts: readonly Account[]): string {
  const chosen = accounts.filter((account) => value.includes(account.id));
  if (chosen.length === 0) return ALL_LABEL;
  if (chosen.length <= 2) return chosen.map((account) => account.name).join(", ");
  return `${chosen.length} ${pluralPl(chosen.length, "konto", "konta", "kont")}`;
}

export const storageKey = (userId: number) => `portfolio.accounts.${userId}`;

export function readSelection(userId: number): number[] {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(storageKey(userId)) ?? "[]");
    return Array.isArray(parsed) && parsed.every(isId) ? normalizeSelection(parsed, null) : [];
  } catch {
    return [];
  }
}

export function writeSelection(userId: number, ids: readonly number[]): void {
  try {
    localStorage.setItem(storageKey(userId), JSON.stringify(ids));
  } catch {
    // private mode or full storage: the choice lives in memory only
  }
}
```

Check that `pluralPl` is exported from `web/src/format/plural.ts` (it is). If `web/src/format/index.ts` re-exports it, importing from `../format` also works; keep the style of nearby files.

- [ ] **Step 7: Write `web/src/accounts/AccountSelection.tsx`**

```tsx
import { useQuery } from "@tanstack/react-query";
import { createContext, useCallback, useContext, useMemo, useState, type ReactNode } from "react";
import { api } from "../api/endpoints";
import { keys } from "../api/queryKeys";
import { normalizeSelection, readSelection, writeSelection } from "./selection";

type Selection = [ids: number[], setIds: (ids: readonly number[]) => void, ready: boolean];

const SelectionContext = createContext<Selection | null>(null);

/** One account choice for the whole signed-in app, remembered in this browser per user. */
export function AccountSelectionProvider({ userId, children }: { userId: number; children: ReactNode }) {
  const accounts = useQuery({ queryKey: keys.accounts, queryFn: api.accounts });
  const [stored, setStored] = useState(() => readSelection(userId));
  const known = useMemo(() => accounts.data?.map((account) => account.id) ?? null, [accounts.data]);
  const ids = useMemo(() => normalizeSelection(stored, known), [stored, known]);
  // A stored choice may name an account deleted meanwhile: wait for the list before asking the API with it.
  const ready = stored.length === 0 || known !== null || accounts.isError;
  const setIds = useCallback((next: readonly number[]) => {
    const clean = normalizeSelection(next, known);
    setStored(clean);
    writeSelection(userId, clean);
  }, [known, userId]);
  const value = useMemo<Selection>(() => [ids, setIds, ready], [ids, setIds, ready]);
  return <SelectionContext.Provider value={value}>{children}</SelectionContext.Provider>;
}

export function useAccountSelection(): Selection {
  const selection = useContext(SelectionContext);
  if (!selection) throw new Error("useAccountSelection needs AccountSelectionProvider");
  return selection;
}
```

- [ ] **Step 8: Mount the provider for the signed-in user**

In `web/src/auth/RequireAuth.tsx`, import `AccountSelectionProvider` from `../accounts/AccountSelection` and replace the last line of `RequireAuth`:

```tsx
  return (
    <AccountSelectionProvider key={state.user.id} userId={state.user.id}>
      <Outlet />
    </AccountSelectionProvider>
  );
```

- [ ] **Step 9: Run the tests and the type check**

Run: `npx vitest run src/accounts src/api/client.test.ts` and then `npx tsc -b && npx vitest run`
Expected: all pass. The screens do not use the hook yet. The provider's extra `/api/accounts` request is shared with the screens' own (same query key); in tests without that route it gets a 404, which the provider treats as "ready".

- [ ] **Step 10: Commit**

```bash
git add web/src/api/client.ts web/src/api/client.test.ts web/src/accounts web/src/auth/RequireAuth.tsx web/src/test/setup.ts
git commit -m "feat(web): one remembered account selection for the whole app, and repeated query values"
```

---

### Task 3: Web — the `AccountSelect` checkbox control

**Files:**
- Modify: `web/src/ui/AccountPicker.tsx` (add `AccountSelect`; the old components stay until Task 4)
- Modify: `web/src/ui/ui.module.css` (styles `.select*`)
- Modify: `web/src/ui/ui.test.tsx`

**Interfaces:**
- Consumes: `selectionLabel`, `toggleAccount`, `ALL_LABEL` from `web/src/accounts/selection.ts`.
- Produces: `AccountSelect({ accounts: Account[]; value: readonly number[]; onChange: (ids: number[]) => void })`. The button's accessible name is `Konta: <label>`, e.g. "Konta: Cały portfel". The panel is `role="group"`, named "Wybór kont", with checkboxes named "Cały portfel" and each account name.

- [ ] **Step 1: Write the failing tests**

In `web/src/ui/ui.test.tsx`, add `AccountSelect` to the import from `./AccountPicker` and add inside `describe("controls", ...)`:

```tsx
  it("shows the choice on a button and opens checkboxes for the accounts", async () => {
    const onChange = vi.fn();
    render(<AccountSelect accounts={THREE} value={[]} onChange={onChange} />);
    const button = screen.getByRole("button", { name: "Konta: Cały portfel" });
    expect(button).toHaveAttribute("aria-expanded", "false");

    await userEvent.click(button);
    expect(button).toHaveAttribute("aria-expanded", "true");
    const panel = screen.getByRole("group", { name: "Wybór kont" });
    expect(within(panel).getAllByRole("checkbox").map((c) => c.getAttribute("aria-label") ?? c.parentElement!.textContent))
      .toEqual(["Cały portfel", "IKE", "XTB", "Oszczędności"]);
    expect(screen.getByRole("checkbox", { name: "Cały portfel" })).toBeChecked();

    await userEvent.click(screen.getByRole("checkbox", { name: "Oszczędności" }));
    expect(onChange).toHaveBeenLastCalledWith([4]);
    expect(button).toHaveAttribute("aria-expanded", "true"); // stays open for more ticks
  });

  it("adds, removes and clears accounts", async () => {
    const onChange = vi.fn();
    render(<AccountSelect accounts={THREE} value={[1, 4]} onChange={onChange} />);
    expect(screen.getByRole("button", { name: "Konta: IKE, Oszczędności" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /^Konta:/ }));

    expect(screen.getByRole("checkbox", { name: "IKE" })).toBeChecked();
    expect(screen.getByRole("checkbox", { name: "Cały portfel" })).not.toBeChecked();
    await userEvent.click(screen.getByRole("checkbox", { name: "XTB" }));
    expect(onChange).toHaveBeenLastCalledWith([]); // every account ticked = the whole portfolio
    await userEvent.click(screen.getByRole("checkbox", { name: "IKE" }));
    expect(onChange).toHaveBeenLastCalledWith([4]);
    await userEvent.click(screen.getByRole("checkbox", { name: "Cały portfel" }));
    expect(onChange).toHaveBeenLastCalledWith([]);
  });

  it("closes on Escape and on a click outside", async () => {
    render(<><AccountSelect accounts={THREE} value={[]} onChange={() => {}} /><p>obok</p></>);
    const button = screen.getByRole("button", { name: "Konta: Cały portfel" });

    await userEvent.click(button);
    await userEvent.keyboard("{Escape}");
    expect(screen.queryByRole("group", { name: "Wybór kont" })).not.toBeInTheDocument();
    expect(button).toHaveFocus();

    await userEvent.click(button);
    await userEvent.click(screen.getByText("obok"));
    expect(screen.queryByRole("group", { name: "Wybór kont" })).not.toBeInTheDocument();
  });
```

Add near the top of the file (next to `ACCOUNTS`), and add `within` to the `@testing-library/react` import:

```tsx
const THREE = [{ id: 1, name: "IKE" }, { id: 2, name: "XTB" }, { id: 4, name: "Oszczędności" }] as Account[];
```

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run src/ui/ui.test.tsx`
Expected: FAIL. `AccountSelect` is not exported.

- [ ] **Step 3: Write `AccountSelect`**

Add to `web/src/ui/AccountPicker.tsx`, with these imports at the top:

```tsx
import { useEffect, useId, useRef, useState } from "react";
import { ALL_LABEL, selectionLabel, toggleAccount } from "../accounts/selection";
```

```tsx
/** The account filter: a button describing the choice, opening a panel of checkboxes. */
export function AccountSelect({
  accounts, value, onChange,
}: { accounts: Account[]; value: readonly number[]; onChange: (ids: number[]) => void }) {
  const [open, setOpen] = useState(false);
  const root = useRef<HTMLDivElement>(null);
  const button = useRef<HTMLButtonElement>(null);
  const panelId = useId();
  const known = accounts.map((account) => account.id);
  const label = selectionLabel(value, accounts);

  useEffect(() => {
    if (!open) return;
    const onPointer = (event: PointerEvent) => {
      if (!root.current?.contains(event.target as Node)) setOpen(false);
    };
    const onKey = (event: KeyboardEvent) => {
      if (event.key !== "Escape") return;
      setOpen(false);
      button.current?.focus();
    };
    document.addEventListener("pointerdown", onPointer);
    document.addEventListener("keydown", onKey);
    return () => {
      document.removeEventListener("pointerdown", onPointer);
      document.removeEventListener("keydown", onKey);
    };
  }, [open]);

  return (
    <div className={styles.select} ref={root}>
      <button
        ref={button} type="button" className={styles.selectButton} aria-label={`Konta: ${label}`}
        aria-expanded={open} aria-controls={panelId} onClick={() => setOpen((was) => !was)}
      >
        <span className={styles.selectLabel}>{label}</span>
        <svg viewBox="0 0 12 12" aria-hidden="true">
          <path d="M3 4.5 6 7.5 9 4.5" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
        </svg>
      </button>
      {open && (
        <div id={panelId} className={styles.selectPanel} role="group" aria-label="Wybór kont">
          <label className={styles.selectOption}>
            <input type="checkbox" checked={value.length === 0} onChange={() => onChange([])} />
            {ALL_LABEL}
          </label>
          {accounts.map((account) => (
            <label key={account.id} className={styles.selectOption}>
              <input type="checkbox" checked={value.includes(account.id)}
                onChange={() => onChange(toggleAccount(value, account.id, known))} />
              {account.name}
            </label>
          ))}
        </div>
      )}
    </div>
  );
}
```

- [ ] **Step 4: Style it**

Add to `web/src/ui/ui.module.css`, after the `.picker` rules. It uses the existing tokens and matches the pill look of `.picker`:

```css
.select { position: relative; display: inline-flex; max-width: 100%; }
.selectButton {
  display: inline-flex; align-items: center; gap: 8px; max-width: 100%; min-height: 44px; padding: 0 14px;
  background: var(--slab); border: 1px solid var(--rule); border-radius: 999px; color: var(--ink);
  font: inherit; font-weight: 500; font-size: 14px; cursor: pointer;
}
.selectButton[aria-expanded="true"] { border-color: rgba(240, 164, 58, .45); }
.selectButton svg { flex: none; width: 12px; height: 12px; }
.selectLabel { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
.selectPanel {
  position: absolute; top: calc(100% + 6px); left: 0; z-index: 20; display: grid;
  min-width: 220px; max-width: calc(100vw - 32px); max-height: 60vh; overflow-y: auto; padding: 6px;
  background: var(--slab); border: 1px solid var(--rule); border-radius: 12px; box-shadow: 0 12px 32px rgba(0, 0, 0, .45);
}
.selectOption {
  display: flex; align-items: center; gap: 10px; min-height: 44px; padding: 0 10px; border-radius: 8px;
  color: var(--ink); font-size: 14px; cursor: pointer;
}
.selectOption:hover { background: var(--amber-soft); }
.selectOption input { width: 18px; height: 18px; margin: 0; accent-color: var(--amber); }
```

- [ ] **Step 5: Run the tests**

Run: `npx vitest run src/ui/ui.test.tsx` and then `npx tsc -b`
Expected: PASS. If the checkbox-order assertion in the first test does not read the label text as written, use `within(panel).getAllByRole("checkbox").map((c) => c.closest("label")!.textContent)` instead. That is the intent: the visible label text in that order.

- [ ] **Step 6: Commit**

```bash
git add web/src/ui/AccountPicker.tsx web/src/ui/ui.module.css web/src/ui/ui.test.tsx
git commit -m "feat(web): AccountSelect — choose several accounts with checkboxes"
```

---

### Task 4: Web — every filtered screen uses the shared selection

**Files:**
- Modify: `web/src/api/types.ts` (`HistoryFilters`)
- Modify: `web/src/api/endpoints.ts`
- Modify: `web/src/api/queryKeys.ts`
- Modify: `web/src/screens/dashboard/DashboardScreen.tsx`
- Modify: `web/src/screens/exposure/ExposureScreen.tsx`
- Modify: `web/src/screens/positions/PositionsScreen.tsx`
- Modify: `web/src/screens/positions/ClosedView.tsx`
- Modify: `web/src/screens/history/HistoryScreen.tsx`
- Modify: `web/src/ui/AccountPicker.tsx` (remove `AccountPicker` and `AccountChips`)
- Modify: `web/src/ui/ui.module.css` (remove `.picker` and `.chips`)
- Modify tests: `web/src/ui/ui.test.tsx`, `web/src/screens/dashboard/dashboard.test.tsx`, `web/src/screens/positions/positions.test.tsx`, `web/src/screens/positions/closed.test.tsx`, `web/src/screens/history/history.test.tsx`, and `web/src/screens/exposure/exposure.test.tsx` if it picks an account
- Create: `web/src/screens/account-selection.test.tsx`
- Modify: `docs/superpowers/plans/2026-09-26-00-roadmap.md`

**Interfaces:**
- Consumes: `useAccountSelection()` (Task 2), `AccountSelect` (Task 3), list-valued `query` (Task 2).
- Produces:
  - `api.summary(ids: readonly number[])`, `api.history(ids, from)`, `api.exposure(ids, day)`, `api.exposureHistory(ids, from)`, `api.closed(ids)` and `api.positions(ids)`.
  - `HistoryFilters.account_ids: number[]`.
  - `keys.summary(ids)`, `keys.history(ids, from)`, `keys.exposure(ids, day)`, `keys.exposureHistory(ids, from)`, `keys.closed(ids)` and `keys.positions(ids)`, each with `ids: readonly number[]`.

- [ ] **Step 1: Write the failing cross-screen tests**

Create `web/src/screens/account-selection.test.tsx`:

```tsx
import { screen, waitFor } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { storageKey, writeSelection } from "../accounts/selection";
import { ACCOUNTS, EXPOSURE, HISTORY, LIMITS, POSITIONS, SUMMARY } from "../test/fixtures";
import { SIGNED_IN, USER, mockFetch, renderApp, type MockRoute } from "../test/render";

const THREE = [...ACCOUNTS, { ...ACCOUNTS[0]!, id: 4, name: "Oszczędności", kind: "savings" as const, broker: null, external_account_number: null }];

function routes(accounts: () => unknown = () => THREE): MockRoute[] {
  return [
    ...SIGNED_IN,
    { path: "/api/accounts", respond: accounts },
    { path: "/api/portfolio/summary", respond: () => SUMMARY },
    { path: "/api/portfolio/history", respond: () => HISTORY },
    { path: "/api/portfolio/exposure", respond: () => EXPOSURE },
    { path: "/api/positions", respond: () => POSITIONS },
    { path: "/api/portfolio/limits", respond: () => LIMITS },
  ];
}

const urls = (fetchMock: { mock: { calls: unknown[][] } }) => fetchMock.mock.calls.map(([url]) => String(url));

describe("one account selection for the whole app", () => {
  it("asks the API for the ticked accounts and keeps them from Pulpit to Pozycje", async () => {
    const fetchMock = mockFetch(routes());
    const { user } = renderApp("/");

    await user.click(await screen.findByRole("button", { name: "Konta: Cały portfel" }));
    await user.click(screen.getByRole("checkbox", { name: "IKE" }));
    await user.click(screen.getByRole("checkbox", { name: "Oszczędności" }));
    await waitFor(() => expect(urls(fetchMock)).toContain("/api/portfolio/summary?account_id=1&account_id=4"));
    expect(localStorage.getItem(storageKey(USER.id))).toBe("[1,4]");

    await user.keyboard("{Escape}");
    await user.click(screen.getAllByRole("link", { name: "Pozycje" })[0]!);
    expect(await screen.findByRole("button", { name: "Konta: IKE, Oszczędności" })).toBeInTheDocument();
    await waitFor(() => expect(urls(fetchMock)).toContain("/api/positions?account_id=1&account_id=4"));
  });

  it("starts with the remembered choice", async () => {
    writeSelection(USER.id, [2]);
    const fetchMock = mockFetch(routes());
    renderApp("/");

    expect(await screen.findByRole("button", { name: "Konta: XTB" })).toBeInTheDocument();
    await waitFor(() => expect(urls(fetchMock)).toContain("/api/portfolio/summary?account_id=2"));
    expect(urls(fetchMock).filter((u) => u.startsWith("/api/portfolio/summary"))).toEqual(["/api/portfolio/summary?account_id=2"]);
  });

  it("drops a deleted account without asking the API about it", async () => {
    writeSelection(USER.id, [1, 9]);
    const fetchMock = mockFetch(routes());
    renderApp("/");

    expect(await screen.findByRole("button", { name: "Konta: IKE" })).toBeInTheDocument();
    await waitFor(() => expect(urls(fetchMock)).toContain("/api/portfolio/summary?account_id=1"));
    expect(urls(fetchMock).some((u) => u.includes("account_id=9"))).toBe(false);
  });
});
```

(If the `Account` type differs from these literal fields, adjust `THREE`'s third entry to satisfy `tsc`. Only `id` and `name` matter to the test.)

- [ ] **Step 2: Run them to see them fail**

Run: `npx vitest run src/screens/account-selection.test.tsx`
Expected: FAIL. There is no button named "Konta: Cały portfel" yet.

- [ ] **Step 3: Lists in the API layer**

`web/src/api/types.ts`:

```ts
export interface HistoryFilters { account_ids: number[]; type: string | null; from: IsoDate | null; to: IsoDate | null; q: string }
```

`web/src/api/endpoints.ts`, replacing the matching lines:

```ts
  entries: (filters: HistoryFilters, cursor: string | null) =>
    request<HistoryPage>("/api/history", {
      query: { account_id: filters.account_ids, type: filters.type, from: filters.from, to: filters.to, q: filters.q, cursor },
    }),
```

```ts
  summary: (ids: readonly number[]) => request<Summary>("/api/portfolio/summary", { query: { account_id: ids } }),
  history: (ids: readonly number[], from: IsoDate | null) =>
    request<History>("/api/portfolio/history", { query: { account_id: ids, from } }),
  exposure: (ids: readonly number[], day: IsoDate) =>
    request<Exposure>("/api/portfolio/exposure", { query: { account_id: ids, from: day, to: day } }),
  exposureHistory: (ids: readonly number[], from: IsoDate | null) =>
    request<Exposure>("/api/portfolio/exposure", { query: { account_id: ids, from } }),
  closed: (ids: readonly number[]) => request<Closed>("/api/portfolio/closed", { query: { account_id: ids } }),
```

```ts
  positions: (ids: readonly number[]) => request<Position[]>("/api/positions", { query: { account_id: ids } }),
```

`web/src/api/queryKeys.ts` (the ids come already sorted from `useAccountSelection`, so one choice gives one key):

```ts
  summary: (ids: readonly number[]) => ["portfolio", "summary", ids] as const,
  history: (ids: readonly number[], from: string | null) => ["portfolio", "history", ids, from] as const,
  exposure: (ids: readonly number[], day: string) => ["portfolio", "exposure", ids, day] as const,
  exposureHistory: (ids: readonly number[], from: string | null) => ["portfolio", "exposure-history", ids, from] as const,
  closed: (ids: readonly number[]) => ["portfolio", "closed", ids] as const,
  ...
  positions: (ids: readonly number[]) => ["portfolio", "positions", ids] as const,
```

- [ ] **Step 4: The screens**

For each screen, import `useAccountSelection` from `../../accounts/AccountSelection` and `AccountSelect` from `../../ui/AccountPicker`. Replace the local `useState<number | null>` with the shared selection. Every account-filtered query also gets `ready` in its `enabled`.

`DashboardScreen.tsx`:

```tsx
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  ...
  const summary = useQuery({
    queryKey: keys.summary(accountIds),
    queryFn: () => api.summary(accountIds),
    enabled: ready,
    refetchInterval: (query) => (query.state.data?.recalculating ? RECALC_POLL_MS : false),
    placeholderData: (previous) => previous,
  });
  ...
  const history = useQuery({ queryKey: keys.history(accountIds, from), queryFn: () => api.history(accountIds, from), enabled: ready && asOf !== null, placeholderData: (previous) => previous });
  const exposure = useQuery({
    queryKey: keys.exposure(accountIds, asOf ?? ""),
    queryFn: () => api.exposure(accountIds, asOf!),
    enabled: ready && asOf !== null && mode === "currency",
  });
  const positions = useQuery({ queryKey: keys.positions(accountIds), queryFn: () => api.positions(accountIds), enabled: ready && asOf !== null, placeholderData: (previous) => previous });
  ...
      {accounts.data ? <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} /> : <span />}
```

`summary.isPending` is true while the query waits for `ready`, so the Dashboard shows its skeleton meanwhile. Nothing else changes.

`ExposureScreen.tsx`:

```tsx
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  ...
  const exposure = useQuery({
    queryKey: keys.exposureHistory(accountIds, from), queryFn: () => api.exposureHistory(accountIds, from),
    enabled: ready, placeholderData: (previous) => previous,
  });
  ...
      {accounts.data && <AccountSelect accounts={accounts.data} value={accountIds} onChange={setAccountIds} />}
```

`PositionsScreen.tsx`:

```tsx
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  ...
  const positions = useQuery({ queryKey: keys.positions(accountIds), queryFn: () => api.positions(accountIds), enabled: ready && view === "open" });
  ...
      {(accounts.data?.length ?? 0) > 0 && <AccountSelect accounts={accounts.data!} value={accountIds} onChange={setAccountIds} />}
      ...
      {view === "closed" ? <ClosedView accountIds={accountIds} ready={ready} /> : (
```

`ClosedView.tsx`:

```tsx
export function ClosedView({ accountIds, ready }: { accountIds: readonly number[]; ready: boolean }) {
  const closed = useQuery({ queryKey: keys.closed(accountIds), queryFn: () => api.closed(accountIds), enabled: ready, placeholderData: (previous) => previous });
```

`HistoryScreen.tsx`:

```tsx
  const [accountIds, setAccountIds, ready] = useAccountSelection();
  ...
  const filters: HistoryFilters = { account_ids: accountIds, type: type || null, from: from || null, to: to || null, q };
  ...
  const entries = useInfiniteQuery({
    queryKey: keys.entries(filters),
    queryFn: ({ pageParam }) => api.entries(filters, pageParam),
    initialPageParam: null as string | null,
    getNextPageParam: (last) => last.next_cursor,
    enabled: ready,
  });
  ...
        {(accounts.data?.length ?? 0) > 0 && <AccountSelect accounts={accounts.data!} value={accountIds} onChange={setAccountIds} />}
```

Remove the now unused `useState` imports where a screen has no other state.

- [ ] **Step 5: Remove the old controls**

In `web/src/ui/AccountPicker.tsx`, delete `AccountPicker` and `AccountChips`, keeping only `AccountSelect`. In `web/src/ui/ui.module.css`, delete the `.picker` rules and the `.chips` rules. First confirm with `grep -rn "picker\|chips\|AccountPicker\b\|AccountChips" web/src` that nothing else uses them. In `web/src/ui/ui.test.tsx`, delete the tests "chooses the whole portfolio or one account" and "filters by account with chips", then drop the unused imports (`AccountChips`, `AccountPicker` and, if unused now, `ACCOUNTS`).

- [ ] **Step 6: Update the existing screen tests to the checkbox control**

The URLs they expect stay the same, because one account still sends a single `account_id`. Only the way of choosing changes:

- `dashboard.test.tsx`, "asks for one account and the currency allocation of the valuation day". Replace the `selectOptions` line with:
  ```tsx
  await user.click(await screen.findByRole("button", { name: "Konta: Cały portfel" }));
  await user.click(screen.getByRole("checkbox", { name: "IKE" }));
  await user.keyboard("{Escape}");
  ```
- `dashboard.test.tsx`, "keeps the numbers on screen while another account loads". Replace the `selectOptions` line with:
  ```tsx
  await user.click(screen.getByRole("button", { name: "Konta: Cały portfel" }));
  await user.click(screen.getByRole("checkbox", { name: "IKE" }));
  ```
- `positions.test.tsx`, "filters by account". Replace `await user.click(await screen.findByRole("button", { name: "IKE" }));` with:
  ```tsx
  await user.click(await screen.findByRole("button", { name: "Konta: Cały portfel" }));
  await user.click(screen.getByRole("checkbox", { name: "IKE" }));
  ```
- `closed.test.tsx`, "filters the closed view by account…". Replace `await user.click(screen.getByRole("button", { name: "IKE" }));` with the same two lines, using `getByRole` for the button (the screen has already loaded there).
- `history.test.tsx`, "sends the filters and the search to the API". Replace the `IKE` chip click with the same two lines, followed by `await user.keyboard("{Escape}");` before the "Rodzaj" select.
- `exposure.test.tsx`: if any test picks an account through the combobox, change it the same way.

- [ ] **Step 7: Run everything**

Run: `npx tsc -b && npx vitest run`
Expected: all pass (180 before this plan, plus the new ones). If a test elsewhere now fails because it counts `/api/accounts` calls or expects no request before a render, check whether the provider's shared accounts query explains it. Fix the test's expectation only when the new behaviour is the intended one.

- [ ] **Step 8: Update the roadmap**

In `docs/superpowers/plans/2026-09-26-00-roadmap.md`, replace the section `## Na później — wybór kilku kont (spec zatwierdzony 2026-09-30)` and its two bullets with:

```markdown
## Wybór kilku kont — zrobiony 2026-09-30

- Filtr kont z checkboxami, wspólny i zapamiętany na Pulpicie, w Ekspozycji, Pozycjach (Otwarte i Zamknięte) i Historii.
  API przyjmuje powtórzony `account_id`. Spec: `specs/2026-09-30-account-selection-design.md`, plan: `2026-09-30-account-selection.md`.
```

- [ ] **Step 9: Commit**

```bash
git add web/src docs/superpowers/plans/2026-09-26-00-roadmap.md
git commit -m "feat(web): Pulpit, Ekspozycja, Pozycje and Historia share one multi-account selection"
```
