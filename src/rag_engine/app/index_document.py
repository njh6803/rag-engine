"""`index_document` 작업의 유스케이스(명세 "수집 파이프라인과 작업", 티켓 07).

이 문서를 그 그룹이 든 모든 지식베이스의 살아 있는 색인 판에 맞춘다. 순서는 넷이다.

1. 작업 단위 하나에서 문서가 속한 원천 행을 공유 잠금으로, 이어서 문서 행을 잠그고 작업 행 조건을
   본 뒤, 지워진 문서이거나 지움 표시가 선 원천의 문서면 아무것도 하지 않고 성공으로 끝내고, 아니면
   세대를 올려 작업 행에 적는다. 그때의 내용 해시와 원본 경로를 기억한다.
2. 파싱 결과가 없거나, 파싱한 내용 해시가 다르거나, 파서 버전이 바뀌었으면 원본을 파싱해 파싱 결과
   행을 쓰고 문서 상태를 `parsed`로 쓴다.
3. 살아 있는 판을 대상 판으로 읽어 판마다 청킹, 토큰 세기, 임베딩, 키워드 토큰화를 한 뒤, 작업 단위
   하나에서 문서 행을 다시 잠그고 세대를 대조한다. 같을 때만 그 (문서, 판)의 옛 조각을 지우고 새
   조각과 색인 상태 `indexed`를 쓴다. 이 한 번의 작업 단위가 문서 단위 원자 교체(ADR 0008)다.
   토크나이저 판만 다른 건설 중인 판은 청킹과 임베딩 대신 현재 판의 조각을 복사하고 키워드만
   다시 만든다(`keyword_copy`). 건설 중인 판에 쓰면 같은 작업 단위에서 전환 검사를 부른다.
4. 작업을 `succeeded`로 끝낸다. 끝내는 일은 호출한 쪽(작업자)이 한다.

문서에 쓰는 작업 단위는 모두 문서 행을 먼저, 작업 행을 마지막에 잠근다. 작업 행 조건이 어긋나면
(작업 담당 기록의 기한이 끝나 다른 작업자가 가져갔다) `AttemptLostError`를 올려 그 작업 단위를
롤백한다. 세대가 첫째 단계에서 올린 값과 다르면(그사이 수집·삭제나 뒤에 시작한 작업이 세대를 올렸다)
문서에 쓰지 않고 성공으로 끝낸다. 새 상태는 세대를 올린 쪽이 맞춘다. 영구 실패는 예외다. 파싱의 영구
실패와 (셋째 단계에서 이미 알아낸) 임베딩의 영구 실패는 세대가 달라 문서와 색인에 쓰지 않을 때도 그
실패를 작업의 결과로 올리므로 작업은 `failed`로 끝난다(아래).

암호가 걸린 파일(파서가 `encrypted_document`로 알린다)과 색인할 글이 하나도 나오지 않는 파일(공백만
있는 것도 같다)은 실패가 아니라 건너뜀이다. 문서 상태를 `skipped`와 그 사유(`encrypted`,
`no_text`)로 쓰고, 대상 판마다 그 문서의 옛 조각을 지운 뒤 색인 상태를 `indexed`(조각 0개)로 쓰며,
건설 중인 판이면 전환 검사를 부르고, 작업은 `succeeded`로 끝난다(`_record_skipped`). 색인 상태를
`indexed`로 쓰는 것은 건너뜀 문서가 판 전환을 막지 않게 하려는 것이다(전환 조건은 모든 색인 상태가
`indexed`나 `failed`다). 오류 코드 `encrypted_document`는 문서, 색인 상태, 작업 행에 더는 쓰이지
않는다.

파싱이 그 밖의 이유로 영구 실패하면 둘째 단계가 문서와 색인에 그 실패를 적고
(`_record_permanent_failure`) 실패를 그대로 올려 작업자가 작업을 재시도 없이 `failed`로 끝낸다.
임베딩이 영구 실패한 판은 그 판만
`failed`로 쓰고(`mark_version_failed`) 남은 판을 끝까지 처리한 뒤 작업을 그 오류 코드로 끝낸다.
일시 실패는 그대로 올리고, 작업자가 `job_failure`로 다시 예약하거나 재시도를 다 썼으면 그쪽에서
끝낸다. 작업 담당 기록 연장은 작업자(`worker/processing.py`)가 이 유스케이스를 돌리는 동안 따로
한다.
"""

import asyncio
import hashlib
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

from rag_engine.app.index_failure import mark_version_failed
from rag_engine.app.job_attempt import hold_attempt
from rag_engine.app.keyword_copy import read_copy_sources, rebuild_keywords
from rag_engine.app.live_versions import live_index_versions
from rag_engine.app.retry_policy import RetryPolicy
from rag_engine.app.version_switch import check_version_switch
from rag_engine.domain.connectors import (
    ConnectorBrokenError,
    ConnectorCallBlockedError,
    ConnectorCallTimedOutError,
    ConnectorError,
    ConnectorFailureReason,
    ConnectorUnavailableError,
)
from rag_engine.domain.entities import (
    Block,
    Chunk,
    ChunkDraft,
    DocumentContent,
    DocumentStatus,
    IndexState,
    IndexStateStatus,
    IndexVersion,
    IndexVersionStatus,
    Job,
    JobStatus,
    SkipReason,
    StoredChunk,
)
from rag_engine.domain.errors import ErrorCode, PermanentFailure, TransientFailure
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.parsing import ParseRunner, ParserVersion
from rag_engine.domain.ports import (
    BlobStore,
    ChunkerFor,
    ConnectorRegistry,
    EmbedderFor,
    IndexMaintenance,
    JobOutcome,
    KeywordTokenizer,
    LockMode,
    UnitOfWork,
)

_MS_PER_SECOND = 1000.0


@dataclass(frozen=True, slots=True)
class IndexDocumentDeps:
    """유스케이스가 부르는 포트와 시계. `now`는 시각 칸에 쓸 지금이다. `maintenance`는 이
    유스케이스가 아니라 작업을 마친 뒤 물러난 판을 정리하는 작업자(`process_job`)가 쓴다."""

    unit_of_work: UnitOfWork
    blob_store: BlobStore
    parse_runner: ParseRunner
    embedder_for: EmbedderFor
    chunker_for: ChunkerFor
    tokenize_keywords: KeywordTokenizer
    now: Callable[[], datetime]
    retry: RetryPolicy
    maintenance: IndexMaintenance
    # 가져오는 원천의 문서는 원본을 그 원천의 커넥터로 읽는다. 호출 하나를 기다리는 한도다.
    connectors: ConnectorRegistry
    source_read_timeout_seconds: float
    # 동기화가 읽은 파일의 크기 상한. 수집 API와 같은 값이다.
    max_upload_bytes: int
    # 정리 작업이 쓰는 보관 기간(날수). 지운 문서와 원천, 끝난 동기화 기록에 각각 적용한다.
    deleted_retention_days: int
    sync_record_retention_days: int


@dataclass(frozen=True, slots=True)
class IndexTimings:
    """단계별 지연(밀리초). 작업자 로그의 `job_finished`가 싣는다."""

    parse_ms: float
    embedding_ms: float
    write_ms: float


@dataclass(frozen=True, slots=True)
class IndexResult:
    """작업이 끝난 모양과 지연. 세대 대조에 걸려 문서에 쓰지 않았어도 `succeeded`다. 작업의 상태는
    그 작업이 끝난 모양이지 문서의 색인 결과가 아니다."""

    outcome: JobOutcome
    timings: IndexTimings


@dataclass(frozen=True, slots=True)
class _Claim:
    """첫째 단계가 기억한 값. 둘째와 셋째 단계가 이 값으로 일하고 세대를 대조한다."""

    generation: int
    content_hash: str
    # 가져오는 원천의 문서는 비어 있고, 그때는 그 원천의 커넥터로 원본을 읽는다.
    blob_path: str | None
    mime: str
    group_id: UUID
    source_id: UUID
    key: str


@dataclass(slots=True)
class IndexTimer:
    """단계별 지연을 쌓는다. 실패로 끝난 시도도 그때까지의 지연을 남기도록 부르는 쪽이 만들어
    건넨다."""

    parse_ms: float = 0.0
    embedding_ms: float = 0.0
    write_ms: float = 0.0

    def timings(self) -> IndexTimings:
        return IndexTimings(self.parse_ms, self.embedding_ms, self.write_ms)

    def result(self, failure: ErrorCode | None = None) -> IndexResult:
        status = JobStatus.SUCCEEDED if failure is None else JobStatus.FAILED
        return IndexResult(outcome=JobOutcome(status, failure), timings=self.timings())


@dataclass(frozen=True, slots=True)
class _Prepared:
    """판 하나에 쓸 조각의 재료. 청킹이 낸 조각과 그 임베딩, 키워드 글."""

    version: IndexVersion
    drafts: list[ChunkDraft]
    embeddings: list[tuple[float, ...]]
    keyword_texts: list[str]


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * _MS_PER_SECOND


async def index_document(
    deps: IndexDocumentDeps, job: Job, timer: IndexTimer | None = None
) -> IndexResult:
    """`timer`를 주면 예외로 끝난 시도의 지연도 부른 쪽이 그 timer에서 읽는다."""
    timer = timer or IndexTimer()
    claim = await _raise_generation(deps, job)
    if claim is None:
        return timer.result()
    content = await _ensure_parsed(deps, job, claim, timer)
    if content is None:
        return timer.result()
    if not _has_text(content):
        await _record_skipped(deps, job, claim, SkipReason.NO_TEXT)
        return timer.result()
    failure = await _replace_chunks(deps, job, claim, content, timer)
    return timer.result(failure)


def _has_text(content: DocumentContent) -> bool:
    """색인할 글이 있는가. 공백만 있는 블록은 글로 세지 않는다."""
    return any(block.text.strip() for block in content.blocks)


async def _raise_generation(deps: IndexDocumentDeps, job: Job) -> _Claim | None:
    """첫째 단계. 지워진 문서이거나 지운 원천의 문서면 `None`이다. 잠금 순서(원천 행, 문서 행, 작업
    행)를 지키려고 문서가 속한 원천을 먼저 읽어 공유 잠금으로 잡는다. 문서의 원천은 바뀌지
    않는다."""
    async with deps.unit_of_work.begin() as transaction:
        peeked = await transaction.documents.get(job.index_document_id)
        source = (
            None
            if peeked is None
            else await transaction.catalog.lock_source_shared(peeked.source_id)
        )
        document = await transaction.documents.lock(job.index_document_id)
        await hold_attempt(transaction, job)
        if document is None or document.deleted_at is not None or document.purged_at is not None:
            return None
        if source is not None and source.deleted_at is not None:
            return None
        generation = document.generation + 1
        await transaction.documents.update(
            replace(document, generation=generation, modified_at=deps.now())
        )
        await transaction.jobs.record_raised_generation(job, generation)
        return _Claim(
            generation=generation,
            content_hash=document.content_hash,
            blob_path=document.blob_path,
            mime=document.mime,
            group_id=document.group_id,
            source_id=document.source_id,
            key=document.key,
        )


async def _ensure_parsed(
    deps: IndexDocumentDeps, job: Job, claim: _Claim, timer: IndexTimer
) -> DocumentContent | None:
    """둘째 단계. 세대 대조에 걸리거나 암호가 걸린 파일이라 건너뛰었으면 `None`이다."""
    async with deps.unit_of_work.begin() as transaction:
        saved = await transaction.documents.get_content(job.index_document_id)
    if saved is not None and _is_reusable(
        saved, claim.content_hash, deps.parse_runner.current_version(claim.mime)
    ):
        return saved
    started = time.perf_counter()
    try:
        return await _parse_and_save(deps, job, claim)
    finally:
        timer.parse_ms += _elapsed_ms(started)


async def _read_original(deps: IndexDocumentDeps, claim: _Claim) -> bytes:
    """원본 바이트를 낸다. 파일 저장소에 복사해 둔 문서는 거기서 읽고, 원본 경로가 빈 문서(가져오는
    원천의 문서)는 그 원천의 커넥터로 읽는다. 목록을 받은 뒤에 원천이 바뀐 것(그 키의 파일이 없거나
    크기 상한을 넘거나 내용 해시가 다르다)은 `source_changed`(영구 실패)이고, 원천을 읽을 수 없거나
    한도까지 돌아오지 않거나 커넥터를 만들지 못한 것은 `source_unreadable`(일시 실패)이다. 예외의
    글과 키는 싣지 않는다(원칙 V)."""
    if claim.blob_path is not None:
        return await deps.blob_store.read(claim.blob_path)
    async with deps.unit_of_work.begin() as transaction:
        source = await transaction.catalog.get_source_by_id(claim.source_id)
    if source is None or source.connector is None or source.config is None:
        raise TransientFailure(ErrorCode.SOURCE_UNREADABLE, "원천을 읽을 수 없다")
    try:
        reader = deps.connectors.open_reader(
            source.connector,
            source.config,
            source=source.name,
            timeout_seconds=deps.source_read_timeout_seconds,
        )
        fetched = await reader.fetch(claim.key)
    except ConnectorError as error:
        if error.reason in (ConnectorFailureReason.NOT_FOUND, ConnectorFailureReason.TOO_LARGE):
            raise PermanentFailure(ErrorCode.SOURCE_CHANGED, "원천이 바뀌었다") from None
        raise TransientFailure(ErrorCode.SOURCE_UNREADABLE, "원천을 읽을 수 없다") from None
    except (
        ConnectorUnavailableError,
        ConnectorCallTimedOutError,
        ConnectorCallBlockedError,
        ConnectorBrokenError,
    ):
        raise TransientFailure(ErrorCode.SOURCE_UNREADABLE, "원천을 읽을 수 없다") from None
    if len(fetched.data) > deps.max_upload_bytes:
        # 동기화 뒤에 운영자가 상한을 낮췄을 수 있고, 커넥터가 제 상한을 지킨다는 보장은 없다.
        raise PermanentFailure(ErrorCode.SOURCE_CHANGED, "원천이 바뀌었다")
    digest = await asyncio.to_thread(lambda: hashlib.sha256(fetched.data).hexdigest())
    if digest != claim.content_hash:
        raise PermanentFailure(ErrorCode.SOURCE_CHANGED, "원천이 바뀌었다")
    return fetched.data


async def _parse_and_save(
    deps: IndexDocumentDeps, job: Job, claim: _Claim
) -> DocumentContent | None:
    """원본을 읽어 파싱하고 결과를 쓴다. 어떻게 끝나든 호출한 쪽이 걸린 시간을 `parse_ms`에
    더한다."""
    try:
        data = await _read_original(deps, claim)
    except PermanentFailure as failure:
        await _record_permanent_failure(deps, job, claim, failure)
        raise
    try:
        parsed = await deps.parse_runner.parse(data, claim.mime)
    except PermanentFailure as failure:
        if failure.code is ErrorCode.ENCRYPTED_DOCUMENT:
            await _record_skipped(deps, job, claim, SkipReason.ENCRYPTED)
            return None
        await _record_permanent_failure(deps, job, claim, failure)
        raise
    content = DocumentContent(
        document_id=job.index_document_id,
        parser_name=parsed.parser_name,
        parser_interface_version=parsed.interface_version,
        parser_library_version=parsed.library_version,
        blocks=parsed.blocks,
        parsed_content_hash=claim.content_hash,
        text_hash=_text_hash(parsed.blocks),
        parsed_at=deps.now(),
    )
    async with deps.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(job.index_document_id)
        await hold_attempt(transaction, job)
        if document is None or document.generation != claim.generation:
            return None
        await transaction.documents.save_content(content)
        await transaction.documents.update(
            replace(
                document,
                status=DocumentStatus.PARSED,
                error_code=None,
                skip_reason=None,
                modified_at=deps.now(),
            )
        )
    return content


async def _record_skipped(
    deps: IndexDocumentDeps, job: Job, claim: _Claim, reason: SkipReason
) -> None:
    """문서를 건너뜀으로 적는다. 세대가 같을 때만 문서 상태를 `skipped`와 사유로 쓰고, 살아 있는
    판마다 그 문서의 옛 조각을 지우고 색인 상태 `indexed`(조각 0개)를 쓴다. 옛 조각을 두면 지금
    내용과 다른 글이 검색에 남는다. 건설 중인 판이면 전환 검사를 부른다. 세대가 다르면 새 내용을
    맡은 쪽이 문서를 맞추므로 아무것도 건드리지 않는다. 잠금 순서는 `_record_permanent_failure`와
    같다."""
    async with deps.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(job.index_document_id)
        versions = await live_index_versions(transaction, claim.group_id)
        building = sorted(
            {v.knowledge_base_id for v in versions if v.status is IndexVersionStatus.BUILDING}
        )
        await transaction.catalog.lock_knowledge_bases(building, LockMode.UPDATE)
        await hold_attempt(transaction, job)
        if document is None or document.generation != claim.generation:
            return
        await transaction.documents.update(
            replace(
                document,
                status=DocumentStatus.SKIPPED,
                error_code=None,
                skip_reason=reason,
                modified_at=deps.now(),
            )
        )
        for version in versions:
            await transaction.index.delete_chunks(document.id, version.id)
            await transaction.index.save_state(
                IndexState(
                    document_id=document.id,
                    index_version_id=version.id,
                    status=IndexStateStatus.INDEXED,
                    chunk_count=0,
                    built_content_hash=document.content_hash,
                    error_code=None,
                    updated_at=deps.now(),
                )
            )
            if version.status is IndexVersionStatus.BUILDING:
                await check_version_switch(transaction, version)


async def _record_permanent_failure(
    deps: IndexDocumentDeps, job: Job, claim: _Claim, failure: PermanentFailure
) -> None:
    """파싱의 영구 실패를 문서와 색인에 적는다. 세대가 같을 때만 문서 상태를 `failed`와 그 코드로
    쓰고, 살아 있는 판마다 그 문서의 조각을 지우고 색인 상태 `failed`를 쓴다. 옛 조각을 두면 지금
    내용과 다른 글이 검색에 남는다. 세대가 다르면 새 내용을 맡은 쪽이 문서를 맞추므로 문서도 조각도
    색인 상태도 건드리지 않는다. 호출한 쪽이 실패를 다시 올려 작업이 재시도 없이 `failed`로
    끝난다."""
    async with deps.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(job.index_document_id)
        versions = await live_index_versions(transaction, claim.group_id)
        # 건설 중인 판에 쓰면 `mark_version_failed`가 전환 검사로 그 지식베이스 행을 `FOR UPDATE`로
        # 잠그므로, 잠금 순서(문서 행, 지식베이스 행, 작업 행)를 지키려고 건설 중인 판이 든
        # 지식베이스만 작업 행 앞에서 ID 순으로 잠근다. 읽은 뒤에 판이 바뀌어도 전환 검사가
        # 잠근 채로 판을 다시 읽으므로 이 목록으로 충분하다.
        building = sorted(
            {v.knowledge_base_id for v in versions if v.status is IndexVersionStatus.BUILDING}
        )
        await transaction.catalog.lock_knowledge_bases(building, LockMode.UPDATE)
        await hold_attempt(transaction, job)
        if document is None or document.generation != claim.generation:
            return
        await transaction.documents.update(
            replace(
                document,
                status=DocumentStatus.FAILED,
                error_code=failure.code,
                skip_reason=None,
                modified_at=deps.now(),
                # 원천이 목록 뒤에 바뀐 것을 알았으므로 다음 동기화가 그 파일을 다시 읽게 비운다.
                change_marker=(
                    None if failure.code is ErrorCode.SOURCE_CHANGED else document.change_marker
                ),
            )
        )
        for version in versions:
            await mark_version_failed(transaction, document.id, version, failure.code, deps.now())


def _is_reusable(saved: DocumentContent, content_hash: str, current: ParserVersion | None) -> bool:
    """저장된 파싱 결과를 다시 쓸 수 있는가. 파싱한 내용이 같고 파서 버전도 같아야 한다."""
    return (
        current is not None
        and saved.parsed_content_hash == content_hash
        and (saved.parser_name, saved.parser_interface_version, saved.parser_library_version)
        == (current.parser_name, current.interface_version, current.library_version)
    )


def _text_hash(blocks: Sequence[Block]) -> str:
    return hashlib.sha256("\n".join(block.text for block in blocks).encode()).hexdigest()


async def _replace_chunks(
    deps: IndexDocumentDeps, job: Job, claim: _Claim, content: DocumentContent, timer: IndexTimer
) -> ErrorCode | None:
    """셋째 단계. 판마다 재료를 만든 뒤 작업 단위 하나에서 세대를 대조하고 모두 바꾼다. 어느 판의
    임베딩이 영구 실패했으면 그 판의 계산은 건너뛰고 남은 판을 이어 가며, 마지막 영구 실패의 코드를
    낸다(작업이 그 코드로 `failed`가 된다). 남은 판에서 일시 실패가 나면 아무것도 쓰기 전에 그
    예외가 올라가 시도 전체가 일시 실패다."""
    async with deps.unit_of_work.begin() as transaction:
        versions = await live_index_versions(transaction, claim.group_id)
        copies = await read_copy_sources(
            transaction, versions, job.index_document_id, claim.content_hash
        )
    started = time.perf_counter()
    prepared: list[_Prepared] = []
    rejected: list[tuple[IndexVersion, ErrorCode]] = []
    try:
        for version in versions:
            try:
                prepared.append(
                    await _prepare(deps, version, content.blocks, copies.get(version.id))
                )
            except PermanentFailure as failure:
                rejected.append((version, failure.code))
    finally:
        timer.embedding_ms += _elapsed_ms(started)
    failure_code = rejected[-1][1] if rejected else None
    building = {
        version.knowledge_base_id
        for version in [material.version for material in prepared] + [v for v, _ in rejected]
        if version.status is IndexVersionStatus.BUILDING
    }

    started = time.perf_counter()
    try:
        async with deps.unit_of_work.begin() as transaction:
            document = await transaction.documents.lock(job.index_document_id)
            # 건설 중인 판에 쓰면 전환 검사가 그 지식베이스 행을 `FOR UPDATE`로 잠그므로, 작업 행
            # 앞에서 먼저 잠근다(잠금 순서는 문서 행, 지식베이스 행, 작업 행이다). 건설 중인 판이
            # 없으면 잠그지 않아 평소의 색인 쓰기가 지식베이스 행에서 줄을 서지 않는다.
            await transaction.catalog.lock_knowledge_bases(sorted(building), LockMode.UPDATE)
            await hold_attempt(transaction, job)
            if document is None or document.generation != claim.generation:
                return failure_code
            if document.status is not DocumentStatus.PARSED:
                await transaction.documents.update(
                    replace(
                        document,
                        status=DocumentStatus.PARSED,
                        error_code=None,
                        skip_reason=None,
                        modified_at=deps.now(),
                    )
                )
            for version, code in rejected:
                await mark_version_failed(transaction, document.id, version, code, deps.now())
            for material in prepared:
                chunks = [
                    Chunk(
                        id=new_id(),
                        document_id=document.id,
                        index_version_id=material.version.id,
                        ordinal=ordinal,
                        text=draft.text,
                        token_count=draft.token_count,
                        location=draft.location,
                        embedding=material.embeddings[ordinal],
                        keyword_text=material.keyword_texts[ordinal],
                        source_content_hash=document.content_hash,
                        group_id=document.group_id,
                        updated_at=document.updated_at,
                        effective_date=document.effective_date,
                        access_groups=document.access_groups,
                    )
                    for ordinal, draft in enumerate(material.drafts)
                ]
                await transaction.index.replace_chunks(document.id, material.version.id, chunks)
                await transaction.index.save_state(
                    IndexState(
                        document_id=document.id,
                        index_version_id=material.version.id,
                        status=IndexStateStatus.INDEXED,
                        chunk_count=len(chunks),
                        built_content_hash=document.content_hash,
                        error_code=None,
                        updated_at=deps.now(),
                    )
                )
                if material.version.status is IndexVersionStatus.BUILDING:
                    await check_version_switch(transaction, material.version)
    finally:
        timer.write_ms += _elapsed_ms(started)
    return failure_code


async def _prepare(
    deps: IndexDocumentDeps,
    version: IndexVersion,
    blocks: Sequence[Block],
    copied: Sequence[StoredChunk] | None,
) -> _Prepared:
    """판에 적힌 청킹 설정으로 자르고, 판에 적힌 끝점·모델·차원으로 임베딩한다. 임베딩과 키워드에는
    청커가 지은 `index_text`를 그대로 쓴다(줄인 절 경로는 토큰 수로 정해져 `location`만으로는 되짓지
    못한다). 현재 판에서 복사해 올 조각이 있으면(토크나이저 판만 다른 건설 중인 판) 청킹과 임베딩을
    하지 않고 키워드만 다시 만든다."""
    embedder = deps.embedder_for(version)
    if copied is not None:
        material = await rebuild_keywords(embedder, deps.tokenize_keywords, version, copied)
        return _Prepared(version, material.drafts, material.embeddings, material.keyword_texts)
    drafts = await deps.chunker_for(version.chunking.strategy).chunk(
        blocks, version.chunking, embedder
    )
    index_texts = [draft.index_text for draft in drafts]
    embeddings = await embedder.embed(index_texts) if index_texts else []
    keyword_texts = [" ".join(deps.tokenize_keywords(text)) for text in index_texts]
    return _Prepared(version, drafts, embeddings, keyword_texts)
