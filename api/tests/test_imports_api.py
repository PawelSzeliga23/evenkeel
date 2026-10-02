import io
import zipfile
from collections.abc import Callable
from datetime import datetime

from fastapi.testclient import TestClient
from sqlalchemy import Engine, func, select, update
from sqlalchemy.orm import Session

from app.models import Transaction
from tests import xtb_factory as xf

LoginAs = Callable[[str], dict[str, str]]
AT = datetime(2026, 3, 2, 9, 30)
IKE_NAME = xf.filename("IKE", "56216965")


def _ike() -> bytes:
    return xf.build_report(
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


def _files(*items: tuple[str, bytes]) -> list[tuple[str, tuple[str, bytes, str]]]:
    return [("files", (name, content, "application/octet-stream")) for name, content in items]


def test_preview_describes_import_without_writing(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    response = client.post("/api/imports/preview", files=_files((IKE_NAME, _ike())), headers=anna)

    assert response.status_code == 200
    (file,) = response.json()["files"]
    assert (file["account_number"], file["wrapper"], file["new_account"], file["account_id"]) == ("56216965", "ike", True, None)
    assert (file["new_transactions"], file["duplicate_transactions"], file["open_lots"]) == (2, 0, 1)
    assert file["import_id"] is None
    assert client.get("/api/accounts", headers=anna).json() == []
    assert client.get("/api/transactions", headers=anna).json() == []


def test_commit_two_copies_of_a_new_account_file_creates_only_one_account(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    response = client.post("/api/imports", files=_files((IKE_NAME, _ike()), (IKE_NAME, _ike())), headers=anna)

    assert response.status_code == 201
    assert len(client.get("/api/accounts", headers=anna).json()) == 1
    first, second = response.json()["files"]
    assert (first["new_account"], first["new_transactions"], first["duplicate_transactions"]) == (True, 2, 0)
    assert (second["new_account"], second["new_transactions"], second["duplicate_transactions"]) == (False, 0, 2)


def test_commit_two_periods_of_a_new_account_creates_only_one_account_and_reconciles(
    client: TestClient, login_as: LoginAs
) -> None:
    anna = login_as("anna@portfolio.dev")
    year1 = _ike()
    year2 = xf.build_report(
        cash=[
            xf.cash_row("IKE deposit", 5000.0, "1001", datetime(2026, 3, 1, 8, 0),
                        comment="Transfer in operation on account with id 56204082"),
            xf.buy_row("SXR8.DE", "2", "500.5", -4304.3, "1002", AT, "777"),
            xf.buy_row("SXR8.DE", "1", "505.0", -505.0, "1003", datetime(2026, 4, 1, 9, 0), "778"),
        ],
        open_rows=[
            xf.summary_row("SXR8.DE", "Core S&P 500", 3.0, 1530.0, 500.5, 19.0),
            xf.lot_row("SXR8.DE", "777", 2.0, 500.5, AT, 510.0, 1020.0, 19.0),
            xf.lot_row("SXR8.DE", "778", 1.0, 505.0, datetime(2026, 4, 1, 9, 0), 510.0, 510.0, 5.0),
        ],
        period_to=datetime(2026, 9, 26),
    )

    response = client.post("/api/imports", files=_files((IKE_NAME, year1), (IKE_NAME, year2)), headers=anna)

    assert response.status_code == 201
    assert len(client.get("/api/accounts", headers=anna).json()) == 1
    first, second = response.json()["files"]
    assert (first["new_transactions"], second["new_transactions"], second["duplicate_transactions"]) == (2, 1, 2)
    all_warning_codes = {w["code"] for f in (first, second) for w in f["warnings"]}
    assert "reconciliation_mismatch" not in all_warning_codes


def test_commit_newer_file_uploaded_first_still_reconciles(client: TestClient, login_as: LoginAs) -> None:
    """Same two-period scenario as above, but the newer (more complete) file is uploaded first:
    upload order must not affect whether the batch reconciles correctly."""
    anna = login_as("anna@portfolio.dev")
    older = xf.build_report(
        cash=[
            xf.cash_row("IKE deposit", 5000.0, "1001", datetime(2026, 3, 1, 8, 0),
                        comment="Transfer in operation on account with id 56204082"),
            xf.buy_row("SXR8.DE", "2", "500.5", -4304.3, "1002", AT, "777"),
        ],
        open_rows=[
            xf.summary_row("SXR8.DE", "Core S&P 500", 2.0, 1020.0, 500.5, 19.0),
            xf.lot_row("SXR8.DE", "777", 2.0, 500.5, AT, 510.0, 1020.0, 19.0),
        ],
        period_to=datetime(2026, 3, 5),
    )
    newer = xf.build_report(
        cash=[
            xf.cash_row("IKE deposit", 5000.0, "1001", datetime(2026, 3, 1, 8, 0),
                        comment="Transfer in operation on account with id 56204082"),
            xf.buy_row("SXR8.DE", "2", "500.5", -4304.3, "1002", AT, "777"),
            xf.buy_row("SXR8.DE", "1", "505.0", -505.0, "1003", datetime(2026, 4, 1, 9, 0), "778"),
        ],
        open_rows=[
            xf.summary_row("SXR8.DE", "Core S&P 500", 3.0, 1530.0, 500.5, 19.0),
            xf.lot_row("SXR8.DE", "777", 2.0, 500.5, AT, 510.0, 1020.0, 19.0),
            xf.lot_row("SXR8.DE", "778", 1.0, 505.0, datetime(2026, 4, 1, 9, 0), 510.0, 510.0, 5.0),
        ],
        period_to=datetime(2026, 9, 26),
    )

    response = client.post("/api/imports", files=_files((IKE_NAME, newer), (IKE_NAME, older)), headers=anna)

    assert response.status_code == 201
    assert len(client.get("/api/accounts", headers=anna).json()) == 1
    first, second = response.json()["files"]
    all_warning_codes = {w["code"] for f in (first, second) for w in f["warnings"]}
    assert "reconciliation_mismatch" not in all_warning_codes


def test_commit_writes_and_second_commit_only_finds_duplicates(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    first = client.post("/api/imports", files=_files((IKE_NAME, _ike())), headers=anna)
    second = client.post("/api/imports", files=_files((IKE_NAME, _ike())), headers=anna)

    assert first.status_code == 201
    created = first.json()["files"][0]
    assert (created["new_account"], created["new_transactions"], created["account_name"]) == (True, 2, "XTB IKE")
    assert created["import_id"] is not None
    again = second.json()["files"][0]
    assert (again["new_account"], again["new_transactions"], again["duplicate_transactions"]) == (False, 0, 2)
    assert len(client.get("/api/transactions", headers=anna).json()) == 2
    assert len(client.get("/api/imports", headers=anna).json()) == 2


def test_transactions_are_listed_newest_first_with_exact_amounts(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    client.post("/api/imports", files=_files((IKE_NAME, _ike())), headers=anna)

    listing = client.get("/api/transactions", headers=anna).json()

    buy, deposit = listing
    assert (buy["type"], buy["ticker"], buy["amount"], buy["quantity"]) == ("buy", "SXR8.DE", "-4304.3000", "2.00000000")
    assert deposit["type"] == "transfer_in"
    only_buys = client.get("/api/transactions", params={"type": "buy"}, headers=anna).json()
    assert [t["external_id"] for t in only_buys] == ["1002"]


def test_zip_upload_is_expanded(client: TestClient, login_as: LoginAs) -> None:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr(f"xtb/{IKE_NAME}", _ike())
        archive.writestr("xtb/opis.txt", "x")

    response = client.post("/api/imports/preview", files=_files(("xtb.zip", buffer.getvalue())),
                           headers=login_as("anna@portfolio.dev"))

    body = response.json()
    assert [f["filename"] for f in body["files"]] == [IKE_NAME]
    assert body["skipped"] == ["opis.txt"]


def test_broken_file_blocks_the_whole_commit(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")

    preview = client.post("/api/imports/preview", files=_files((IKE_NAME, _ike()), ("zly.xlsx", b"smieci")), headers=anna)
    commit = client.post("/api/imports", files=_files((IKE_NAME, _ike()), ("zly.xlsx", b"smieci")), headers=anna)

    assert preview.status_code == 200
    assert preview.json()["errors"] == [{"filename": "zly.xlsx", "code": "not_xlsx", "message": "Plik nie jest poprawnym plikiem XLSX."}]
    assert commit.status_code == 422
    assert commit.json()["code"] == "import_invalid_files"
    assert client.get("/api/accounts", headers=anna).json() == []


def test_corrupted_xlsx_is_reported_and_blocks_the_commit(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    corrupted = xf.corrupt_worksheet_xml(_ike())

    preview = client.post("/api/imports/preview", files=_files((IKE_NAME, corrupted)), headers=anna)
    commit = client.post("/api/imports", files=_files((IKE_NAME, corrupted)), headers=anna)

    assert preview.status_code == 200
    assert preview.json()["errors"] == [
        {"filename": IKE_NAME, "code": "not_xlsx", "message": "Plik nie jest poprawnym plikiem XLSX."}
    ]
    assert commit.status_code == 422
    assert commit.json()["code"] == "import_invalid_files"
    assert client.get("/api/accounts", headers=anna).json() == []


def test_commit_without_xlsx_files_is_rejected(client: TestClient, login_as: LoginAs) -> None:
    response = client.post("/api/imports", files=_files(("notatki.txt", b"x")), headers=login_as("anna@portfolio.dev"))

    assert response.status_code == 422
    assert response.json()["code"] == "import_empty"


def test_imports_require_authentication(client: TestClient) -> None:
    assert client.post("/api/imports/preview", files=_files((IKE_NAME, _ike()))).status_code == 401


def test_other_user_sees_nothing_and_gets_own_account(client: TestClient, login_as: LoginAs) -> None:
    anna = login_as("anna@portfolio.dev")
    bartek = login_as("bartek@portfolio.dev")
    client.post("/api/imports", files=_files((IKE_NAME, _ike())), headers=anna)
    anna_account = client.get("/api/accounts", headers=anna).json()[0]["id"]

    assert client.get("/api/transactions", headers=bartek).json() == []
    assert client.get("/api/imports", headers=bartek).json() == []
    assert client.get("/api/transactions", params={"account_id": anna_account}, headers=bartek).status_code == 404
    preview = client.post("/api/imports/preview", files=_files((IKE_NAME, _ike())), headers=bartek).json()
    assert (preview["files"][0]["new_account"], preview["files"][0]["duplicate_transactions"]) == (True, 0)


def test_a_reimport_that_only_fixes_stored_operations_can_be_saved(
    client: TestClient, login_as: LoginAs, engine: Engine,
) -> None:
    anna = login_as("anna@portfolio.dev")
    client.post("/api/imports", files=_files((IKE_NAME, _ike())), headers=anna)
    with Session(engine) as db:  # what an older importer left behind
        db.execute(update(Transaction).where(Transaction.type == "buy").values(type="unknown", quantity=None, price=None))
        db.commit()

    (preview,) = client.post("/api/imports/preview", files=_files((IKE_NAME, _ike())), headers=anna).json()["files"]
    assert (preview["new_transactions"], preview["reclassified_transactions"]) == (0, 1)
    (saved,) = client.post("/api/imports", files=_files((IKE_NAME, _ike())), headers=anna).json()["files"]

    assert saved["reclassified_transactions"] == 1
    with Session(engine) as db:
        assert db.scalar(select(func.count()).select_from(Transaction).where(Transaction.type == "unknown")) == 0
