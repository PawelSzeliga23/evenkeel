"""Portfolio backup (plan 8c): download the user's whole portfolio, check a file, restore it in place of everything."""
import datetime as dt

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session, sessionmaker

from app.backup.export import export_user
from app.backup.restore import counts, read_backup, restore
from app.db import get_session_factory
from app.errors import ApiError
from app.scoping import UserScope, get_scope
from app.valuation.service import recompute_in_background

router = APIRouter(prefix="/api/backup", tags=["backup"])

MAX_BYTES = 20 * 1024 * 1024
CONFIRM = "ZASTĄP"


class BackupCounts(BaseModel):
    accounts: int
    transactions: int
    bond_holdings: int
    savings_accounts: int
    tags: int
    notes: int
    scenarios: int
    ai_reviews: int


class BackupSummaryOut(BaseModel):
    exported_at: str
    app_version: str
    counts: BackupCounts


def _content(file: UploadFile) -> bytes:
    content = file.file.read(MAX_BYTES + 1)
    if len(content) > MAX_BYTES:
        raise ApiError(413, "file_too_large", "Plik jest za duży (maks. 20 MB).")
    return content


@router.get("")
def download_backup(scope: UserScope = Depends(get_scope)) -> JSONResponse:
    name = f"evenkeel-kopia-{dt.date.today().isoformat()}.json"
    return JSONResponse(export_user(scope.db, scope.user),
                        headers={"Content-Disposition": f'attachment; filename="{name}"'})


@router.post("/check", response_model=BackupSummaryOut)
def check_backup(file: UploadFile = File(...), scope: UserScope = Depends(get_scope)) -> BackupSummaryOut:
    backup = read_backup(_content(file))
    return BackupSummaryOut(exported_at=backup.exported_at, app_version=backup.app_version,
                            counts=BackupCounts(**counts(backup)))


@router.post("/restore", response_model=BackupSummaryOut)
def restore_backup(
    background: BackgroundTasks,
    file: UploadFile = File(...),
    confirm: str = Form(""),
    scope: UserScope = Depends(get_scope),
    sessions: sessionmaker[Session] = Depends(get_session_factory),
) -> BackupSummaryOut:
    if confirm.strip() != CONFIRM:
        raise ApiError(422, "confirm_required", f"Wpisz {CONFIRM}, żeby wczytać kopię.")
    backup = read_backup(_content(file))
    restore(scope.db, scope.user, backup)
    background.add_task(recompute_in_background, sessions, scope.user.id)
    return BackupSummaryOut(exported_at=backup.exported_at, app_version=backup.app_version,
                            counts=BackupCounts(**counts(backup)))
