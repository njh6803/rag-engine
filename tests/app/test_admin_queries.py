"""관리 조회의 유스케이스(명세 "관리 API", 스토리 7, 8, 티켓 15).

작업 조회는 작업 행에 그 문서의 결과(문서 상태, 오류 코드, 지식베이스마다의 색인 상태)와 같은 문서에
대기·실행 중인 작업이 남았는지를 더해 낸다. 작업의 상태는 문서의 결과가 아니라서(수집 파이프라인의
넷째 단계) 세대 대조에 걸려 `succeeded`로 끝난 작업도 뒤 작업이 남았으면 남았다고 낸다. 실제 테스트
PostgreSQL과 실제 DOCX 파서, 실제 청커 위에서 돌고 임베딩 서버만 스텁이다.
"""

from uuid import UUID

import pytest
from tests.support.docx_files import docx_bytes
from tests.support.interleaving import FailingRunner
from tests.support.pipeline import Pipeline

from rag_engine.app.admin_queries import (
    DocumentReport,
    get_document_report,
    get_job_report,
    list_document_reports,
    list_jobs,
)
from rag_engine.domain.entities import (
    DocumentState,
    IndexStateStatus,
    IndexVersionStatus,
    JobStatus,
)
from rag_engine.domain.errors import ErrorCode, RequestError
from rag_engine.domain.identifiers import new_id
from rag_engine.worker.processing import run_once

휴가 = docx_bytes("제1조 휴가", "연차휴가는 입사 일 년 뒤부터 발생한다.")
출장 = docx_bytes("제2조 출장", "출장비는 실비로 정산한다.")


async def _work(pipeline: Pipeline) -> int:
    return await run_once(pipeline.deps(), worker_id="작업자", lease_seconds=600.0)


async def _document_report(pipeline: Pipeline, document_id: UUID) -> DocumentReport:
    return await get_document_report(pipeline.unit_of_work, document_id)


async def test_수집_직후의_작업_조회는_받음_상태와_색인_전과_남은_작업을_낸다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    assert ingested.job_id is not None

    report = await get_job_report(pipeline.unit_of_work, ingested.job_id)

    assert report.job.status is JobStatus.QUEUED
    assert report.active_jobs_remain
    assert report.document.document.state is DocumentState.RECEIVED
    (index,) = report.document.indexes
    assert (index.knowledge_base, index.version, index.state) == (
        "default",
        IndexVersionStatus.CURRENT,
        None,
    )
    assert index.chunk_count == 0


async def test_색인이_끝난_작업_조회는_파싱됨_상태와_판마다의_조각_수를_낸다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    assert ingested.job_id is not None
    await _work(pipeline)

    report = await get_job_report(pipeline.unit_of_work, ingested.job_id)

    assert report.job.status is JobStatus.SUCCEEDED
    assert not report.active_jobs_remain
    assert report.document.document.state is DocumentState.PARSED
    (index,) = report.document.indexes
    assert index.state is IndexStateStatus.INDEXED
    assert index.chunk_count > 0
    assert index.error_code is None


async def test_파싱이_영구_실패한_작업_조회는_실패_상태와_오류_코드를_문서와_판에_낸다(
    pipeline: Pipeline,
) -> None:
    ingested = await pipeline.ingest(휴가)
    assert ingested.job_id is not None
    deps = pipeline.deps(parse_runner=FailingRunner(ErrorCode.PARSE_FAILED))
    await run_once(deps, worker_id="작업자", lease_seconds=600.0)

    report = await get_job_report(pipeline.unit_of_work, ingested.job_id)

    assert (report.job.status, report.job.last_error_code) == (
        JobStatus.FAILED,
        ErrorCode.PARSE_FAILED,
    )
    assert report.document.document.state is DocumentState.FAILED
    assert report.document.document.error_code is ErrorCode.PARSE_FAILED
    (index,) = report.document.indexes
    assert (index.state, index.error_code) == (IndexStateStatus.FAILED, ErrorCode.PARSE_FAILED)


async def test_내용을_바꿔_다시_넣으면_앞선_작업이_succeeded여도_남은_작업이_있다고_낸다(
    pipeline: Pipeline,
) -> None:
    first = await pipeline.ingest(휴가)
    assert first.job_id is not None
    await _work(pipeline)
    second = await pipeline.ingest(출장)
    assert second.job_id is not None and second.job_id != first.job_id

    report = await get_job_report(pipeline.unit_of_work, first.job_id)

    assert report.job.status is JobStatus.SUCCEEDED
    assert report.active_jobs_remain
    assert report.document.document.state is DocumentState.RECEIVED


async def test_없는_작업은_job_not_found다(pipeline: Pipeline) -> None:
    with pytest.raises(RequestError) as caught:
        await get_job_report(pipeline.unit_of_work, new_id())

    assert caught.value.code is ErrorCode.JOB_NOT_FOUND


async def test_작업_목록은_최근_순이고_상태와_커서와_한도를_따른다(pipeline: Pipeline) -> None:
    first = await pipeline.ingest(휴가, "휴가.docx")
    await _work(pipeline)
    second = await pipeline.ingest(출장, "출장.docx")
    assert first.job_id is not None and second.job_id is not None

    everything = await list_jobs(pipeline.unit_of_work, status=None, limit=10, after=None)
    queued = await list_jobs(pipeline.unit_of_work, status=JobStatus.QUEUED, limit=10, after=None)
    older = await list_jobs(pipeline.unit_of_work, status=None, limit=10, after=second.job_id)

    assert [job.id for job in everything] == [second.job_id, first.job_id]
    assert [job.id for job in queued] == [second.job_id]
    assert [job.id for job in older] == [first.job_id]


async def test_문서_조회는_원천과_그룹과_메타데이터와_색인_상태를_낸다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)

    report = await _document_report(pipeline, ingested.document_id)

    assert (report.source, report.group) == ("default", "default")
    assert report.document.key == "규정.docx"
    assert [(i.knowledge_base, i.state) for i in report.indexes] == [
        ("default", IndexStateStatus.INDEXED)
    ]


async def test_없는_문서는_document_not_found다(pipeline: Pipeline) -> None:
    with pytest.raises(RequestError) as caught:
        await _document_report(pipeline, new_id())

    assert caught.value.code is ErrorCode.DOCUMENT_NOT_FOUND


async def test_지운_문서는_삭제됨_상태이고_색인_상태를_내지_않는다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    await pipeline.delete()

    report = await _document_report(pipeline, ingested.document_id)

    assert report.document.state is DocumentState.DELETED
    assert report.indexes == ()


async def test_건설_중인_판의_색인_상태도_판마다_따로_낸다(pipeline: Pipeline) -> None:
    ingested = await pipeline.ingest(휴가)
    await _work(pipeline)
    building = await pipeline.add_building_version()

    report = await _document_report(pipeline, ingested.document_id)

    assert [(i.version, i.state) for i in report.indexes] == [
        (IndexVersionStatus.CURRENT, IndexStateStatus.INDEXED),
        (IndexVersionStatus.BUILDING, None),
    ]
    assert building.status is IndexVersionStatus.BUILDING


async def test_문서_목록은_상태_그룹_키_필터를_따르고_없는_그룹은_빈_목록이다(
    pipeline: Pipeline,
) -> None:
    await pipeline.ingest(휴가, "휴가.docx")
    await pipeline.ingest(출장, "출장.docx")
    await _work(pipeline)
    await pipeline.delete("출장.docx")
    unit_of_work = pipeline.unit_of_work

    async def keys(
        *, state: DocumentState | None = None, group: str | None = None, key: str | None = None
    ) -> list[str]:
        reports = await list_document_reports(
            unit_of_work, state=state, group=group, key=key, limit=50, after=None
        )
        return [report.document.key for report in reports]

    assert await keys() == ["출장.docx", "휴가.docx"]
    assert await keys(state=DocumentState.DELETED) == ["출장.docx"]
    assert await keys(state=DocumentState.PARSED) == ["휴가.docx"]
    assert await keys(key="휴가.docx") == ["휴가.docx"]
    assert await keys(group="default") == ["출장.docx", "휴가.docx"]
    assert await keys(group="없는 그룹") == []
