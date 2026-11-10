"""`index_document` 작업의 유스케이스(명세 "수집 파이프라인과 작업", 티켓 07).

이 문서를 그 그룹이 든 모든 지식베이스의 살아 있는 색인 판에 맞춘다. 순서는 넷이다.

1. 작업 단위 하나에서 문서 행을 잠그고 작업 행 조건을 본 뒤, 지워진 문서면 아무것도 하지 않고
   성공으로 끝내고, 아니면 세대를 올려 작업 행에 적는다. 그때의 내용 해시와 원본 경로를 기억한다.
2. 파싱 결과가 없거나, 파싱한 내용 해시가 다르거나, 파서의 판이 바뀌었으면 원본을 파싱해 파싱 결과
   행을 쓰고 문서 상태를 `parsed`로 쓴다.
3. 살아 있는 판을 대상 판으로 읽어 판마다 청킹, 토큰 세기, 임베딩, 키워드 토큰화를 한 뒤, 작업 단위
   하나에서 문서 행을 다시 잠그고 세대를 대조한다. 같을 때만 그 (문서, 판)의 옛 조각을 지우고 새
   조각과 색인 상태 `indexed`를 쓴다. 이 한 번의 작업 단위가 문서 단위 원자 교체(ADR 0008)다.
4. 작업을 `succeeded`로 끝낸다. 끝내는 일은 호출한 쪽(작업자)이 한다.

문서에 쓰는 작업 단위는 모두 문서 행을 먼저, 작업 행을 마지막에 잠근다. 작업 행 조건이 어긋나면
(임대가 끝나 다른 작업자가 가져갔다) `AttemptLostError`를 올려 그 작업 단위를 롤백한다. 세대가
첫째 단계에서 올린 값과 다르면(그사이 수집·삭제나 뒤에 시작한 작업이 세대를 올렸다) 문서에 쓰지
않고 성공으로 끝낸다. 새 상태는 세대를 올린 쪽이 맞춘다.

실패 분류와 재시도(12), 파싱의 영구 실패 종결(08), 전환 검사(14), 임대 연장(13)은 뒤 티켓이 채운다.
이 모듈은 영구·일시 실패 예외를 그대로 올리고 작업자가 작업을 `failed`로 끝낸다.
"""

import hashlib
import time
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from datetime import datetime
from uuid import UUID

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
)
from rag_engine.domain.errors import AttemptLostError
from rag_engine.domain.identifiers import new_id
from rag_engine.domain.parsing import ParseRunner, ParserVersion
from rag_engine.domain.ports import (
    BlobStore,
    ChunkerFor,
    EmbedderFor,
    JobOutcome,
    KeywordTokenizer,
    Transaction,
    UnitOfWork,
)

_MS_PER_SECOND = 1000.0


@dataclass(frozen=True, slots=True)
class IndexDocumentDeps:
    """유스케이스가 부르는 포트와 시계. `now`는 시각 칸에 쓸 지금이다."""

    unit_of_work: UnitOfWork
    blob_store: BlobStore
    parse_runner: ParseRunner
    embedder_for: EmbedderFor
    chunker_for: ChunkerFor
    tokenize_keywords: KeywordTokenizer
    now: Callable[[], datetime]


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
    blob_path: str
    mime: str
    group_id: UUID


@dataclass(slots=True)
class _Timer:
    parse_ms: float = 0.0
    embedding_ms: float = 0.0
    write_ms: float = 0.0

    def result(self) -> IndexResult:
        return IndexResult(
            outcome=JobOutcome(JobStatus.SUCCEEDED, None),
            timings=IndexTimings(self.parse_ms, self.embedding_ms, self.write_ms),
        )


@dataclass(frozen=True, slots=True)
class _Prepared:
    """판 하나에 쓸 조각의 재료. 청킹이 낸 조각과 그 임베딩, 키워드 글."""

    version: IndexVersion
    drafts: list[ChunkDraft]
    embeddings: list[tuple[float, ...]]
    keyword_texts: list[str]


def _elapsed_ms(started: float) -> float:
    return (time.perf_counter() - started) * _MS_PER_SECOND


async def index_document(deps: IndexDocumentDeps, job: Job) -> IndexResult:
    timer = _Timer()
    claim = await _raise_generation(deps, job)
    if claim is None:
        return timer.result()
    content = await _ensure_parsed(deps, job, claim, timer)
    if content is None:
        return timer.result()
    await _replace_chunks(deps, job, claim, content, timer)
    return timer.result()


async def _raise_generation(deps: IndexDocumentDeps, job: Job) -> _Claim | None:
    """첫째 단계. 지워진 문서면 `None`이다."""
    async with deps.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(job.document_id)
        await _hold(transaction, job)
        if document is None or document.deleted_at is not None or document.purged_at is not None:
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
        )


async def _hold(transaction: Transaction, job: Job) -> None:
    if not await transaction.jobs.hold_attempt(job):
        raise AttemptLostError


async def _ensure_parsed(
    deps: IndexDocumentDeps, job: Job, claim: _Claim, timer: _Timer
) -> DocumentContent | None:
    """둘째 단계. 세대 대조에 걸리면 `None`이다."""
    async with deps.unit_of_work.begin() as transaction:
        saved = await transaction.documents.get_content(job.document_id)
    if saved is not None and _is_reusable(
        saved, claim.content_hash, deps.parse_runner.current_version(claim.mime)
    ):
        return saved
    started = time.perf_counter()
    data = await deps.blob_store.read(claim.blob_path)
    parsed = await deps.parse_runner.parse(data, claim.mime)
    content = DocumentContent(
        document_id=job.document_id,
        parser_name=parsed.parser_name,
        parser_interface_version=parsed.interface_version,
        parser_library_version=parsed.library_version,
        blocks=parsed.blocks,
        parsed_content_hash=claim.content_hash,
        text_hash=_text_hash(parsed.blocks),
        parsed_at=deps.now(),
    )
    async with deps.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(job.document_id)
        await _hold(transaction, job)
        if document is None or document.generation != claim.generation:
            timer.parse_ms += _elapsed_ms(started)
            return None
        await transaction.documents.save_content(content)
        await transaction.documents.update(
            replace(
                document,
                status=DocumentStatus.PARSED,
                error_code=None,
                modified_at=deps.now(),
            )
        )
    timer.parse_ms += _elapsed_ms(started)
    return content


def _is_reusable(saved: DocumentContent, content_hash: str, current: ParserVersion | None) -> bool:
    """저장된 파싱 결과를 다시 쓸 수 있는가. 파싱한 내용이 같고 파서의 판도 같아야 한다."""
    return (
        current is not None
        and saved.parsed_content_hash == content_hash
        and (saved.parser_name, saved.parser_interface_version, saved.parser_library_version)
        == (current.parser_name, current.interface_version, current.library_version)
    )


def _text_hash(blocks: Sequence[Block]) -> str:
    return hashlib.sha256("\n".join(block.text for block in blocks).encode()).hexdigest()


async def _replace_chunks(
    deps: IndexDocumentDeps, job: Job, claim: _Claim, content: DocumentContent, timer: _Timer
) -> None:
    """셋째 단계. 판마다 재료를 만든 뒤 작업 단위 하나에서 세대를 대조하고 모두 바꾼다."""
    async with deps.unit_of_work.begin() as transaction:
        versions = await _live_versions(transaction, claim.group_id)
    started = time.perf_counter()
    prepared = [await _prepare(deps, version, content.blocks) for version in versions]
    timer.embedding_ms += _elapsed_ms(started)

    started = time.perf_counter()
    async with deps.unit_of_work.begin() as transaction:
        document = await transaction.documents.lock(job.document_id)
        await _hold(transaction, job)
        if document is None or document.generation != claim.generation:
            return
        if document.status is not DocumentStatus.PARSED:
            await transaction.documents.update(
                replace(
                    document,
                    status=DocumentStatus.PARSED,
                    error_code=None,
                    modified_at=deps.now(),
                )
            )
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
                await _check_version_switch(transaction, material.version)
    timer.write_ms += _elapsed_ms(started)


async def _live_versions(transaction: Transaction, group_id: UUID) -> list[IndexVersion]:
    """그 그룹이 든 모든 지식베이스의 현재 판과 건설 중인 판."""
    versions: list[IndexVersion] = []
    for knowledge_base in await transaction.catalog.list_knowledge_bases_of_group(group_id):
        versions.extend(await transaction.catalog.list_live_index_versions(knowledge_base.id))
    return versions


async def _prepare(
    deps: IndexDocumentDeps, version: IndexVersion, blocks: Sequence[Block]
) -> _Prepared:
    """판에 적힌 청킹 설정으로 자르고, 판에 적힌 끝점·모델·차원으로 임베딩한다. 임베딩과 키워드에는
    청커가 지은 `index_text`를 그대로 쓴다(절 경로가 상한을 넘어 줄었으면 `location`으로 되지을 수
    없다)."""
    embedder = deps.embedder_for(version)
    drafts = await deps.chunker_for(version.chunking.strategy).chunk(
        blocks, version.chunking, embedder
    )
    index_texts = [draft.index_text for draft in drafts]
    embeddings = await embedder.embed(index_texts) if index_texts else []
    keyword_texts = [" ".join(deps.tokenize_keywords(text)) for text in index_texts]
    return _Prepared(version, drafts, embeddings, keyword_texts)


async def _check_version_switch(transaction: Transaction, version: IndexVersion) -> None:
    """색인 상태를 쓴 뒤 그 판이 건설 중이면 하는 전환 검사의 자리다. 지식베이스 행을 잠그고 그 판의
    모든 색인 상태가 `indexed`나 `failed`면 판을 전환한다. 14가 채운다."""
