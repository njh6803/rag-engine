"""동기화의 로그 줄이 닫힌 수준 값을 단다(source-sync 티켓 08).

처음에는 경고인지를 불리언 칸 하나로 알렸다. 줄이 늘면 칸의 뜻이 흐려지므로 닫힌 열거로 바꿨다. 이
시험은 유스케이스가 내는 줄의 수준과, 작업자가 그 수준을 로그 수준으로 옮기는 것을 본다.
"""

import logging
from datetime import datetime

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.pipeline import Pipeline
from tests.support.scripted_connectors import ScriptedFolder, ScriptedRegistry
from tests.support.sync_world import make_pull_source, run_sync

from rag_engine.app.sync_requests import request_sync
from rag_engine.app.sync_source import SyncDeps, SyncLogLevel, SyncLogLine, sync_source
from rag_engine.domain.connectors import ConnectorError, ConnectorFailureReason
from rag_engine.domain.identifiers import new_id


async def _lines_of_one_sync(
    pipeline: Pipeline, folder: ScriptedFolder, *, now: datetime
) -> list[SyncLogLine]:
    """동기화 작업 하나를 꺼내 유스케이스를 직접 부르고 그 유스케이스가 낸 로그 줄을 모은다."""
    source = await make_pull_source(pipeline)
    await request_sync(
        pipeline.unit_of_work,
        source.name,
        apply_empty=False,
        reread=False,
        request_id=new_id(),
        now=now,
    )
    job = await pipeline.claim("worker-lines")
    lines: list[SyncLogLine] = []
    deps = SyncDeps(
        unit_of_work=pipeline.unit_of_work,
        connectors=ScriptedRegistry(folder),
        source_read_timeout_seconds=600.0,
        max_upload_bytes=100 * 1024 * 1024,
        now=lambda: now,
        log=lines.append,
    )
    await sync_source(deps, job)
    return lines


async def test_성공한_동기화의_두_줄은_정보_수준이다(pipeline: Pipeline) -> None:
    folder = ScriptedFolder()
    folder.put("규정.docx", docx_bytes("규정", "본문이다."), "m1")

    lines = await _lines_of_one_sync(pipeline, folder, now=pipeline.clock[0])

    assert [(line.event, line.level) for line in lines] == [
        ("sync_started", SyncLogLevel.INFO),
        ("sync_finished", SyncLogLevel.INFO),
    ]


async def test_실패한_동기화의_끝_줄만_경고_수준이다(pipeline: Pipeline) -> None:
    folder = ScriptedFolder()
    folder.list_error = ConnectorError(ConnectorFailureReason.UNREADABLE)

    lines = await _lines_of_one_sync(pipeline, folder, now=pipeline.clock[0])

    assert [(line.event, line.level) for line in lines] == [
        ("sync_started", SyncLogLevel.INFO),
        ("sync_finished", SyncLogLevel.WARNING),
    ]


async def test_작업자는_동기화의_수준을_로그_수준으로_옮긴다(
    pipeline: Pipeline, caplog: pytest.LogCaptureFixture
) -> None:
    caplog.set_level(logging.INFO)
    source = await make_pull_source(pipeline)
    folder = ScriptedFolder()
    folder.list_error = ConnectorError(ConnectorFailureReason.UNREADABLE)

    await run_sync(pipeline, source, ScriptedRegistry(folder))

    levels = {
        entry.getMessage(): entry.levelno
        for entry in caplog.records
        if entry.getMessage() in {"sync_started", "sync_finished"}
    }
    assert levels == {"sync_started": logging.INFO, "sync_finished": logging.WARNING}
