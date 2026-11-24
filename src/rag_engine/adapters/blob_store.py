"""로컬 볼륨 `BlobStore` 어댑터(명세 "포트 열셋과 그 값", ADR 0013 이력).

키 `blobs/<문서 UUID>/<원본 UUID>`를 데이터 폴더(`RAG_DATA_DIR`) 아래 같은 경로의 파일로 둔다. 파일
입출력은 스레드로 넘겨 이벤트 루프를 막지 않는다. 입출력 오류는 일시 실패 `blob_store_error`로 바꿔
올리고, 운영체제 오류의 메시지(경로가 든다)는 옮기지 않는다(원칙 V).
"""

import asyncio
import contextlib
from datetime import datetime
from pathlib import Path
from typing import Final

from rag_engine.domain.errors import ErrorCode, TransientFailure

# 원본 키의 첫 토막. 정리 작업이 데이터 폴더의 다른 파일을 건드리지 않게 이 아래만 훑는다.
BLOB_FOLDER: Final = "blobs"


class LocalBlobStore:
    def __init__(self, root: Path) -> None:
        self._root = root.resolve()

    def _path(self, key: str) -> Path:
        path = (self._root / key).resolve()
        if not path.is_relative_to(self._root):
            raise ValueError("키가 데이터 폴더 밖을 가리킨다")
        return path

    async def write(self, key: str, data: bytes) -> None:
        path = self._path(key)
        try:
            await asyncio.to_thread(self._write, path, data)
        except OSError:
            raise TransientFailure(ErrorCode.BLOB_STORE_ERROR, "원본을 쓰지 못했다") from None

    async def read(self, key: str) -> bytes:
        path = self._path(key)
        try:
            return await asyncio.to_thread(path.read_bytes)
        except OSError:
            raise TransientFailure(ErrorCode.BLOB_STORE_ERROR, "원본을 읽지 못했다") from None

    async def delete(self, key: str) -> None:
        path = self._path(key)
        try:
            await asyncio.to_thread(self._delete, path)
        except OSError:
            raise TransientFailure(ErrorCode.BLOB_STORE_ERROR, "원본을 지우지 못했다") from None

    async def list_written_before(self, cutoff: datetime) -> list[str]:
        try:
            return await asyncio.to_thread(self._list_written_before, cutoff.timestamp())
        except OSError:
            raise TransientFailure(ErrorCode.BLOB_STORE_ERROR, "원본을 훑지 못했다") from None

    def _list_written_before(self, cutoff: float) -> list[str]:
        """`blobs/<문서 UUID>/<원본 UUID>` 모양의 파일만 훑는다. 훑는 도중에 지워진 파일은 건너뛴다.
        링크는 따라가지 않는다. `blobs/`와 그 아래 문서 폴더가 링크이면 그 아래 파일은 훑지 않는다.
        `glob`이 폴더 링크를 따라 들어가므로 파일 쪽 링크만 보면 링크 아래 파일이 열거되고, 그
        키는 `delete`가 실제 경로로 풀어 데이터 폴더 밖이라 거부하거나 별칭이라 주인 없는 원본으로
        오판한다."""
        blob_root = self._root / BLOB_FOLDER
        if blob_root.is_symlink():
            return []
        found: list[str] = []
        for path in sorted(blob_root.glob("*/*")):
            try:
                if (
                    path.parent.is_symlink()
                    or path.is_symlink()
                    or not path.is_file()
                    or path.stat().st_mtime >= cutoff
                ):
                    continue
            except FileNotFoundError:
                continue
            found.append(path.relative_to(self._root).as_posix())
        return found

    @staticmethod
    def _write(path: Path, data: bytes) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        try:
            path.write_bytes(data)
        except OSError:
            path.unlink(missing_ok=True)
            raise

    @staticmethod
    def _delete(path: Path) -> None:
        path.unlink(missing_ok=True)
        # 같은 문서의 다른 원본이 남았거나 폴더가 이미 없으면 치우지 않는다. 폴더는 비었을 때만
        # 치운다.
        with contextlib.suppress(OSError):
            path.parent.rmdir()
