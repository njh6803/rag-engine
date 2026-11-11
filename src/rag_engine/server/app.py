"""HTTP 표면을 짓는다. REST 와 MCP 를 한 FastAPI 앱이 연다(ADR 0005).

`create_app`이 설정 객체를 받아 엔진, 작업 단위, 어댑터를 만들고 REST 경로와 MCP 하위 앱을 붙인다.
앱 바깥에 순수 ASGI 미들웨어 둘(요청 문맥, 인증)을 씌운다(명세 "층, 패키지, 조립", ADR 0014).
"""

import asyncio
import logging
from collections.abc import AsyncGenerator, Sequence
from contextlib import asynccontextmanager

import httpx
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from mcp.server import MCPServer
from mcp.server.transport_security import TransportSecuritySettings
from starlette.responses import JSONResponse
from starlette.types import ASGIApp

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.log_format import configure_logging, log_event
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.token_store import PostgresTokenStore
from rag_engine.adapters.postgres.unit_of_work import PostgresUnitOfWork
from rag_engine.adapters.settings import Settings
from rag_engine.adapters.tei import TeiEmbedderPool, TeiRerankerPool
from rag_engine.app.search import SearchDeps
from rag_engine.domain.errors import ErrorCode, InvalidInput, RequestError
from rag_engine.server.auth import AuthMiddleware
from rag_engine.server.ingest_api import build_ingest_router
from rag_engine.server.problem_response import problem_response, validation_response
from rag_engine.server.problems import ValidationIssue
from rag_engine.server.read_tools import register_read_tools
from rag_engine.server.request_context import RequestContextMiddleware, request_id_of
from rag_engine.server.search_tool import register_search_tool
from rag_engine.server.token_api import build_token_router

logger = logging.getLogger(__name__)

# 설정에 적지 않아도 늘 받는 호스트(ADR 0014).
_ALWAYS_ALLOWED_HOSTS = ("localhost", "127.0.0.1")
_BYTES_PER_MB = 1024 * 1024


def health() -> dict[str, str]:
    return {"status": "ok"}


def allowed_host_patterns(hosts: Sequence[str]) -> list[str]:
    """허용 호스트를 그대로와 `값:*`의 두 꼴로 펼친다. SDK의 `host:*`는 포트가 붙은 Host만 받아서
    기본 포트로 오는 포트 없는 `Host: host`가 421이 되기 때문이다(ADR 0014)."""
    patterns: list[str] = []
    for host in dict.fromkeys([*_ALWAYS_ALLOWED_HOSTS, *hosts]):
        patterns += [host, f"{host}:*"]
    return patterns


def _install_error_handlers(app: FastAPI) -> None:
    async def on_validation_error(request: Request, error: Exception) -> JSONResponse:
        assert isinstance(error, RequestValidationError)
        # 입력 값(`input`)과 `ctx`는 싣지 않는다(ADR 0015).
        issues = [
            ValidationIssue(loc=list(issue["loc"]), type=issue["type"], msg=issue["msg"])
            for issue in error.errors()
        ]
        return validation_response(request_id_of(request.scope), issues)

    async def on_invalid_input(request: Request, error: Exception) -> JSONResponse:
        assert isinstance(error, InvalidInput)
        # 유스케이스는 입력 칸의 이름만 알고, 이 API에서 입력은 모두 요청 본문이다.
        issue = ValidationIssue(loc=["body", *error.loc], type=error.kind, msg=str(error))
        return validation_response(request_id_of(request.scope), [issue])

    async def on_request_error(request: Request, error: Exception) -> JSONResponse:
        assert isinstance(error, RequestError)
        return problem_response(error.code, request_id_of(request.scope), detail=str(error))

    async def on_unhandled(request: Request, _error: Exception) -> JSONResponse:
        # 원인 예외는 요청 문맥 미들웨어가 타입과 프레임만 로그에 남긴다. 응답에는 싣지 않는다.
        return problem_response(ErrorCode.INTERNAL_ERROR, request_id_of(request.scope))

    app.add_exception_handler(RequestValidationError, on_validation_error)
    app.add_exception_handler(InvalidInput, on_invalid_input)
    app.add_exception_handler(RequestError, on_request_error)
    app.add_exception_handler(Exception, on_unhandled)


async def _warm_up_kiwi() -> None:
    """Kiwi 모델을 스레드에서 미리 적재한다. 실패해도 서버가 뜨도록 기록만 남긴다. 적재가 실패하면
    결과를 캐시하지 않으므로 첫 검색이 적재를 다시 시도한다."""
    try:
        await asyncio.to_thread(tokenize_keywords, "준비")
    except Exception as error:
        log_event(logger, "kiwi_warmup_failed", level=logging.ERROR, exception=error)


def create_app(settings: Settings) -> ASGIApp:
    # MCPServer를 만들기 전에 부른다. 로거를 되찾는 일이라 나중에 만든 핸들러가 앞서지 못하게 한다.
    configure_logging(settings.log_format)
    engine = create_engine(settings.database_url)
    unit_of_work = PostgresUnitOfWork(engine)
    token_store = PostgresTokenStore(engine)

    def tei_client(endpoint: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(base_url=endpoint, timeout=settings.tei_timeout_seconds)

    embedders = TeiEmbedderPool(tei_client, batch_size=settings.tei_batch_size)
    rerankers = TeiRerankerPool(tei_client, batch_size=settings.tei_batch_size)
    mcp = MCPServer(name="rag-engine")
    register_search_tool(
        mcp,
        SearchDeps(
            unit_of_work=unit_of_work,
            embedder_for=embedders,
            reranker_for=rerankers,
            tokenize_keywords=tokenize_keywords,
            candidates=settings.search_candidates,
            max_top_k=settings.search_max_top_k,
            timeout_seconds=settings.search_timeout_seconds,
        ),
        default_top_k=settings.search_default_top_k,
    )
    register_read_tools(mcp, unit_of_work, max_text_chars=settings.document_text_max_chars)
    mcp_app = mcp.streamable_http_app(
        stateless_http=settings.mcp_stateless,
        json_response=settings.mcp_json_response,
        transport_security=TransportSecuritySettings(
            allowed_hosts=allowed_host_patterns(settings.allowed_hosts)
        ),
    )

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
        # 마운트한 하위 앱의 lifespan 은 돌지 않아 여기서 세션 관리자를 돌린다(ADR 0005). Kiwi 모델
        # 적재(약 1초)는 기동을 막지 않게 스레드에서 미리 한다. 첫 검색이 그 값을 쓴다.
        warmup = asyncio.create_task(_warm_up_kiwi())
        try:
            async with mcp.session_manager.run():
                yield
        finally:
            # 종료가 취소로 오면 `await warmup`이 끊기므로 정리는 안쪽 `finally`에 둔다.
            try:
                await warmup
            finally:
                try:
                    await embedders.aclose()
                finally:
                    try:
                        await rerankers.aclose()
                    finally:
                        await engine.dispose()

    app = FastAPI(title="rag-engine", lifespan=lifespan)
    _install_error_handlers(app)
    app.add_api_route("/health", health, methods=["GET"])
    token_router = build_token_router(token_store, unit_of_work)
    ingest_router = build_ingest_router(
        unit_of_work, LocalBlobStore(settings.data_dir), settings.max_upload_mb * _BYTES_PER_MB
    )
    app.include_router(token_router)
    app.include_router(ingest_router)
    # 하위 앱은 자기 안에 `/mcp` 경로를 둔다. "/" 마운트는 모든 경로를 받으므로 REST 경로 뒤에 둔다.
    app.mount("/", mcp_app)
    # FastAPI는 포함한 라우터를 `app.routes`에 평평하게 펼치지 않는다. 경로 템플릿을 로그에 남기려면
    # 라우터가 가진 접두사 포함 경로를 따로 넘겨야 한다.
    return RequestContextMiddleware(
        AuthMiddleware(app, token_store),
        [*app.routes, *token_router.routes, *ingest_router.routes],
    )
