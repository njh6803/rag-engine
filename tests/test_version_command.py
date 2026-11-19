"""`rag-engine --version`은 필수 설정 없이 종료 코드 0으로 끝나고, 첫 줄에 설치된 패키지의 번호를,
이어서 계약마다 버전을 한 줄씩 찍는다(release-image 명세 "번호가 보이는 자리", 스토리 29·30)."""

import os
from pathlib import Path

import pytest

from rag_engine.adapters.index_elements import SCHEMA_VERSION
from rag_engine.domain.parsing import PARSER_INTERFACE_VERSION
from rag_engine.main import main
from rag_engine.server.api_version import API_VERSION
from rag_engine.server.tool_models import FORMAT_VERSION


@pytest.fixture
def no_settings_environment(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """필수 설정(데이터베이스 주소, 허용 호스트, 임베딩 서버 주소)이 하나도 없는 환경. 개발자 셸의
    `RAG_*`와 작업 폴더의 `.env`가 시험을 바꾸지 못하게 지우고 빈 폴더에서 돈다."""
    for name in [name for name in os.environ if name.startswith("RAG_")]:
        monkeypatch.delenv(name)
    monkeypatch.chdir(tmp_path)


def _run_version(capsys: pytest.CaptureFixture[str]) -> list[str]:
    with pytest.raises(SystemExit) as caught:
        main(["--version"])
    assert caught.value.code == 0
    return capsys.readouterr().out.splitlines()


@pytest.mark.usefixtures("no_settings_environment")
def test_필수_설정_없이_종료_코드_0으로_끝나고_첫_줄에_설치된_번호를_찍는다(
    marker_release_number: str, capsys: pytest.CaptureFixture[str]
) -> None:
    lines = _run_version(capsys)

    assert lines[0] == f"rag-engine {marker_release_number}"


@pytest.mark.usefixtures("no_settings_environment", "marker_release_number")
def test_이어서_계약마다_버전을_한_줄씩_그_계약을_정한_코드의_값으로_찍는다(
    capsys: pytest.CaptureFixture[str],
) -> None:
    lines = _run_version(capsys)

    assert lines[1:] == [
        f"검색 도구의 형식 {FORMAT_VERSION}",
        f"수집 API와 관리 API의 경로 {API_VERSION}",
        f"파서 인터페이스 {PARSER_INTERFACE_VERSION}",
        f"색인 형식의 스키마 {SCHEMA_VERSION}",
    ]


@pytest.mark.usefixtures("no_settings_environment")
def test_계약_버전_값이_지금_릴리스_노트가_옮기는_값이다(
    marker_release_number: str, capsys: pytest.CaptureFixture[str]
) -> None:
    """위 시험은 상수를 읽어 견주므로 상수를 올려도 초록이다. 이 시험은 지금 버전이 붙은 값을 글자로
    고정해, 계약 버전을 올리는 변경이 이 줄과 릴리스 노트를 함께 보게 한다."""
    lines = _run_version(capsys)

    assert marker_release_number in lines[0]
    assert lines[1:] == [
        "검색 도구의 형식 1.1.0",
        "수집 API와 관리 API의 경로 v1",
        "파서 인터페이스 1.0.0",
        "색인 형식의 스키마 1",
    ]
