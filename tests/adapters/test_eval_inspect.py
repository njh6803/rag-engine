"""`inspect`의 출력 경계(`adapters/eval_inspect.emit`) 시험. 표준 출력의 인코딩으로 표현할 수 없는
글자가 조각 글에 있어도 `inspect`가 오류로 끝나지 않는다."""

import io

from rag_engine.adapters.eval_inspect import emit


def _stream(encoding: str) -> io.TextIOWrapper:
    # 줄바꿈 변환을 끈다. 윈도에서는 기본값이 "\n"을 "\r\n"으로 바꿔 쓴다.
    return io.TextIOWrapper(io.BytesIO(), encoding=encoding, newline="")


def _written(stream: io.TextIOWrapper) -> bytes:
    stream.flush()
    buffer = stream.buffer
    assert isinstance(buffer, io.BytesIO)
    return buffer.getvalue()


def test_cp949로_표현할_수_없는_글자는_물음표로_바꿔_쓰고_나머지는_그대로_쓴다() -> None:
    stream = _stream("cp949")

    emit("조각 😀 끝\n", stream)

    assert _written(stream) == "조각 ? 끝\n".encode("cp949")


def test_utf_8_출력에는_글자를_바꾸지_않는다() -> None:
    stream = _stream("utf-8")

    emit("조각 😀 끝\n", stream)

    assert _written(stream) == "조각 😀 끝\n".encode()


def test_인코딩을_모르는_출력은_utf_8로_쓴다() -> None:
    stream = io.StringIO()

    emit("조각 😀 끝\n", stream)

    assert stream.getvalue() == "조각 😀 끝\n"
