# Plan 4a: Wycena — rdzeń (stan posiadania, `daily_valuations`, pulpit, pozycje) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplikacja wylicza z transakcji XTB i danych rynkowych wartość portfela dzień po dniu (per konto i składnik, w PLN), trzyma ją w tabeli-cache `daily_valuations` przeliczanej w tle po imporcie i po nowych danych rynkowych, i wystawia API pulpitu (wartość, zmiana dzienna i łączna, wpłacony kapitał, historia, alokacja, dywidendy) oraz listy i szczegółów pozycji (partie, zysk rozbity na efekt ceny i waluty, dywidendy, sprzedaże, zgodność z XTB) — poprawnie także po splitach pobieranych automatycznie z Yahoo.

**Architecture:** Silnik wyceny to czyste funkcje (`app/valuation/market_data.py`, `app/valuation/engine.py`): odtwarza transakcje w kolejności (`Book`), trzyma ilości „w bieżących jednostkach” (bazie cen skorygowanych o splity) i wycenia dzień po dniu na danych rynkowych wczytanych z góry do pamięci. Warstwa `app/valuation/service.py` ładuje dane użytkownika przez `UserScope`, oznacza użytkownika do przeliczenia (`users.valuations_stale_from`, najwcześniejsza data wygrywa) i przelicza pod blokadą doradczą Postgresa (`pg_advisory_xact_lock`) — zapisuje wiersze od daty „stale” do dziś. Wyzwalacze: zapis importu (znacznik w tej samej transakcji + `BackgroundTasks` zaraz po odpowiedzi), zmiana symbolu instrumentu, worker (nowe ceny/kursy/splity → znacznik → przeliczenie w tym samym ticku; każdy tick domyka zaległe przeliczenia). Pulpit czyta gotowe wiersze; lista i szczegóły pozycji liczą się na żywo tym samym silnikiem dla jednego dnia.

**Tech Stack:** jak w planach 1–3 (Python 3.12, FastAPI, SQLAlchemy 2, Alembic, Postgres 16, pytest w Dockerze). Bez nowych zależności: stdlib `bisect`, `decimal`, `zoneinfo`, `threading` (test blokady).

**Spec:** `docs/superpowers/specs/2026-09-26-portfolio-tracker-design.md` — §6 „Akcje / ETF-y”, „Splity i konwersje” (część: splity od dostawcy i przeliczanie ilości), „Historia wartości i zwrot” (bez TWR), §4 (`corporate_actions`, `daily_valuations`), §5 „Mapowanie tickerów” (wycena ceną z importu XTB), §7 (Pulpit, Pozycje), §9 (wycena przybliżona z flagą). Szkic z decyzjami: `docs/superpowers/plans/2026-09-27-04-valuation-draft.md` (sekcje „Ustalenia przeniesione…” i „Decyzje” są wiążące). Mapa: `docs/superpowers/plans/2026-09-26-00-roadmap.md`.

## Global Constraints

- Obowiązują wszystkie ograniczenia planów 1–3: Python 3.12 w kontenerze, testy `docker compose run --rm api pytest`, błędy `{code, message, details}` z `message` po polsku, dane użytkownika wyłącznie przez `UserScope`, obcy zasób → 404 `not_found`, testy nigdy nie łączą się z siecią, każdy commit z linią `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Pieniądze, ilości, ceny, kursy: **`Decimal` / `NUMERIC`, nigdy float**. Kwoty PLN w odpowiedziach API zaokrąglone do groszy (`ROUND_HALF_UP`), procenty do 0,01 (w JSON-ie liczby dziesiętne są stringami).
- Znaki `transactions.amount` (waluta konta): buy < 0, sell > 0, dividend > 0, withholding_tax < 0, deposit / transfer_in > 0, transfer_out / withdrawal < 0. `quantity` zawsze dodatnie; `price` w walucie notowania.
- Stan posiadania wyprowadzany **z transakcji**; `position_lots` tylko uzupełniająco (SL/TP w szczegółach). Sprzedaż dopasowana do partii po `xtb_position_id`; bez dopasowania — proporcjonalnie ze wszystkich otwartych partii (średni koszt), z oznaczeniem `matched = false`.
- Koszt partii w PLN = faktyczna kwota operacji gotówkowej XTB (`|amount|` × kurs NBP waluty konta; dla kont PLN kurs = 1).
- `prices.close` jest **skorygowany o splity** (Yahoo, `split_adjusted = True`). Silnik trzyma ilości w „bieżących jednostkach”: ilość z transakcji z dnia D × iloczyn współczynników splitów z `effective_date > D`. Split z `effective_date = E` dotyczy transakcji z dni `< E`. Ilość „na dzień D” pokazywana w API = bieżące jednostki ÷ ten sam iloczyn dla D.
- Dzień wyceny = **data kalendarzowa w strefie `Europe/Warsaw`** (`occurred_at` jest w UTC); siatka dni od pierwszej transakcji użytkownika do „dziś” (Warszawa). Brak notowania w dniu D → ostatnia cena ≤ D; kurs NBP → ostatni ≤ D, a gdy historia kursów zaczyna się później — pierwszy po D.
- Brak ceny dostawcy lub kursu waluty notowania w dniu D → wycena **ostatnią wartością z XTB** (nowsza z: cena transakcji tego konta w PLN za jednostkę; `value / volume` z wiersza zbiorczego *Open Positions* ostatniego importu) i flaga `xtb_price` w `daily_valuations.flags` oraz w API (`price_source = "xtb"`, `price_date`).
- `daily_valuations` to wyłącznie cache (spec §3 zasada 1): można skasować i odbudować. Wiersz instrumentu: `instrument_id` ustawione; wiersz gotówki konta: `instrument_id IS NULL`, `quantity` = saldo w walucie konta. `net_flow_pln` tylko na wierszu gotówki i tylko dla `deposit`, `withdrawal`, `transfer_in`, `transfer_out` (sparowane transfery wewnętrzne znoszą się na poziomie portfela).
- Przeliczenie użytkownika: znacznik `users.valuations_stale_from` (najwcześniejsza data wygrywa, `LEAST`), zapis wierszy od tej daty, blokada `pg_advisory_xact_lock((4 << 32) | user_id)` zarówno przy oznaczaniu, jak i przy przeliczaniu.

## Review Focus

- Split między zakupem a dziś (NVDA 10:1, 2024-06-10) → wartość pozycji ciągła przed i po splicie, ilość pokazywana 1 przed i 10 po, cena zakupu w szczegółach w bazie danego dnia; nowy split od dostawcy wymusza przeliczenie całej historii posiadaczy. *(Task 2, Task 5, Task 6)*
- Instrument bez cen u dostawcy (symbol nieznany / brak mapowania) → pozycja wyceniona ostatnią wartością z XTB, z flagą `xtb_price` i datą tej wartości, nigdy wartością 0 ani błędem 500. *(Task 5, Task 7, Task 9)*
- Sprzedaż bez pasującego `xtb_position_id`, sprzedaż częściowa, sprzedaż większa niż posiadanie → koszt zdejmowany proporcjonalnie, zysk zrealizowany policzony, brak wyjątku, pozycja w pełni sprzedana znika z listy, a jej szczegóły dalej pokazują zysk zrealizowany. *(Task 4, Task 9)*
- Import starszej historii po tym, jak wycena już istnieje → przeliczenie od najwcześniejszej nowej daty; wiersze sprzed tej daty nietknięte, nowsze odbudowane. *(Task 6, Task 7)*
- Import i worker przeliczają tego samego użytkownika jednocześnie → brak zdublowanych wierszy i brak zgubionego znacznika (przeliczenie czeka na blokadę). *(Task 6)*

---

## Mapa plików

```
README.md                                       + wiersze API pulpitu i pozycji, akapit o przeliczaniu wyceny
docs/superpowers/plans/2026-09-26-00-roadmap.md  wiersz 3 → ✅, wiersz 4 → 4a/4b
docs/superpowers/plans/2026-09-27-04-valuation-draft.md  „Stan” → plan 4a napisany
api/
  alembic/versions/0004_valuation.py            corporate_actions, daily_valuations, users.valuations_stale_from, instruments.splits_synced
  app/models/valuation.py                       CorporateAction, DailyValuation
  app/models/user.py                            + valuations_stale_from
  app/models/instrument.py                      + splits_synced
  app/models/__init__.py                        eksporty
  app/market/types.py                           + SplitEvent, PriceHistory.splits
  app/market/providers/yahoo.py                 events=split, parsowanie splitów
  app/market/store.py                           + replace_provider_splits
  app/market/update.py                          splity, pełna historia raz dla starych instrumentów, zapis zmienionych dat, waluty kont w FX
  app/db.py                                     + get_session_factory
  app/scoping.py                                + snapshots(), daily_valuations()
  app/valuation/__init__.py
  app/valuation/market_data.py                  Series, MarketData
  app/valuation/engine.py                       Entry, Split, Lot, Sale, Book, Quote, widoki, daily_rows, replay, sesje
  app/valuation/service.py                      load_inputs, mark_stale, holders, recompute_user, recompute_stale, …
  app/imports/service.py                        znacznik przeliczenia w apply_import
  app/imports/router.py                         przeliczenie w tle po zapisie importu
  app/instruments/router.py                     znacznik po zmianie symbolu
  app/worker.py                                 znaczniki po aktualizacji rynku, przeliczanie w każdym ticku
  app/portfolio/__init__.py
  app/portfolio/schemas.py                      odpowiedzi pulpitu, historii, pozycji
  app/portfolio/service.py                      portfolio_summary, portfolio_history, build_positions, position_detail
  app/portfolio/router.py                       GET /api/portfolio/summary, /history, /api/positions, /api/positions/{account}/{instrument}
  app/main.py                                   + router portfela
  tests/conftest.py                             nadpisanie get_session_factory
  tests/market_fakes.py                         + NVDA z splitem
  tests/valuation_seed.py                       wspólne dane testowe wyceny
  tests/test_valuation_models.py
  tests/test_valuation_engine_book.py
  tests/test_valuation_engine_rows.py
  tests/test_valuation_service.py
  tests/test_valuation_triggers.py
  tests/test_portfolio_api.py
  tests/test_positions_api.py
  tests/test_yahoo.py, test_market_store.py, test_market_update.py   + testy splitów i FX
```

## Decyzje

Wiążące decyzje ze szkicu (podział 4a/4b, splity z Yahoo, cena z XTB przy braku ceny, waluty kont w FX, tabela-cache przeliczana w tle, TWR i limity w 4b) są przyjęte bez zmian. Doprecyzowania tego planu:

- **Wycena zastępcza w PLN, bez zgadywania waluty.** Szkic zakładał cenę z `xtb_snapshots.current_price` i walutę z transakcji XTB. Zamiast tego silnik bierze wartość **w PLN za jednostkę**, którą XTB już wyliczył: `|amount| / quantity` ostatniej transakcji konta albo `value / volume` z wiersza zbiorczego *Open Positions* (wartość w walucie konta). Nowsza wygrywa. To omija problem GBX w pensach i nieznanej waluty ceny XTB, a przy obecnym stanie danych daje ten sam wynik. Efekt walutowy takiej pozycji = 0 (nieznany), cały wynik trafia do efektu ceny.
- **Kurs zakupu w rozbiciu zysku = kurs NBP waluty notowania z dnia zakupu** (`fx_open`), a efektywna cena zakupu = `koszt_PLN / (ilość × fx_open)`. Wtedy efekt ceny + efekt walutowy = wartość − koszt co do grosza, niezależnie od prowizji i spreadu XTB, także gdy ręczny symbol wskazuje notowanie w innej walucie niż transakcje XTB (spec §6: efekt ceny = qty × (cena_D − cena_zakupu) × kurs_zakupu; efekt walutowy = qty × cena_D × (kurs_D − kurs_zakupu)).
- **`daily_valuations` w 4a ma tylko wiersze instrumentów i gotówki.** Kolumny `bond_holding_id` i `savings_account_id` dodaje plan 5 razem z tabelami, do których wskazują. Unikalność: indeks `(account_id, instrument_id, date)` z `NULLS NOT DISTINCT` (Postgres 15+), więc wiersz gotówki też jest jeden na konto i dzień.
- **Znacznik per użytkownik zamiast kolejki zadań.** `users.valuations_stale_from` + blokada doradcza per użytkownik. Oznaczenie (import, worker) bierze tę samą blokadę co przeliczenie, więc import czeka na trwające przeliczenie, a przeliczenie uruchomione po imporcie widzi jego dane. Przeliczenie odtwarza całą historię w pamięci (tanio: dni × pozycje), a zapisuje tylko wiersze od daty znacznika.
- **Pełna historia raz dla instrumentów sprzed planu 4a** — kolumna `instruments.splits_synced` (dla istniejących wierszy `false`, dla nowych `true`, bo i tak dostają pełną historię przy pierwszym pobraniu). Instrument z `false` pobiera przy najbliższej aktualizacji pełną historię razem ze splitami. Splity dostawcy zapisujemy tylko w oknie pobranych danych (`replace_provider_splits(..., since)`), wpisy `manual`/`xtb` są nietknięte. Pierwszeństwo źródeł i ręczna edycja to plan 4b.
- **Zmiana dzienna liczona między sesjami (pn–pt)**: sesja = dzień wyceny cofnięty do piątku, jeśli wypada w weekend; poprzednia sesja = dzień roboczy wcześniej. W sobotę pulpit pokazuje zmianę z piątku, a nie 0. Święta giełdowe nie są rozpoznawane (w taki dzień zmiana = 0).
- **Worker codziennie oznacza wszystkich użytkowników z transakcjami od „dziś”**, żeby historia każdego portfela dostała nowy dzień, także portfela bez instrumentów zagranicznych.
- **Poza zakresem (4b):** konwersje walorów, ręczne zdarzenia korporacyjne i ich API, zamknięte inwestycje (podsumowanie), ekspozycja walutowa, limity IKE/IKZE (`wrapper_limits`), TWR, koszty (prowizje) jako osobna pozycja rozbicia zysku.

---
### Task 1: Modele i migracja 0004

**Files:**
- Create: `api/app/models/valuation.py`, `api/alembic/versions/0004_valuation.py`, `api/tests/test_valuation_models.py`
- Modify: `api/app/models/user.py`, `api/app/models/instrument.py`, `api/app/models/__init__.py`
- Test: `api/tests/test_valuation_models.py` + istniejący `test_models_match_migrations` w `api/tests/test_models.py`

**Interfaces:**
- Consumes: `Base`, `MONEY`, `QUANTITY` z `app.models.ledger`; tabele `users`, `accounts`, `instruments`.
- Produces:
  - `CorporateAction` (tabela `corporate_actions`): `id`, `instrument_id` (FK → instruments, ON DELETE CASCADE, indeks), `type: str` ∈ `CORPORATE_ACTION_TYPES = ("split", "reverse_split", "conversion")`, `effective_date: date`, `ratio_from: Decimal`, `ratio_to: Decimal` (split 10:1 → `ratio_from=1`, `ratio_to=10`; oba > 0), `target_instrument_id: int | None`, `source: str` ∈ `CORPORATE_ACTION_SOURCES = ("manual", "xtb", "provider")`; unikalne (`instrument_id`, `type`, `effective_date`, `source`).
  - `DailyValuation` (tabela `daily_valuations`): `id: int` (BIGINT), `user_id`, `account_id` (FK, CASCADE), `instrument_id: int | None`, `date: date`, `quantity: Decimal | None`, `value_pln`, `cost_pln`, `net_flow_pln: Decimal`, `flags: list[str]` (JSONB, domyślnie `[]`); unikalny indeks `uq_daily_valuations_account_id_instrument_id_date` z `NULLS NOT DISTINCT`, indeks `ix_daily_valuations_user_id_date`.
  - `User.valuations_stale_from: date | None`; `Instrument.splits_synced: bool` (domyślnie `true`; istniejące wiersze po migracji `false`).

- [ ] **Step 1: Napisz test**

`api/tests/test_valuation_models.py`:
```python
import datetime as dt
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import Account, CorporateAction, DailyValuation, Instrument, User

DAY = dt.date(2026, 9, 25)


def _world(session: Session) -> tuple[User, Account, Instrument]:
    user = User(email="anna@portfolio.dev", password_hash="x")
    instrument = Instrument(xtb_ticker="SXR8.DE", name="Core S&P 500")
    session.add_all([user, instrument])
    session.flush()
    account = Account(user_id=user.id, name="XTB IKE", kind="broker", wrapper="ike", broker="xtb",
                      external_account_number="56216965", currency="PLN")
    session.add(account)
    session.flush()
    return user, account, instrument


def _row(user: User, account: Account, instrument_id: int | None) -> DailyValuation:
    return DailyValuation(user_id=user.id, account_id=account.id, instrument_id=instrument_id, date=DAY,
                          quantity=Decimal("1"), value_pln=Decimal("10"), cost_pln=Decimal("10"),
                          net_flow_pln=Decimal("0"))


def test_cash_row_is_unique_per_account_and_day(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, account, _ = _world(session)
        session.add(_row(user, account, None))
        session.flush()
        session.add(_row(user, account, None))
        with pytest.raises(IntegrityError):
            session.flush()


def test_instrument_row_is_unique_per_account_instrument_and_day(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, account, instrument = _world(session)
        session.add_all([_row(user, account, instrument.id), _row(user, account, None)])
        session.flush()
        session.add(_row(user, account, instrument.id))
        with pytest.raises(IntegrityError):
            session.flush()


def test_flags_default_to_empty_list_and_rows_go_with_the_account(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, account, instrument = _world(session)
        row = _row(user, account, instrument.id)
        session.add(row)
        session.commit()
        session.refresh(row)
        assert row.flags == []
        session.delete(account)
        session.commit()
        assert session.scalar(select(func.count()).select_from(DailyValuation)) == 0


@pytest.mark.parametrize(
    ("fields", "reason"),
    [
        ({"type": "merger"}, "type"),
        ({"source": "yahoo"}, "source"),
        ({"ratio_from": Decimal("0")}, "ratio"),
    ],
)
def test_corporate_action_is_constrained(engine: Engine, clean_db: None, fields: dict, reason: str) -> None:
    with Session(engine) as session:
        _, _, instrument = _world(session)
        values = {"type": "split", "effective_date": DAY, "ratio_from": Decimal("1"), "ratio_to": Decimal("10"),
                  "source": "provider", **fields}
        session.add(CorporateAction(instrument_id=instrument.id, **values))
        with pytest.raises(IntegrityError):
            session.flush()


def test_new_instrument_counts_as_split_synced_and_user_is_not_stale(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, _, instrument = _world(session)
        session.commit()
        session.refresh(instrument)
        session.refresh(user)
        assert instrument.splits_synced is True
        assert user.valuations_stale_from is None
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_models.py -v`
Expected: FAIL — `ImportError: cannot import name 'CorporateAction' from 'app.models'`.

- [ ] **Step 3: Modele**

`api/app/models/valuation.py`:
```python
import datetime as dt
from decimal import Decimal

from sqlalchemy import BigInteger, CheckConstraint, Date, ForeignKey, Index, Numeric, String, UniqueConstraint, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.ledger import MONEY, QUANTITY

RATIO = Numeric(18, 8)
CORPORATE_ACTION_TYPES = ("split", "reverse_split", "conversion")
CORPORATE_ACTION_SOURCES = ("manual", "xtb", "provider")


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class CorporateAction(Base):
    """A split or conversion of an instrument, shared by all users. Split 10:1 -> ratio_from=1, ratio_to=10."""

    __tablename__ = "corporate_actions"
    __table_args__ = (
        UniqueConstraint("instrument_id", "type", "effective_date", "source"),
        CheckConstraint(_in_list("type", CORPORATE_ACTION_TYPES), name="type"),
        CheckConstraint(_in_list("source", CORPORATE_ACTION_SOURCES), name="source"),
        CheckConstraint("ratio_from > 0 AND ratio_to > 0", name="ratio_positive"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    effective_date: Mapped[dt.date] = mapped_column(Date)
    ratio_from: Mapped[Decimal] = mapped_column(RATIO)
    ratio_to: Mapped[Decimal] = mapped_column(RATIO)
    target_instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    source: Mapped[str] = mapped_column(String(10))


class DailyValuation(Base):
    """Cache of the valuation engine: one row per account, component and day; can be dropped and rebuilt.

    `instrument_id` NULL is the account's cash: `quantity` is the balance in the account currency and
    `net_flow_pln` carries its external flows (deposits, withdrawals, transfers) of that day.
    """

    __tablename__ = "daily_valuations"
    __table_args__ = (
        Index(
            "uq_daily_valuations_account_id_instrument_id_date", "account_id", "instrument_id", "date",
            unique=True, postgresql_nulls_not_distinct=True,
        ),
        Index("ix_daily_valuations_user_id_date", "user_id", "date"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"))
    instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    date: Mapped[dt.date] = mapped_column(Date)
    quantity: Mapped[Decimal | None] = mapped_column(QUANTITY)
    value_pln: Mapped[Decimal] = mapped_column(MONEY)
    cost_pln: Mapped[Decimal] = mapped_column(MONEY)
    net_flow_pln: Mapped[Decimal] = mapped_column(MONEY)
    flags: Mapped[list[str]] = mapped_column(JSONB, server_default=text("'[]'::jsonb"))
```

W `api/app/models/user.py` zmień import na `from datetime import date, datetime`, dodaj `Date` do importu z `sqlalchemy` i w klasie `User` po `created_at`:
```python
    valuations_stale_from: Mapped[date | None] = mapped_column(Date)
```

W `api/app/models/instrument.py` zmień import na `from sqlalchemy import DateTime, String, false, func, true` i w klasie `Instrument` po `price_error`:
```python
    # False = the stored price history predates split events; the next update refetches it in full once.
    splits_synced: Mapped[bool] = mapped_column(server_default=true())
```

`api/app/models/__init__.py` — dodaj import i eksporty:
```python
from app.models.valuation import CORPORATE_ACTION_SOURCES, CORPORATE_ACTION_TYPES, CorporateAction, DailyValuation
```
oraz do `__all__`: `"CORPORATE_ACTION_SOURCES"`, `"CORPORATE_ACTION_TYPES"`, `"CorporateAction"`, `"DailyValuation"`.

- [ ] **Step 4: Migracja**

`api/alembic/versions/0004_valuation.py`:
```python
"""valuation: corporate actions, daily valuations cache, stale marker, provider split sync

Revision ID: 0004
Revises: 0003
Create Date: 2026-09-27

"""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects import postgresql

revision: str = "0004"
down_revision: str | None = "0003"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(20, 4)
QUANTITY = sa.Numeric(24, 8)
RATIO = sa.Numeric(18, 8)


def upgrade() -> None:
    op.add_column("users", sa.Column("valuations_stale_from", sa.Date(), nullable=True))
    # Existing instruments were fetched without split events: false makes the next update refetch them in full
    # once. New instruments get their full history on first sight anyway, hence the default true afterwards.
    op.add_column("instruments", sa.Column("splits_synced", sa.Boolean(), server_default=sa.text("false"), nullable=False))
    op.alter_column("instruments", "splits_synced", server_default=sa.text("true"))
    op.create_table(
        "corporate_actions",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=False),
        sa.Column("type", sa.String(length=20), nullable=False),
        sa.Column("effective_date", sa.Date(), nullable=False),
        sa.Column("ratio_from", RATIO, nullable=False),
        sa.Column("ratio_to", RATIO, nullable=False),
        sa.Column("target_instrument_id", sa.Integer(), nullable=True),
        sa.Column("source", sa.String(length=10), nullable=False),
        sa.CheckConstraint("type IN ('split', 'reverse_split', 'conversion')", name=op.f("ck_corporate_actions_type")),
        sa.CheckConstraint("source IN ('manual', 'xtb', 'provider')", name=op.f("ck_corporate_actions_source")),
        sa.CheckConstraint("ratio_from > 0 AND ratio_to > 0", name=op.f("ck_corporate_actions_ratio_positive")),
        sa.ForeignKeyConstraint(
            ["instrument_id"], ["instruments.id"],
            name=op.f("fk_corporate_actions_instrument_id_instruments"), ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["target_instrument_id"], ["instruments.id"],
            name=op.f("fk_corporate_actions_target_instrument_id_instruments"),
        ),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_corporate_actions")),
        sa.UniqueConstraint(
            "instrument_id", "type", "effective_date", "source",
            name=op.f("uq_corporate_actions_instrument_id_type_effective_date_source"),
        ),
    )
    op.create_index(op.f("ix_corporate_actions_instrument_id"), "corporate_actions", ["instrument_id"])
    op.create_table(
        "daily_valuations",
        sa.Column("id", sa.BigInteger(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("instrument_id", sa.Integer(), nullable=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("quantity", QUANTITY, nullable=True),
        sa.Column("value_pln", MONEY, nullable=False),
        sa.Column("cost_pln", MONEY, nullable=False),
        sa.Column("net_flow_pln", MONEY, nullable=False),
        sa.Column("flags", postgresql.JSONB(astext_type=sa.Text()), server_default=sa.text("'[]'::jsonb"), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name=op.f("fk_daily_valuations_user_id_users"), ondelete="CASCADE"),
        sa.ForeignKeyConstraint(
            ["account_id"], ["accounts.id"], name=op.f("fk_daily_valuations_account_id_accounts"), ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(["instrument_id"], ["instruments.id"], name=op.f("fk_daily_valuations_instrument_id_instruments")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_daily_valuations")),
    )
    op.create_index(
        "uq_daily_valuations_account_id_instrument_id_date", "daily_valuations", ["account_id", "instrument_id", "date"],
        unique=True, postgresql_nulls_not_distinct=True,
    )
    op.create_index("ix_daily_valuations_user_id_date", "daily_valuations", ["user_id", "date"])


def downgrade() -> None:
    op.drop_index("ix_daily_valuations_user_id_date", table_name="daily_valuations")
    op.drop_index("uq_daily_valuations_account_id_instrument_id_date", table_name="daily_valuations")
    op.drop_table("daily_valuations")
    op.drop_index(op.f("ix_corporate_actions_instrument_id"), table_name="corporate_actions")
    op.drop_table("corporate_actions")
    op.drop_column("instruments", "splits_synced")
    op.drop_column("users", "valuations_stale_from")
```

- [ ] **Step 5: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_models.py tests/test_models.py -v`
Expected: PASS — 7 testów z `test_valuation_models.py` (3 + 3 parametryzowane + 1) i wszystkie z `test_models.py`, w tym `test_models_match_migrations` (model i migracja zgodne). Jeśli `compare_metadata` zgłosi różnicę tylko dla `postgresql_nulls_not_distinct` indeksu `uq_daily_valuations_…`, sprawdź wersję Alembica (`pip show alembic` w kontenerze) — oba miejsca muszą mieć tę opcję; nie usuwaj jej z modelu.

- [ ] **Step 6: Commit**

```bash
git add api/app/models api/alembic/versions/0004_valuation.py api/tests/test_valuation_models.py
git commit -m "feat(valuation): corporate actions and daily valuations tables" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Splity od dostawcy cen i zapis zmienionych dat

**Files:**
- Modify: `api/app/market/types.py`, `api/app/market/providers/yahoo.py`, `api/app/market/store.py`, `api/app/market/update.py`, `api/tests/market_fakes.py`
- Test: `api/tests/test_yahoo.py`, `api/tests/test_market_store.py`, `api/tests/test_market_update.py`

**Interfaces:**
- Consumes: `CorporateAction`, `Instrument.splits_synced` (Task 1); `PriceHistory`, `update_instrument_prices`, `_update_prices`, `update_all_prices`, `backfill_new_instruments`, `run_market_update`, `UpdateSummary` (plan 3).
- Produces:
  - `SplitEvent(date: dt.date, ratio_from: Decimal, ratio_to: Decimal)` w `app.market.types`; `PriceHistory.splits: tuple[SplitEvent, ...] = ()`.
  - `replace_provider_splits(db, instrument_id: int, splits: Iterable[SplitEvent], since: dt.date | None) -> bool` w `app.market.store` — `True`, gdy coś się zmieniło.
  - `update_instrument_prices(db, provider, instrument, now, changed: dict[int, dt.date] | None = None) -> int`; tak samo opcjonalny `changed` w `_update_prices`, `update_all_prices`, `backfill_new_instruments`. `changed[instrument_id]` = najwcześniejszy dzień, od którego wycena mogła się zmienić (`dt.date.min` = cała historia).
  - `_note(changed, key, day)` w `app.market.update` (zachowuje minimum; `changed=None` = nic nie rób).
  - `UpdateSummary.prices_changed_from: dict[int, dt.date]`, `UpdateSummary.fx_changed_from: dict[str, dt.date]` (to drugie wypełnia Task 3).

- [ ] **Step 1: Testy dostawcy Yahoo**

Dopisz do `api/tests/test_yahoo.py` (import `SplitEvent` z `app.market.types`; `Decimal` i `dt` są już zaimportowane):
```python
NVDA_JUN_10 = 1718026200  # 2024-06-10 13:30 UTC = 09:30 in New York: first session on the 10:1 basis


def _with_split(payload: dict[str, Any], timestamp: int, numerator: Any, denominator: Any) -> dict[str, Any]:
    event = {"date": timestamp, "numerator": numerator, "denominator": denominator, "splitRatio": f"{numerator}:{denominator}"}
    payload["chart"]["result"][0]["events"] = {"splits": {str(timestamp): event}}
    return payload


def test_split_events_are_requested_and_parsed_on_the_exchange_day() -> None:
    payload = _with_split(_chart([NVDA_JUN_10], [121.79], currency="USD", gmtoffset=-14400), NVDA_JUN_10, 10, 1)
    seen: list[httpx.Request] = []

    history = _provider(_serving(payload, seen=seen)).history("NVDA", None)

    assert seen[0].url.params["events"] == "split"
    assert history.splits == (SplitEvent(dt.date(2024, 6, 10), Decimal(1), Decimal(10)),)


def test_response_without_events_has_no_splits() -> None:
    history = _provider(_serving(_chart([SEP_01_0700], [711.72]))).history("SXR8.DE", None)
    assert history.splits == ()


def test_one_to_one_split_is_ignored() -> None:
    payload = _with_split(_chart([NVDA_JUN_10], [121.79], currency="USD", gmtoffset=-14400), NVDA_JUN_10, 1, 1)
    assert _provider(_serving(payload)).history("NVDA", None).splits == ()


def test_malformed_split_event_is_a_provider_error() -> None:
    payload = _with_split(_chart([NVDA_JUN_10], [121.79], currency="USD", gmtoffset=-14400), NVDA_JUN_10, "abc", 1)
    with pytest.raises(ProviderError):
        _provider(_serving(payload)).history("NVDA", None)
```

- [ ] **Step 2: Test zapisu splitów**

Dopisz do `api/tests/test_market_store.py` (import `replace_provider_splits` z `app.market.store`, `SplitEvent` z `app.market.types`, `CorporateAction` z `app.models`):
```python
def _actions(db: Session, instrument_id: int) -> list[tuple]:
    rows = db.scalars(select(CorporateAction).where(CorporateAction.instrument_id == instrument_id)
                      .order_by(CorporateAction.effective_date, CorporateAction.source))
    return [(a.type, a.effective_date, a.ratio_from, a.ratio_to, a.source) for a in rows]


def test_provider_splits_are_replaced_only_inside_the_fetched_window(db: Session) -> None:
    instrument = _instrument(db, "NVDA.US")
    old = SplitEvent(dt.date(2021, 7, 20), Decimal(1), Decimal(4))
    new = SplitEvent(dt.date(2024, 6, 10), Decimal(1), Decimal(10))
    db.add(CorporateAction(instrument_id=instrument.id, type="split", effective_date=dt.date(2024, 6, 10),
                           ratio_from=Decimal(1), ratio_to=Decimal(10), source="manual"))

    assert replace_provider_splits(db, instrument.id, [old, new], None) is True
    assert replace_provider_splits(db, instrument.id, [new], dt.date(2024, 1, 1)) is False
    assert replace_provider_splits(db, instrument.id, [], dt.date(2025, 1, 1)) is False
    db.commit()

    assert _actions(db, instrument.id) == [
        ("split", dt.date(2021, 7, 20), Decimal(1), Decimal(4), "provider"),
        ("split", dt.date(2024, 6, 10), Decimal(1), Decimal(10), "manual"),
        ("split", dt.date(2024, 6, 10), Decimal(1), Decimal(10), "provider"),
    ]


def test_reverse_split_and_changed_ratio_are_detected(db: Session) -> None:
    instrument = _instrument(db, "XYZ.US")
    replace_provider_splits(db, instrument.id, [SplitEvent(dt.date(2025, 3, 3), Decimal(10), Decimal(1))], None)

    changed = replace_provider_splits(db, instrument.id, [SplitEvent(dt.date(2025, 3, 3), Decimal(20), Decimal(1))], None)
    db.commit()

    assert changed is True
    assert _actions(db, instrument.id) == [("reverse_split", dt.date(2025, 3, 3), Decimal(20), Decimal(1), "provider")]
```

- [ ] **Step 3: Testy serwisu aktualizacji**

W `api/tests/market_fakes.py` dodaj import `SplitEvent` i stałą:
```python
NVDA = PriceHistory(
    "NVDA", "USD",
    (PriceBar(dt.date(2024, 6, 7), Decimal("120.89")), PriceBar(dt.date(2024, 6, 10), Decimal("121.79"))),
    splits=(SplitEvent(dt.date(2024, 6, 10), Decimal(1), Decimal(10)),),
)
```

Dopisz do `api/tests/test_market_update.py` (import `NVDA` z `tests.market_fakes`, `CorporateAction` z `app.models`):
```python
def test_price_update_reports_the_earliest_written_day(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE")
    changed: dict[int, dt.date] = {}

    update_all_prices(db, FakePrices({"SXR8.DE": SXR8}), NOW, changed)

    assert changed == {instrument.id: dt.date(2026, 9, 24)}


def test_new_provider_split_is_stored_and_marks_the_whole_history(db: Session) -> None:
    instrument = _instrument(db, "NVDA.US")
    provider = FakePrices({"NVDA": NVDA})
    first: dict[int, dt.date] = {}
    second: dict[int, dt.date] = {}

    update_all_prices(db, provider, NOW, first)
    update_all_prices(db, provider, NOW, second)

    action = db.scalar(select(CorporateAction).where(CorporateAction.instrument_id == instrument.id))
    assert (action.type, action.effective_date, action.ratio_from, action.ratio_to, action.source) == (
        "split", dt.date(2024, 6, 10), Decimal(1), Decimal(10), "provider")
    assert first == {instrument.id: dt.date.min}
    assert second == {instrument.id: dt.date(2024, 6, 7)}


def test_instrument_fetched_before_splits_existed_refetches_full_history_once(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE", splits_synced=False)
    upsert_prices(db, instrument.id, [PriceBar(dt.date(2026, 9, 1), Decimal("700"))], "yahoo")
    db.commit()
    provider = FakePrices({"SXR8.DE": SXR8})

    update_all_prices(db, provider, NOW)
    update_all_prices(db, provider, NOW)

    db.refresh(instrument)
    assert instrument.splits_synced is True
    assert provider.calls == [("SXR8.DE", None), ("SXR8.DE", dt.date(2026, 9, 20))]


def test_changed_currency_marks_the_whole_history(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE", currency="USD")
    upsert_prices(db, instrument.id, [PriceBar(dt.date(2026, 9, 23), Decimal("700"))], "yahoo")
    db.commit()
    changed: dict[int, dt.date] = {}

    update_all_prices(db, FakePrices({"SXR8.DE": SXR8}), NOW, changed)

    assert changed == {instrument.id: dt.date.min}


def test_run_market_update_reports_changed_instruments(db: Session) -> None:
    instrument = _instrument(db, "SXR8.DE")
    summary = run_market_update(db, fake_providers(), NOW, TODAY)
    assert summary.prices_changed_from == {instrument.id: dt.date(2026, 9, 24)}
```

- [ ] **Step 4: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_yahoo.py tests/test_market_store.py tests/test_market_update.py -v`
Expected: FAIL — `ImportError: cannot import name 'SplitEvent' from 'app.market.types'`.

- [ ] **Step 5: Typy i dostawca**

W `api/app/market/types.py` przed `PriceHistory`:
```python
@dataclass(frozen=True)
class SplitEvent:
    """`ratio_from` old shares became `ratio_to` new ones on `date` (first session on the new basis)."""

    date: dt.date
    ratio_from: Decimal
    ratio_to: Decimal
```
i w `PriceHistory` po `bars`:
```python
    splits: tuple[SplitEvent, ...] = ()
```

W `api/app/market/providers/yahoo.py`: import `SplitEvent` z `app.market.types`; w `YahooPriceProvider.history` słownik parametrów:
```python
        params = {
            "period1": period1, "period2": int(time.time()) + ONE_DAY_SECONDS, "interval": "1d", "events": "split",
        }
```
Dodaj funkcję nad `parse_chart`:
```python
def _splits(symbol: str, result: dict[str, Any], offset: int) -> tuple[SplitEvent, ...]:
    events = ((result.get("events") or {}).get("splits") or {}).values()
    splits = []
    for event in events:
        try:
            numerator = Decimal(str(event["numerator"]))
            denominator = Decimal(str(event["denominator"]))
            day = dt.datetime.fromtimestamp(int(event["date"]) + offset, dt.UTC).date()
        except (KeyError, TypeError, ValueError, ArithmeticError) as exc:
            raise ProviderError(f"Yahoo {symbol}: malformed split event") from exc
        if numerator > 0 and denominator > 0 and numerator != denominator:
            splits.append(SplitEvent(day, ratio_from=denominator, ratio_to=numerator))
    return tuple(sorted(splits, key=lambda split: split.date))
```
i w `parse_chart` zmień ostatnią linię:
```python
    return PriceHistory(
        symbol=symbol, currency=currency, bars=tuple(bars[day] for day in sorted(bars)),
        splits=_splits(symbol, result, offset),
    )
```
Uzupełnij docstring klasy `YahooPriceProvider` o zdanie: `Split events come from the same request (events=split).`

- [ ] **Step 6: Zapis splitów**

W `api/app/market/store.py`: import `SplitEvent` z `app.market.types`, `CorporateAction` z `app.models`; dodaj:
```python
def _split_type(split: SplitEvent) -> str:
    return "split" if split.ratio_to > split.ratio_from else "reverse_split"


def replace_provider_splits(
    db: Session, instrument_id: int, splits: Iterable[SplitEvent], since: dt.date | None
) -> bool:
    """Makes the provider's splits of the instrument dated `since` or later (all when None) equal `splits`.

    The provider only reports events inside the fetched window, so older ones are kept. Manual and XTB
    entries are never touched. Returns True when anything was added, removed or changed. Does not commit.
    """
    query = select(CorporateAction).where(
        CorporateAction.instrument_id == instrument_id,
        CorporateAction.source == "provider",
        CorporateAction.type.in_(("split", "reverse_split")),
    )
    if since is not None:
        query = query.where(CorporateAction.effective_date >= since)
    stored = db.scalars(query).all()
    wanted = {(s.date, s.ratio_from, s.ratio_to) for s in splits if since is None or s.date >= since}
    if {(a.effective_date, a.ratio_from, a.ratio_to) for a in stored} == wanted:
        return False
    for action in stored:
        db.delete(action)
    db.flush()
    for day, ratio_from, ratio_to in sorted(wanted):
        split = SplitEvent(day, ratio_from, ratio_to)
        db.add(CorporateAction(instrument_id=instrument_id, type=_split_type(split), effective_date=day,
                               ratio_from=ratio_from, ratio_to=ratio_to, source="provider"))
    db.flush()
    return True
```
(`Decimal("1.00000000") == Decimal(1)`, więc porównanie zbiorów nie zależy od skali z bazy.)

- [ ] **Step 7: Serwis aktualizacji**

W `api/app/market/update.py`: import `replace_provider_splits` z `app.market.store`. Dodaj pomocniczą funkcję nad `resolve_symbol`:
```python
def _note(changed: dict[Any, dt.date] | None, key: Any, day: dt.date) -> None:
    """Remembers the earliest day from which valuations depending on `key` may have changed."""
    if changed is not None:
        changed[key] = min(day, changed.get(key, day))
```
(dodaj `from typing import Any`). W `UpdateSummary` dopisz pola:
```python
    prices_changed_from: dict[int, dt.date] = field(default_factory=dict)
    fx_changed_from: dict[str, dt.date] = field(default_factory=dict)
```
Zastąp `update_instrument_prices`:
```python
def update_instrument_prices(
    db: Session, provider: PriceProvider, instrument: Instrument, now: dt.datetime,
    changed: dict[int, dt.date] | None = None,
) -> int:
    """Fetches missing prices of one instrument: full history on first sight, then from the last stored day.

    The instrument list is loaded once per run and kept as a plain Python list for its whole duration, so a
    PATCH committed by another session after the list was loaded would otherwise go unseen (the session's
    identity map keeps serving the pre-PATCH copy). `db.refresh(..., with_for_update=True)` reloads the
    current symbol/override/checked-at and holds the row lock until the caller's per-instrument commit.

    An instrument whose history predates split events (`splits_synced` False) is fetched in full once.
    Provider splits inside the fetched window replace the stored ones. `changed[instrument.id]` gets the
    earliest day whose valuation may differ: the first bar written, or the whole history (`date.min`) when
    a split or the quote currency changed.

    Provider problems end up in `instrument.price_error` (Polish, shown in the UI) and are never raised.
    Does not commit.
    """
    db.refresh(instrument, with_for_update=True)
    instrument.price_checked_at = now
    symbol = resolve_symbol(provider, instrument)
    if symbol is None:
        instrument.price_error = MSG_UNMAPPED
        return 0
    last = last_price_date(db, instrument.id)
    full = last is None or not instrument.splits_synced
    start = None if full else last - dt.timedelta(days=PRICE_OVERLAP_DAYS)
    try:
        history = provider.history(symbol, start)
    except SymbolNotFound:
        instrument.price_error = MSG_NOT_FOUND.format(symbol=symbol)[:ERROR_MAX_LENGTH]
        logger.warning("Price provider does not know %s (instrument %s)", symbol, instrument.xtb_ticker)
        return 0
    except ProviderError as exc:
        instrument.price_error = MSG_FAILED.format(symbol=symbol)[:ERROR_MAX_LENGTH]
        logger.warning("Price update failed for %s (%s): %s", instrument.xtb_ticker, symbol, exc)
        return 0
    currency_changed = instrument.currency is not None and instrument.currency != history.currency
    instrument.currency = history.currency
    instrument.price_error = None
    instrument.splits_synced = True
    splits_changed = replace_provider_splits(db, instrument.id, history.splits, start)
    if splits_changed or currency_changed:
        _note(changed, instrument.id, dt.date.min)
    elif history.bars:
        _note(changed, instrument.id, history.bars[0].date)
    return upsert_prices(db, instrument.id, history.bars, provider.name)
```
W `_update_prices` dodaj parametr `changed: dict[int, dt.date] | None = None` i przekaż go: `rows += update_instrument_prices(db, provider, instrument, now, changed)`. W `update_all_prices` i `backfill_new_instruments` dodaj ten sam ostatni parametr `changed: dict[int, dt.date] | None = None` i przekaż do `_update_prices(db, provider, instruments, now, changed)`. W `run_market_update` pierwsza linia po `summary = UpdateSummary()`:
```python
    summary.price_rows, summary.failed_instruments = update_all_prices(
        db, providers.prices, now, summary.prices_changed_from
    )
```

- [ ] **Step 8: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest -v`
Expected: PASS — cały zestaw, w tym 4 nowe testy w `test_yahoo.py`, 2 w `test_market_store.py`, 5 w `test_market_update.py`; wcześniejsze testy serwisu przechodzą bez zmian (nowe instrumenty mają `splits_synced = true`).

- [ ] **Step 9: Commit**

```bash
git add api/app/market api/tests/market_fakes.py api/tests/test_yahoo.py api/tests/test_market_store.py api/tests/test_market_update.py
git commit -m "feat(market): provider split events and changed-from dates for revaluation" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Kursy NBP także dla walut kont i transakcji

**Files:**
- Modify: `api/app/market/update.py`
- Test: `api/tests/test_market_update.py`

**Interfaces:**
- Consumes: `_note`, `UpdateSummary.fx_changed_from` (Task 2); `update_fx`, `fx_ranges_to_fetch`, `fx_needed_from` (plan 3).
- Produces: `fx_currencies(db) -> list[str]` (waluty notowania instrumentów, do których są odwołania, ∪ waluty transakcji, bez PLN, posortowane); `update_fx(db, provider, today, changed: dict[str, dt.date] | None = None) -> tuple[int, list[str]]` — `changed[waluta]` = początek najwcześniejszego pobranego zakresu, gdy coś zapisano.

- [ ] **Step 1: Napisz testy**

Dopisz do `api/tests/test_market_update.py` (import `fx_currencies` z `app.market.update`):
```python
def test_fx_covers_currencies_of_foreign_currency_accounts(db: Session) -> None:
    user = User(email="usd@portfolio.dev", password_hash="x")
    db.add(user)
    db.flush()
    account = Account(user_id=user.id, name="XTB USD", kind="broker", wrapper="regular", broker="xtb",
                      external_account_number="99", currency="USD")
    db.add(account)
    db.flush()
    db.add(Transaction(account_id=account.id, type="deposit", xtb_type="Deposit",
                       occurred_at=dt.datetime(2026, 9, 1, tzinfo=dt.UTC), amount=Decimal("100"), currency="USD",
                       external_id="1", comment="", raw={}))
    _instrument(db, "SXR8.DE", currency="EUR")

    assert fx_currencies(db) == ["EUR", "USD"]


def test_fx_update_reports_the_earliest_fetched_day(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")
    _first_transaction_at(db, dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.UTC))
    changed: dict[str, dt.date] = {}

    update_fx(db, FakeFx(), TODAY, changed)

    assert changed == {"EUR": dt.date(2026, 9, 1) - dt.timedelta(days=FX_MARGIN_DAYS)}


def test_fx_without_new_rows_reports_nothing(db: Session) -> None:
    _instrument(db, "SXR8.DE", currency="EUR")
    upsert_fx_rates(db, "EUR", [FxPoint(TODAY - dt.timedelta(days=30), Decimal("4.3")), FxPoint(TODAY, Decimal("4.2"))])
    db.commit()
    changed: dict[str, dt.date] = {}

    update_fx(db, FakeFx(), TODAY, changed)

    assert changed == {}
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_market_update.py -v`
Expected: FAIL — `ImportError: cannot import name 'fx_currencies'`.

- [ ] **Step 3: Implementacja**

W `api/app/market/update.py` dodaj nad `update_fx`:
```python
def fx_currencies(db: Session) -> list[str]:
    """Quote currencies of referenced instruments and currencies of transactions (= account currencies:
    cash held in USD/EUR on an XTB account needs rates too)."""
    quoted = db.scalars(
        select(Instrument.currency).where(Instrument.currency.is_not(None), _referenced()).distinct()
    )
    booked = db.scalars(select(Transaction.currency).distinct())
    return sorted((set(quoted) | set(booked)) - {BASE_CURRENCY})
```
i zastąp `update_fx`:
```python
def update_fx(
    db: Session, provider: FxProvider, today: dt.date, changed: dict[str, dt.date] | None = None
) -> tuple[int, list[str]]:
    needed_from = fx_needed_from(db, today)
    rows, failed = 0, []
    for currency in fx_currencies(db):
        stored_min, stored_max = fx_date_bounds(db, currency)
        ranges = fx_ranges_to_fetch(stored_min, stored_max, needed_from, today)
        try:
            written = sum(upsert_fx_rates(db, currency, provider.rates(currency, start, end)) for start, end in ranges)
        except ProviderError as exc:
            db.rollback()
            failed.append(currency)
            logger.warning("FX update failed for %s: %s", currency, exc)
            continue
        except Exception:
            db.rollback()
            failed.append(currency)
            logger.exception("FX update crashed for %s", currency)
            continue
        db.commit()
        rows += written
        if written:
            _note(changed, currency, ranges[0][0])
    return rows, failed
```
W `run_market_update`:
```python
    summary.fx_rows, summary.failed_currencies = update_fx(db, providers.fx, today, summary.fx_changed_from)
```

- [ ] **Step 4: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest tests/test_market_update.py tests/test_worker.py -v`
Expected: PASS — 3 nowe testy i wszystkie dotychczasowe (np. `test_unreferenced_instrument_currency_is_excluded_from_fx` dalej przechodzi: transakcje w tym teście są w PLN).

- [ ] **Step 5: Commit**

```bash
git add api/app/market/update.py api/tests/test_market_update.py
git commit -m "feat(market): fetch NBP rates for account and transaction currencies" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: Silnik wyceny — dane rynkowe w pamięci i księga transakcji

**Files:**
- Create: `api/app/valuation/__init__.py` (pusty), `api/app/valuation/market_data.py`, `api/app/valuation/engine.py`
- Test: `api/tests/test_valuation_engine_book.py`

**Interfaces:**
- Consumes: nic z bazy (czyste funkcje, spec §3 zasada 4).
- Produces (używane w Task 5, 6, 9):
  - `market_data.BASE_CURRENCY = "PLN"`; `Series(points: Iterable[tuple[date, Decimal]] = ())` z metodami `add(day, value)`, `on(day) -> tuple[date, Decimal] | None` (ostatni ≤ dzień), `near(day)` (ostatni ≤ dzień, inaczej pierwszy); atrybuty `days`, `values`.
  - `MarketData(prices: dict[int, Series], currencies: dict[int, str | None], fx: dict[str, Series], snapshots: dict[tuple[int, int], Series])` z metodami `price(instrument_id, day) -> tuple[date, Decimal] | None`, `rate(currency: str | None, day) -> Decimal | None`.
  - `engine.Entry(id, account_id, instrument_id, type, day, amount, currency, quantity=None, price=None, position_id=None)`; `engine.Split(instrument_id, effective_date, ratio_from, ratio_to)` z własnością `factor`; `engine.Lot` (`key`, `position_id`, `opened_on`, `quantity` w bieżących jednostkach, `cost_pln`, `fx_open`); `engine.Sale` (`account_id`, `instrument_id`, `day`, `quantity`, `proceeds_pln`, `cost_pln`, `position_id`, `matched`, własność `realized_pln`).
  - `engine.Book(splits, market)`: `apply(entry)`, `factor(instrument_id, day) -> Decimal`, `to_pln(amount, currency, day) -> Decimal`; stan: `lots: dict[(account_id, instrument_id), dict[str, Lot]]`, `cash: dict[account_id, Decimal]` (waluta konta), `account_currency: dict[int, str]`, `flows: dict[(account_id, day), Decimal]` (PLN), `dividends`, `withholding: dict[(account_id, instrument_id), Decimal]` (PLN), `sales: list[Sale]`, `trades: dict[(account_id, instrument_id), Series]` (PLN za bieżącą jednostkę).
  - `engine.money(value) -> Decimal` (grosze, `ROUND_HALF_UP`), stałe `ZERO`, `ONE_DAY`.

- [ ] **Step 1: Napisz testy**

`api/tests/test_valuation_engine_book.py`:
```python
import datetime as dt
from decimal import Decimal as D

from app.valuation.engine import Book, Entry, Split
from app.valuation.market_data import MarketData, Series

MAR_01, MAR_02, MAR_05, JUN_01 = dt.date(2026, 3, 1), dt.date(2026, 3, 2), dt.date(2026, 3, 5), dt.date(2026, 6, 1)
ACCOUNT, USD_ACCOUNT, SXR8 = 1, 2, 1


def _market() -> MarketData:
    return MarketData(
        currencies={SXR8: "EUR"},
        fx={"EUR": Series([(MAR_02, D("4.30"))]), "USD": Series([(MAR_01, D("4.00"))])},
    )


def _entry(
    id_: int, type_: str, day: dt.date, amount: str, *, account: int = ACCOUNT, instrument: int | None = None,
    quantity: str | None = None, position: str | None = None, currency: str = "PLN",
) -> Entry:
    return Entry(id=id_, account_id=account, instrument_id=instrument, type=type_, day=day, amount=D(amount),
                 currency=currency, quantity=None if quantity is None else D(quantity), position_id=position)


def _buy(id_: int, day: dt.date, quantity: str, amount: str, position: str | None = None, **kw: object) -> Entry:
    return _entry(id_, "buy", day, amount, instrument=SXR8, quantity=quantity, position=position, **kw)


def _sell(id_: int, day: dt.date, quantity: str, amount: str, position: str | None = None) -> Entry:
    return _entry(id_, "sell", day, amount, instrument=SXR8, quantity=quantity, position=position)


def _book(*entries: Entry, splits: tuple[Split, ...] = ()) -> Book:
    book = Book(splits, _market())
    for entry in entries:
        book.apply(entry)
    return book


def _lots(book: Book, account: int = ACCOUNT) -> dict[str, tuple[D, D]]:
    return {key: (lot.quantity, lot.cost_pln) for key, lot in book.lots[(account, SXR8)].items()}


def test_buy_opens_a_lot_costed_at_the_cash_amount_with_the_rate_of_its_day() -> None:
    book = _book(_entry(1, "deposit", MAR_01, "10000"), _buy(2, MAR_02, "2", "-4304.30", "777"))

    lot = book.lots[(ACCOUNT, SXR8)]["777"]
    assert (lot.quantity, lot.cost_pln, lot.fx_open, lot.opened_on, lot.position_id) == (
        D("2"), D("4304.30"), D("4.30"), MAR_02, "777")
    assert book.cash[ACCOUNT] == D("5695.70")
    assert dict(book.flows) == {(ACCOUNT, MAR_01): D("10000")}


def test_buys_without_position_id_get_separate_lots() -> None:
    book = _book(_buy(1, MAR_02, "1", "-2150"), _buy(2, MAR_05, "1", "-2200"))
    assert _lots(book) == {"tx-1": (D("1"), D("2150")), "tx-2": (D("1"), D("2200"))}


def test_sale_is_matched_to_its_lot_by_position_id() -> None:
    book = _book(
        _buy(1, MAR_02, "2", "-4304.30", "777"), _buy(2, MAR_05, "1", "-2200.00", "778"),
        _sell(3, JUN_01, "1", "2600.00", "777"),
    )

    assert _lots(book) == {"777": (D("1"), D("2152.15")), "778": (D("1"), D("2200.00"))}
    (sale,) = book.sales
    assert (sale.cost_pln, sale.realized_pln, sale.matched, sale.quantity) == (D("2152.15"), D("447.85"), True, D("1"))


def test_sale_without_position_id_takes_the_cost_from_all_lots_pro_rata() -> None:
    book = _book(
        _buy(1, MAR_02, "2", "-4304.30", "777"), _buy(2, MAR_05, "1", "-2200.00", "778"),
        _sell(3, JUN_01, "1.5", "3300.00"),
    )

    assert _lots(book) == {"777": (D("1"), D("2152.15")), "778": (D("0.5"), D("1100.00"))}
    (sale,) = book.sales
    assert (sale.cost_pln, sale.realized_pln, sale.matched) == (D("3252.15"), D("47.85"), False)


def test_sale_larger_than_the_holding_closes_everything_without_error() -> None:
    book = _book(_buy(1, MAR_02, "2", "-4304.30", "777"), _sell(2, JUN_01, "3", "6000.00", "777"))

    assert _lots(book) == {}
    (sale,) = book.sales
    assert (sale.cost_pln, sale.realized_pln, sale.matched) == (D("4304.30"), D("1695.70"), False)


def test_quantities_are_kept_in_current_units_across_a_split() -> None:
    split = Split(SXR8, dt.date(2024, 6, 10), D(1), D(10))
    book = _book(
        _buy(1, dt.date(2024, 6, 3), "1", "-4800", "1"), _sell(2, dt.date(2024, 6, 20), "5", "2500", "1"),
        splits=(split,),
    )

    assert book.factor(SXR8, dt.date(2024, 6, 9)) == D(10)
    assert book.factor(SXR8, dt.date(2024, 6, 10)) == D(1)
    assert _lots(book) == {"1": (D("5"), D("2400"))}
    assert book.sales[0].cost_pln == D("2400")
    assert book.sales[0].matched is True


def test_cash_flows_and_income_are_booked_separately() -> None:
    book = _book(
        _entry(1, "deposit", MAR_01, "1000"),
        _entry(2, "transfer_out", MAR_02, "-200"),
        _entry(3, "withdrawal", MAR_02, "-100"),
        _entry(4, "dividend", JUN_01, "40", instrument=SXR8),
        _entry(5, "withholding_tax", JUN_01, "-6", instrument=SXR8),
        _entry(6, "interest", JUN_01, "1.5"),
        _entry(7, "fee", JUN_01, "-2"),
        _entry(8, "unknown", JUN_01, "3"),
    )

    assert book.cash[ACCOUNT] == D("736.5")
    assert dict(book.flows) == {(ACCOUNT, MAR_01): D("1000"), (ACCOUNT, MAR_02): D("-300")}
    assert book.dividends[(ACCOUNT, SXR8)] == D("40")
    assert book.withholding[(ACCOUNT, SXR8)] == D("-6")


def test_foreign_currency_account_converts_flows_and_costs_at_the_nbp_rate() -> None:
    book = _book(
        _entry(1, "deposit", MAR_01, "100", account=USD_ACCOUNT, currency="USD"),
        _buy(2, MAR_02, "1", "-50", "9", account=USD_ACCOUNT, currency="USD"),
    )

    assert book.flows[(USD_ACCOUNT, MAR_01)] == D("400.00")
    assert book.lots[(USD_ACCOUNT, SXR8)]["9"].cost_pln == D("200.00")
    assert book.cash[USD_ACCOUNT] == D("50")
    assert book.account_currency[USD_ACCOUNT] == "USD"


def test_series_lookups() -> None:
    series = Series([(MAR_05, D("2")), (MAR_02, D("1")), (MAR_05, D("3"))])
    assert series.on(MAR_01) is None
    assert series.near(MAR_01) == (MAR_02, D("1"))
    assert series.on(JUN_01) == (MAR_05, D("3"))
    series.add(JUN_01, D("4"))
    assert series.on(JUN_01) == (JUN_01, D("4"))
    assert MarketData().rate("PLN", MAR_01) == D(1)
    assert MarketData().rate(None, MAR_01) is None
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_engine_book.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.valuation'`.

- [ ] **Step 3: Dane rynkowe w pamięci**

`api/app/valuation/__init__.py` — pusty plik.

`api/app/valuation/market_data.py`:
```python
import datetime as dt
from bisect import bisect_right
from collections.abc import Iterable
from dataclasses import dataclass, field
from decimal import Decimal

BASE_CURRENCY = "PLN"


class Series:
    """Values by day; a later point for the same day replaces an earlier one."""

    def __init__(self, points: Iterable[tuple[dt.date, Decimal]] = ()) -> None:
        by_day = dict(points)
        self.days = sorted(by_day)
        self.values = [by_day[day] for day in self.days]

    def add(self, day: dt.date, value: Decimal) -> None:
        """Appends a point; `day` must not be earlier than the last one (a replay only moves forward)."""
        if self.days and self.days[-1] == day:
            self.values[-1] = value
        else:
            self.days.append(day)
            self.values.append(value)

    def on(self, day: dt.date) -> tuple[dt.date, Decimal] | None:
        """The last point on or before `day`."""
        index = bisect_right(self.days, day)
        return (self.days[index - 1], self.values[index - 1]) if index else None

    def near(self, day: dt.date) -> tuple[dt.date, Decimal] | None:
        """The last point on or before `day`, otherwise the first one after it."""
        found = self.on(day)
        if found is None and self.days:
            return self.days[0], self.values[0]
        return found


@dataclass
class MarketData:
    """Everything the engine looks up, preloaded: one query per table instead of one per day."""

    prices: dict[int, Series] = field(default_factory=dict)  # close in the quote currency, split-adjusted
    currencies: dict[int, str | None] = field(default_factory=dict)  # quote currency per instrument
    fx: dict[str, Series] = field(default_factory=dict)  # NBP table A mid: PLN per unit
    # XTB Open Positions value per unit, in the account currency and in units of the snapshot day
    snapshots: dict[tuple[int, int], Series] = field(default_factory=dict)

    def price(self, instrument_id: int, day: dt.date) -> tuple[dt.date, Decimal] | None:
        series = self.prices.get(instrument_id)
        return series.on(day) if series else None

    def rate(self, currency: str | None, day: dt.date) -> Decimal | None:
        """PLN per unit: the last NBP rate on or before `day`, or the first one after it when the stored
        history starts later (the worker fetches from 10 days before the first transaction). PLN is 1."""
        if currency is None:
            return None
        if currency == BASE_CURRENCY:
            return Decimal(1)
        series = self.fx.get(currency)
        found = series.near(day) if series else None
        return found[1] if found else None
```

- [ ] **Step 4: Księga transakcji**

`api/app/valuation/engine.py`:
```python
"""Valuation engine: pure functions over transactions, splits and preloaded market data (no database, no HTTP).

Quantities are kept in *current units* — the basis of the provider's split-adjusted closes (Yahoo `close`,
verified on NVDA 10:1). A quantity traded on day D becomes `quantity × factor(D)`, where factor(D) multiplies
all splits effective after D; a quantity shown "as of day D" is divided back by factor(D).
"""
import datetime as dt
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

from app.valuation.market_data import MarketData, Series

ZERO = Decimal(0)
ONE = Decimal(1)
CENT = Decimal("0.01")
ONE_DAY = dt.timedelta(days=1)
EXTERNAL_FLOWS = frozenset({"deposit", "withdrawal", "transfer_in", "transfer_out"})

Key = tuple[int, int]  # (account_id, instrument_id)


def money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Entry:
    """One transaction as the engine sees it; `amount` is in the account currency `currency`."""

    id: int
    account_id: int
    instrument_id: int | None
    type: str
    day: dt.date
    amount: Decimal
    currency: str
    quantity: Decimal | None = None
    price: Decimal | None = None
    position_id: str | None = None


@dataclass(frozen=True)
class Split:
    instrument_id: int
    effective_date: dt.date  # first day on the new basis
    ratio_from: Decimal
    ratio_to: Decimal

    @property
    def factor(self) -> Decimal:
        return self.ratio_to / self.ratio_from


@dataclass
class Lot:
    key: str
    position_id: str | None
    opened_on: dt.date
    quantity: Decimal  # current units
    cost_pln: Decimal
    fx_open: Decimal | None  # NBP rate of the quote currency on the purchase day


@dataclass(frozen=True)
class Sale:
    account_id: int
    instrument_id: int
    day: dt.date
    quantity: Decimal  # as traded
    proceeds_pln: Decimal
    cost_pln: Decimal
    position_id: str | None
    matched: bool  # the whole quantity came from the lot named by position_id

    @property
    def realized_pln(self) -> Decimal:
        return self.proceeds_pln - self.cost_pln


class Book:
    """Replays transactions in date order and keeps lots, cash, external flows, income and sales."""

    def __init__(self, splits: Iterable[Split], market: MarketData) -> None:
        self.market = market
        self.splits: dict[int, list[Split]] = defaultdict(list)
        for split in splits:
            self.splits[split.instrument_id].append(split)
        self.lots: dict[Key, dict[str, Lot]] = defaultdict(dict)
        self.cash: dict[int, Decimal] = {}
        self.account_currency: dict[int, str] = {}
        self.flows: dict[tuple[int, dt.date], Decimal] = defaultdict(Decimal)
        self.dividends: dict[Key, Decimal] = defaultdict(Decimal)
        self.withholding: dict[Key, Decimal] = defaultdict(Decimal)
        self.sales: list[Sale] = []
        self.trades: dict[Key, Series] = {}

    def factor(self, instrument_id: int, day: dt.date) -> Decimal:
        """How many current units one unit held on `day` has become."""
        result = ONE
        for split in self.splits.get(instrument_id, ()):
            if split.effective_date > day:
                result *= split.factor
        return result

    def to_pln(self, amount: Decimal, currency: str, day: dt.date) -> Decimal:
        """An account-currency amount in PLN. Without any NBP rate for the currency the amount counts as 0;
        the account's cash rows are flagged `fx_missing` until the worker has fetched the rates."""
        rate = self.market.rate(currency, day)
        return amount * rate if rate is not None else ZERO

    def apply(self, entry: Entry) -> None:
        self.account_currency.setdefault(entry.account_id, entry.currency)
        self.cash[entry.account_id] = self.cash.get(entry.account_id, ZERO) + entry.amount
        if entry.type in EXTERNAL_FLOWS:
            self.flows[(entry.account_id, entry.day)] += self.to_pln(entry.amount, entry.currency, entry.day)
        if entry.instrument_id is None:
            return
        key = (entry.account_id, entry.instrument_id)
        if entry.type == "dividend":
            self.dividends[key] += self.to_pln(entry.amount, entry.currency, entry.day)
        elif entry.type == "withholding_tax":
            self.withholding[key] += self.to_pln(entry.amount, entry.currency, entry.day)
        elif entry.type == "buy" and entry.quantity:
            self._buy(key, entry)
        elif entry.type == "sell" and entry.quantity:
            self._sell(key, entry)

    def _record_trade(self, key: Key, day: dt.date, unit_pln: Decimal) -> None:
        self.trades.setdefault(key, Series()).add(day, unit_pln)

    def _buy(self, key: Key, entry: Entry) -> None:
        assert entry.quantity is not None and entry.instrument_id is not None
        quantity = entry.quantity * self.factor(entry.instrument_id, entry.day)
        cost = -self.to_pln(entry.amount, entry.currency, entry.day)
        lot_key = entry.position_id or f"tx-{entry.id}"
        lots = self.lots[key]
        lot = lots.get(lot_key)
        if lot is None:
            fx_open = self.market.rate(self.market.currencies.get(entry.instrument_id), entry.day)
            lots[lot_key] = Lot(lot_key, entry.position_id, entry.day, quantity, cost, fx_open)
        else:
            lot.quantity += quantity
            lot.cost_pln += cost
        self._record_trade(key, entry.day, cost / quantity)

    def _sell(self, key: Key, entry: Entry) -> None:
        assert entry.quantity is not None and entry.instrument_id is not None
        quantity = entry.quantity * self.factor(entry.instrument_id, entry.day)
        proceeds = self.to_pln(entry.amount, entry.currency, entry.day)
        lots = self.lots[key]
        target = lots.get(entry.position_id) if entry.position_id else None
        matched = target is not None and target.quantity >= quantity
        cost, remaining = ZERO, quantity
        if target is not None:
            taken = min(remaining, target.quantity)
            cost += self._take(lots, target, taken)
            remaining -= taken
        if remaining > 0:
            cost += self._take_pro_rata(lots, remaining)
        self.sales.append(Sale(entry.account_id, entry.instrument_id, entry.day, entry.quantity, proceeds, cost,
                               entry.position_id, matched))
        self._record_trade(key, entry.day, proceeds / quantity)

    @staticmethod
    def _take(lots: dict[str, Lot], lot: Lot, quantity: Decimal) -> Decimal:
        cost = lot.cost_pln * quantity / lot.quantity
        lot.quantity -= quantity
        lot.cost_pln -= cost
        if lot.quantity <= 0:
            del lots[lot.key]
        return cost

    def _take_pro_rata(self, lots: dict[str, Lot], quantity: Decimal) -> Decimal:
        """A sale without (enough of) a matching lot is taken from all open lots in proportion (average cost)."""
        held = sum((lot.quantity for lot in lots.values()), ZERO)
        if held <= 0:
            return ZERO
        share = min(quantity, held) / held
        return sum((self._take(lots, lot, lot.quantity * share) for lot in list(lots.values())), ZERO)
```

- [ ] **Step 5: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_engine_book.py -v`
Expected: PASS — 9 testów.

- [ ] **Step 6: Commit**

```bash
git add api/app/valuation api/tests/test_valuation_engine_book.py
git commit -m "feat(valuation): ledger replay with lots, pro-rata sales, splits, cash and flows" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Silnik wyceny — wycena dnia, rozbicie zysku, wiersze dzienne

**Files:**
- Modify: `api/app/valuation/engine.py`
- Test: `api/tests/test_valuation_engine_rows.py`

**Interfaces:**
- Consumes: `Book`, `Entry`, `Split`, `Lot`, `money`, `ZERO`, `ONE_DAY` (Task 4); `MarketData`, `BASE_CURRENCY` (Task 4).
- Produces (używane w Task 6, 9):
  - `FLAG_XTB_PRICE = "xtb_price"`, `FLAG_FX_MISSING = "fx_missing"`, `SOURCE_PROVIDER = "provider"`, `SOURCE_XTB = "xtb"`.
  - `Quote(unit_pln, price: Decimal | None, price_date: date, rate: Decimal | None, source: str)`.
  - `LotView(position_id, opened_on, quantity, open_price: Decimal | None, cost_pln, value_pln, price_effect_pln, fx_effect_pln)` — ilość i cena zakupu w jednostkach dnia wyceny.
  - `PositionView(account_id, instrument_id, day, quantity, cost_pln, value_pln, price_effect_pln, fx_effect_pln, quote: Quote | None, lots: tuple[LotView, ...], flags: tuple[str, ...])`.
  - `Row(account_id, instrument_id: int | None, day, quantity: Decimal | None, value_pln, cost_pln, net_flow_pln, flags: tuple[str, ...])`.
  - Metody `Book`: `quote(account_id, instrument_id, day) -> Quote | None`, `position(account_id, instrument_id, day) -> PositionView | None`, `cash_row(account_id, day) -> Row`, `rows(day) -> list[Row]`, `day_change(account_id, instrument_id, session, previous) -> Decimal`.
  - Funkcje: `replay(entries, splits, market, until: date) -> Book`, `daily_rows(entries, splits, market, end: date) -> list[Row]`, `last_session(day) -> date`, `previous_session(day) -> date`.

- [ ] **Step 1: Napisz testy**

`api/tests/test_valuation_engine_rows.py`:
```python
import datetime as dt
from decimal import Decimal as D

from app.valuation.engine import (
    FLAG_FX_MISSING,
    FLAG_XTB_PRICE,
    SOURCE_PROVIDER,
    SOURCE_XTB,
    Entry,
    Split,
    daily_rows,
    last_session,
    previous_session,
    replay,
)
from app.valuation.market_data import MarketData, Series

SXR8, NOPRICE, NVDA = 1, 2, 3
MAR_01, MAR_02, MAR_03 = dt.date(2026, 3, 1), dt.date(2026, 3, 2), dt.date(2026, 3, 3)
SEP_10, SEP_20 = dt.date(2026, 9, 10), dt.date(2026, 9, 20)
THU, FRI, SAT = dt.date(2026, 9, 24), dt.date(2026, 9, 25), dt.date(2026, 9, 26)
JUN_07, JUN_10 = dt.date(2024, 6, 7), dt.date(2024, 6, 10)

DEPOSIT = Entry(1, 1, None, "deposit", MAR_01, D("10000"), "PLN")
BUY = Entry(2, 1, SXR8, "buy", MAR_02, D("-4304.30"), "PLN", D("2"), D("500.5"), "777")


def _market() -> MarketData:
    return MarketData(
        prices={
            SXR8: Series([(MAR_02, D("500.00")), (FRI, D("600.00"))]),
            NVDA: Series([(JUN_07, D("120.00")), (JUN_10, D("121.00"))]),
        },
        currencies={SXR8: "EUR", NOPRICE: None, NVDA: "USD"},
        fx={"EUR": Series([(MAR_02, D("4.30")), (FRI, D("4.25"))]), "USD": Series([(dt.date(2024, 6, 3), D("4.00"))])},
        snapshots={(1, NOPRICE): Series([(SEP_20, D("120"))])},
    )


def test_position_value_splits_into_price_and_currency_effects() -> None:
    view = replay([DEPOSIT, BUY], [], _market(), FRI).position(1, SXR8, FRI)

    assert view is not None
    assert (view.quantity, view.value_pln, view.cost_pln) == (D("2"), D("5100.00"), D("4304.30"))
    assert (view.price_effect_pln, view.fx_effect_pln, view.flags) == (D("855.70"), D("-60.00"), ())
    assert view.quote is not None
    assert (view.quote.price, view.quote.price_date, view.quote.rate, view.quote.source) == (
        D("600.00"), FRI, D("4.25"), SOURCE_PROVIDER)
    (lot,) = view.lots
    assert (lot.position_id, lot.open_price, lot.value_pln, lot.price_effect_pln) == ("777", D("500.5"), D("5100.00"), D("855.70"))


def test_weekend_is_valued_with_the_last_session() -> None:
    view = replay([DEPOSIT, BUY], [], _market(), SAT).position(1, SXR8, SAT)
    assert view is not None and view.value_pln == D("5100.00") and view.quote.price_date == FRI


def test_missing_provider_price_falls_back_to_the_newest_xtb_value() -> None:
    buy = Entry(3, 1, NOPRICE, "buy", MAR_02, D("-400"), "PLN", D("4"), D("100"), "5")
    book = replay([buy], [], _market(), FRI)

    latest = book.position(1, NOPRICE, FRI)
    earlier = book.position(1, NOPRICE, SEP_10)

    assert latest is not None and earlier is not None
    assert (latest.value_pln, latest.flags, latest.quote.source, latest.quote.price) == (
        D("480.00"), (FLAG_XTB_PRICE,), SOURCE_XTB, None)
    assert (latest.quote.price_date, latest.fx_effect_pln, latest.price_effect_pln) == (SEP_20, D("0.00"), D("80.00"))
    assert (earlier.value_pln, earlier.quote.price_date) == (D("400.00"), MAR_02)


def test_split_keeps_the_value_continuous_and_shows_the_quantity_of_the_day() -> None:
    split = Split(NVDA, JUN_10, D(1), D(10))
    buy = Entry(4, 1, NVDA, "buy", dt.date(2024, 6, 3), D("-4800"), "PLN", D("1"), D("1200"), "1")
    book = replay([buy], [split], _market(), JUN_10)

    before, after = book.position(1, NVDA, JUN_07), book.position(1, NVDA, JUN_10)

    assert before is not None and after is not None
    assert (before.quantity, before.value_pln, before.lots[0].open_price) == (D("1"), D("4800.00"), D("1200"))
    assert (after.quantity, after.value_pln, after.lots[0].open_price) == (D("10"), D("4840.00"), D("120"))


def test_daily_rows_cover_every_day_with_cash_and_open_positions() -> None:
    rows = daily_rows([DEPOSIT, BUY], [], _market(), MAR_03)

    assert [(r.day, r.instrument_id, r.value_pln, r.net_flow_pln) for r in rows] == [
        (MAR_01, None, D("10000.00"), D("10000.00")),
        (MAR_02, None, D("5695.70"), D("0.00")),
        (MAR_02, SXR8, D("4300.00"), D("0")),
        (MAR_03, None, D("5695.70"), D("0.00")),
        (MAR_03, SXR8, D("4300.00"), D("0")),
    ]
    position = rows[2]
    assert (position.quantity, position.cost_pln, position.flags) == (D("2"), D("4304.30"), ())
    assert (rows[0].quantity, rows[0].cost_pln) == (D("10000"), D("10000.00"))


def test_sold_out_position_has_no_rows_after_the_sale() -> None:
    sell = Entry(5, 1, SXR8, "sell", MAR_03, D("4400"), "PLN", D("2"), D("510"), "777")
    rows = daily_rows([DEPOSIT, BUY, sell], [], _market(), MAR_03)
    assert [(r.instrument_id, r.value_pln) for r in rows if r.day == MAR_03] == [(None, D("10095.70"))]


def test_cash_of_an_account_without_rates_is_flagged() -> None:
    deposit = Entry(6, 2, None, "deposit", MAR_01, D("100"), "CHF")
    (row,) = daily_rows([deposit], [], _market(), MAR_01)
    assert (row.quantity, row.value_pln, row.flags) == (D("100"), D("0"), (FLAG_FX_MISSING,))


def test_day_change_compares_the_quotes_of_two_sessions() -> None:
    book = replay([DEPOSIT, BUY], [], _market(), SAT)
    assert book.day_change(1, SXR8, FRI, THU) == D("800.00")
    assert book.day_change(1, NOPRICE, FRI, THU) == D("0")


def test_sessions_skip_weekends() -> None:
    assert last_session(SAT) == FRI
    assert last_session(FRI) == FRI
    assert previous_session(dt.date(2026, 9, 28)) == FRI
    assert previous_session(FRI) == THU


def test_no_transactions_no_rows() -> None:
    assert daily_rows([], [], MarketData(), FRI) == []
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_engine_rows.py -v`
Expected: FAIL — `ImportError: cannot import name 'FLAG_FX_MISSING' from 'app.valuation.engine'`.

- [ ] **Step 3: Implementacja**

W `api/app/valuation/engine.py`: zmień import z `market_data` na `from app.valuation.market_data import BASE_CURRENCY, MarketData, Series`, dopisz `from collections.abc import Iterable, Sequence`, a pod `EXTERNAL_FLOWS`:
```python
FLAG_XTB_PRICE = "xtb_price"
FLAG_FX_MISSING = "fx_missing"
SOURCE_PROVIDER = "provider"
SOURCE_XTB = "xtb"
PRICE_PLACES = Decimal("0.0001")
```
Pod klasą `Sale` dodaj widoki:
```python
@dataclass(frozen=True)
class Quote:
    unit_pln: Decimal  # value of one current unit in PLN
    price: Decimal | None  # provider close in the quote currency; None when valued from XTB figures
    price_date: dt.date
    rate: Decimal | None
    source: str


@dataclass(frozen=True)
class LotView:
    position_id: str | None
    opened_on: dt.date
    quantity: Decimal  # units of the valuation day
    open_price: Decimal | None  # effective purchase price per unit of the valuation day, quote currency
    cost_pln: Decimal
    value_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal


@dataclass(frozen=True)
class PositionView:
    account_id: int
    instrument_id: int
    day: dt.date
    quantity: Decimal  # units of the valuation day
    cost_pln: Decimal
    value_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    quote: Quote | None
    lots: tuple[LotView, ...]
    flags: tuple[str, ...]


@dataclass(frozen=True)
class Row:
    """One `daily_valuations` row; `instrument_id` None is the account's cash."""

    account_id: int
    instrument_id: int | None
    day: dt.date
    quantity: Decimal | None
    value_pln: Decimal
    cost_pln: Decimal
    net_flow_pln: Decimal
    flags: tuple[str, ...] = ()
```
Dopisz metody na końcu klasy `Book`:
```python
    def quote(self, account_id: int, instrument_id: int, day: dt.date) -> Quote | None:
        """Provider close × NBP rate; without either, the newest XTB figure on or before `day`: a trade of this
        account (PLN per unit, costs included) or the Open Positions value per unit of an import."""
        price = self.market.price(instrument_id, day)
        rate = self.market.rate(self.market.currencies.get(instrument_id), day)
        if price is not None and rate is not None:
            return Quote(price[1] * rate, price[1], price[0], rate, SOURCE_PROVIDER)
        key = (account_id, instrument_id)
        candidates: list[tuple[dt.date, Decimal]] = []
        trades = self.trades.get(key)
        trade = trades.on(day) if trades else None
        if trade is not None:
            candidates.append(trade)
        snapshots = self.market.snapshots.get(key)
        snapshot = snapshots.on(day) if snapshots else None
        if snapshot is not None:
            taken_on, unit = snapshot
            currency = self.account_currency.get(account_id, BASE_CURRENCY)
            candidates.append((taken_on, self.to_pln(unit, currency, taken_on) / self.factor(instrument_id, taken_on)))
        if not candidates:
            return None
        found_on, unit = max(candidates, key=lambda candidate: candidate[0])
        return Quote(unit, None, found_on, None, SOURCE_XTB)

    def position(self, account_id: int, instrument_id: int, day: dt.date) -> PositionView | None:
        """Open lots valued on `day`. Price effect + currency effect = value − cost (spec §6), the purchase
        rate being the NBP rate of the purchase day; positions valued from XTB figures have no currency effect."""
        lots = self.lots.get((account_id, instrument_id))
        if not lots:
            return None
        quote = self.quote(account_id, instrument_id, day)
        factor = self.factor(instrument_id, day)
        views: list[LotView] = []
        quantity = value_total = cost_total = price_total = fx_total = ZERO
        for lot in lots.values():
            value = lot.quantity * quote.unit_pln if quote else ZERO
            fx_effect = ZERO
            if quote is not None and quote.source == SOURCE_PROVIDER and lot.fx_open is not None:
                assert quote.price is not None and quote.rate is not None
                fx_effect = lot.quantity * quote.price * (quote.rate - lot.fx_open)
            price_effect = value - lot.cost_pln - fx_effect
            open_price = (
                (lot.cost_pln * factor / (lot.quantity * lot.fx_open)).quantize(PRICE_PLACES) if lot.fx_open else None
            )
            views.append(LotView(lot.position_id, lot.opened_on, lot.quantity / factor, open_price, money(lot.cost_pln),
                                 money(value), money(price_effect), money(fx_effect)))
            quantity += lot.quantity
            value_total += value
            cost_total += lot.cost_pln
            price_total += price_effect
            fx_total += fx_effect
        flags = () if quote is not None and quote.source == SOURCE_PROVIDER else (FLAG_XTB_PRICE,)
        return PositionView(account_id, instrument_id, day, quantity / factor, money(cost_total), money(value_total),
                            money(price_total), money(fx_total), quote, tuple(views), flags)

    def cash_row(self, account_id: int, day: dt.date) -> Row:
        cash = self.cash[account_id]
        rate = self.market.rate(self.account_currency[account_id], day)
        value = money(cash * rate) if rate is not None else ZERO
        flags = () if rate is not None else (FLAG_FX_MISSING,)
        return Row(account_id, None, day, cash, value, value, money(self.flows.get((account_id, day), ZERO)), flags)

    def rows(self, day: dt.date) -> list[Row]:
        result = [self.cash_row(account_id, day) for account_id in sorted(self.cash)]
        for account_id, instrument_id in sorted(self.lots):
            view = self.position(account_id, instrument_id, day)
            if view is not None:
                result.append(Row(account_id, instrument_id, day, view.quantity, view.value_pln, view.cost_pln,
                                  ZERO, view.flags))
        return result

    def day_change(self, account_id: int, instrument_id: int, session: dt.date, previous: dt.date) -> Decimal:
        """Change of the value of the quantity held now between two sessions' quotes."""
        lots = self.lots.get((account_id, instrument_id))
        if not lots:
            return ZERO
        now, before = self.quote(account_id, instrument_id, session), self.quote(account_id, instrument_id, previous)
        if now is None or before is None:
            return ZERO
        quantity = sum((lot.quantity for lot in lots.values()), ZERO)
        return money(quantity * (now.unit_pln - before.unit_pln))
```
Na końcu pliku funkcje:
```python
def _ordered(entries: Iterable[Entry]) -> list[Entry]:
    return sorted(entries, key=lambda entry: (entry.day, entry.id))


def replay(entries: Iterable[Entry], splits: Iterable[Split], market: MarketData, until: dt.date) -> Book:
    """The book after every transaction dated `until` or earlier."""
    book = Book(splits, market)
    for entry in _ordered(entries):
        if entry.day > until:
            break
        book.apply(entry)
    return book


def daily_rows(entries: Sequence[Entry], splits: Iterable[Split], market: MarketData, end: dt.date) -> list[Row]:
    """Every day from the first transaction to `end`: a cash row per account and a row per open position."""
    ordered = _ordered(entries)
    if not ordered:
        return []
    book = Book(splits, market)
    rows: list[Row] = []
    index, day = 0, ordered[0].day
    while day <= end:
        while index < len(ordered) and ordered[index].day <= day:
            book.apply(ordered[index])
            index += 1
        rows.extend(book.rows(day))
        day += ONE_DAY
    return rows


def last_session(day: dt.date) -> dt.date:
    """`day`, or the Friday before it when it falls on a weekend (exchange holidays are not known)."""
    while day.weekday() >= 5:
        day -= ONE_DAY
    return day


def previous_session(day: dt.date) -> dt.date:
    return last_session(day - ONE_DAY)
```

- [ ] **Step 4: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_engine_rows.py tests/test_valuation_engine_book.py -v`
Expected: PASS — 10 + 9 testów.

- [ ] **Step 5: Commit**

```bash
git add api/app/valuation/engine.py api/tests/test_valuation_engine_rows.py
git commit -m "feat(valuation): daily position valuation with price/fx effects and XTB fallback" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: Przeliczanie `daily_valuations` (ładowanie danych, znacznik, blokada)

**Files:**
- Create: `api/app/valuation/service.py`, `api/tests/valuation_seed.py`, `api/tests/test_valuation_service.py`
- Modify: `api/app/scoping.py`

**Interfaces:**
- Consumes: `Entry`, `Split`, `daily_rows` (Task 4–5); `Series`, `MarketData`, `BASE_CURRENCY` (Task 4); `DailyValuation`, `CorporateAction`, `User.valuations_stale_from` (Task 1); `UserScope` (plany 1–3).
- Produces (używane w Task 7–9):
  - `UserScope.snapshots() -> Select[tuple[XtbSnapshot]]` (migawki XTB kont użytkownika).
  - `service.ZONE = ZoneInfo("Europe/Warsaw")`, `local_day(moment: datetime) -> date`, `local_today(now: datetime | None = None) -> date`.
  - `Inputs(entries: list[Entry], splits: list[Split], market: MarketData)`; `load_inputs(scope: UserScope) -> Inputs`.
  - `lock_user(db, user_id) -> None`; `mark_stale(db, user_ids: Iterable[int], from_day: date) -> None` (nie commituje); `holders(db, instrument_ids: Iterable[int]) -> list[int]`; `users_with_transactions(db) -> list[int]`; `mark_market_changes(db, prices_from: dict[int, date], fx_from: dict[str, date]) -> None`.
  - `recompute_user(db, user_id, today: date) -> int` (commituje; liczba zapisanych wierszy); `recompute_stale(db, today) -> int` (liczba użytkowników); `recompute_in_background(sessions: Callable[[], Session], user_id: int) -> None`.
  - `tests/valuation_seed.py`: `SAT`, `FRI`, `THU`, `AT_DEPOSIT`, `AT_BUY`, `AT_DIVIDEND`, `seed_market(db) -> int`, `seed_user(db, email) -> int`, `seed_holdings(db, user_id, instrument_id, number="56216965") -> int`, `seed_snapshot(db, account_id, instrument_id, volume: str) -> None`, `valuate(db, user_id, today=SAT) -> None`.

- [ ] **Step 1: Wspólne dane testowe**

`api/tests/valuation_seed.py`:
```python
"""A small portfolio with known numbers, shared by the valuation, portfolio and positions tests.

SXR8.DE (EUR): 500 EUR on 2026-03-02, 600 EUR on 2026-09-25; EUR: 4.30 PLN from 2026-02-20, 4.25 from 2026-09-25.
Account: deposit 10 000 zł (03-01), 2 × SXR8.DE for 4 304.30 zł (03-02, lot 777), dividend 40 zł − 6 zł tax (06-15).
On Saturday 2026-09-26: position 2 × 600 × 4.25 = 5 100.00 zł, cash 5 729.70 zł.
"""
import datetime as dt
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models import Account, FxRate, ImportRecord, Instrument, PositionLot, Price, Transaction, User, XtbSnapshot
from app.valuation.service import mark_stale, recompute_user

AT_DEPOSIT = dt.datetime(2026, 3, 1, 10, 0, tzinfo=dt.UTC)
AT_BUY = dt.datetime(2026, 3, 2, 9, 30, tzinfo=dt.UTC)
AT_DIVIDEND = dt.datetime(2026, 6, 15, 12, 0, tzinfo=dt.UTC)
THU, FRI, SAT = dt.date(2026, 9, 24), dt.date(2026, 9, 25), dt.date(2026, 9, 26)


def seed_market(db: Session) -> int:
    instrument = Instrument(
        xtb_ticker="SXR8.DE", name="Core S&P 500", category="etf", currency="EUR", price_symbol="SXR8.DE",
        price_checked_at=dt.datetime(2026, 9, 25, 21, 0, tzinfo=dt.UTC),
    )
    db.add(instrument)
    db.flush()
    db.add_all([
        Price(instrument_id=instrument.id, date=dt.date(2026, 3, 2), close=Decimal("500.00"), source="yahoo"),
        Price(instrument_id=instrument.id, date=FRI, close=Decimal("600.00"), source="yahoo"),
        FxRate(currency="EUR", date=dt.date(2026, 2, 20), rate_pln=Decimal("4.30")),
        FxRate(currency="EUR", date=FRI, rate_pln=Decimal("4.25")),
    ])
    db.commit()
    return instrument.id


def seed_user(db: Session, email: str = "anna@portfolio.dev") -> int:
    user = User(email=email, password_hash="x")
    db.add(user)
    db.commit()
    return user.id


def seed_holdings(db: Session, user_id: int, instrument_id: int, number: str = "56216965") -> int:
    account = Account(user_id=user_id, name="XTB IKE", kind="broker", wrapper="ike", broker="xtb",
                      external_account_number=number, currency="PLN")
    db.add(account)
    db.flush()

    def tx(external_id: str, type_: str, at: dt.datetime, amount: str, **fields: object) -> Transaction:
        return Transaction(account_id=account.id, type=type_, xtb_type=type_, occurred_at=at, amount=Decimal(amount),
                           currency="PLN", external_id=external_id, comment="", raw={}, **fields)

    db.add_all([
        tx("1", "deposit", AT_DEPOSIT, "10000"),
        tx("2", "buy", AT_BUY, "-4304.30", instrument_id=instrument_id, quantity=Decimal("2"),
           price=Decimal("500.5"), xtb_position_id="777"),
        tx("3", "dividend", AT_DIVIDEND, "40.00", instrument_id=instrument_id),
        tx("4", "withholding_tax", AT_DIVIDEND, "-6.00", instrument_id=instrument_id),
        PositionLot(account_id=account.id, instrument_id=instrument_id, xtb_position_id="777", side="buy",
                    quantity=Decimal("2"), open_price=Decimal("500.5"), opened_at=AT_BUY,
                    stop_loss=Decimal("450"), raw={}),
    ])
    db.commit()
    return account.id


def seed_snapshot(db: Session, account_id: int, instrument_id: int, volume: str) -> None:
    """An XTB import taken on Saturday 2026-09-26 reporting `volume` units worth 5 100 zł."""
    account = db.get(Account, account_id)
    record = ImportRecord(user_id=account.user_id, account_id=account_id, filename="IKE.xlsx", file_hash="0" * 64,
                          rows_added=0, rows_duplicate=0, rows_unknown=0)
    db.add(record)
    db.flush()
    db.add(XtbSnapshot(import_id=record.id, account_id=account_id, instrument_id=instrument_id,
                       row_kind="instrument_summary", volume=Decimal(volume), value=Decimal("5100"),
                       taken_at=dt.datetime(2026, 9, 26, 12, 0, tzinfo=dt.UTC), raw={}))
    db.commit()


def valuate(db: Session, user_id: int, today: dt.date = SAT) -> None:
    mark_stale(db, [user_id], dt.date.min)
    db.commit()
    recompute_user(db, user_id, today)
```

- [ ] **Step 2: Napisz testy**

`api/tests/test_valuation_service.py`:
```python
import datetime as dt
import threading
from collections.abc import Iterator
from decimal import Decimal

import pytest
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from app.models import DailyValuation, Price, Transaction, User
from app.scoping import UserScope
from app.valuation.engine import FLAG_XTB_PRICE
from app.valuation.service import (
    holders,
    load_inputs,
    local_day,
    mark_market_changes,
    mark_stale,
    recompute_stale,
    recompute_user,
    users_with_transactions,
)
from tests.valuation_seed import FRI, SAT, seed_holdings, seed_market, seed_snapshot, seed_user, valuate

MAR_01 = dt.date(2026, 3, 1)


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _rows(db: Session, user_id: int, day: dt.date) -> dict[int | None, DailyValuation]:
    rows = db.scalars(select(DailyValuation).where(DailyValuation.user_id == user_id, DailyValuation.date == day))
    return {row.instrument_id: row for row in rows}


def _count(db: Session, user_id: int) -> int:
    return db.scalar(select(func.count()).select_from(DailyValuation).where(DailyValuation.user_id == user_id))


def _stale(db: Session, user_id: int) -> dt.date | None:
    return db.scalar(select(User.valuations_stale_from).where(User.id == user_id))


def test_local_day_is_the_warsaw_calendar_day() -> None:
    assert local_day(dt.datetime(2026, 3, 1, 23, 30, tzinfo=dt.UTC)) == dt.date(2026, 3, 2)


def test_load_inputs_reads_only_the_users_own_data(db: Session) -> None:
    instrument_id = seed_market(db)
    anna, bartek = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    anna_account = seed_holdings(db, anna, instrument_id)
    seed_holdings(db, bartek, instrument_id, number="11111111")
    seed_snapshot(db, anna_account, instrument_id, "2")

    inputs = load_inputs(UserScope(db, db.get(User, anna)))

    assert sorted(entry.type for entry in inputs.entries) == ["buy", "deposit", "dividend", "withholding_tax"]
    assert {entry.account_id for entry in inputs.entries} == {anna_account}
    assert min(entry.day for entry in inputs.entries) == MAR_01
    assert inputs.market.currencies == {instrument_id: "EUR"}
    assert inputs.market.price(instrument_id, SAT) == (FRI, Decimal("600.00000000"))
    assert inputs.market.rate("EUR", SAT) == Decimal("4.25000000")
    assert inputs.market.snapshots[(anna_account, instrument_id)].on(SAT) == (SAT, Decimal("2550"))


def test_recompute_writes_every_day_and_clears_the_marker(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))

    valuate(db, user_id)

    days = (SAT - MAR_01).days + 1
    assert _count(db, user_id) == days + (days - 1)
    rows = _rows(db, user_id, SAT)
    assert (rows[None].value_pln, rows[None].quantity) == (Decimal("5729.70"), Decimal("5729.70"))
    position = next(row for key, row in rows.items() if key is not None)
    assert (position.value_pln, position.cost_pln, position.quantity, position.flags) == (
        Decimal("5100.00"), Decimal("4304.30"), Decimal("2"), [])
    assert _rows(db, user_id, MAR_01)[None].net_flow_pln == Decimal("10000.00")
    assert _stale(db, user_id) is None


def test_recompute_only_rewrites_rows_from_the_stale_date(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))
    valuate(db, user_id)
    db.execute(update(DailyValuation).where(DailyValuation.date.in_([dt.date(2026, 4, 1), dt.date(2026, 9, 1)]))
               .values(value_pln=Decimal("1")))
    db.commit()

    mark_stale(db, [user_id], dt.date(2026, 8, 1))
    db.commit()
    recompute_user(db, user_id, SAT)

    assert _rows(db, user_id, dt.date(2026, 4, 1))[None].value_pln == Decimal("1")
    assert _rows(db, user_id, dt.date(2026, 9, 1))[None].value_pln == Decimal("5729.70")


def test_marking_keeps_the_earliest_date(db: Session) -> None:
    user_id = seed_user(db)
    mark_stale(db, [user_id], dt.date(2026, 5, 1))
    mark_stale(db, [user_id], dt.date(2026, 6, 1))
    mark_stale(db, [], dt.date(2020, 1, 1))
    db.commit()
    assert _stale(db, user_id) == dt.date(2026, 5, 1)
    mark_stale(db, [user_id], dt.date(2026, 4, 1))
    db.commit()
    assert _stale(db, user_id) == dt.date(2026, 4, 1)


def test_recompute_of_a_user_without_transactions_clears_old_rows(db: Session) -> None:
    user_id = seed_user(db)
    account_id = seed_holdings(db, user_id, seed_market(db))
    valuate(db, user_id)
    db.query(Transaction).filter(Transaction.account_id == account_id).delete()
    db.commit()

    valuate(db, user_id)

    assert _count(db, user_id) == 0


def test_instrument_without_prices_is_valued_from_xtb_and_flagged(db: Session) -> None:
    instrument_id = seed_market(db)
    user_id = seed_user(db)
    seed_holdings(db, user_id, instrument_id)
    db.query(Price).delete()
    db.commit()

    valuate(db, user_id)

    position = next(row for key, row in _rows(db, user_id, SAT).items() if key is not None)
    assert (position.value_pln, position.flags) == (Decimal("4304.30"), [FLAG_XTB_PRICE])


def test_market_changes_mark_holders_and_fx_marks_everyone(db: Session) -> None:
    instrument_id = seed_market(db)
    anna, bartek, carol = seed_user(db), seed_user(db, "bartek@portfolio.dev"), seed_user(db, "carol@portfolio.dev")
    seed_holdings(db, anna, instrument_id)
    bartek_account = seed_holdings(db, bartek, instrument_id, number="22222222")
    db.query(Transaction).filter(Transaction.account_id == bartek_account, Transaction.instrument_id.is_not(None)).delete()
    db.commit()

    assert holders(db, [instrument_id]) == [anna]
    assert users_with_transactions(db) == [anna, bartek]
    mark_market_changes(db, {instrument_id: FRI}, {})
    db.commit()
    assert (_stale(db, anna), _stale(db, bartek), _stale(db, carol)) == (FRI, None, None)
    mark_market_changes(db, {}, {"EUR": dt.date(2026, 9, 1), "USD": dt.date(2026, 8, 1)})
    db.commit()
    assert (_stale(db, anna), _stale(db, bartek), _stale(db, carol)) == (dt.date(2026, 8, 1), dt.date(2026, 8, 1), None)


def test_recompute_stale_handles_every_marked_user(db: Session) -> None:
    instrument_id = seed_market(db)
    anna, bartek = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    seed_holdings(db, anna, instrument_id)
    seed_holdings(db, bartek, instrument_id, number="11111111")
    mark_stale(db, [anna, bartek], dt.date.min)
    db.commit()

    assert recompute_stale(db, SAT) == 2
    assert _count(db, anna) == _count(db, bartek) > 0
    assert (_stale(db, anna), _stale(db, bartek)) == (None, None)
    assert recompute_stale(db, SAT) == 0


def test_recompute_waits_for_a_concurrent_marking(engine: Engine, db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))
    finished = threading.Event()

    def run() -> None:
        with Session(engine) as worker_db:
            recompute_user(worker_db, user_id, SAT)
        finished.set()

    with Session(engine) as importer:
        mark_stale(importer, [user_id], dt.date.min)  # holds the user's lock until commit, like an import
        thread = threading.Thread(target=run)
        thread.start()
        assert not finished.wait(0.5)
        importer.commit()
    thread.join(10)

    assert finished.is_set()
    assert _count(db, user_id) > 0
    assert _stale(db, user_id) is None
```

- [ ] **Step 3: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_service.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'app.valuation.service'`.

- [ ] **Step 4: Zakres użytkownika**

W `api/app/scoping.py` dodaj `XtbSnapshot` do importu z `app.models` i metodę w `UserScope` (po `imports`):
```python
    def snapshots(self) -> Select[tuple[XtbSnapshot]]:
        return (
            select(XtbSnapshot)
            .join(Account, XtbSnapshot.account_id == Account.id)
            .where(Account.user_id == self.user.id)
        )
```

- [ ] **Step 5: Serwis przeliczania**

`api/app/valuation/service.py`:
```python
"""Loads a user's data for the valuation engine and maintains the `daily_valuations` cache.

A recompute is requested with `mark_stale` (the earliest requested day wins) and done by `recompute_user`.
Both take the user's advisory lock, so a marking transaction (an import) waits for a running recompute,
and the next recompute sees the committed data.
"""
import datetime as dt
import logging
from collections import defaultdict
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from zoneinfo import ZoneInfo

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.orm import Session

from app.models import Account, CorporateAction, DailyValuation, FxRate, Instrument, Price, Transaction, User, XtbSnapshot
from app.scoping import UserScope
from app.valuation.engine import Entry, Split, daily_rows
from app.valuation.market_data import BASE_CURRENCY, MarketData, Series

logger = logging.getLogger(__name__)

ZONE = ZoneInfo("Europe/Warsaw")  # valuation days are Warsaw calendar days, like the worker's schedule
LOCK_NAMESPACE = 4  # high 32 bits of the advisory lock key "valuations of user N"
INSERT_CHUNK = 1000
SPLIT_TYPES = ("split", "reverse_split")


def local_day(moment: dt.datetime) -> dt.date:
    return moment.astimezone(ZONE).date()


def local_today(now: dt.datetime | None = None) -> dt.date:
    return local_day(now or dt.datetime.now(dt.UTC))


@dataclass(frozen=True)
class Inputs:
    entries: list[Entry]
    splits: list[Split]
    market: MarketData


def _series(points: dict[object, list[tuple[dt.date, object]]]) -> dict:
    return {key: Series(values) for key, values in points.items()}


def load_inputs(scope: UserScope) -> Inputs:
    """The user's transactions and every piece of market data the engine may look up for them."""
    db = scope.db
    entries = [
        Entry(t.id, t.account_id, t.instrument_id, t.type, local_day(t.occurred_at), t.amount, t.currency,
              t.quantity, t.price, t.xtb_position_id)
        for t in db.scalars(scope.transactions()).unique()
    ]
    instrument_ids = sorted({entry.instrument_id for entry in entries if entry.instrument_id is not None})
    market = MarketData()
    splits: list[Split] = []
    if instrument_ids:
        prices: dict[object, list] = defaultdict(list)
        for instrument_id, day, close in db.execute(
            select(Price.instrument_id, Price.date, Price.close).where(Price.instrument_id.in_(instrument_ids))
        ):
            prices[instrument_id].append((day, close))
        market.prices = _series(prices)
        market.currencies = dict(
            db.execute(select(Instrument.id, Instrument.currency).where(Instrument.id.in_(instrument_ids))).all()
        )
        splits = [
            Split(action.instrument_id, action.effective_date, action.ratio_from, action.ratio_to)
            for action in db.scalars(
                select(CorporateAction).where(
                    CorporateAction.instrument_id.in_(instrument_ids), CorporateAction.type.in_(SPLIT_TYPES)
                )
            )
        ]
        snapshots: dict[object, list] = defaultdict(list)
        for snapshot in db.scalars(
            scope.snapshots()
            .where(
                XtbSnapshot.row_kind == "instrument_summary",
                XtbSnapshot.instrument_id.is_not(None),
                XtbSnapshot.value.is_not(None),
                XtbSnapshot.volume > 0,
            )
            .order_by(XtbSnapshot.taken_at, XtbSnapshot.id)
        ):
            key = (snapshot.account_id, snapshot.instrument_id)
            snapshots[key].append((local_day(snapshot.taken_at), snapshot.value / snapshot.volume))
        market.snapshots = _series(snapshots)
    currencies = ({c for c in market.currencies.values() if c} | {entry.currency for entry in entries}) - {BASE_CURRENCY}
    if currencies:
        rates: dict[object, list] = defaultdict(list)
        for currency, day, rate in db.execute(
            select(FxRate.currency, FxRate.date, FxRate.rate_pln).where(FxRate.currency.in_(currencies))
        ):
            rates[currency].append((day, rate))
        market.fx = _series(rates)
    return Inputs(entries, splits, market)


def lock_user(db: Session, user_id: int) -> None:
    """Transaction-scoped: released on commit or rollback."""
    db.execute(text("SELECT pg_advisory_xact_lock(CAST(:key AS bigint))"), {"key": (LOCK_NAMESPACE << 32) | user_id})


def mark_stale(db: Session, user_ids: Iterable[int], from_day: dt.date) -> None:
    """Requests a recompute of the users' valuations from `from_day`; an earlier pending day wins. Does not commit."""
    ids = sorted(set(user_ids))
    if not ids:
        return
    for user_id in ids:  # always in id order: two markers never wait for each other in a cycle
        lock_user(db, user_id)
    earliest = func.least(func.coalesce(User.valuations_stale_from, from_day), from_day)
    db.execute(
        update(User).where(User.id.in_(ids)).values(valuations_stale_from=earliest)
        .execution_options(synchronize_session=False)
    )


def holders(db: Session, instrument_ids: Iterable[int]) -> list[int]:
    """Users with any transaction in one of the instruments."""
    ids = list(instrument_ids)
    if not ids:
        return []
    return list(db.scalars(
        select(Account.user_id).join(Transaction, Transaction.account_id == Account.id)
        .where(Transaction.instrument_id.in_(ids)).distinct().order_by(Account.user_id)
    ))


def users_with_transactions(db: Session) -> list[int]:
    return list(db.scalars(
        select(Account.user_id).join(Transaction, Transaction.account_id == Account.id)
        .distinct().order_by(Account.user_id)
    ))


def mark_market_changes(db: Session, prices_from: dict[int, dt.date], fx_from: dict[str, dt.date]) -> None:
    """New prices or splits concern the instrument's holders; new NBP rates concern everyone with transactions
    (cash in a foreign currency too). Does not commit."""
    for instrument_id, day in prices_from.items():
        mark_stale(db, holders(db, [instrument_id]), day)
    if fx_from:
        mark_stale(db, users_with_transactions(db), min(fx_from.values()))


def recompute_user(db: Session, user_id: int, today: dt.date) -> int:
    """Rebuilds the user's rows from `valuations_stale_from` to `today` and commits; returns the rows written.

    The whole history is replayed in memory (days × positions: cheap); rows before the stale day are kept.
    """
    try:
        lock_user(db, user_id)
        stale_from = db.scalar(select(User.valuations_stale_from).where(User.id == user_id))
        user = db.get(User, user_id)
        if stale_from is None or user is None:
            db.commit()
            return 0
        inputs = load_inputs(UserScope(db, user))
        rows = [row for row in daily_rows(inputs.entries, inputs.splits, inputs.market, today) if row.day >= stale_from]
        db.execute(delete(DailyValuation).where(DailyValuation.user_id == user_id, DailyValuation.date >= stale_from))
        values = [
            {
                "user_id": user_id, "account_id": row.account_id, "instrument_id": row.instrument_id, "date": row.day,
                "quantity": row.quantity, "value_pln": row.value_pln, "cost_pln": row.cost_pln,
                "net_flow_pln": row.net_flow_pln, "flags": list(row.flags),
            }
            for row in rows
        ]
        for start in range(0, len(values), INSERT_CHUNK):
            db.execute(insert(DailyValuation), values[start:start + INSERT_CHUNK])
        db.execute(
            update(User).where(User.id == user_id).values(valuations_stale_from=None)
            .execution_options(synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        raise
    return len(rows)


def recompute_stale(db: Session, today: dt.date) -> int:
    """Recomputes every user with a pending request; one user's failure does not stop the others."""
    user_ids = db.scalars(
        select(User.id).where(User.valuations_stale_from.is_not(None)).order_by(User.id)
    ).all()
    for user_id in user_ids:
        try:
            recompute_user(db, user_id, today)
        except Exception:
            logger.exception("Valuation recompute failed for user %s; it stays marked for the next run", user_id)
    return len(user_ids)


def recompute_in_background(sessions: Callable[[], Session], user_id: int) -> None:
    """Runs right after an import's response; on failure the worker's next tick retries (the user stays marked)."""
    try:
        with sessions() as db:
            recompute_user(db, user_id, local_today())
    except Exception:
        logger.exception("Background valuation recompute failed for user %s", user_id)
```

- [ ] **Step 6: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_service.py -v`
Expected: PASS — 10 testów. Test blokady trwa ok. 0,5 s.

- [ ] **Step 7: Commit**

```bash
git add api/app/valuation/service.py api/app/scoping.py api/tests/valuation_seed.py api/tests/test_valuation_service.py
git commit -m "feat(valuation): recompute daily valuations per user under an advisory lock" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 7: Wyzwalacze przeliczenia — import, zmiana symbolu, worker

**Files:**
- Modify: `api/app/db.py`, `api/app/imports/service.py`, `api/app/imports/router.py`, `api/app/instruments/router.py`, `api/app/worker.py`, `api/tests/conftest.py`
- Test: `api/tests/test_valuation_triggers.py`

**Interfaces:**
- Consumes: `mark_stale`, `holders`, `users_with_transactions`, `mark_market_changes`, `recompute_stale`, `recompute_in_background`, `local_day` (Task 6); `UpdateSummary.prices_changed_from`, `fx_changed_from`, parametr `changed` w `backfill_new_instruments` (Task 2–3).
- Produces: `app.db.get_session_factory() -> sessionmaker[Session]` (zależność FastAPI; testy ją nadpisują); `apply_import` oznacza użytkownika od najwcześniejszego dnia importu w tej samej transakcji; `POST /api/imports` przelicza w tle po odpowiedzi; `PATCH /api/instruments/{id}` (zmiana symbolu) oznacza posiadaczy od `date.min`; `tick` workera oznacza zmiany rynkowe i na końcu każdego ticku wywołuje `recompute_stale`.

- [ ] **Step 1: Napisz testy**

`api/tests/test_valuation_triggers.py`:
```python
import datetime as dt
from collections.abc import Callable, Iterator
from datetime import datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.imports.service import apply_import, plan_import
from app.models import DailyValuation, Instrument, User
from app.scoping import UserScope
from app.valuation.engine import FLAG_XTB_PRICE
from app.worker import WorkerState, tick
from app.xtb.report import parse_report
from tests import xtb_factory as xf
from tests.market_fakes import fake_providers
from tests.test_worker import SCHEDULE, _at
from tests.valuation_seed import FRI, seed_holdings, seed_market, seed_user

LoginAs = Callable[[str], dict[str, str]]
IKE = "56216965"
AT = datetime(2026, 3, 2, 9, 30)


def _ike() -> bytes:
    return xf.build_report(
        account_number=IKE,
        cash=[
            xf.cash_row("IKE deposit", 5000.0, "1001", datetime(2026, 3, 1, 8, 0),
                        comment="Transfer in operation on account with id 56204082"),
            xf.buy_row("SXR8.DE", "2", "500.5", -4304.3, "1002", AT, "777"),
        ],
        open_rows=[
            xf.summary_row("SXR8.DE", "Core S&P 500", 2.0, 1020.0, 500.5, 19.0),
            xf.lot_row("SXR8.DE", "777", 2.0, 500.5, AT, 510.0, 1020.0, 19.0),
        ],
    )


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _stale(db: Session, user_id: int) -> dt.date | None:
    return db.scalar(select(User.valuations_stale_from).where(User.id == user_id))


def _import(db: Session, user_id: int) -> None:
    scope = UserScope(db, db.get(User, user_id))
    apply_import(scope, plan_import(scope, [parse_report(xf.filename("IKE", IKE), _ike())]))


def test_import_marks_the_user_from_its_earliest_operation(db: Session) -> None:
    user_id = seed_user(db)
    _import(db, user_id)
    assert _stale(db, user_id) == dt.date(2026, 3, 1)


def test_reimport_of_known_operations_marks_only_the_snapshot_day(db: Session) -> None:
    user_id = seed_user(db)
    _import(db, user_id)
    db.execute(update(User).values(valuations_stale_from=None))
    db.commit()

    _import(db, user_id)

    assert _stale(db, user_id) == dt.date(2026, 9, 26)


def test_committed_import_is_valued_in_the_background(client: TestClient, login_as: LoginAs, engine: Engine) -> None:
    anna = login_as("anna@portfolio.dev")

    response = client.post(
        "/api/imports", files=[("files", (xf.filename("IKE", IKE), _ike(), "application/octet-stream"))], headers=anna
    )

    assert response.status_code == 201, response.json()
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        assert _stale(db, user_id) is None
        rows = {
            (row.date, row.instrument_id is None): row
            for row in db.scalars(select(DailyValuation).where(DailyValuation.user_id == user_id))
        }
    bought = rows[(dt.date(2026, 3, 2), False)]
    assert (bought.value_pln, bought.cost_pln, bought.flags) == (Decimal("4304.30"), Decimal("4304.30"), [FLAG_XTB_PRICE])
    assert rows[(dt.date(2026, 9, 26), False)].value_pln == Decimal("1020.00")
    assert rows[(dt.date(2026, 3, 1), True)].net_flow_pln == Decimal("5000.00")


def test_price_symbol_change_marks_holders_for_a_full_recompute(
    client: TestClient, login_as: LoginAs, engine: Engine
) -> None:
    anna, _ = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        anna_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        bartek_id = db.scalar(select(User.id).where(User.email == "bartek@portfolio.dev"))
        seed_holdings(db, anna_id, instrument_id)

    response = client.patch(f"/api/instruments/{instrument_id}", json={"price_symbol": "CSPX.L"}, headers=anna)

    assert response.status_code == 200, response.json()
    with Session(engine) as db:
        assert (_stale(db, anna_id), _stale(db, bartek_id)) == (dt.date.min, None)


def test_daily_tick_revalues_holders_with_the_new_prices(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))

    assert tick(db, fake_providers(), SCHEDULE, WorkerState(), _at(10)) == "daily"

    assert _stale(db, user_id) is None
    position = db.scalar(select(DailyValuation).where(
        DailyValuation.user_id == user_id, DailyValuation.date == FRI, DailyValuation.instrument_id.is_not(None)))
    assert position.value_pln == Decimal("6067.30")  # 2 × 713.80 EUR (fake provider) × 4.25


def test_backfill_tick_finishes_pending_recomputes(db: Session) -> None:
    user_id = seed_user(db)
    seed_holdings(db, user_id, seed_market(db))
    db.execute(update(User).values(valuations_stale_from=dt.date.min))
    db.execute(update(Instrument).values(price_checked_at=datetime(2026, 9, 25, 7, 0, tzinfo=dt.UTC)))
    db.commit()
    state = WorkerState(last_completed=FRI)

    assert tick(db, fake_providers(), SCHEDULE, state, _at(10, 5)) == "backfill"

    assert _stale(db, user_id) is None
    assert db.scalar(select(DailyValuation.date).where(DailyValuation.user_id == user_id)
                     .order_by(DailyValuation.date.desc()).limit(1)) == FRI
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_triggers.py -v`
Expected: FAIL — pierwsze testy: `assert None == datetime.date(2026, 3, 1)` (import jeszcze nie oznacza), test tła: `KeyError` przy braku wierszy.

- [ ] **Step 3: Fabryka sesji dla pracy w tle**

W `api/app/db.py` dopisz:
```python
def get_session_factory() -> sessionmaker[Session]:
    """Sessions for work that outlives the request (background tasks); tests override it like get_db."""
    return get_sessionmaker()
```
W `api/tests/conftest.py` zmień import na `from app.db import get_db, get_session_factory` i w `make_app._make` po `app.dependency_overrides[get_db] = _get_db`:
```python
        app.dependency_overrides[get_session_factory] = lambda: test_sessionmaker
```

- [ ] **Step 4: Import oznacza i przelicza w tle**

W `api/app/imports/service.py` dodaj import `from datetime import date` (obok istniejącego `from datetime import UTC, datetime, timedelta` — dopisz `date` do tej linii) i `from app.valuation.service import local_day, mark_stale`. Dodaj funkcję nad `apply_import`:
```python
def _valuations_changed_from(plans: list[FilePlan]) -> date | None:
    """The earliest day an import changes: a new operation, or the day of an XTB snapshot (fallback prices)."""
    days = [local_day(operation.occurred_at) for plan in plans for operation in plan.new_operations]
    days += [
        local_day(plan.report.generated_at)
        for plan in plans
        if plan.report.generated_at is not None and plan.report.instrument_summaries
    ]
    return min(days, default=None)
```
W `apply_import` zamień
```python
        pair_transfers(scope)
        db.commit()
```
na
```python
        pair_transfers(scope)
        changed_from = _valuations_changed_from(plans)
        if changed_from is not None:
            mark_stale(db, [scope.user.id], changed_from)
        db.commit()
```
Dopisz do docstringu `apply_import` zdanie: `The user is marked for a valuation recompute from the earliest changed day, in the same transaction.`

W `api/app/imports/router.py`:
```python
from fastapi import APIRouter, BackgroundTasks, Depends, File, UploadFile
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session_factory
from app.valuation.service import recompute_in_background
```
i zastąp nagłówek oraz koniec `commit_import`:
```python
@router.post("", status_code=201, response_model=ImportResultOut)
def commit_import(
    background: BackgroundTasks,
    files: list[UploadFile] = File(...),
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> ImportResultOut:
    reports, errors, skipped = _parse(files)
    if errors:
        raise ApiError(
            422, "import_invalid_files", "Niektórych plików nie da się odczytać. Nic nie zapisano.", {"errors": errors}
        )
    if not reports:
        raise ApiError(422, "import_empty", "Brak plików XLSX z XTB do zaimportowania.")
    plans = plan_import(scope, reports)
    records = apply_import(scope, plans)
    background.add_task(recompute_in_background, sessions, scope.user.id)
    return ImportResultOut(
        files=[_file_out(plan, record) for plan, record in zip(plans, records, strict=True)],
        errors=[],
        skipped=skipped,
    )
```

- [ ] **Step 5: Zmiana symbolu oznacza posiadaczy**

W `api/app/instruments/router.py` dodaj `import datetime as dt` i `from app.valuation.service import holders, mark_stale`; w `update_instrument` zamień
```python
        delete_prices(scope.db, instrument.id)
        scope.db.commit()
```
na
```python
        delete_prices(scope.db, instrument.id)
        # Every holder's history was valued with the old symbol's prices.
        mark_stale(scope.db, holders(scope.db, [instrument.id]), dt.date.min)
        scope.db.commit()
```

- [ ] **Step 6: Worker**

W `api/app/worker.py` dodaj import:
```python
from app.valuation.service import mark_market_changes, mark_stale, recompute_stale, users_with_transactions
```
i zastąp `tick`:
```python
def tick(
    db: Session, providers: MarketProviders, schedule: DailySchedule, state: WorkerState, now: dt.datetime
) -> Literal["daily", "backfill"]:
    today = now.astimezone(schedule.zone).date()
    result: Literal["daily", "backfill"]
    if schedule.is_due(now, state.last_completed):
        summary = run_market_update(db, providers, now, today)
        mark_market_changes(db, summary.prices_changed_from, summary.fx_changed_from)
        mark_stale(db, users_with_transactions(db), today)  # every portfolio's history gets the new day
        pruned = prune_refresh_tokens(db, now)
        db.commit()
        state.last_completed = schedule.completed_through(now)
        logger.info("Daily market update done: %s; pruned %d refresh tokens", summary, pruned)
        result = "daily"
    else:
        changed: dict[int, dt.date] = {}
        rows, failed = backfill_new_instruments(db, providers.prices, now, changed)
        mark_market_changes(db, changed, {})
        db.commit()
        if rows or failed:
            logger.info("Backfilled new instruments: %d price rows, failed: %s", rows, failed)
        result = "backfill"
    recomputed = recompute_stale(db, today)  # also retries recomputes whose background run failed
    if recomputed:
        logger.info("Recomputed valuations of %d users", recomputed)
    return result
```
Zaktualizuj docstring modułu: `Background worker: daily market data update, backfill of new instruments, valuation recompute, housekeeping.`

- [ ] **Step 7: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest -v`
Expected: PASS — cały zestaw, w tym 6 testów z `test_valuation_triggers.py`; testy importu, instrumentów i workera z planów 2–3 przechodzą bez zmian.

- [ ] **Step 8: Commit**

```bash
git add api/app/db.py api/app/imports api/app/instruments/router.py api/app/worker.py api/tests/conftest.py api/tests/test_valuation_triggers.py
git commit -m "feat(valuation): recompute after imports, symbol changes and market updates" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: API pulpitu — podsumowanie i historia wartości

**Files:**
- Create: `api/app/portfolio/__init__.py` (pusty), `api/app/portfolio/schemas.py`, `api/app/portfolio/service.py`, `api/app/portfolio/router.py`, `api/tests/test_portfolio_api.py`
- Modify: `api/app/scoping.py`, `api/app/main.py`

**Interfaces:**
- Consumes: `DailyValuation` (Task 1); `last_session`, `previous_session`, `money`, `ZERO` (Task 5); `local_day`, `mark_stale` (Task 6); `fx_on` (plan 3); seed z `tests/valuation_seed.py` (Task 6).
- Produces:
  - `UserScope.daily_valuations() -> Select[tuple[DailyValuation]]`.
  - `app.portfolio.service`: `percent(part, whole) -> Decimal | None`, `amount_pln(db, transaction) -> Decimal`, `portfolio_summary(scope, account_id: int | None) -> SummaryOut`, `portfolio_history(scope, account_id, start: date | None, end: date | None) -> HistoryOut`.
  - `app.portfolio.router`: `router` (prefiks `/api`), `AccountFilter`, `_account(scope, account_id) -> int | None`.
  - `GET /api/portfolio/summary?account_id=` → `SummaryOut`; `GET /api/portfolio/history?account_id=&from=&to=` → `HistoryOut`.

- [ ] **Step 1: Napisz testy**

`api/tests/test_portfolio_api.py`:
```python
import datetime as dt
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import User
from app.valuation.service import mark_stale
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]


def _user_id(db: Session, email: str) -> int:
    return db.scalar(select(User.id).where(User.email == email))


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        user_id = _user_id(db, "anna@portfolio.dev")
        account_id = seed_holdings(db, user_id, seed_market(db))
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id}


def test_summary_shows_value_gain_day_change_income_and_allocation(client: TestClient, world: dict) -> None:
    body = client.get("/api/portfolio/summary", headers=world["anna"]).json()

    assert {key: body[key] for key in (
        "as_of", "value_pln", "cash_pln", "invested_pln", "total_gain_pln", "total_gain_pct",
        "day_change_pln", "day_change_pct", "dividends_net_pln", "interest_net_pln", "approximate_positions",
        "recalculating",
    )} == {
        "as_of": "2026-09-26", "value_pln": "10829.70", "cash_pln": "5729.70", "invested_pln": "10000.00",
        "total_gain_pln": "829.70", "total_gain_pct": "8.30", "day_change_pln": "800.00", "day_change_pct": "7.98",
        "dividends_net_pln": "34.00", "interest_net_pln": "0.00", "approximate_positions": 0, "recalculating": False,
    }
    assert body["by_kind"] == [
        {"key": "cash", "name": "Gotówka", "value_pln": "5729.70", "share_pct": "52.91"},
        {"key": "etf", "name": "ETF", "value_pln": "5100.00", "share_pct": "47.09"},
    ]
    assert body["by_account"] == [
        {"key": str(world["account_id"]), "name": "XTB IKE", "value_pln": "10829.70", "share_pct": "100.00"},
    ]


def test_summary_filtered_by_own_account_and_foreign_account_is_404(client: TestClient, world: dict) -> None:
    own = client.get("/api/portfolio/summary", params={"account_id": world["account_id"]}, headers=world["anna"])
    foreign = client.get("/api/portfolio/summary", params={"account_id": world["account_id"]}, headers=world["bartek"])

    assert own.json()["value_pln"] == "10829.70"
    assert (foreign.status_code, foreign.json()["code"]) == (404, "not_found")


def test_user_without_data_gets_an_empty_summary(client: TestClient, world: dict) -> None:
    body = client.get("/api/portfolio/summary", headers=world["bartek"]).json()
    assert (body["as_of"], body["value_pln"], body["by_kind"], body["day_change_pln"], body["recalculating"]) == (
        None, "0.00", [], None, False)


def test_summary_says_when_a_recompute_is_pending(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        mark_stale(db, [_user_id(db, "anna@portfolio.dev")], dt.date(2026, 9, 1))
        db.commit()
    assert client.get("/api/portfolio/summary", headers=world["anna"]).json()["recalculating"] is True


def test_history_in_a_range(client: TestClient, world: dict) -> None:
    body = client.get("/api/portfolio/history", params={"from": "2026-09-24", "to": "2026-09-26"},
                      headers=world["anna"]).json()

    assert body["points"] == [
        {"date": "2026-09-24", "value_pln": "10029.70", "invested_pln": "10000.00", "net_flow_pln": "0.00"},
        {"date": "2026-09-25", "value_pln": "10829.70", "invested_pln": "10000.00", "net_flow_pln": "0.00"},
        {"date": "2026-09-26", "value_pln": "10829.70", "invested_pln": "10000.00", "net_flow_pln": "0.00"},
    ]
    assert body["events"] == []


def test_full_history_starts_with_the_first_deposit_and_marks_operations(client: TestClient, world: dict) -> None:
    body = client.get("/api/portfolio/history", headers=world["anna"]).json()

    assert len(body["points"]) == 210
    assert body["points"][0] == {"date": "2026-03-01", "value_pln": "10000.00", "invested_pln": "10000.00",
                                 "net_flow_pln": "10000.00"}
    assert body["events"] == [
        {"date": "2026-03-01", "type": "deposit", "amount_pln": "10000.00"},
        {"date": "2026-03-02", "type": "buy", "amount_pln": "-4304.30"},
        {"date": "2026-06-15", "type": "dividend", "amount_pln": "40.00"},
    ]


def test_portfolio_requires_login(client: TestClient) -> None:
    assert client.get("/api/portfolio/summary").status_code == 401
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_portfolio_api.py -v`
Expected: FAIL — 404 dla `/api/portfolio/summary` (brak routera) → `KeyError` przy odczycie pól.

- [ ] **Step 3: Zakres użytkownika**

W `api/app/scoping.py` dodaj `DailyValuation` do importu z `app.models` i metodę w `UserScope`:
```python
    def daily_valuations(self) -> Select[tuple[DailyValuation]]:
        return select(DailyValuation).where(DailyValuation.user_id == self.user.id)
```

- [ ] **Step 4: Schematy**

`api/app/portfolio/schemas.py`:
```python
import datetime as dt
from decimal import Decimal

from pydantic import BaseModel


class AllocationOut(BaseModel):
    key: str
    name: str
    value_pln: Decimal
    share_pct: Decimal | None


class SummaryOut(BaseModel):
    as_of: dt.date | None
    value_pln: Decimal
    cash_pln: Decimal
    invested_pln: Decimal
    total_gain_pln: Decimal
    total_gain_pct: Decimal | None
    day_change_pln: Decimal | None
    day_change_pct: Decimal | None
    dividends_net_pln: Decimal
    interest_net_pln: Decimal
    by_account: list[AllocationOut]
    by_kind: list[AllocationOut]
    approximate_positions: int
    recalculating: bool


class HistoryPointOut(BaseModel):
    date: dt.date
    value_pln: Decimal
    invested_pln: Decimal
    net_flow_pln: Decimal


class HistoryEventOut(BaseModel):
    date: dt.date
    type: str
    amount_pln: Decimal


class HistoryOut(BaseModel):
    points: list[HistoryPointOut]
    events: list[HistoryEventOut]
```

- [ ] **Step 5: Serwis**

`api/app/portfolio/service.py`:
```python
"""Dashboard (from the cached daily_valuations) and positions (computed live for one day)."""
import datetime as dt
from collections import defaultdict
from decimal import ROUND_HALF_UP, Decimal

from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session

from app.market.store import fx_on
from app.models import DailyValuation, Instrument, Transaction, User
from app.portfolio.schemas import AllocationOut, HistoryEventOut, HistoryOut, HistoryPointOut, SummaryOut
from app.scoping import UserScope
from app.valuation.engine import ZERO, last_session, money, previous_session
from app.valuation.service import local_day

HUNDRED = Decimal(100)
PERCENT_PLACES = Decimal("0.01")
DIVIDEND_TYPES = ("dividend", "withholding_tax")
INTEREST_TYPES = ("interest", "interest_tax")
EVENT_TYPES = ("deposit", "withdrawal", "transfer_in", "transfer_out", "buy", "sell", "dividend")
CASH_KIND = "cash"
OTHER_KIND = "other"
KIND_NAMES = {CASH_KIND: "Gotówka", "etf": "ETF", "stock": "Akcje", OTHER_KIND: "Inne"}


def percent(part: Decimal, whole: Decimal) -> Decimal | None:
    return (part * HUNDRED / whole).quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP) if whole else None


def amount_pln(db: Session, transaction: Transaction) -> Decimal:
    """The amount in PLN at the NBP rate of its day (0 while that rate is still missing)."""
    rate = fx_on(db, transaction.currency, local_day(transaction.occurred_at))
    return transaction.amount * rate if rate is not None else ZERO


def _transactions(scope: UserScope, account_id: int | None, types: tuple[str, ...]) -> list[Transaction]:
    query = scope.transactions().where(Transaction.type.in_(types))
    if account_id is not None:
        query = query.where(Transaction.account_id == account_id)
    return list(scope.db.scalars(query).unique())


def _valuations(scope: UserScope, account_id: int | None) -> Select[tuple[DailyValuation]]:
    query = scope.daily_valuations()
    return query if account_id is None else query.where(DailyValuation.account_id == account_id)


def _flow_sum() -> object:
    return func.coalesce(func.sum(DailyValuation.net_flow_pln), 0)


def _allocation(groups: dict[str, tuple[str, Decimal]], total: Decimal) -> list[AllocationOut]:
    items = [
        AllocationOut(key=key, name=name, value_pln=money(value), share_pct=percent(value, total))
        for key, (name, value) in groups.items()
    ]
    return sorted(items, key=lambda item: (-item.value_pln, item.key))


def portfolio_summary(scope: UserScope, account_id: int | None) -> SummaryOut:
    db = scope.db
    rows = _valuations(scope, account_id)
    income = _transactions(scope, account_id, DIVIDEND_TYPES + INTEREST_TYPES)
    dividends = sum((amount_pln(db, t) for t in income if t.type in DIVIDEND_TYPES), ZERO)
    interest = sum((amount_pln(db, t) for t in income if t.type in INTEREST_TYPES), ZERO)
    recalculating = db.scalar(select(User.valuations_stale_from).where(User.id == scope.user.id)) is not None
    latest = db.scalar(rows.with_only_columns(func.max(DailyValuation.date)))
    if latest is None:
        return SummaryOut(
            as_of=None, value_pln=money(ZERO), cash_pln=money(ZERO), invested_pln=money(ZERO),
            total_gain_pln=money(ZERO), total_gain_pct=None, day_change_pln=None, day_change_pct=None,
            dividends_net_pln=money(dividends), interest_net_pln=money(interest), by_account=[], by_kind=[],
            approximate_positions=0, recalculating=recalculating,
        )
    session = last_session(latest)
    previous = previous_session(session)
    totals: dict[dt.date, Decimal] = dict(db.execute(
        rows.with_only_columns(DailyValuation.date, func.sum(DailyValuation.value_pln))
        .where(DailyValuation.date.in_([latest, session, previous]))
        .group_by(DailyValuation.date)
    ).all())
    value = totals[latest]
    invested = db.scalar(rows.with_only_columns(_flow_sum()).where(DailyValuation.date <= latest))
    day_change = day_change_pct = None
    if session in totals and previous in totals:
        flows = db.scalar(rows.with_only_columns(_flow_sum()).where(
            DailyValuation.date > previous, DailyValuation.date <= session))
        day_change = money(totals[session] - totals[previous] - flows)
        day_change_pct = percent(day_change, totals[previous])
    names = {account.id: account.name for account in db.scalars(scope.accounts())}
    latest_rows = db.execute(
        rows.with_only_columns(DailyValuation.account_id, DailyValuation.instrument_id, DailyValuation.value_pln,
                               DailyValuation.flags)
        .where(DailyValuation.date == latest)
    ).all()
    instrument_ids = {row.instrument_id for row in latest_rows if row.instrument_id is not None}
    categories = dict(db.execute(
        select(Instrument.id, Instrument.category).where(Instrument.id.in_(instrument_ids))
    ).all()) if instrument_ids else {}
    by_account: dict[str, tuple[str, Decimal]] = {}
    by_kind: dict[str, tuple[str, Decimal]] = {}
    cash, approximate = ZERO, 0
    for row in latest_rows:
        account_key = str(row.account_id)
        by_account[account_key] = (names[row.account_id], by_account.get(account_key, ("", ZERO))[1] + row.value_pln)
        kind = CASH_KIND if row.instrument_id is None else (categories.get(row.instrument_id) or OTHER_KIND)
        by_kind[kind] = (KIND_NAMES.get(kind, kind), by_kind.get(kind, ("", ZERO))[1] + row.value_pln)
        if row.instrument_id is None:
            cash += row.value_pln
        elif row.flags:
            approximate += 1
    gain = value - invested
    return SummaryOut(
        as_of=latest, value_pln=money(value), cash_pln=money(cash), invested_pln=money(invested),
        total_gain_pln=money(gain), total_gain_pct=percent(gain, invested) if invested > 0 else None,
        day_change_pln=day_change, day_change_pct=day_change_pct,
        dividends_net_pln=money(dividends), interest_net_pln=money(interest),
        by_account=_allocation(by_account, value), by_kind=_allocation(by_kind, value),
        approximate_positions=approximate, recalculating=recalculating,
    )


def portfolio_history(
    scope: UserScope, account_id: int | None, start: dt.date | None, end: dt.date | None
) -> HistoryOut:
    """Daily value with invested capital (cumulative external flows from the very first day) and operations."""
    db = scope.db

    def inside(day: dt.date) -> bool:
        return (start is None or day >= start) and (end is None or day <= end)

    grouped = db.execute(
        _valuations(scope, account_id)
        .with_only_columns(DailyValuation.date, func.sum(DailyValuation.value_pln), func.sum(DailyValuation.net_flow_pln))
        .group_by(DailyValuation.date)
        .order_by(DailyValuation.date)
    ).all()
    invested = ZERO
    points = []
    for day, value, flow in grouped:
        invested += flow
        if inside(day):
            points.append(HistoryPointOut(date=day, value_pln=money(value), invested_pln=money(invested),
                                          net_flow_pln=money(flow)))
    buckets: dict[tuple[dt.date, str], Decimal] = defaultdict(Decimal)
    for transaction in _transactions(scope, account_id, EVENT_TYPES):
        day = local_day(transaction.occurred_at)
        if inside(day):
            buckets[(day, transaction.type)] += amount_pln(db, transaction)
    events = [HistoryEventOut(date=day, type=type_, amount_pln=money(amount))
              for (day, type_), amount in sorted(buckets.items())]
    return HistoryOut(points=points, events=events)
```

- [ ] **Step 6: Router**

`api/app/portfolio/router.py`:
```python
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, Depends, Query

from app.portfolio.schemas import HistoryOut, SummaryOut
from app.portfolio.service import portfolio_history, portfolio_summary
from app.scoping import UserScope, get_scope

router = APIRouter(prefix="/api", tags=["portfolio"])

AccountFilter = Annotated[int | None, Query(ge=1, le=2**31 - 1)]


def _account(scope: UserScope, account_id: int | None) -> int | None:
    """A filter by someone else's account is a 404, like the account itself."""
    if account_id is not None:
        scope.get_account(account_id)
    return account_id


@router.get("/portfolio/summary", response_model=SummaryOut)
def get_summary(scope: UserScope = Depends(get_scope), account_id: AccountFilter = None) -> SummaryOut:
    return portfolio_summary(scope, _account(scope, account_id))


@router.get("/portfolio/history", response_model=HistoryOut)
def get_history(
    scope: UserScope = Depends(get_scope),
    account_id: AccountFilter = None,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> HistoryOut:
    return portfolio_history(scope, _account(scope, account_id), start, end)
```
`api/app/portfolio/__init__.py` — pusty plik. W `api/app/main.py` dodaj `from app.portfolio.router import router as portfolio_router` i w `create_app` po ostatnim `include_router`: `app.include_router(portfolio_router)`.

- [ ] **Step 7: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest tests/test_portfolio_api.py -v`
Expected: PASS — 7 testów.

- [ ] **Step 8: Commit**

```bash
git add api/app/portfolio api/app/scoping.py api/app/main.py api/tests/test_portfolio_api.py
git commit -m "feat(portfolio): dashboard summary and value history API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: API pozycji — lista i szczegóły

**Files:**
- Modify: `api/app/portfolio/schemas.py`, `api/app/portfolio/service.py`, `api/app/portfolio/router.py`, `README.md`
- Test: `api/tests/test_positions_api.py`

**Interfaces:**
- Consumes: `load_inputs`, `local_day`, `local_today` (Task 6); `replay`, `Book`, `PositionView`, `last_session`, `previous_session`, `money`, `ZERO` (Task 5); `percent`, `amount_pln`, `AccountFilter`, `_account` (Task 8); `TransactionOut` (plan 2); `UserScope.instruments()`, `get_instrument()` (plan 3).
- Produces: `GET /api/positions?account_id=&date=` → `list[PositionOut]` (pozycje otwarte, potem gotówka kont); `GET /api/positions/{account_id}/{instrument_id}?date=` → `PositionDetailOut`; funkcje `build_positions(scope, inputs, day, account_id) -> tuple[Book, list[PositionOut]]`, `list_positions(scope, account_id, day)`, `position_detail(scope, account, instrument, day)`.

- [ ] **Step 1: Napisz testy**

`api/tests/test_positions_api.py`:
```python
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Price, Transaction, User
from tests.valuation_seed import seed_holdings, seed_market, seed_snapshot

LoginAs = Callable[[str], dict[str, str]]
ON = {"date": "2026-09-26"}


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = seed_holdings(db, user_id, instrument_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id, "instrument_id": instrument_id}


def _detail(client: TestClient, world: dict, who: str = "anna") -> dict:
    url = f"/api/positions/{world['account_id']}/{world['instrument_id']}"
    return client.get(url, params=ON, headers=world[who]).json()


def test_positions_list_open_instruments_and_cash_with_the_profit_breakdown(client: TestClient, world: dict) -> None:
    instrument, cash = client.get("/api/positions", params=ON, headers=world["anna"]).json()

    assert Decimal(instrument["quantity"]) == 2 and Decimal(instrument["price"]) == 600
    assert {key: instrument[key] for key in (
        "kind", "ticker", "name", "currency", "price_date", "price_source", "value_pln", "cost_pln", "unrealized_pln",
        "unrealized_pct", "price_effect_pln", "fx_effect_pln", "dividends_net_pln", "realized_pln", "day_change_pln",
        "share_pct", "flags",
    )} == {
        "kind": "instrument", "ticker": "SXR8.DE", "name": "Core S&P 500", "currency": "EUR", "price_date": "2026-09-25",
        "price_source": "provider", "value_pln": "5100.00", "cost_pln": "4304.30", "unrealized_pln": "795.70",
        "unrealized_pct": "18.49", "price_effect_pln": "855.70", "fx_effect_pln": "-60.00", "dividends_net_pln": "34.00",
        "realized_pln": "0.00", "day_change_pln": "800.00", "share_pct": "47.09", "flags": [],
    }
    assert (cash["kind"], cash["name"], cash["currency"], cash["value_pln"], cash["share_pct"]) == (
        "cash", "Gotówka", "PLN", "5729.70", "52.91")
    assert Decimal(cash["quantity"]) == Decimal("5729.70")


def test_position_without_provider_prices_is_valued_from_xtb(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.query(Price).delete()
        db.commit()

    instrument = client.get("/api/positions", params=ON, headers=world["anna"]).json()[0]

    assert (instrument["price_source"], instrument["price"], instrument["price_date"], instrument["value_pln"],
            instrument["flags"]) == ("xtb", None, "2026-03-02", "4304.30", ["xtb_price"])


def test_positions_are_private_and_filterable_by_own_account(client: TestClient, world: dict) -> None:
    assert client.get("/api/positions", params=ON, headers=world["bartek"]).json() == []
    foreign = client.get("/api/positions", params={**ON, "account_id": world["account_id"]}, headers=world["bartek"])
    own = client.get("/api/positions", params={**ON, "account_id": world["account_id"]}, headers=world["anna"])
    assert foreign.status_code == 404
    assert len(own.json()) == 2


def test_position_detail_lists_lots_income_transactions_and_reconciles_with_xtb(
    client: TestClient, world: dict, engine: Engine
) -> None:
    with Session(engine) as db:
        seed_snapshot(db, world["account_id"], world["instrument_id"], "2")

    body = _detail(client, world)

    assert body["position"]["value_pln"] == "5100.00"
    (lot,) = body["lots"]
    assert Decimal(lot["quantity"]) == 2 and Decimal(lot["stop_loss"]) == 450
    assert {key: lot[key] for key in ("position_id", "opened_on", "open_price", "cost_pln", "value_pln", "gain_pln",
                                      "price_effect_pln", "fx_effect_pln", "holding_days", "take_profit")} == {
        "position_id": "777", "opened_on": "2026-03-02", "open_price": "500.5000", "cost_pln": "4304.30",
        "value_pln": "5100.00", "gain_pln": "795.70", "price_effect_pln": "855.70", "fx_effect_pln": "-60.00",
        "holding_days": 208, "take_profit": None,
    }
    assert body["sales"] == []
    assert [(i["date"], i["type"], i["amount_pln"]) for i in body["income"]] == [
        ("2026-06-15", "dividend", "40.00"), ("2026-06-15", "withholding_tax", "-6.00")]
    assert [t["type"] for t in body["transactions"]] == ["withholding_tax", "dividend", "buy"]
    reconciliation = body["reconciliation"]
    assert reconciliation["status"] == "ok"
    assert Decimal(reconciliation["xtb_quantity"]) == Decimal(reconciliation["calculated_quantity"]) == 2


@pytest.mark.parametrize(("volume", "status"), [("3", "mismatch"), (None, "no_snapshot")])
def test_reconciliation_reports_mismatch_and_missing_snapshot(
    client: TestClient, world: dict, engine: Engine, volume: str | None, status: str
) -> None:
    if volume is not None:
        with Session(engine) as db:
            seed_snapshot(db, world["account_id"], world["instrument_id"], volume)
    assert _detail(client, world)["reconciliation"]["status"] == status


def test_sold_out_position_leaves_the_list_but_keeps_its_realized_gain(
    client: TestClient, world: dict, engine: Engine
) -> None:
    with Session(engine) as db:
        db.add(Transaction(account_id=world["account_id"], instrument_id=world["instrument_id"], type="sell",
                           xtb_type="Stock sale", occurred_at=dt.datetime(2026, 9, 1, 10, 0, tzinfo=dt.UTC),
                           amount=Decimal("5000"), currency="PLN", quantity=Decimal("2"), price=Decimal("600"),
                           xtb_position_id="777", external_id="5", comment="CLOSE BUY 2/2 @ 600", raw={}))
        db.commit()

    positions = client.get("/api/positions", params=ON, headers=world["anna"]).json()
    body = _detail(client, world)

    assert [(p["kind"], p["value_pln"], p["share_pct"]) for p in positions] == [("cash", "10729.70", "100.00")]
    assert (Decimal(body["position"]["quantity"]), body["position"]["realized_pln"], body["lots"]) == (0, "695.70", [])
    (sale,) = body["sales"]
    assert {key: sale[key] for key in ("date", "proceeds_pln", "cost_pln", "realized_pln", "position_id", "matched")} == {
        "date": "2026-09-01", "proceeds_pln": "5000.00", "cost_pln": "4304.30", "realized_pln": "695.70",
        "position_id": "777", "matched": True,
    }


def test_someone_elses_position_is_404(client: TestClient, world: dict) -> None:
    response = client.get(f"/api/positions/{world['account_id']}/{world['instrument_id']}", headers=world["bartek"])
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
```

- [ ] **Step 2: Uruchom — ma nie przejść**

Run: `docker compose run --rm api pytest tests/test_positions_api.py -v`
Expected: FAIL — 404 dla `/api/positions` (brak endpointu).

- [ ] **Step 3: Schematy**

Dopisz do `api/app/portfolio/schemas.py` (import `from typing import Literal` i `from app.transactions.schemas import TransactionOut`):
```python
class PositionOut(BaseModel):
    kind: Literal["instrument", "cash"]
    account_id: int
    account_name: str
    instrument_id: int | None
    ticker: str | None
    name: str
    category: str | None
    currency: str | None
    quantity: Decimal  # units of the valuation day; for cash the balance in the account currency
    price: Decimal | None
    price_date: dt.date | None
    price_source: Literal["provider", "xtb"] | None
    value_pln: Decimal
    cost_pln: Decimal
    unrealized_pln: Decimal
    unrealized_pct: Decimal | None
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    dividends_net_pln: Decimal
    realized_pln: Decimal
    day_change_pln: Decimal
    share_pct: Decimal | None = None
    flags: list[str]


class LotOut(BaseModel):
    position_id: str | None
    opened_on: dt.date
    quantity: Decimal
    open_price: Decimal | None
    cost_pln: Decimal
    value_pln: Decimal
    gain_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    holding_days: int
    stop_loss: Decimal | None
    take_profit: Decimal | None


class SaleOut(BaseModel):
    date: dt.date
    quantity: Decimal
    proceeds_pln: Decimal
    cost_pln: Decimal
    realized_pln: Decimal
    position_id: str | None
    matched: bool


class IncomeOut(BaseModel):
    date: dt.date
    type: str
    amount: Decimal
    currency: str
    amount_pln: Decimal


class ReconciliationOut(BaseModel):
    status: Literal["ok", "mismatch", "no_snapshot"]
    taken_at: dt.datetime | None
    xtb_quantity: Decimal | None
    calculated_quantity: Decimal | None


class PositionDetailOut(BaseModel):
    position: PositionOut
    lots: list[LotOut]
    sales: list[SaleOut]
    income: list[IncomeOut]
    transactions: list[TransactionOut]
    reconciliation: ReconciliationOut
```

- [ ] **Step 4: Serwis**

W `api/app/portfolio/service.py` rozszerz importy:
```python
from app.models import Account, DailyValuation, Instrument, PositionLot, Transaction, User, XtbSnapshot
from app.portfolio.schemas import (
    AllocationOut, HistoryEventOut, HistoryOut, HistoryPointOut, IncomeOut, LotOut, PositionDetailOut, PositionOut,
    ReconciliationOut, SaleOut, SummaryOut,
)
from app.transactions.schemas import TransactionOut
from app.valuation.engine import ZERO, Book, PositionView, last_session, money, previous_session, replay
from app.valuation.service import Inputs, load_inputs, local_day
```
Pod `KIND_NAMES` dodaj `CASH_NAME = "Gotówka"`, a na końcu pliku:
```python
def _instrument_item(book: Book, account: Account, instrument: Instrument, view: PositionView | None,
                     day: dt.date) -> PositionOut:
    key = (account.id, instrument.id)
    realized = sum((s.realized_pln for s in book.sales if (s.account_id, s.instrument_id) == key), ZERO)
    dividends = book.dividends.get(key, ZERO) + book.withholding.get(key, ZERO)
    zero = money(ZERO)
    fields = {
        "kind": "instrument", "account_id": account.id, "account_name": account.name, "instrument_id": instrument.id,
        "ticker": instrument.xtb_ticker, "name": instrument.name, "category": instrument.category,
        "currency": instrument.currency, "dividends_net_pln": money(dividends), "realized_pln": money(realized),
    }
    if view is None:  # fully sold: only realized gain and income remain
        return PositionOut(
            **fields, quantity=ZERO, price=None, price_date=None, price_source=None, value_pln=zero, cost_pln=zero,
            unrealized_pln=zero, unrealized_pct=None, price_effect_pln=zero, fx_effect_pln=zero, day_change_pln=zero,
            flags=[],
        )
    quote = view.quote
    unrealized = view.value_pln - view.cost_pln
    session = last_session(day)
    return PositionOut(
        **fields, quantity=view.quantity,
        price=quote.price if quote else None, price_date=quote.price_date if quote else None,
        price_source=quote.source if quote else None,
        value_pln=view.value_pln, cost_pln=view.cost_pln, unrealized_pln=unrealized,
        unrealized_pct=percent(unrealized, view.cost_pln),
        price_effect_pln=view.price_effect_pln, fx_effect_pln=view.fx_effect_pln,
        day_change_pln=book.day_change(account.id, instrument.id, session, previous_session(session)),
        flags=list(view.flags),
    )


def _cash_item(book: Book, account: Account, day: dt.date) -> PositionOut:
    row = book.cash_row(account.id, day)
    zero = money(ZERO)
    return PositionOut(
        kind="cash", account_id=account.id, account_name=account.name, instrument_id=None, ticker=None, name=CASH_NAME,
        category=None, currency=book.account_currency[account.id], quantity=row.quantity or ZERO, price=None,
        price_date=None, price_source=None, value_pln=row.value_pln, cost_pln=row.value_pln, unrealized_pln=zero,
        unrealized_pct=None, price_effect_pln=zero, fx_effect_pln=zero, dividends_net_pln=zero, realized_pln=zero,
        day_change_pln=zero, flags=list(row.flags),
    )


def build_positions(
    scope: UserScope, inputs: Inputs, day: dt.date, account_id: int | None
) -> tuple[Book, list[PositionOut]]:
    """Open positions, then each account's cash, valued on `day`; shares are of the listed total."""
    db = scope.db
    book = replay(inputs.entries, inputs.splits, inputs.market, day)
    accounts = {account.id: account for account in db.scalars(scope.accounts())}
    instruments = {instrument.id: instrument for instrument in db.scalars(scope.instruments())}
    items: list[PositionOut] = []
    for owner, instrument_id in sorted(book.lots):
        if account_id is not None and owner != account_id:
            continue
        view = book.position(owner, instrument_id, day)
        if view is not None:
            items.append(_instrument_item(book, accounts[owner], instruments[instrument_id], view, day))
    for owner in sorted(book.cash):
        if account_id is None or owner == account_id:
            items.append(_cash_item(book, accounts[owner], day))
    total = sum((item.value_pln for item in items), ZERO)
    for item in items:
        item.share_pct = percent(item.value_pln, total)
    return book, items


def list_positions(scope: UserScope, account_id: int | None, day: dt.date) -> list[PositionOut]:
    return build_positions(scope, load_inputs(scope), day, account_id)[1]


def _reconciliation(db: Session, book: Book, inputs: Inputs, account: Account, instrument: Instrument) -> ReconciliationOut:
    """Our quantity on the day of the account's newest XTB import vs XTB's Open Positions summary row."""
    # `account` already passed scope.get_account, so its snapshots are the user's own.
    taken_at = db.scalar(select(func.max(XtbSnapshot.taken_at)).where(XtbSnapshot.account_id == account.id))
    if taken_at is None:
        return ReconciliationOut(status="no_snapshot", taken_at=None, xtb_quantity=None, calculated_quantity=None)
    xtb = db.scalar(select(func.coalesce(func.sum(XtbSnapshot.volume), 0)).where(
        XtbSnapshot.account_id == account.id, XtbSnapshot.instrument_id == instrument.id,
        XtbSnapshot.row_kind == "instrument_summary", XtbSnapshot.taken_at == taken_at,
    ))
    snapshot_day = local_day(taken_at)
    calculated = sum(
        (
            entry.quantity * book.factor(instrument.id, entry.day) / book.factor(instrument.id, snapshot_day)
            * (1 if entry.type == "buy" else -1)
            for entry in inputs.entries
            if entry.account_id == account.id and entry.instrument_id == instrument.id
            and entry.type in ("buy", "sell") and entry.quantity and entry.day <= snapshot_day
        ),
        ZERO,
    )
    return ReconciliationOut(status="ok" if calculated == xtb else "mismatch", taken_at=taken_at,
                             xtb_quantity=xtb, calculated_quantity=calculated)


def position_detail(scope: UserScope, account: Account, instrument: Instrument, day: dt.date) -> PositionDetailOut:
    db = scope.db
    inputs = load_inputs(scope)
    book, items = build_positions(scope, inputs, day, None)
    item = next(
        (i for i in items if i.kind == "instrument" and i.account_id == account.id and i.instrument_id == instrument.id),
        None,
    ) or _instrument_item(book, account, instrument, None, day)
    view = book.position(account.id, instrument.id, day)
    stops = {
        lot.xtb_position_id: lot
        for lot in db.scalars(select(PositionLot).where(
            PositionLot.account_id == account.id, PositionLot.instrument_id == instrument.id))
    }
    lots = []
    for lot in view.lots if view else ():
        stored = stops.get(lot.position_id) if lot.position_id else None
        lots.append(LotOut(
            position_id=lot.position_id, opened_on=lot.opened_on, quantity=lot.quantity, open_price=lot.open_price,
            cost_pln=lot.cost_pln, value_pln=lot.value_pln, gain_pln=lot.value_pln - lot.cost_pln,
            price_effect_pln=lot.price_effect_pln, fx_effect_pln=lot.fx_effect_pln,
            holding_days=(day - lot.opened_on).days,
            stop_loss=stored.stop_loss if stored else None, take_profit=stored.take_profit if stored else None,
        ))
    key = (account.id, instrument.id)
    sales = [
        SaleOut(date=s.day, quantity=s.quantity, proceeds_pln=money(s.proceeds_pln), cost_pln=money(s.cost_pln),
                realized_pln=money(s.realized_pln), position_id=s.position_id, matched=s.matched)
        for s in book.sales if (s.account_id, s.instrument_id) == key
    ]
    transactions = list(db.scalars(scope.transactions().where(
        Transaction.account_id == account.id, Transaction.instrument_id == instrument.id)).unique())
    income = [
        IncomeOut(date=local_day(t.occurred_at), type=t.type, amount=t.amount, currency=t.currency,
                  amount_pln=money(amount_pln(db, t)))
        for t in reversed(transactions) if t.type in DIVIDEND_TYPES
    ]
    return PositionDetailOut(
        position=item, lots=lots, sales=sales, income=income,
        transactions=[TransactionOut.model_validate(t) for t in transactions],
        reconciliation=_reconciliation(db, book, inputs, account, instrument),
    )
```

- [ ] **Step 5: Router**

W `api/app/portfolio/router.py`: rozszerz importy (`PositionDetailOut`, `PositionOut` z `app.portfolio.schemas`; `list_positions`, `position_detail` z `app.portfolio.service`; `DbId` z `app.scoping`; `local_today` z `app.valuation.service`) i dopisz:
```python
DayQuery = Annotated[dt.date | None, Query(alias="date")]


@router.get("/positions", response_model=list[PositionOut])
def get_positions(
    scope: UserScope = Depends(get_scope), account_id: AccountFilter = None, day: DayQuery = None
) -> list[PositionOut]:
    return list_positions(scope, _account(scope, account_id), day or local_today())


@router.get("/positions/{account_id}/{instrument_id}", response_model=PositionDetailOut)
def get_position(
    account_id: DbId, instrument_id: DbId, scope: UserScope = Depends(get_scope), day: DayQuery = None
) -> PositionDetailOut:
    account, instrument = scope.get_account(account_id), scope.get_instrument(instrument_id)
    return position_detail(scope, account, instrument, day or local_today())
```

- [ ] **Step 6: Uruchom — ma przejść**

Run: `docker compose run --rm api pytest -v`
Expected: PASS — cały zestaw, w tym 8 testów z `test_positions_api.py` (7 + 1 dodatkowy z parametryzacji), bez nowych ostrzeżeń.

- [ ] **Step 7: README**

W `README.md` w tabeli „API” dopisz wiersze:
```markdown
| GET | `/api/portfolio/summary` | pulpit: wartość, gotówka, wpłacony kapitał, zysk łączny, zmiana dzienna, dywidendy i odsetki netto, alokacja wg kont i typów (`account_id`) |
| GET | `/api/portfolio/history` | wartość dzień po dniu z wpłaconym kapitałem i operacjami (`account_id`, `from`, `to`) |
| GET | `/api/positions` | pozycje i gotówka na dzień (`account_id`, `date`): wartość, koszt, zysk (efekt ceny / waluty), dywidendy, udział, źródło ceny |
| GET | `/api/positions/{account_id}/{instrument_id}` | szczegóły pozycji: partie z SL/TP, sprzedaże, dywidendy, operacje, zgodność z XTB (`date`) |
```
i pod tabelą akapit:
```markdown
### Wycena

Wartość portfela dzień po dniu jest w tabeli `daily_valuations` (pamięć podręczna — można ją skasować i odbudować).
Przelicza się w tle: zaraz po zapisie importu, po zmianie symbolu instrumentu i po każdej aktualizacji danych rynkowych
w workerze (od najwcześniejszej zmienionej daty). `recalculating: true` w `/api/portfolio/summary` oznacza, że przeliczenie
jeszcze trwa. Pozycja bez cen u dostawcy jest wyceniana ostatnią wartością z XTB i ma flagę `xtb_price`.
```

- [ ] **Step 8: Commit**

```bash
git add api/app/portfolio api/tests/test_positions_api.py README.md
git commit -m "feat(portfolio): positions list and position detail API" -m "Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
