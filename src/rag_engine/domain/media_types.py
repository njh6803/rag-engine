"""수집이 받는 문서 형식 셋(PDF, DOCX, HWPX)의 MIME과 판정(명세 "수집 API").

확장자가 셋 가운데 하나면 바이트를 보지 않고 그 형식으로 본다. 깨진 파일은 작업의 파싱이
`parse_failed`로 가린다. 확장자가 없거나 셋 밖이면 바이트 머리로 가린다. PDF는 `%PDF-`로 시작하고,
ZIP은 안의 항목 이름으로 DOCX(`word/document.xml`)와 HWPX(`Contents/header.xml`)를 가른다.
"""

import io
import zipfile
from pathlib import PurePath
from typing import Final

PDF_MIME: Final = "application/pdf"
DOCX_MIME: Final = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
HWPX_MIME: Final = "application/hwp+zip"

SUPPORTED_EXTENSIONS: Final = {".pdf": PDF_MIME, ".docx": DOCX_MIME, ".hwpx": HWPX_MIME}

_PDF_HEAD: Final = b"%PDF-"
_ZIP_HEAD: Final = b"PK\x03\x04"
_DOCX_ENTRY: Final = "word/document.xml"
_HWPX_ENTRY: Final = "Contents/header.xml"


def detect_media_type(filename: str | None, data: bytes) -> str | None:
    """형식의 MIME을 낸다. 셋 밖이면 `None`이다."""
    if filename:
        by_extension = SUPPORTED_EXTENSIONS.get(PurePath(filename).suffix.lower())
        if by_extension is not None:
            return by_extension
    return _sniff(data)


def _sniff(data: bytes) -> str | None:
    if data.startswith(_PDF_HEAD):
        return PDF_MIME
    if data.startswith(_ZIP_HEAD):
        return _sniff_zip(data)
    return None


def _sniff_zip(data: bytes) -> str | None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            names = set(archive.namelist())
    except (zipfile.BadZipFile, NotImplementedError, UnicodeDecodeError):
        # 머리만 ZIP인 변조 입력이다. 버전이 지원 밖이면 `NotImplementedError`,
        # UTF-8 표지가 선 항목 이름이 틀리면 `UnicodeDecodeError`가 난다.
        return None
    if _DOCX_ENTRY in names:
        return DOCX_MIME
    if _HWPX_ENTRY in names:
        return HWPX_MIME
    return None
