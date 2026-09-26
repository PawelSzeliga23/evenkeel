import io
import zipfile
from dataclasses import dataclass
from typing import Any

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

SUMMARY_LABELS = frozenset({"Total", "Profit/loss"})
HEADER_SEARCH_ROWS = 40


class XtbFormatError(Exception):
    """A file that cannot be read as an XTB export; the message is user-facing Polish."""

    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass(frozen=True)
class Sheet:
    title: str
    metadata: dict[str, Any]
    pre_rows: list[tuple[Any, ...]]
    rows: list[dict[str, Any]]


def clean(value: Any) -> Any:
    if isinstance(value, str):
        return value.strip() or None
    return value


def open_workbook(content: bytes) -> dict[str, list[tuple[Any, ...]]]:
    try:
        workbook = load_workbook(io.BytesIO(content), data_only=True)
    except (InvalidFileException, zipfile.BadZipFile, KeyError, ValueError, OSError) as exc:
        raise XtbFormatError("not_xlsx", "Plik nie jest poprawnym plikiem XLSX.") from exc
    return {
        sheet.title: [tuple(clean(cell) for cell in row) for row in sheet.iter_rows(values_only=True)]
        for sheet in workbook.worksheets
    }


def read_sheet(title: str, rows: list[tuple[Any, ...]], required_columns: frozenset[str]) -> Sheet:
    header_index = next(
        (
            index
            for index, row in enumerate(rows[:HEADER_SEARCH_ROWS])
            if required_columns <= {cell for cell in row if isinstance(cell, str)}
        ),
        None,
    )
    if header_index is None:
        raise XtbFormatError(
            "missing_columns",
            f"Zakładka „{title}” nie ma oczekiwanych kolumn: {', '.join(sorted(required_columns))}.",
        )
    header = [cell if isinstance(cell, str) else None for cell in rows[header_index]]
    pre_rows = rows[:header_index]
    metadata = {row[0]: (row[1] if len(row) > 1 else None) for row in pre_rows if row and isinstance(row[0], str)}
    data = []
    for row in rows[header_index + 1:]:
        if all(cell is None for cell in row) or row[0] in SUMMARY_LABELS:
            continue
        data.append({name: (row[i] if i < len(row) else None) for i, name in enumerate(header) if name})
    return Sheet(title, metadata, pre_rows, data)
