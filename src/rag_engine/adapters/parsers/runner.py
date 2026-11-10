"""파싱 실행기. 파서를 spawn한 자식 프로세스에서 돌려 작업자를 지킨다(명세 "파싱의 격리와 자원
한도").

부모는 파서 대상(`모듈:클래스`)과 원본 바이트, 한도를 spawn 인자로 자식에게 넘기고 파이프로
결과(또는 오류 코드)를 받는다. `RAG_PARSE_TIMEOUT_SECONDS` 안에 끝나지 않으면 자식을 죽이고
`parse_timeout`이다. 자식이 신호로 죽거나 `MemoryError`를 내면 `parse_memory_exceeded`, 파서의 그
밖의 예외는 `parse_failed`다. 서드파티 예외의 메시지는 부모에 넘기지 않는다(원칙 V). 메모리 한도는
리눅스에서 `RLIMIT_AS`로 걸고 Windows에서는 걸지 않는다(그 사실을 로그에 한 번 남긴다). 파싱 결과의
글 크기와 U+0000은 부모가 본다.
"""

import asyncio
import logging
import multiprocessing
import sys
from dataclasses import dataclass, replace
from multiprocessing.connection import Connection
from typing import Final

from pydantic import BaseModel, ValidationError

from rag_engine.adapters.log_format import log_event
from rag_engine.adapters.parsers.registry import (
    ParserRegistry,
    library_version,
    load_parser,
)
from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.parsing import (
    EncryptedDocumentError,
    ParsedDocument,
    ParserLimits,
    ParserVersion,
    TooManyPagesError,
)

logger = logging.getLogger(__name__)

_BYTES_PER_MB: Final = 1024 * 1024
_REAP_SECONDS: Final = 5

# `_parse_to_message`가 자식에서 실제로 내는 오류 코드.
_CHILD_ERROR_CODES: Final = frozenset(
    {
        ErrorCode.ENCRYPTED_DOCUMENT,
        ErrorCode.TOO_MANY_PAGES,
        ErrorCode.PARSE_MEMORY_EXCEEDED,
        ErrorCode.PARSE_FAILED,
    }
)

type _BlockTuple = tuple[BlockKind, str, int | None, int | None, int]


class ChildMessage(BaseModel, frozen=True):
    """자식이 부모에게 보내는 유일한 메시지. 오류는 서드파티 예외의 글이 아니라 코드만 싣는다.
    JSON 바이트로 보내고 부모는 스키마로 검증해서 읽는다. `Connection.recv()`는 pickle을 풀어서,
    파서 라이브러리가 침해된 자식이 부모(작업자)에서 코드를 실행하는 통로가 된다."""

    error: ErrorCode | None
    blocks: list[_BlockTuple]


def _apply_memory_limit(memory_mb: int) -> None:
    if sys.platform == "win32":
        return
    import resource

    limit = memory_mb * _BYTES_PER_MB
    resource.setrlimit(resource.RLIMIT_AS, (limit, limit))


def run_parser_child(
    connection: Connection, target: str, data: bytes, mime: str, max_pages: int, memory_mb: int
) -> None:
    """자식 프로세스의 입구. 블록 튜플들이나 오류 코드를 JSON 바이트(`ChildMessage`)로 보낸다.
    오류에는 서드파티 예외의 글을 싣지 않고 코드만 싣는다."""
    try:
        message = _parse_to_message(target, data, mime, max_pages, memory_mb)
        connection.send_bytes(message.model_dump_json().encode())
    finally:
        connection.close()


def _parse_to_message(
    target: str, data: bytes, mime: str, max_pages: int, memory_mb: int
) -> ChildMessage:
    try:
        _apply_memory_limit(memory_mb)
        parser = load_parser(target)
        blocks = parser.parse(data, mime, ParserLimits(max_pages=max_pages))
    except EncryptedDocumentError:
        return ChildMessage(error=ErrorCode.ENCRYPTED_DOCUMENT, blocks=[])
    except TooManyPagesError:
        return ChildMessage(error=ErrorCode.TOO_MANY_PAGES, blocks=[])
    except MemoryError:
        return ChildMessage(error=ErrorCode.PARSE_MEMORY_EXCEEDED, blocks=[])
    except Exception:
        return ChildMessage(error=ErrorCode.PARSE_FAILED, blocks=[])
    return ChildMessage(
        error=None,
        blocks=[
            (block.kind, block.text, block.level, block.page, block.ordinal) for block in blocks
        ],
    )


@dataclass(frozen=True, slots=True)
class _ChildResult:
    error: ErrorCode | None
    blocks: tuple[Block, ...]


def _fail(code: ErrorCode, message: str) -> PermanentFailure:
    return PermanentFailure(code, message)


class SubprocessParseRunner:
    def __init__(
        self,
        registry: ParserRegistry,
        *,
        timeout_seconds: int,
        memory_mb: int,
        max_pages: int,
        max_text_mb: int,
    ) -> None:
        self._registry = registry
        self._timeout_seconds = timeout_seconds
        self._memory_mb = memory_mb
        self._max_pages = max_pages
        self._max_text_bytes = max_text_mb * _BYTES_PER_MB
        self._memory_limit_noted = False

    def current_version(self, mime: str) -> ParserVersion | None:
        registered = self._registry.for_mime(mime)
        if registered is None:
            return None
        return ParserVersion(
            parser_name=registered.spec.name,
            interface_version=registered.interface_version,
            library_version=library_version(registered.spec.library),
        )

    async def parse(self, data: bytes, mime: str) -> ParsedDocument:
        registered = self._registry.for_mime(mime)
        if registered is None:
            raise _fail(ErrorCode.PARSE_FAILED, "이 형식을 받는 파서가 없다")
        self._note_memory_limit()
        result = await asyncio.to_thread(self._run_child, registered.spec.target, data, mime)
        if result.error is not None:
            raise _fail(result.error, f"파싱이 실패했다: {result.error.value}")
        blocks = tuple(
            replace(block, text=block.text.replace("\x00", "")) for block in result.blocks
        )
        if sum(len(block.text.encode()) for block in blocks) > self._max_text_bytes:
            raise _fail(ErrorCode.DOCUMENT_TOO_LARGE, "뽑은 글이 한도를 넘었다")
        return ParsedDocument(
            parser_name=registered.spec.name,
            interface_version=registered.interface_version,
            library_version=library_version(registered.spec.library),
            blocks=blocks,
        )

    def _note_memory_limit(self) -> None:
        if sys.platform == "win32" and not self._memory_limit_noted:
            self._memory_limit_noted = True
            log_event(logger, "parse_memory_limit_not_applied")

    def _run_child(self, target: str, data: bytes, mime: str) -> _ChildResult:
        context = multiprocessing.get_context("spawn")
        receiver, sender = context.Pipe(duplex=False)
        process = context.Process(
            target=run_parser_child,
            args=(sender, target, data, mime, self._max_pages, self._memory_mb),
            daemon=True,
        )
        process.start()
        sender.close()
        try:
            if not receiver.poll(self._timeout_seconds):
                return _ChildResult(ErrorCode.PARSE_TIMEOUT, ())
            try:
                payload = receiver.recv_bytes()
            except EOFError:
                # 보내기 전에 죽었다. 신호로 죽었으면(OOM 킬러, 한도) 메모리로 본다.
                process.join(_REAP_SECONDS)
                killed = process.exitcode is not None and process.exitcode < 0
                code = ErrorCode.PARSE_MEMORY_EXCEEDED if killed else ErrorCode.PARSE_FAILED
                return _ChildResult(code, ())
            return decode_child_message(payload)
        finally:
            if process.is_alive():
                process.terminate()
            process.join(_REAP_SECONDS)
            if process.is_alive():
                # SIGTERM을 무시하는 자식이 좀비로 남지 않게 한다.
                process.kill()
                process.join(_REAP_SECONDS)
            receiver.close()


def decode_child_message(payload: bytes) -> _ChildResult:
    """자식이 보낸 바이트를 스키마로 검증해 읽는다. 모양이 틀리거나, 모르는 오류 코드·블록 종류가
    들어 있거나, 자식이 보낼 수 없는 오류 코드이거나, `Block`의 불변식을 어기면 `parse_failed`다."""
    try:
        message = ChildMessage.model_validate_json(payload)
    except ValidationError:
        return _ChildResult(ErrorCode.PARSE_FAILED, ())
    if message.error is not None:
        # 스키마는 모든 오류 코드를 받는다. 자식이 보낼 수 있는 코드 밖은 영구 실패의 코드가 아니라
        # 부모에서 `ValueError`가 되므로 거른다.
        code = message.error if message.error in _CHILD_ERROR_CODES else ErrorCode.PARSE_FAILED
        return _ChildResult(code, ())
    try:
        blocks = tuple(
            Block(kind, text, level, page, ordinal)
            for kind, text, level, page, ordinal in message.blocks
        )
    except ValueError:
        # 스키마는 `Block`의 불변식(제목 수준, 쪽 번호, 순번)을 보지 않는다.
        return _ChildResult(ErrorCode.PARSE_FAILED, ())
    return _ChildResult(None, blocks)
