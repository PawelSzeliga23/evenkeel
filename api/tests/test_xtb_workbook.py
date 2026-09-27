import io
import time
import zipfile
from datetime import datetime

import pytest
from openpyxl import Workbook

from app.xtb.workbook import XtbFormatError, open_workbook, read_sheet
from tests import xtb_factory as xf

CASH_REQUIRED = frozenset({"Type", "Time", "Amount", "ID", "Comment"})
OPEN_REQUIRED = frozenset({"Instrument/Position", "Ticker", "Type", "Volume", "Open price"})


def _cash_rows() -> list[dict]:
    return [
        xf.cash_row("Deposit", 500.0, "1001", datetime(2026, 3, 1, 8, 0), comment="BLIK deposit"),
        xf.cash_row("Deposit", 250.0, "1002", datetime(2026, 3, 5, 8, 0), comment="PAYU deposit"),
    ]


def test_open_workbook_lists_sheets_with_cleaned_cells() -> None:
    sheets = open_workbook(xf.build_report(cash=_cash_rows()))

    assert set(sheets) == {"Closed Positions", "Cash Operations", "Open Positions"}
    assert sheets["Cash Operations"][1][:2] == ("Cash Operations", None)  # "" became None


def test_read_sheet_finds_header_skips_total_and_reads_metadata() -> None:
    sheets = open_workbook(xf.build_report(cash=_cash_rows()))

    sheet = read_sheet("Cash Operations", sheets["Cash Operations"], CASH_REQUIRED)

    assert sheet.metadata["Account number"] == "56216965"
    assert sheet.metadata["Date from (UTC)"] == xf.PERIOD_FROM
    assert [row["ID"] for row in sheet.rows] == ["1001", "1002"]  # "Total" row skipped
    assert sheet.rows[0]["Comment"] == "BLIK deposit"
    assert sheet.rows[0]["Ticker"] is None


def test_read_sheet_ignores_summary_table_that_looks_like_a_header() -> None:
    rows = [xf.lot_row("SXR8.DE", "777", 2.0, 500.5, datetime(2026, 3, 2, 9, 30), 510.0, 1020.0, 19.0)]
    sheets = open_workbook(xf.build_report(open_rows=rows))

    sheet = read_sheet("Open Positions", sheets["Open Positions"], OPEN_REQUIRED)

    assert [row["Instrument/Position"] for row in sheet.rows] == ["777"]
    assert ("Product", "Metric", "Amount", "Currency") == sheet.pre_rows[3][:4]


def test_read_sheet_skips_blank_rows_between_data() -> None:
    rows = [("Type", "Time", "Amount", "ID", "Comment"), ("Deposit", None, 1.0, "1", None), (None, None), ("Deposit", None, 2.0, "2", None)]

    sheet = read_sheet("Cash Operations", rows, CASH_REQUIRED)

    assert [row["ID"] for row in sheet.rows] == ["1", "2"]


def test_read_sheet_without_required_columns_fails() -> None:
    with pytest.raises(XtbFormatError) as exc_info:
        read_sheet("Cash Operations", [("Foo", "Bar"), ("1", "2")], CASH_REQUIRED)

    assert exc_info.value.code == "missing_columns"


def test_garbage_bytes_are_not_xlsx() -> None:
    with pytest.raises(XtbFormatError) as exc_info:
        open_workbook(b"to nie jest plik excela")

    assert exc_info.value.code == "not_xlsx"


def test_zip_with_unsupported_declared_version_is_not_xlsx() -> None:
    """zipfile.ZipFile raises NotImplementedError (not BadZipFile) for a central directory entry
    declaring a "version needed to extract" above what the stdlib supports; this must not 500."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        archive.writestr("a.txt", b"hello")
    data = bytearray(buffer.getvalue())
    idx = data.index(b"PK\x01\x02")
    data[idx + 6] = 200  # "version needed to extract" byte, way above zipfile.MAX_EXTRACT_VERSION

    with pytest.raises(XtbFormatError) as exc_info:
        open_workbook(bytes(data))

    assert exc_info.value.code == "not_xlsx"


def test_corrupted_worksheet_xml_is_not_xlsx() -> None:
    content = xf.corrupt_worksheet_xml(xf.build_report(cash=_cash_rows()))

    with pytest.raises(XtbFormatError) as exc_info:
        open_workbook(content)

    assert exc_info.value.code == "not_xlsx"


def test_stale_worksheet_dimension_does_not_drop_rows() -> None:
    """Some real XTB exports declare a <dimension ref> that undershoots the sheet's actual rows;
    openpyxl's read-only iter_rows trusts it and stops there unless dimensions are reset."""
    rows = [xf.cash_row("Deposit", 1.0, str(i), datetime(2026, 3, 1, 8, 0)) for i in range(35)]
    content = xf.stale_worksheet_dimensions(
        xf.build_report(cash=rows, include_open=False, include_closed=False)
    )

    sheets = open_workbook(content)
    sheet = read_sheet("Cash Operations", sheets["Cash Operations"], CASH_REQUIRED)

    assert len(sheet.rows) == 35


def test_far_out_of_range_cell_does_not_cause_a_huge_scan() -> None:
    """A tiny workbook with one cell at XFD200000 must not force a scan of ~3.3 billion cells."""
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Cash Operations"
    sheet["A1"] = "Account number"
    sheet["B1"] = "1"
    sheet["XFD200000"] = "boom"
    buffer = io.BytesIO()
    workbook.save(buffer)

    started = time.monotonic()
    sheets = open_workbook(buffer.getvalue())
    elapsed = time.monotonic() - started

    assert elapsed < 5
    assert all(len(row) <= 40 for row in sheets["Cash Operations"])
    assert len(sheets["Cash Operations"]) < 1000
