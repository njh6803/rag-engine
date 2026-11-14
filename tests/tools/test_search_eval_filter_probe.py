"""필터가 붙은 질의의 벡터 후보 수 판정을 실제 데이터베이스 위에서 본다(티켓 search-eval 06, 명세
"지표").

실제 HNSW가 후보를 모자라게 내는 경우는 결정적으로 만들기 어렵다. 그래서 유스케이스가 받는
`VectorIndex`를 감싸 `CandidateScan.INDEX`일 때만 벡터 후보를 지우는 대역(`_CutIndex`)을 쓴다. 정확
스캔은 그대로 돌려, 두 스캔의 후보 수 차이가 있는 질의만 모자란 것으로 세는지를 본다. 늘 0을 내는
구현은 첫째 질의에서, 늘 모자란 것으로 세는 구현은 둘째 질의와 대조 실행에서 걸린다.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from dataclasses import replace
from pathlib import Path

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine
from tests.support.eval_bundle import PASSAGE, PASSAGE_B, passage_evidence
from tests.support.eval_run_support import QUERY_A, QUERY_B, make_bundle, run_index
from tests.support.eval_world import World

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.adapters.eval_set_reader import read_eval_set
from rag_engine.adapters.kiwi import tokenize_keywords
from rag_engine.adapters.postgres.engine import create_engine
from rag_engine.adapters.postgres.unit_of_work import PostgresTransaction, PostgresUnitOfWork
from rag_engine.adapters.postgres.vector_index import PostgresVectorIndex
from rag_engine.adapters.tei import TeiEmbedderPool
from rag_engine.app.eval_run import EvalRunDeps, EvalRunResult, run_fast_evaluation
from rag_engine.domain.entities import CandidateScan, SearchDiagnosis, SearchQuery
from rag_engine.domain.eval_set import EvalSet
from rag_engine.domain.ports import UnitOfWork

CANDIDATES = 50
TIMEOUT_SECONDS = 30.0
BATCH_SIZE = 8
PASS_ALL = {"updated_after": "2026-01-01T00:00:00+09:00"}
PASS_NONE = {"updated_after": "2026-02-01T00:00:00+09:00"}


class _CutIndex(PostgresVectorIndex):
    """`INDEX` 스캔의 진단에서 벡터 순위를 모두 지운다. 정확 스캔은 그대로 돌려준다."""

    async def diagnose_candidates(
        self, query: SearchQuery, *, scan: CandidateScan
    ) -> SearchDiagnosis:
        diagnosis = await super().diagnose_candidates(query, scan=scan)
        if scan is not CandidateScan.INDEX:
            return diagnosis
        return replace(
            diagnosis,
            hits=tuple(replace(line, vector_rank=None) for line in diagnosis.hits),
        )


class _CutTransaction(PostgresTransaction):
    def __init__(self, connection: AsyncConnection) -> None:
        super().__init__(connection)
        self.index = _CutIndex(connection)


class _CutUnitOfWork:
    def __init__(self, engine: AsyncEngine) -> None:
        self._engine = engine

    @asynccontextmanager
    async def begin(self) -> AsyncGenerator[_CutTransaction]:
        async with self._engine.connect() as connection, connection.begin():
            yield _CutTransaction(connection)


@pytest.fixture
def indexed_bundle(world: World, tmp_path: Path) -> Path:
    """q1은 모든 문서를 지나는 필터, q2는 모든 문서를 거르는 필터, q3는 필터가 없다. q2는 묶음의
    목록 검사(`check_eval_set`)가 거부하는 모양이라 이 시험은 목록 검사 없이 묶음을 읽는다."""
    bundle = make_bundle(
        tmp_path,
        evidence=[
            passage_evidence("q1", "a.docx", PASSAGE),
            passage_evidence("q2", "sub/b.docx", PASSAGE_B),
            passage_evidence("q3", "a.docx", PASSAGE),
        ],
        human=[
            {"evidence_id": "q1", "query": QUERY_A, "filter": PASS_ALL},
            {"evidence_id": "q2", "query": QUERY_B, "filter": PASS_NONE},
            {"evidence_id": "q3", "query": QUERY_A},
        ],
    )
    assert run_index(bundle) == 0
    return bundle


async def _evaluate(tei_url: str, unit_of_work: UnitOfWork, eval_set: EvalSet) -> EvalRunResult:
    pool = TeiEmbedderPool(
        lambda endpoint: httpx.AsyncClient(base_url=endpoint, timeout=TIMEOUT_SECONDS),
        batch_size=BATCH_SIZE,
    )
    deps = EvalRunDeps(
        unit_of_work=unit_of_work,
        embedder_for=lambda version: pool(replace(version, embedding_endpoint=tei_url)),
        tokenize_keywords=tokenize_keywords,
    )
    try:
        return await run_fast_evaluation(deps, eval_set, candidates=CANDIDATES)
    finally:
        await pool.aclose()


def _short(result: EvalRunResult) -> dict[str, bool | None]:
    return {
        outcome.evidence_id: None if outcome.filter_probe is None else outcome.filter_probe.short
        for outcome in result.outcomes
    }


async def test_색인_스캔의_벡터_후보가_정확_스캔보다_적은_필터_질의만_모자란_것으로_센다(
    world: World, indexed_bundle: Path
) -> None:
    eval_set = read_eval_set(BundlePaths(indexed_bundle))
    engine = create_engine(world.database_url)
    try:
        cut = await _evaluate(world.tei_url, _CutUnitOfWork(engine), eval_set)
        plain = await _evaluate(world.tei_url, PostgresUnitOfWork(engine), eval_set)
    finally:
        await engine.dispose()

    # q1: 정확 스캔이 벡터 후보 둘을 내는데 대역의 색인 스캔은 0이라 모자라다.
    # q2: 필터가 모든 조각을 걸러 정확 스캔도 0이다. 후보를 채우지 못한 몫은 모자란 것이 아니다.
    # q3: 필터가 없어 `filter_probe`가 없다.
    assert _short(cut) == {"q1": True, "q2": False, "q3": None}
    assert _short(plain) == {"q1": False, "q2": False, "q3": None}
    probe = cut.outcomes[0].filter_probe
    assert probe is not None
    assert (probe.expected_vectors, probe.index_vectors) == (2, 0)
