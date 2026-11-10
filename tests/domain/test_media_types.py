"""수집이 받는 문서 형식의 판정(명세 "수집 API"). 확장자를 먼저 보고, 없거나 셋 밖이면 바이트
머리로 가린다."""

import io
import zipfile

import pytest

from rag_engine.domain.media_types import DOCX_MIME, HWPX_MIME, PDF_MIME, detect_media_type


def _zip(*names: str) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as archive:
        for name in names:
            archive.writestr(name, "<x/>")
    return buffer.getvalue()


_CENTRAL_HEAD = b"PK\x01\x02"
_CENTRAL_NAME_OFFSET = 46


def _unsupported_version_zip() -> bytes:
    """중앙 디렉터리의 필요한 버전을 `zipfile`의 지원 상한(63) 위로 올려
    `NotImplementedError`를 낸다."""
    data = bytearray(_zip("word/document.xml"))
    data[data.rindex(_CENTRAL_HEAD) + 6] = 100
    return bytes(data)


def _invalid_utf8_name_zip() -> bytes:
    """UTF-8 표지가 선 항목 이름을 잘못된 바이트로 바꿔 `UnicodeDecodeError`를 낸다."""
    data = bytearray(_zip("aaa"))
    head = data.rindex(_CENTRAL_HEAD)
    data[head + 9] |= 0x08
    data[head + _CENTRAL_NAME_OFFSET : head + _CENTRAL_NAME_OFFSET + 3] = b"\xff\xfe\xfd"
    return bytes(data)


@pytest.mark.parametrize(
    ("filename", "mime"),
    [
        ("규정.pdf", PDF_MIME),
        ("규정.DOCX", DOCX_MIME),
        ("규정.hwpx", HWPX_MIME),
        ("dir/규정.v2.pdf", PDF_MIME),
    ],
)
def test_확장자가_셋_가운데_하나면_바이트를_보지_않고_그_형식이다(filename: str, mime: str) -> None:
    assert detect_media_type(filename, b"") == mime


def test_확장자가_없으면_PDF_머리로_가린다() -> None:
    assert detect_media_type("규정", b"%PDF-1.7\n...") == PDF_MIME
    assert detect_media_type(None, b"%PDF-1.4") == PDF_MIME


def test_확장자가_셋_밖이면_바이트_머리로_가린다() -> None:
    assert detect_media_type("규정.bin", b"%PDF-1.7") == PDF_MIME


def test_확장자가_없을_때_ZIP_안의_내용_종류로_DOCX와_HWPX를_가른다() -> None:
    docx = _zip("[Content_Types].xml", "word/document.xml")
    hwpx = _zip("mimetype", "Contents/header.xml", "Contents/section0.xml")

    assert detect_media_type("규정", docx) == DOCX_MIME
    assert detect_media_type("규정", hwpx) == HWPX_MIME


@pytest.mark.parametrize(
    "data",
    [
        b"",
        b"hello",
        b"PK\x03\x04 not really a zip",
        _zip("other.xml"),
        b"x%PDF-1.7",
        _unsupported_version_zip(),
        _invalid_utf8_name_zip(),
    ],
    ids=[
        "빈 바이트",
        "글",
        "깨진 ZIP",
        "알 수 없는 ZIP",
        "머리가 아닌 PDF 표지",
        "지원하지 않는 ZIP 버전",
        "잘못된 UTF-8 항목 이름",
    ],
)
def test_어느_형식도_아니면_판정하지_못한다(data: bytes) -> None:
    assert detect_media_type("규정.txt", data) is None
    assert detect_media_type(None, data) is None
