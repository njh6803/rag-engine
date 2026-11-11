"""ZIP 컨테이너(DOCX, HWPX)의 사전 검사(명세 "파싱의 격리와 자원 한도").

부모가 자식을 띄우기 전에 목록만 읽어 판정한다. 항목 4096개 초과, 압축 해제 합계 초과, 압축된
크기가 1MiB를 넘는 항목의 압축비 초과는 `compressed_too_large`이고, 암호 항목은
`encrypted_document`다. 압축된 크기가 1MiB 이하인 항목은 압축비를 보지 않는다. 그런 항목이 많아도
항목 수와 합계가 막는다.

목록의 크기는 중앙 디렉터리가 적은 값이다. `zipfile`은 항목을 읽을 때 그 크기를 넘겨 풀지 않아 이
값은 파서가 실제로 풀 양의 상한이다. 다만 `ZipFile`은 열 때 중앙 디렉터리를 통째로 읽어 항목마다
객체를 만드므로, 목록을 읽기 전에 그 디렉터리의 크기를 먼저 본다(`central_directory_fits`).
"""

import io
import zipfile
from typing import Final

from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.media_types import central_directory_fits

MAX_ENTRIES: Final = 4096
_RATIO_CHECKED_FROM_BYTES: Final = 1024 * 1024
_ENCRYPTED_FLAG: Final = 0x1


def check_zip_container(
    data: bytes, *, max_unzipped_bytes: int, max_compression_ratio: int
) -> None:
    """한도를 넘거나 암호가 걸린 ZIP이면 `PermanentFailure`를 올린다."""
    # `is_zipfile`은 끝 레코드만 찾고 중앙 디렉터리를 읽지 않는다. 이것이 거짓이면 ZIP이 아니고,
    # 참인데 `central_directory_fits`가 거짓이면 목록이 한도를 넘었거나 ZIP64다.
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise PermanentFailure(ErrorCode.PARSE_FAILED, "ZIP을 읽을 수 없다")
    if not central_directory_fits(data):
        raise PermanentFailure(ErrorCode.COMPRESSED_TOO_LARGE, "ZIP의 목록이 한도를 넘었다")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            entries = archive.infolist()
    except (zipfile.BadZipFile, NotImplementedError, UnicodeDecodeError) as error:
        raise PermanentFailure(ErrorCode.PARSE_FAILED, "ZIP을 읽을 수 없다") from error
    if len(entries) > MAX_ENTRIES:
        raise PermanentFailure(ErrorCode.COMPRESSED_TOO_LARGE, "ZIP의 항목 수가 한도를 넘었다")
    if any(entry.flag_bits & _ENCRYPTED_FLAG for entry in entries):
        raise PermanentFailure(ErrorCode.ENCRYPTED_DOCUMENT, "암호가 걸린 항목이 있다")
    if sum(entry.file_size for entry in entries) > max_unzipped_bytes:
        raise PermanentFailure(ErrorCode.COMPRESSED_TOO_LARGE, "압축 해제 크기가 한도를 넘었다")
    if any(_ratio_exceeds(entry, max_compression_ratio) for entry in entries):
        raise PermanentFailure(ErrorCode.COMPRESSED_TOO_LARGE, "압축비가 한도를 넘었다")


def _ratio_exceeds(entry: zipfile.ZipInfo, max_ratio: int) -> bool:
    return (
        entry.compress_size > _RATIO_CHECKED_FROM_BYTES
        and entry.file_size > entry.compress_size * max_ratio
    )
