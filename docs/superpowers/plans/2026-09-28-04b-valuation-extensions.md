# Plan 4b: Wycena — rozszerzenia (zdarzenia korporacyjne, koszty, zamknięte inwestycje, ekspozycja, limity IKE, TWR) — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Silnik wyceny z planu 4a obsługuje konwersje walorów i prywatne ręczne zdarzenia korporacyjne (z pierwszeństwem źródeł i wyłączaniem błędnych splitów Yahoo), rozbija zysk o koszty (opłaty) i zysk zrealizowany o efekt ceny i waluty, a API wystawia zamknięte inwestycje, ekspozycję walutową, limity IKE/IKZE i stopę zwrotu TWR.

**Architecture:** Wszystko liczone na bieżąco z danych, które już są (bez nowych tabel-cache). Zdarzenia korporacyjne: `corporate_actions.user_id` (NULL = wpis wspólny Yahoo/XTB), czysta funkcja `app/valuation/actions.py::resolve` wybiera jeden wpis na walor i dzień (ręczny użytkownika > XTB > dostawca; `suppress` = „brak zdarzenia”), a `Book` stosuje konwersje na początku dnia (`Book.advance`). Zamknięte inwestycje z odtworzenia historii (`replay`), ekspozycja i TWR z `daily_valuations`, limity z transakcji kont `ike`/`ikze` i tabeli `wrapper_limits`.

**Tech Stack:** jak w planach 1–4a (Python 3.12, FastAPI, SQLAlchemy 2.1, Alembic, Postgres 16, pytest w Dockerze). Bez nowych zależności.

**Spec:** `docs/superpowers/specs/2026-09-28-04b-valuation-extensions-design.md` (decyzje 4b — wiążące) oraz `docs/superpowers/specs/2026-09-26-portfolio-tracker-design.md` §6 („Splity i konwersje”, „Zamknięte inwestycje”, „Ekspozycja walutowa”, „Limity IKE/IKZE”, „Historia wartości i zwrot”), §4 (`corporate_actions`, `wrapper_limits`). Plan 4a (`docs/superpowers/plans/2026-09-27-04a-valuation-core.md`) — sekcja „Decyzje” nadal obowiązuje.

## Global Constraints

- Obowiązują wszystkie ograniczenia planów 1–4a: testy `docker compose run --rm api pytest` (z katalogu repozytorium), błędy `{code, message, details}` z `message` po polsku, dane użytkownika wyłącznie przez `UserScope`, obcy zasób → 404 `not_found`, testy nigdy nie łączą się z siecią, każdy commit kończy się linią `Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>`.
- Pieniądze, ilości, ceny, kursy: **`Decimal` / `NUMERIC`, nigdy float**. Kwoty PLN w API zaokrąglone do groszy (`money()`, `ROUND_HALF_UP`), procenty do 0,01 (`percent()` z `app/portfolio/service.py`); w JSON-ie liczby dziesiętne są stringami.
- Znaki `transactions.amount` (waluta konta): buy < 0, sell > 0, dividend > 0, withholding_tax < 0, fee < 0, deposit / transfer_in > 0, transfer_out / withdrawal < 0. `quantity` zawsze dodatnie; `price` w walucie notowania.
- Ilości w silniku są w „bieżących jednostkach” (baza cen Yahoo skorygowanych o splity): ilość z dnia D × iloczyn współczynników splitów z `effective_date > D` (`Book.factor`). Split / konwersja z `effective_date = E` dotyczy stanu z dni `< E` — konwersja działa **na początku dnia E**, przed transakcjami z dnia E.
- Wpis ręczny (`source = 'manual'`) ma zawsze `user_id` i działa **tylko na konta autora**; wpisy `provider` i `xtb` mają `user_id IS NULL` i są wspólne. Synchronizacja Yahoo (`replace_provider_splits`) zmienia wyłącznie wpisy `provider`.
- Dzień wyceny = data kalendarzowa `Europe/Warsaw` (`local_day`, `local_today` z `app/valuation/service.py`).
- Limit IKE/IKZE jest na osobę: wpłaty ze wszystkich kont użytkownika o tym samym `wrapper` sumują się w roku kalendarzowym. Seed: IKE 2026 = **28 260 zł** (obwieszczenie MRPiPS z 17.11.2025, M.P. 2025 poz. 1202).

## Doprecyzowania względem dokumentu decyzji

- **Kurs zakupu partii po konwersji** = kurs NBP **waluty notowania waloru docelowego** z dnia zakupu partii (dokument mówił o walucie waloru źródłowego). Dzięki temu efekt ceny + efekt walutowy = wartość − koszt także wtedy, gdy walory A i B są notowane w różnych walutach — tak samo jak w 4a („kurs zakupu = kurs NBP waluty notowania z dnia zakupu”).
- **Walor docelowy konwersji podaje się tickerem XTB** (`target_ticker`), nie `id`: walor, którego nikt jeszcze nie importował, jest tworzony (wspólny, jak przy imporcie) i dostaje ceny w najbliższym ticku „backfill” workera. Użytkownik widzi walor docelowy swojej konwersji (`UserScope.instruments()`), worker pobiera dla niego ceny i kursy.
- **Zmiana wpisu ręcznego to `PUT`** (pełne dane wpisu), nie `PATCH` — wpis ma kilka zależnych pól (typ ↔ stosunek ↔ walor docelowy), które walidujemy razem.
- **Ekspozycja walutowa przyjmuje `from` / `to`** jak `/api/portfolio/history` (zamiast `range=1M|3M|…`), żeby frontend liczył zakresy w jednym miejscu.
- Ręczne wpisy sprzed tej migracji (plan 4a nie miał API, więc istnieją tylko w danych testowych) są usuwane w migracji 0005 — nie mają właściciela.

## Review Focus

- Konwersja na walor bez żadnych cen (nowy ticker) → pozycja widoczna na walorze docelowym z ilością i kosztem, wartość 0 z flagą `xtb_price` (nie błąd 500), a worker pobiera jego ceny w najbliższym ticku. *(Task 3, Task 4)*
- Ręczny wpis jednego użytkownika (split, `suppress`, konwersja) nigdy nie zmienia wyceny ani listy walorów innego użytkownika, także gdy obaj mają ten sam walor. *(Task 3, Task 4)*
- Sprzedaż waloru bez znanej waluty notowania lub bez kursu NBP → efekt walutowy 0, cały zysk w efekcie ceny, bez wyjątku. *(Task 5)*
- Dwa konta IKE w jednym roku sumują się do jednego limitu; wypłata nie przywraca limitu; rok bez limitu w tabeli pokazuje wpłaty z `limit_pln = null`. *(Task 8)*
- Portfel opróżniony i zasilony ponownie → dni po pustym portfelu pomijane w TWR, bez dzielenia przez zero. *(Task 9)*

---

## Mapa plików

```
README.md                                        + wiersze nowych endpointów
docs/superpowers/plans/2026-09-26-00-roadmap.md  wiersz 4b → plan napisany / zrobiony
api/
  alembic/versions/0005_valuation_extensions.py  corporate_actions.user_id, typ suppress, CHECK-i, nowy klucz unikalny; wrapper_limits + seed
  app/models/valuation.py                        CorporateAction (+user_id, suppress), WrapperLimit
  app/models/__init__.py                         eksporty
  app/valuation/engine.py                        Conversion, Book.advance/_convert, fees, Sale (+opened_on, fx_effect_pln)
  app/valuation/actions.py                       Action, winning, resolve, action_of (NOWY)
  app/valuation/returns.py                       twr_index, twr_percent (NOWY)
  app/valuation/service.py                       load_inputs: widoczne zdarzenia + cele konwersji; Inputs.conversions; holders
  app/scoping.py                                 instruments(): + cele własnych konwersji
  app/market/update.py                           _referenced(): + cele konwersji
  app/corporate_actions/__init__.py              (NOWY, pusty)
  app/corporate_actions/schemas.py               CorporateActionIn/Out (NOWY)
  app/corporate_actions/router.py                GET/POST/PUT/DELETE /api/corporate-actions (NOWY)
  app/main.py                                    + router zdarzeń
  app/portfolio/schemas.py                       + fees_pln, pola sprzedaży, Closed*, Exposure*, Limit*, twr_pct
  app/portfolio/service.py                       fees, sprzedaże, TWR, conversions w replay
  app/portfolio/closed.py                        closed_investments (NOWY)
  app/portfolio/exposure.py                      currency_exposure (NOWY)
  app/portfolio/limits.py                        wrapper_limits (NOWY)
  app/portfolio/router.py                        + /closed, /exposure, /limits
  tests/test_valuation_models.py                 + ograniczenia corporate_actions, wrapper_limits, seed
  tests/test_market_store.py, test_positions_api.py   wpisy „manual” w danych testowych → „xtb”
  tests/test_valuation_actions.py                (NOWY)
  tests/test_valuation_conversions.py            (NOWY)
  tests/test_valuation_service.py                + widoczność zdarzeń, konwersja end-to-end, holders
  tests/test_market_update.py                    + ceny dla celu konwersji
  tests/test_corporate_actions_api.py            (NOWY)
  tests/test_valuation_engine_book.py            + opłaty, rozbicie zysku sprzedaży
  tests/test_positions_api.py                    + koszty, pola sprzedaży
  tests/test_closed_api.py                       (NOWY)
  tests/test_exposure_api.py                     (NOWY)
  tests/test_limits_api.py                       (NOWY)
  tests/test_valuation_returns.py                (NOWY)
  tests/test_portfolio_api.py                    + TWR w podsumowaniu i historii
```

---

### Task 1: Model — prywatne wpisy ręczne, `suppress`, `wrapper_limits` (migracja 0005)

**Files:**
- Create: `api/alembic/versions/0005_valuation_extensions.py`
- Modify: `api/app/models/valuation.py`, `api/app/models/__init__.py`, `api/tests/test_market_store.py:157-169`, `api/tests/test_positions_api.py:129-131`
- Test: `api/tests/test_valuation_models.py` + istniejący `test_models_match_migrations` w `api/tests/test_models.py`

**Interfaces:**
- Consumes: `Base`, `MONEY` z `app.models.ledger`; tabele `users`, `instruments`, `corporate_actions` (migracja 0004).
- Produces:
  - `CORPORATE_ACTION_TYPES = ("split", "reverse_split", "conversion", "suppress")`, `CORPORATE_ACTION_SOURCES = ("manual", "xtb", "provider")`, `WRAPPER_LIMIT_KINDS = ("ike", "ikze", "ikze_self_employed")` w `app.models.valuation` (eksportowane z `app.models`).
  - `CorporateAction.user_id: int | None` (FK → users, ON DELETE CASCADE, indeks); CHECK: `(source = 'manual') = (user_id IS NOT NULL)`, `(type = 'conversion') = (target_instrument_id IS NOT NULL)`, `target_instrument_id <> instrument_id`; unikalny indeks `uq_corporate_actions_instrument_id_effective_date_source_user_id` (`instrument_id`, `effective_date`, `source`, `user_id`) z `NULLS NOT DISTINCT` (zastępuje stary klucz z `type`).
  - `WrapperLimit` (tabela `wrapper_limits`): `year: int`, `wrapper: str` (PK złożony), `limit_pln: Decimal` (`MONEY`); seed `(2026, 'ike', 28260)`.

- [ ] **Step 1: Napisz testy**

Dopisz do `api/tests/test_valuation_models.py` (importy na górze pliku uzupełnij o `from alembic import command`, `from alembic.config import Config`, `WrapperLimit` z `app.models` i `from tests.conftest import API_DIR, TEST_DATABASE_URL`):

```python
def _action(instrument: Instrument, **fields: object) -> CorporateAction:
    values = {"type": "split", "effective_date": DAY, "ratio_from": Decimal("1"), "ratio_to": Decimal("10"),
              "source": "provider", **fields}
    return CorporateAction(instrument_id=instrument.id, **values)


@pytest.mark.parametrize(
    "fields",
    [
        {"source": "manual"},  # a manual entry needs its author
        {"type": "conversion"},  # a conversion needs a target
    ],
)
def test_corporate_action_owner_and_target_are_constrained(engine: Engine, clean_db: None, fields: dict) -> None:
    with Session(engine) as session:
        _, _, instrument = _world(session)
        session.add(_action(instrument, **fields))
        with pytest.raises(IntegrityError):
            session.flush()


def test_shared_action_has_no_owner_and_conversion_has_another_target(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, _, instrument = _world(session)
        session.add(_action(instrument, user_id=user.id))  # provider entry with an owner
        with pytest.raises(IntegrityError):
            session.flush()
    with Session(engine) as session:
        _, _, instrument = _world(session)
        session.add(_action(instrument, type="conversion", target_instrument_id=instrument.id))
        with pytest.raises(IntegrityError):
            session.flush()
    with Session(engine) as session:
        _, _, instrument = _world(session)
        other = Instrument(xtb_ticker="CSPX.UK", name="CSPX.UK")
        session.add(other)
        session.flush()
        session.add(_action(instrument, type="split", target_instrument_id=other.id))  # only a conversion has one
        with pytest.raises(IntegrityError):
            session.flush()


def test_one_entry_per_instrument_day_source_and_author(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        user, _, instrument = _world(session)
        other = User(email="bartek@portfolio.dev", password_hash="x")
        session.add(other)
        session.flush()
        session.add_all([
            _action(instrument),
            _action(instrument, source="xtb"),
            _action(instrument, source="manual", user_id=user.id, type="suppress", ratio_to=Decimal("1")),
            _action(instrument, source="manual", user_id=other.id),
        ])
        session.flush()
        session.add(_action(instrument, source="manual", user_id=user.id))
        with pytest.raises(IntegrityError):
            session.flush()
    with Session(engine) as session:
        _, _, instrument = _world(session)
        session.add_all([_action(instrument), _action(instrument, type="reverse_split", ratio_to=Decimal("0.5"))])
        with pytest.raises(IntegrityError):  # two provider entries on one day, whatever their type
            session.flush()


def test_wrapper_limit_kind_is_constrained(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        session.add(WrapperLimit(year=2026, wrapper="ppk", limit_pln=Decimal("1000")))
        with pytest.raises(IntegrityError):
            session.flush()


def test_migration_seeds_the_ike_limit_for_2026(engine: Engine, clean_db: None) -> None:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.downgrade(config, "0004")  # also exercises the downgrade of 0005
    command.upgrade(config, "head")
    with Session(engine) as session:
        limit = session.get(WrapperLimit, (2026, "ike"))
        assert limit is not None and limit.limit_pln == Decimal("28260.0000")
```

Uwaga: `_world` w tym pliku tworzy użytkownika o stałym e-mailu — w drugim bloku `with` pierwszego testu sesja jest nowa, a poprzednia transakcja została wycofana (`IntegrityError` bez commita), więc e-mail jest wolny.

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'WrapperLimit'`.

- [ ] **Step 3: Model**

W `api/app/models/valuation.py` dopisz `Integer` do importu z `sqlalchemy`, podmień stałe i klasę `CorporateAction`, dodaj `WrapperLimit`:

```python
CORPORATE_ACTION_TYPES = ("split", "reverse_split", "conversion", "suppress")
CORPORATE_ACTION_SOURCES = ("manual", "xtb", "provider")
WRAPPER_LIMIT_KINDS = ("ike", "ikze", "ikze_self_employed")
```

```python
class CorporateAction(Base):
    """A split, conversion or `suppress` ("no event that day") of an instrument. Split 10:1 -> ratio_from=1, ratio_to=10.

    Provider and XTB entries (`user_id` NULL) are shared by all users. A manual entry belongs to its author and
    applies to their accounts only; on one instrument and day it wins over XTB, and XTB over the provider.
    """

    __tablename__ = "corporate_actions"
    __table_args__ = (
        Index(
            "uq_corporate_actions_instrument_id_effective_date_source_user_id",
            "instrument_id", "effective_date", "source", "user_id", unique=True, postgresql_nulls_not_distinct=True,
        ),
        CheckConstraint(_in_list("type", CORPORATE_ACTION_TYPES), name="type"),
        CheckConstraint(_in_list("source", CORPORATE_ACTION_SOURCES), name="source"),
        CheckConstraint("ratio_from > 0 AND ratio_to > 0", name="ratio_positive"),
        CheckConstraint("(source = 'manual') = (user_id IS NOT NULL)", name="manual_has_user"),
        CheckConstraint("(type = 'conversion') = (target_instrument_id IS NOT NULL)", name="conversion_has_target"),
        CheckConstraint("target_instrument_id <> instrument_id", name="target_differs"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    instrument_id: Mapped[int] = mapped_column(ForeignKey("instruments.id", ondelete="CASCADE"), index=True)
    type: Mapped[str] = mapped_column(String(20))
    effective_date: Mapped[dt.date] = mapped_column(Date)
    ratio_from: Mapped[Decimal] = mapped_column(RATIO)
    ratio_to: Mapped[Decimal] = mapped_column(RATIO)
    target_instrument_id: Mapped[int | None] = mapped_column(ForeignKey("instruments.id"))
    source: Mapped[str] = mapped_column(String(10))
    user_id: Mapped[int | None] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
```

```python
class WrapperLimit(Base):
    """Statutory yearly contribution limit of an IKE / IKZE (one row per year, seeded by migrations)."""

    __tablename__ = "wrapper_limits"
    __table_args__ = (CheckConstraint(_in_list("wrapper", WRAPPER_LIMIT_KINDS), name="wrapper"),)

    year: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=False)
    wrapper: Mapped[str] = mapped_column(String(20), primary_key=True)
    limit_pln: Mapped[Decimal] = mapped_column(MONEY)
```

`UniqueConstraint` przestaje być używany w tym pliku — usuń go z importu, jeśli nic innego go nie używa.

W `api/app/models/__init__.py`:

```python
from app.models.valuation import (
    CORPORATE_ACTION_SOURCES,
    CORPORATE_ACTION_TYPES,
    WRAPPER_LIMIT_KINDS,
    CorporateAction,
    DailyValuation,
    WrapperLimit,
)
```

i dopisz `"WRAPPER_LIMIT_KINDS"` oraz `"WrapperLimit"` do `__all__` (zachowaj kolejność alfabetyczną w obu grupach).

- [ ] **Step 4: Migracja**

`api/alembic/versions/0005_valuation_extensions.py`:

```python
"""valuation extensions: private manual corporate actions, suppress, IKE/IKZE limits

Revision ID: 0005
Revises: 0004
Create Date: 2026-09-28

"""
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0005"
down_revision: str | None = "0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(20, 4)
UNIQUE_ACTION = "uq_corporate_actions_instrument_id_effective_date_source_user_id"
OLD_UNIQUE_ACTION = "uq_corporate_actions_instrument_id_type_effective_date_source"
# Obwieszczenie Ministra Rodziny, Pracy i Polityki Społecznej z 17.11.2025 (M.P. 2025 poz. 1202).
WRAPPER_LIMITS = [{"year": 2026, "wrapper": "ike", "limit_pln": Decimal("28260")}]


def upgrade() -> None:
    op.add_column("corporate_actions", sa.Column("user_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        op.f("fk_corporate_actions_user_id_users"), "corporate_actions", "users", ["user_id"], ["id"],
        ondelete="CASCADE",
    )
    op.create_index(op.f("ix_corporate_actions_user_id"), "corporate_actions", ["user_id"])
    # Manual entries had neither an API nor an owner before this revision: none can be attributed, none are kept.
    op.execute("DELETE FROM corporate_actions WHERE source = 'manual'")
    op.drop_constraint(op.f(OLD_UNIQUE_ACTION), "corporate_actions", type_="unique")
    op.create_index(
        UNIQUE_ACTION, "corporate_actions", ["instrument_id", "effective_date", "source", "user_id"],
        unique=True, postgresql_nulls_not_distinct=True,
    )
    op.drop_constraint(op.f("ck_corporate_actions_type"), "corporate_actions", type_="check")
    op.create_check_constraint(
        op.f("ck_corporate_actions_type"), "corporate_actions",
        "type IN ('split', 'reverse_split', 'conversion', 'suppress')",
    )
    op.create_check_constraint(
        op.f("ck_corporate_actions_manual_has_user"), "corporate_actions", "(source = 'manual') = (user_id IS NOT NULL)"
    )
    op.create_check_constraint(
        op.f("ck_corporate_actions_conversion_has_target"), "corporate_actions",
        "(type = 'conversion') = (target_instrument_id IS NOT NULL)",
    )
    op.create_check_constraint(
        op.f("ck_corporate_actions_target_differs"), "corporate_actions", "target_instrument_id <> instrument_id"
    )
    limits = op.create_table(
        "wrapper_limits",
        sa.Column("year", sa.Integer(), autoincrement=False, nullable=False),
        sa.Column("wrapper", sa.String(length=20), nullable=False),
        sa.Column("limit_pln", MONEY, nullable=False),
        sa.CheckConstraint("wrapper IN ('ike', 'ikze', 'ikze_self_employed')", name=op.f("ck_wrapper_limits_wrapper")),
        sa.PrimaryKeyConstraint("year", "wrapper", name=op.f("pk_wrapper_limits")),
    )
    op.bulk_insert(limits, WRAPPER_LIMITS)


def downgrade() -> None:
    op.drop_table("wrapper_limits")
    for name in ("target_differs", "conversion_has_target", "manual_has_user", "type"):
        op.drop_constraint(op.f(f"ck_corporate_actions_{name}"), "corporate_actions", type_="check")
    op.execute("DELETE FROM corporate_actions WHERE source = 'manual' OR type = 'suppress'")
    op.create_check_constraint(
        op.f("ck_corporate_actions_type"), "corporate_actions", "type IN ('split', 'reverse_split', 'conversion')"
    )
    op.drop_index(UNIQUE_ACTION, table_name="corporate_actions")
    op.create_unique_constraint(
        op.f(OLD_UNIQUE_ACTION), "corporate_actions", ["instrument_id", "type", "effective_date", "source"]
    )
    op.drop_index(op.f("ix_corporate_actions_user_id"), table_name="corporate_actions")
    op.drop_constraint(op.f("fk_corporate_actions_user_id_users"), "corporate_actions", type_="foreignkey")
    op.drop_column("corporate_actions", "user_id")
```

- [ ] **Step 5: Dane testowe z wpisami „manual” bez autora**

Dwa istniejące testy dodają wpis `source="manual"` bez `user_id` — po migracji to naruszenie CHECK. Oba potrzebują po prostu wpisu, którego Yahoo nie rusza, więc zmień źródło na `"xtb"`:

`api/tests/test_market_store.py` w `test_provider_splits_are_replaced_only_inside_the_fetched_window`: `source="manual"` → `source="xtb"`, a oczekiwana lista (sortowanie po dacie, potem źródle: `"provider"` < `"xtb"`):

```python
    assert _actions(db, instrument.id) == [
        ("split", dt.date(2021, 7, 20), Decimal(1), Decimal(4), "provider"),
        ("split", dt.date(2024, 6, 10), Decimal(1), Decimal(10), "provider"),
        ("split", dt.date(2024, 6, 10), Decimal(1), Decimal(10), "xtb"),
    ]
```

`api/tests/test_positions_api.py` w `test_reconciliation_compares_quantities_at_the_stored_precision`: `source="manual"` → `source="xtb"`.

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_valuation_models.py tests/test_models.py tests/test_market_store.py tests/test_positions_api.py -q`
Expected: PASS (także `test_models_match_migrations`).

Run: `docker compose run --rm api pytest -q`
Expected: PASS, jedno istniejące ostrzeżenie (StarletteDeprecationWarning).

- [ ] **Step 7: Commit**

```bash
git add api/alembic/versions/0005_valuation_extensions.py api/app/models/valuation.py api/app/models/__init__.py \
  api/tests/test_valuation_models.py api/tests/test_market_store.py api/tests/test_positions_api.py
git commit -m "feat(valuation): private manual corporate actions, suppress, and IKE/IKZE limits table

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 2: Silnik — pierwszeństwo źródeł i konwersje walorów

**Files:**
- Create: `api/app/valuation/actions.py`, `api/tests/test_valuation_actions.py`, `api/tests/test_valuation_conversions.py`
- Modify: `api/app/valuation/engine.py`

**Interfaces:**
- Consumes: `Split`, `Lot`, `Book`, `replay`, `daily_rows` z `app.valuation.engine` (plan 4a); `MarketData.rate(currency, day)`, `MarketData.currencies`.
- Produces:
  - `engine.Conversion(instrument_id: int, target_instrument_id: int, effective_date: date, ratio_from: Decimal, ratio_to: Decimal)` (frozen dataclass).
  - `Book(splits, market, conversions: Iterable[Conversion] = ())`; `Book.advance(day: date) -> None` stosuje zaległe konwersje z `effective_date <= day`; `Book.apply(entry)` najpierw woła `advance(entry.day)`.
  - `replay(entries, splits, market, until, conversions: Iterable[Conversion] = ()) -> Book` (na końcu `advance(until)`); `daily_rows(entries, splits, market, end, start=None, conversions: Iterable[Conversion] = ()) -> list[Row]`.
  - `actions.Action(id, instrument_id, type, effective_date, ratio_from, ratio_to, target_instrument_id, source)` (frozen dataclass); `actions.action_of(row) -> Action` (z wiersza `CorporateAction` lub czegokolwiek o tych atrybutach); `actions.winning(actions) -> dict[tuple[int, date], Action]`; `actions.resolve(actions) -> tuple[list[Split], list[Conversion]]`.

- [ ] **Step 1: Testy pierwszeństwa**

`api/tests/test_valuation_actions.py`:

```python
import datetime as dt
from decimal import Decimal as D

from app.valuation.actions import Action, resolve, winning
from app.valuation.engine import Conversion, Split

NVDA, NEW = 3, 4
JUN_10, JUL_01 = dt.date(2024, 6, 10), dt.date(2024, 7, 1)


def _action(id_: int, type_: str, source: str, day: dt.date = JUN_10, ratio: tuple[str, str] = ("1", "10"),
            target: int | None = None) -> Action:
    return Action(id_, NVDA, type_, day, D(ratio[0]), D(ratio[1]), target, source)


def test_xtb_wins_over_the_provider_and_a_manual_entry_over_both() -> None:
    provider, xtb = _action(1, "split", "provider"), _action(2, "split", "xtb", ratio=("1", "5"))
    manual = _action(3, "split", "manual", ratio=("1", "20"))

    assert winning([provider, xtb]) == {(NVDA, JUN_10): xtb}
    assert winning([manual, provider, xtb]) == {(NVDA, JUN_10): manual}


def test_suppress_hides_its_day_only() -> None:
    actions = [
        _action(1, "split", "provider"),
        _action(2, "suppress", "manual", ratio=("1", "1")),
        _action(3, "split", "provider", day=JUL_01, ratio=("1", "2")),
    ]

    assert resolve(actions) == ([Split(NVDA, JUL_01, D(1), D(2))], [])


def test_conversion_is_resolved_to_the_engine_input() -> None:
    conversion = _action(1, "conversion", "manual", ratio=("1", "2"), target=NEW)

    assert resolve([conversion]) == ([], [Conversion(NVDA, NEW, JUN_10, D(1), D(2))])
```

- [ ] **Step 2: Testy konwersji w silniku**

`api/tests/test_valuation_conversions.py`:

```python
"""A (USD) converted 1:2 into B (EUR) on 2026-06-01; one lot of 10 A bought for 4 000 zł on 2026-03-02."""
import datetime as dt
from decimal import Decimal as D

from app.valuation.engine import Conversion, Entry, Split, daily_rows, replay
from app.valuation.market_data import MarketData, Series

A, B = 1, 2
MAR_01, MAR_02, APR_01 = dt.date(2026, 3, 1), dt.date(2026, 3, 2), dt.date(2026, 4, 1)
MAY_31, JUN_01, JUN_02, JUL_01 = dt.date(2026, 5, 31), dt.date(2026, 6, 1), dt.date(2026, 6, 2), dt.date(2026, 7, 1)

BUY_A = Entry(1, 1, A, "buy", MAR_02, D("-4000"), "PLN", D("10"), D("100"), "11")
CONVERSION = Conversion(A, B, JUN_01, D(1), D(2))


def _market() -> MarketData:
    return MarketData(
        prices={A: Series([(MAR_02, D("100.00"))]), B: Series([(JUN_01, D("30.00"))])},
        currencies={A: "USD", B: "EUR"},
        fx={"USD": Series([(MAR_01, D("4.00"))]), "EUR": Series([(MAR_01, D("4.30")), (JUN_01, D("4.40"))])},
    )


def test_conversion_moves_the_lot_with_its_cost_purchase_day_and_position_id() -> None:
    book = replay([BUY_A], [], _market(), JUN_01, conversions=[CONVERSION])

    assert book.position(1, A, JUN_01) is None
    view = book.position(1, B, JUN_01)
    assert view is not None
    # 20 B × 30 EUR × 4.40; purchase rate = EUR on the purchase day (4.30): currency effect 20 × 30 × 0.10
    assert (view.quantity, view.cost_pln, view.value_pln, view.fx_effect_pln, view.price_effect_pln) == (
        D("20"), D("4000.00"), D("2640.00"), D("60.00"), D("-1420.00"))
    (lot,) = view.lots
    assert (lot.position_id, lot.opened_on) == ("11", MAR_02)


def test_daily_rows_switch_instruments_on_the_conversion_day() -> None:
    rows = daily_rows([BUY_A], [], _market(), JUN_01, conversions=[CONVERSION])

    assert {row.instrument_id for row in rows if row.day == MAY_31} == {None, A}
    assert {row.instrument_id for row in rows if row.day == JUN_01} == {None, B}


def test_the_target_is_sold_by_the_original_position_id() -> None:
    sell_b = Entry(2, 1, B, "sell", JUN_02, D("2700"), "PLN", D("20"), D("30"), "11")

    book = replay([BUY_A, sell_b], [], _market(), JUN_02, conversions=[CONVERSION])

    (sale,) = book.sales
    assert (sale.instrument_id, sale.cost_pln, sale.matched) == (B, D("4000"), True)
    assert book.position(1, B, JUN_02) is None


def test_splits_before_and_after_the_conversion_keep_the_units_consistent() -> None:
    splits = [Split(A, APR_01, D(1), D(2)), Split(B, JUL_01, D(1), D(3))]

    book = replay([BUY_A], splits, _market(), JUL_01, conversions=[CONVERSION])

    # 10 A → 20 A (split) → 40 B (conversion 1:2) → 120 B (split 1:3)
    assert book.position(1, B, JUN_01).quantity == D("40")
    assert book.position(1, B, JUL_01).quantity == D("120")


def test_a_conversion_after_the_last_transaction_still_applies() -> None:
    book = replay([BUY_A], [], _market(), JUL_01, conversions=[CONVERSION])
    assert book.position(1, B, JUL_01) is not None
```

- [ ] **Step 3: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_actions.py tests/test_valuation_conversions.py -q`
Expected: FAIL — `ImportError: cannot import name 'Conversion'` / `No module named 'app.valuation.actions'`.

- [ ] **Step 4: Konwersje w silniku**

W `api/app/valuation/engine.py` pod klasą `Split` dodaj:

```python
@dataclass(frozen=True)
class Conversion:
    """At the start of `effective_date` every lot of `instrument_id` becomes `target_instrument_id`: one unit held
    that day becomes ratio_to / ratio_from units. Cost in PLN, purchase day and position id are kept."""

    instrument_id: int
    target_instrument_id: int
    effective_date: dt.date
    ratio_from: Decimal
    ratio_to: Decimal
```

W `Book.__init__` zmień sygnaturę i dopisz stan konwersji (reszta ciała bez zmian):

```python
    def __init__(self, splits: Iterable[Split], market: MarketData, conversions: Iterable[Conversion] = ()) -> None:
        ...
        self._conversions = sorted(conversions, key=lambda c: (c.effective_date, c.instrument_id))
        self._converted = 0  # conversions applied so far (they are applied in date order)
```

Dodaj metody (np. pod `to_pln`):

```python
    def advance(self, day: dt.date) -> None:
        """Applies the conversions effective on or before `day` that have not been applied yet."""
        while self._converted < len(self._conversions) and self._conversions[self._converted].effective_date <= day:
            self._convert(self._conversions[self._converted])
            self._converted += 1

    def _convert(self, conversion: Conversion) -> None:
        day, source_id, target_id = conversion.effective_date, conversion.instrument_id, conversion.target_instrument_id
        # Current units of the source → units held on the day → units of the target → its current units.
        scale = conversion.ratio_to / conversion.ratio_from * self.factor(target_id, day) / self.factor(source_id, day)
        currency = self.market.currencies.get(target_id)
        for account_id, instrument_id in [key for key in self.lots if key[1] == source_id]:
            source = self.lots.pop((account_id, instrument_id))
            target = self.lots[(account_id, target_id)]
            for lot in source.values():
                quantity = lot.quantity * scale
                existing = target.get(lot.key)
                if existing is None:
                    # The purchase rate is the target's quote currency on the purchase day (price + currency
                    # effects must add up to value − cost in the target's currency).
                    fx_open = self.market.rate(currency, lot.opened_on)
                    target[lot.key] = Lot(lot.key, lot.position_id, lot.opened_on, quantity, lot.cost_pln, fx_open)
                else:
                    existing.quantity += quantity
                    existing.cost_pln += lot.cost_pln
```

W `Book.apply` pierwszą linią ciała dopisz:

```python
        self.advance(entry.day)
```

Podmień `replay` i `daily_rows`:

```python
def replay(
    entries: Iterable[Entry], splits: Iterable[Split], market: MarketData, until: dt.date,
    conversions: Iterable[Conversion] = (),
) -> Book:
    """The book after every transaction and conversion dated `until` or earlier."""
    book = Book(splits, market, conversions)
    for entry in _ordered(entries):
        if entry.day > until:
            break
        book.apply(entry)
    book.advance(until)
    return book


def daily_rows(
    entries: Sequence[Entry], splits: Iterable[Split], market: MarketData, end: dt.date, start: dt.date | None = None,
    conversions: Iterable[Conversion] = (),
) -> list[Row]:
    """Every day from the first transaction (or from `start`, if later) to `end`: a cash row per account and a
    row per open position. Transactions before `start` are still replayed; only their days get no rows."""
    ordered = _ordered(entries)
    if not ordered:
        return []
    book = Book(splits, market, conversions)
    rows: list[Row] = []
    index, day = 0, ordered[0].day
    while day <= end:
        book.advance(day)
        while index < len(ordered) and ordered[index].day <= day:
            book.apply(ordered[index])
            index += 1
        if start is None or day >= start:
            rows.extend(book.rows(day))
        day += ONE_DAY
    return rows
```

- [ ] **Step 5: Pierwszeństwo źródeł**

`api/app/valuation/actions.py`:

```python
"""Which corporate actions count for one user: one entry per instrument and day (pure functions, no database).

The input is already limited to the shared entries (provider, XTB) and the user's own manual ones.
"""
import datetime as dt
from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from app.valuation.engine import Conversion, Split

SOURCE_RANK = {"manual": 0, "xtb": 1, "provider": 2}  # lower wins
SPLIT_TYPES = ("split", "reverse_split")


@dataclass(frozen=True)
class Action:
    id: int
    instrument_id: int
    type: str
    effective_date: dt.date
    ratio_from: Decimal
    ratio_to: Decimal
    target_instrument_id: int | None
    source: str


def action_of(row: Any) -> Action:
    """An `Action` from a `CorporateAction` row (or anything with the same attributes)."""
    return Action(row.id, row.instrument_id, row.type, row.effective_date, row.ratio_from, row.ratio_to,
                  row.target_instrument_id, row.source)


def winning(actions: Iterable[Action]) -> dict[tuple[int, dt.date], Action]:
    """The entry that counts on each (instrument, day): manual > xtb > provider, then the lowest id."""
    best: dict[tuple[int, dt.date], Action] = {}
    for action in actions:
        key = (action.instrument_id, action.effective_date)
        current = best.get(key)
        if current is None or (SOURCE_RANK[action.source], action.id) < (SOURCE_RANK[current.source], current.id):
            best[key] = action
    return best


def resolve(actions: Iterable[Action]) -> tuple[list[Split], list[Conversion]]:
    """The splits and conversions the engine applies; a winning `suppress` removes its day's event."""
    splits: list[Split] = []
    conversions: list[Conversion] = []
    for action in sorted(winning(actions).values(), key=lambda a: (a.effective_date, a.instrument_id)):
        if action.type in SPLIT_TYPES:
            splits.append(Split(action.instrument_id, action.effective_date, action.ratio_from, action.ratio_to))
        elif action.type == "conversion":
            assert action.target_instrument_id is not None
            conversions.append(Conversion(action.instrument_id, action.target_instrument_id, action.effective_date,
                                          action.ratio_from, action.ratio_to))
    return splits, conversions
```

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_valuation_actions.py tests/test_valuation_conversions.py tests/test_valuation_engine_book.py tests/test_valuation_engine_rows.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/valuation/actions.py api/app/valuation/engine.py api/tests/test_valuation_actions.py \
  api/tests/test_valuation_conversions.py
git commit -m "feat(valuation): source precedence of corporate actions and conversions in the engine

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 3: Zdarzenia w wycenie użytkownika — widoczność, cele konwersji, worker

**Files:**
- Modify: `api/app/valuation/service.py`, `api/app/scoping.py`, `api/app/market/update.py:65-70`, `api/app/portfolio/service.py:210`
- Test: `api/tests/test_valuation_service.py`, `api/tests/test_market_update.py`

**Interfaces:**
- Consumes: `Action`, `action_of`, `resolve` (Task 2); `Conversion`, `daily_rows(..., conversions=)`, `replay(..., conversions=)` (Task 2); `CorporateAction.user_id` (Task 1).
- Produces:
  - `Inputs(entries, splits, market, conversions: list[Conversion] = [])` — `load_inputs(scope)` bierze wpisy wspólne i własne ręczne użytkownika, rozstrzyga pierwszeństwo i dociąga dane rynkowe także dla walorów docelowych konwersji (łańcuchowo).
  - `UserScope.instruments()` — walory, którymi użytkownik handlował, które ma, **lub które są celem jego własnej konwersji**.
  - `holders(db, instrument_ids) -> list[int]` — także autorzy konwersji na któryś z tych walorów.
  - `_referenced()` w `app/market/update.py` — także cele konwersji (worker pobiera ich ceny i kursy walut).
  - Każde wywołanie `replay` / `daily_rows` w aplikacji przekazuje `conversions=inputs.conversions`.

- [ ] **Step 1: Testy usługi**

Dopisz do `api/tests/test_valuation_service.py` (import `CorporateAction` z `app.models`, `Conversion`, `Split` z `app.valuation.engine`, `holders` z `app.valuation.service`):

```python
JUN_01, JUL_01 = dt.date(2026, 6, 1), dt.date(2026, 7, 1)


def _manual(db: Session, user_id: int, instrument_id: int, type_: str, day: dt.date, ratio: tuple[int, int] = (1, 1),
            target: int | None = None) -> None:
    db.add(CorporateAction(instrument_id=instrument_id, type=type_, effective_date=day, ratio_from=Decimal(ratio[0]),
                           ratio_to=Decimal(ratio[1]), target_instrument_id=target, source="manual", user_id=user_id))
    db.commit()


def _cspx(db: Session) -> int:
    """The conversion target: EUR, one close of 50 EUR on Friday 2026-09-25."""
    instrument = Instrument(xtb_ticker="CSPX.UK", name="CSPX.UK", category="etf", currency="EUR", price_symbol="CSPX.L",
                            price_checked_at=dt.datetime(2026, 9, 25, 21, 0, tzinfo=dt.UTC))
    db.add(instrument)
    db.flush()
    db.add(Price(instrument_id=instrument.id, date=FRI, close=Decimal("50.00"), source="yahoo"))
    db.commit()
    return instrument.id


def test_load_inputs_applies_shared_and_own_actions_but_not_other_users(db: Session) -> None:
    instrument_id = seed_market(db)
    anna, bartek = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    seed_holdings(db, anna, instrument_id)
    seed_holdings(db, bartek, instrument_id, number="22222222")
    db.add(CorporateAction(instrument_id=instrument_id, type="split", effective_date=JUN_01, ratio_from=Decimal(1),
                           ratio_to=Decimal(2), source="provider"))
    db.commit()
    _manual(db, anna, instrument_id, "suppress", JUN_01)
    _manual(db, bartek, instrument_id, "split", JUL_01, (1, 3))

    for_anna = load_inputs(UserScope(db, db.get(User, anna)))
    for_bartek = load_inputs(UserScope(db, db.get(User, bartek)))

    assert (for_anna.splits, for_anna.conversions) == ([], [])
    assert for_bartek.splits == [Split(instrument_id, JUN_01, Decimal(1), Decimal(2)),
                                 Split(instrument_id, JUL_01, Decimal(1), Decimal(3))]


def test_own_conversion_moves_the_valuation_to_the_target(db: Session) -> None:
    instrument_id = seed_market(db)
    target_id = _cspx(db)
    anna = seed_user(db)
    seed_holdings(db, anna, instrument_id)
    _manual(db, anna, instrument_id, "conversion", dt.date(2026, 9, 1), target=target_id)

    inputs = load_inputs(UserScope(db, db.get(User, anna)))
    valuate(db, anna)

    assert inputs.conversions == [Conversion(instrument_id, target_id, dt.date(2026, 9, 1), Decimal(1), Decimal(1))]
    assert (inputs.market.currencies[target_id], target_id in inputs.market.prices) == ("EUR", True)
    assert set(_rows(db, anna, dt.date(2026, 8, 31))) == {None, instrument_id}
    rows = _rows(db, anna, SAT)
    assert set(rows) == {None, target_id}
    assert (rows[target_id].quantity, rows[target_id].value_pln, rows[target_id].cost_pln) == (
        Decimal("2.00000000"), Decimal("425.0000"), Decimal("4304.3000"))  # 2 × 50 EUR × 4.25


def test_conversion_target_is_visible_to_its_author_only_and_makes_them_a_holder(db: Session) -> None:
    instrument_id = seed_market(db)
    target_id = _cspx(db)
    anna, bartek = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    seed_holdings(db, anna, instrument_id)
    seed_holdings(db, bartek, instrument_id, number="22222222")
    _manual(db, anna, instrument_id, "conversion", dt.date(2026, 9, 1), target=target_id)

    def tickers(user_id: int) -> list[str]:
        return [i.xtb_ticker for i in db.scalars(UserScope(db, db.get(User, user_id)).instruments())]

    assert (tickers(anna), tickers(bartek)) == (["CSPX.UK", "SXR8.DE"], ["SXR8.DE"])
    assert holders(db, [target_id]) == [anna]
```

(Jeśli `holders` nie jest jeszcze importowane w tym pliku, dopisz je do importu z `app.valuation.service`.)

- [ ] **Step 2: Test workera**

Dopisz do `api/tests/test_market_update.py` (import `CorporateAction`, `User` z `app.models`, jeśli ich brak; `PriceBar`, `PriceHistory` są już importowane):

```python
def test_conversion_target_gets_prices_although_nobody_traded_it(db: Session) -> None:
    source = _instrument(db, "SXR8.DE")
    target = Instrument(xtb_ticker="CSPX.UK", name="CSPX.UK")
    db.add(target)
    db.flush()
    owner = db.scalar(select(User.id).where(User.email == f"ref-{source.id}@portfolio.dev"))
    db.add(CorporateAction(instrument_id=source.id, type="conversion", effective_date=dt.date(2026, 9, 1),
                           ratio_from=Decimal(1), ratio_to=Decimal(1), target_instrument_id=target.id,
                           source="manual", user_id=owner))
    db.commit()
    cspx = PriceHistory("CSPX.L", "USD", (PriceBar(dt.date(2026, 9, 24), Decimal("610.00")),))

    backfill_new_instruments(db, FakePrices({"SXR8.DE": SXR8, "CSPX.L": cspx}), NOW)

    assert _stored_closes(db, target.id) == {dt.date(2026, 9, 24): Decimal("610.00000000")}
```

(`_stored_closes` jest zdefiniowane niżej w tym pliku — to funkcja modułu, więc działa. Jeśli kolumna `close` ma inną skalę niż 8 miejsc, porównuj `Decimal` liczbowo — `Decimal("610.00") == Decimal("610.00000000")` jest prawdą, więc słownik i tak się zgadza.)

- [ ] **Step 3: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_service.py tests/test_market_update.py -q`
Expected: FAIL — `Inputs` nie ma `conversions`, walor docelowy nie jest widoczny, worker nie pobiera jego cen.

- [ ] **Step 4: `load_inputs` i `holders`**

W `api/app/valuation/service.py`:
- import: `from dataclasses import dataclass, field`, `from sqlalchemy import ..., or_` (dopisz do istniejącego importu), `from app.valuation.actions import Action, action_of, resolve`, `from app.valuation.engine import Conversion, Entry, Split, daily_rows`;
- usuń stałą `SPLIT_TYPES` (po tej zmianie nieużywana).

```python
@dataclass(frozen=True)
class Inputs:
    entries: list[Entry]
    splits: list[Split]
    market: MarketData
    conversions: list[Conversion] = field(default_factory=list)


def _actions(db: Session, user_id: int, instrument_ids: set[int]) -> list[Action]:
    """Shared corporate actions and the user's own manual ones for the instruments, following conversion targets
    (a converted holding needs the target's actions too)."""
    found: dict[int, Action] = {}
    seen: set[int] = set()
    pending = set(instrument_ids)
    while pending:
        seen |= pending
        rows = db.scalars(select(CorporateAction).where(
            CorporateAction.instrument_id.in_(pending),
            or_(CorporateAction.user_id.is_(None), CorporateAction.user_id == user_id),
        )).all()
        pending = set()
        for row in rows:
            found[row.id] = action_of(row)
            if row.target_instrument_id is not None and row.target_instrument_id not in seen:
                pending.add(row.target_instrument_id)
    return list(found.values())
```

W `load_inputs` zastąp wyznaczanie `instrument_ids` i ładowanie splitów (reszta — ceny, waluty, snapshoty, kursy — bez zmian):

```python
    first_day = min(entry.day for entry in entries)
    traded = {entry.instrument_id for entry in entries if entry.instrument_id is not None}
    splits, conversions = resolve(_actions(db, scope.user.id, traded))
    instrument_ids = sorted(traded | {conversion.target_instrument_id for conversion in conversions})
    market = MarketData()
    if instrument_ids:
        market.prices = _series_from(db, Price.instrument_id, Price.date, Price.close, instrument_ids, first_day)
        market.currencies = dict(
            db.execute(select(Instrument.id, Instrument.currency).where(Instrument.id.in_(instrument_ids))).all()
        )
        snapshots: dict[object, list] = defaultdict(list)
        ...  # bez zmian
```

a na końcu:

```python
    return Inputs(entries, splits, market, conversions)
```

(Blok `splits = [Split(...) for action in db.scalars(select(CorporateAction)...)]` i deklaracja `splits: list[Split] = []` znikają.)

W `recompute_user`:

```python
        rows = daily_rows(inputs.entries, inputs.splits, inputs.market, today, start=stale_from,
                          conversions=inputs.conversions)
```

`holders`:

```python
def holders(db: Session, instrument_ids: Iterable[int]) -> list[int]:
    """Users with any transaction in one of the instruments, or whose own conversion leads into one of them."""
    ids = list(instrument_ids)
    if not ids:
        return []
    traded = db.scalars(
        select(Account.user_id).join(Transaction, Transaction.account_id == Account.id)
        .where(Transaction.instrument_id.in_(ids)).distinct()
    )
    converted = db.scalars(
        select(CorporateAction.user_id).where(
            CorporateAction.target_instrument_id.in_(ids), CorporateAction.user_id.is_not(None)
        ).distinct()
    )
    return sorted(set(traded) | set(converted))
```

- [ ] **Step 5: `UserScope.instruments()`**

W `api/app/scoping.py` dopisz `CorporateAction` do importu z `app.models` i podmień metodę:

```python
    def instruments(self) -> Select[tuple[Instrument]]:
        """Instruments this user has traded, holds, or converted a holding into. Instruments are shared;
        visibility is not."""
        own_accounts = select(Account.id).where(Account.user_id == self.user.id)
        traded = select(Transaction.instrument_id).where(
            Transaction.account_id.in_(own_accounts), Transaction.instrument_id.is_not(None)
        )
        held = select(PositionLot.instrument_id).where(PositionLot.account_id.in_(own_accounts))
        converted = select(CorporateAction.target_instrument_id).where(
            CorporateAction.user_id == self.user.id, CorporateAction.target_instrument_id.is_not(None)
        )
        return (
            select(Instrument)
            .where(or_(Instrument.id.in_(traded), Instrument.id.in_(held), Instrument.id.in_(converted)))
            .order_by(Instrument.xtb_ticker)
        )
```

- [ ] **Step 6: Worker i pozycje**

`api/app/market/update.py` (dopisz `CorporateAction` do importu z `app.models`):

```python
def _referenced() -> object:
    """Instruments are shared across users; the worker only touches ones held, traded or converted into."""
    return or_(
        exists().where(Transaction.instrument_id == Instrument.id),
        exists().where(PositionLot.instrument_id == Instrument.id),
        exists().where(CorporateAction.target_instrument_id == Instrument.id),
    )
```

`api/app/portfolio/service.py` w `build_positions`:

```python
    book = replay(inputs.entries, inputs.splits, inputs.market, day, conversions=inputs.conversions)
```

- [ ] **Step 7: Uruchom testy**

Run: `docker compose run --rm api pytest -q`
Expected: PASS, jedno istniejące ostrzeżenie.

- [ ] **Step 8: Commit**

```bash
git add api/app/valuation/service.py api/app/scoping.py api/app/market/update.py api/app/portfolio/service.py \
  api/tests/test_valuation_service.py api/tests/test_market_update.py
git commit -m "feat(valuation): apply shared and own corporate actions and follow conversion targets

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 4: API zdarzeń korporacyjnych

**Files:**
- Create: `api/app/corporate_actions/__init__.py` (pusty), `api/app/corporate_actions/schemas.py`, `api/app/corporate_actions/router.py`, `api/tests/test_corporate_actions_api.py`
- Modify: `api/app/main.py`

**Interfaces:**
- Consumes: `CorporateAction` z `user_id` (Task 1); `action_of`, `winning` (Task 2); `UserScope.get_instrument`, `UserScope.instruments()` z celami konwersji (Task 3); `mark_stale`, `recompute_in_background` z `app.valuation.service`; `get_session_factory` z `app.db`; `DbId`, `not_found` z `app.scoping`; `ApiError`.
- Produces (HTTP, prefiks `/api/corporate-actions`):
  - `GET ?instrument_id=` → `list[CorporateActionOut]`: wpisy walorów użytkownika (wspólne + własne ręczne), posortowane po walorze, dacie, id; pola `active` (wygrywa pierwszeństwo) i `editable` (własny ręczny).
  - `POST` (`CorporateActionIn`) → 201 `CorporateActionOut`; `PUT /{id}` → 200; `DELETE /{id}` → 204. Każdy zapis oznacza autora do przeliczenia od najwcześniejszej dotkniętej daty i przelicza go w tle po odpowiedzi.
  - Błędy: walor lub wpis nie użytkownika → 404 `not_found`; wspólny wpis jego waloru → 409 `shared_action`; drugi własny wpis na ten sam walor i dzień → 409 `duplicate_action`; konwersja na ten sam walor → 422 `conversion_to_itself`; niespójne pola → 422 `validation_error`.

- [ ] **Step 1: Testy API**

`api/tests/test_corporate_actions_api.py`:

```python
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import CorporateAction, Instrument, User
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/corporate-actions"
BEFORE = "10829.70"  # 2 × 600 EUR × 4.25 + 5 729.70 zł cash (tests/valuation_seed.py)
DOUBLED = "15929.70"  # after a 1:2 split effective 2026-09-25: 4 × 600 × 4.25 + 5 729.70


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        ids = {email: db.scalar(select(User.id).where(User.email == email))
               for email in ("anna@portfolio.dev", "bartek@portfolio.dev")}
        seed_holdings(db, ids["anna@portfolio.dev"], instrument_id)
        seed_holdings(db, ids["bartek@portfolio.dev"], instrument_id, number="22222222")
        for user_id in ids.values():
            valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "instrument_id": instrument_id,
            "anna_id": ids["anna@portfolio.dev"], "bartek_id": ids["bartek@portfolio.dev"]}


def _value(client: TestClient, headers: dict[str, str]) -> str:
    return client.get("/api/portfolio/summary", headers=headers).json()["value_pln"]


def _split(world: dict, ratio_to: str = "2", day: str = "2026-09-25") -> dict:
    return {"instrument_id": world["instrument_id"], "type": "split", "effective_date": day,
            "ratio_from": "1", "ratio_to": ratio_to}


def _provider_split(engine: Engine, world: dict) -> int:
    with Session(engine) as db:
        action = CorporateAction(instrument_id=world["instrument_id"], type="split", effective_date=dt.date(2026, 9, 25),
                                 ratio_from=Decimal(1), ratio_to=Decimal(2), source="provider")
        db.add(action)
        db.commit()
        for key in ("anna_id", "bartek_id"):
            valuate(db, world[key])
        return action.id


def test_own_split_changes_only_the_authors_valuation(client: TestClient, world: dict) -> None:
    response = client.post(URL, json=_split(world), headers=world["anna"])

    assert response.status_code == 201
    body = response.json()
    assert {key: body[key] for key in ("ticker", "type", "effective_date", "source", "active", "editable",
                                       "target_ticker")} == {
        "ticker": "SXR8.DE", "type": "split", "effective_date": "2026-09-25", "source": "manual", "active": True,
        "editable": True, "target_ticker": None,
    }
    assert (_value(client, world["anna"]), _value(client, world["bartek"])) == (DOUBLED, BEFORE)


def test_suppress_hides_a_provider_split_for_its_author_only(client: TestClient, world: dict, engine: Engine) -> None:
    _provider_split(engine, world)
    assert _value(client, world["anna"]) == DOUBLED

    response = client.post(URL, json={"instrument_id": world["instrument_id"], "type": "suppress",
                                      "effective_date": "2026-09-25"}, headers=world["anna"])

    assert (response.status_code, response.json()["ratio_from"], response.json()["ratio_to"]) == (
        201, "1.00000000", "1.00000000")
    assert (_value(client, world["anna"]), _value(client, world["bartek"])) == (BEFORE, DOUBLED)


def test_list_shows_shared_and_own_entries_with_precedence(client: TestClient, world: dict, engine: Engine) -> None:
    _provider_split(engine, world)
    client.post(URL, json={"instrument_id": world["instrument_id"], "type": "suppress",
                           "effective_date": "2026-09-25"}, headers=world["anna"])

    anna = client.get(URL, headers=world["anna"]).json()
    bartek = client.get(URL, params={"instrument_id": world["instrument_id"]}, headers=world["bartek"]).json()

    assert [(a["source"], a["type"], a["active"], a["editable"]) for a in anna] == [
        ("provider", "split", False, False), ("manual", "suppress", True, True)]
    assert [(a["source"], a["active"], a["editable"]) for a in bartek] == [("provider", True, False)]


def test_conversion_moves_the_holding_to_a_new_ticker(client: TestClient, world: dict, engine: Engine) -> None:
    response = client.post(URL, json={"instrument_id": world["instrument_id"], "type": "conversion",
                                      "effective_date": "2026-09-01", "ratio_from": "1", "ratio_to": "1",
                                      "target_ticker": " cspx.uk "}, headers=world["anna"])

    assert response.status_code == 201
    assert response.json()["target_ticker"] == "CSPX.UK"
    with Session(engine) as db:
        target = db.scalar(select(Instrument).where(Instrument.xtb_ticker == "CSPX.UK"))
        assert (target.category, target.exchange_suffix, target.price_checked_at) == ("etf", "UK", None)
    (item, _cash) = client.get("/api/positions", params={"date": "2026-09-26"}, headers=world["anna"]).json()
    # No prices for the new ticker yet: quantity and cost carried over, value flagged until the worker fetches them.
    assert (item["ticker"], Decimal(item["quantity"]), item["cost_pln"], item["value_pln"], item["flags"]) == (
        "CSPX.UK", 2, "4304.30", "0.00", ["xtb_price"])
    tickers = {who: [i["xtb_ticker"] for i in client.get("/api/instruments", headers=world[who]).json()]
               for who in ("anna", "bartek")}
    assert tickers == {"anna": ["CSPX.UK", "SXR8.DE"], "bartek": ["SXR8.DE"]}


def test_update_and_delete_own_entry_recompute_the_valuation(client: TestClient, world: dict) -> None:
    action_id = client.post(URL, json=_split(world), headers=world["anna"]).json()["id"]

    updated = client.put(f"{URL}/{action_id}", json=_split(world, ratio_to="3"), headers=world["anna"])
    assert (updated.status_code, _value(client, world["anna"])) == (200, "21029.70")  # 6 × 600 × 4.25 + cash

    deleted = client.delete(f"{URL}/{action_id}", headers=world["anna"])
    assert (deleted.status_code, _value(client, world["anna"])) == (204, BEFORE)


def test_shared_entry_is_read_only_and_foreign_entries_are_404(client: TestClient, world: dict, engine: Engine) -> None:
    shared_id = _provider_split(engine, world)
    bartek_id = client.post(URL, json=_split(world, day="2026-09-01"), headers=world["bartek"]).json()["id"]

    shared_put = client.put(f"{URL}/{shared_id}", json=_split(world), headers=world["anna"])
    shared_delete = client.delete(f"{URL}/{shared_id}", headers=world["anna"])
    foreign_put = client.put(f"{URL}/{bartek_id}", json=_split(world), headers=world["anna"])
    foreign_delete = client.delete(f"{URL}/{bartek_id}", headers=world["anna"])

    assert [(r.status_code, r.json()["code"]) for r in (shared_put, shared_delete, foreign_put, foreign_delete)] == [
        (409, "shared_action"), (409, "shared_action"), (404, "not_found"), (404, "not_found")]


def test_entry_for_an_instrument_the_user_does_not_have_is_404(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        other = Instrument(xtb_ticker="NVDA.US", name="NVIDIA")
        db.add(other)
        db.commit()
        other_id = other.id

    response = client.post(URL, json={**_split(world), "instrument_id": other_id}, headers=world["anna"])
    listed = client.get(URL, params={"instrument_id": other_id}, headers=world["anna"])

    assert [(r.status_code, r.json()["code"]) for r in (response, listed)] == [(404, "not_found"), (404, "not_found")]


def test_second_own_entry_on_the_same_day_is_409(client: TestClient, world: dict) -> None:
    client.post(URL, json=_split(world), headers=world["anna"])

    response = client.post(URL, json={"instrument_id": world["instrument_id"], "type": "suppress",
                                      "effective_date": "2026-09-25"}, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (409, "duplicate_action")


def test_conversion_into_itself_is_422(client: TestClient, world: dict) -> None:
    response = client.post(URL, json={"instrument_id": world["instrument_id"], "type": "conversion",
                                      "effective_date": "2026-09-01", "ratio_from": "1", "ratio_to": "1",
                                      "target_ticker": "SXR8.DE"}, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "conversion_to_itself")


@pytest.mark.parametrize(
    "fields",
    [
        {"type": "split", "ratio_from": "2", "ratio_to": "1"},
        {"type": "reverse_split", "ratio_from": "1", "ratio_to": "2"},
        {"type": "split", "ratio_from": "0", "ratio_to": "2"},
        {"type": "split", "ratio_from": "1"},
        {"type": "suppress", "ratio_from": "1", "ratio_to": "2"},
        {"type": "conversion", "ratio_from": "1", "ratio_to": "1"},
        {"type": "split", "ratio_from": "1", "ratio_to": "2", "target_ticker": "CSPX.UK"},
        {"type": "conversion", "ratio_from": "1", "ratio_to": "1", "target_ticker": "..."},
        {"type": "merger", "ratio_from": "1", "ratio_to": "1"},
    ],
)
def test_inconsistent_entries_are_rejected(client: TestClient, world: dict, fields: dict) -> None:
    body = {"instrument_id": world["instrument_id"], "effective_date": "2026-09-25", **fields}

    response = client.post(URL, json=body, headers=world["anna"])

    assert (response.status_code, response.json()["code"]) == (422, "validation_error")


def test_corporate_actions_require_login(client: TestClient) -> None:
    assert client.get(URL).status_code == 401
```

Uwaga do liczb: po zapisie przeliczenie w tle (`recompute_in_background`, w `TestClient` wykonywane zaraz po odpowiedzi) pisze wiersze do **dzisiejszej** daty (`local_today()`), a ostatnia cena i kurs są z piątku 2026-09-25 — dlatego wartość pulpitu jest taka sama jak w sobotę 2026-09-26 (tak jak testy 4a, zakładamy dziś ≥ 2026-09-26).

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_corporate_actions_api.py -q`
Expected: FAIL — 404 dla `/api/corporate-actions` (brak routera).

- [ ] **Step 3: Schematy**

`api/app/corporate_actions/schemas.py`:

```python
import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, model_validator

ActionType = Literal["split", "reverse_split", "conversion", "suppress"]
TICKER_PATTERN = r"^[A-Z0-9][A-Z0-9.\-]{0,39}$"  # XTB tickers: SXR8.DE, NVDA.US, CSPX.UK
Ratio = Annotated[Decimal, Field(gt=0, max_digits=18, decimal_places=8)]


def _ticker(value: object) -> object:
    return value.strip().upper() if isinstance(value, str) else value


class CorporateActionIn(BaseModel):
    """A manual entry. `suppress` ("no event that day") has no ratio; only a conversion has a target."""

    model_config = ConfigDict(extra="forbid")

    instrument_id: Annotated[int, Field(ge=1, le=2**31 - 1)]
    type: ActionType
    effective_date: dt.date
    ratio_from: Ratio | None = None
    ratio_to: Ratio | None = None
    # Pattern on the str branch only (see InstrumentUpdate.price_symbol for why the validator wraps the union).
    target_ticker: Annotated[Annotated[str, Field(pattern=TICKER_PATTERN)] | None, BeforeValidator(_ticker)] = None

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.type == "suppress":
            if self.ratio_from is not None or self.ratio_to is not None:
                raise ValueError("Wyłączenie zdarzenia nie ma stosunku.")
        elif self.ratio_from is None or self.ratio_to is None:
            raise ValueError("Podaj stosunek: ratio_from i ratio_to.")
        elif self.type == "split" and self.ratio_to <= self.ratio_from:
            raise ValueError("Split zwiększa liczbę akcji: ratio_to musi być większe od ratio_from.")
        elif self.type == "reverse_split" and self.ratio_to >= self.ratio_from:
            raise ValueError("Scalenie zmniejsza liczbę akcji: ratio_to musi być mniejsze od ratio_from.")
        if (self.type == "conversion") != (self.target_ticker is not None):
            raise ValueError("Walor docelowy (target_ticker) podaje się tylko przy konwersji.")
        return self


class CorporateActionOut(BaseModel):
    id: int
    instrument_id: int
    ticker: str
    type: ActionType
    effective_date: dt.date
    ratio_from: Decimal
    ratio_to: Decimal
    target_instrument_id: int | None
    target_ticker: str | None
    source: Literal["manual", "xtb", "provider"]
    active: bool  # the entry that counts for this user on its instrument and day
    editable: bool  # the user's own manual entry
```

- [ ] **Step 4: Router**

`api/app/corporate_actions/router.py`:

```python
"""Corporate actions: shared entries (provider, XTB) are read-only; a user's manual entries apply to their own
accounts only and trigger a recompute of their valuations."""
import datetime as dt
import logging
from collections.abc import Iterable
from decimal import Decimal
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy import Select, or_, select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.corporate_actions.schemas import CorporateActionIn, CorporateActionOut
from app.db import get_session_factory
from app.errors import ApiError
from app.models import CorporateAction, Instrument
from app.scoping import DbId, UserScope, get_scope, not_found
from app.valuation.actions import action_of, winning
from app.valuation.service import mark_stale, recompute_in_background

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/corporate-actions", tags=["corporate-actions"])

InstrumentFilter = Annotated[int | None, Query(ge=1, le=2**31 - 1)]
ONE = Decimal(1)
DUPLICATE = "Masz już własny wpis dla tego waloru w tym dniu."


def _visible(scope: UserScope, instrument_ids: object) -> Select[tuple[CorporateAction]]:
    """Shared entries and the user's own manual ones of the given instruments."""
    return select(CorporateAction).where(
        CorporateAction.instrument_id.in_(instrument_ids),
        or_(CorporateAction.user_id.is_(None), CorporateAction.user_id == scope.user.id),
    ).order_by(CorporateAction.instrument_id, CorporateAction.effective_date, CorporateAction.id)


def _out(scope: UserScope, actions: list[CorporateAction]) -> list[CorporateActionOut]:
    active = {action.id for action in winning(action_of(a) for a in actions).values()}
    ids = {a.instrument_id for a in actions} | {a.target_instrument_id for a in actions if a.target_instrument_id}
    tickers = dict(scope.db.execute(
        select(Instrument.id, Instrument.xtb_ticker).where(Instrument.id.in_(ids))
    ).all()) if ids else {}
    return [
        CorporateActionOut(
            id=a.id, instrument_id=a.instrument_id, ticker=tickers[a.instrument_id], type=a.type,
            effective_date=a.effective_date, ratio_from=a.ratio_from, ratio_to=a.ratio_to,
            target_instrument_id=a.target_instrument_id, target_ticker=tickers.get(a.target_instrument_id),
            source=a.source, active=a.id in active, editable=a.user_id == scope.user.id,
        )
        for a in actions
    ]


def _out_one(scope: UserScope, action: CorporateAction) -> CorporateActionOut:
    """The entry as the list shows it (`active` depends on the other entries of its instrument and day)."""
    items = _out(scope, list(scope.db.scalars(_visible(scope, [action.instrument_id]))))
    return next(item for item in items if item.id == action.id)


def _target(db: Session, ticker: str, source: Instrument) -> int:
    """The instrument with this XTB ticker; a new one is created (shared, like on import) and gets its price
    history in the worker's next backfill tick."""
    db.execute(
        insert(Instrument).values(
            xtb_ticker=ticker, name=ticker, category=source.category,
            exchange_suffix=ticker.rsplit(".", 1)[1] if "." in ticker else None,
        ).on_conflict_do_nothing(index_elements=["xtb_ticker"])
    )
    return db.scalar(select(Instrument.id).where(Instrument.xtb_ticker == ticker))


def _fill(scope: UserScope, action: CorporateAction, body: CorporateActionIn) -> None:
    instrument = scope.get_instrument(body.instrument_id)
    duplicate = select(CorporateAction.id).where(
        CorporateAction.user_id == scope.user.id, CorporateAction.instrument_id == instrument.id,
        CorporateAction.effective_date == body.effective_date,
    )
    if action.id is not None:
        duplicate = duplicate.where(CorporateAction.id != action.id)
    if scope.db.scalar(duplicate) is not None:
        raise ApiError(409, "duplicate_action", DUPLICATE)
    target_id = None
    if body.type == "conversion":
        assert body.target_ticker is not None
        if body.target_ticker == instrument.xtb_ticker:
            raise ApiError(422, "conversion_to_itself", "Walor nie może zostać zamieniony sam na siebie.")
        target_id = _target(scope.db, body.target_ticker, instrument)
    action.instrument_id = instrument.id
    action.type = body.type
    action.effective_date = body.effective_date
    action.ratio_from = body.ratio_from if body.ratio_from is not None else ONE  # suppress is stored as 1:1
    action.ratio_to = body.ratio_to if body.ratio_to is not None else ONE
    action.target_instrument_id = target_id


def _save(
    scope: UserScope, days: Iterable[dt.date], background: BackgroundTasks, sessions: sessionmaker[Session]
) -> None:
    """Marks the author's valuations from the earliest affected day, commits, recomputes after the response."""
    try:
        scope.db.flush()
    except IntegrityError:  # a concurrent request stored an entry for the same instrument and day first
        scope.db.rollback()
        raise ApiError(409, "duplicate_action", DUPLICATE) from None
    mark_stale(scope.db, [scope.user.id], min(days))
    scope.db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)


def _own(scope: UserScope, action_id: int) -> CorporateAction:
    """The user's own manual entry; a shared entry of their instrument is read-only (409), anything else is 404."""
    action = scope.db.get(CorporateAction, action_id)
    if action is None or action.user_id not in (None, scope.user.id):
        raise not_found()
    if action.user_id is None:
        scope.get_instrument(action.instrument_id)  # 404 unless the user has the instrument
        raise ApiError(409, "shared_action", "Wpis z Yahoo lub XTB można tylko przykryć własnym wpisem.")
    return action


@router.get("", response_model=list[CorporateActionOut])
def list_actions(scope: UserScope = Depends(get_scope), instrument_id: InstrumentFilter = None) -> list[CorporateActionOut]:
    if instrument_id is not None:
        ids: object = [scope.get_instrument(instrument_id).id]
    else:
        ids = scope.instruments().with_only_columns(Instrument.id).order_by(None)
    return _out(scope, list(scope.db.scalars(_visible(scope, ids))))


@router.post("", status_code=201, response_model=CorporateActionOut)
def create_action(
    body: CorporateActionIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> CorporateActionOut:
    action = CorporateAction(user_id=scope.user.id, source="manual")
    _fill(scope, action, body)
    scope.db.add(action)
    _save(scope, [action.effective_date], background, sessions)
    logger.info("User %s added a %s of instrument %s", scope.user.id, action.type, action.instrument_id)
    return _out_one(scope, action)


@router.put("/{action_id}", response_model=CorporateActionOut)
def update_action(
    action_id: DbId,
    body: CorporateActionIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> CorporateActionOut:
    action = _own(scope, action_id)
    before = action.effective_date
    _fill(scope, action, body)
    _save(scope, [before, action.effective_date], background, sessions)
    return _out_one(scope, action)


@router.delete("/{action_id}", status_code=204)
def delete_action(
    action_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    action = _own(scope, action_id)
    day = action.effective_date
    scope.db.delete(action)
    _save(scope, [day], background, sessions)
    return Response(status_code=204)
```

Uwaga: po `_save` sesja ma `expire_on_commit` — `_out_one` odczyta `action` na nowo (dodatkowe SELECT, bez znaczenia dla poprawności).

- [ ] **Step 5: Rejestracja routera**

`api/app/main.py`: `from app.corporate_actions.router import router as corporate_actions_router` (import alfabetycznie, po `accounts`) i `app.include_router(corporate_actions_router)` po `instruments_router`.

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_corporate_actions_api.py -q`
Expected: PASS.

Run: `docker compose run --rm api pytest -q`
Expected: PASS, jedno istniejące ostrzeżenie.

- [ ] **Step 7: Commit**

```bash
git add api/app/corporate_actions api/app/main.py api/tests/test_corporate_actions_api.py
git commit -m "feat(corporate-actions): API for private manual splits, conversions and suppressions

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 5: Koszty (opłaty) i rozbicie zysku zrealizowanego

**Files:**
- Modify: `api/app/valuation/engine.py`, `api/app/portfolio/schemas.py`, `api/app/portfolio/service.py`
- Test: `api/tests/test_valuation_engine_book.py`, `api/tests/test_positions_api.py`, `api/tests/test_portfolio_api.py`

**Interfaces:**
- Consumes: `Book`, `Sale`, `_take`, `_take_pro_rata` (plan 4a, z konwersjami z Task 2); `amount_pln`, `percent`, `money`.
- Produces:
  - `Book.fees: dict[Key, Decimal]` — suma opłat (`fee`, ujemne, PLN) per (konto, walor).
  - `Sale.opened_on: date` (najwcześniejsza data otwarcia sprzedanych partii), `Sale.fx_effect_pln: Decimal` (niezaokrąglony: Σ ilość × cena sprzedaży za bieżącą jednostkę × (kurs dnia sprzedaży − kurs zakupu partii)); `Sale.price_effect_pln` (property, w groszach) = `money(realized_pln) − money(fx_effect_pln)`.
  - `PositionOut.fees_pln`; `SaleOut.opened_on`, `SaleOut.holding_days`, `SaleOut.price_effect_pln`, `SaleOut.fx_effect_pln`; `SummaryOut.fees_pln` (wszystkie opłaty, także bez waloru).

- [ ] **Step 1: Testy silnika**

Dopisz do `api/tests/test_valuation_engine_book.py`:

```python
JUN_02 = dt.date(2026, 6, 2)


def _eur_market() -> MarketData:
    """SXR8 in EUR: 4.30 on the purchase day, 4.50 on the sale day."""
    return MarketData(currencies={SXR8: "EUR"}, fx={"EUR": Series([(MAR_02, D("4.30")), (JUN_02, D("4.50"))])})


def test_fees_are_kept_per_instrument_and_account() -> None:
    book = _book(_entry(1, "fee", MAR_02, "-5.00", instrument=SXR8), _entry(2, "fee", MAR_02, "-2.00"))

    assert dict(book.fees) == {(ACCOUNT, SXR8): D("-5.00")}


def test_realized_gain_splits_into_price_and_currency_effects() -> None:
    buy = _entry(1, "buy", MAR_02, "-4304.30", instrument=SXR8, quantity="2", position="777")
    sell = Entry(2, ACCOUNT, SXR8, "sell", JUN_02, D("4950.00"), "PLN", D("2"), D("550"), "777")
    book = Book((), _eur_market())
    book.apply(buy)
    book.apply(sell)

    (sale,) = book.sales
    # 2 × 550 EUR × (4.50 − 4.30) = 220 zł currency effect; the rest of 645.70 zł is the price effect
    assert (sale.opened_on, money(sale.fx_effect_pln), sale.price_effect_pln, money(sale.realized_pln)) == (
        MAR_02, D("220.00"), D("425.70"), D("645.70"))


def test_sale_without_a_known_quote_currency_has_no_currency_effect() -> None:
    unknown = 9
    buy = _entry(1, "buy", MAR_02, "-400", instrument=unknown, quantity="4", position="6")
    sell = Entry(2, ACCOUNT, unknown, "sell", JUN_02, D("480"), "PLN", D("4"), D("120"), "6")
    book = Book((), _eur_market())
    book.apply(buy)
    book.apply(sell)

    (sale,) = book.sales
    assert (sale.fx_effect_pln, sale.price_effect_pln) == (D(0), D("80.00"))
```

- [ ] **Step 2: Testy API**

Dopisz do `api/tests/test_positions_api.py`:

```python
def _add(engine: Engine, world: dict, external_id: str, type_: str, amount: str, **fields: object) -> None:
    with Session(engine) as db:
        db.add(Transaction(account_id=world["account_id"], type=type_, xtb_type=type_,
                           occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC), amount=Decimal(amount),
                           currency="PLN", external_id=external_id, comment="", raw={}, **fields))
        db.commit()


def test_fees_of_the_instrument_are_a_separate_part_of_the_gain(
    client: TestClient, world: dict, engine: Engine
) -> None:
    _add(engine, world, "5", "fee", "-5.00", instrument_id=world["instrument_id"])
    _add(engine, world, "6", "fee", "-2.00")

    (instrument, _cash) = client.get("/api/positions", params=ON, headers=world["anna"]).json()

    assert instrument["fees_pln"] == "-5.00"


def test_sale_shows_its_holding_time_and_the_price_and_currency_effects(
    client: TestClient, world: dict, engine: Engine
) -> None:
    _add(engine, world, "5", "sell", "2550.00", instrument_id=world["instrument_id"], quantity=Decimal("1"),
         price=Decimal("600"), xtb_position_id="777")

    (sale,) = _detail(client, world)["sales"]

    # cost ½ × 4 304.30 = 2 152.15; currency effect 1 × 600 EUR × (4.25 − 4.30) = −30.00
    assert {key: sale[key] for key in ("opened_on", "holding_days", "realized_pln", "price_effect_pln",
                                       "fx_effect_pln")} == {
        "opened_on": "2026-03-02", "holding_days": 207, "realized_pln": "397.85", "price_effect_pln": "427.85",
        "fx_effect_pln": "-30.00",
    }
```

Dopisz do `api/tests/test_portfolio_api.py` (import `Decimal`, `Transaction` z `app.models`):

```python
def test_summary_shows_all_fees(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        for external_id, amount in (("5", "-5.00"), ("6", "-2.00")):
            db.add(Transaction(account_id=world["account_id"], type="fee", xtb_type="SEC fee",
                               occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC), amount=Decimal(amount),
                               currency="PLN", external_id=external_id, comment="", raw={}))
        db.commit()

    assert client.get("/api/portfolio/summary", headers=world["anna"]).json()["fees_pln"] == "-7.00"
```

- [ ] **Step 3: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_engine_book.py tests/test_positions_api.py tests/test_portfolio_api.py -q`
Expected: FAIL — brak `Book.fees`, `Sale.opened_on`, pól `fees_pln` / `holding_days`.

- [ ] **Step 4: Silnik**

W `api/app/valuation/engine.py`:

`Sale` — dopisz dwa pola na końcu i właściwość:

```python
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
    opened_on: dt.date  # the earliest purchase day of the lots sold
    fx_effect_pln: Decimal  # Σ quantity × sale price × (NBP rate of the sale day − purchase rate), unrounded

    @property
    def realized_pln(self) -> Decimal:
        return self.proceeds_pln - self.cost_pln

    @property
    def price_effect_pln(self) -> Decimal:
        """The realized gain minus the currency effect, in grosze: the two add up to the rounded gain exactly."""
        return money(self.realized_pln) - money(self.fx_effect_pln)
```

`Book.__init__`: dopisz `self.fees: dict[Key, Decimal] = defaultdict(Decimal)`.

`Book.apply`: po gałęzi `withholding_tax` dopisz

```python
        elif entry.type == "fee":
            self.fees[key] += self.to_pln(entry.amount, entry.currency, entry.day)
```

Podmień `_sell` i `_take_pro_rata` (`_take` bez zmian):

```python
    def _sell(self, key: Key, entry: Entry) -> None:
        assert entry.quantity is not None and entry.instrument_id is not None
        factor = self.factor(entry.instrument_id, entry.day)
        quantity = entry.quantity * factor
        proceeds = self.to_pln(entry.amount, entry.currency, entry.day)
        lots = self.lots[key]
        target = lots.get(entry.position_id) if entry.position_id else None
        matched = target is not None and target.quantity >= quantity
        cost, remaining = ZERO, quantity
        parts: list[tuple[Lot, Decimal]] = []  # (lot, current units taken from it)
        if target is not None:
            taken = min(remaining, target.quantity)
            parts.append((target, taken))
            cost += self._take(lots, target, taken)
            remaining -= taken
        if remaining > 0:
            pro_rata_cost, pro_rata_parts = self._take_pro_rata(lots, remaining)
            cost += pro_rata_cost
            parts += pro_rata_parts
        self.sales.append(Sale(entry.account_id, entry.instrument_id, entry.day, entry.quantity, proceeds, cost,
                               entry.position_id, matched, min((lot.opened_on for lot, _ in parts), default=entry.day),
                               self._sale_fx_effect(entry, factor, parts)))
        self._record_trade(key, entry.day, proceeds / quantity)

    def _sale_fx_effect(self, entry: Entry, factor: Decimal, parts: list[tuple[Lot, Decimal]]) -> Decimal:
        """Currency effect of a sale (spec §6, like an open lot's): 0 without the sale price, the quote currency's
        rate or a lot's purchase rate."""
        assert entry.instrument_id is not None
        rate = self.market.rate(self.market.currencies.get(entry.instrument_id), entry.day)
        if rate is None or entry.price is None:
            return ZERO
        unit_price = entry.price / factor  # per current unit
        return sum(
            (taken * unit_price * (rate - lot.fx_open) for lot, taken in parts if lot.fx_open is not None), ZERO
        )

    def _take_pro_rata(self, lots: dict[str, Lot], quantity: Decimal) -> tuple[Decimal, list[tuple[Lot, Decimal]]]:
        """A sale without (enough of) a matching lot is taken from all open lots in proportion (average cost)."""
        held = sum((lot.quantity for lot in lots.values()), ZERO)
        if held <= 0:
            return ZERO, []
        whole = quantity >= held  # everything: whole lots, no inexact share
        share = quantity / held
        parts = [(lot, lot.quantity if whole else lot.quantity * share) for lot in list(lots.values())]
        return sum((self._take(lots, lot, taken) for lot, taken in parts), ZERO), parts
```

(`parts` w `_take_pro_rata` jest liczone przed pierwszym `_take`, więc udziały są takie jak dotąd.)

- [ ] **Step 5: Schematy i usługa**

`api/app/portfolio/schemas.py`:
- `SummaryOut`: po `interest_net_pln: Decimal` dopisz `fees_pln: Decimal`.
- `PositionOut`: po `dividends_net_pln: Decimal` dopisz `fees_pln: Decimal`.
- `SaleOut`:

```python
class SaleOut(BaseModel):
    date: dt.date
    opened_on: dt.date
    holding_days: int
    quantity: Decimal
    proceeds_pln: Decimal
    cost_pln: Decimal
    realized_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    position_id: str | None
    matched: bool
```

`api/app/portfolio/service.py`:
- stała `FEE_TYPES = ("fee",)` pod `INTEREST_TYPES`.
- `portfolio_summary`: `income = _transactions(scope, account_id, DIVIDEND_TYPES + INTEREST_TYPES + FEE_TYPES)`, `fees = sum((amount_pln(db, t) for t in income if t.type in FEE_TYPES), ZERO)` i `fees_pln=money(fees)` w **obu** konstruktorach `SummaryOut` (pustym i pełnym).
- `_instrument_item`: w `fields` dopisz `"fees_pln": money(book.fees.get(key, ZERO))`.
- `_cash_item`: dopisz `fees_pln=zero`.
- `position_detail`, lista `sales`:

```python
    sales = [
        SaleOut(date=s.day, opened_on=s.opened_on, holding_days=(s.day - s.opened_on).days, quantity=s.quantity,
                proceeds_pln=money(s.proceeds_pln), cost_pln=money(s.cost_pln), realized_pln=money(s.realized_pln),
                price_effect_pln=s.price_effect_pln, fx_effect_pln=money(s.fx_effect_pln),
                position_id=s.position_id, matched=s.matched)
        for s in book.sales if (s.account_id, s.instrument_id) == key
    ]
```

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest -q`
Expected: PASS, jedno istniejące ostrzeżenie.

- [ ] **Step 7: Commit**

```bash
git add api/app/valuation/engine.py api/app/portfolio/schemas.py api/app/portfolio/service.py \
  api/tests/test_valuation_engine_book.py api/tests/test_positions_api.py api/tests/test_portfolio_api.py
git commit -m "feat(valuation): fees as a part of the gain; realized gain split into price and currency effects

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---
### Task 6: Zamknięte inwestycje

**Files:**
- Create: `api/app/portfolio/closed.py`, `api/tests/test_closed_api.py`
- Modify: `api/app/portfolio/schemas.py`, `api/app/portfolio/router.py`

**Interfaces:**
- Consumes: `load_inputs` (z `conversions`, Task 3), `replay(..., conversions=)` (Task 2), `Sale.opened_on`, `Sale.fx_effect_pln`, `Sale.price_effect_pln`, `Book.fees` (Task 5), `Book.dividends`, `Book.withholding`, `Book.lots`; `money`, `percent`; `_account`, `AccountFilter` z `app/portfolio/router.py`.
- Produces: `GET /api/portfolio/closed?account_id=` → `ClosedOut {sales: list[ClosedSaleOut], investments: list[ClosedInvestmentOut], totals: ClosedTotalsOut}`; `closed_investments(scope, account_id, day) -> ClosedOut` w `app/portfolio/closed.py`.

- [ ] **Step 1: Testy**

`api/tests/test_closed_api.py`:

```python
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Transaction, User
from tests.valuation_seed import seed_holdings, seed_market

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/portfolio/closed"


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        instrument_id = seed_market(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = seed_holdings(db, user_id, instrument_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id, "instrument_id": instrument_id}


def _add(engine: Engine, world: dict, external_id: str, type_: str, amount: str, **fields: object) -> None:
    with Session(engine) as db:
        db.add(Transaction(account_id=world["account_id"], instrument_id=world["instrument_id"], type=type_,
                           xtb_type=type_, occurred_at=dt.datetime(2026, 9, 25, 10, 0, tzinfo=dt.UTC),
                           amount=Decimal(amount), currency="PLN", external_id=external_id, comment="", raw={},
                           **fields))
        db.commit()


def _sell_one(engine: Engine, world: dict, external_id: str) -> None:
    _add(engine, world, external_id, "sell", "2550.00", quantity=Decimal("1"), price=Decimal("600"),
         xtb_position_id="777")


def test_partial_sale_with_dividends_and_fees(client: TestClient, world: dict, engine: Engine) -> None:
    _sell_one(engine, world, "5")
    _add(engine, world, "6", "fee", "-5.00")

    body = client.get(URL, headers=world["anna"]).json()

    (sale,) = body["sales"]
    assert {key: sale[key] for key in (
        "ticker", "opened_on", "closed_on", "holding_days", "cost_pln", "proceeds_pln", "realized_pln",
        "price_effect_pln", "fx_effect_pln", "return_pct", "matched",
    )} == {
        "ticker": "SXR8.DE", "opened_on": "2026-03-02", "closed_on": "2026-09-25", "holding_days": 207,
        "cost_pln": "2152.15", "proceeds_pln": "2550.00", "realized_pln": "397.85", "price_effect_pln": "427.85",
        "fx_effect_pln": "-30.00", "return_pct": "18.49", "matched": True,
    }
    (investment,) = body["investments"]
    assert {key: investment[key] for key in (
        "status", "first_buy", "last_sale", "sold_cost_pln", "realized_pln", "dividends_net_pln", "fees_pln",
        "total_pln", "return_pct",
    )} == {
        "status": "partial", "first_buy": "2026-03-02", "last_sale": "2026-09-25", "sold_cost_pln": "2152.15",
        "realized_pln": "397.85", "dividends_net_pln": "34.00", "fees_pln": "-5.00", "total_pln": "426.85",
        "return_pct": "19.83",
    }
    assert body["totals"] == {"sold_cost_pln": "2152.15", "realized_pln": "397.85", "dividends_net_pln": "34.00",
                              "fees_pln": "-5.00", "total_pln": "426.85", "return_pct": "19.83"}


def test_everything_sold_is_closed(client: TestClient, world: dict, engine: Engine) -> None:
    _sell_one(engine, world, "5")
    _sell_one(engine, world, "6")

    body = client.get(URL, params={"account_id": world["account_id"]}, headers=world["anna"]).json()

    assert [s["realized_pln"] for s in body["sales"]] == ["397.85", "397.85"]
    (investment,) = body["investments"]
    assert (investment["status"], investment["sold_cost_pln"], investment["total_pln"]) == (
        "closed", "4304.30", "829.70")  # 795.70 realized + 34.00 dividends


def test_nothing_sold_gives_empty_lists_and_zero_totals(client: TestClient, world: dict) -> None:
    body = client.get(URL, headers=world["bartek"]).json()

    assert (body["sales"], body["investments"]) == ([], [])
    assert body["totals"] == {"sold_cost_pln": "0.00", "realized_pln": "0.00", "dividends_net_pln": "0.00",
                              "fees_pln": "0.00", "total_pln": "0.00", "return_pct": None}


def test_foreign_account_filter_is_404(client: TestClient, world: dict) -> None:
    response = client.get(URL, params={"account_id": world["account_id"]}, headers=world["bartek"])
    assert (response.status_code, response.json()["code"]) == (404, "not_found")
```

(Liczby: koszt 1 z 2 jednostek = 4 304,30 / 2 = 2 152,15; zysk 2 550 − 2 152,15 = 397,85; efekt walutowy 1 × 600 EUR × (4,25 − 4,30) = −30,00; 397,85 / 2 152,15 = 18,49 %; łącznie 397,85 + 34,00 − 5,00 = 426,85 → 19,83 %. Dwie sprzedaże: 2 × 397,85 = 795,70 + 34,00 = 829,70.)

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_closed_api.py -q`
Expected: FAIL — 404 dla `/api/portfolio/closed`.

- [ ] **Step 3: Schematy**

Dopisz do `api/app/portfolio/schemas.py`:

```python
class ClosedSaleOut(BaseModel):
    account_id: int
    account_name: str
    instrument_id: int
    ticker: str
    name: str
    opened_on: dt.date
    closed_on: dt.date
    holding_days: int
    quantity: Decimal  # as traded
    cost_pln: Decimal
    proceeds_pln: Decimal
    realized_pln: Decimal
    price_effect_pln: Decimal
    fx_effect_pln: Decimal
    return_pct: Decimal | None
    matched: bool


class ClosedTotalsOut(BaseModel):
    sold_cost_pln: Decimal
    realized_pln: Decimal
    dividends_net_pln: Decimal
    fees_pln: Decimal
    total_pln: Decimal  # realized + dividends + fees
    return_pct: Decimal | None  # total / sold cost


class ClosedInvestmentOut(ClosedTotalsOut):
    account_id: int
    account_name: str
    instrument_id: int
    ticker: str
    name: str
    status: Literal["closed", "partial"]
    first_buy: dt.date
    last_sale: dt.date


class ClosedOut(BaseModel):
    sales: list[ClosedSaleOut]
    investments: list[ClosedInvestmentOut]
    totals: ClosedTotalsOut
```

- [ ] **Step 4: Usługa**

`api/app/portfolio/closed.py`:

```python
"""Closed investments: every sale with its realized gain, per instrument and account (with its dividends and
fees; a partly sold holding counts all of them), and in total. Computed live by replaying the history."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from app.portfolio.schemas import ClosedInvestmentOut, ClosedOut, ClosedSaleOut, ClosedTotalsOut
from app.portfolio.service import percent
from app.scoping import UserScope
from app.valuation.engine import ZERO, Key, Sale, money, replay
from app.valuation.service import load_inputs


def _totals(sold_cost: Decimal, realized: Decimal, dividends: Decimal, fees: Decimal) -> dict[str, Decimal | None]:
    total = realized + dividends + fees
    return {"sold_cost_pln": sold_cost, "realized_pln": realized, "dividends_net_pln": dividends, "fees_pln": fees,
            "total_pln": total, "return_pct": percent(total, sold_cost)}


def closed_investments(scope: UserScope, account_id: int | None, day: dt.date) -> ClosedOut:
    inputs = load_inputs(scope)
    book = replay(inputs.entries, inputs.splits, inputs.market, day, conversions=inputs.conversions)
    accounts = {account.id: account for account in scope.db.scalars(scope.accounts())}
    instruments = {instrument.id: instrument for instrument in scope.db.scalars(scope.instruments())}
    grouped: dict[Key, list[Sale]] = defaultdict(list)
    for sale in book.sales:
        if account_id is None or sale.account_id == account_id:
            grouped[(sale.account_id, sale.instrument_id)].append(sale)

    def names(key: Key) -> dict:
        instrument = instruments[key[1]]
        return {"account_id": key[0], "account_name": accounts[key[0]].name, "instrument_id": key[1],
                "ticker": instrument.xtb_ticker, "name": instrument.name}

    sales = [
        ClosedSaleOut(
            **names((s.account_id, s.instrument_id)), opened_on=s.opened_on, closed_on=s.day,
            holding_days=(s.day - s.opened_on).days, quantity=s.quantity, cost_pln=money(s.cost_pln),
            proceeds_pln=money(s.proceeds_pln), realized_pln=money(s.realized_pln),
            price_effect_pln=s.price_effect_pln, fx_effect_pln=money(s.fx_effect_pln),
            return_pct=percent(s.realized_pln, s.cost_pln), matched=s.matched,
        )
        for group in grouped.values() for s in group
    ]
    sales.sort(key=lambda s: (s.closed_on, s.ticker, s.account_id), reverse=True)
    investments = []
    for key, group in grouped.items():
        numbers = _totals(
            money(sum((s.cost_pln for s in group), ZERO)), money(sum((s.realized_pln for s in group), ZERO)),
            money(book.dividends.get(key, ZERO) + book.withholding.get(key, ZERO)), money(book.fees.get(key, ZERO)),
        )
        investments.append(ClosedInvestmentOut(
            **names(key), **numbers, status="partial" if book.lots.get(key) else "closed",
            first_buy=min(s.opened_on for s in group), last_sale=max(s.day for s in group),
        ))
    investments.sort(key=lambda i: (i.last_sale, i.ticker, i.account_id), reverse=True)

    def summed(field: str) -> Decimal:
        return sum((getattr(item, field) for item in investments), money(ZERO))

    totals = ClosedTotalsOut(**_totals(summed("sold_cost_pln"), summed("realized_pln"), summed("dividends_net_pln"),
                                       summed("fees_pln")))
    return ClosedOut(sales=sales, investments=investments, totals=totals)
```

(`book.lots.get(key)` nie tworzy wpisu w `defaultdict`; pusty słownik partii = walor w pełni sprzedany.)

- [ ] **Step 5: Endpoint**

W `api/app/portfolio/router.py` dopisz import `from app.portfolio.closed import closed_investments` i `ClosedOut` do importu schematów, oraz:

```python
@router.get("/portfolio/closed", response_model=ClosedOut)
def get_closed(scope: UserScope = Depends(get_scope), account_id: AccountFilter = None) -> ClosedOut:
    return closed_investments(scope, _account(scope, account_id), local_today())
```

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_closed_api.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/portfolio/closed.py api/app/portfolio/schemas.py api/app/portfolio/router.py api/tests/test_closed_api.py
git commit -m "feat(portfolio): closed investments API with realized gain, dividends and fees

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 7: Ekspozycja walutowa

**Files:**
- Create: `api/app/portfolio/exposure.py`, `api/tests/test_exposure_api.py`
- Modify: `api/app/portfolio/schemas.py`, `api/app/portfolio/router.py`

**Interfaces:**
- Consumes: `DailyValuation`, `Account.currency`, `Instrument.currency`; `_valuations(scope, account_id)`, `percent` z `app/portfolio/service.py`; `money`, `ZERO`.
- Produces: `GET /api/portfolio/exposure?account_id=&from=&to=` → `ExposureOut {as_of, current: list[ExposureItemOut], history: list[ExposurePointOut]}`; waluta wiersza = waluta notowania instrumentu, gotówka = waluta konta, instrument bez waluty → `"unknown"`. `current` zawsze z najnowszego dnia (niezależnie od zakresu), `history` z zakresu.

- [ ] **Step 1: Testy**

`api/tests/test_exposure_api.py`:

```python
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select, update
from sqlalchemy.orm import Session

from app.models import Instrument, User
from tests.valuation_seed import seed_holdings, seed_market, valuate

LoginAs = Callable[[str], dict[str, str]]
URL = "/api/portfolio/exposure"


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = seed_holdings(db, user_id, seed_market(db))
        valuate(db, user_id)
    return {"anna": anna, "bartek": bartek, "account_id": account_id}


def test_exposure_now_and_over_time(client: TestClient, world: dict) -> None:
    body = client.get(URL, params={"from": "2026-09-24", "to": "2026-09-25"}, headers=world["anna"]).json()

    assert body["as_of"] == "2026-09-26"
    assert body["current"] == [
        {"currency": "PLN", "value_pln": "5729.70", "share_pct": "52.91"},
        {"currency": "EUR", "value_pln": "5100.00", "share_pct": "47.09"},
    ]
    assert body["history"] == [
        {"date": "2026-09-24", "values": {"EUR": "4300.00", "PLN": "5729.70"}},  # 2 × 500 EUR × 4.30
        {"date": "2026-09-25", "values": {"EUR": "5100.00", "PLN": "5729.70"}},
    ]


def test_instrument_without_a_known_currency_is_unknown(client: TestClient, world: dict, engine: Engine) -> None:
    with Session(engine) as db:
        db.execute(update(Instrument).values(currency=None))
        db.commit()

    current = client.get(URL, params={"account_id": world["account_id"]}, headers=world["anna"]).json()["current"]

    assert [(item["currency"], item["value_pln"]) for item in current] == [("PLN", "5729.70"), ("unknown", "5100.00")]


def test_no_valuations_and_foreign_account(client: TestClient, world: dict) -> None:
    empty = client.get(URL, headers=world["bartek"]).json()
    foreign = client.get(URL, params={"account_id": world["account_id"]}, headers=world["bartek"])

    assert empty == {"as_of": None, "current": [], "history": []}
    assert (foreign.status_code, foreign.json()["code"]) == (404, "not_found")
```

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_exposure_api.py -q`
Expected: FAIL — 404 dla `/api/portfolio/exposure`.

- [ ] **Step 3: Schematy**

Dopisz do `api/app/portfolio/schemas.py`:

```python
class ExposureItemOut(BaseModel):
    currency: str  # ISO code of the quote currency (cash: the account currency) or "unknown"
    value_pln: Decimal
    share_pct: Decimal | None


class ExposurePointOut(BaseModel):
    date: dt.date
    values: dict[str, Decimal]  # currency → value in PLN


class ExposureOut(BaseModel):
    as_of: dt.date | None
    current: list[ExposureItemOut]
    history: list[ExposurePointOut]
```

- [ ] **Step 4: Usługa**

`api/app/portfolio/exposure.py`:

```python
"""Currency exposure from the cached daily valuations: by quote currency (spec §6), cash in its account currency."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import func

from app.models import Account, DailyValuation, Instrument
from app.portfolio.schemas import ExposureItemOut, ExposureOut, ExposurePointOut
from app.portfolio.service import _valuations, percent
from app.scoping import UserScope
from app.valuation.engine import ZERO, money

UNKNOWN_CURRENCY = "unknown"  # an instrument the price provider has no quotes for


def currency_exposure(
    scope: UserScope, account_id: int | None, start: dt.date | None, end: dt.date | None
) -> ExposureOut:
    # Grouped by plain columns (a CASE with a bound literal would differ between SELECT and GROUP BY in
    # Postgres); the currency of each group is decided below.
    is_cash = DailyValuation.instrument_id.is_(None)
    query = (
        _valuations(scope, account_id)
        .with_only_columns(DailyValuation.date, is_cash, Account.currency, Instrument.currency,
                           func.sum(DailyValuation.value_pln))
        .select_from(DailyValuation)
        .join(Account, Account.id == DailyValuation.account_id)
        .outerjoin(Instrument, Instrument.id == DailyValuation.instrument_id)
        .group_by(DailyValuation.date, is_cash, Account.currency, Instrument.currency)
    )
    points: dict[dt.date, dict[str, Decimal]] = defaultdict(dict)
    for day, cash, account_currency, quote_currency, value in scope.db.execute(query):
        code = account_currency if cash else (quote_currency or UNKNOWN_CURRENCY)
        points[day][code] = points[day].get(code, ZERO) + value
    if not points:
        return ExposureOut(as_of=None, current=[], history=[])
    latest = max(points)
    total = sum(points[latest].values(), ZERO)
    current = sorted(
        (ExposureItemOut(currency=code, value_pln=money(value), share_pct=percent(value, total))
         for code, value in points[latest].items()),
        key=lambda item: (-item.value_pln, item.currency),
    )
    history = [
        ExposurePointOut(date=day, values={code: money(value) for code, value in sorted(values.items())})
        for day, values in sorted(points.items())
        if (start is None or day >= start) and (end is None or day <= end)
    ]
    return ExposureOut(as_of=latest, current=current, history=history)
```

(`_valuations` jest „prywatne” w `service.py`, ale to ten sam pakiet `portfolio` — import jest świadomy; nie kopiuj filtra.)

- [ ] **Step 5: Endpoint**

W `api/app/portfolio/router.py` (import `currency_exposure`, `ExposureOut`):

```python
@router.get("/portfolio/exposure", response_model=ExposureOut)
def get_exposure(
    scope: UserScope = Depends(get_scope),
    account_id: AccountFilter = None,
    start: Annotated[dt.date | None, Query(alias="from")] = None,
    end: Annotated[dt.date | None, Query(alias="to")] = None,
) -> ExposureOut:
    return currency_exposure(scope, _account(scope, account_id), start, end)
```

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_exposure_api.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/portfolio/exposure.py api/app/portfolio/schemas.py api/app/portfolio/router.py api/tests/test_exposure_api.py
git commit -m "feat(portfolio): currency exposure now and over time

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 8: Limity IKE/IKZE

**Files:**
- Create: `api/app/portfolio/limits.py`, `api/tests/test_limits_api.py`
- Modify: `api/app/portfolio/schemas.py`, `api/app/portfolio/router.py`

**Interfaces:**
- Consumes: `WrapperLimit` (Task 1); `Account.wrapper`; `amount_pln` z `app/portfolio/service.py`; `local_day`, `local_today`.
- Produces: `wrapper_limits(scope, today) -> list[LimitOut]` w `app/portfolio/limits.py`; `GET /api/portfolio/limits` → `list[LimitOut]` (per `wrapper` alfabetycznie, lata od bieżącego wstecz do roku pierwszej wpłaty).

- [ ] **Step 1: Testy**

`api/tests/test_limits_api.py`:

```python
import datetime as dt
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import Account, Transaction, User, WrapperLimit
from app.portfolio.limits import wrapper_limits
from app.scoping import UserScope
from tests.valuation_seed import seed_holdings, seed_market, seed_user

LoginAs = Callable[[str], dict[str, str]]
TODAY = dt.date(2026, 9, 26)


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _account(db: Session, user_id: int, name: str, wrapper: str, number: str) -> int:
    account = Account(user_id=user_id, name=name, kind="broker", wrapper=wrapper, broker="xtb",
                      external_account_number=number, currency="PLN")
    db.add(account)
    db.commit()
    return account.id


def _cash(db: Session, account_id: int, external_id: str, type_: str, amount: str, at: dt.datetime) -> None:
    db.add(Transaction(account_id=account_id, type=type_, xtb_type=type_, occurred_at=at, amount=Decimal(amount),
                       currency="PLN", external_id=external_id, comment="", raw={}))
    db.commit()


def test_contributions_to_all_ike_accounts_count_against_one_yearly_limit(db: Session) -> None:
    db.add(WrapperLimit(year=2026, wrapper="ike", limit_pln=Decimal("28260")))
    user_id = seed_user(db)
    first = seed_holdings(db, user_id, seed_market(db))  # "XTB IKE": deposit 10 000 zł on 2026-03-01
    second = _account(db, user_id, "XTB IKE 2", "ike", "22222222")
    _cash(db, second, "1", "transfer_in", "20000", dt.datetime(2026, 5, 1, 10, 0, tzinfo=dt.UTC))
    _cash(db, second, "2", "withdrawal", "-1000", dt.datetime(2026, 6, 1, 10, 0, tzinfo=dt.UTC))
    _cash(db, first, "9", "deposit", "5000", dt.datetime(2025, 12, 1, 10, 0, tzinfo=dt.UTC))
    _account(db, user_id, "XTB", "regular", "33333333")

    limits = wrapper_limits(UserScope(db, db.get(User, user_id)), TODAY)

    assert [item.model_dump(mode="json") for item in limits] == [
        {"wrapper": "ike", "year": 2026, "paid_pln": "30000.00", "limit_pln": "28260.00", "remaining_pln": "0.00",
         "exceeded": True, "accounts": [{"account_id": first, "name": "XTB IKE", "paid_pln": "10000.00"},
                                        {"account_id": second, "name": "XTB IKE 2", "paid_pln": "20000.00"}]},
        {"wrapper": "ike", "year": 2025, "paid_pln": "5000.00", "limit_pln": None, "remaining_pln": None,
         "exceeded": False, "accounts": [{"account_id": first, "name": "XTB IKE", "paid_pln": "5000.00"},
                                         {"account_id": second, "name": "XTB IKE 2", "paid_pln": "0.00"}]},
    ]


def test_ike_without_contributions_shows_the_current_year(db: Session) -> None:
    db.add(WrapperLimit(year=2026, wrapper="ike", limit_pln=Decimal("28260")))
    user_id = seed_user(db)
    _account(db, user_id, "XTB IKE", "ike", "11111111")

    (item,) = wrapper_limits(UserScope(db, db.get(User, user_id)), TODAY)

    assert (item.year, item.paid_pln, item.remaining_pln, item.exceeded) == (
        2026, Decimal("0.00"), Decimal("28260.00"), False)


def test_limits_api_lists_only_the_users_own_wrappers(client: TestClient, login_as: LoginAs, engine: Engine) -> None:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        seed_holdings(db, db.scalar(select(User.id).where(User.email == "anna@portfolio.dev")), seed_market(db))

    own = client.get("/api/portfolio/limits", headers=anna).json()
    other = client.get("/api/portfolio/limits", headers=bartek).json()

    assert [(item["wrapper"], item["year"], item["paid_pln"]) for item in own if item["year"] == 2026] == [
        ("ike", 2026, "10000.00")]
    assert other == []
```

(API używa dzisiejszej daty — test API sprawdza tylko wiersz 2026; liczby lat i limitów sprawdza test usługi z `TODAY`.)

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_limits_api.py -q`
Expected: FAIL — `No module named 'app.portfolio.limits'`.

- [ ] **Step 3: Schematy**

Dopisz do `api/app/portfolio/schemas.py`:

```python
class LimitAccountOut(BaseModel):
    account_id: int
    name: str
    paid_pln: Decimal


class LimitOut(BaseModel):
    wrapper: Literal["ike", "ikze"]
    year: int
    paid_pln: Decimal
    limit_pln: Decimal | None  # None: no statutory limit stored for that year
    remaining_pln: Decimal | None
    exceeded: bool
    accounts: list[LimitAccountOut]
```

- [ ] **Step 4: Usługa**

`api/app/portfolio/limits.py`:

```python
"""IKE / IKZE contributions per calendar year against the statutory limit. The limit is per person, so all of
the user's accounts of one wrapper count together; withdrawals do not give the limit back (spec §6)."""
import datetime as dt
from collections import defaultdict
from decimal import Decimal

from sqlalchemy import select

from app.models import Transaction, WrapperLimit
from app.portfolio.schemas import LimitAccountOut, LimitOut
from app.portfolio.service import amount_pln
from app.scoping import UserScope
from app.valuation.engine import ZERO, money
from app.valuation.service import local_day

LIMITED_WRAPPERS = ("ike", "ikze")
CONTRIBUTION_TYPES = ("deposit", "transfer_in")  # a transfer from the user's own regular account is a contribution


def wrapper_limits(scope: UserScope, today: dt.date) -> list[LimitOut]:
    db = scope.db
    accounts = [account for account in db.scalars(scope.accounts()) if account.wrapper in LIMITED_WRAPPERS]
    if not accounts:
        return []
    wrapper_of = {account.id: account.wrapper for account in accounts}
    paid: dict[tuple[str, int], dict[int, Decimal]] = defaultdict(lambda: defaultdict(Decimal))
    for transaction in db.scalars(scope.transactions().where(
        Transaction.account_id.in_(list(wrapper_of)), Transaction.type.in_(CONTRIBUTION_TYPES)
    )).unique():
        year = local_day(transaction.occurred_at).year
        paid[(wrapper_of[transaction.account_id], year)][transaction.account_id] += amount_pln(db, transaction)
    limits = {(row.wrapper, row.year): row.limit_pln for row in db.scalars(select(WrapperLimit))}
    result = []
    for wrapper in sorted(set(wrapper_of.values())):
        first_year = min((year for kind, year in paid if kind == wrapper), default=today.year)
        for year in range(today.year, first_year - 1, -1):
            by_account = paid.get((wrapper, year), {})
            total = money(sum(by_account.values(), ZERO))
            limit = limits.get((wrapper, year))
            result.append(LimitOut(
                wrapper=wrapper, year=year, paid_pln=total,
                limit_pln=money(limit) if limit is not None else None,
                remaining_pln=money(max(limit - total, ZERO)) if limit is not None else None,
                exceeded=limit is not None and total > limit,
                accounts=[LimitAccountOut(account_id=account.id, name=account.name,
                                          paid_pln=money(by_account.get(account.id, ZERO)))
                          for account in accounts if account.wrapper == wrapper],
            ))
    return result
```

(`paid.get(...)` na `defaultdict` nie tworzy wpisu.)

- [ ] **Step 5: Endpoint**

W `api/app/portfolio/router.py` (import `wrapper_limits`, `LimitOut`):

```python
@router.get("/portfolio/limits", response_model=list[LimitOut])
def get_limits(scope: UserScope = Depends(get_scope)) -> list[LimitOut]:
    return wrapper_limits(scope, local_today())
```

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_limits_api.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/portfolio/limits.py api/app/portfolio/schemas.py api/app/portfolio/router.py api/tests/test_limits_api.py
git commit -m "feat(portfolio): IKE/IKZE contributions against the yearly statutory limit

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```

---

### Task 9: TWR w pulpicie i historii; README i mapa planów

**Files:**
- Create: `api/app/valuation/returns.py`, `api/tests/test_valuation_returns.py`
- Modify: `api/app/portfolio/schemas.py`, `api/app/portfolio/service.py`, `api/tests/test_portfolio_api.py`, `README.md`, `docs/superpowers/plans/2026-09-26-00-roadmap.md`

**Interfaces:**
- Consumes: `DailyValuation` (suma `value_pln` i `net_flow_pln` per dzień); `_valuations(scope, account_id)`.
- Produces: `returns.twr_index(days: Iterable[tuple[date, Decimal, Decimal]]) -> list[tuple[date, Decimal | None]]` (współczynnik wzrostu 1 zł od pierwszego dnia z wartością); `returns.twr_percent(factor: Decimal | None) -> Decimal | None`; `SummaryOut.twr_pct`, `HistoryPointOut.twr_pct` (skumulowany od pierwszego dnia historii, nie od początku zakresu).

- [ ] **Step 1: Testy funkcji**

`api/tests/test_valuation_returns.py`:

```python
import datetime as dt
from decimal import Decimal as D

from app.valuation.returns import twr_index, twr_percent

D1, D2, D3, D4, D5, D6 = (dt.date(2026, 3, day) for day in range(1, 7))


def test_a_deposit_in_the_middle_does_not_count_as_return() -> None:
    days = [(D1, D("100"), D("100")), (D2, D("110"), D("0")), (D3, D("160"), D("50")), (D4, D("176"), D("0"))]

    factors = twr_index(days)

    # +10 % on day 2, 0 % on day 3 (the 50 zł deposit), +10 % on day 4
    assert [twr_percent(factor) for _, factor in factors] == [D("0.00"), D("10.00"), D("10.00"), D("21.00")]


def test_days_after_an_empty_portfolio_are_skipped() -> None:
    days = [(D1, D("0"), D("0")), (D2, D("100"), D("100")), (D3, D("0"), D("-100")), (D4, D("0"), D("0")),
            (D5, D("200"), D("200")), (D6, D("220"), D("0"))]

    assert [twr_percent(factor) for _, factor in twr_index(days)] == [
        None, D("0.00"), D("0.00"), D("0.00"), D("0.00"), D("10.00")]
```

- [ ] **Step 2: Testy API — zaktualizuj i dopisz**

W `api/tests/test_portfolio_api.py` w `test_history_in_a_range` dopisz `"twr_pct"` do każdego punktu (wartość rośnie z 10 000 zł wpłaconych 03-01 bez kolejnych przepływów, więc TWR = wartość / 10 000 − 1):

```python
    assert body["points"] == [
        {"date": "2026-09-24", "value_pln": "10029.70", "invested_pln": "10000.00", "net_flow_pln": "0.00",
         "twr_pct": "0.30"},
        {"date": "2026-09-25", "value_pln": "10829.70", "invested_pln": "10000.00", "net_flow_pln": "0.00",
         "twr_pct": "8.30"},
        {"date": "2026-09-26", "value_pln": "10829.70", "invested_pln": "10000.00", "net_flow_pln": "0.00",
         "twr_pct": "8.30"},
    ]
```

W `test_full_history_starts_with_the_first_deposit_and_marks_operations` pierwszy punkt:

```python
    assert body["points"][0] == {"date": "2026-03-01", "value_pln": "10000.00", "invested_pln": "10000.00",
                                 "net_flow_pln": "10000.00", "twr_pct": "0.00"}
```

Dopisz:

```python
def test_summary_shows_the_time_weighted_return(client: TestClient, world: dict) -> None:
    anna = client.get("/api/portfolio/summary", headers=world["anna"]).json()
    bartek = client.get("/api/portfolio/summary", headers=world["bartek"]).json()

    assert (anna["twr_pct"], bartek["twr_pct"]) == ("8.30", None)
```

- [ ] **Step 3: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_valuation_returns.py tests/test_portfolio_api.py -q`
Expected: FAIL — brak `app.valuation.returns`, brak `twr_pct`.

- [ ] **Step 4: Funkcje TWR**

`api/app/valuation/returns.py`:

```python
"""Time-weighted return from daily portfolio values and external flows (pure functions, spec §6)."""
import datetime as dt
from collections.abc import Iterable
from decimal import ROUND_HALF_UP, Decimal

ONE = Decimal(1)
HUNDRED = Decimal(100)
PERCENT_PLACES = Decimal("0.01")


def twr_index(days: Iterable[tuple[dt.date, Decimal, Decimal]]) -> list[tuple[dt.date, Decimal | None]]:
    """For each (day, value, net external flow) in date order: how much 1 zł held since the first day with a
    value has grown to (TWR = factor − 1), or None before that day. A flow counts at the end of its day:
    r = (V_t − F_t) / V_{t−1} − 1. A day after an empty portfolio (V_{t−1} = 0) has no return and is skipped."""
    result: list[tuple[dt.date, Decimal | None]] = []
    factor: Decimal | None = None
    previous = Decimal(0)
    for day, value, flow in days:
        if previous > 0:
            factor = (factor or ONE) * (value - flow) / previous
        elif factor is None and value > 0:
            factor = ONE
        result.append((day, factor))
        previous = value
    return result


def twr_percent(factor: Decimal | None) -> Decimal | None:
    return None if factor is None else ((factor - ONE) * HUNDRED).quantize(PERCENT_PLACES, rounding=ROUND_HALF_UP)
```

- [ ] **Step 5: Pulpit i historia**

`api/app/portfolio/schemas.py`: `SummaryOut` — po `day_change_pct` dopisz `twr_pct: Decimal | None`; `HistoryPointOut` — na końcu `twr_pct: Decimal | None`.

`api/app/portfolio/service.py` (import `from app.valuation.returns import twr_index, twr_percent`):

```python
def _daily_totals(scope: UserScope, account_id: int | None) -> list[tuple[dt.date, Decimal, Decimal]]:
    """(day, value, net external flow) of the portfolio or one account, in date order."""
    return [tuple(row) for row in scope.db.execute(
        _valuations(scope, account_id)
        .with_only_columns(DailyValuation.date, func.sum(DailyValuation.value_pln), func.sum(DailyValuation.net_flow_pln))
        .group_by(DailyValuation.date)
        .order_by(DailyValuation.date)
    )]
```

`portfolio_history` — zastąp zapytanie `grouped` i pętlę:

```python
    grouped = _daily_totals(scope, account_id)
    invested = ZERO
    points = []
    for (day, value, flow), (_, factor) in zip(grouped, twr_index(grouped), strict=True):
        invested += flow
        if inside(day):
            points.append(HistoryPointOut(date=day, value_pln=money(value), invested_pln=money(invested),
                                          net_flow_pln=money(flow), twr_pct=twr_percent(factor)))
```

`portfolio_summary` — pusty wynik dostaje `twr_pct=None`; w pełnym przed `return`:

```python
    index = twr_index(_daily_totals(scope, account_id))
```

i `twr_pct=twr_percent(index[-1][1])` w konstruktorze `SummaryOut`.

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest -q`
Expected: PASS, jedno istniejące ostrzeżenie.

- [ ] **Step 7: README i mapa planów**

`README.md` — w tabeli API po wierszu `GET /api/positions/{account_id}/{instrument_id}` dopisz:

```markdown
| GET | `/api/portfolio/closed` | zamknięte inwestycje: sprzedaże z zyskiem (efekt ceny / waluty, czas trzymania), podsumowanie per walor z dywidendami i kosztami, suma (`account_id`) |
| GET | `/api/portfolio/exposure` | ekspozycja walutowa wg waluty notowania: dziś i dzień po dniu (`account_id`, `from`, `to`) |
| GET | `/api/portfolio/limits` | wpłaty na IKE/IKZE w latach kalendarzowych vs limit ustawowy, rozbicie na konta |
| GET | `/api/corporate-actions` | splity, scalenia, konwersje walorów użytkownika (wspólne z Yahoo/XTB i własne), z informacją, który wpis obowiązuje (`instrument_id`) |
| POST | `/api/corporate-actions` | własny wpis: `split` / `reverse_split` / `conversion` (`target_ticker`) / `suppress` (wyłącza zdarzenie z Yahoo tego dnia); działa tylko na konta autora |
| PUT, DELETE | `/api/corporate-actions/{id}` | zmiana / usunięcie własnego wpisu (wpisy z Yahoo/XTB są tylko do odczytu) |
```

oraz w opisie `/api/portfolio/summary` dopisz „TWR, opłaty”, a w `/api/portfolio/history` „TWR per dzień”.

`docs/superpowers/plans/2026-09-26-00-roadmap.md` — w wierszu 4b w kolumnie „Status” wpisz `✅ zrobiony (`2026-09-28-04b-valuation-extensions.md`)`.

- [ ] **Step 8: Commit**

```bash
git add api/app/valuation/returns.py api/app/portfolio/schemas.py api/app/portfolio/service.py \
  api/tests/test_valuation_returns.py api/tests/test_portfolio_api.py README.md docs/superpowers/plans/2026-09-26-00-roadmap.md
git commit -m "feat(portfolio): time-weighted return on the dashboard and in the value history

Co-Authored-By: Claude Opus 5.5 <noreply@anthropic.com>"
```
