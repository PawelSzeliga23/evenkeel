# Small fixes batch 2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the remaining small items of the roadmap section „Left for later on purpose” that a user can notice, plus the cheap test gaps. Deployment, the iPhone test, scale, catalog-data migrations and tooling stay for later.

**Architecture:** Local fixes only: the catalog add, the register flow, session restore, the import screen, the exposure share order, the simulator target picker and draft, Analiza headings and the value-chart readout.

**Tech Stack:** FastAPI + pytest (docker), React + Vitest.

**Spec:** none. Each item's authority is its roadmap line (`docs/superpowers/plans/2026-09-26-00-roadmap.md`, „Left for later on purpose”).

## Global Constraints

- Polish copy, in the style of the surrounding screens.
- Owner rule (memory `mirror-xtb-numbers`): numbers follow XTB. No item here changes a figure.
- Commands:
  - `docker compose run --rm api pytest -q`
  - `cd web && npx vitest run && npx tsc --noEmit`

## Review Focus

1. **Registration when the account is created but sign-in fails:** the retry must not hit „email zajęty”. The person must be told to sign in.
2. **A 404 from `/api/auth/me` at startup** (the user was deleted while its refresh cookie lived) must end at the login screen, not „Serwer ma problem”.
3. **The catalog-add race with an imported winner** must put the instrument in the catalog for the caller.

---

### Task 1: API

- [ ] **(7b-1, small-fixes review) Race winner in the catalog.** In `add_ticker`'s `IntegrityError` branch, a winner with `in_catalog = False` (saved by a concurrent XTB import) gets `in_catalog = True` and `catalog_group = catalog_group or ADDED_GROUP`, then a commit, exactly like the "existing" branch.
  - Test `test_add_racing_an_import_puts_the_winner_in_the_catalog` in `tests/test_catalog_api.py`: like the existing race test, but the racing insert has `in_catalog=False` and no group. After the POST, `GET /api/catalog` lists VWCE.DE in „Dodane przez Ciebie”.
- [ ] **(7b-1) Pin the `price_symbol` dedupe.** Test `test_add_by_yahoo_spelling_returns_the_known_instrument`: an instrument `EIMI.UK` with `price_symbol="EIMI.L"`. Posting `EIMI.L` gives 200 with ticker `EIMI.UK`, and the fake provider gets no call. Change code only if the test fails.
- [ ] **(6c) Pin a current year without a limit.** Read `tests/test_limits_api.py` and `app/portfolio/limits.py` first. Then add a test that `/api/portfolio/limits` with no `wrapper_limits` row for the current year answers without crashing, as the code intends (`limit_pln` null or the year left out). Change code only if it 500s.
- [ ] Commit `fix(api): catalog race puts an imported winner in the catalog; pins for the price_symbol dedupe and a year without a limit`.

### Task 2: Web — account flows

- [ ] **(6a) An empty invite code is never sent.** When the invite field is shown and empty, the form says „Podaj kod zaproszenia.” and sends nothing.
  - Test in `src/auth/auth.test.tsx`: after `invite_required`, submit with an empty code. The alert says „Podaj kod zaproszenia.” and the register POST count stays 1.
- [ ] **(6a) Registered but not signed in.** `session.register` registers. If the sign-in that follows fails, it throws `ApiError(status, "registered_sign_in_failed", "Konto zostało założone, ale nie udało się zalogować. Zaloguj się.")`. `RegisterScreen` shows that message with a link „Przejdź do logowania” to `/logowanie`, and the submit button is gone, so a retry cannot hit „email zajęty”.
  - Test: register answers 201, login answers 500. The alert says „Konto zostało założone…” and the link has `href="/logowanie"`.
- [ ] **(6c) A 404 from `/api/auth/me` at startup** is treated like 401/403: anonymous, ending at the login screen.
  - Test in `auth.test.tsx`: refresh OK, `me` 404, then the heading of the login screen is shown.
- [ ] **(6a, test gap) `signIn` resets the token when `me()` fails.** Test: login OK, `me` 500. The alert shows the server message. The next request does not carry `Authorization` (check the headers of a later call), or `getAccessToken()` is null if it is exported.
- [ ] Commit `fix(web): registration and session edge cases — empty invite code, registered but not signed in, 404 from me at startup`.

### Task 3: Web — screens

- [ ] **(6a) Import:**
  - the chosen file list uses ``key={`${i}-${f.name}`}``, because two files may share a name in different folders;
  - the skipped-file note becomes „Pominięto plik {name}: to nie jest eksport XTB (XLSX).”, which also fits `._*.xlsx` and ZIP entries.
  - Test: two files named `a.xlsx` give no React key warning (spy on `console.error`), and the new note text is shown for a skipped name.
- [ ] **(6a, test gap) Import: a failed commit keeps the preview and shows the API message.** Test with the commit POST answering 500 `{code, message}`: the alert has the message, and the „Zapisz import” button is still there.
- [ ] **(6c) Exposure share order** does not rely on the API's sort: `shareSeries` sorts `current` by `value_pln` descending before taking the order.
  - Test in `src/charts/shares.test.ts`: `current` given ascending still yields the larger currency first.
- [ ] **(small-fixes review) Simulator:**
  - `TargetSelect` shows an instrument that is in the catalog but outside the shown groups under its own name, „{name} ({ticker})”, not „Instrument niedostępny”. „Niedostępny” is only for ids absent from the whole catalog.
    - Test in `editor.test.tsx`: a saved replace whose `from` is id 20 (in CATALOG, „ETF: USA”, not held). „Zamiast” shows the option „iShares NASDAQ 100 (SXRV.DE)”.
  - `toBody` sends `ike: false` when the top-up target is not EDO.
    - Test in `model.test.ts`: a draft with `ike: true` and target "20" gives a body with `ike: false`.
- [ ] **(small-fixes review) `.titleRow` gap is 0,** because InfoTip's own margin gives the usual 6 px. CSS only; check visually with the e2e screenshot of Analiza if one exists, otherwise skip.
- [ ] **(6a) The value chart's readout is not announced on every pointer move:** `aria-live="off"` on the readout in `ValueChart.tsx`. The image's `aria-label` stays the accessible summary.
  - Test in `ValueChart.test.tsx`: the readout element has `aria-live="off"`.
- [ ] Run `npx vitest run` and `npx tsc --noEmit`. Commit `fix(web): import keys and wording, exposure order, simulator picker and IKE flag, quieter chart readout`.

### Task 4: Roadmap

- [ ] Remove the fixed items from „Left for later on purpose”. Add a line under „Paczka drobnych poprawek” for batch 2. Commit.
