"""수집과 작업이 엇갈리는 순간을 정하는 시험 도우미(명세 Testing Decisions의 동시성 교차).

실제 테스트 PostgreSQL 위에서 교차 시점을 정한다. 끼어들 일은 대개 한 번만 하고(`FailingRunner`는
파싱을 부를 때마다 돈다), 나머지는 실제 포트에 맡긴다. 임베딩 직전과 파싱 직전에 끼어드는 것은 작업
쪽, 원본을 쓴 직후와 지우기 직전에 끼어드는 것은 수집 쪽이다.
"""

from collections.abc import Awaitable, Callable, Sequence
from pathlib import Path

from rag_engine.adapters.blob_store import LocalBlobStore
from rag_engine.domain.entities import IndexVersion
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.parsing import ParsedDocument, ParserVersion
from rag_engine.domain.ports import Embedder, EmbedderFor

type Interloper = Callable[[], Awaitable[None]]


class InterruptingEmbedder:
    """임베딩 직전에 끼어들 일을 한 번 한다. 나머지는 실제 임베더에 맡긴다."""

    def __init__(self, inner: Embedder, interrupt: Interloper) -> None:
        self._inner = inner
        self._interrupt = interrupt
        self._interrupted = False

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        if not self._interrupted:
            self._interrupted = True
            await self._interrupt()
        return await self._inner.embed(texts)

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        return await self._inner.count_tokens(texts)

    async def special_token_count(self) -> int:
        return await self._inner.special_token_count()

    async def token_spans(self, text: str) -> list[tuple[int, int]]:
        return await self._inner.token_spans(text)


def interrupting_embedder_for(embedder_for: EmbedderFor, interrupt: Interloper) -> EmbedderFor:
    """임베딩 직전에 한 번 끼어드는 임베더를 판마다 낸다."""

    def make(version: IndexVersion) -> Embedder:
        return InterruptingEmbedder(embedder_for(version), interrupt)

    return make


class FailingRunner:
    """파싱이 영구 실패하는 실행기. `before_failing`을 주면 실패하기 직전에 끼어들 일을 한다."""

    def __init__(
        self,
        code: ErrorCode = ErrorCode.ENCRYPTED_DOCUMENT,
        before_failing: Interloper | None = None,
    ) -> None:
        self._code = code
        self._before_failing = before_failing

    def current_version(self, mime: str) -> ParserVersion | None:
        return None

    async def parse(self, data: bytes, mime: str) -> ParsedDocument:
        if self._before_failing is not None:
            await self._before_failing()
        raise PermanentFailure(self._code, "시험용 영구 실패")


class InterruptingBlobStore(LocalBlobStore):
    """원본을 쓴 직후(`after_write`)나 원본을 지우기 직전(`before_delete`)에 다른 수집이 끼어들게
    한다. 끼어들 일은 각각 한 번이다."""

    def __init__(
        self,
        root: Path,
        *,
        after_write: Interloper | None = None,
        before_delete: Interloper | None = None,
    ) -> None:
        super().__init__(root)
        self._after_write = after_write
        self._before_delete = before_delete

    async def write(self, key: str, data: bytes) -> None:
        await super().write(key, data)
        interloper, self._after_write = self._after_write, None
        if interloper is not None:
            await interloper()

    async def delete(self, key: str) -> None:
        interloper, self._before_delete = self._before_delete, None
        if interloper is not None:
            await interloper()
        await super().delete(key)
