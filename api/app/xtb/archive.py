import io
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.xtb.workbook import XtbFormatError

MAX_XLSX_BYTES = 10 * 1024 * 1024
MAX_ZIP_ENTRIES = 50
MAX_UNZIPPED_BYTES = 100 * 1024 * 1024


@dataclass(frozen=True)
class UploadedFile:
    filename: str
    content: bytes


def _too_large(name: str) -> XtbFormatError:
    return XtbFormatError("file_too_large", f"Plik {name} jest za duży (maks. 10 MB).")


def expand_uploads(
    files: list[UploadedFile],
    *,
    max_xlsx_bytes: int = MAX_XLSX_BYTES,
    max_entries: int = MAX_ZIP_ENTRIES,
    max_unzipped_bytes: int = MAX_UNZIPPED_BYTES,
) -> tuple[list[UploadedFile], list[str]]:
    """Turns uploaded files (XLSX, ZIP, or a browser-selected folder) into XLSX files to parse.

    Returns the XLSX files and the names of everything skipped. Limits guard against zip bombs.
    """
    result: list[UploadedFile] = []
    skipped: list[str] = []
    for upload in files:
        name = PurePosixPath(upload.filename.replace("\\", "/")).name
        lower = name.lower()
        if lower.endswith(".zip"):
            result.extend(_expand_zip(name, upload.content, skipped, max_xlsx_bytes, max_entries, max_unzipped_bytes))
        elif lower.endswith(".xlsx") and not name.startswith("._"):
            if len(upload.content) > max_xlsx_bytes:
                raise _too_large(name)
            result.append(UploadedFile(name, upload.content))
        else:
            skipped.append(name)
    return result, skipped


def _expand_zip(
    zip_name: str, content: bytes, skipped: list[str], max_xlsx_bytes: int, max_entries: int, max_unzipped_bytes: int
) -> list[UploadedFile]:
    try:
        archive = zipfile.ZipFile(io.BytesIO(content))
    except zipfile.BadZipFile as exc:
        raise XtbFormatError("not_zip", f"Plik {zip_name} nie jest poprawnym archiwum ZIP.") from exc
    with archive:
        all_entries = archive.infolist()
        if len(all_entries) > max_entries:
            raise XtbFormatError(
                "archive_too_many_files", f"Archiwum {zip_name} ma za dużo plików (maks. {max_entries})."
            )
        files: list[UploadedFile] = []
        total = 0
        for info in all_entries:
            if info.is_dir():
                continue
            path = info.filename.replace("\\", "/")
            name = PurePosixPath(path).name
            if not name.lower().endswith(".xlsx") or name.startswith("._") or path.startswith("__MACOSX/"):
                skipped.append(name)
                continue
            with archive.open(info) as entry:
                data = entry.read(max_xlsx_bytes + 1)  # never trust the declared size
            if len(data) > max_xlsx_bytes:
                raise _too_large(name)
            total += len(data)
            if total > max_unzipped_bytes:
                raise XtbFormatError("archive_too_large", f"Archiwum {zip_name} po rozpakowaniu jest za duże.")
            files.append(UploadedFile(name, data))
        return files
