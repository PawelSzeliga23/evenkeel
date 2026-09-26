from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class ImportWarningOut(BaseModel):
    code: str
    message: str
    details: dict[str, Any] = {}


class ImportFileOut(BaseModel):
    filename: str
    account_number: str
    wrapper: str
    currency: str
    account_id: int | None
    account_name: str
    new_account: bool
    report_from: datetime | None
    report_to: datetime | None
    new_transactions: int
    duplicate_transactions: int
    unknown_transactions: int
    open_lots: int
    closed_lots: int
    warnings: list[ImportWarningOut]
    import_id: int | None = None


class ImportFileErrorOut(BaseModel):
    filename: str
    code: str
    message: str


class ImportResultOut(BaseModel):
    files: list[ImportFileOut]
    errors: list[ImportFileErrorOut]
    skipped: list[str]


class ImportOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    account_id: int
    filename: str
    imported_at: datetime
    report_from: datetime | None
    report_to: datetime | None
    rows_added: int
    rows_duplicate: int
    rows_unknown: int
    warnings: list[ImportWarningOut]
