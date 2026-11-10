"""로컬 볼륨 `BlobStore` 어댑터(명세 "포트 열셋과 그 값", ADR 0013 이력).

키는 `blobs/<문서 UUID>/<원본 UUID>`이고 데이터 폴더 아래에 그대로 놓인다. 입출력 오류는 일시 실패
`blob_store_error`다.
"""

from pathlib import Path

import pytest

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.domain.errors import ErrorCode, TransientFailure

KEY = "blobs/0198f4a0-0000-7000-8000-000000000001/0198f4a0-0000-7000-8000-000000000002"


async def test_쓴_바이트를_같은_키로_읽는다(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)

    await store.write(KEY, b"%PDF-1.7 \xff\x00")

    assert await store.read(KEY) == b"%PDF-1.7 \xff\x00"
    assert (tmp_path / KEY).is_file()


async def test_지우면_파일이_없어지고_빈_문서_폴더도_치운다(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    await store.write(KEY, b"x")

    await store.delete(KEY)

    assert not (tmp_path / KEY).exists()
    assert not (tmp_path / KEY).parent.exists()


async def test_같은_문서_폴더의_다른_원본이_남아_있으면_폴더를_남긴다(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    other = KEY.rsplit("/", 1)[0] + "/other"
    await store.write(KEY, b"x")
    await store.write(other, b"y")

    await store.delete(KEY)

    assert await store.read(other) == b"y"


async def test_없는_키를_지워도_오류가_없다(tmp_path: Path) -> None:
    await LocalBlobStore(tmp_path).delete(KEY)


async def test_없는_키를_읽으면_일시_실패_blob_store_error다(tmp_path: Path) -> None:
    with pytest.raises(TransientFailure) as raised:
        await LocalBlobStore(tmp_path).read(KEY)

    assert raised.value.code is ErrorCode.BLOB_STORE_ERROR


async def test_쓰기가_입출력_오류로_실패하면_일시_실패_blob_store_error다(tmp_path: Path) -> None:
    blocker = tmp_path / "blobs"
    blocker.write_text("폴더가 있어야 할 자리의 파일", encoding="utf-8")

    with pytest.raises(TransientFailure) as raised:
        await LocalBlobStore(tmp_path).write(KEY, b"x")

    assert raised.value.code is ErrorCode.BLOB_STORE_ERROR
    assert str(tmp_path) not in str(raised.value)


@pytest.mark.parametrize("key", ["../escape", "blobs/../../escape", "/abs/path"])
async def test_데이터_폴더_밖을_가리키는_키는_거부한다(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="데이터 폴더"):
        await LocalBlobStore(tmp_path).write(key, b"x")
