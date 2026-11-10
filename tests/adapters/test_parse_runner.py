"""파싱 실행기(명세 "파싱의 격리와 자원 한도").

파싱은 작업자 프로세스가 아니라 spawn한 자식 프로세스에서 한다. 시간 초과는 `parse_timeout`, 메모리
오류는 `parse_memory_exceeded`, 파서의 예외는 `parse_failed`, 파서가 알린 암호 문서는
`encrypted_document`이고 모두 영구 실패다. 서드파티 예외의 메시지는 옮기지 않는다(원칙 V).
"""

import io
import logging
import sys
from pathlib import Path

import pytest
from docx import Document
from tests.support.fake_parsers import FAKE_MIME, MARKER_ENV

from rag_engine.adapters.parsers.registry import ParserRegistry, ParserSpec, discover_parser_specs
from rag_engine.adapters.parsers.runner import SubprocessParseRunner, decode_child_message
from rag_engine.domain.entities import BlockKind
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.media_types import DOCX_MIME
from rag_engine.domain.parsing import PARSER_INTERFACE_VERSION

FAKES = "tests.support.fake_parsers"


def _registry(fake: str | None = None) -> ParserRegistry:
    specs = discover_parser_specs()
    if fake is not None:
        specs = [ParserSpec(name="fake", target=f"{FAKES}:{fake}", library="fake-lib"), *specs]
    return ParserRegistry(specs)


def _runner(registry: ParserRegistry, **overrides: int) -> SubprocessParseRunner:
    values = {
        "timeout_seconds": 60,
        "memory_mb": 2048,
        "max_pages": 1000,
        "max_text_mb": 64,
        **overrides,
    }
    return SubprocessParseRunner(registry, **values)


def _docx_bytes() -> bytes:
    document = Document()
    document.add_heading("제1조", level=1)
    document.add_paragraph("본문이다.")
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


async def _failure_code(runner: SubprocessParseRunner, data: bytes = b"x") -> ErrorCode:
    with pytest.raises(PermanentFailure) as caught:
        await runner.parse(data, FAKE_MIME)
    return caught.value.code


async def test_실제_DOCX를_자식_프로세스에서_파싱해_블록과_파서_판을_낸다() -> None:
    parsed = await _runner(_registry()).parse(_docx_bytes(), DOCX_MIME)

    assert parsed.parser_name == "docx"
    assert parsed.interface_version == PARSER_INTERFACE_VERSION
    assert parsed.library_version
    assert [(block.kind, block.text) for block in parsed.blocks] == [
        (BlockKind.HEADING, "제1조"),
        (BlockKind.PARAGRAPH, "본문이다."),
    ]


async def test_시간_안에_끝나지_않는_파싱은_자식을_죽이고_parse_timeout이다() -> None:
    runner = _runner(_registry("SleepingParser"), timeout_seconds=1)

    assert await _failure_code(runner) is ErrorCode.PARSE_TIMEOUT


async def test_파서의_예외는_parse_failed이고_메시지를_옮기지_않는다() -> None:
    with pytest.raises(PermanentFailure) as caught:
        await _runner(_registry("RaisingParser")).parse(b"x", FAKE_MIME)

    assert caught.value.code is ErrorCode.PARSE_FAILED
    assert "SECRET-FRAGMENT" not in str(caught.value)


async def test_파서가_알린_암호_문서는_encrypted_document다() -> None:
    runner = _runner(_registry("EncryptedParser"))

    assert await _failure_code(runner) is ErrorCode.ENCRYPTED_DOCUMENT


async def test_파서의_메모리_오류는_parse_memory_exceeded다() -> None:
    runner = _runner(_registry("MemoryHungryParser"))

    assert await _failure_code(runner) is ErrorCode.PARSE_MEMORY_EXCEEDED


async def test_메시지를_보내기_전에_죽은_자식은_신호로_죽었을_때만_메모리_초과로_본다() -> None:
    runner = _runner(_registry("CrashingParser"))

    expected = (
        ErrorCode.PARSE_FAILED if sys.platform == "win32" else ErrorCode.PARSE_MEMORY_EXCEEDED
    )
    assert [await _failure_code(runner)] == [expected]


async def test_침해된_자식이_pickle을_보내도_부모는_코드를_실행하지_않고_parse_failed다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    marker = tmp_path / "pwned.txt"
    monkeypatch.setenv(MARKER_ENV, str(marker))
    runner = _runner(_registry("HijackingParser"))

    assert [await _failure_code(runner), marker.exists()] == [ErrorCode.PARSE_FAILED, False]


@pytest.mark.parametrize(
    "payload",
    [
        b'{"error": "not_a_code", "blocks": []}',
        b'{"error": null, "blocks": [["not_a_kind", "text", null, null, 0]]}',
    ],
)
def test_자식이_모르는_오류_코드나_블록_종류를_보내면_parse_failed다(payload: bytes) -> None:
    assert decode_child_message(payload).error is ErrorCode.PARSE_FAILED


async def test_받는_파서가_없는_MIME은_parse_failed다() -> None:
    with pytest.raises(PermanentFailure) as caught:
        await _runner(_registry()).parse(b"x", "application/x-nothing")

    assert caught.value.code is ErrorCode.PARSE_FAILED


async def test_뽑은_글이_상한을_넘으면_document_too_large다() -> None:
    runner = _runner(_registry("EchoParser"), max_text_mb=1)

    assert await _failure_code(runner, b"a" * (1024 * 1024 + 1)) is ErrorCode.DOCUMENT_TOO_LARGE


async def test_블록_글의_U0000은_저장_전에_지운다() -> None:
    parsed = await _runner(_registry("EchoParser")).parse("가\x00나".encode(), FAKE_MIME)

    assert [block.text for block in parsed.blocks] == ["가나"]


def test_파서의_인터페이스_major가_다르면_레지스트리가_거부하고_기록한다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.WARNING)
    specs = [ParserSpec(name="major-two", target=f"{FAKES}:MajorTwoParser", library="fake")]

    registry = ParserRegistry(specs)

    assert registry.names() == []
    assert any(record.getMessage() == "parser_rejected" for record in caplog.records)


async def test_메모리_한도는_리눅스에서_걸리고_Windows에서는_걸지_않는다고_기록한다(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    runner = _runner(_registry())

    await runner.parse(_docx_bytes(), DOCX_MIME)

    not_applied = [r for r in caplog.records if r.getMessage() == "parse_memory_limit_not_applied"]
    assert bool(not_applied) is (sys.platform == "win32")
