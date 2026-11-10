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

_ZIP_END_HEAD: Final = b"PK\x05\x06"
_ZIP_END_SIZE: Final = 22
_ZIP_END_SEARCH_WINDOW: Final = (1 << 16) + _ZIP_END_SIZE
_ZIP_END_DIRECTORY_SIZE_OFFSET: Final = 12
_ZIP64_LOCATOR_HEAD: Final = b"PK\x06\x07"
_ZIP64_LOCATOR_SIZE: Final = 20
_MAX_CENTRAL_DIRECTORY_BYTES: Final = 1 << 20


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


def _central_directory_fits(data: bytes) -> bool:
    """끝 레코드가 적은 중앙 디렉터리의 크기가 상한 안인지 본다.

    `ZipFile`은 열 때 중앙 디렉터리를 통째로 읽어 항목마다 객체를 만든다. 업로드 상한 안에서도
    항목이 수십만이면 메모리와 시간이 크게 든다. 읽는 양은 항목 수 필드가 아니라 이 크기가
    정하므로 크기를 본다. 끝 레코드는 `ZipFile`과 같은 구간(뒤에서 64KiB와 레코드 길이)에서 마지막
    표지를 찾는다. ZIP64 locator가 앞에 있으면 `ZipFile`이 32비트 칸을 버리고 ZIP64 레코드의 크기를
    쓰므로 이 칸의 상한이 뜻이 없다. 상한 안의 문서는 ZIP64가 필요 없으니 그런 ZIP은 거부한다.
    """
    start = data.rfind(_ZIP_END_HEAD, max(0, len(data) - _ZIP_END_SEARCH_WINDOW))
    if start < 0 or start + _ZIP_END_SIZE > len(data):
        return False
    if data[max(0, start - _ZIP64_LOCATOR_SIZE) :][:4] == _ZIP64_LOCATOR_HEAD:
        return False
    size = int.from_bytes(data[start + _ZIP_END_DIRECTORY_SIZE_OFFSET :][:4], "little")
    return size <= _MAX_CENTRAL_DIRECTORY_BYTES


def _sniff_zip(data: bytes) -> str | None:
    if not _central_directory_fits(data):
        return None
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
