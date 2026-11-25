"""로컬 볼륨 `BlobStore` 어댑터(명세 "포트 열셋과 그 값", ADR 0013 이력).

키는 `blobs/<문서 UUID>/<원본 UUID>`이고 데이터 폴더 아래에 그대로 놓인다. 입출력 오류는 일시 실패
`blob_store_error`다.
"""

import os
from datetime import UTC, datetime, timedelta
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


async def test_쓴_지_기준_시각보다_오래된_원본만_키로_열거한다(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path)
    now = datetime.now(UTC)
    old_key = KEY
    fresh_key = KEY.rsplit("/", 1)[0] + "/fresh"
    await store.write(old_key, b"x")
    await store.write(fresh_key, b"y")
    old_stamp = (now - timedelta(hours=25)).timestamp()
    os.utime(tmp_path / old_key, (old_stamp, old_stamp))
    # 원본 폴더 밖의 파일은 아무리 묵어도 열거하지 않는다(서버 폴더, 데이터 폴더의 다른 파일).
    for outside in ("sources/규정.pdf", "memo.txt"):
        path = tmp_path / outside
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"z")
        os.utime(path, (old_stamp, old_stamp))

    found = await store.list_written_before(now - timedelta(hours=24))

    assert found == [old_key]


async def test_폴더_링크_아래의_파일은_열거하지_않는다(tmp_path: Path) -> None:
    store = LocalBlobStore(tmp_path / "data")
    now = datetime.now(UTC)
    old_stamp = (now - timedelta(hours=25)).timestamp()
    await store.write(KEY, b"x")
    os.utime(tmp_path / "data" / KEY, (old_stamp, old_stamp))
    # 링크 대상은 데이터 폴더 밖과 안 둘이다. 밖은 지울 수 없는 키가 되고, 안은 같은 파일의 별칭
    # 키가 되어 진짜 원본을 주인 없는 것으로 오판하게 한다.
    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "secret").write_bytes(b"z")
    os.utime(outside / "secret", (old_stamp, old_stamp))
    (tmp_path / "data" / "blobs" / "link-out").symlink_to(outside, target_is_directory=True)
    (tmp_path / "data" / "blobs" / "link-in").symlink_to(
        (tmp_path / "data" / KEY).parent, target_is_directory=True
    )

    found = await store.list_written_before(now - timedelta(hours=24))

    assert found == [KEY]


async def test_원본_폴더_자체가_링크이면_열거하지_않는다(tmp_path: Path) -> None:
    now = datetime.now(UTC)
    old_stamp = (now - timedelta(hours=25)).timestamp()
    outside = tmp_path / "outside" / "doc"
    outside.mkdir(parents=True)
    (outside / "secret").write_bytes(b"z")
    os.utime(outside / "secret", (old_stamp, old_stamp))
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "blobs").symlink_to(tmp_path / "outside", target_is_directory=True)

    found = await LocalBlobStore(tmp_path / "data").list_written_before(now - timedelta(hours=24))

    assert found == []


async def test_원본_폴더가_아직_없으면_빈_목록이다(tmp_path: Path) -> None:
    assert await LocalBlobStore(tmp_path).list_written_before(datetime.now(UTC)) == []


@pytest.mark.parametrize("key", ["../escape", "blobs/../../escape", "/abs/path"])
async def test_데이터_폴더_밖을_가리키는_키는_거부한다(tmp_path: Path, key: str) -> None:
    with pytest.raises(ValueError, match="데이터 폴더"):
        await LocalBlobStore(tmp_path).write(key, b"x")
