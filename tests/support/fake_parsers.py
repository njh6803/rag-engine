"""파싱 실행기 시험이 레지스트리에 더하는 가짜 파서(명세 "포트 열셋과 그 값"의 `Parser` 항목: 실패
분류의 시험만 테스트 쪽 가짜 파서를 쓴다). 자식 프로세스가 `tests.support.fake_parsers`로 불러
쓰므로 모듈 최상위에서 부수 효과를 내지 않는다.
"""

import gc
import os
import signal
import sys
import time
from collections.abc import Callable, Sequence

from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.parsing import (
    PARSER_INTERFACE_VERSION,
    EncryptedDocumentError,
    ParserLimits,
)

FAKE_MIME = "application/x-fake"
MARKER_ENV = "RAG_TEST_PWN_MARKER"


class _FakeParser:
    @property
    def interface_version(self) -> str:
        return PARSER_INTERFACE_VERSION

    @property
    def mime_types(self) -> Sequence[str]:
        return (FAKE_MIME,)

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        raise NotImplementedError


class EchoParser(_FakeParser):
    """원본 바이트를 UTF-8 글 한 문단으로 낸다. 글 안의 U+0000도 그대로 낸다."""

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        return [Block(BlockKind.PARAGRAPH, data.decode("utf-8"), None, None, 0)]


class SleepingParser(_FakeParser):
    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        time.sleep(60)
        return []


class RaisingParser(_FakeParser):
    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        raise RuntimeError("파서 안쪽 메시지 SECRET-FRAGMENT")


class EncryptedParser(_FakeParser):
    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        raise EncryptedDocumentError


class MemoryHungryParser(_FakeParser):
    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        raise MemoryError


class CrashingParser(_FakeParser):
    """메시지를 보내기 전에 죽는다. 리눅스에서는 신호(`SIGKILL`)로, 윈도에서는 양수 종료 코드로
    죽는다. 신호 종료는 OOM 킬러와 `RLIMIT_AS`가 자식을 죽이는 모양이다."""

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        if sys.platform == "win32":
            os._exit(3)
        os.kill(os.getpid(), signal.SIGKILL)
        return []


def write_marker(path: str) -> None:
    """부모가 자식의 메시지를 pickle로 풀면 불려 표지 파일을 남긴다."""
    with open(path, "w", encoding="utf-8") as marker:
        marker.write("pwned")


class _Exploit:
    def __init__(self, path: str) -> None:
        self._path = path

    def __reduce__(self) -> tuple[Callable[[str], None], tuple[str]]:
        return (write_marker, (self._path,))


class HijackingParser(_FakeParser):
    """침해된 파서를 흉내 낸다. 자식이 부모에게 쓰는 연결을 찾아, 부모가 pickle로 풀면 코드가 도는
    메시지를 보낸다. 표지 파일의 경로는 환경 변수(`MARKER_ENV`)로 받는다."""

    def parse(self, data: bytes, mime: str, limits: ParserLimits) -> Sequence[Block]:
        marker = os.environ[MARKER_ENV]
        # 연결의 클래스는 리눅스에서 `Connection`, 윈도에서 `PipeConnection`이라 모듈 이름으로
        # 찾는다.
        connection = next(
            item
            for item in gc.get_objects()
            if type(item).__module__ == "multiprocessing.connection"
        )
        connection.send(_Exploit(marker))
        os._exit(0)


class MajorTwoParser(_FakeParser):
    @property
    def interface_version(self) -> str:
        return "2.0.0"
