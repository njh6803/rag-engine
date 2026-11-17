"""`tools/search_eval.py` 시험의 픽스처(티켓 search-eval 03, 04)."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.support.claude_server import serve_claude_stub
from tests.support.claude_stub import (
    JUDGE_API_KEY,
    JUDGE_API_KEY_ENV,
    JUDGE_MODEL,
    JUDGE_MODEL_ENV,
    JUDGE_URL_ENV,
    ClaudeStub,
)
from tests.support.eval_world import (
    DATA_DIR_ENV,
    DATABASE_ENV,
    EMBEDDING_ENV,
    RERANKER_ENV,
    World,
)
from tests.support.tei_server import serve_stub
from tests.support.tei_stub import TeiStub


@pytest.fixture
def tei_stub() -> TeiStub:
    """시험이 요청 횟수와 본문을 보는 임베딩 스텁. `tei_url`이 이것을 띄운다."""
    return TeiStub()


@pytest.fixture
def tei_url(tei_stub: TeiStub) -> Iterator[str]:
    with serve_stub(tei_stub) as url:
        yield url


@pytest.fixture
def reranker_stub() -> TeiStub:
    """전체 실행의 리랭커 스텁. 모델은 묶음 구성의 `reranker_model`과 같다. 시험이 `score_with`로
    점수를 정한다."""
    return TeiStub(model_id="BAAI/bge-reranker-v2-m3")


@pytest.fixture
def reranker_url(
    reranker_stub: TeiStub, world: World, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """리랭커 스텁을 띄우고 `RAG_EVAL_RERANKER_URL`을 준다."""
    del world
    with serve_stub(reranker_stub) as url:
        monkeypatch.setenv(RERANKER_ENV, url)
        yield url


@pytest.fixture
def claude_stub() -> ClaudeStub:
    """판정기의 가짜 끝점. 시험이 `relevant_when`과 오류를 정하고 받은 요청을 본다."""
    return ClaudeStub()


@pytest.fixture
def claude_url(
    claude_stub: ClaudeStub, world: World, monkeypatch: pytest.MonkeyPatch
) -> Iterator[str]:
    """가짜 끝점을 띄우고 판정기의 설정 셋을 준다. `world`가 `RAG_*`를 지운 뒤에 준다."""
    del world
    with serve_claude_stub(claude_stub) as url:
        monkeypatch.setenv(JUDGE_URL_ENV, url)
        monkeypatch.setenv(JUDGE_MODEL_ENV, JUDGE_MODEL)
        monkeypatch.setenv(JUDGE_API_KEY_ENV, JUDGE_API_KEY)
        yield url


@pytest.fixture
def world(
    empty_eval_database_url: str, tei_url: str, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> World:
    """개발자 셸의 `RAG_*`를 지우고(시험이 쓰는 `RAG_TEST_DATABASE_URL`은 남긴다) 평가 전용 이름
    셋을 준다. 작업 폴더는 빈 폴더다."""
    for name in [name for name in os.environ if name.startswith("RAG_")]:
        if name != "RAG_TEST_DATABASE_URL":
            monkeypatch.delenv(name)
    work_dir = tmp_path / "work"
    work_dir.mkdir()
    data_dir = tmp_path / "eval-data"
    monkeypatch.chdir(work_dir)
    monkeypatch.setenv(DATABASE_ENV, empty_eval_database_url)
    monkeypatch.setenv(DATA_DIR_ENV, str(data_dir))
    monkeypatch.setenv(EMBEDDING_ENV, tei_url)
    return World(empty_eval_database_url, data_dir, tei_url, work_dir)
