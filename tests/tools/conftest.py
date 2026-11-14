"""`tools/search_eval.py` 시험의 픽스처(티켓 search-eval 03, 04)."""

import os
from collections.abc import Iterator
from pathlib import Path

import pytest
from tests.support.eval_world import DATA_DIR_ENV, DATABASE_ENV, EMBEDDING_ENV, World
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
