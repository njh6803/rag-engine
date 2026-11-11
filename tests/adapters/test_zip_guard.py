"""ZIP 컨테이너 사전 검사(명세 "파싱의 격리와 자원 한도", 티켓 08).

DOCX와 HWPX는 ZIP이다. 부모가 목록만 읽어 항목 수, 압축 해제 합계, 큰 항목의 압축비, 암호 항목을
보고 한도를 넘으면 자식을 띄우지 않고 영구 실패로 끝낸다. 압축 폭탄은 시험이 만든다.
"""

import os

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.zip_files import zip_bytes

from rag_engine.adapters.parsers.zip_guard import check_zip_container
from rag_engine.domain.errors import ErrorCode, PermanentFailure

MIB = 1024 * 1024
UNZIPPED_LIMIT = 64 * MIB
RATIO_LIMIT = 100


def _failure_code(
    data: bytes, *, unzipped: int = UNZIPPED_LIMIT, ratio: int = RATIO_LIMIT
) -> object:
    with pytest.raises(PermanentFailure) as caught:
        check_zip_container(data, max_unzipped_bytes=unzipped, max_compression_ratio=ratio)
    return caught.value.code


def test_정상_DOCX는_통과한다() -> None:
    check_zip_container(
        docx_bytes("제1조", "본문이다."),
        max_unzipped_bytes=UNZIPPED_LIMIT,
        max_compression_ratio=RATIO_LIMIT,
    )


def test_항목이_4096개이면_통과하고_4097개이면_compressed_too_large다() -> None:
    at_limit = zip_bytes({f"f{i}.txt": b"x" for i in range(4096)})
    over_limit = zip_bytes({f"f{i}.txt": b"x" for i in range(4097)})

    check_zip_container(
        at_limit, max_unzipped_bytes=UNZIPPED_LIMIT, max_compression_ratio=RATIO_LIMIT
    )
    assert _failure_code(over_limit) is ErrorCode.COMPRESSED_TOO_LARGE


def test_압축_해제_합계가_한도를_넘으면_compressed_too_large다() -> None:
    bomb = zip_bytes({"a.bin": bytes(2 * MIB)})

    assert _failure_code(bomb, unzipped=1 * MIB) is ErrorCode.COMPRESSED_TOO_LARGE


def test_압축된_크기가_1MiB를_넘는_항목의_압축비가_한도를_넘으면_compressed_too_large다() -> None:
    # 난수 1.2MiB는 거의 줄지 않아 압축된 크기가 1MiB를 넘고, 영 3MiB가 비를 4배 가까이 올린다.
    mostly_zeros = zip_bytes({"a.bin": os.urandom(1200 * 1024) + bytes(3 * MIB)})

    assert _failure_code(mostly_zeros, ratio=2) is ErrorCode.COMPRESSED_TOO_LARGE
    check_zip_container(mostly_zeros, max_unzipped_bytes=UNZIPPED_LIMIT, max_compression_ratio=10)


def test_압축된_크기가_1MiB_이하인_항목은_압축비를_보지_않는다() -> None:
    # 합계는 한도 안이다. 항목 수와 합계가 이 경우를 막고, 압축비는 큰 항목만 본다.
    highly_compressible = zip_bytes({"a.bin": bytes(8 * MIB)})

    check_zip_container(
        highly_compressible, max_unzipped_bytes=UNZIPPED_LIMIT, max_compression_ratio=RATIO_LIMIT
    )


def test_암호_항목이_있으면_encrypted_document다() -> None:
    locked = zip_bytes({"a.txt": "비밀".encode(), "b.txt": "공개".encode()}, encrypted=("a.txt",))

    assert _failure_code(locked) is ErrorCode.ENCRYPTED_DOCUMENT


def test_ZIP이_아닌_바이트는_parse_failed다() -> None:
    assert _failure_code(b"PK\x03\x04 broken") is ErrorCode.PARSE_FAILED


def test_중앙_디렉터리가_상한을_넘으면_목록을_읽기_전에_compressed_too_large다() -> None:
    # 항목 수는 4096 이하이지만 이름이 길어 중앙 디렉터리가 1MiB를 넘는다. `ZipFile`은 열 때 그
    # 디렉터리를 통째로 읽으므로 목록을 읽기 전에 크기로 거른다.
    long_names = zip_bytes({f"{i:04d}" + "n" * 400: b"x" for i in range(3000)})

    assert _failure_code(long_names) is ErrorCode.COMPRESSED_TOO_LARGE
