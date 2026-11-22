"""설치처가 만든 커넥터의 흉내가 동기화에 미치는 영향(source-sync 티켓 07, 명세 "Testing
Decisions").

실제 `EntryPointConnectorRegistry`에 가짜 entry point를 물려, 인터페이스 버전의 major가 다른
커넥터와 인터페이스에 없는 예외(비밀번호처럼 보이는 글이 든다)를 내는 커넥터를 쓴다. 동기화 기록과
로그 어디에도 예외의 글, 파일 이름, 커넥터 설정이 없어야 한다(원칙 V).
"""

import json
import logging
from importlib.metadata import EntryPoint

import pytest
from tests.records import NOW
from tests.support.fake_connectors import LEAKED_TEXT
from tests.support.leaky_connectors import LEAKED_KEY
from tests.support.pipeline import Pipeline

from rag_engine.adapters.connectors.registry import (
    CONNECTOR_ENTRY_POINT_GROUP,
    EntryPointConnectorRegistry,
)
from rag_engine.adapters.log_format import JsonLinesFormatter
from rag_engine.app.sync_requests import request_sync
from rag_engine.domain.entities import Source, SourceKind, SyncRecord, SyncRecordStatus
from rag_engine.domain.errors import ErrorCode
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import run_once

LEASE_SECONDS = 600.0
SECRET_FOLDER = "비밀폴더-토큰"


def _registry(name: str, module: str, function: str) -> EntryPointConnectorRegistry:
    entry = EntryPoint(name=name, value=f"{module}:{function}", group=CONNECTOR_ENTRY_POINT_GROUP)
    return EntryPointConnectorRegistry(lambda: [entry])


async def _sync_with(pipeline: Pipeline, registry: EntryPointConnectorRegistry) -> SyncRecord:
    source = Source(
        new_id(),
        "설치처원천",
        SourceKind.PULL,
        NOW,
        connector="installed",
        config={"folder": SECRET_FOLDER},
        group_id=pipeline.group.id,
        exclude_patterns=(),
    )
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(source)
    requested = await request_sync(
        pipeline.unit_of_work,
        source.name,
        apply_empty=False,
        reread=False,
        request_id=new_id(),
        now=pipeline.clock[0],
    )
    await run_once(
        pipeline.deps(connectors=registry, source_read_timeout_seconds=5.0),
        worker_id="worker-sync",
        lease_seconds=LEASE_SECONDS,
    )
    async with pipeline.unit_of_work.begin() as transaction:
        record = await transaction.sync_records.get(requested.sync_record_id)
    assert record is not None
    return record


def _everything_written(record: SyncRecord, caplog: pytest.LogCaptureFixture) -> str:
    """동기화 기록과 이 시험 동안 남은 로그 줄(우리 포매터로 낸 것)을 한 글로 모은다."""
    formatter = JsonLinesFormatter()
    lines = [formatter.format(entry) for entry in caplog.records]
    record_text = json.dumps(
        {"failure_code": record.failure_code, "failed": record.failed, "options": record.options},
        ensure_ascii=False,
    )
    return "\n".join([record_text, *lines])


async def test_인터페이스_버전의_major가_다른_커넥터의_원천은_connector_unavailable로_닫는다(
    pipeline: Pipeline,
) -> None:
    registry = _registry("installed", "tests.support.fake_connectors", "create_next_major")

    record = await _sync_with(pipeline, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.CONNECTOR_UNAVAILABLE.value
    assert record.listed is None


async def test_목록을_받다_인터페이스에_없는_예외가_나면_글을_어디에도_남기지_않는다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    registry = _registry("installed", "tests.support.leaky_connectors", "create_list_breaks")

    record = await _sync_with(pipeline, registry)

    assert record.status is SyncRecordStatus.FAILED
    assert record.failure_code == ErrorCode.CONNECTOR_ERROR.value
    written = _everything_written(record, caplog)
    assert LEAKED_TEXT not in written
    assert SECRET_FOLDER not in written


async def test_파일을_읽다_인터페이스에_없는_예외가_나도_글과_파일_이름을_남기지_않는다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.DEBUG)
    registry = _registry("installed", "tests.support.leaky_connectors", "create_fetch_breaks")

    record = await _sync_with(pipeline, registry)

    assert record.status is SyncRecordStatus.SUCCEEDED
    assert record.failed == {ErrorCode.CONNECTOR_ERROR.value: 1}
    written = _everything_written(record, caplog)
    assert LEAKED_TEXT not in written
    assert LEAKED_KEY not in written
    assert SECRET_FOLDER not in written


async def test_동기화는_시작과_끝에_한_줄씩_닫힌_칸만_로그로_남긴다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    registry = _registry("installed", "tests.support.leaky_connectors", "create_fetch_breaks")

    await _sync_with(pipeline, registry)

    lines = [
        json.loads(JsonLinesFormatter().format(entry))
        for entry in caplog.records
        if entry.getMessage() in {"sync_started", "sync_finished"}
    ]
    assert [line["event"] for line in lines] == ["sync_started", "sync_finished"]
    started, finished = lines
    assert started["source"] == "설치처원천"
    assert started["trigger"] == "manual"
    assert finished["result"] == "succeeded"
    assert finished["failure_code"] is None
    assert finished["listed"] == 1
    assert finished["failed"] == "connector_error=1"
    assert finished["duration_ms"] is not None
    assert started["request_id"] == finished["request_id"]
