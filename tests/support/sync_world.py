"""동기화 시험이 함께 쓰는 도우미(source-sync 티켓 07): 가져오는 원천을 세우고, 지금 동기화를
요청해 작업자 루프를 비울 때까지 돈 뒤 그 동기화 기록을 낸다."""

from tests.records import NOW
from tests.support.pipeline import LEASE_SECONDS, Pipeline

from rag_engine.app.sync_requests import request_sync
from rag_engine.domain.entities import Source, SourceKind, SyncRecord
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.ports import ConnectorRegistry
from rag_engine.worker.processing import run_once


async def make_pull_source(
    pipeline: Pipeline,
    *,
    name: str = "공유폴더",
    connector: str = "server_path",
    exclude_patterns: tuple[str, ...] = (),
    folder: str = "docs",
) -> Source:
    """세계의 그룹에 묶인 가져오는 원천을 만든다. `folder`는 서버 경로 커넥터의 설정이다."""
    source = Source(
        new_id(),
        name,
        SourceKind.PULL,
        NOW,
        connector=connector,
        config={"folder": folder},
        group_id=pipeline.group.id,
        exclude_patterns=exclude_patterns,
    )
    async with pipeline.unit_of_work.begin() as transaction:
        await transaction.catalog.create_source(source)
    return source


async def run_sync(
    pipeline: Pipeline,
    source: Source,
    registry: ConnectorRegistry,
    *,
    source_read_timeout_seconds: float = 600.0,
) -> SyncRecord:
    """지금 동기화를 요청하고 작업자 루프를 비울 때까지 돌린 뒤 그 기록을 읽어 낸다. 동기화가 넣은
    문서의 색인 작업도 같은 루프에서 돈다."""
    requested = await request_sync(
        pipeline.unit_of_work,
        source.name,
        apply_empty=False,
        reread=False,
        request_id=new_id(),
        now=pipeline.clock[0],
    )
    await run_once(
        pipeline.deps(connectors=registry, source_read_timeout_seconds=source_read_timeout_seconds),
        worker_id="worker-sync",
        lease_seconds=LEASE_SECONDS,
    )
    async with pipeline.unit_of_work.begin() as transaction:
        record = await transaction.sync_records.get(requested.sync_record_id)
    assert record is not None
    return record
