# Plan 5: Obligacje EDO i konta oszczędnościowe — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Aplikacja wycenia obligacje skarbowe EDO (dzień po dniu, netto po podatku, z wartością przy wcześniejszym wykupie i harmonogramem okresów) oraz konta oszczędnościowe (odsetki między saldami przepisanymi z banku), wpina oba w `daily_valuations`, pulpit, pozycje, historię i TWR, i wystawia API do ich wprowadzania.

**Architecture:** Dwa czyste moduły liczące: `app/bonds/edo.py` (jedna obligacja EDO wg listu emisyjnego) i `app/savings/interest.py` (saldo konta dzień po dniu). `app/valuation/fixed_income.py` zamienia je na wiersze `Row` (z nowymi polami `bond_holding_id` / `savings_account_id`), a `recompute_user` dokłada te wiersze do wierszy instrumentów. Dane użytkownika (zakupy, salda, stawki) idą przez `UserScope`; tabela serii jest wspólna.

**Tech Stack:** jak w planach 1–4b (Python 3.12, FastAPI, SQLAlchemy 2.1, Alembic, Postgres 16, pytest w Dockerze). Bez nowych zależności.

**Spec:** `docs/superpowers/specs/2026-09-28-05-bonds-savings-design.md` (decyzje planu 5 — wiążące) oraz `docs/superpowers/specs/2026-09-26-portfolio-tracker-design.md` §4, §6 „Obligacje skarbowe”, „Konto oszczędnościowe”, §7.

## Global Constraints

- Obowiązują ograniczenia planów 1–4b: testy `docker compose run --rm api pytest` (z katalogu repozytorium), błędy `{code, message, details}` z `message` po polsku, dane użytkownika wyłącznie przez `UserScope`, obcy zasób → 404 `not_found`, testy nigdy nie łączą się z siecią, każdy commit kończy się linią `Co-Authored-By: <model, który napisał commit> <noreply@anthropic.com>`.
- Pieniądze, stawki, ilości: **`Decimal` / `NUMERIC`, nigdy float**; kwoty w groszach `ROUND_HALF_UP`; w JSON-ie liczby dziesiętne są stringami.
- EDO: 1 szt. = 100 zł; 10 rocznych okresów liczonych **od dnia zakupu** (rocznica po rocznicy); okres 1 = stawka serii, okres k ≥ 2 = max(inflacja r/r, 0) + marża, inflacja = wskaźnik GUS **za miesiąc o dwa wcześniejszy niż pierwszy miesiąc okresu** (okres od września → CPI lipca, ogłoszony w sierpniu).
- Wartość 1 szt. w dniu d: `100 · Π_{i<k}(1 + r_i) · (1 + r_k · a_k / ACT_k)`, zaokrąglona do grosza; `a_k` = dni od początku okresu k do d, `ACT_k` = dni okresu k.
- Podatek 19 % od odsetek i opłata za wcześniejszy wykup liczone **od jednej obligacji** (przykład MF: odsetki 4,16 zł, opłata 2,00 zł, podatek 0,41 zł od 2,16 zł, wypłata 101,75 zł); opłata = min(opłata serii, narosłe odsetki); konto `ike` / `ikze` — bez podatku.
- Seed serii: `EDO0936` — 5,35 % w 1. roku, marża 2,00 %, opłata 3,00 zł.
- Konto oszczędnościowe: stawka **w skali roku**, odsetki dzienne `saldo × stawka / 100 / 365`, dopisywane w dniu kapitalizacji (`daily` / ostatni dzień miesiąca / ostatni dzień kwartału) po zaokrągleniu do grosza, minus 19 % podatku (zaokrąglony do grosza; na IKE/IKZE bez podatku). Wpisane saldo to saldo **na koniec dnia**; różnica względem wyliczonego = wpłata / wypłata.
- Dzień wyceny = data kalendarzowa `Europe/Warsaw` (`local_today`).

## Doprecyzowania względem dokumentu decyzji

- **Zweryfikowane w źródłach MF** (obligacjeskarbowe.pl, oferta EDO0936): inflacja okresu = wskaźnik ogłoszony w miesiącu przed pierwszym miesiącem okresu, czyli CPI za miesiąc M−2; podatek i opłata liczone od jednej obligacji. Przykłady MF (101,75 zł przy wcześniejszym wykupie; 138,11 zł netto przy 47,05 zł odsetek) są testami w Task 2.
- **Wykup w wycenie dziennej**: w dniu wypłaty wiersz ma wartość wypłaty, a wypłata opuszcza konto następnego dnia (przepływ na początku dnia, jak w TWR z planu 4b) — portfel z samych obligacji nie pokazuje wtedy dnia −100 %.
- **Nowa inflacja z GUS**: zamiast osobnego sygnału z workera `mark_new_days` codziennie oznacza każdego od pierwszego wiersza z flagą `rate_estimated` — gdy CPI dojdzie, szacunek zostaje zastąpiony w najbliższym ticku.
- **Kapitalizacja konta** ustawiana osobnym `PUT /api/savings-accounts/{account_id}` (zmiana przelicza całą historię konta); salda i stawki wymagają ustawionej kapitalizacji.
- **Zmiana IKE ↔ zwykłe** na koncie (`PATCH /api/accounts/{id}`) przelicza historię, bo zmienia podatek od odsetek.
- `GET /api/bonds` i `/api/bonds/{id}` przyjmują `date` (jak `/api/positions`), żeby wycena na wybrany dzień była testowalna.

## Review Focus

- Zmiana konta z „regular” na IKE (albo odwrotnie) po wpisaniu obligacji / konta oszczędnościowego → wycena przeliczona od początku bez podatku (albo z podatkiem), a nie tylko od dziś. *(Task 5)*
- Brak inflacji GUS dla nowego okresu → pozycja wyceniona stawką poprzedniego okresu z flagą `rate_estimated`; gdy worker pobierze inflację, historia od początku tego okresu przelicza się sama w najbliższym ticku. *(Task 2, Task 5)*
- Wykup obligacji (w terminie lub wcześniej) → w dniu wykupu pozycja jest warta wypłatę, następnego dnia znika jako wypłata z konta; TWR nie spada do −100 % dla portfela z samych obligacji. *(Task 4)*
- Użytkownik z samymi obligacjami / kontem oszczędnościowym (bez transakcji XTB) → dostaje codzienne wiersze wyceny i pulpit z typami „Obligacje” / „Konta oszczędnościowe”, nie „Gotówka”. *(Task 4, Task 5)*
- Zakup obligacji serii spoza tabeli bez podanej stawki → 422 z polską prośbą o stawkę 1. roku i marżę; z podaną stawką → seria dopisana i widoczna dla wszystkich. *(Task 6)*

---

## Mapa plików

```
README.md                                         + wiersze API obligacji i kont oszczędnościowych
docs/superpowers/plans/2026-09-26-00-roadmap.md   wiersz 5 → zrobiony
api/
  alembic/versions/0006_bonds_savings.py          bond_series (+seed EDO0936), bond_holdings, savings_*, kolumny daily_valuations
  app/models/fixed_income.py                      BondSeries, BondHolding, SavingsAccount, SavingsRate, SavingsBalance (NOWY)
  app/models/valuation.py                         DailyValuation: + bond_holding_id, savings_account_id, nowy klucz unikalny
  app/models/__init__.py                          eksporty
  app/bonds/__init__.py, app/bonds/edo.py         silnik EDO (NOWY, czysty)
  app/savings/__init__.py, app/savings/interest.py  saldo konta dzień po dniu (NOWY, czysty)
  app/valuation/engine.py                         Row: + bond_holding_id, savings_account_id
  app/valuation/fixed_income.py                   Holding, SavingsInput, bond_rows, savings_rows, bond_position (NOWY, czysty)
  app/valuation/service.py                        load_fixed_income, recompute_user, users_with_holdings, mark_new_days
  app/scoping.py                                  + bond_holdings(), savings_accounts()
  app/accounts/router.py                          zmiana wrapper → przeliczenie
  app/portfolio/service.py                        typy „Obligacje” / „Konta oszczędnościowe” na pulpicie; pozycje obligacji i kont
  app/portfolio/schemas.py                        PositionOut: kind bond / savings, bond_holding_id, savings_account_id
  app/bonds/schemas.py, app/bonds/router.py       /api/bond-series, /api/bonds (NOWE)
  app/savings/schemas.py, app/savings/router.py   /api/savings-accounts/{account_id}… (NOWE)
  app/main.py                                     + routery
  tests/test_fixed_income_models.py               (NOWY)
  tests/test_bonds_edo.py                         (NOWY)
  tests/test_savings_interest.py                  (NOWY)
  tests/test_fixed_income_rows.py                 (NOWY)
  tests/test_fixed_income_valuation.py            (NOWY)
  tests/test_bonds_api.py                         (NOWY)
  tests/test_savings_api.py                       (NOWY)
  tests/test_positions_api.py                     + pozycje obligacji i kont
```

---

### Task 1: Model — serie, zakupy obligacji, konta oszczędnościowe (migracja 0006)

**Files:**
- Create: `api/app/models/fixed_income.py`, `api/alembic/versions/0006_bonds_savings.py`, `api/tests/test_fixed_income_models.py`
- Modify: `api/app/models/valuation.py`, `api/app/models/__init__.py`
- Test: `api/tests/test_fixed_income_models.py` + istniejący `test_models_match_migrations` (`api/tests/test_models.py`)

**Interfaces:**
- Consumes: `Base`, `MONEY` (`app.models.ledger`), tabele `accounts`, `daily_valuations`.
- Produces:
  - `BondSeries` (`bond_series`): `series: str` (PK), `bond_type: str` ∈ `BOND_TYPES`, `issue_month: date`, `maturity_months: int`, `first_period_rate: Decimal`, `margin: Decimal`, `early_redemption_fee: Decimal`, `interest_mode: str` ∈ `INTEREST_MODES`, `rate_basis: str` ∈ `RATE_BASES`. Seed `EDO0936`.
  - `BondHolding` (`bond_holdings`): `id`, `account_id` (FK, CASCADE, indeks), `bond_type`, `series` (FK → `bond_series.series`), `quantity: int` (> 0), `purchase_date: date`, `redeemed_at: date | None` (≥ `purchase_date`), `note: str` (domyślnie `''`).
  - `SavingsAccount` (`savings_accounts`): `id`, `account_id` (FK, CASCADE, unikalne), `capitalization` ∈ `CAPITALIZATIONS = ("daily", "monthly", "quarterly")`.
  - `SavingsRate` (`savings_rates`): `id`, `savings_account_id` (FK, CASCADE), `valid_from: date`, `annual_rate: Decimal` (≥ 0); unikalne (`savings_account_id`, `valid_from`).
  - `SavingsBalance` (`savings_balances`): `id`, `savings_account_id` (FK, CASCADE), `as_of_date: date`, `balance: Decimal` (≥ 0); unikalne (`savings_account_id`, `as_of_date`).
  - `DailyValuation.bond_holding_id: int | None` (FK → bond_holdings, CASCADE), `DailyValuation.savings_account_id: int | None` (FK → savings_accounts, CASCADE); unikalny indeks `uq_daily_valuations_component_date` (`account_id`, `instrument_id`, `bond_holding_id`, `savings_account_id`, `date`) `NULLS NOT DISTINCT` zamiast `uq_daily_valuations_account_id_instrument_id_date`; CHECK `one_component`: `num_nonnulls(instrument_id, bond_holding_id, savings_account_id) <= 1`.

- [ ] **Step 1: Napisz testy**

`api/tests/test_fixed_income_models.py`:

```python
import datetime as dt
from decimal import Decimal

import pytest
from alembic import command
from alembic.config import Config
from sqlalchemy import Engine
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models import (
    Account, BondHolding, BondSeries, DailyValuation, Instrument, SavingsAccount, SavingsBalance, SavingsRate, User,
)
from tests.conftest import API_DIR, TEST_DATABASE_URL

DAY = dt.date(2026, 9, 25)


def _series(**fields: object) -> BondSeries:
    values = {"series": "EDO0936", "bond_type": "EDO", "issue_month": dt.date(2026, 9, 1), "maturity_months": 120,
              "first_period_rate": Decimal("5.35"), "margin": Decimal("2.00"), "early_redemption_fee": Decimal("3.00"),
              "interest_mode": "capitalized", "rate_basis": "cpi", **fields}
    return BondSeries(**values)


def _account(session: Session, kind: str = "bonds") -> Account:
    user = User(email=f"{kind}@portfolio.dev", password_hash="x")
    session.add(user)
    session.flush()
    account = Account(user_id=user.id, name=kind, kind=kind, wrapper="regular", currency="PLN")
    session.add(account)
    session.flush()
    return account


def _holding(account: Account, **fields: object) -> BondHolding:
    values = {"account_id": account.id, "bond_type": "EDO", "series": "EDO0936", "quantity": 10,
              "purchase_date": dt.date(2026, 9, 15), **fields}
    return BondHolding(**values)


def test_holding_references_its_series_and_defaults(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_series())
        session.flush()
        holding = _holding(account)
        session.add(holding)
        session.commit()
        session.refresh(holding)
        assert (holding.note, holding.redeemed_at) == ("", None)


@pytest.mark.parametrize(
    "fields",
    [
        {"quantity": 0},
        {"redeemed_at": dt.date(2026, 9, 14)},  # before the purchase
        {"series": "EDO1036"},  # not in bond_series
        {"bond_type": "XYZ"},
    ],
)
def test_holding_is_constrained(engine: Engine, clean_db: None, fields: dict) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_series())
        session.flush()
        session.add(_holding(account, **fields))
        with pytest.raises(IntegrityError):
            session.flush()


@pytest.mark.parametrize("fields", [{"interest_mode": "weekly"}, {"rate_basis": "wibor"}, {"bond_type": "ABC"}])
def test_series_is_constrained(engine: Engine, clean_db: None, fields: dict) -> None:
    with Session(engine) as session:
        session.add(_series(**fields))
        with pytest.raises(IntegrityError):
            session.flush()


def test_savings_rates_and_balances_are_unique_per_day(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        savings = SavingsAccount(account_id=_account(session, "savings").id, capitalization="monthly")
        session.add(savings)
        session.flush()
        session.add(SavingsRate(savings_account_id=savings.id, valid_from=DAY, annual_rate=Decimal("5.00")))
        session.add(SavingsBalance(savings_account_id=savings.id, as_of_date=DAY, balance=Decimal("100")))
        session.flush()
        session.add(SavingsBalance(savings_account_id=savings.id, as_of_date=DAY, balance=Decimal("200")))
        with pytest.raises(IntegrityError):
            session.flush()


@pytest.mark.parametrize(
    ("model", "fields"),
    [
        (SavingsAccount, {"capitalization": "yearly"}),
        (SavingsRate, {"valid_from": DAY, "annual_rate": Decimal("-1")}),
        (SavingsBalance, {"as_of_date": DAY, "balance": Decimal("-1")}),
    ],
)
def test_savings_values_are_constrained(engine: Engine, clean_db: None, model: type, fields: dict) -> None:
    with Session(engine) as session:
        account = _account(session, "savings")
        if model is SavingsAccount:
            session.add(SavingsAccount(account_id=account.id, **fields))
        else:
            savings = SavingsAccount(account_id=account.id, capitalization="monthly")
            session.add(savings)
            session.flush()
            session.add(model(savings_account_id=savings.id, **fields))
        with pytest.raises(IntegrityError):
            session.flush()


def _row(account: Account, **component: object) -> DailyValuation:
    return DailyValuation(user_id=account.user_id, account_id=account.id, date=DAY, quantity=Decimal("1"),
                          value_pln=Decimal("100"), cost_pln=Decimal("100"), net_flow_pln=Decimal("0"), **component)


def test_valuation_rows_are_unique_per_component_and_have_one_component(engine: Engine, clean_db: None) -> None:
    with Session(engine) as session:
        account = _account(session)
        session.add(_series())
        session.flush()
        first, second = _holding(account), _holding(account, quantity=5)
        session.add_all([first, second])
        session.flush()
        session.add_all([_row(account), _row(account, bond_holding_id=first.id), _row(account, bond_holding_id=second.id)])
        session.flush()  # the cash row and two holdings of one account on one day
        session.add(_row(account, bond_holding_id=first.id))
        with pytest.raises(IntegrityError):
            session.flush()
    with Session(engine) as session:
        account = _account(session)
        session.add(_series())
        instrument = Instrument(xtb_ticker="SXR8.DE", name="SXR8")
        session.add(instrument)
        session.flush()
        holding = _holding(account)
        session.add(holding)
        session.flush()
        session.add(_row(account, instrument_id=instrument.id, bond_holding_id=holding.id))
        with pytest.raises(IntegrityError):
            session.flush()


def test_migration_seeds_edo0936(engine: Engine, clean_db: None) -> None:
    config = Config(str(API_DIR / "alembic.ini"))
    config.set_main_option("sqlalchemy.url", TEST_DATABASE_URL)
    command.downgrade(config, "0005")  # also exercises the downgrade of 0006
    command.upgrade(config, "head")
    with Session(engine) as session:
        series = session.get(BondSeries, "EDO0936")
        assert series is not None
        assert (series.first_period_rate, series.margin, series.early_redemption_fee, series.issue_month) == (
            Decimal("5.3500"), Decimal("2.0000"), Decimal("3.00"), dt.date(2026, 9, 1))
```

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_fixed_income_models.py -q`
Expected: FAIL — `ImportError: cannot import name 'BondHolding'`.

- [ ] **Step 3: Modele**

`api/app/models/fixed_income.py`:

```python
"""Treasury bonds and savings accounts. Series are shared (like prices); holdings, rates and balances belong to
the owner of their account."""
import datetime as dt
from decimal import Decimal

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.ledger import MONEY

BOND_TYPES = ("OTS", "ROR", "DOR", "DOS", "TOS", "COI", "EDO", "ROS", "ROD")
INTEREST_MODES = ("capitalized", "paid_annually", "paid_monthly", "fixed_at_maturity")
RATE_BASES = ("fixed", "cpi", "nbp_ref")
CAPITALIZATIONS = ("daily", "monthly", "quarterly")
PERCENT = Numeric(7, 4)


def _in_list(column: str, values: tuple[str, ...]) -> str:
    return f"{column} IN ({', '.join(repr(v) for v in values)})"


class BondSeries(Base):
    """One monthly issue of a treasury bond, e.g. EDO0936: 5.35 % in the first year, then CPI + 2.00 %."""

    __tablename__ = "bond_series"
    __table_args__ = (
        CheckConstraint(_in_list("bond_type", BOND_TYPES), name="bond_type"),
        CheckConstraint(_in_list("interest_mode", INTEREST_MODES), name="interest_mode"),
        CheckConstraint(_in_list("rate_basis", RATE_BASES), name="rate_basis"),
    )

    series: Mapped[str] = mapped_column(String(10), primary_key=True)
    bond_type: Mapped[str] = mapped_column(String(3))
    issue_month: Mapped[dt.date] = mapped_column(Date)  # first day of the month the series was sold in
    maturity_months: Mapped[int] = mapped_column(Integer)
    first_period_rate: Mapped[Decimal] = mapped_column(PERCENT)  # percent a year
    margin: Mapped[Decimal] = mapped_column(PERCENT)  # percentage points over the rate basis
    early_redemption_fee: Mapped[Decimal] = mapped_column(Numeric(6, 2))  # zł per bond of 100 zł
    interest_mode: Mapped[str] = mapped_column(String(20))
    rate_basis: Mapped[str] = mapped_column(String(10))


class BondHolding(Base):
    """One purchase of bonds: interest periods run from the purchase day. `redeemed_at`: early redemption of all
    of them."""

    __tablename__ = "bond_holdings"
    __table_args__ = (
        CheckConstraint(_in_list("bond_type", BOND_TYPES), name="bond_type"),
        CheckConstraint("quantity > 0", name="quantity_positive"),
        CheckConstraint("redeemed_at IS NULL OR redeemed_at >= purchase_date", name="redeemed_after_purchase"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), index=True)
    bond_type: Mapped[str] = mapped_column(String(3))
    series: Mapped[str] = mapped_column(ForeignKey("bond_series.series"))
    quantity: Mapped[int] = mapped_column(Integer)  # bonds of 100 zł
    purchase_date: Mapped[dt.date] = mapped_column(Date)
    redeemed_at: Mapped[dt.date | None] = mapped_column(Date)
    note: Mapped[str] = mapped_column(Text, server_default="")


class SavingsAccount(Base):
    __tablename__ = "savings_accounts"
    __table_args__ = (CheckConstraint(_in_list("capitalization", CAPITALIZATIONS), name="capitalization"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    account_id: Mapped[int] = mapped_column(ForeignKey("accounts.id", ondelete="CASCADE"), unique=True)
    capitalization: Mapped[str] = mapped_column(String(10))


class SavingsRate(Base):
    """Annual interest rate in percent, valid from `valid_from` until the next row."""

    __tablename__ = "savings_rates"
    __table_args__ = (
        UniqueConstraint("savings_account_id", "valid_from"),
        CheckConstraint("annual_rate >= 0", name="rate_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    savings_account_id: Mapped[int] = mapped_column(ForeignKey("savings_accounts.id", ondelete="CASCADE"))
    valid_from: Mapped[dt.date] = mapped_column(Date)
    annual_rate: Mapped[Decimal] = mapped_column(PERCENT)


class SavingsBalance(Base):
    """The balance at the end of `as_of_date`, copied from the bank."""

    __tablename__ = "savings_balances"
    __table_args__ = (
        UniqueConstraint("savings_account_id", "as_of_date"),
        CheckConstraint("balance >= 0", name="balance_not_negative"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    savings_account_id: Mapped[int] = mapped_column(ForeignKey("savings_accounts.id", ondelete="CASCADE"))
    as_of_date: Mapped[dt.date] = mapped_column(Date)
    balance: Mapped[Decimal] = mapped_column(MONEY)
```

`api/app/models/valuation.py` — w `DailyValuation` zastąp indeks unikalny i dodaj CHECK oraz kolumny (reszta klasy bez zmian; zaktualizuj docstring o obligacje i konta):

```python
    __table_args__ = (
        Index(
            "uq_daily_valuations_component_date",
            "account_id", "instrument_id", "bond_holding_id", "savings_account_id", "date",
            unique=True, postgresql_nulls_not_distinct=True,
        ),
        Index("ix_daily_valuations_user_id_date", "user_id", "date"),
        CheckConstraint("num_nonnulls(instrument_id, bond_holding_id, savings_account_id) <= 1", name="one_component"),
    )
    ...
    bond_holding_id: Mapped[int | None] = mapped_column(ForeignKey("bond_holdings.id", ondelete="CASCADE"))
    savings_account_id: Mapped[int | None] = mapped_column(ForeignKey("savings_accounts.id", ondelete="CASCADE"))
```

Docstring `DailyValuation`: „`instrument_id`, `bond_holding_id`, `savings_account_id` — co najwyżej jeden ustawiony; żaden = gotówka konta”.

`api/app/models/__init__.py`: import `BOND_TYPES`, `CAPITALIZATIONS`, `BondHolding`, `BondSeries`, `SavingsAccount`, `SavingsBalance`, `SavingsRate` z `app.models.fixed_income` i dopisz je do `__all__` (alfabetycznie w grupach).

- [ ] **Step 4: Migracja**

`api/alembic/versions/0006_bonds_savings.py`:

```python
"""bonds and savings: bond series (seed EDO0936), holdings, savings accounts, daily valuation components

Revision ID: 0006
Revises: 0005
Create Date: 2026-09-28

"""
import datetime as dt
from collections.abc import Sequence
from decimal import Decimal

import sqlalchemy as sa
from alembic import op

revision: str = "0006"
down_revision: str | None = "0005"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

MONEY = sa.Numeric(20, 4)
PERCENT = sa.Numeric(7, 4)
OLD_UNIQUE = "uq_daily_valuations_account_id_instrument_id_date"
NEW_UNIQUE = "uq_daily_valuations_component_date"
BOND_TYPES = "bond_type IN ('OTS', 'ROR', 'DOR', 'DOS', 'TOS', 'COI', 'EDO', 'ROS', 'ROD')"
# obligacjeskarbowe.pl, oferta wrzesień 2026 (list emisyjny EDO0936): 5,35 % w 1. roku, potem inflacja + 2,00 %.
SERIES = [{"series": "EDO0936", "bond_type": "EDO", "issue_month": dt.date(2026, 9, 1), "maturity_months": 120,
           "first_period_rate": Decimal("5.35"), "margin": Decimal("2.00"), "early_redemption_fee": Decimal("3.00"),
           "interest_mode": "capitalized", "rate_basis": "cpi"}]


def upgrade() -> None:
    series = op.create_table(
        "bond_series",
        sa.Column("series", sa.String(length=10), nullable=False),
        sa.Column("bond_type", sa.String(length=3), nullable=False),
        sa.Column("issue_month", sa.Date(), nullable=False),
        sa.Column("maturity_months", sa.Integer(), nullable=False),
        sa.Column("first_period_rate", PERCENT, nullable=False),
        sa.Column("margin", PERCENT, nullable=False),
        sa.Column("early_redemption_fee", sa.Numeric(6, 2), nullable=False),
        sa.Column("interest_mode", sa.String(length=20), nullable=False),
        sa.Column("rate_basis", sa.String(length=10), nullable=False),
        sa.CheckConstraint(BOND_TYPES, name=op.f("ck_bond_series_bond_type")),
        sa.CheckConstraint(
            "interest_mode IN ('capitalized', 'paid_annually', 'paid_monthly', 'fixed_at_maturity')",
            name=op.f("ck_bond_series_interest_mode"),
        ),
        sa.CheckConstraint("rate_basis IN ('fixed', 'cpi', 'nbp_ref')", name=op.f("ck_bond_series_rate_basis")),
        sa.PrimaryKeyConstraint("series", name=op.f("pk_bond_series")),
    )
    op.bulk_insert(series, SERIES)
    op.create_table(
        "bond_holdings",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("bond_type", sa.String(length=3), nullable=False),
        sa.Column("series", sa.String(length=10), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("purchase_date", sa.Date(), nullable=False),
        sa.Column("redeemed_at", sa.Date(), nullable=True),
        sa.Column("note", sa.Text(), server_default="", nullable=False),
        sa.CheckConstraint(BOND_TYPES, name=op.f("ck_bond_holdings_bond_type")),
        sa.CheckConstraint("quantity > 0", name=op.f("ck_bond_holdings_quantity_positive")),
        sa.CheckConstraint(
            "redeemed_at IS NULL OR redeemed_at >= purchase_date", name=op.f("ck_bond_holdings_redeemed_after_purchase")
        ),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_bond_holdings_account_id_accounts"),
                                ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["series"], ["bond_series.series"], name=op.f("fk_bond_holdings_series_bond_series")),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_bond_holdings")),
    )
    op.create_index(op.f("ix_bond_holdings_account_id"), "bond_holdings", ["account_id"])
    op.create_table(
        "savings_accounts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("account_id", sa.Integer(), nullable=False),
        sa.Column("capitalization", sa.String(length=10), nullable=False),
        sa.CheckConstraint("capitalization IN ('daily', 'monthly', 'quarterly')",
                           name=op.f("ck_savings_accounts_capitalization")),
        sa.ForeignKeyConstraint(["account_id"], ["accounts.id"], name=op.f("fk_savings_accounts_account_id_accounts"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_savings_accounts")),
        sa.UniqueConstraint("account_id", name=op.f("uq_savings_accounts_account_id")),
    )
    op.create_table(
        "savings_rates",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("savings_account_id", sa.Integer(), nullable=False),
        sa.Column("valid_from", sa.Date(), nullable=False),
        sa.Column("annual_rate", PERCENT, nullable=False),
        sa.CheckConstraint("annual_rate >= 0", name=op.f("ck_savings_rates_rate_not_negative")),
        sa.ForeignKeyConstraint(["savings_account_id"], ["savings_accounts.id"],
                                name=op.f("fk_savings_rates_savings_account_id_savings_accounts"), ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_savings_rates")),
        sa.UniqueConstraint("savings_account_id", "valid_from",
                            name=op.f("uq_savings_rates_savings_account_id_valid_from")),
    )
    op.create_table(
        "savings_balances",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("savings_account_id", sa.Integer(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("balance", MONEY, nullable=False),
        sa.CheckConstraint("balance >= 0", name=op.f("ck_savings_balances_balance_not_negative")),
        sa.ForeignKeyConstraint(["savings_account_id"], ["savings_accounts.id"],
                                name=op.f("fk_savings_balances_savings_account_id_savings_accounts"),
                                ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name=op.f("pk_savings_balances")),
        sa.UniqueConstraint("savings_account_id", "as_of_date",
                            name=op.f("uq_savings_balances_savings_account_id_as_of_date")),
    )
    op.add_column("daily_valuations", sa.Column("bond_holding_id", sa.Integer(), nullable=True))
    op.add_column("daily_valuations", sa.Column("savings_account_id", sa.Integer(), nullable=True))
    op.create_foreign_key(op.f("fk_daily_valuations_bond_holding_id_bond_holdings"), "daily_valuations",
                          "bond_holdings", ["bond_holding_id"], ["id"], ondelete="CASCADE")
    op.create_foreign_key(op.f("fk_daily_valuations_savings_account_id_savings_accounts"), "daily_valuations",
                          "savings_accounts", ["savings_account_id"], ["id"], ondelete="CASCADE")
    op.drop_index(OLD_UNIQUE, table_name="daily_valuations")
    op.create_index(NEW_UNIQUE, "daily_valuations",
                    ["account_id", "instrument_id", "bond_holding_id", "savings_account_id", "date"],
                    unique=True, postgresql_nulls_not_distinct=True)
    op.create_check_constraint(op.f("ck_daily_valuations_one_component"), "daily_valuations",
                               "num_nonnulls(instrument_id, bond_holding_id, savings_account_id) <= 1")


def downgrade() -> None:
    op.execute("DELETE FROM daily_valuations WHERE bond_holding_id IS NOT NULL OR savings_account_id IS NOT NULL")
    op.drop_constraint(op.f("ck_daily_valuations_one_component"), "daily_valuations", type_="check")
    op.drop_index(NEW_UNIQUE, table_name="daily_valuations")
    op.create_index(OLD_UNIQUE, "daily_valuations", ["account_id", "instrument_id", "date"],
                    unique=True, postgresql_nulls_not_distinct=True)
    op.drop_constraint(op.f("fk_daily_valuations_savings_account_id_savings_accounts"), "daily_valuations",
                       type_="foreignkey")
    op.drop_constraint(op.f("fk_daily_valuations_bond_holding_id_bond_holdings"), "daily_valuations",
                       type_="foreignkey")
    op.drop_column("daily_valuations", "savings_account_id")
    op.drop_column("daily_valuations", "bond_holding_id")
    op.drop_table("savings_balances")
    op.drop_table("savings_rates")
    op.drop_table("savings_accounts")
    op.drop_index(op.f("ix_bond_holdings_account_id"), table_name="bond_holdings")
    op.drop_table("bond_holdings")
    op.drop_table("bond_series")
```

Nazwy ograniczeń w migracji muszą się zgadzać z konwencją nazw modeli (`Base.metadata.naming_convention`) — `test_models_match_migrations` to sprawdza; jeśli któraś nazwa (np. unikalna z dwoma kolumnami) wychodzi inaczej, popraw migrację, nie model.

- [ ] **Step 5: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_fixed_income_models.py tests/test_models.py tests/test_valuation_models.py -q`
Expected: PASS.

Run: `docker compose run --rm api pytest -q`
Expected: PASS, jedno istniejące ostrzeżenie (StarletteDeprecationWarning).

- [ ] **Step 6: Commit**

```bash
git add api/alembic/versions/0006_bonds_savings.py api/app/models/fixed_income.py api/app/models/valuation.py \
  api/app/models/__init__.py api/tests/test_fixed_income_models.py
git commit -m "feat(bonds): bond series, holdings and savings accounts tables; valuation rows per component

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 2: Silnik EDO (czyste funkcje)

**Files:**
- Create: `api/app/bonds/__init__.py` (pusty), `api/app/bonds/edo.py`, `api/tests/test_bonds_edo.py`

**Interfaces:**
- Consumes: nic z bazy (czyste funkcje).
- Produces (`app.bonds.edo`): `NOMINAL = Decimal(100)`, `YEARS = 10`; `Series(first_period_rate, margin, early_redemption_fee)` (Decimal, stawki w %); `Period(number, start, end, rate, estimated)` (`end` = następna rocznica, wyłącznie); `series_name(purchase_date) -> str`; `anniversary(purchase_date, years) -> date`; `cpi_month(period_start) -> date`; `periods(purchase_date, series, cpi: Mapping[date, Decimal]) -> list[Period]`; `period_on(periods, day) -> Period`; `value(periods, day) -> Decimal` (1 szt., brutto, grosze); `tax(interest) -> Decimal`; `net_value(gross, taxed) -> Decimal`; `redemption_value(gross, fee, taxed) -> Decimal`.

- [ ] **Step 1: Testy**

`api/tests/test_bonds_edo.py`:

```python
"""EDO rules: issue letter EDO0936 (annex 3) and the MF offer page examples."""
import datetime as dt
from decimal import Decimal as D

from app.bonds.edo import (
    Series, anniversary, cpi_month, net_value, period_on, periods, redemption_value, series_name, value,
)

EDO0936 = Series(D("5.35"), D("2.00"), D("3.00"))
BOUGHT = dt.date(2026, 9, 15)
CPI = {dt.date(2027, 7, 1): D("3.0")}  # July 2027 → the 2nd period (from 2027-09-15) earns 3.0 + 2.00 = 5.00 %


def test_series_is_named_after_the_maturity_month() -> None:
    assert (series_name(BOUGHT), series_name(dt.date(2026, 10, 1))) == ("EDO0936", "EDO1036")


def test_anniversary_of_29_february_falls_on_28_february() -> None:
    assert anniversary(dt.date(2024, 2, 29), 1) == dt.date(2025, 2, 28)
    assert anniversary(dt.date(2024, 2, 29), 4) == dt.date(2028, 2, 29)


def test_a_period_uses_the_cpi_of_two_months_before_its_first_month() -> None:
    assert (cpi_month(dt.date(2027, 9, 15)), cpi_month(dt.date(2027, 1, 15))) == (
        dt.date(2027, 7, 1), dt.date(2026, 11, 1))


def test_periods_first_rate_then_cpi_plus_margin_then_estimated_while_cpi_is_unknown() -> None:
    schedule = periods(BOUGHT, EDO0936, CPI)

    assert len(schedule) == 10
    assert [(p.number, p.start, p.end, p.rate, p.estimated) for p in schedule[:3]] == [
        (1, BOUGHT, dt.date(2027, 9, 15), D("5.35"), False),
        (2, dt.date(2027, 9, 15), dt.date(2028, 9, 15), D("5.00"), False),
        (3, dt.date(2028, 9, 15), dt.date(2029, 9, 15), D("5.00"), True),  # CPI for July 2028 not known yet
    ]
    assert schedule[-1].end == dt.date(2036, 9, 15)


def test_negative_inflation_counts_as_zero() -> None:
    schedule = periods(BOUGHT, EDO0936, {dt.date(2027, 7, 1): D("-1.2")})
    assert schedule[1].rate == D("2.00")


def test_value_accrues_within_a_period_and_compounds_after_the_anniversary() -> None:
    schedule = periods(BOUGHT, EDO0936, CPI)

    assert value(schedule, BOUGHT) == D("100.00")
    # 100 × (1 + 5.35 % × 181 / 365)
    assert value(schedule, dt.date(2027, 3, 15)) == D("102.65")
    assert value(schedule, dt.date(2027, 9, 15)) == D("105.35")
    # 105.35 × (1 + 5.00 % × 182 / 366) — the 2nd period contains 29 February 2028
    assert value(schedule, dt.date(2028, 3, 15)) == D("107.97")
    assert period_on(schedule, dt.date(2028, 3, 15)).number == 2


def test_value_at_maturity_compounds_all_ten_periods() -> None:
    schedule = periods(BOUGHT, EDO0936, CPI)  # periods 3–10 estimated at 5.00 %
    # 100 × 1.0535 × 1.05⁹
    assert value(schedule, dt.date(2036, 9, 15)) == D("163.43")
    assert value(schedule, dt.date(2040, 1, 1)) == D("163.43")


def test_net_value_after_tax_matches_the_mf_example() -> None:
    # MF: 47.05 zł of interest before tax → 38.11 zł after it
    assert net_value(D("147.05"), taxed=True) == D("138.11")
    assert net_value(D("147.05"), taxed=False) == D("147.05")


def test_early_redemption_matches_the_mf_example() -> None:
    # MF: 4.16 zł of interest, 2.00 zł fee, tax 0.41 zł on 2.16 zł → 101.75 zł
    assert redemption_value(D("104.16"), D("2.00"), taxed=True) == D("101.75")


def test_early_redemption_fee_never_exceeds_the_interest() -> None:
    assert redemption_value(D("102.65"), D("3.00"), taxed=True) == D("100.00")
    assert redemption_value(D("107.97"), D("3.00"), taxed=True) == D("104.03")  # 107.97 − 3 − 19 % × 4.97
    assert redemption_value(D("107.97"), D("3.00"), taxed=False) == D("104.97")
```

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_bonds_edo.py -q`
Expected: FAIL — `No module named 'app.bonds'`.

- [ ] **Step 3: Implementacja**

`api/app/bonds/edo.py`:

```python
"""EDO treasury bonds (10 years, inflation-linked, interest capitalized yearly): pure functions on one bond of
100 zł. Rules from the issue letter (EDO0936, annex 3) and the MF offer page; tax and the early redemption fee
are computed per bond."""
import calendar
import datetime as dt
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

NOMINAL = Decimal(100)
YEARS = 10
TAX_RATE = Decimal("0.19")
ZERO = Decimal(0)
ONE = Decimal(1)
HUNDRED = Decimal(100)
CENT = Decimal("0.01")


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class Series:
    first_period_rate: Decimal  # percent a year
    margin: Decimal  # percentage points over CPI from the 2nd period
    early_redemption_fee: Decimal  # zł per bond


@dataclass(frozen=True)
class Period:
    number: int  # 1..10
    start: dt.date
    end: dt.date  # the next anniversary (exclusive)
    rate: Decimal  # percent a year
    estimated: bool  # the CPI it needs is not known yet: the previous period's rate stands in


def series_name(purchase_date: dt.date) -> str:
    """EDO + month and two-digit year of maturity: bought on 2026-09-15 → EDO0936."""
    return f"EDO{purchase_date.month:02d}{(purchase_date.year + YEARS) % 100:02d}"


def anniversary(purchase_date: dt.date, years: int) -> dt.date:
    """The purchase day `years` later; 29 February falls on 28 February in a common year."""
    year = purchase_date.year + years
    return dt.date(year, purchase_date.month, min(purchase_date.day, calendar.monthrange(year, purchase_date.month)[1]))


def cpi_month(period_start: dt.date) -> dt.date:
    """The CPI a period earns: announced by GUS in the month before the period's first month, i.e. the index for
    two months before it (a period from September uses July's year-on-year CPI)."""
    month = period_start.month - 2
    year = period_start.year + (month - 1) // 12
    return dt.date(year, (month - 1) % 12 + 1, 1)


def periods(purchase_date: dt.date, series: Series, cpi: Mapping[dt.date, Decimal]) -> list[Period]:
    """The ten interest periods: the series' first-year rate, then CPI (negative counts as 0) + margin."""
    result: list[Period] = []
    for number in range(1, YEARS + 1):
        start, end = anniversary(purchase_date, number - 1), anniversary(purchase_date, number)
        if number == 1:
            rate, estimated = series.first_period_rate, False
        elif (inflation := cpi.get(cpi_month(start))) is None:
            rate, estimated = result[-1].rate, True
        else:
            rate, estimated = max(inflation, ZERO) + series.margin, False
        result.append(Period(number, start, end, rate, estimated))
    return result


def period_on(schedule: Sequence[Period], day: dt.date) -> Period:
    """The period containing `day`; the last one on and after maturity."""
    return next((period for period in schedule if day < period.end), schedule[-1])


def value(schedule: Sequence[Period], day: dt.date) -> Decimal:
    """One bond on `day` before tax: 100 × Π(1 + r_i) over finished periods × (1 + r_k × a_k / ACT_k), rounded to
    the grosz; on and after maturity the value at maturity."""
    factor = ONE
    for period in schedule:
        rate = period.rate / HUNDRED
        if day < period.end:
            elapsed, length = (day - period.start).days, (period.end - period.start).days
            return _money(NOMINAL * factor * (ONE + rate * elapsed / length))
        factor *= ONE + rate
    return _money(NOMINAL * factor)


def tax(interest: Decimal) -> Decimal:
    return _money(max(interest, ZERO) * TAX_RATE)


def net_value(gross: Decimal, taxed: bool) -> Decimal:
    """One bond after the 19 % tax on its interest (IKE / IKZE: no tax)."""
    return gross - tax(gross - NOMINAL) if taxed else gross


def redemption_value(gross: Decimal, fee: Decimal, taxed: bool) -> Decimal:
    """Early redemption of one bond: the fee is taken in full or up to the interest accrued (the capital is never
    touched), and the tax is on the interest after the fee."""
    interest = gross - NOMINAL
    charged = min(fee, max(interest, ZERO))
    return gross - charged - (tax(interest - charged) if taxed else ZERO)
```

- [ ] **Step 4: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_bonds_edo.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/bonds/__init__.py api/app/bonds/edo.py api/tests/test_bonds_edo.py
git commit -m "feat(bonds): EDO valuation per bond from the issue letter

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---
### Task 3: Konto oszczędnościowe — saldo dzień po dniu (czyste funkcje)

**Files:**
- Create: `api/app/savings/__init__.py` (pusty), `api/app/savings/interest.py`, `api/tests/test_savings_interest.py`

**Interfaces:**
- Consumes: nic z bazy.
- Produces (`app.savings.interest`): `SavingsDay(day, balance, net_flow)` (frozen); `is_capitalization_day(day, capitalization) -> bool`; `savings_days(balances: Sequence[tuple[date, Decimal]], rates: Sequence[tuple[date, Decimal]], capitalization: str, taxed: bool, end: date) -> list[SavingsDay]` — każdy dzień od pierwszego wpisanego salda do `end`.

- [ ] **Step 1: Testy**

`api/tests/test_savings_interest.py`:

```python
import datetime as dt
from decimal import Decimal as D

from app.savings.interest import is_capitalization_day, savings_days

SEP_01, SEP_30, OCT_10, OCT_31 = dt.date(2026, 9, 1), dt.date(2026, 9, 30), dt.date(2026, 10, 10), dt.date(2026, 10, 31)
RATES = [(SEP_01, D("5.00"))]


def _on(days: list, day: dt.date):  # noqa: ANN202
    return next(d for d in days if d.day == day)


def test_capitalization_days() -> None:
    assert is_capitalization_day(dt.date(2026, 9, 12), "daily")
    assert (is_capitalization_day(SEP_30, "monthly"), is_capitalization_day(dt.date(2026, 9, 29), "monthly")) == (
        True, False)
    assert (is_capitalization_day(SEP_30, "quarterly"), is_capitalization_day(OCT_31, "quarterly")) == (True, False)


def test_first_balance_is_a_deposit_and_interest_is_credited_monthly_after_tax() -> None:
    days = savings_days([(SEP_01, D("10000"))], RATES, "monthly", taxed=True, end=OCT_31)

    assert (days[0].day, days[0].balance, days[0].net_flow) == (SEP_01, D("10000"), D("10000"))
    assert _on(days, dt.date(2026, 9, 29)).balance == D("10000")  # nothing credited before month end
    # 29 days (2–30 Sep) × 10 000 × 5 % / 365 = 39.73 gross, 7.55 tax
    assert _on(days, SEP_30).balance == D("10032.18")
    # 31 days × 10 032.18 × 5 % / 365 = 42.60 gross, 8.09 tax
    assert _on(days, OCT_31).balance == D("10066.69")
    assert days[-1].day == OCT_31 and all(d.net_flow == 0 for d in days[1:])


def test_ike_savings_pay_no_tax() -> None:
    days = savings_days([(SEP_01, D("10000"))], RATES, "monthly", taxed=False, end=SEP_30)
    assert days[-1].balance == D("10039.73")


def test_a_copied_balance_that_differs_is_a_deposit_and_interest_follows_it() -> None:
    days = savings_days([(SEP_01, D("10000")), (OCT_10, D("11032.18"))], RATES, "monthly", taxed=True, end=OCT_31)

    assert _on(days, OCT_10).net_flow == D("1000.00")
    # 10 days on 10 032.18 + 21 days on 11 032.18 = 45.48 gross, 8.64 tax
    assert _on(days, OCT_31).balance == D("11069.02")


def test_rate_changes_apply_from_their_day_and_no_rate_earns_nothing() -> None:
    days = savings_days([(SEP_01, D("10000"))], [(dt.date(2026, 9, 16), D("3.65"))], "monthly", taxed=False, end=SEP_30)
    # 15 days (16–30 Sep) × 10 000 × 3.65 % / 365 = 15.00
    assert days[-1].balance == D("10015.00")


def test_no_balances_no_days() -> None:
    assert savings_days([], RATES, "monthly", taxed=True, end=OCT_31) == []
```

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_savings_interest.py -q`
Expected: FAIL — `No module named 'app.savings'`.

- [ ] **Step 3: Implementacja**

`api/app/savings/interest.py`:

```python
"""A savings account between balances copied from the bank (pure functions). Interest accrues daily at the annual
rate of the day (balance × rate / 100 / 365) and is credited on each capitalization day, rounded to the grosz,
minus the 19 % tax (none on IKE / IKZE). A copied balance is the balance at the end of its day; its difference
from the computed balance is the owner's deposit or withdrawal."""
import bisect
import calendar
import datetime as dt
from collections.abc import Sequence
from dataclasses import dataclass
from decimal import ROUND_HALF_UP, Decimal

ZERO = Decimal(0)
HUNDRED = Decimal(100)
DAYS_IN_YEAR = Decimal(365)
TAX_RATE = Decimal("0.19")
CENT = Decimal("0.01")
ONE_DAY = dt.timedelta(days=1)
QUARTER_ENDS = (3, 6, 9, 12)


def _money(value: Decimal) -> Decimal:
    return value.quantize(CENT, rounding=ROUND_HALF_UP)


@dataclass(frozen=True)
class SavingsDay:
    day: dt.date
    balance: Decimal  # at the end of the day
    net_flow: Decimal  # the owner's deposit (+) or withdrawal (−) that day


def is_capitalization_day(day: dt.date, capitalization: str) -> bool:
    if capitalization == "daily":
        return True
    month_end = day.day == calendar.monthrange(day.year, day.month)[1]
    return month_end if capitalization == "monthly" else month_end and day.month in QUARTER_ENDS


def savings_days(
    balances: Sequence[tuple[dt.date, Decimal]], rates: Sequence[tuple[dt.date, Decimal]], capitalization: str,
    taxed: bool, end: dt.date,
) -> list[SavingsDay]:
    """Every day from the first copied balance to `end`."""
    if not balances:
        return []
    copied = dict(balances)
    rate_days = sorted(rates)
    starts = [start for start, _ in rate_days]
    day = min(copied)
    balance = accrued = ZERO
    result: list[SavingsDay] = []
    while day <= end:
        index = bisect.bisect_right(starts, day) - 1
        rate = rate_days[index][1] if index >= 0 else ZERO
        accrued += balance * rate / HUNDRED / DAYS_IN_YEAR
        if is_capitalization_day(day, capitalization):
            gross = _money(accrued)
            balance += gross - (_money(gross * TAX_RATE) if taxed else ZERO)
            accrued = ZERO
        flow = ZERO
        if day in copied:
            flow = copied[day] - balance
            balance = copied[day]
        result.append(SavingsDay(day, balance, flow))
        day += ONE_DAY
    return result
```

(Kolejność w dniu: odsetki od salda z poprzedniego dnia, kapitalizacja, potem porównanie z wpisanym saldem — wpisane saldo to stan na koniec dnia, więc odsetki od wpłaty liczą się od następnego dnia.)

- [ ] **Step 4: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_savings_interest.py -q`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add api/app/savings/__init__.py api/app/savings/interest.py api/tests/test_savings_interest.py
git commit -m "feat(savings): savings account balance day by day with capitalization and tax

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 4: Wiersze dzienne obligacji i kont oszczędnościowych (czyste funkcje)

**Files:**
- Create: `api/app/valuation/fixed_income.py`, `api/tests/test_fixed_income_rows.py`
- Modify: `api/app/valuation/engine.py` (klasa `Row`)

**Interfaces:**
- Consumes: `edo.*` (Task 2), `interest.savings_days` (Task 3); `Row`, `ONE_DAY`, `ZERO`, `money` z `app.valuation.engine`.
- Produces:
  - `Row` + pola na końcu: `bond_holding_id: int | None = None`, `savings_account_id: int | None = None`.
  - `app.valuation.fixed_income`: `FLAG_RATE_ESTIMATED = "rate_estimated"`; `Holding(id, account_id, purchase_date, quantity: int, redeemed_at, series: edo.Series, taxed: bool)`; `SavingsInput(id, account_id, capitalization, taxed, balances, rates)`; `payout_day(holding, schedule) -> date`; `payout_per_bond(holding, schedule) -> Decimal`; `bond_rows(holdings, cpi, start, end) -> list[Row]`; `savings_rows(accounts, start, end) -> list[Row]`.
  - Wiersz obligacji: od dnia zakupu do dnia wypłaty wartość = ilość × wartość netto 1 szt. (`net_flow_pln` = ilość × 100 w dniu zakupu, flaga `rate_estimated` w okresie szacunkowym); **w dniu wypłaty** wartość = wypłata (wcześniejszy wykup: `redemption_value`; w terminie: `net_value`); **dzień po wypłacie** wiersz z wartością 0 i `net_flow_pln` = −wypłata; później brak wierszy.
  - Wiersz konta oszczędnościowego: `quantity` = saldo, `value_pln` = saldo w groszach, `cost_pln` = suma wpłat/wypłat do tego dnia, `net_flow_pln` = wpłata/wypłata dnia.

- [ ] **Step 1: Testy**

`api/tests/test_fixed_income_rows.py`:

```python
import datetime as dt
from decimal import Decimal as D

from app.bonds.edo import Series
from app.valuation.fixed_income import FLAG_RATE_ESTIMATED, Holding, SavingsInput, bond_rows, savings_rows

EDO0936 = Series(D("5.35"), D("2.00"), D("3.00"))
BOUGHT, SAT = dt.date(2026, 9, 15), dt.date(2026, 9, 26)


def _holding(**fields: object) -> Holding:
    values = {"id": 7, "account_id": 3, "purchase_date": BOUGHT, "quantity": 10, "redeemed_at": None,
              "series": EDO0936, "taxed": True, **fields}
    return Holding(**values)


def test_bond_rows_from_the_purchase_day_with_the_purchase_as_a_deposit() -> None:
    rows = bond_rows([_holding()], {}, dt.date.min, SAT)

    assert [row.day for row in rows] == [BOUGHT + dt.timedelta(days=n) for n in range(12)]
    first, last = rows[0], rows[-1]
    assert (first.value_pln, first.cost_pln, first.net_flow_pln, first.bond_holding_id) == (
        D("1000.00"), D("1000"), D("1000"), 7)
    # 11 days: 100 × (1 + 5.35 % × 11 / 365) = 100.16; tax 0.03 → 100.13 × 10
    assert (last.quantity, last.value_pln, last.net_flow_pln, last.instrument_id, last.flags) == (
        D("10"), D("1001.30"), D("0"), None, ())


def test_ike_bonds_are_valued_without_tax() -> None:
    assert bond_rows([_holding(taxed=False)], {}, SAT, SAT)[0].value_pln == D("1001.60")


def test_early_redemption_pays_out_on_its_day_and_leaves_the_next_day() -> None:
    rows = bond_rows([_holding(redeemed_at=dt.date(2026, 9, 20))], {}, dt.date(2026, 9, 19), SAT)

    # 5 days: 100.07 per bond, the fee takes the 0.07 zł of interest → 100.00 × 10
    assert [(row.day, row.value_pln, row.net_flow_pln) for row in rows] == [
        (dt.date(2026, 9, 19), D("1000.50"), D("0")),  # 100.06 − 0.01 tax
        (dt.date(2026, 9, 20), D("1000.00"), D("0")),
        (dt.date(2026, 9, 21), D("0"), D("-1000.00")),
    ]


def test_maturity_pays_the_net_value_of_all_periods() -> None:
    cpi = {dt.date(year, 7, 1): D("3.0") for year in range(2027, 2036)}  # every period after the 1st: 5.00 %
    rows = bond_rows([_holding(quantity=1)], cpi, dt.date(2036, 9, 14), dt.date(2036, 9, 30))

    # 163.43 gross at maturity, tax 19 % × 63.43 = 12.05 → 151.38
    assert [(row.day, row.value_pln, row.net_flow_pln) for row in rows][1:] == [
        (dt.date(2036, 9, 15), D("151.38"), D("0")), (dt.date(2036, 9, 16), D("0"), D("-151.38"))]


def test_rows_in_an_estimated_period_are_flagged() -> None:
    rows = bond_rows([_holding(purchase_date=dt.date(2025, 9, 15))], {}, SAT, SAT)  # 2nd period: no CPI for 07/2026
    assert rows[0].flags == (FLAG_RATE_ESTIMATED,)


def test_savings_rows_carry_balance_capital_and_flows() -> None:
    account = SavingsInput(4, 5, "monthly", True, [(dt.date(2026, 9, 1), D("10000"))],
                           [(dt.date(2026, 9, 1), D("5.00"))])

    rows = savings_rows([account], dt.date(2026, 9, 30), dt.date(2026, 9, 30))

    (row,) = rows
    assert (row.account_id, row.savings_account_id, row.quantity, row.value_pln, row.cost_pln, row.net_flow_pln) == (
        5, 4, D("10032.18"), D("10032.18"), D("10000.00"), D("0.00"))
```

(Liczby: 19 IX = 4 dni → 100 × (1 + 5,35 % × 4 / 365) = 100,0586 → 100,06, podatek 19 % × 0,06 = 0,0114 → 0,01 → 100,05 × 10 = 1 000,50. 20 IX = 5 dni → 100,0733 → 100,07, opłata 0,07, podatek 0 → 100,00.)

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_fixed_income_rows.py -q`
Expected: FAIL — `No module named 'app.valuation.fixed_income'`.

- [ ] **Step 3: `Row`**

W `api/app/valuation/engine.py` rozszerz `Row` (docstring: „`instrument_id`, `bond_holding_id`, `savings_account_id` None = gotówka konta”):

```python
@dataclass(frozen=True)
class Row:
    """One `daily_valuations` row: a holding of an instrument, a bond purchase or a savings account (at most one
    of the three ids), or with none of them the account's cash."""

    account_id: int
    instrument_id: int | None
    day: dt.date
    quantity: Decimal | None
    value_pln: Decimal
    cost_pln: Decimal
    net_flow_pln: Decimal
    flags: tuple[str, ...] = ()
    bond_holding_id: int | None = None
    savings_account_id: int | None = None
```

- [ ] **Step 4: Wiersze**

`api/app/valuation/fixed_income.py`:

```python
"""Daily valuation rows of treasury bonds and savings accounts (pure functions over preloaded inputs)."""
import datetime as dt
from collections.abc import Iterable, Mapping, Sequence
from dataclasses import dataclass
from decimal import Decimal

from app.bonds import edo
from app.savings.interest import savings_days
from app.valuation.engine import ONE_DAY, ZERO, Row, money

FLAG_RATE_ESTIMATED = "rate_estimated"


@dataclass(frozen=True)
class Holding:
    id: int
    account_id: int
    purchase_date: dt.date
    quantity: int
    redeemed_at: dt.date | None
    series: edo.Series
    taxed: bool  # a regular account: 19 % on interest; IKE / IKZE pay none


@dataclass(frozen=True)
class SavingsInput:
    id: int
    account_id: int
    capitalization: str
    taxed: bool
    balances: Sequence[tuple[dt.date, Decimal]]
    rates: Sequence[tuple[dt.date, Decimal]]


def payout_day(holding: Holding, schedule: Sequence[edo.Period]) -> dt.date:
    """Early redemption before maturity, otherwise the maturity day."""
    maturity = schedule[-1].end
    return holding.redeemed_at if holding.redeemed_at is not None and holding.redeemed_at < maturity else maturity


def payout_per_bond(holding: Holding, schedule: Sequence[edo.Period]) -> Decimal:
    day = payout_day(holding, schedule)
    gross = edo.value(schedule, day)
    if day < schedule[-1].end:
        return edo.redemption_value(gross, holding.series.early_redemption_fee, holding.taxed)
    return edo.net_value(gross, holding.taxed)


def bond_rows(holdings: Iterable[Holding], cpi: Mapping[dt.date, Decimal], start: dt.date, end: dt.date) -> list[Row]:
    """Each purchase from its day: net value (the purchase is a deposit of 100 zł a bond); on the payout day the
    payout; the next day nothing, the payout leaving the account (a withdrawal at the start of that day, so a
    portfolio of bonds alone never shows the payout as a −100 % day)."""
    rows: list[Row] = []
    for holding in holdings:
        schedule = edo.periods(holding.purchase_date, holding.series, cpi)
        paid_on = payout_day(holding, schedule)
        quantity = Decimal(holding.quantity)
        cost = quantity * edo.NOMINAL
        payout = quantity * payout_per_bond(holding, schedule)
        day = max(holding.purchase_date, start)
        while day <= min(end, paid_on + ONE_DAY):
            flow = cost if day == holding.purchase_date else ZERO
            if day < paid_on:
                value = quantity * edo.net_value(edo.value(schedule, day), holding.taxed)
                flags = (FLAG_RATE_ESTIMATED,) if edo.period_on(schedule, day).estimated else ()
                rows.append(Row(holding.account_id, None, day, quantity, value, cost, flow, flags,
                                bond_holding_id=holding.id))
            elif day == paid_on:
                rows.append(Row(holding.account_id, None, day, quantity, payout, cost, flow,
                                bond_holding_id=holding.id))
            else:
                rows.append(Row(holding.account_id, None, day, ZERO, ZERO, ZERO, -payout, bond_holding_id=holding.id))
            day += ONE_DAY
    return rows


def savings_rows(accounts: Iterable[SavingsInput], start: dt.date, end: dt.date) -> list[Row]:
    """Each savings account from its first copied balance: the balance, the capital put in so far (cost) and the
    day's deposit or withdrawal."""
    rows: list[Row] = []
    for account in accounts:
        invested = ZERO
        for day in savings_days(account.balances, account.rates, account.capitalization, account.taxed, end):
            invested += day.net_flow
            if day.day >= start:
                rows.append(Row(account.account_id, None, day.day, day.balance, money(day.balance), money(invested),
                                money(day.net_flow), savings_account_id=account.id))
    return rows
```

Uwaga do testu wykupu w terminie: wiersz z 14 IX 2036 jest pierwszy na liście (dlatego `[1:]` w teście), 15 IX to dzień wypłaty, 16 IX — wypłata opuszcza konto; pętla kończy się na `paid_on + 1`, więc 17–30 IX nie ma wierszy.

- [ ] **Step 5: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_fixed_income_rows.py tests/test_valuation_engine_rows.py tests/test_valuation_engine_book.py -q`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add api/app/valuation/engine.py api/app/valuation/fixed_income.py api/tests/test_fixed_income_rows.py
git commit -m "feat(valuation): daily rows of bond purchases and savings accounts

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 5: Przeliczanie wyceny z obligacjami i kontami; pulpit

**Files:**
- Modify: `api/app/valuation/service.py`, `api/app/scoping.py`, `api/app/accounts/router.py`, `api/app/portfolio/service.py`
- Create: `api/tests/test_fixed_income_valuation.py`

**Interfaces:**
- Consumes: `Holding`, `SavingsInput`, `bond_rows`, `savings_rows`, `FLAG_RATE_ESTIMATED` (Task 4); modele z Task 1; `Cpi` (`app.models`).
- Produces:
  - `UserScope.bond_holdings() -> Select[tuple[BondHolding]]`, `UserScope.savings_accounts() -> Select[tuple[SavingsAccount]]` (przez konta użytkownika).
  - `service.FixedIncome(holdings: list[Holding], savings: list[SavingsInput], cpi: dict[date, Decimal])`; `service.load_fixed_income(scope) -> FixedIncome`.
  - `recompute_user` zapisuje też wiersze obligacji i kont (`bond_holding_id`, `savings_account_id`).
  - `service.users_with_holdings(db) -> list[int]` — użytkownicy z transakcjami, zakupami obligacji lub kontem oszczędnościowym; `mark_new_days` używa go zamiast `users_with_transactions` i dodatkowo oznacza każdego od najwcześniejszego wiersza z flagą `rate_estimated` (inflacja mogła dojść).
  - `PATCH /api/accounts/{id}` ze zmianą `wrapper` oznacza właściciela od `date.min` i przelicza w tle.
  - Pulpit: typy `bonds` („Obligacje”) i `savings` („Konta oszczędnościowe”) w `by_kind`; `cash_pln` tylko z wierszy gotówki; `approximate_positions` liczy każdy wiersz składnika z flagami.

- [ ] **Step 1: Testy**

`api/tests/test_fixed_income_valuation.py`:

```python
import datetime as dt
from collections.abc import Callable, Iterator
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import (
    Account, BondHolding, BondSeries, Cpi, DailyValuation, SavingsAccount, SavingsBalance, SavingsRate, User,
)
from app.valuation.service import mark_new_days, recompute_user
from tests.valuation_seed import SAT, seed_user, valuate

LoginAs = Callable[[str], dict[str, str]]


@pytest.fixture
def db(engine: Engine, clean_db: None) -> Iterator[Session]:
    with Session(engine, expire_on_commit=False) as session:
        yield session


def _series(db: Session, name: str = "EDO0936", issue: dt.date = dt.date(2026, 9, 1)) -> None:
    db.add(BondSeries(series=name, bond_type="EDO", issue_month=issue, maturity_months=120,
                      first_period_rate=Decimal("5.35"), margin=Decimal("2.00"), early_redemption_fee=Decimal("3.00"),
                      interest_mode="capitalized", rate_basis="cpi"))
    db.commit()


def _account(db: Session, user_id: int, kind: str, wrapper: str = "regular") -> int:
    account = Account(user_id=user_id, name=f"{kind} {wrapper}", kind=kind, wrapper=wrapper, currency="PLN")
    db.add(account)
    db.commit()
    return account.id


def _bonds(db: Session, account_id: int, bought: dt.date = dt.date(2026, 9, 15), series: str = "EDO0936") -> int:
    holding = BondHolding(account_id=account_id, bond_type="EDO", series=series, quantity=10, purchase_date=bought)
    db.add(holding)
    db.commit()
    return holding.id


def _savings(db: Session, account_id: int) -> int:
    savings = SavingsAccount(account_id=account_id, capitalization="monthly")
    db.add(savings)
    db.flush()
    db.add_all([SavingsRate(savings_account_id=savings.id, valid_from=dt.date(2026, 9, 1), annual_rate=Decimal("5")),
                SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 9, 1), balance=Decimal("10000"))])
    db.commit()
    return savings.id


def _row(db: Session, user_id: int, day: dt.date, **component: int) -> DailyValuation:
    return db.scalar(select(DailyValuation).filter_by(user_id=user_id, date=day, **component))


def test_bonds_and_savings_alone_get_daily_rows(db: Session) -> None:
    _series(db)
    user_id = seed_user(db)
    holding_id = _bonds(db, _account(db, user_id, "bonds"))
    savings_id = _savings(db, _account(db, user_id, "savings"))

    valuate(db, user_id)

    bond = _row(db, user_id, SAT, bond_holding_id=holding_id)
    savings = _row(db, user_id, dt.date(2026, 9, 30), savings_account_id=savings_id)
    assert (bond.value_pln, bond.cost_pln, bond.instrument_id) == (Decimal("1001.3000"), Decimal("1000.0000"), None)
    assert savings is None  # valued up to Saturday 2026-09-26 only
    savings = _row(db, user_id, SAT, savings_account_id=savings_id)
    assert (savings.value_pln, savings.net_flow_pln) == (Decimal("10000.0000"), Decimal("0.0000"))
    assert _row(db, user_id, dt.date(2026, 9, 15), bond_holding_id=holding_id).net_flow_pln == Decimal("1000.0000")


def test_new_days_mark_holders_of_bonds_and_savings_and_reopen_estimated_periods(db: Session) -> None:
    _series(db)
    _series(db, "EDO0935", dt.date(2025, 9, 1))
    bonds_only, savings_only = seed_user(db), seed_user(db, "bartek@portfolio.dev")
    _bonds(db, _account(db, bonds_only, "bonds"), dt.date(2025, 9, 15), "EDO0935")  # 2nd period from 2026-09-15
    _savings(db, _account(db, savings_only, "savings"))
    valuate(db, bonds_only)
    valuate(db, savings_only)

    mark_new_days(db, SAT)
    db.commit()

    stale = dict(db.execute(select(User.id, User.valuations_stale_from)).all())
    # no CPI for July 2026 yet: the bond rows from 2026-09-15 are estimated and stay open
    assert (stale[bonds_only], stale[savings_only]) == (dt.date(2026, 9, 15), SAT)


def test_cpi_arrival_replaces_the_estimated_rate(db: Session) -> None:
    _series(db, "EDO0935", dt.date(2025, 9, 1))
    user_id = seed_user(db)
    holding_id = _bonds(db, _account(db, user_id, "bonds"), dt.date(2025, 9, 15), "EDO0935")
    valuate(db, user_id)
    assert _row(db, user_id, SAT, bond_holding_id=holding_id).flags == ["rate_estimated"]

    db.add(Cpi(year_month=dt.date(2026, 7, 1), yoy=Decimal("2.5")))
    db.commit()
    mark_new_days(db, SAT)
    db.commit()
    recompute_user(db, user_id, SAT)

    assert _row(db, user_id, SAT, bond_holding_id=holding_id).flags == []


def test_dashboard_shows_bonds_and_savings_as_their_own_kinds(
    client: TestClient, login_as: LoginAs, engine: Engine
) -> None:
    headers = login_as("anna@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        _series(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        _bonds(db, _account(db, user_id, "bonds"))
        _savings(db, _account(db, user_id, "savings"))
        valuate(db, user_id)

    body = client.get("/api/portfolio/summary", headers=headers).json()

    assert (body["value_pln"], body["cash_pln"], body["invested_pln"]) == ("11001.30", "0.00", "11000.00")
    assert [(item["key"], item["name"], item["value_pln"]) for item in body["by_kind"]] == [
        ("savings", "Konta oszczędnościowe", "10000.00"), ("bonds", "Obligacje", "1001.30")]


def test_switching_an_account_to_ike_revalues_its_history_without_tax(
    client: TestClient, login_as: LoginAs, engine: Engine
) -> None:
    headers = login_as("anna@portfolio.dev")
    with Session(engine, expire_on_commit=False) as db:
        _series(db)
        user_id = db.scalar(select(User.id).where(User.email == "anna@portfolio.dev"))
        account_id = _account(db, user_id, "bonds")
        holding_id = _bonds(db, account_id)
        valuate(db, user_id)

    response = client.patch(f"/api/accounts/{account_id}", json={"wrapper": "ike"}, headers=headers)

    assert response.status_code == 200
    with Session(engine) as db:
        rows = db.scalars(select(DailyValuation).filter_by(bond_holding_id=holding_id, date=SAT)).all()
        assert [row.value_pln for row in rows] == [Decimal("1001.6000")]
```


- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_fixed_income_valuation.py -q`
Expected: FAIL — brak wierszy obligacji / kont (`None.value_pln`).

- [ ] **Step 3: `UserScope`**

W `api/app/scoping.py` (import `BondHolding`, `SavingsAccount` z `app.models`):

```python
    def bond_holdings(self) -> Select[tuple[BondHolding]]:
        own_accounts = select(Account.id).where(Account.user_id == self.user.id)
        return (
            select(BondHolding).where(BondHolding.account_id.in_(own_accounts))
            .order_by(BondHolding.purchase_date, BondHolding.id)
        )

    def savings_accounts(self) -> Select[tuple[SavingsAccount]]:
        own_accounts = select(Account.id).where(Account.user_id == self.user.id)
        return select(SavingsAccount).where(SavingsAccount.account_id.in_(own_accounts)).order_by(SavingsAccount.id)
```

- [ ] **Step 4: Ładowanie i przeliczanie**

W `api/app/valuation/service.py` (importy: `BondHolding`, `BondSeries`, `Cpi`, `SavingsAccount`, `SavingsBalance`, `SavingsRate` z `app.models`; `from app.bonds.edo import Series`; `from app.valuation.fixed_income import FLAG_RATE_ESTIMATED, Holding, SavingsInput, bond_rows, savings_rows`):

```python
@dataclass(frozen=True)
class FixedIncome:
    holdings: list[Holding]
    savings: list[SavingsInput]
    cpi: dict[dt.date, Decimal]


def load_fixed_income(scope: UserScope) -> FixedIncome:
    """The user's bond purchases (with their series) and savings accounts (with balances and rates); CPI when
    there are bonds. Accounts marked IKE / IKZE pay no tax."""
    db = scope.db
    taxed = {account.id: account.wrapper == "regular" for account in db.scalars(scope.accounts())}
    holdings = [
        Holding(holding.id, holding.account_id, holding.purchase_date, holding.quantity, holding.redeemed_at,
                Series(series.first_period_rate, series.margin, series.early_redemption_fee), taxed[holding.account_id])
        for holding, series in db.execute(
            scope.bond_holdings().add_columns(BondSeries).join(BondSeries, BondSeries.series == BondHolding.series)
        ).tuples()
    ]
    savings = []
    for account in db.scalars(scope.savings_accounts()):
        balances = db.execute(select(SavingsBalance.as_of_date, SavingsBalance.balance)
                              .where(SavingsBalance.savings_account_id == account.id)
                              .order_by(SavingsBalance.as_of_date)).tuples().all()
        rates = db.execute(select(SavingsRate.valid_from, SavingsRate.annual_rate)
                           .where(SavingsRate.savings_account_id == account.id)
                           .order_by(SavingsRate.valid_from)).tuples().all()
        savings.append(SavingsInput(account.id, account.account_id, account.capitalization, taxed[account.account_id],
                                    list(balances), list(rates)))
    cpi = dict(db.execute(select(Cpi.year_month, Cpi.yoy)).tuples().all()) if holdings else {}
    return FixedIncome(holdings, savings, cpi)
```

(`Decimal` importuj z `decimal`, jeśli jeszcze nie ma w pliku.)

W `recompute_user` po `rows = daily_rows(...)`:

```python
        fixed = load_fixed_income(UserScope(db, user))
        rows += bond_rows(fixed.holdings, fixed.cpi, stale_from, today) + savings_rows(fixed.savings, stale_from, today)
```

i w słowniku `values` dopisz `"bond_holding_id": row.bond_holding_id, "savings_account_id": row.savings_account_id`.

Użytkownicy i nowe dni:

```python
def users_with_holdings(db: Session) -> list[int]:
    """Users with anything to value: transactions, bond purchases or a savings account."""
    traded = select(Account.user_id).join(Transaction, Transaction.account_id == Account.id)
    bonds = select(Account.user_id).join(BondHolding, BondHolding.account_id == Account.id)
    savings = select(Account.user_id).join(SavingsAccount, SavingsAccount.account_id == Account.id)
    return sorted(set(db.scalars(traded)) | set(db.scalars(bonds)) | set(db.scalars(savings)))


def mark_new_days(db: Session, today: dt.date) -> None:
    """Requests the days each user's history is missing: from the day after their last stored row (at most
    `today`, so today's row is refreshed), or the whole history when they have no rows yet; and from the first
    row valued at an estimated bond rate (the CPI may have arrived since). Days missed while the worker was down
    are filled this way. Does not commit."""
    last_rows = dict(db.execute(
        select(DailyValuation.user_id, func.max(DailyValuation.date)).group_by(DailyValuation.user_id)
    ).all())
    estimated = dict(db.execute(
        select(DailyValuation.user_id, func.min(DailyValuation.date))
        .where(DailyValuation.flags.contains([FLAG_RATE_ESTIMATED]))
        .group_by(DailyValuation.user_id)
    ).all())
    days = {}
    for user_id in users_with_holdings(db):
        day = min(today, last_rows[user_id] + dt.timedelta(days=1)) if user_id in last_rows else dt.date.min
        days[user_id] = min(day, estimated.get(user_id, day))
    _mark_stale_days(db, days)
```

(`users_with_transactions` zostaje — używa go `mark_market_changes` dla kursów walut. `DailyValuation.flags` to JSONB, `.contains([...])` daje `@>`.)

- [ ] **Step 5: Zmiana IKE / zwykłe**

`api/app/accounts/router.py`, w obsłudze `PATCH /{account_id}`: gdy `wrapper` się zmienia, przed commitem `mark_stale(scope.db, [scope.user.id], dt.date.min)` i po commicie `background.add_task(recompute_in_background, sessions, scope.user.id)` (parametry `background: BackgroundTasks`, `sessions: sessionmaker[Session] = Depends(get_session_factory)` jak w `app/imports/router.py`; importy: `mark_stale`, `recompute_in_background` z `app.valuation.service`, `get_session_factory` z `app.db`). Zmiana samej nazwy nie oznacza przeliczenia. Komentarz: „Podatek od odsetek obligacji i kont zależy od IKE/IKZE — cała historia konta się zmienia.”

- [ ] **Step 6: Pulpit**

`api/app/portfolio/service.py`:
- `BOND_KIND = "bonds"`, `SAVINGS_KIND = "savings"`, `KIND_NAMES` + `BOND_KIND: "Obligacje"`, `SAVINGS_KIND: "Konta oszczędnościowe"`.
- W `portfolio_summary` zapytanie `latest_rows` pobiera też `DailyValuation.bond_holding_id`, `DailyValuation.savings_account_id`; typ wiersza:

```python
def _kind(row: object, categories: dict[int, str | None]) -> str:
    if row.bond_holding_id is not None:
        return BOND_KIND
    if row.savings_account_id is not None:
        return SAVINGS_KIND
    if row.instrument_id is None:
        return CASH_KIND
    return categories.get(row.instrument_id) or OTHER_KIND
```

(adnotacja `row: Any`), w pętli: `kind = _kind(row, categories)`; `if kind == CASH_KIND: cash += row.value_pln` `elif row.flags: approximate += 1`.

- [ ] **Step 7: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_fixed_income_valuation.py -q`
Expected: PASS.

Run: `docker compose run --rm api pytest -q`
Expected: PASS, jedno istniejące ostrzeżenie.

- [ ] **Step 8: Commit**

```bash
git add api/app/valuation/service.py api/app/scoping.py api/app/accounts/router.py api/app/portfolio/service.py \
  api/tests/test_fixed_income_valuation.py
git commit -m "feat(valuation): value bonds and savings accounts daily; dashboard kinds; IKE switch revalues

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---
### Task 6: API obligacji i serii

**Files:**
- Create: `api/app/bonds/schemas.py`, `api/app/bonds/service.py`, `api/app/bonds/router.py`, `api/tests/test_bonds_api.py`
- Modify: `api/app/main.py`

**Interfaces:**
- Consumes: `edo.*` (Task 2); `Holding`, `payout_day`, `FLAG_RATE_ESTIMATED` (Task 4); `load_fixed_income`, `mark_stale`, `recompute_in_background`, `local_today` (`app.valuation.service`); `UserScope.bond_holdings()`, `get_account`; modele z Task 1.
- Produces (HTTP):
  - `GET /api/bond-series` → `list[BondSeriesOut]`; `POST /api/bond-series` (`BondSeriesIn`) → 201; seria już istnieje → 409 `series_exists`.
  - `GET /api/bonds?date=` → `list[BondOut]`; `GET /api/bonds/{id}?date=` → `BondDetailOut` (wartość brutto 1 szt., wartość netto, wartość przy wykupie tego dnia, harmonogram okresów); `POST /api/bonds` (`BondIn`) → 201 `BondOut`; `PATCH /api/bonds/{id}` (`BondUpdate`) → `BondOut`; `DELETE /api/bonds/{id}` → 204. Każdy zapis oznacza właściciela od dnia zakupu i przelicza w tle.
  - Błędy: konto nie typu `bonds` → 422 `wrong_account_kind`; seria spoza tabeli bez stawki i marży → 422 `series_unknown`; data zakupu w przyszłości → 422 `purchase_in_future`; `redeemed_at` przed zakupem lub od dnia wykupu → 422 `bad_redemption_date`; obce konto / zakup → 404.

- [ ] **Step 1: Testy**

`api/tests/test_bonds_api.py`:

```python
import datetime as dt
from collections.abc import Callable
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import Engine, select
from sqlalchemy.orm import Session

from app.models import BondSeries, DailyValuation

LoginAs = Callable[[str], dict[str, str]]
ON = {"date": "2026-09-26"}


@pytest.fixture
def world(client: TestClient, login_as: LoginAs, engine: Engine) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    with Session(engine) as db:
        db.add(BondSeries(series="EDO0936", bond_type="EDO", issue_month=dt.date(2026, 9, 1), maturity_months=120,
                          first_period_rate=Decimal("5.35"), margin=Decimal("2.00"),
                          early_redemption_fee=Decimal("3.00"), interest_mode="capitalized", rate_basis="cpi"))
        db.commit()
    bonds = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=anna).json()["id"]
    broker = client.post("/api/accounts", json={"name": "XTB", "kind": "broker", "broker": "xtb",
                                                "external_account_number": "1"}, headers=anna).json()["id"]
    return {"anna": anna, "bartek": bartek, "bonds": bonds, "broker": broker}


def _buy(client: TestClient, world: dict, **fields: object) -> object:
    body = {"account_id": world["bonds"], "bond_type": "EDO", "quantity": 10, "purchase_date": "2026-09-15", **fields}
    return client.post("/api/bonds", json=body, headers=world["anna"])


def test_purchase_is_valued_net_of_tax_with_its_schedule(client: TestClient, world: dict, engine: Engine) -> None:
    created = _buy(client, world)
    assert created.status_code == 201
    holding_id = created.json()["id"]

    detail = client.get(f"/api/bonds/{holding_id}", params=ON, headers=world["anna"]).json()

    assert {key: detail["bond"][key] for key in ("series", "quantity", "maturity_date", "status", "value_pln")} == {
        "series": "EDO0936", "quantity": 10, "maturity_date": "2036-09-15", "status": "active", "value_pln": "1001.30"}
    # 11 days: 100.16 per bond; early redemption: the fee takes the 0.16 zł of interest → 100.00 × 10
    assert (detail["value_per_bond"], detail["redemption_today_pln"]) == ("100.16", "1000.00")
    assert [(p["number"], p["start"], p["estimated"]) for p in detail["periods"][:2]] == [
        (1, "2026-09-15", False), (2, "2027-09-15", True)]
    with Session(engine) as db:  # recomputed in the background after the purchase
        assert db.scalar(select(DailyValuation.net_flow_pln).where(
            DailyValuation.bond_holding_id == holding_id, DailyValuation.date == dt.date(2026, 9, 15))) == Decimal(
            "1000.0000")


def test_series_outside_the_table_needs_its_rates_and_is_then_shared(client: TestClient, world: dict) -> None:
    missing = _buy(client, world, purchase_date="2026-08-20")
    added = _buy(client, world, purchase_date="2026-08-20", first_period_rate="5.60", margin="2.00")

    assert (missing.status_code, missing.json()["code"], missing.json()["details"]) == (
        422, "series_unknown", {"series": "EDO0836"})
    assert added.status_code == 201
    series = {s["series"]: s for s in client.get("/api/bond-series", headers=world["bartek"]).json()}
    assert (series["EDO0836"]["first_period_rate"], series["EDO0836"]["early_redemption_fee"],
            series["EDO0836"]["issue_month"]) == ("5.6000", "3.00", "2026-08-01")


def test_early_redemption_marks_the_purchase_redeemed(client: TestClient, world: dict) -> None:
    holding_id = _buy(client, world).json()["id"]

    updated = client.patch(f"/api/bonds/{holding_id}", json={"redeemed_at": "2026-09-20"}, headers=world["anna"])
    listed = client.get("/api/bonds", params=ON, headers=world["anna"]).json()

    assert (updated.status_code, updated.json()["redeemed_at"]) == (200, "2026-09-20")
    assert [(b["status"], b["value_pln"]) for b in listed] == [("redeemed", "0.00")]


@pytest.mark.parametrize(
    ("fields", "code"),
    [
        ({"account_id": "broker"}, "wrong_account_kind"),
        ({"purchase_date": "2999-01-01"}, "purchase_in_future"),
    ],
)
def test_purchase_errors(client: TestClient, world: dict, fields: dict, code: str) -> None:
    if fields.get("account_id") == "broker":
        fields = {**fields, "account_id": world["broker"]}
    response = _buy(client, world, **fields)
    assert (response.status_code, response.json()["code"]) == (422, code)


@pytest.mark.parametrize("day", ["2026-09-14", "2036-09-15"])
def test_redemption_date_must_fall_between_purchase_and_maturity(client: TestClient, world: dict, day: str) -> None:
    holding_id = _buy(client, world).json()["id"]
    response = client.patch(f"/api/bonds/{holding_id}", json={"redeemed_at": day}, headers=world["anna"])
    assert (response.status_code, response.json()["code"]) == (422, "bad_redemption_date")


def test_existing_series_cannot_be_added_again(client: TestClient, world: dict) -> None:
    response = client.post("/api/bond-series", json={"series": "EDO0936", "first_period_rate": "6", "margin": "2"},
                           headers=world["anna"])
    assert (response.status_code, response.json()["code"]) == (409, "series_exists")


def test_someone_elses_bonds_are_404(client: TestClient, world: dict) -> None:
    holding_id = _buy(client, world).json()["id"]
    foreign = [
        client.get(f"/api/bonds/{holding_id}", headers=world["bartek"]),
        client.patch(f"/api/bonds/{holding_id}", json={"note": "x"}, headers=world["bartek"]),
        client.delete(f"/api/bonds/{holding_id}", headers=world["bartek"]),
        client.post("/api/bonds", json={"account_id": world["bonds"], "bond_type": "EDO", "quantity": 1,
                                        "purchase_date": "2026-09-15"}, headers=world["bartek"]),
    ]
    assert [(r.status_code, r.json()["code"]) for r in foreign] == [(404, "not_found")] * 4
    assert client.get("/api/bonds", headers=world["bartek"]).json() == []


def test_deleting_a_purchase_removes_its_valuation(client: TestClient, world: dict, engine: Engine) -> None:
    holding_id = _buy(client, world).json()["id"]

    assert client.delete(f"/api/bonds/{holding_id}", headers=world["anna"]).status_code == 204
    with Session(engine) as db:
        assert db.scalar(select(DailyValuation.id).where(DailyValuation.bond_holding_id == holding_id)) is None
```

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_bonds_api.py -q`
Expected: FAIL — 404 dla `/api/bonds`.

- [ ] **Step 3: Schematy**

`api/app/bonds/schemas.py`:

```python
import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, model_validator

SERIES_PATTERN = r"^EDO(0[1-9]|1[0-2])\d{2}$"
DEFAULT_EDO_FEE = Decimal("3.00")  # zł per bond for purchases from 1 September 2024
Rate = Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]


class BondSeriesIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    series: str = Field(pattern=SERIES_PATTERN)
    first_period_rate: Rate
    margin: Rate
    early_redemption_fee: Annotated[Decimal, Field(ge=0, max_digits=6, decimal_places=2)] = DEFAULT_EDO_FEE


class BondSeriesOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    series: str
    bond_type: str
    issue_month: dt.date
    maturity_months: int
    first_period_rate: Decimal
    margin: Decimal
    early_redemption_fee: Decimal


class BondIn(BaseModel):
    """A purchase. The series follows from the purchase day; the rates are needed only for a series the
    application does not know yet (a known series keeps its stored rates)."""

    model_config = ConfigDict(extra="forbid")

    account_id: Annotated[int, Field(ge=1, le=2**31 - 1)]
    bond_type: Literal["EDO"]
    quantity: Annotated[int, Field(ge=1, le=1_000_000)]
    purchase_date: dt.date
    first_period_rate: Rate | None = None
    margin: Rate | None = None
    note: Annotated[str, Field(max_length=500)] = ""


class BondUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    quantity: Annotated[int, Field(ge=1, le=1_000_000)] | None = None
    redeemed_at: dt.date | None = None  # null cancels an early redemption
    note: Annotated[str, Field(max_length=500)] | None = None

    @model_validator(mode="after")
    def _no_null_except_redemption(self) -> Self:
        for name in ("quantity", "note"):
            if name in self.model_fields_set and getattr(self, name) is None:
                raise ValueError(f"Pole {name} nie może być puste.")
        return self


class BondOut(BaseModel):
    id: int
    account_id: int
    account_name: str
    bond_type: str
    series: str
    quantity: int
    purchase_date: dt.date
    redeemed_at: dt.date | None
    maturity_date: dt.date
    note: str
    status: Literal["active", "redeemed", "matured"]
    value_pln: Decimal  # net of tax on the day; 0 once paid out
    flags: list[str]


class PeriodOut(BaseModel):
    number: int
    start: dt.date
    end: dt.date
    rate: Decimal
    estimated: bool


class BondDetailOut(BaseModel):
    bond: BondOut
    value_per_bond: Decimal  # before tax
    redemption_today_pln: Decimal | None  # early redemption on the day (None once paid out)
    periods: list[PeriodOut]
```

- [ ] **Step 4: Usługa**

`api/app/bonds/service.py`:

```python
"""Bond purchases as the API shows them (computed live for one day with the valuation's own functions)."""
import datetime as dt

from app.bonds import edo
from app.bonds.schemas import BondDetailOut, BondOut, PeriodOut
from app.models import Account, BondHolding
from app.valuation.engine import ZERO
from app.valuation.fixed_income import FLAG_RATE_ESTIMATED, Holding, payout_day
from app.valuation.service import FixedIncome


def _status(holding: Holding, schedule: list[edo.Period], day: dt.date) -> str:
    paid_on = payout_day(holding, schedule)
    if day < paid_on:
        return "active"
    return "redeemed" if paid_on < schedule[-1].end else "matured"


def bond_detail(stored: BondHolding, account: Account, fixed: FixedIncome, day: dt.date) -> BondDetailOut:
    holding = next(h for h in fixed.holdings if h.id == stored.id)
    schedule = edo.periods(holding.purchase_date, holding.series, fixed.cpi)
    status = _status(holding, schedule, day)
    gross = edo.value(schedule, day)
    active = status == "active"
    quantity = holding.quantity
    flags = [FLAG_RATE_ESTIMATED] if active and edo.period_on(schedule, day).estimated else []
    bond = BondOut(
        id=stored.id, account_id=account.id, account_name=account.name, bond_type=stored.bond_type,
        series=stored.series, quantity=quantity, purchase_date=stored.purchase_date, redeemed_at=stored.redeemed_at,
        maturity_date=schedule[-1].end, note=stored.note, status=status,
        value_pln=quantity * edo.net_value(gross, holding.taxed) if active else ZERO.quantize(edo.CENT), flags=flags,
    )
    redemption = (quantity * edo.redemption_value(gross, holding.series.early_redemption_fee, holding.taxed)
                  if active else None)
    return BondDetailOut(
        bond=bond, value_per_bond=gross, redemption_today_pln=redemption,
        periods=[PeriodOut(number=p.number, start=p.start, end=p.end, rate=p.rate, estimated=p.estimated)
                 for p in schedule],
    )
```

- [ ] **Step 5: Router**

`api/app/bonds/router.py`:

```python
"""Treasury bond purchases (the owner's) and bond series (shared). Each change recomputes the owner's valuations
from the purchase day in the background."""
import datetime as dt
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.bonds import edo
from app.bonds.schemas import (
    DEFAULT_EDO_FEE, BondDetailOut, BondIn, BondOut, BondSeriesIn, BondSeriesOut, BondUpdate,
)
from app.bonds.service import bond_detail
from app.db import get_session_factory
from app.errors import ApiError
from app.models import BondHolding, BondSeries
from app.scoping import DbId, UserScope, get_scope, not_found
from app.valuation.service import load_fixed_income, local_today, mark_stale, recompute_in_background

router = APIRouter(prefix="/api", tags=["bonds"])

DayQuery = Annotated[dt.date | None, Query(alias="date")]
EDO_MONTHS = 120


def _new_series(name: str, first_period_rate: Decimal, margin: Decimal, fee: Decimal) -> BondSeries:
    """An EDO series from its name: EDOmmyy matures in month mm of 20yy and was sold ten years earlier."""
    month, year = int(name[3:5]), 2000 + int(name[5:7])
    return BondSeries(series=name, bond_type="EDO", issue_month=dt.date(year - edo.YEARS, month, 1),
                      maturity_months=EDO_MONTHS, first_period_rate=first_period_rate, margin=margin,
                      early_redemption_fee=fee, interest_mode="capitalized", rate_basis="cpi")


def _holding(scope: UserScope, holding_id: int) -> BondHolding:
    holding = scope.db.scalar(scope.bond_holdings().where(BondHolding.id == holding_id))
    if holding is None:
        raise not_found()
    return holding


def _saved(scope: UserScope, day: dt.date, background: BackgroundTasks, sessions: sessionmaker[Session]) -> None:
    mark_stale(scope.db, [scope.user.id], day)
    scope.db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)


def _detail(scope: UserScope, holding: BondHolding, day: dt.date) -> BondDetailOut:
    return bond_detail(holding, scope.get_account(holding.account_id), load_fixed_income(scope), day)


@router.get("/bond-series", response_model=list[BondSeriesOut])
def list_series(scope: UserScope = Depends(get_scope)) -> list[BondSeries]:
    return list(scope.db.scalars(select(BondSeries).order_by(BondSeries.issue_month, BondSeries.series)))


@router.post("/bond-series", status_code=201, response_model=BondSeriesOut)
def add_series(body: BondSeriesIn, scope: UserScope = Depends(get_scope)) -> BondSeries:
    if scope.db.get(BondSeries, body.series) is not None:
        raise ApiError(409, "series_exists", f"Seria {body.series} już jest w aplikacji.")
    series = _new_series(body.series, body.first_period_rate, body.margin, body.early_redemption_fee)
    scope.db.add(series)
    scope.db.commit()
    return series


@router.get("/bonds", response_model=list[BondOut])
def list_bonds(scope: UserScope = Depends(get_scope), day: DayQuery = None) -> list[BondOut]:
    fixed = load_fixed_income(scope)
    accounts = {account.id: account for account in scope.db.scalars(scope.accounts())}
    return [bond_detail(h, accounts[h.account_id], fixed, day or local_today()).bond
            for h in scope.db.scalars(scope.bond_holdings())]


@router.get("/bonds/{holding_id}", response_model=BondDetailOut)
def get_bond(holding_id: DbId, scope: UserScope = Depends(get_scope), day: DayQuery = None) -> BondDetailOut:
    return _detail(scope, _holding(scope, holding_id), day or local_today())


@router.post("/bonds", status_code=201, response_model=BondOut)
def buy_bonds(
    body: BondIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> BondOut:
    account = scope.get_account(body.account_id)
    if account.kind != "bonds":
        raise ApiError(422, "wrong_account_kind", "Obligacje zapisuje się na koncie typu „obligacje”.")
    if body.purchase_date > local_today():
        raise ApiError(422, "purchase_in_future", "Data zakupu nie może być z przyszłości.")
    name = edo.series_name(body.purchase_date)
    if scope.db.get(BondSeries, name) is None:
        if body.first_period_rate is None or body.margin is None:
            raise ApiError(422, "series_unknown",
                           f"Serii {name} nie ma jeszcze w aplikacji — podaj oprocentowanie 1. roku i marżę.",
                           {"series": name})
        scope.db.add(_new_series(name, body.first_period_rate, body.margin, DEFAULT_EDO_FEE))
    holding = BondHolding(account_id=account.id, bond_type=body.bond_type, series=name, quantity=body.quantity,
                          purchase_date=body.purchase_date, note=body.note)
    scope.db.add(holding)
    scope.db.flush()
    _saved(scope, holding.purchase_date, background, sessions)
    return _detail(scope, holding, local_today()).bond


@router.patch("/bonds/{holding_id}", response_model=BondOut)
def update_bonds(
    holding_id: DbId,
    body: BondUpdate,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> BondOut:
    holding = _holding(scope, holding_id)
    if "redeemed_at" in body.model_fields_set and body.redeemed_at is not None:
        maturity = edo.anniversary(holding.purchase_date, edo.YEARS)
        if not holding.purchase_date <= body.redeemed_at < maturity:
            raise ApiError(422, "bad_redemption_date",
                           "Data wcześniejszego wykupu musi przypadać od dnia zakupu do dnia przed terminem wykupu.")
    for name in body.model_fields_set:
        setattr(holding, name, getattr(body, name))
    _saved(scope, holding.purchase_date, background, sessions)
    return _detail(scope, holding, local_today()).bond


@router.delete("/bonds/{holding_id}", status_code=204)
def delete_bonds(
    holding_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    holding = _holding(scope, holding_id)
    day = holding.purchase_date
    scope.db.delete(holding)
    _saved(scope, day, background, sessions)
    return Response(status_code=204)
```

(`from decimal import Decimal` w importach routera.)

`api/app/main.py`: `from app.bonds.router import router as bonds_router` i `app.include_router(bonds_router)` (po `corporate_actions_router`).

- [ ] **Step 6: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_bonds_api.py -q`
Expected: PASS.

- [ ] **Step 7: Commit**

```bash
git add api/app/bonds api/app/main.py api/tests/test_bonds_api.py
git commit -m "feat(bonds): API for bond purchases, early redemption and series

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 7: API kont oszczędnościowych

**Files:**
- Create: `api/app/savings/schemas.py`, `api/app/savings/router.py`, `api/tests/test_savings_api.py`
- Modify: `api/app/main.py`

**Interfaces:**
- Consumes: `SavingsAccount`, `SavingsBalance`, `SavingsRate` (Task 1); `UserScope.get_account`; `mark_stale`, `recompute_in_background`, `local_today`.
- Produces (HTTP, prefiks `/api/savings-accounts/{account_id}`):
  - `PUT ""` (`{capitalization}`) → ustawia / zmienia kapitalizację (konto musi być typu `savings`, inaczej 422 `wrong_account_kind`); `GET ""` → `SavingsAccountOut {account_id, capitalization, rates, balances}` (nieustawione → 404).
  - `POST /balances` (`{as_of_date, balance}`), `DELETE /balances/{id}`; `POST /rates` (`{valid_from, annual_rate}`), `DELETE /rates/{id}`. Nieustawione konto → 409 `savings_not_configured`; ta sama data drugi raz → 409 `duplicate_date`; saldo z przyszłości → 422 `balance_in_future`.
  - Każdy zapis oznacza właściciela od dotkniętej daty (zmiana kapitalizacji — od `date.min`) i przelicza w tle.

- [ ] **Step 1: Testy**

`api/tests/test_savings_api.py`:

```python
from collections.abc import Callable

import pytest
from fastapi.testclient import TestClient

LoginAs = Callable[[str], dict[str, str]]
ON = {"date": "2026-09-30"}


@pytest.fixture
def world(client: TestClient, login_as: LoginAs) -> dict[str, object]:
    anna, bartek = login_as("anna@portfolio.dev"), login_as("bartek@portfolio.dev")
    savings = client.post("/api/accounts", json={"name": "Konto oszczędnościowe", "kind": "savings"},
                          headers=anna).json()["id"]
    bonds = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=anna).json()["id"]
    return {"anna": anna, "bartek": bartek, "savings": savings, "bonds": bonds,
            "url": f"/api/savings-accounts/{savings}"}


def test_configured_account_with_rate_and_balance_earns_interest(client: TestClient, world: dict) -> None:
    anna, url = world["anna"], world["url"]
    assert client.put(url, json={"capitalization": "monthly"}, headers=anna).status_code == 200
    assert client.post(f"{url}/rates", json={"valid_from": "2026-09-01", "annual_rate": "5"},
                       headers=anna).status_code == 201
    assert client.post(f"{url}/balances", json={"as_of_date": "2026-09-01", "balance": "10000"},
                       headers=anna).status_code == 201

    account = client.get(url, headers=anna).json()
    positions = client.get("/api/positions", params=ON, headers=anna).json()

    assert (account["capitalization"], [r["annual_rate"] for r in account["rates"]],
            [b["balance"] for b in account["balances"]]) == ("monthly", ["5.0000"], ["10000.0000"])
    (item,) = [p for p in positions if p["kind"] == "savings"]
    assert (item["name"], item["value_pln"], item["cost_pln"], item["unrealized_pln"]) == (
        "Konto oszczędnościowe", "10032.18", "10000.00", "32.18")


def test_entries_need_a_configured_account_and_one_entry_per_day(client: TestClient, world: dict) -> None:
    anna, url = world["anna"], world["url"]
    early = client.post(f"{url}/balances", json={"as_of_date": "2026-09-01", "balance": "1"}, headers=anna)
    client.put(url, json={"capitalization": "daily"}, headers=anna)
    client.post(f"{url}/rates", json={"valid_from": "2026-09-01", "annual_rate": "5"}, headers=anna)
    duplicate = client.post(f"{url}/rates", json={"valid_from": "2026-09-01", "annual_rate": "4"}, headers=anna)
    future = client.post(f"{url}/balances", json={"as_of_date": "2999-01-01", "balance": "1"}, headers=anna)

    assert [(r.status_code, r.json()["code"]) for r in (early, duplicate, future)] == [
        (409, "savings_not_configured"), (409, "duplicate_date"), (422, "balance_in_future")]


def test_deleting_an_entry(client: TestClient, world: dict) -> None:
    anna, url = world["anna"], world["url"]
    client.put(url, json={"capitalization": "monthly"}, headers=anna)
    balance_id = client.post(f"{url}/balances", json={"as_of_date": "2026-09-01", "balance": "5"},
                             headers=anna).json()["id"]

    assert client.delete(f"{url}/balances/{balance_id}", headers=anna).status_code == 204
    assert client.get(url, headers=anna).json()["balances"] == []


def test_wrong_kind_and_foreign_accounts(client: TestClient, world: dict) -> None:
    wrong = client.put(f"/api/savings-accounts/{world['bonds']}", json={"capitalization": "monthly"},
                       headers=world["anna"])
    foreign = client.put(world["url"], json={"capitalization": "monthly"}, headers=world["bartek"])
    unset = client.get(world["url"], headers=world["anna"])

    assert [(r.status_code, r.json()["code"]) for r in (wrong, foreign, unset)] == [
        (422, "wrong_account_kind"), (404, "not_found"), (404, "not_found")]
```

(Pozycja konta oszczędnościowego w `/api/positions` pochodzi z Task 8 — ten test przechodzi dopiero po Task 8. W Task 7 oznacz go `@pytest.mark.skip(reason="positions of savings accounts come in Task 8")` i usuń ten znacznik w Task 8.)

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_savings_api.py -q`
Expected: FAIL — 404 dla `/api/savings-accounts/...`.

- [ ] **Step 3: Schematy**

`api/app/savings/schemas.py`:

```python
import datetime as dt
from decimal import Decimal
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field

Capitalization = Literal["daily", "monthly", "quarterly"]


class SavingsSettingsIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    capitalization: Capitalization


class SavingsRateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    valid_from: dt.date
    annual_rate: Annotated[Decimal, Field(ge=0, le=100, max_digits=7, decimal_places=4)]  # percent a year


class SavingsBalanceIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    as_of_date: dt.date
    balance: Annotated[Decimal, Field(ge=0, max_digits=16, decimal_places=2)]


class SavingsRateOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    valid_from: dt.date
    annual_rate: Decimal


class SavingsBalanceOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    as_of_date: dt.date
    balance: Decimal


class SavingsAccountOut(BaseModel):
    account_id: int
    capitalization: Capitalization
    rates: list[SavingsRateOut]
    balances: list[SavingsBalanceOut]
```

- [ ] **Step 4: Router**

`api/app/savings/router.py`:

```python
"""A savings account's capitalization, rate history and balances copied from the bank. Each change recomputes
the owner's valuations from the affected day in the background."""
import datetime as dt

from fastapi import APIRouter, BackgroundTasks, Depends, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, sessionmaker

from app.db import get_session_factory
from app.errors import ApiError
from app.models import Account, SavingsAccount, SavingsBalance, SavingsRate
from app.savings.schemas import (
    SavingsAccountOut, SavingsBalanceIn, SavingsBalanceOut, SavingsRateIn, SavingsRateOut, SavingsSettingsIn,
)
from app.scoping import DbId, UserScope, get_scope, not_found
from app.valuation.service import local_today, mark_stale, recompute_in_background

router = APIRouter(prefix="/api/savings-accounts/{account_id}", tags=["savings"])
DUPLICATE = "Dla tego dnia jest już wpis."


def _account(scope: UserScope, account_id: int) -> Account:
    account = scope.get_account(account_id)
    if account.kind != "savings":
        raise ApiError(422, "wrong_account_kind", "Saldo i stawki wpisuje się na koncie typu „oszczędnościowe”.")
    return account


def _settings(scope: UserScope, account_id: int) -> SavingsAccount | None:
    return scope.db.scalar(select(SavingsAccount).where(SavingsAccount.account_id == _account(scope, account_id).id))


def _configured(scope: UserScope, account_id: int) -> SavingsAccount:
    settings = _settings(scope, account_id)
    if settings is None:
        raise ApiError(409, "savings_not_configured", "Najpierw ustaw kapitalizację konta.")
    return settings


def _out(scope: UserScope, settings: SavingsAccount) -> SavingsAccountOut:
    rates = scope.db.scalars(select(SavingsRate).where(SavingsRate.savings_account_id == settings.id)
                             .order_by(SavingsRate.valid_from))
    balances = scope.db.scalars(select(SavingsBalance).where(SavingsBalance.savings_account_id == settings.id)
                                .order_by(SavingsBalance.as_of_date))
    return SavingsAccountOut(
        account_id=settings.account_id, capitalization=settings.capitalization,
        rates=[SavingsRateOut.model_validate(rate) for rate in rates],
        balances=[SavingsBalanceOut.model_validate(balance) for balance in balances],
    )


def _saved(scope: UserScope, day: dt.date, background: BackgroundTasks, sessions: sessionmaker[Session]) -> None:
    try:
        scope.db.flush()
    except IntegrityError:  # (account, day) is unique for rates and balances
        scope.db.rollback()
        raise ApiError(409, "duplicate_date", DUPLICATE) from None
    mark_stale(scope.db, [scope.user.id], day)
    scope.db.commit()
    background.add_task(recompute_in_background, sessions, scope.user.id)


@router.get("", response_model=SavingsAccountOut)
def get_savings(account_id: DbId, scope: UserScope = Depends(get_scope)) -> SavingsAccountOut:
    settings = _settings(scope, account_id)
    if settings is None:
        raise not_found()
    return _out(scope, settings)


@router.put("", response_model=SavingsAccountOut)
def set_savings(
    account_id: DbId,
    body: SavingsSettingsIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsAccountOut:
    settings = _settings(scope, account_id)
    if settings is None:
        settings = SavingsAccount(account_id=account_id, capitalization=body.capitalization)
        scope.db.add(settings)
    settings.capitalization = body.capitalization
    _saved(scope, dt.date.min, background, sessions)  # the whole history follows the capitalization
    return _out(scope, settings)


@router.post("/rates", status_code=201, response_model=SavingsRateOut)
def add_rate(
    account_id: DbId,
    body: SavingsRateIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsRate:
    rate = SavingsRate(savings_account_id=_configured(scope, account_id).id, valid_from=body.valid_from,
                       annual_rate=body.annual_rate)
    scope.db.add(rate)
    _saved(scope, body.valid_from, background, sessions)
    return rate


@router.post("/balances", status_code=201, response_model=SavingsBalanceOut)
def add_balance(
    account_id: DbId,
    body: SavingsBalanceIn,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> SavingsBalance:
    settings = _configured(scope, account_id)
    if body.as_of_date > local_today():
        raise ApiError(422, "balance_in_future", "Saldo może być najpóźniej z dzisiaj.")
    balance = SavingsBalance(savings_account_id=settings.id, as_of_date=body.as_of_date, balance=body.balance)
    scope.db.add(balance)
    _saved(scope, body.as_of_date, background, sessions)
    return balance


@router.delete("/rates/{entry_id}", status_code=204)
def delete_rate(
    account_id: DbId,
    entry_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    settings = _configured(scope, account_id)
    rate = scope.db.scalar(select(SavingsRate).where(SavingsRate.id == entry_id,
                                                     SavingsRate.savings_account_id == settings.id))
    if rate is None:
        raise not_found()
    day = rate.valid_from
    scope.db.delete(rate)
    _saved(scope, day, background, sessions)
    return Response(status_code=204)


@router.delete("/balances/{entry_id}", status_code=204)
def delete_balance(
    account_id: DbId,
    entry_id: DbId,
    background: BackgroundTasks,
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> Response:
    settings = _configured(scope, account_id)
    balance = scope.db.scalar(select(SavingsBalance).where(SavingsBalance.id == entry_id,
                                                           SavingsBalance.savings_account_id == settings.id))
    if balance is None:
        raise not_found()
    day = balance.as_of_date
    scope.db.delete(balance)
    _saved(scope, day, background, sessions)
    return Response(status_code=204)
```

`api/app/main.py`: `from app.savings.router import router as savings_router` i `app.include_router(savings_router)` (po `bonds_router`).

- [ ] **Step 5: Uruchom testy**

Run: `docker compose run --rm api pytest tests/test_savings_api.py -q`
Expected: PASS (1 skipped — pozycje w Task 8).

- [ ] **Step 6: Commit**

```bash
git add api/app/savings/schemas.py api/app/savings/router.py api/app/main.py api/tests/test_savings_api.py
git commit -m "feat(savings): API for savings account capitalization, rates and balances

Co-Authored-By: <model> <noreply@anthropic.com>"
```

---

### Task 8: Pozycje obligacji i kont oszczędnościowych; README i mapa planów

**Files:**
- Modify: `api/app/valuation/fixed_income.py`, `api/app/portfolio/schemas.py`, `api/app/portfolio/service.py`, `api/tests/test_savings_api.py` (usunięcie `skip`), `api/tests/test_positions_api.py`, `README.md`, `docs/superpowers/plans/2026-09-26-00-roadmap.md`
- Test: `api/tests/test_positions_api.py`, `api/tests/test_fixed_income_rows.py`

**Interfaces:**
- Consumes: `bond_rows`, `savings_rows`, `Holding`, `SavingsInput` (Task 4); `load_fixed_income` (Task 5); `build_positions`, `percent`, `money` (`app/portfolio/service.py`).
- Produces:
  - `fixed_income.day_view(rows: list[Row], day) -> tuple[Row, Decimal] | None` — wiersz składnika z dnia `day` i jego zmiana dzienna (wartość − przepływ dnia − wartość z dnia poprzedniego); `None`, gdy tego dnia nie ma wiersza albo składnik ma ilość 0.
  - `PositionOut.kind` ∈ `"instrument" | "cash" | "bond" | "savings"`; nowe pola `bond_holding_id: int | None = None`, `savings_account_id: int | None = None`.
  - `/api/positions` (i `build_positions`): po instrumentach i gotówce — pozycje obligacji (per zakup, nazwa = seria, kategoria `bonds`) i kont oszczędnościowych (nazwa = nazwa konta, kategoria `savings`, ilość = saldo, koszt = wpłacony kapitał); udziały liczone ze wszystkich pozycji.

- [ ] **Step 1: Testy**

Dopisz do `api/tests/test_fixed_income_rows.py` (import `day_view`):

```python
def test_day_view_gives_the_row_and_its_change_net_of_the_days_flow() -> None:
    rows = bond_rows([_holding()], {}, dt.date(2026, 9, 25), SAT)

    row, change = day_view(rows, SAT)

    # 25 IX: 10 days → 100.15, tax 0.03 → 100.12 × 10 = 1001.20; 26 IX: 1001.30
    assert (row.value_pln, change) == (D("1001.30"), D("0.10"))
    assert day_view(bond_rows([_holding()], {}, BOUGHT, BOUGHT), BOUGHT)[1] == D("0.00")  # the purchase is a flow
    assert day_view(rows, dt.date(2026, 9, 27)) is None
```

Dopisz do `api/tests/test_positions_api.py`:

```python
def test_bonds_and_savings_accounts_are_positions(client: TestClient, login_as: LoginAs, engine: Engine) -> None:
    headers = login_as("carol@portfolio.dev")
    with Session(engine) as db:
        db.add(BondSeries(series="EDO0936", bond_type="EDO", issue_month=dt.date(2026, 9, 1), maturity_months=120,
                          first_period_rate=Decimal("5.35"), margin=Decimal("2.00"),
                          early_redemption_fee=Decimal("3.00"), interest_mode="capitalized", rate_basis="cpi"))
        db.commit()
    bonds = client.post("/api/accounts", json={"name": "Obligacje", "kind": "bonds"}, headers=headers).json()["id"]
    client.post("/api/bonds", json={"account_id": bonds, "bond_type": "EDO", "quantity": 10,
                                    "purchase_date": "2026-09-15"}, headers=headers)
    savings = client.post("/api/accounts", json={"name": "Konto", "kind": "savings"}, headers=headers).json()["id"]
    client.put(f"/api/savings-accounts/{savings}", json={"capitalization": "monthly"}, headers=headers)
    client.post(f"/api/savings-accounts/{savings}/balances", json={"as_of_date": "2026-09-01", "balance": "9000"},
                headers=headers)

    positions = client.get("/api/positions", params=ON, headers=headers).json()

    assert [(p["kind"], p["name"], p["category"], p["value_pln"], p["cost_pln"], p["unrealized_pln"],
             p["day_change_pln"], p["share_pct"]) for p in positions] == [
        ("bond", "EDO0936", "bonds", "1001.30", "1000.00", "1.30", "0.10", "10.01"),
        ("savings", "Konto", "savings", "9000.00", "9000.00", "0.00", "0.00", "89.99"),
    ]
    assert positions[0]["bond_holding_id"] is not None and positions[1]["savings_account_id"] is not None
```

(importy w `test_positions_api.py`: `BondSeries` z `app.models`; `login_as` jest fixture z `conftest.py` — dodaj parametr; `LoginAs` już zdefiniowany w pliku. Udziały: 1 001,30 / 10 001,30 = 10,01 %; 9 000 / 10 001,30 = 89,99 %.)

W `api/tests/test_savings_api.py` usuń `@pytest.mark.skip(...)` z `test_configured_account_with_rate_and_balance_earns_interest`.

- [ ] **Step 2: Uruchom testy — mają nie przejść**

Run: `docker compose run --rm api pytest tests/test_fixed_income_rows.py tests/test_positions_api.py tests/test_savings_api.py -q`
Expected: FAIL — brak `day_view`, brak pozycji `bond` / `savings`.

- [ ] **Step 3: `day_view`**

W `api/app/valuation/fixed_income.py`:

```python
def day_view(rows: Sequence[Row], day: dt.date) -> tuple[Row, Decimal] | None:
    """One component's row on `day` and its change since the day before (net of that day's deposit); None when the
    component has no row that day or has been paid out."""
    by_day = {row.day: row for row in rows}
    today = by_day.get(day)
    if today is None or today.quantity == 0:
        return None
    before = by_day.get(day - ONE_DAY)
    return today, today.value_pln - today.net_flow_pln - (before.value_pln if before else ZERO)
```

- [ ] **Step 4: Pozycje**

`api/app/portfolio/schemas.py`, `PositionOut`: `kind: Literal["instrument", "cash", "bond", "savings"]` oraz na końcu klasy `bond_holding_id: int | None = None`, `savings_account_id: int | None = None`.

`api/app/portfolio/service.py` (importy: `load_fixed_income` z `app.valuation.service`; `bond_rows`, `savings_rows`, `day_view` z `app.valuation.fixed_income`; `ONE_DAY` z `app.valuation.engine`; `BondHolding` z `app.models`):

```python
def _fixed_item(row: Row, change: Decimal, account: Account, kind: str, name: str) -> PositionOut:
    zero = money(ZERO)
    value, cost = money(row.value_pln), money(row.cost_pln)
    return PositionOut(
        kind=kind, account_id=account.id, account_name=account.name, instrument_id=None, ticker=None, name=name,
        category=BOND_KIND if kind == "bond" else SAVINGS_KIND, currency=account.currency,
        quantity=row.quantity or ZERO, price=None, price_date=None, price_source=None, value_pln=value, cost_pln=cost,
        unrealized_pln=value - cost, unrealized_pct=percent(value - cost, cost), price_effect_pln=value - cost,
        fx_effect_pln=zero, dividends_net_pln=zero, fees_pln=zero, realized_pln=zero, day_change_pln=money(change),
        flags=list(row.flags), bond_holding_id=row.bond_holding_id, savings_account_id=row.savings_account_id,
    )


def _fixed_items(scope: UserScope, accounts: dict[int, Account], day: dt.date, account_id: int | None) -> list[PositionOut]:
    """Bond purchases and savings accounts valued on `day` with the valuation's own rows."""
    fixed = load_fixed_income(scope)
    series = dict(scope.db.execute(scope.bond_holdings().with_only_columns(BondHolding.id, BondHolding.series)).all())
    items: list[PositionOut] = []
    for holding in fixed.holdings:
        view = day_view(bond_rows([holding], fixed.cpi, day - ONE_DAY, day), day)
        if view is not None and (account_id is None or holding.account_id == account_id):
            items.append(_fixed_item(*view, accounts[holding.account_id], "bond", series[holding.id]))
    for savings in fixed.savings:
        view = day_view(savings_rows([savings], day - ONE_DAY, day), day)
        if view is not None and (account_id is None or savings.account_id == account_id):
            account = accounts[savings.account_id]
            items.append(_fixed_item(*view, account, "savings", account.name))
    return items
```

W `build_positions` po pętli gotówki, przed liczeniem udziałów: `items += _fixed_items(scope, accounts, day, account_id)`.

(`Row` importuj z `app.valuation.engine`. Dla konta oszczędnościowego `row.quantity` to saldo; dla obligacji — liczba sztuk.)

- [ ] **Step 5: Uruchom testy**

Run: `docker compose run --rm api pytest -q`
Expected: PASS, jedno istniejące ostrzeżenie.

- [ ] **Step 6: README i mapa planów**

`README.md` — w tabeli API po wierszach `/api/corporate-actions` dopisz:

```markdown
| GET, POST | `/api/bond-series` | serie obligacji (wspólne): stawka 1. roku, marża, opłata; dopisanie serii spoza tabeli |
| GET, POST | `/api/bonds` | zakupy obligacji EDO (`date`): wartość netto, status; zakup `{account_id, bond_type, quantity, purchase_date}` (+ stawki dla nowej serii) |
| GET, PATCH, DELETE | `/api/bonds/{id}` | szczegóły (`date`): wartość 1 szt., wartość przy wykupie dziś, harmonogram okresów; `PATCH` — `redeemed_at`, `quantity`, `note` |
| GET, PUT | `/api/savings-accounts/{account_id}` | konto oszczędnościowe: kapitalizacja (`daily` / `monthly` / `quarterly`), stawki i salda |
| POST, DELETE | `/api/savings-accounts/{account_id}/rates`, `…/balances` | stawka w skali roku od dnia / saldo z banku na koniec dnia |
```

i w opisie `/api/positions` dopisz „obligacje i konta oszczędnościowe”.

`docs/superpowers/plans/2026-09-26-00-roadmap.md` — wiersz 5: kolumna „Wynik” → „EDO (inne rodzaje: kolejny plan), konta oszczędnościowe, API”, „Status” → `✅ zrobiony (`2026-09-28-05-bonds-savings.md`)`.

- [ ] **Step 7: Commit**

```bash
git add api/app/valuation/fixed_income.py api/app/portfolio/schemas.py api/app/portfolio/service.py \
  api/tests/test_fixed_income_rows.py api/tests/test_positions_api.py api/tests/test_savings_api.py README.md \
  docs/superpowers/plans/2026-09-26-00-roadmap.md
git commit -m "feat(portfolio): bond purchases and savings accounts in the positions list

Co-Authored-By: <model> <noreply@anthropic.com>"
```
