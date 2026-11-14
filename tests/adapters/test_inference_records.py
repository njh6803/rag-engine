"""추론 기록을 끼우는 감싸는 어댑터(명세 search-eval "추론 기록", 티켓 07).

감싼 포트를 부르기 전에 기록을 보고, 없으면 감싼 포트를 불러 결과를 쓴다. 토큰 세기는 기록하지
않고 그대로 넘긴다. 시험은 가짜 임베더와 가짜 리랭커가 받은 호출을 세어 "기록에 있는 글은 감싼
포트를 부르지 않는다"를 본다.
"""

import hashlib
from collections.abc import Sequence
from pathlib import Path

import pytest
from tests.support.eval_bundle import make_folder_link

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.adapters.inference_record_files import RecordKind
from rag_engine.adapters.inference_records import (
    READ_COMPUTE_LIMIT,
    EmbeddingRecorder,
    RecordMode,
    RecordsOptions,
    RecordsRun,
    RerankRecorder,
    embedding_key,
    rerank_key,
)
from rag_engine.domain.errors import PermanentFailure
from rag_engine.domain.eval_set import ChunkingConfig, EvalConfig

MODEL = "모델-가"
DIMENSIONS = 2


class _Embedder:
    """호출을 센다. 글마다 길이로 정한 결정적 벡터를 낸다."""

    def __init__(self) -> None:
        self.embedded: list[list[str]] = []
        self.token_calls = 0

    async def embed(self, texts: Sequence[str]) -> list[tuple[float, ...]]:
        self.embedded.append(list(texts))
        return [(float(len(text)), 1.0) for text in texts]

    async def count_tokens(self, texts: Sequence[str]) -> list[int]:
        self.token_calls += 1
        return [len(text) for text in texts]

    async def special_token_count(self) -> int:
        self.token_calls += 1
        return 2

    async def token_spans(self, text: str) -> list[tuple[int, int]]:
        self.token_calls += 1
        return [(0, len(text))]


class _Reranker:
    def __init__(self) -> None:
        self.calls: list[tuple[str, list[str]]] = []

    async def rerank(self, query: str, texts: Sequence[str]) -> list[float]:
        self.calls.append((query, list(texts)))
        return [float(len(text)) / 10 for text in texts]


def test_임베딩_열쇠는_모델_이름과_글의_utf8_바이트로_낸다() -> None:
    expected = hashlib.sha256(MODEL.encode() + b"\0" + "연차휴가".encode()).hexdigest()

    assert embedding_key(MODEL, "연차휴가") == expected


def test_리랭크_열쇠는_모델_이름과_질의와_글로_낸다() -> None:
    expected = hashlib.sha256(
        MODEL.encode() + b"\0" + "질의".encode() + b"\0" + "글".encode()
    ).hexdigest()

    assert rerank_key(MODEL, "질의", "글") == expected


def test_열쇠는_모델_이름이_다르면_달라지고_경계가_다른_글_쌍은_갈린다() -> None:
    assert embedding_key("모델-가", "글") != embedding_key("모델-나", "글")
    assert rerank_key(MODEL, "가", "나다") != rerank_key(MODEL, "가나", "다")


async def test_기록에_있는_글은_감싼_임베더를_부르지_않는다() -> None:
    known = {embedding_key(MODEL, "기록된 글"): (9.0, 9.0)}
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known=known, limit=None)
    inner = _Embedder()

    vectors = await recorder.wrap(inner).embed(["기록된 글"])

    assert vectors == [(9.0, 9.0)]
    assert inner.embedded == []
    assert (recorder.read_count, recorder.computed_count) == (1, 0)


async def test_기록에_없는_글만_감싼_임베더로_계산하고_입력_순서를_지킨다() -> None:
    known = {embedding_key(MODEL, "기록"): (9.0, 9.0)}
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known=known, limit=None)
    inner = _Embedder()

    vectors = await recorder.wrap(inner).embed(["새 글", "기록", "또 새 글"])

    assert vectors == [(3.0, 1.0), (9.0, 9.0), (5.0, 1.0)]
    assert inner.embedded == [["새 글", "또 새 글"]]
    counts = (recorder.read_count, recorder.computed_count)
    assert counts == (1, 2), f"기록에서 읽은 수와 새로 계산한 수: {counts}"


async def test_같은_글이_거듭_와도_한_번만_계산하고_열쇠로_센다() -> None:
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known={}, limit=None)
    inner = _Embedder()
    wrapped = recorder.wrap(inner)

    await wrapped.embed(["같은 글", "같은 글"])
    await wrapped.embed(["같은 글"])

    assert inner.embedded == [["같은 글"]]
    assert (recorder.read_count, recorder.computed_count) == (0, 1)
    assert list(recorder.used) == [embedding_key(MODEL, "같은 글")]


async def test_이번_실행이_쓴_열쇠만_used에_남는다() -> None:
    stale = embedding_key(MODEL, "쓰이지 않은 글")
    known = {stale: (1.0, 1.0), embedding_key(MODEL, "쓴 글"): (2.0, 2.0)}
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known=known, limit=None)

    await recorder.wrap(_Embedder()).embed(["쓴 글"])

    assert stale not in recorder.used
    assert set(recorder.used) == {embedding_key(MODEL, "쓴 글")}


async def test_모델_이름이_다르면_기록의_값을_쓰지_않는다() -> None:
    known = {embedding_key("모델-가", "글"): (9.0, 9.0)}
    recorder = EmbeddingRecorder(model="모델-나", dimensions=DIMENSIONS, known=known, limit=None)
    inner = _Embedder()

    vectors = await recorder.wrap(inner).embed(["글"])

    assert vectors == [(1.0, 1.0)]
    assert inner.embedded == [["글"]]


async def test_읽기에서_새로_계산할_글이_상한을_넘으면_계산하지_않고_멈춘다() -> None:
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known={}, limit=3)
    inner = _Embedder()
    wrapped = recorder.wrap(inner)

    with pytest.raises(PermanentFailure, match="상한을 넘어"):
        await wrapped.embed(["글 1", "글 2", "글 3", "글 4"])

    assert inner.embedded == []
    assert recorder.exceeded is True


async def test_상한_안의_계산은_누적해서_세고_넘는_순간_멈춘다() -> None:
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known={}, limit=3)
    inner = _Embedder()
    wrapped = recorder.wrap(inner)

    await wrapped.embed(["글 1", "글 2"])
    with pytest.raises(PermanentFailure, match="상한을 넘어"):
        await wrapped.embed(["글 3", "글 4"])

    assert inner.embedded == [["글 1", "글 2"]]
    assert recorder.computed_count == 2


async def test_새로_계산할_글이_상한과_같은_수이면_계산한다() -> None:
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known={}, limit=3)
    inner = _Embedder()

    await recorder.wrap(inner).embed(["글 1", "글 2", "글 3"])

    assert inner.embedded == [["글 1", "글 2", "글 3"]]
    assert recorder.exceeded is False


async def test_상한을_넘은_뒤에는_작은_호출도_계산하지_않는다() -> None:
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known={}, limit=1)
    inner = _Embedder()
    wrapped = recorder.wrap(inner)
    with pytest.raises(PermanentFailure, match="상한을 넘어"):
        await wrapped.embed(["글 1", "글 2"])

    with pytest.raises(PermanentFailure, match="상한을 넘어"):
        await wrapped.embed(["글 3"])

    assert inner.embedded == []


async def test_상한이_없으면_얼마든지_계산한다() -> None:
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known={}, limit=None)
    inner = _Embedder()
    texts = [f"글 {number}" for number in range(READ_COMPUTE_LIMIT + 50)]

    await recorder.wrap(inner).embed(texts)

    assert recorder.computed_count == READ_COMPUTE_LIMIT + 50
    assert recorder.exceeded is False


async def test_토큰_세기는_기록하지_않고_감싼_포트로_넘긴다() -> None:
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known={}, limit=None)
    inner = _Embedder()
    wrapped = recorder.wrap(inner)

    assert await wrapped.count_tokens(["가나"]) == [2]
    assert await wrapped.special_token_count() == 2
    assert await wrapped.token_spans("가나다") == [(0, 3)]

    assert inner.token_calls == 3
    assert recorder.used == {}


async def test_빈_글_목록은_감싼_임베더를_부르지_않는다() -> None:
    recorder = EmbeddingRecorder(model=MODEL, dimensions=DIMENSIONS, known={}, limit=None)
    inner = _Embedder()

    assert await recorder.wrap(inner).embed([]) == []
    assert inner.embedded == []


async def test_리랭크는_기록에_있는_쌍을_감싼_리랭커로_부르지_않는다() -> None:
    known = {rerank_key(MODEL, "질의", "기록된 글"): 0.75}
    recorder = RerankRecorder(model=MODEL, known=known)
    inner = _Reranker()

    scores = await recorder.wrap(inner).rerank("질의", ["기록된 글", "새 글"])

    assert scores == [0.75, 0.3]
    assert inner.calls == [("질의", ["새 글"])]
    assert (recorder.read_count, recorder.computed_count) == (1, 1)


async def test_리랭크_기록은_질의가_다르면_같은_글도_다른_쌍이다() -> None:
    known = {rerank_key(MODEL, "질의 가", "글"): 0.75}
    recorder = RerankRecorder(model=MODEL, known=known)
    inner = _Reranker()

    await recorder.wrap(inner).rerank("질의 나", ["글"])

    assert inner.calls == [("질의 나", ["글"])]


async def test_리랭커가_없으면_기록에_없는_쌍_하나에도_실패한다() -> None:
    known = {rerank_key(MODEL, "질의", "기록된 글"): 0.75}
    recorder = RerankRecorder(model=MODEL, known=known)
    wrapped = recorder.wrap(None)

    assert await wrapped.rerank("질의", ["기록된 글"]) == [0.75]
    with pytest.raises(PermanentFailure, match="끝점이 없다"):
        await wrapped.rerank("질의", ["기록된 글", "없는 글"])

    assert recorder.unavailable is True


async def test_리랭크도_이번_실행이_쓴_쌍만_used에_남는다() -> None:
    stale = rerank_key(MODEL, "질의", "쓰이지 않은 글")
    known = {stale: 0.1}
    recorder = RerankRecorder(model=MODEL, known=known)

    await recorder.wrap(_Reranker()).rerank("질의", ["쓴 글"])

    assert set(recorder.used) == {rerank_key(MODEL, "질의", "쓴 글")}


async def test_리랭크의_빈_글_목록은_감싼_리랭커를_부르지_않는다() -> None:
    recorder = RerankRecorder(model=MODEL, known={})
    inner = _Reranker()

    assert await recorder.wrap(inner).rerank("질의", []) == []
    assert inner.calls == []


def _config() -> EvalConfig:
    return EvalConfig(
        embedding_model=MODEL,
        embedding_dimensions=DIMENSIONS,
        reranker_model="리랭커-가",
        chunking=ChunkingConfig(strategy="structure_first", max_tokens=512, overlap_tokens=64),
        search_candidates=50,
        tei_version="1.9.4",
        judge_model="none",
        judge_prompt_version="1",
    )


def test_write는_주인_파일_중_하나라도_쓸_경로가_묶음_밖이면_시작할_때_거부한다(
    tmp_path: Path,
) -> None:
    bundle = tmp_path / "bundle"
    (bundle / "records").mkdir(parents=True)
    outside = tmp_path / "outside"
    outside.mkdir()
    make_folder_link(bundle / "records" / "rerank.jsonl.tmp", outside)

    with pytest.raises(BundlePathError):
        RecordsRun(
            BundlePaths(bundle),
            _config(),
            RecordsOptions(mode=RecordMode.WRITE, device="cpu"),
            owned=(RecordKind.QUERY_EMBEDDINGS, RecordKind.RERANK),
        )
