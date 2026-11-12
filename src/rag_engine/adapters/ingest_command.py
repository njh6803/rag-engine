"""`ingest <경로> [--group 이름] [--wait] [--timeout 초]`의 조립(명세 "관리 명령", 스토리 9).

서버 없이 파일 하나나 폴더를 수집한다. 폴더면 지원 확장자의 파일을 재귀로 걷고 키는 폴더 기준 상대
경로(POSIX 구분자)이며, 파일 하나면 키를 주지 않아 파일 이름이 키가 된다. 파일마다 수집 유스케이스를
직접 불러 `action`을 한 줄씩(`action<탭>키`) 표준 출력에 찍는다. 거부된 파일(`upload_too_large`,
`unsupported_media_type`)과 읽지 못한 파일(`읽기 실패`)은 표준 오류에 사유와 키를 적고 나머지를
이어 넣으며 종료 코드 1로 끝낸다.

실행마다 UUIDv7 요청 ID 하나를 만들어 그 실행의 로그(`request_id_var`)와 넣은 작업에 쓴다.
`--wait`면 넣은 문서마다 작업이 없어질 때까지 기다리고 색인이 실패한 문서를 표준 오류에 낸다.
`--timeout`은 `--wait`와 함께 쓰고(없으면 무시한다) 0 이하면 끝날 때까지 기다린다. 종료 코드는
0(문제 없음. 수집할 파일이 없는 폴더도 안내만 하고 0), 1(없는 경로·없는 그룹·거부된 파일·색인이
실패한 문서), 2(`--timeout`이 지남)다. 거부된 파일과 시간 초과가 겹치면 2가 앞선다. 거부는 표준
오류에 이미 적혔기 때문이다. 기다림은 작업자가 따로 떠 있어야 끝난다.
"""

import asyncio
import sys
import time
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Final
from uuid import UUID

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.adapters.log_format import configure_logging, request_id_var
from rag_engine.adapters.postgres.engine import create_engine, run_in_selector_loop
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.settings import Settings
from rag_engine.app.await_documents import WaitResult, WaitStatus, wait_for_documents
from rag_engine.app.ingest import (
    IngestRequest,
    IngestResult,
    ensure_within_upload_limit,
    group_exists,
    ingest_document,
)
from rag_engine.domain.entities import JsonValue
from rag_engine.domain.errors import RequestError
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.media_types import SUPPORTED_EXTENSIONS
from rag_engine.domain.ports import UnitOfWork

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_TIMED_OUT: Final = 2
POLL_SECONDS: Final = 1.0
_BYTES_PER_MB: Final = 1024 * 1024
_UNREADABLE: Final = "읽기 실패"
_NO_METADATA: Final[dict[str, JsonValue]] = {}


@dataclass(frozen=True, slots=True)
class _Entry:
    """수집할 파일 하나. `key`가 `None`이면 파일 이름이 키다."""

    file: Path
    key: str | None

    @property
    def label(self) -> str:
        return self.key if self.key is not None else self.file.name


def ingest_path(
    settings: Settings, path: Path, *, group: str | None, wait_timeout_seconds: float | None
) -> int:
    """종료 코드를 낸다. `wait_timeout_seconds`가 `None`이면 기다리지 않고, 0이면 끝날 때까지
    기다린다."""
    configure_logging(settings.log_format)
    return run_in_selector_loop(_ingest(settings, path, group, wait_timeout_seconds))


def _collect(path: Path) -> list[_Entry]:
    if path.is_file():
        return [_Entry(path, None)]
    # 폴더 밖을 가리키는 링크는 걷는 범위 밖의 파일을 이 폴더의 문서로 넣게 되므로 거른다.
    root = path.resolve()
    found = (
        file
        for file in path.rglob("*")
        if file.is_file()
        and file.suffix.lower() in SUPPORTED_EXTENSIONS
        and file.resolve().is_relative_to(root)
    )
    return [_Entry(file, file.relative_to(path).as_posix()) for file in sorted(found)]


def _read_within_limit(file: Path, max_bytes: int) -> bytes:
    """상한까지만 읽는다. 크기를 잰 뒤 파일이 커져도 상한을 넘는 바이트는 메모리에 올리지 않는다."""
    ensure_within_upload_limit(file.stat().st_size, max_bytes)
    with file.open("rb") as stream:
        data = stream.read(max_bytes + 1)
    ensure_within_upload_limit(len(data), max_bytes)
    return data


async def _read(file: Path, max_bytes: int) -> bytes | str:
    """읽은 바이트나 거부 사유를 낸다. 권한이 없거나 다른 프로그램이 잠갔거나 걷는 사이 사라진
    파일의 사유 문구에는 운영체제의 메시지(경로)를 싣지 않는다."""
    try:
        return await asyncio.to_thread(_read_within_limit, file, max_bytes)
    except RequestError as error:
        return error.code.value
    except OSError:
        return _UNREADABLE


async def _ingest_entry(
    unit_of_work: UnitOfWork,
    blob_store: LocalBlobStore,
    entry: _Entry,
    group: str | None,
    request_id: UUID,
    max_upload_bytes: int,
) -> IngestResult | str:
    """수집 결과를 내고, 거부하면 사유를 낸다."""
    data = await _read(entry.file, max_upload_bytes)
    if isinstance(data, str):
        return data
    try:
        return await ingest_document(
            unit_of_work,
            blob_store,
            IngestRequest(
                filename=entry.file.name,
                data=data,
                key=entry.key,
                group=group,
                metadata=_NO_METADATA,
                updated_at=None,
            ),
            request_id=request_id,
            now=datetime.now(UTC),
            max_upload_bytes=max_upload_bytes,
        )
    except RequestError as error:
        return error.code.value


async def _ingest(
    settings: Settings, path: Path, group: str | None, wait_timeout_seconds: float | None
) -> int:
    if not path.exists():
        print(f"경로가 없다: {path}", file=sys.stderr)
        return EXIT_FAILED
    request_id = new_id()
    reset = request_id_var.set(request_id)
    engine = create_engine(settings.database_url)
    try:
        return await _ingest_with(
            PostgresUnitOfWork(engine), settings, path, group, wait_timeout_seconds, request_id
        )
    finally:
        await engine.dispose()
        request_id_var.reset(reset)


async def _ingest_with(
    unit_of_work: UnitOfWork,
    settings: Settings,
    path: Path,
    group: str | None,
    wait_timeout_seconds: float | None,
    request_id: UUID,
) -> int:
    if group is not None and not await group_exists(unit_of_work, group):
        print(f"그룹이 없다: {group}", file=sys.stderr)
        return EXIT_FAILED
    entries = await asyncio.to_thread(_collect, path)
    if not entries:
        print("수집할 파일이 없다(PDF, DOCX, HWPX)", file=sys.stderr)
        return EXIT_OK
    labels: dict[UUID, str] = {}
    rejected = 0
    blob_store = LocalBlobStore(settings.data_dir)
    max_upload_bytes = settings.max_upload_mb * _BYTES_PER_MB
    for entry in entries:
        outcome = await _ingest_entry(
            unit_of_work, blob_store, entry, group, request_id, max_upload_bytes
        )
        if isinstance(outcome, str):
            print(f"거부\t{entry.label}\t{outcome}", file=sys.stderr)
            rejected += 1
            continue
        print(f"{outcome.action.value}\t{entry.label}")
        labels[outcome.document_id] = entry.label
    waited: WaitResult | None = None
    if wait_timeout_seconds is not None and labels:
        waited = await _wait(unit_of_work, list(labels), wait_timeout_seconds)
        _report_failures(waited, labels)
    return _exit_code(rejected, waited)


async def _wait(
    unit_of_work: UnitOfWork, document_ids: list[UUID], timeout_seconds: float
) -> WaitResult:
    print("작업자가 따로 떠 있어야 끝난다. 색인이 끝날 때까지 기다린다", file=sys.stderr)
    return await wait_for_documents(
        unit_of_work,
        document_ids,
        poll_seconds=POLL_SECONDS,
        timeout_seconds=timeout_seconds,
        sleep=asyncio.sleep,
        monotonic=time.monotonic,
    )


def _report_failures(waited: WaitResult, labels: dict[UUID, str]) -> None:
    for failed in waited.failed:
        print(f"실패\t{labels[failed.document_id]}\t{failed.error_code.value}", file=sys.stderr)
    if waited.status is WaitStatus.TIMED_OUT:
        print("기다리는 시간이 지났다. 작업이 아직 남아 있다", file=sys.stderr)


def _exit_code(rejected: int, waited: WaitResult | None) -> int:
    if waited is not None and waited.status is WaitStatus.TIMED_OUT:
        return EXIT_TIMED_OUT
    if rejected or (waited is not None and waited.failed):
        return EXIT_FAILED
    return EXIT_OK
