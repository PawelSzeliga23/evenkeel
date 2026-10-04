"""Plan 8c: a backup holds the whole portfolio of one user and restores it in place of everything."""
import datetime as dt
import json
from collections.abc import Callable
from decimal import Decimal
from typing import Any

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select
from sqlalchemy.orm import Session

from app.backup.tables import NOT_BACKED_UP, SHARED_KEYS, TABLES
from app.models import (
    Account,
    AiReview,
    BondHolding,
    CatalogAddition,
    BondSeries,
    CorporateAction,
    ImportRecord,
    Instrument,
    JournalEntry,
    PositionLot,
    SavingsAccount,
    SavingsBalance,
    SavingsFlow,
    SavingsRate,
    Scenario,
    Tag,
    TagLink,
    Thesis,
    Transaction,
    User,
    XtbSnapshot,
)
from app.models.base import Base

LoginAs = Callable[[str], dict[str, str]]
AT = dt.datetime(2026, 3, 2, 9, 30, tzinfo=dt.UTC)


def _user_id(engine: Engine, email: str) -> int:
    with Session(engine) as db:
        return db.scalar(select(User.id).where(User.email == email))  # type: ignore[return-value]


def seed(engine: Engine, email: str, ticker: str = "CDR.PL") -> None:
    """One row of every kind the backup holds, with links between them."""
    user_id = _user_id(engine, email)
    with Session(engine) as db:
        instrument = db.scalar(select(Instrument).where(Instrument.xtb_ticker == ticker))
        if instrument is None:
            instrument = Instrument(xtb_ticker=ticker, name="CD Projekt", currency="PLN", spread_pct=Decimal("0.1"),
                                    in_catalog=True, catalog_group="Dodane przez Ciebie")
            db.add(instrument)
        if db.get(BondSeries, "EDO0936") is None:
            db.add(BondSeries(series="EDO0936", bond_type="EDO", issue_month=dt.date(2026, 9, 1), maturity_months=120,
                              first_period_rate=Decimal("5.35"), margin=Decimal("2"),
                              early_redemption_fee=Decimal("3"), interest_mode="capitalized", rate_basis="cpi"))
        ike = Account(user_id=user_id, name="XTB IKE", kind="broker", wrapper="ike", broker="xtb",
                      external_account_number="123")
        cash = Account(user_id=user_id, name="Gotówka", kind="cash")
        bonds = Account(user_id=user_id, name="Obligacje", kind="bonds")
        bank = Account(user_id=user_id, name="Bank", kind="savings")
        db.add_all([ike, cash, bonds, bank])
        db.flush()
        record = ImportRecord(user_id=user_id, account_id=ike.id, filename="ike.xlsx", file_hash="a" * 64,
                              rows_added=2, rows_duplicate=0, rows_unknown=0, warnings=[{"code": "x"}])
        db.add(record)
        db.flush()

        def tx(account: Account, ext: str, type_: str, amount: str, **fields: Any) -> Transaction:
            return Transaction(account_id=account.id, type=type_, xtb_type=type_, occurred_at=AT,
                               amount=Decimal(amount), currency="PLN", external_id=ext, comment="", raw={"r": ext},
                               **fields)

        buy = tx(ike, "1", "buy", "-500.1234", instrument_id=instrument.id, quantity=Decimal("2"),
                 price=Decimal("250.0617"), xtb_position_id="77", import_id=record.id)
        out = tx(cash, "2", "transfer_out", "-100")
        into = tx(ike, "3", "transfer_in", "100")
        db.add_all([buy, out, into])
        db.flush()
        out.transfer_pair_id, into.transfer_pair_id = into.id, out.id
        db.add_all([
            PositionLot(account_id=ike.id, instrument_id=instrument.id, xtb_position_id="77", side="buy",
                        quantity=Decimal("2"), open_price=Decimal("250.0617"), opened_at=AT, raw={}),
            XtbSnapshot(import_id=record.id, account_id=ike.id, instrument_id=instrument.id, row_kind="lot",
                        volume=Decimal("2"), taken_at=AT, raw={}),
            BondHolding(account_id=bonds.id, bond_type="EDO", series="EDO0936", quantity=10,
                        purchase_date=dt.date(2026, 9, 3)),
        ])
        savings = SavingsAccount(account_id=bank.id, capitalization="monthly")
        db.add(savings)
        db.flush()
        db.add_all([
            SavingsRate(savings_account_id=savings.id, valid_from=dt.date(2026, 1, 1), annual_rate=Decimal("5")),
            SavingsBalance(savings_account_id=savings.id, as_of_date=dt.date(2026, 1, 1), balance=Decimal("1000")),
            SavingsFlow(savings_account_id=savings.id, date=dt.date(2026, 2, 1), amount=Decimal("250")),
        ])
        tag = Tag(user_id=user_id, name="emerytura", color="#F0A43A")
        db.add(tag)
        db.flush()
        db.add_all([
            TagLink(tag_id=tag.id, instrument_id=instrument.id),
            TagLink(tag_id=tag.id, instrument_id=instrument.id, account_id=ike.id),
            TagLink(tag_id=tag.id, bond_series="EDO0936"),
            TagLink(tag_id=tag.id, account_id=bank.id),
            Thesis(user_id=user_id, instrument_id=instrument.id, body="Teza"),
            JournalEntry(user_id=user_id, entry_date=dt.date(2026, 3, 2), body="Wpis", account_id=bank.id),
            JournalEntry(user_id=user_id, entry_date=dt.date(2026, 3, 3), body="O portfelu"),
            Scenario(user_id=user_id, name="Inaczej", base="portfolio",
                     allocation=[{"target": {"instrument_id": instrument.id}, "share_pct": "100"}],
                     steps=[{"kind": "recurring", "amount_pln": "100", "day_of_month": 1, "start": "2026-01",
                             "target": {"bond": "EDO"}, "ike": False}]),
            CatalogAddition(user_id=user_id, instrument_id=instrument.id),
            AiReview(user_id=user_id, account_ids=[ike.id], account_label="XTB IKE", content="# Przegląd",
                     sections=1),
            CorporateAction(instrument_id=instrument.id, type="split", effective_date=dt.date(2026, 2, 1),
                            ratio_from=Decimal("1"), ratio_to=Decimal("10"), source="manual", user_id=user_id),
        ])
        db.get(User, user_id).preferences = {"start_screen": "analysis", "accounts_fixed": [ike.id]}  # type: ignore[union-attr]
        db.commit()


def _numbered(backup: dict[str, Any]) -> str:
    """The backup with `exported_at` dropped: equal for the same data on another account, whatever the ids."""
    return json.dumps({k: v for k, v in backup.items() if k != "exported_at"}, sort_keys=True)


def _upload(client: TestClient, headers: dict[str, str], path: str, content: bytes, confirm: str | None = None):
    data = {"confirm": confirm} if confirm is not None else None
    return client.post(path, headers=headers, files={"file": ("kopia.json", content, "application/json")}, data=data)


def _renumber(backup: dict[str, Any]) -> dict[str, Any]:
    """Ids of each table replaced by 1, 2, … in file order, links and JSON ids following."""
    from app.backup import json_ids
    from app.backup.tables import BY_NAME

    data = json.loads(json.dumps(backup["data"]))
    maps: dict[str, dict[Any, Any]] = {}
    for name in ["instruments", *[spec.name for spec in TABLES]]:
        maps[name] = {row["id"]: n for n, row in enumerate(data[name], start=1)}
    maps["bond_series"] = {s["series"]: s["series"] for s in data["bond_series"]}
    for name in ["instruments", *[spec.name for spec in TABLES]]:
        refs = BY_NAME[name].refs if name in BY_NAME else {}
        for row in data[name]:
            row["id"] = maps[name][row["id"]]
            for column, table in refs.items():
                if row.get(column) is not None:
                    row[column] = maps[table][row[column]]
            if name in json_ids.ROWS:
                json_ids.ROWS[name](row, lambda table, value: maps[table][value])
    json_ids.preferences(data["user"]["preferences"], lambda table, value: maps[table][value])
    return {**backup, "data": data}


def test_every_table_is_in_the_backup_or_left_out_on_purpose() -> None:
    covered = {spec.model.__tablename__ for spec in TABLES} | set(SHARED_KEYS) | NOT_BACKED_UP
    assert set(Base.metadata.tables) - covered == set()


def test_the_backup_holds_every_row_of_the_user_and_nothing_else(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    anna, ben = login_as("anna@portfolio.dev"), login_as("ben@portfolio.dev")
    seed(engine, "anna@portfolio.dev")
    seed(engine, "ben@portfolio.dev")

    response = client.get("/api/backup", headers=anna)

    assert response.status_code == 200, response.text
    assert response.headers["content-disposition"].startswith('attachment; filename="evenkeel-kopia-')
    backup = response.json()
    assert (backup["format"], backup["version"]) == ("evenkeel-backup", 1)
    sizes = {name: len(rows) for name, rows in backup["data"].items() if isinstance(rows, list)}
    assert sizes == {"accounts": 4, "imports": 1, "transactions": 3, "position_lots": 1, "xtb_snapshots": 1,
                     "bond_holdings": 1, "savings_accounts": 1, "savings_rates": 1, "savings_balances": 1,
                     "savings_flows": 1, "tags": 1, "tag_links": 4, "theses": 1, "journal_entries": 2,
                     "scenarios": 1, "ai_reviews": 1, "catalog_additions": 1, "corporate_actions": 1, "instruments": 1,
                     "bond_series": 1}
    buy = backup["data"]["transactions"][0]
    assert buy["amount"] == "-500.1234" and "user_id" not in backup["data"]["accounts"][0]
    assert "price_checked_at" not in backup["data"]["instruments"][0]
    assert backup["data"]["user"]["preferences"]["start_screen"] == "analysis"
    assert client.get("/api/backup", headers=ben).json()["data"]["accounts"][0]["id"] != \
        backup["data"]["accounts"][0]["id"]


def test_a_backup_restored_on_another_account_gives_the_same_backup(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    anna, ben = login_as("anna@portfolio.dev"), login_as("ben@portfolio.dev")
    seed(engine, "anna@portfolio.dev")
    seed(engine, "ben@portfolio.dev", ticker="PKO.PL")  # Ben's own data, to be replaced
    original = client.get("/api/backup", headers=anna).json()

    restored = _upload(client, ben, "/api/backup/restore", json.dumps(original).encode(), "ZASTĄP")

    assert restored.status_code == 200, restored.text
    assert restored.json()["counts"] == {"accounts": 4, "transactions": 3, "bond_holdings": 1, "savings_accounts": 1,
                                         "tags": 1, "notes": 3, "scenarios": 1, "ai_reviews": 1}
    again = client.get("/api/backup", headers=ben).json()
    assert _numbered(_renumber(again)) == _numbered(_renumber(original))
    with Session(engine) as db:
        ben_id = _user_id(engine, "ben@portfolio.dev")
        # marked stale from the start, then recomputed by the background task the test client runs at once
        assert db.get(User, ben_id).valuations_stale_from is None  # type: ignore[union-attr]
        names = set(db.scalars(select(Account.name).where(Account.user_id == ben_id)))
        assert names == {"XTB IKE", "Gotówka", "Obligacje", "Bank"}
        pkos = db.scalar(select(func.count()).select_from(Transaction).join(Instrument)
                         .where(Instrument.xtb_ticker == "PKO.PL"))
        assert pkos == 0  # Ben's old transactions are gone
    assert client.get("/api/backup", headers=anna).json()["data"] == original["data"]  # Anna untouched


def test_restoring_on_a_new_server_creates_the_missing_instruments(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    anna = login_as("anna@portfolio.dev")
    seed(engine, "anna@portfolio.dev")
    backup = client.get("/api/backup", headers=anna).json()
    backup["data"]["instruments"][0]["xtb_ticker"] = "NEW.US"

    response = _upload(client, anna, "/api/backup/restore", json.dumps(backup).encode(), "ZASTĄP")

    assert response.status_code == 200, response.text
    with Session(engine) as db:
        new = db.scalar(select(Instrument).where(Instrument.xtb_ticker == "NEW.US"))
        assert new is not None and new.price_checked_at is None and new.spread_pct == Decimal("0.1000")


def test_check_tells_what_is_in_the_file_and_changes_nothing(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    anna = login_as("anna@portfolio.dev")
    seed(engine, "anna@portfolio.dev")
    content = client.get("/api/backup", headers=anna).content

    response = _upload(client, anna, "/api/backup/check", content)

    assert response.status_code == 200, response.text
    assert response.json()["counts"]["transactions"] == 3 and response.json()["app_version"]


def _rejected(client: TestClient, headers: dict[str, str], content: bytes, confirm: str = "ZASTĄP") -> tuple[int, str]:
    response = _upload(client, headers, "/api/backup/restore", content, confirm)
    return response.status_code, response.json()["message"]


def test_bad_files_are_refused_and_the_old_data_stays(client: TestClient, login_as: LoginAs, engine: Engine) -> None:
    anna = login_as("anna@portfolio.dev")
    seed(engine, "anna@portfolio.dev")
    good = client.get("/api/backup", headers=anna).json()

    def changed(edit: Callable[[dict[str, Any]], None]) -> bytes:
        copy = json.loads(json.dumps(good))
        edit(copy)
        return json.dumps(copy).encode()

    assert _rejected(client, anna, b"nie json") == (422, "To nie jest plik kopii Evenkeel.")
    assert _rejected(client, anna, changed(lambda b: b.update(format="inny"))) == (
        422, "To nie jest plik kopii Evenkeel.")
    assert _rejected(client, anna, changed(lambda b: b.update(version=2))) == (
        422, "Kopia pochodzi z nowszej wersji Evenkeel. Zaktualizuj aplikację.")
    status, message = _rejected(client, anna, changed(lambda b: b["data"]["accounts"][0].update(kolor="x")))
    assert status == 422 and "nieznana kolumna kolor w tabeli accounts" in message
    status, message = _rejected(client, anna, changed(lambda b: b["data"]["transactions"][0].update(account_id=999)))
    assert status == 422 and "odwołanie do accounts 999" in message
    status, message = _rejected(client, anna, changed(lambda b: b["data"]["transactions"][0].update(amount="dużo")))
    assert status == 422 and "zła wartość amount w tabeli transactions" in message
    status, message = _rejected(client, anna, changed(lambda b: b["data"]["accounts"][0].update(kind="konto")))
    assert status == 422 and message.startswith("Plik kopii jest uszkodzony:")  # refused by the database
    assert _rejected(client, anna, json.dumps(good).encode(), confirm="tak") == (
        422, "Wpisz ZASTĄP, żeby wczytać kopię.")
    big = _upload(client, anna, "/api/backup/restore", b" " * (20 * 1024 * 1024 + 1), "ZASTĄP")
    assert big.status_code == 413

    assert client.get("/api/backup", headers=anna).json()["data"] == good["data"]


def test_a_backup_cannot_put_an_instrument_on_everyones_starter_list(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    anna, ben = login_as("anna@portfolio.dev"), login_as("ben@portfolio.dev")
    seed(engine, "anna@portfolio.dev")
    backup = client.get("/api/backup", headers=anna).json()
    backup["data"]["instruments"][0].update(xtb_ticker="FAKE.US", in_catalog=True, catalog_group="ETF: USA",
                                            catalog_seeded=True)
    backup["data"]["catalog_additions"] = []

    assert _upload(client, ben, "/api/backup/restore", json.dumps(backup).encode(), "ZASTĄP").status_code == 200
    with Session(engine) as db:
        fake = db.scalar(select(Instrument).where(Instrument.xtb_ticker == "FAKE.US"))
        assert (fake.in_catalog, fake.catalog_group, fake.catalog_seeded) == (False, None, False)
