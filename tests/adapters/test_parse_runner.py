"""파싱 실행기(명세 "파싱의 격리와 자원 한도").

파싱은 작업자 프로세스가 아니라 spawn한 자식 프로세스에서 한다. 시간 초과는 `parse_timeout`, 메모리
오류는 `parse_memory_exceeded`, 파서의 예외는 `parse_failed`, 파서가 알린 암호 문서는
`encrypted_document`이고 모두 영구 실패다. 서드파티 예외의 메시지는 옮기지 않는다(원칙 V).
"""

import asyncio
import io
import logging
import sys
import time
from importlib.metadata import version
from pathlib import Path

import pytest
from docx import Document
from tests.support.fake_parsers import FAKE_MIME, MARKER_ENV
from tests.support.hwpx_files import HwpxHeading, HwpxParagraph, hwpx_bytes
from tests.support.pdf_files import PdfPage, blank_pages_pdf, pdf_bytes, text_block
from tests.support.zip_files import zip_bytes

from rag_engine.adapters.parsers.hwpx_parser import HwpxParser
from rag_engine.adapters.parsers.pdf_parser import PdfParser
from rag_engine.adapters.parsers.registry import ParserRegistry, ParserSpec, discover_parser_specs
from rag_engine.adapters.parsers.runner import SubprocessParseRunner, decode_child_message
from rag_engine.domain.entities import BlockKind
from rag_engine.domain.errors import ErrorCode, PermanentFailure
from rag_engine.domain.media_types import DOCX_MIME, HWPX_MIME, PDF_MIME
from rag_engine.domain.parsing import PARSER_INTERFACE_VERSION

FAKES = "tests.support.fake_parsers"
FIXTURES = Path(__file__).parent.parent / "fixtures"
MIB = 1024 * 1024


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
        "max_unzipped_mb": 512,
        "max_compression_ratio": 100,
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


async def _failure_code(
    runner: SubprocessParseRunner, data: bytes = b"x", mime: str = FAKE_MIME
) -> ErrorCode:
    with pytest.raises(PermanentFailure) as caught:
        await runner.parse(data, mime)
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


async def test_한도보다_많이_잡으면_리눅스는_parse_memory_exceeded이고_윈도는_걸지_않는다() -> None:
    runner = _runner(_registry("AllocatingParser"), memory_mb=512)

    if sys.platform == "win32":
        parsed = await runner.parse(b"x", FAKE_MIME)
        assert [block.text for block in parsed.blocks] == [str(768 * MIB)]
    else:
        assert await _failure_code(runner) is ErrorCode.PARSE_MEMORY_EXCEEDED


async def test_제어_문자로_부푼_메시지도_글이_한도_안이면_받는다() -> None:
    # 글은 900KiB로 한도(1MiB) 안이지만 `\u0001`이 JSON에서 여섯 바이트라 메시지는 5MiB를 넘는다.
    runner = _runner(_registry("EchoParser"), max_text_mb=1)

    parsed = await runner.parse(b"\x01" * (900 * 1024), FAKE_MIME)

    assert [len(block.text) for block in parsed.blocks] == [900 * 1024]


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
        # 스키마는 통과하지만 파서가 보낼 수 없는 값이다.
        b'{"error": "search_unavailable", "blocks": []}',
        b'{"error": null, "blocks": [["heading", "text", null, null, 0]]}',
        b'{"error": null, "blocks": [["paragraph", "text", null, null, -1]]}',
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


async def test_실제_PDF를_자식_프로세스에서_파싱해_블록과_파서_판을_낸다() -> None:
    parsed = await _runner(_registry()).parse((FIXTURES / "small_text.pdf").read_bytes(), PDF_MIME)

    assert (parsed.parser_name, parsed.library_version) == ("pdf", version("pdfplumber"))
    assert parsed.interface_version == PARSER_INTERFACE_VERSION
    assert [(block.kind, block.page) for block in parsed.blocks] == [
        (BlockKind.PARAGRAPH, 1),
        (BlockKind.PARAGRAPH, 1),
        (BlockKind.TABLE, 1),
    ]


async def test_실제_HWPX를_자식_프로세스에서_파싱해_블록과_파서_판을_낸다() -> None:
    data = hwpx_bytes(HwpxHeading("제1조", level=1), HwpxParagraph("본문이다."))

    parsed = await _runner(_registry()).parse(data, HWPX_MIME)

    assert (parsed.parser_name, parsed.library_version) == ("hwpx", version("python-hwpx"))
    assert [(block.kind, block.text) for block in parsed.blocks] == [
        (BlockKind.HEADING, "제1조"),
        (BlockKind.PARAGRAPH, "본문이다."),
    ]


def test_내장_파서_셋은_entry_point로_등록된다() -> None:
    registry = ParserRegistry(discover_parser_specs())

    assert sorted(registry.names()) == ["docx", "hwpx", "pdf"]
    assert [
        registered.spec.name
        for registered in (registry.for_mime(mime) for mime in (DOCX_MIME, PDF_MIME, HWPX_MIME))
        if registered is not None
    ] == ["docx", "pdf", "hwpx"]


@pytest.mark.parametrize(("parser_class", "name"), [(PdfParser, "pdf"), (HwpxParser, "hwpx")])
def test_PDF와_HWPX_파서도_인터페이스_major가_다르면_거부된다(
    monkeypatch: pytest.MonkeyPatch, parser_class: type, name: str
) -> None:
    monkeypatch.setattr(parser_class, "interface_version", property(lambda _self: "2.0.0"))

    assert name not in ParserRegistry(discover_parser_specs()).names()


async def test_암호_PDF는_encrypted_document다() -> None:
    data = pdf_bytes([PdfPage(text_block("가나다"))], user_password="secret")

    assert await _failure_code(_runner(_registry()), data, PDF_MIME) is ErrorCode.ENCRYPTED_DOCUMENT


async def test_쪽이_수만_장인_PDF는_too_many_pages다() -> None:
    runner = _runner(_registry(), max_pages=1000)

    assert await _failure_code(runner, blank_pages_pdf(20000), PDF_MIME) is ErrorCode.TOO_MANY_PAGES


@pytest.mark.parametrize("mime", [PDF_MIME, HWPX_MIME, DOCX_MIME])
async def test_깨진_문서는_parse_failed다(mime: str) -> None:
    runner = _runner(_registry())

    assert (
        await _failure_code(runner, b"%PDF-1.4 PK\x03\x04 broken", mime) is ErrorCode.PARSE_FAILED
    )


@pytest.mark.parametrize("mime", [DOCX_MIME, HWPX_MIME])
async def test_압축_폭탄_ZIP은_자식을_띄우지_않고_compressed_too_large다(mime: str) -> None:
    # 자식이 이 바이트를 파싱했다면 DOCX도 HWPX도 아닌 ZIP이라 `parse_failed`였을 것이다.
    bomb = zip_bytes({"a.bin": bytes(2 * MIB)})

    code = await _failure_code(_runner(_registry(), max_unzipped_mb=1), bomb, mime)

    assert code is ErrorCode.COMPRESSED_TOO_LARGE


@pytest.mark.parametrize("mime", [DOCX_MIME, HWPX_MIME])
async def test_암호_항목이_든_ZIP은_encrypted_document다(mime: str) -> None:
    locked = zip_bytes({"a.xml": b"x"}, encrypted=("a.xml",))

    assert await _failure_code(_runner(_registry()), locked, mime) is ErrorCode.ENCRYPTED_DOCUMENT


async def test_받는_크기_상한을_넘는_메시지는_끝까지_읽지_않고_document_too_large다() -> None:
    # 글은 한 글자도 없는 메시지라 상한(1MiB × 6 + 1MiB = 7MiB)이 없으면 부모는 8MiB를 다 읽고
    # 빈 블록으로 성공한다.
    runner = _runner(_registry("OversizedMessageParser"), max_text_mb=1)

    assert await _failure_code(runner, str(8 * MIB).encode()) is ErrorCode.DOCUMENT_TOO_LARGE


async def test_메시지를_보내다_멈춘_자식이_있어도_수신이_영영_막히지_않는다() -> None:
    # 리눅스의 연결은 길이를 알린 뒤 멈추면 읽는 쪽이 기다리고, 윈도의 연결은 한 번의 쓰기가 온전한
    # 메시지라 잘린 JSON이 `parse_failed`로 간다(`StallingMidMessageParser`의 독스트링). 러너의
    # 기한은 자식을 띄운 때부터 세므로 자식의 기동도 그 안에 든다. 윈도의 기대는 자식이 기한 안에
    # 잘린 메시지를 보내야 서서, 기한이 짧으면 부하에서 기동이 늘어난 자식을 타이머가 먼저 죽여
    # `parse_timeout`이 난다. 윈도는 메시지를 받으면 바로 돌아오니 기한을 넉넉히 주고, 리눅스는
    # 기한까지 기다려야 끝나니 짧게 준다.
    on_windows = sys.platform == "win32"
    deadline = 30 if on_windows else 2
    slack = 15  # 기한이 지난 뒤 자식을 거두는 대기(최대 5초씩 둘)와 부하를 덮는 여유
    runner = _runner(_registry("StallingMidMessageParser"), timeout_seconds=deadline)
    started = time.monotonic()

    code = await _failure_code(runner)

    expected = ErrorCode.PARSE_FAILED if on_windows else ErrorCode.PARSE_TIMEOUT
    assert [code, time.monotonic() - started < deadline + slack] == [expected, True]


async def test_자식이_기동하기_전에_기한이_지나도_수신이_풀리고_parse_timeout이다() -> None:
    # 윈도의 연결은 자식이 기동한 뒤에 가져가는 복제 핸들이 부모에 남아 있어, 그 전에 죽은 자식의
    # 파이프는 끊기지 않는다. 기한 0초는 감시 타이머가 자식이 기동하기 전에 죽이게 한다.
    runner = _runner(_registry("SleepingParser"), timeout_seconds=0)

    code = await asyncio.wait_for(_failure_code(runner), timeout=30)

    assert code is ErrorCode.PARSE_TIMEOUT
