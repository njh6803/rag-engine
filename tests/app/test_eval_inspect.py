"""`inspect`가 찍는 글(티켓 search-eval 06, 명세 "보고서"의 `inspect` 항목).

질의의 글, 기대 근거, 단계마다의 상위 조각의 글을 사람이 읽는 글 하나로 옮긴다. 이 글은 표준
출력에만 가고 파일로 쓰지 않는다. 조각의 글이 실리는 유일한 자리라 보고서에 쓰는 값과 다르다.
"""

from rag_engine.app.eval_inspect import InspectedChunk, Inspection, StageView, inspection_text
from rag_engine.app.eval_misses import MissCause
from rag_engine.app.eval_run import QueryMiss
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.eval_set import PageEvidence, PassageEvidence


def _inspection(*, miss: QueryMiss | None = None) -> Inspection:
    return Inspection(
        query_list="human",
        evidence_id="q1",
        query="연차휴가는 언제 생기나요",
        filter=None,
        tags=("table",),
        expectations=(
            PassageEvidence(document="a.docx", passage="입사 일 년 뒤부터 발생한다"),
            PageEvidence(document="b.pdf", page=2),
        ),
        stages=(
            StageView(
                stage=Stage.FUSED,
                chunks=(
                    InspectedChunk(
                        rank=1,
                        key="a.docx",
                        ordinal=3,
                        section=("제2장", "휴가"),
                        text="연차휴가는 입사 일 년 뒤부터 발생한다. 그 밖의 말",
                        reached=True,
                        score=None,
                    ),
                    InspectedChunk(
                        rank=2,
                        key="c.docx",
                        ordinal=0,
                        section=(),
                        text="출장 규정",
                        reached=False,
                        score=None,
                    ),
                ),
            ),
        ),
        miss=miss,
    )


def test_질의의_글과_기대_근거를_싣는다() -> None:
    text = inspection_text(_inspection())

    assert "human" in text
    assert "q1" in text
    assert "연차휴가는 언제 생기나요" in text
    assert "a.docx" in text
    assert "입사 일 년 뒤부터 발생한다" in text
    assert "b.pdf" in text
    assert "2쪽" in text


def test_단계마다_상위_조각의_순위와_글과_닿았는지를_싣는다() -> None:
    text = inspection_text(_inspection())

    assert "fused" in text
    assert "연차휴가는 입사 일 년 뒤부터 발생한다. 그 밖의 말" in text
    assert "출장 규정" in text
    assert "제2장 > 휴가" in text
    lines = text.splitlines()
    reached = next(line for line in lines if line.lstrip().startswith("1."))
    missed = next(line for line in lines if line.lstrip().startswith("2."))
    assert "닿음" in reached
    assert "닿음" not in missed


def test_놓친_질의는_탈락_지점과_낱말_겹침을_싣고_겹침이_없으면_없음이라고_적는다() -> None:
    with_overlap = inspection_text(_inspection(miss=QueryMiss(MissCause.LOST_IN_FUSION, 0.5)))
    without = inspection_text(_inspection(miss=QueryMiss(MissCause.NO_MATCHING_CHUNK, None)))

    assert "lost_in_fusion" in with_overlap
    assert "0.500" in with_overlap
    assert "no_matching_chunk" in without
    assert "낱말 겹침: 없음" in without


def test_놓치지_않은_질의는_마지막_단계에서_닿았다고_적는다() -> None:
    assert "마지막 단계에서 닿았다" in inspection_text(_inspection())
