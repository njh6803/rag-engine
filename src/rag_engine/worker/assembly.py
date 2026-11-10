"""작업자의 조립(명세 "층, 패키지, 조립"). 설정에서 어댑터를 만들어 유스케이스에 건넨다.

`run_once_with_settings`는 설정에 적힌 데이터베이스에 붙어 꺼낼 수 있는 작업을 모두 처리하고
돌아온다. Kiwi 모델 적재(약 1초)는 첫 작업이 이벤트 루프를 멈추지 않게 조립할 때 미리 한다. 청커의
문장 분리와 키워드 토큰화는 동기 함수이고 CPU를 쓰며 이벤트 루프 안에서 그대로 부른다(Kiwi 호출은
어댑터가 잠금으로 직렬화한다). 큰 문서를 처리하는 동안 같은 이벤트 루프의 임대 연장이 멈출 수 있다는
점은 13이 본다.
"""

import os
import socket
from datetime import UTC, datetime

import httpx

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.adapters.chunking import chunker_for
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.log_format import configure_logging
from rag_engine.adapters.parsers.registry import ParserRegistry, discover_parser_specs
from rag_engine.adapters.parsers.runner import SubprocessParseRunner
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.settings import Settings
from rag_engine.adapters.tei import TeiEmbedderPool
from rag_engine.app.index_document import IndexDocumentDeps
from rag_engine.worker.processing import run_once


def worker_id() -> str:
    """작업자 ID는 호스트 이름과 PID다."""
    return f"{socket.gethostname()}-{os.getpid()}"


async def run_once_with_settings(settings: Settings) -> int:
    """꺼낼 수 있는 작업을 모두 처리하고 처리한 수를 낸다. 작업자는 서버 없이 따로 돌 수 있어 로깅을
    여기서 설정한다."""
    configure_logging(settings.log_format)
    engine = create_engine(settings.database_url)
    embedders = TeiEmbedderPool(
        lambda endpoint: httpx.AsyncClient(base_url=endpoint, timeout=settings.tei_timeout_seconds),
        batch_size=settings.tei_batch_size,
    )
    tokenize_keywords("준비")
    deps = IndexDocumentDeps(
        unit_of_work=PostgresUnitOfWork(engine),
        blob_store=LocalBlobStore(settings.data_dir),
        parse_runner=SubprocessParseRunner(
            ParserRegistry(discover_parser_specs()),
            timeout_seconds=settings.parse_timeout_seconds,
            memory_mb=settings.parse_memory_mb,
            max_pages=settings.parse_max_pages,
            max_text_mb=settings.parse_max_text_mb,
        ),
        embedder_for=embedders,
        chunker_for=chunker_for,
        tokenize_keywords=tokenize_keywords,
        now=lambda: datetime.now(UTC),
    )
    try:
        return await run_once(
            deps, worker_id=worker_id(), lease_seconds=float(settings.job_lease_seconds)
        )
    finally:
        await embedders.aclose()
        await engine.dispose()
