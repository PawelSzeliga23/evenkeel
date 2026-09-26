import io
import zipfile

import pytest

from app.xtb.archive import UploadedFile, expand_uploads
from app.xtb.workbook import XtbFormatError


def _zip(entries: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in entries.items():
            archive.writestr(name, content)
    return buffer.getvalue()


def test_xlsx_files_pass_through_and_other_files_are_skipped() -> None:
    files, skipped = expand_uploads([UploadedFile("IKE_1.xlsx", b"a"), UploadedFile("notatki.txt", b"b")])

    assert [f.filename for f in files] == ["IKE_1.xlsx"]
    assert skipped == ["notatki.txt"]


def test_zip_is_expanded_by_basename_skipping_junk() -> None:
    archive = _zip({
        "eksport/IKE_1.xlsx": b"ike",
        "eksport/PLN_2.xlsx": b"pln",
        "__MACOSX/eksport/._IKE_1.xlsx": b"junk",
        "eksport/readme.txt": b"txt",
    })

    files, skipped = expand_uploads([UploadedFile("xtb.zip", archive)])

    assert sorted((f.filename, f.content) for f in files) == [("IKE_1.xlsx", b"ike"), ("PLN_2.xlsx", b"pln")]
    assert sorted(skipped) == ["._IKE_1.xlsx", "readme.txt"]


def test_zip_with_too_many_entries_is_rejected() -> None:
    archive = _zip({f"f{i}.xlsx": b"x" for i in range(4)})

    with pytest.raises(XtbFormatError) as exc_info:
        expand_uploads([UploadedFile("a.zip", archive)], max_entries=3)

    assert exc_info.value.code == "archive_too_many_files"


def test_zip_that_unpacks_too_large_is_rejected() -> None:
    archive = _zip({"a.xlsx": b"0" * 600, "b.xlsx": b"0" * 600})

    with pytest.raises(XtbFormatError) as exc_info:
        expand_uploads([UploadedFile("a.zip", archive)], max_unzipped_bytes=1000)

    assert exc_info.value.code == "archive_too_large"


def test_oversized_xlsx_is_rejected_directly_and_inside_zip() -> None:
    for upload in (UploadedFile("a.xlsx", b"0" * 11), UploadedFile("a.zip", _zip({"a.xlsx": b"0" * 11}))):
        with pytest.raises(XtbFormatError) as exc_info:
            expand_uploads([upload], max_xlsx_bytes=10)
        assert exc_info.value.code == "file_too_large"


def test_broken_zip_is_rejected() -> None:
    with pytest.raises(XtbFormatError) as exc_info:
        expand_uploads([UploadedFile("a.zip", b"to nie zip")])

    assert exc_info.value.code == "not_zip"
