"""파서 인터페이스 1.0.0. 플러그인 자리 하나(ADR 0003, 0012)이고 판의 규칙은 원칙 VII다.

메서드나 칸을 더하면 minor, 지우거나 뜻을 바꾸면 major다. 서버와 작업자는 entry point 그룹
`rag_engine.parsers`에서 파서를 로드할 때 major가 다르면 거부하고 기록한다. 내장 파서 셋도 같은 길로
등록한다. 파서는 자식 프로세스에서 돌므로 상태를 들지 않는다.

파서가 알리는 실패는 아래 예외 둘이다. 그 밖의 예외는 모두 `parse_failed`로 번역한다. 글 크기
(`document_too_large`)는 파서가 아니라 자식 프로세스의 실행기가 파싱 결과를 받은 뒤 보고하고,
같은 자리에서 블록 글의 U+0000을 지운다(명세 "파싱의 격리와 자원 한도").
"""

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Final, Protocol

from rag_engine.domain.entities import Block
from rag_engine.domain.errors import ErrorCode, PermanentFailure

PARSER_INTERFACE_VERSION: Final = "1.0.0"


@dataclass(frozen=True, slots=True)
class ParserLimits:
    """파서가 스스로 지킬 한도. 지금은 쪽 수 상한 하나다."""

    max_pages: int


class EncryptedDocumentError(PermanentFailure):
    """암호가 걸려 읽을 수 없는 문서. 파서가 올리면 `encrypted_document`가 된다."""

    def __init__(self, message: str = "암호가 걸린 문서라 읽을 수 없다") -> None:
        super().__init__(ErrorCode.ENCRYPTED_DOCUMENT, message)


class TooManyPagesError(PermanentFailure):
    """쪽 수가 `ParserLimits.max_pages`를 넘은 문서. 파서가 올리면 `too_many_pages`가 된다."""

    def __init__(self, message: str = "쪽 수가 한도를 넘었다") -> None:
        super().__init__(ErrorCode.TOO_MANY_PAGES, message)


class Parser(Protocol):
    """원본 바이트에서 글과 구조(제목, 문단, 표, 위치)를 뽑는 플러그인.

    `interface_version`은 이 인터페이스의 판(`PARSER_INTERFACE_VERSION`을 따르는 semver)이다.
    `mime_types`는 받는 MIME 목록이다. 블록의 모양(종류 넷, 제목 수준, 쪽 번호 1부터, 순번 0부터)은
    `rag_engine.domain.entities.Block`이 정한다. 글이 하나도 없는 문서(스캔본)는 빈 목록을 낸다.
    """

    @property
    def interface_version(self) -> str: ...

    @property
    def mime_types(self) -> Sequence[str]: ...

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]: ...
