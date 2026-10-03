# Plan 7g — Przegląd AI: cała Analiza w paczce i „W skrócie” — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The review package carries everything from Analiza (tags at holdings, Tagi, Walory, Dochód i koszty). Claude infers the owner's plan from tags and notes. Its answer opens with „W skrócie” (2–3 sentences + 1–5 proposals from different perspectives), which the Analiza card shows.

**Architecture:**
- **API:**
  - the package's number formatting moves from `package.py` to `app/reviews/fmt.py`;
  - the new sections live in `app/reviews/analysis.py`, built from the same functions as the Analiza screens (`holdings`, `income`, `tag_analytics`, `TagLookup`);
  - `prompt.py` gets the new rules and „W skrócie” as the first of 10 sections;
  - `clean.summary()` cuts that section out of a saved answer for `GET /api/reviews`.
- **Web:** `ReviewCard` shows the summary, and `SECTION_COUNT` becomes 10.

**Tech Stack:** FastAPI, pytest; React, TanStack Query, Vitest.

**Spec:** `docs/superpowers/specs/2026-10-04-07g-review-context-design.md`

## Global Constraints

- **Section order in the package:**
  1. Podsumowanie
  2. Konta
  3. Pozycje
  4. Obligacje
  5. Konta oszczędnościowe
  6. Alokacja
  7. **Tagi**
  8. **Walory**
  9. **Dochód i koszty**
  10. Miary
  11. Historia
  12. Limity
  13. Zamknięte
  14. Notatki właściciela
  15. Scenariusze
- **Every new section:**
  - respects the package's account filter;
  - counts savings accounts in.
- **Periods:**
  - Walory ranking: `1m`, `1y`, `all`; groups: `all`;
  - Dochód: totals `12m` and `all`; sources and costs `all`; months `12m`.
- **Copy:**
  - „Brak tagów.”, „Brak danych.”, „Bez tagu”, „Gotówka”;
  - „Walor może mieć kilka tagów, więc udziały mogą sumować się do ponad 100 %.”;
  - „To nie jest porada inwestycyjna.” (card);
  - kind names of income sources: savings → „konto oszczędnościowe”, bond → „obligacje”, xtb_interest → „odsetki XTB”, dividend → „dywidenda”;
  - month label: „wrz 2026”.
- **A holding without tags** shows „—” in the „Tagi” column.
- **Answer sections:** `SECTIONS[0] == "W skrócie"`, then the previous 9 in their order (10 in all).
- **Commands:**
  - `docker compose run --rm api pytest -q` (≈ 2½ min, 400 s timeout); one file: `docker compose run --rm api pytest -q tests/test_review_package.py`;
  - `cd web && NO_COLOR=1 npx vitest run && npx tsc --noEmit`.

## Review Focus

1. **A tag linked on both levels** (on the holding and on its account) must appear once in the „Tagi” column, not twice. Pinned in Task 1.
2. **The account filter:**
   - a tag of a holding on another account must not show in „Tagi”;
   - Walory and Dochód carry only the chosen accounts.

   Pinned in Tasks 1 and 2.
3. **A holding missing from a short period** (bought after the 1-month window started is still in it, but one sold before is not) shows „—” there and is not dropped from the ranking. Pinned in Task 2.
4. **„W skrócie” written by Claude with an emoji or another case** („## 📌 w skrócie”) is still cut out as the summary. The cut stops at the next `## `, but not at `### `. Pinned in Task 3.
5. **An old review without „W skrócie”** has `summary: null`, and the card shows just the date. Pinned in Tasks 3 and 4.

---

### Task 1: Tags in the package — the „Tagi” column and the „## Tagi” section

**Files:**
- Create:
  - `api/app/reviews/fmt.py`;
  - `api/app/reviews/analysis.py`.
- Modify:
  - `api/app/reviews/package.py`;
  - `api/tests/test_review_package.py`.

**Interfaces — Produces:**
- `app.reviews.fmt`: `NBSP`, `MINUS`, `NONE`, `MONTHS`, `money`, `pct`, `number`, `date`, `table` (moved from `package.py`, same behaviour; `package.py` imports them, so `package.money` etc. still exist);
- `app.reviews.analysis`:
  - `tag_names(lookup: TagLookup, key: str, account_id: int) -> str`;
  - `tags_section(scope: UserScope, account_ids: frozenset[int] | None) -> str`.

- [ ] **Step 1: Failing tests.** In `api/tests/test_review_package.py`:
  - extend the imports: `from app.models import Account, Instrument, Price, SavingsAccount, SavingsBalance, SavingsRate, Transaction, User` (keep what is there, add the three savings models);
  - add `from tests.tag_seed import add_link, add_tag` (next to `tag_world`);
  - append:

```python
def _section(body: str, heading: str) -> str:
    """The text of one package section: from its heading to the next `## `."""
    return body.split(f"\n{heading}", 1)[1].split("\n## ", 1)[0]


def _savings_balance(engine: Engine, world: dict) -> None:
    """Gives tag_world's savings account a balance, so the package lists it."""
    with Session(engine) as db:
        savings = db.scalar(select(SavingsAccount).where(SavingsAccount.account_id == world["savings"]))
        db.add_all([SavingsRate(savings_account_id=savings.id, valid_from=dt.date(2026, 9, 1), annual_rate=Decimal("5")),
                    SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 9, 1),
                                   balance=Decimal("10000"))])
        db.commit()
        valuate(db, world["user_id"])


def test_holdings_carry_their_tags_once(client: TestClient, tagged: dict, engine: Engine) -> None:
    _savings_balance(engine, tagged)
    anna = tagged["anna"]
    core, spec, retirement, cushion = (add_tag(client, anna, n) for n in ("core", "spekulacja", "emerytura", "poduszka"))
    add_link(client, tagged, core, instrument_id=tagged["sxr8"])
    add_link(client, tagged, core, instrument_id=tagged["sxr8"], account_id=tagged["ike"])  # both levels
    add_link(client, tagged, spec, instrument_id=tagged["sxr8"], account_id=tagged["plain"])  # another account
    add_link(client, tagged, retirement, bond_series="EDO0336")
    add_link(client, tagged, cushion, account_id=tagged["savings"])

    body = _package(client, anna)

    positions = _section(body, "## Pozycje")
    assert "| Uwagi | Tagi |" in positions
    sxr8_row = next(line for line in positions.splitlines() if line.startswith("| SXR8.DE |"))
    assert sxr8_row.endswith("| core |")  # once, and not the plain account's „spekulacja”
    bonds = _section(body, "## Obligacje")
    assert "| Konto | Tagi |" in bonds and "| emerytura |" in bonds
    assert "| poduszka |" in _section(body, "## Konta oszczędnościowe")


def test_a_holding_without_tags_shows_a_dash(client: TestClient, world: dict) -> None:
    positions = _section(_package(client, world["anna"]), "## Pozycje")

    sxr8_row = next(line for line in positions.splitlines() if line.startswith("| SXR8.DE |"))
    assert sxr8_row.endswith("| — |")


def test_package_has_the_tags_with_share_and_gain(client: TestClient, tagged: dict) -> None:
    anna = tagged["anna"]
    core = add_tag(client, anna, "core")
    add_link(client, tagged, core, instrument_id=tagged["sxr8"])
    report = client.get("/api/analytics/tags", params={"period": "all"}, headers=anna).json()
    (row,) = report["tags"]

    section = _section(_package(client, anna), "## Tagi")

    assert "| Tag | Wartość | Udział w portfelu | Zysk (cały okres) | Zysk % | Walorów |" in section
    assert (f"| core | {money(Decimal(row['value_pln']))} | {pct(Decimal(row['share_pct']))} | "
            f"{money(Decimal(row['gain_pln']))} | {pct(Decimal(row['gain_pct']))} | 1 |") in section
    assert "| Bez tagu |" in section  # the bond is not tagged
    assert "udziały mogą sumować się do ponad 100" in section


def test_package_tags_follow_the_account_filter(client: TestClient, tagged: dict) -> None:
    anna = tagged["anna"]
    core = add_tag(client, anna, "core")
    add_link(client, tagged, core, instrument_id=tagged["sxr8"])

    section = _section(_package(client, anna, account_id=tagged["plain"]), "## Tagi")

    assert "| core |" not in section


def test_package_without_tags_says_so(client: TestClient, world: dict) -> None:
    assert _section(_package(client, world["anna"]), "## Tagi").strip() == "Brak tagów."
```

  - add `from app.reviews.fmt import money, pct` to the imports.

- [ ] **Step 2: Run them, they fail.** Run `docker compose run --rm api pytest -q tests/test_review_package.py`. Expected: the new tests FAIL. `app.reviews.fmt` cannot be imported, so the whole file errors at collection, which counts as RED.

- [ ] **Step 3: Move the formatting.** Create `api/app/reviews/fmt.py`. Its content is `package.py`'s current definitions of `NBSP`, `MINUS`, `NONE`, `MONTHS`, `_decimal`, `money`, `pct`, `number`, `date` and `table`, moved verbatim, under this docstring:

```python
"""Polish number, date and table formatting of the review package."""
import datetime as dt
from decimal import ROUND_HALF_UP, Decimal
```

  - In `package.py`, delete those definitions.
  - Import them: `from app.reviews.fmt import MONTHS, NBSP, NONE, date, money, number, pct, table`. Keep only the names `package.py` still uses; drop `ROUND_HALF_UP` from its imports if it becomes unused.
  - Keep `WRAPPERS`, `KINDS` and `BASES` in `package.py`.

- [ ] **Step 4: The tags.** Create `api/app/reviews/analysis.py`:

```python
"""The Analiza screens in the review package (plan 7g): tags, the holdings' gains, income and costs — built by the
same functions as the screens, so the numbers match the app."""
from app.analytics.tags import tag_analytics
from app.reviews.fmt import NONE, money, pct, table
from app.scoping import UserScope
from app.tags.lookup import TagLookup

NO_TAGS = "Brak tagów."
OVERLAP = "Walor może mieć kilka tagów, więc udziały mogą sumować się do ponad 100 %."


def tag_names(lookup: TagLookup, key: str, account_id: int) -> str:
    """The holding's tags as its details show them, each once; „—” without any."""
    names = dict.fromkeys(tag.name for tag in lookup.on(key, account_id))
    return ", ".join(names) or NONE


def tags_section(scope: UserScope, account_ids: frozenset[int] | None) -> str:
    report = tag_analytics(scope, account_ids, "all")
    if not report.tags:
        return NO_TAGS
    rows = [[t.name, money(t.value_pln), pct(t.share_pct), money(t.gain_pln), pct(t.gain_pct), str(t.holdings)]
            for t in report.tags]
    if report.untagged is not None:
        u = report.untagged
        rows.append(["Bez tagu", money(u.value_pln), pct(u.share_pct), money(u.gain_pln), pct(u.gain_pct),
                     str(u.holdings)])
    if report.cash.value_pln:
        rows.append(["Gotówka", money(report.cash.value_pln), pct(report.cash.share_pct), NONE, NONE, NONE])
    return table(["Tag", "Wartość", "Udział w portfelu", "Zysk (cały okres)", "Zysk %", "Walorów"], rows) + "\n\n" + OVERLAP
```

In `package.py`:
- import `from app.reviews.analysis import tag_names, tags_section` and `from app.tags.lookup import TagLookup`;
- `_positions`, `_bonds` and `_savings` each take one more argument, `lookup: TagLookup`, and add the column „Tagi” at the end:
  - `_positions`: the header list gets `"Tagi"` after `"Uwagi"`. Each row gets `tag_names(lookup, f"i:{p.instrument_id}", p.account_id)` as its last cell.
  - `_bonds`: the header gets `"Tagi"` after `"Konto"`. Each row gets `tag_names(lookup, f"b:{stored.series}", stored.account_id)` last.
  - `_savings`: the header gets `"Tagi"` after `"Odsetki od wpłat"`. Each row gets `tag_names(lookup, "s:", p.account_id)` last.
- in `build_package`:
  - add `lookup = TagLookup(scope)` after `by_account = …`;
  - pass `lookup` to the three calls;
  - right after the „Według konta” allocation item, add `"## Tagi", tags_section(scope, account_ids),`.

- [ ] **Step 5: Run the tests, they pass.** Run `docker compose run --rm api pytest -q tests/test_review_package.py tests/test_reviews_api.py`. Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add api/app/reviews api/tests/test_review_package.py
git commit -m "feat(review): tags at the holdings and the „Tagi” section in the package"
```

---

### Task 2: „## Walory” and „## Dochód i koszty” in the package

**Files:**
- Modify:
  - `api/app/reviews/analysis.py`;
  - `api/app/reviews/package.py`;
  - `api/tests/test_review_package.py`.

**Interfaces:**
- Consumes (Task 1): `app.reviews.fmt`, `analysis.py`, `_section`.
- Produces: `holdings_section(scope, account_ids) -> str`, `income_section(scope, account_ids) -> str`, `month_label(month: str) -> str`.

- [ ] **Step 1: Failing tests.** Append to `api/tests/test_review_package.py`:

```python
def test_package_ranks_the_holdings_over_three_periods(client: TestClient, world: dict) -> None:
    anna = world["anna"]
    whole = client.get("/api/analytics/holdings", params={"period": "all"}, headers=anna).json()
    month = client.get("/api/analytics/holdings", params={"period": "1m"}, headers=anna).json()
    (item,) = whole["items"]
    in_month = {i["key"]: i for i in month["items"]}.get(item["key"])

    section = _section(_package(client, anna), "## Walory")

    assert "| Walor | Typ | Wartość | Zysk 1 mies. | % | Zysk 1 rok | % | Zysk cały okres | % |" in section
    month_cells = (f"{money(Decimal(in_month['gain_pln']))} | {pct(_dec(in_month['gain_pct']))}" if in_month
                   else "— | —")
    assert (f"| SXR8.DE — Core S&P 500 | ETF | {money(Decimal(item['value_pln']))} | {month_cells} |") in section
    assert f"| {money(Decimal(item['gain_pln']))} | {pct(Decimal(item['gain_pct']))} |" in section
    assert "### Według kont" in section and "| XTB IKE |" in section
    assert "### Według typów" in section and "| ETF |" in section
    assert "cały okres: " in section  # the dates of the periods


def test_a_holding_outside_a_period_has_dashes(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:  # CD Projekt bought and sold in April: in the whole history only
        cdr = Instrument(xtb_ticker="CDR.PL", name="CD Projekt", category="stock", currency="PLN", price_symbol="CDR.WA")
        db.add(cdr)
        db.flush()
        db.add(Price(instrument_id=cdr.id, date=dt.date(2026, 4, 1), close=Decimal("250"), source="yahoo"))
        for number, (kind, amount, day) in enumerate([("buy", "-500", 2), ("sell", "520", 3)], start=900):
            db.add(Transaction(account_id=world["account_id"], type=kind, xtb_type=kind, amount=Decimal(amount),
                               occurred_at=dt.datetime(2026, 4, day, 10, tzinfo=dt.UTC), currency="PLN",
                               external_id=str(number), comment="", raw={}, instrument_id=cdr.id,
                               quantity=Decimal("2"), price=Decimal("250")))
        db.commit()
        valuate(db, world["user_id"])

    section = _section(_package(client, world["anna"]), "## Walory")

    row = next(line for line in section.splitlines() if line.startswith("| CDR.PL — CD Projekt |"))
    assert "| — | — |" in row  # not in the last month
    assert section.index("| SXR8.DE") < section.index("| CDR.PL")  # by the whole-history gain, highest first


def test_package_has_income_and_costs(client: TestClient, world: dict) -> None:
    section = _section(_package(client, world["anna"]), "## Dochód i koszty")

    assert "| Ostatnie 12 miesięcy |" in section and "| Cały okres |" in section
    assert f"| SXR8.DE Core S&P 500 | dywidenda | {money(Decimal('40'))} | {money(Decimal('6'))} | {money(Decimal('34'))} |" in section
    assert f"| Przewalutowanie XTB | {money(Decimal('21.41'))} | 1 |" in section
    assert "### Miesiące (ostatnie 12)" in section and "| cze 2026 |" in section


def test_package_analysis_follows_the_account_filter(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        other = Account(user_id=world["user_id"], name="Puste", kind="broker", wrapper="regular", currency="PLN")
        db.add(other)
        db.commit()
        other_id = other.id

    body = _package(client, world["anna"], account_id=other_id)

    assert "SXR8.DE" not in _section(body, "## Walory")
    assert "dywidenda" not in _section(body, "## Dochód i koszty")


def test_month_label() -> None:
    from app.reviews.analysis import month_label

    assert month_label("2026-09") == "wrz 2026"
```

Also add the helper next to `_section`:

```python
def _dec(value: str | None) -> Decimal | None:
    return None if value is None else Decimal(value)
```

- [ ] **Step 2: Run them, they fail.** Run `docker compose run --rm api pytest -q tests/test_review_package.py`. Expected: the five new tests FAIL (IndexError for the missing sections, ImportError for `month_label`).

- [ ] **Step 3: The sections.** In `api/app/reviews/analysis.py`:
  - add the imports:

```python
from app.analytics.holdings import KINDS as HOLDING_KINDS
from app.analytics.holdings import holdings
from app.analytics.income import income
from app.analytics.schemas import GroupGainOut
from app.reviews.fmt import MONTHS, date
```

  - add:

```python
NO_DATA = "Brak danych."
PERIODS = (("1m", "1 mies."), ("1y", "1 rok"), ("all", "cały okres"))
SOURCE_KINDS = {"savings": "konto oszczędnościowe", "bond": "obligacje", "xtb_interest": "odsetki XTB",
                "dividend": "dywidenda"}


def month_label(month: str) -> str:
    """"2026-09" → "wrz 2026"."""
    year, number = month.split("-")
    return f"{MONTHS[int(number) - 1]} {year}"


def _groups(groups: list[GroupGainOut], name: str) -> str:
    return table([name, "Wartość", "Zysk", "Zysk %"],
                 [[g.name, money(g.value_pln), money(g.gain_pln), pct(g.gain_pct)] for g in groups])


def holdings_section(scope: UserScope, account_ids: frozenset[int] | None) -> str:
    """Walory (7c): every holding's gain over 1 month, 1 year and the whole history, ranked by the last; and the whole
    history by account and by kind."""
    reports = {period: holdings(scope, account_ids, period) for period, _ in PERIODS}
    whole = reports["all"]
    if not whole.items:
        return NO_DATA
    found = {period: {item.key: item for item in report.items} for period, report in reports.items()}
    rows = []
    for item in sorted(whole.items, key=lambda i: i.gain_pln, reverse=True):
        row = [f"{item.ticker} — {item.name}" if item.ticker else item.name,
               HOLDING_KINDS.get(item.category, item.category), money(item.value_pln)]
        for period, _ in PERIODS:
            other = found[period].get(item.key)
            row += [money(other.gain_pln), pct(other.gain_pct)] if other else [NONE, NONE]
        rows.append(row)
    ranges = "; ".join(f"{name}: {date(reports[period].period.start)}–{date(reports[period].period.end)}"
                       for period, name in PERIODS if reports[period].period is not None)
    return "\n\n".join([
        "### Ranking walorów",
        table(["Walor", "Typ", "Wartość", "Zysk 1 mies.", "%", "Zysk 1 rok", "%", "Zysk cały okres", "%"], rows),
        f"Okresy — {ranges}.",
        "### Według kont", _groups(whole.by_account, "Konto"),
        "### Według typów", _groups(whole.by_kind, "Typ"),
    ])


def income_section(scope: UserScope, account_ids: frozenset[int] | None) -> str:
    """Dochód i koszty (7d): totals over 12 months and the whole history, the sources and costs of the whole history,
    and the last 12 months."""
    year, whole = income(scope, account_ids, "12m"), income(scope, account_ids, "all")
    if whole.period is None:
        return NO_DATA
    totals = [[name, money(t.income_pln), money(t.costs_pln), money(t.balance_pln)]
              for name, t in (("Ostatnie 12 miesięcy", year.totals), ("Cały okres", whole.totals))]
    return "\n\n".join([
        "### Suma", table(["Okres", "Dochód", "Koszty", "Bilans"], totals),
        "### Źródła dochodu (cały okres)",
        table(["Źródło", "Rodzaj", "Brutto", "Podatek", "Netto"],
              [[s.name, SOURCE_KINDS.get(s.kind, s.kind), money(s.gross_pln), money(s.tax_pln), money(s.net_pln)]
               for s in whole.sources]),
        "### Koszty (cały okres)",
        table(["Koszt", "Kwota", "Liczba"], [[c.name, money(c.amount_pln), str(c.count)] for c in whole.costs]),
        "### Miesiące (ostatnie 12)",
        table(["Miesiąc", "Odsetki", "Dywidendy", "Przewalutowanie", "Podatki", "Opłaty", "Bilans"],
              [[month_label(m.month), money(m.interest_pln), money(m.dividends_pln), money(m.fx_pln),
                money(m.taxes_pln), money(m.fees_pln), money(m.balance_pln)] for m in year.months]),
    ])
```

In `package.py`:
- import `holdings_section` and `income_section` from `app.reviews.analysis`;
- right after `"## Tagi", tags_section(scope, account_ids),` add:

```python
        "## Walory", holdings_section(scope, account_ids),
        "## Dochód i koszty", income_section(scope, account_ids),
```

- [ ] **Step 4: Run the tests, they pass.** Run `docker compose run --rm api pytest -q tests/test_review_package.py tests/test_reviews_api.py`. Expected: PASS. If the „cały okres: ” assertion fails because the range sentence reads „Okresy — … cały okres: …”, the sentence is right and the assertion matches it as a substring.

- [ ] **Step 5: Commit.**

```bash
git add api/app/reviews api/tests/test_review_package.py
git commit -m "feat(review): Walory and Dochód i koszty in the package"
```

---

### Task 3: The prompt, „W skrócie” and the summary in the reviews list

**Files:**
- Modify:
  - `api/app/reviews/prompt.py`;
  - `api/app/reviews/clean.py`;
  - `api/app/reviews/schemas.py`;
  - `api/app/reviews/router.py`;
  - `api/tests/test_reviews_api.py`;
  - `api/tests/test_review_package.py`.

**Interfaces — Produces:**
- `SECTIONS` with 10 items, `"W skrócie"` first;
- `clean.summary(text: str) -> str | None`;
- `ReviewListItem.summary: str | None` in `GET /api/reviews`.

- [ ] **Step 1: Failing tests.**
  - In `api/tests/test_reviews_api.py`:
    - import `summary` beside `clean, count_sections`;
    - change the expected count in `test_sections_are_counted_whatever_the_case_or_an_emoji` from 9 to 10. Before that, check how `ANSWER` is built:
      - if it is built from `SECTIONS`, it already has 10 headings;
      - if it is a literal, prepend `"## W skrócie\n\nKrótko.\n\n"` to it.
    - append:

```python
def test_the_summary_is_the_text_of_w_skrocie() -> None:
    text = "## 📌 W SKRÓCIE\n\nPortfel jest ostrożny.\n\n1. **Porządki:** wpłać 1 000 zł.\n\n### Szczegół\n\nx\n\n## Ocena ogólna\n\nDalej."

    assert summary(text) == "Portfel jest ostrożny.\n\n1. **Porządki:** wpłać 1 000 zł.\n\n### Szczegół\n\nx"
    assert summary("## Ocena ogólna\n\nBez skrótu.") is None
    assert summary("## W skrócie\n\n## Ocena ogólna") is None


def test_the_list_carries_the_summary(client: TestClient, headers: dict) -> None:
    saved = client.post("/api/reviews", json={"content": "## W skrócie\n\nKrótko.\n\n## Ryzyka\n\nDużo."}, headers=headers)
    assert saved.status_code == 201, saved.text
    client.post("/api/reviews", json={"content": "## Ryzyka\n\nStary układ."}, headers=headers)

    items = client.get("/api/reviews", headers=headers).json()

    assert [item["summary"] for item in items] == [None, "Krótko."]
```

    The second test uses the file's existing fixtures for a signed-in client. If the headers fixture has another name (e.g. `anna`), use that name. Newest comes first, as in the list's order.

  - In `api/tests/test_review_package.py`, append:

```python
def test_the_instructions_ask_for_w_skrocie_and_read_tags_and_notes() -> None:
    from app.reviews.prompt import INSTRUCTIONS

    assert SECTIONS[0] == "W skrócie" and len(SECTIONS) == 10
    assert INSTRUCTIONS.index("## W skrócie") < INSTRUCTIONS.index("## Ocena ogólna")
    assert "Wywnioskuj z nich, do czego zmierzam — nie pytaj mnie o to." in INSTRUCTIONS
    assert "od 1 do 5 propozycji" in INSTRUCTIONS
    assert "rozwiń w niej propozycje z „W skrócie”" in INSTRUCTIONS
```

- [ ] **Step 2: Run them, they fail.** Run `docker compose run --rm api pytest -q tests/test_reviews_api.py tests/test_review_package.py`. Expected: FAIL (ImportError `summary`, the count is 9, the prompt has no „W skrócie”).

- [ ] **Step 3: The prompt.** In `api/app/reviews/prompt.py`:
  - `SECTIONS` gets `"W skrócie",` as its first item;
  - in „## Zasady”, replace the 7f-2 bullet („- Jeśli są notatki właściciela … i wskaż rozbieżności.”) with:

```
- Tagi i notatki to mój własny opis portfela: z tagów wynika, co jest trzonem, emeryturą, poduszką, a co spekulacją;
  notatki dodają moje powody i plany. Wywnioskuj z nich, do czego zmierzam — nie pytaj mnie o to. Oceniaj portfel
  względem tego i wskazuj rozbieżności.
- Zysk walorów za okresy, według kont i typów jest w sekcji „Walory”; dywidendy, odsetki, podatki i koszty
  w „Dochód i koszty”; udział i zysk tagów w „Tagi”.
```

  - replace the bullet about „Propozycje” with:

```
- W sekcji „Propozycje” rozwiń w niej propozycje z „W skrócie” (szczegóły, ryzyka, alternatywy); możesz być
  konkretny (co kupić, sprzedać, przenieść, ile), ale zacznij ją zdaniem: „To nie jest porada inwestycyjna — to
  propozycje do przemyślenia; decyzja należy do Ciebie.”
```

  - in „## Format odpowiedzi”, at the start of the paragraph that begins „W sekcji „Twoje instrumenty”…”, add:

```
„W skrócie”: najpierw 2–3 zdania — jak rozumiesz mój plan i jak portfel do niego dziś pasuje. Potem od 1 do 5
propozycji jako lista numerowana; każda zaczyna się pogrubioną nazwą perspektywy (np. **Więcej ryzyka, większy
potencjał:**, **Bezpieczniej:**, **Porządki:**), ma konkretną kwotę i jedno zdanie powodu. Każda propozycja z innej
perspektywy; gdy dajesz więcej niż jedną, przynajmniej jedna ma zwiększać potencjał zysku, a jedna zmniejszać ryzyko.
Liczbę propozycji dobierz do tego, co naprawdę warto zrobić.

```

- [ ] **Step 4: The summary.** In `api/app/reviews/clean.py`, add:

```python
def summary(text: str) -> str | None:
    """The text of the „W skrócie” section, without its heading, up to the next `## `; None without one."""
    lines = text.splitlines()
    for index, line in enumerate(lines):
        if line.startswith("## ") and _title(line) == SECTIONS[0].lower():
            body: list[str] = []
            for rest in lines[index + 1:]:
                if rest.startswith("## "):
                    break
                body.append(rest)
            return "\n".join(body).strip() or None
    return None
```

  - In `api/app/reviews/schemas.py`, `ReviewListItem` gets `summary: str | None = None` after `sections`.
  - In `api/app/reviews/router.py`:
    - import `summary` from `app.reviews.clean`;
    - `list_reviews` becomes:

```python
@router.get("", response_model=list[ReviewListItem])
def list_reviews(scope: UserScope = Depends(get_scope)) -> list[ReviewListItem]:
    return [ReviewListItem(id=r.id, created_at=r.created_at, account_label=r.account_label, sections=r.sections,
                           summary=summary(r.content)) for r in scope.db.scalars(scope.reviews())]
```

- [ ] **Step 5: Run the tests, they pass.** Run `docker compose run --rm api pytest -q tests/test_reviews_api.py tests/test_review_package.py`, then the whole suite (400 s). Expected: PASS.

- [ ] **Step 6: Commit.**

```bash
git add api/app/reviews api/tests
git commit -m "feat(review): „W skrócie” with proposals from different perspectives; summary in the reviews list"
```

---

### Task 4: Web — the summary on the Analiza card and 10 sections

**Files:**
- Modify:
  - `web/src/api/types.ts`;
  - `web/src/screens/review/ReviewCard.tsx`;
  - `web/src/screens/review/ReviewScreen.tsx`;
  - `web/src/screens/review/review.test.tsx`;
  - `docs/superpowers/plans/2026-09-26-00-roadmap.md`.

**Interfaces:** consumes `summary` from Task 3.

- [ ] **Step 1: Failing tests.** In `web/src/screens/review/review.test.tsx`:
  - `SAVED` gets `summary: null`;
  - inside `describe("Przegląd portfela", …)`, add:

```tsx
  it("shows the latest summary on Analiza", async () => {
    routes([{ path: "/api/reviews", respond: () => [{ ...SAVED, sections: 10,
      summary: "Portfel jest ostrożny.\n\n1. **Bezpieczniej:** dokup ETF na cały świat za 1 000 zł." }] }]);
    renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Przegląd AI" });
    expect(await within(card).findByText("Portfel jest ostrożny.")).toBeInTheDocument();
    expect(within(card).getByText("Bezpieczniej:")).toBeInTheDocument();
    expect(within(card).getByText("To nie jest porada inwestycyjna.")).toBeInTheDocument();
  });

  it("shows only the date for a review without a summary", async () => {
    routes();
    renderApp("/analiza");

    const card = await screen.findByRole("region", { name: "Przegląd AI" });
    expect(await within(card).findByText(/2 października/)).toBeInTheDocument();
    expect(within(card).queryByText("To nie jest porada inwestycyjna.")).not.toBeInTheDocument();
  });
```

  - change the expected „9/9 sekcji” (or whatever count text the list test checks for `SAVED`) to „9/10 sekcji”.
  - `routes(extra)` puts `extra` before the defaults, so the first test's `/api/reviews` answer wins.

- [ ] **Step 2: Run them, they fail.** Run `cd web && NO_COLOR=1 npx vitest run src/screens/review`. Expected: FAIL. The summary is not shown, and the count is still „/9”. `tsc` will also complain about `summary` until Step 3.

- [ ] **Step 3: The card.**
  - In `web/src/api/types.ts`: `export interface ReviewListItem { id: number; created_at: IsoDateTime; account_label: string; sections: number; summary: string | null }`.
  - In `web/src/screens/review/ReviewScreen.tsx`: `export const SECTION_COUNT = 10;`.
  - In `web/src/screens/review/ReviewCard.tsx`: import `{ Markdown } from "./Markdown"`, and after the `<p className={styles.note}>…</p>` add:

```tsx
      {latest?.summary && (
        <>
          <Markdown text={latest.summary} />
          <small className="dim">To nie jest porada inwestycyjna.</small>
        </>
      )}
```

  - Update the card's doc comment to: `/** On Analiza: when the last review was made, its „W skrócie”, and the way to the review screen; nothing while unreadable. */`.

- [ ] **Step 4: Run the tests, they pass.** Run `cd web && NO_COLOR=1 npx vitest run && npx tsc --noEmit`. Expected: PASS, tsc clean. Fix any other literal that now lacks `summary`; tsc names it.

- [ ] **Step 5: Roadmap.** In `docs/superpowers/plans/2026-09-26-00-roadmap.md`, change row 7g's status „specyfikacja gotowa” to „✅ zrobiony (`2026-10-04-07g-review-context.md`)”.

- [ ] **Step 6: Commit.**

```bash
git add web/src docs/superpowers/plans/2026-09-26-00-roadmap.md
git commit -m "feat(web): „W skrócie” of the latest review on the Analiza card; 10 sections; roadmap: 7g done"
```
