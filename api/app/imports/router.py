from collections.abc import Sequence

from fastapi import APIRouter, Depends, File, UploadFile

from app.errors import ApiError
from app.imports.schemas import ImportFileOut, ImportOut, ImportResultOut
from app.imports.service import FilePlan, apply_import, plan_import
from app.models import ImportRecord
from app.scoping import UserScope, get_scope
from app.xtb.archive import UploadedFile, expand_uploads
from app.xtb.report import XtbReport, parse_report
from app.xtb.workbook import XtbFormatError

router = APIRouter(prefix="/api/imports", tags=["imports"])

MAX_UPLOAD_BYTES = 20 * 1024 * 1024


def _read_uploads(files: list[UploadFile]) -> list[UploadedFile]:
    uploads = []
    for file in files:
        content = file.file.read(MAX_UPLOAD_BYTES + 1)
        name = file.filename or "plik"
        if len(content) > MAX_UPLOAD_BYTES:
            raise ApiError(413, "file_too_large", f"Plik {name} jest za duży (maks. 20 MB).")
        uploads.append(UploadedFile(name, content))
    return uploads


def _parse(files: list[UploadFile]) -> tuple[list[XtbReport], list[dict[str, str]], list[str]]:
    try:
        expanded, skipped = expand_uploads(_read_uploads(files))
    except XtbFormatError as exc:
        raise ApiError(422, exc.code, exc.message) from exc
    reports, errors = [], []
    for upload in expanded:
        try:
            reports.append(parse_report(upload.filename, upload.content))
        except XtbFormatError as exc:
            errors.append({"filename": upload.filename, "code": exc.code, "message": exc.message})
    return reports, errors, skipped


def _file_out(plan: FilePlan, record: ImportRecord | None = None) -> ImportFileOut:
    report = plan.report
    return ImportFileOut(
        filename=report.filename,
        account_number=report.account_number,
        wrapper=report.wrapper,
        currency=report.currency,
        account_id=plan.account.id if plan.account else None,
        account_name=plan.account_name,
        new_account=plan.new_account is not None,
        report_from=report.report_from,
        report_to=report.report_to,
        new_transactions=record.rows_added if record else len(plan.new_operations),
        duplicate_transactions=plan.duplicate_count,
        unknown_transactions=plan.unknown_count,
        open_lots=len(report.open_lots),
        closed_lots=len(report.closed_lots),
        warnings=plan.warnings,
        import_id=record.id if record else None,
    )


@router.post("/preview", response_model=ImportResultOut)
def preview_import(files: list[UploadFile] = File(...), scope: UserScope = Depends(get_scope)) -> ImportResultOut:
    reports, errors, skipped = _parse(files)
    plans = plan_import(scope, reports)
    return ImportResultOut(files=[_file_out(plan) for plan in plans], errors=errors, skipped=skipped)


@router.post("", status_code=201, response_model=ImportResultOut)
def commit_import(files: list[UploadFile] = File(...), scope: UserScope = Depends(get_scope)) -> ImportResultOut:
    reports, errors, skipped = _parse(files)
    if errors:
        raise ApiError(
            422, "import_invalid_files", "Niektórych plików nie da się odczytać. Nic nie zapisano.", {"errors": errors}
        )
    if not reports:
        raise ApiError(422, "import_empty", "Brak plików XLSX z XTB do zaimportowania.")
    plans = plan_import(scope, reports)
    records = apply_import(scope, plans)
    return ImportResultOut(
        files=[_file_out(plan, record) for plan, record in zip(plans, records, strict=True)],
        errors=[],
        skipped=skipped,
    )


@router.get("", response_model=list[ImportOut])
def list_imports(scope: UserScope = Depends(get_scope)) -> Sequence[ImportRecord]:
    return scope.db.scalars(scope.imports()).all()
