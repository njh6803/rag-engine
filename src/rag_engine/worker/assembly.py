"""작업자의 조립(명세 "층, 패키지, 조립"). 설정에서 어댑터를 만들어 유스케이스에 건넨다.

`run_once_with_settings`는 설정에 적힌 데이터베이스에 붙어 꺼낼 수 있는 작업을 모두 처리하고
돌아온다. `run_worker`는 종료 신호를 받을 때까지 상시로 돈다(`rag-engine worker`). 둘이 같은
조립(`_assembled`)을 거친다. Kiwi 모델 적재(수 초)는 첫 작업이 이벤트 루프를 멈추지 않게 조립할 때
미리 한다. 청커의 문장 분리와 키워드 토큰화는 동기 함수이고 CPU를 쓰며 이벤트 루프 안에서 그대로
부른다(Kiwi 호출은 어댑터가 잠금으로 직렬화해 스레드로 넘겨도 속도가 늘지 않는다). 큰 문서에서는 그
동안 같은 이벤트 루프의 임대 연장이 늦을 수 있으나, 임대를 잃은 시도는 작업 행 조건에 걸려 쓰지
못하므로 데이터는 어긋나지 않는다. 다만 인수마다 시도 횟수가 오르므로, 임대보다 오래 루프를 막는
문서는 인수가 되풀이되다 `worker_lost`로 끝날 수 있다.
"""

import asyncio
import os
import socket
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import UTC, datetime
from typing import Final

import httpx

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.adapters.chunking import chunker_for
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.log_format import configure_logging
from rag_engine.adapters.parsers.registry import ParserRegistry, discover_parser_specs
from rag_engine.adapters.parsers.runner import SubprocessParseRunner
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.index_maintenance import PostgresIndexMaintenance
from rag_engine.adapters.postgres.notifications import JobNotificationListener
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.settings import Settings
from rag_engine.adapters.tei import TeiEmbedderPool
from rag_engine.app.index_document import IndexDocumentDeps
from rag_engine.app.retry_policy import RetryPolicy
from rag_engine.worker.processing import run_once
from rag_engine.worker.service import WorkerConfig, serve
from rag_engine.worker.signals import stop_on_signals

# 슬롯 하나가 동시에 쥐는 연결의 수. 처리하는 작업 단위 하나와 임대 연장 하나다.
_CONNECTIONS_PER_SLOT: Final = 2


def worker_id() -> str:
    """작업자 ID는 호스트 이름과 PID다."""
    return f"{socket.gethostname()}-{os.getpid()}"


async def run_once_with_settings(settings: Settings) -> int:
    """꺼낼 수 있는 작업을 모두 처리하고 처리한 수를 낸다."""
    async with _assembled(settings) as deps:
        return await run_once(
            deps, worker_id=worker_id(), lease_seconds=float(settings.job_lease_seconds)
        )


async def run_worker(settings: Settings) -> int:
    """종료 신호를 받을 때까지 상시로 작업을 꺼내 처리한다. 신호를 받으면 새 작업을 꺼내지 않고
    진행 중인 작업을 끝낸 뒤 0으로 돌아온다. 메인 스레드의 이벤트 루프 안에서만 부를 수 있다."""
    config = WorkerConfig(
        worker_id=worker_id(),
        lease_seconds=float(settings.job_lease_seconds),
        concurrency=settings.worker_concurrency,
        poll_seconds=float(settings.worker_poll_seconds),
    )
    stop = asyncio.Event()
    # 조립(Kiwi 예열이 수 초 걸린다) 중에 온 신호도 놓치지 않으려고 신호 처리기를 먼저 단다.
    with stop_on_signals(stop):
        async with _assembled(settings) as deps:
            await serve(
                deps, config, stop=stop, listener=JobNotificationListener(settings.database_url)
            )
    return 0


@asynccontextmanager
async def _assembled(settings: Settings) -> AsyncGenerator[IndexDocumentDeps]:
    """설정에서 어댑터를 만들어 유스케이스에 건넬 묶음을 낸다. 작업자는 서버 없이 따로 돌 수 있어
    로깅을 여기서 설정한다. 블록을 나가면 TEI 클라이언트와 엔진을 닫는다."""
    configure_logging(settings.log_format)
    engine = create_engine(
        settings.database_url,
        at_least_connections=settings.worker_concurrency * _CONNECTIONS_PER_SLOT,
    )
    embedders = TeiEmbedderPool(
        lambda endpoint: httpx.AsyncClient(base_url=endpoint, timeout=settings.tei_timeout_seconds),
        batch_size=settings.tei_batch_size,
    )
    tokenize_keywords("준비")
    deps = IndexDocumentDeps(
        unit_of_work=PostgresUnitOfWork(engine),
        maintenance=PostgresIndexMaintenance(engine),
        blob_store=LocalBlobStore(settings.data_dir),
        parse_runner=SubprocessParseRunner(
            ParserRegistry(discover_parser_specs()),
            timeout_seconds=settings.parse_timeout_seconds,
            memory_mb=settings.parse_memory_mb,
            max_pages=settings.parse_max_pages,
            max_text_mb=settings.parse_max_text_mb,
            max_unzipped_mb=settings.parse_max_unzipped_mb,
            max_compression_ratio=settings.parse_max_compression_ratio,
        ),
        embedder_for=embedders,
        chunker_for=chunker_for,
        tokenize_keywords=tokenize_keywords,
        now=lambda: datetime.now(UTC),
        retry=RetryPolicy(
            max_attempts=settings.job_max_attempts,
            backoff_base_seconds=settings.job_backoff_base_seconds,
        ),
    )
    try:
        yield deps
    finally:
        await embedders.aclose()
        await engine.dispose()
