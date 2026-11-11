"""시험의 로그 도우미 `LogCapture`. 기대한 개수에 못 미친 채 기다림이 끝나면 조용히 모자란 목록을
돌려주지 않고 실패한다. 돌려주면 그 목록을 단언하지 않는 시험이 아무것도 보지 않은 채 초록이
된다."""

import json

import pytest
from tests.harness import LogCapture


def test_기대한_개수의_이벤트가_있으면_그_이벤트를_돌려준다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print(json.dumps({"event": "search", "n": 1}))
    print(json.dumps({"event": "other"}))
    print(json.dumps({"event": "search", "n": 2}))

    found = LogCapture(capsys).events("search", count=2, timeout=1.0)

    assert [line["n"] for line in found] == [1, 2]


def test_기대한_개수에_못_미치면_기다린_뒤_실패한다(capsys: pytest.CaptureFixture[str]) -> None:
    print(json.dumps({"event": "search"}))

    with pytest.raises(AssertionError, match="search"):
        LogCapture(capsys).events("search", count=2, timeout=0.2)


def test_텍스트_줄을_찾을_때도_기대한_개수에_못_미치면_실패한다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    print("http_request ok")

    with pytest.raises(AssertionError, match="http_request"):
        LogCapture(capsys).lines_containing("http_request", count=2, timeout=0.2)
