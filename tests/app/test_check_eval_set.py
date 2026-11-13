"""평가 세트 묶음의 목록 판정(`check_eval_set`, 명세 "평가 세트의 형식"의 `validate`가 보는 것).

파일을 열지 않고 읽어 온 값만으로 판정한다. 파일의 존재·해시·경로·용량은 어댑터 시험이
(`tests/tools/test_search_eval.py`) 본다.
"""

from dataclasses import replace
from datetime import UTC, date, datetime, timedelta, timezone

from rag_engine.app.check_eval_set import check_eval_set
from rag_engine.domain.eval_set import (
    ChunkingConfig,
    EvalConfig,
    EvalDocument,
    EvalFilter,
    EvalProblem,
    EvalQuery,
    EvalSet,
    EvidenceItem,
    MissReview,
    PageEvidence,
    PassageEvidence,
    QueryList,
    QueryStyle,
)

KST = timezone(timedelta(hours=9))


def _document(key: str, updated_at: datetime) -> EvalDocument:
    return EvalDocument(
        key=key,
        title=key,
        publisher="행정안전부",
        source_url="https://example.invalid/" + key,
        license="공공누리 제1유형",
        license_evidence="문서 1쪽",
        downloaded_at=date(2026, 11, 13),
        sha256="0" * 64,
        bytes=10,
        updated_at=updated_at,
    )


def _eval_set(**changes: object) -> EvalSet:
    """문제 없는 작은 세트. 문서 둘, 기대 근거 둘, 질의 목록 둘이다."""
    base = EvalSet(
        format_version="1.0.0",
        name="tiny",
        config=EvalConfig(
            embedding_model="BAAI/bge-m3",
            embedding_dimensions=1024,
            reranker_model="BAAI/bge-reranker-v2-m3",
            chunking=ChunkingConfig(strategy="structure_first", max_tokens=512, overlap_tokens=64),
            search_candidates=50,
            tei_version="1.9",
            judge_model="none",
            judge_prompt_version="1",
        ),
        documents=(
            _document("a.docx", datetime(2026, 1, 15, tzinfo=KST)),
            _document("b.pdf", datetime(2026, 3, 1, tzinfo=KST)),
        ),
        evidence=(
            EvidenceItem(
                id="q1",
                evidence=(PassageEvidence(document="a.docx", passage="연차는 일 년 뒤 발생한다"),),
                tags=("table",),
            ),
            EvidenceItem(id="q2", evidence=(PageEvidence(document="b.pdf", page=2),), tags=()),
        ),
        query_lists=(
            QueryList(
                name="human",
                style=QueryStyle.QUESTION,
                queries=(
                    EvalQuery(evidence_id="q1", query="연차는 언제 생기나요", filter=None),
                    EvalQuery(evidence_id="q2", query="출장비는", filter=None),
                ),
            ),
            QueryList(
                name="keyword",
                style=QueryStyle.KEYWORD,
                queries=(EvalQuery(evidence_id="q1", query="연차 발생", filter=None),),
            ),
        ),
        miss_reviews=(),
    )
    return replace(base, **changes)


def _filtered(
    document_updated_at: datetime,
    *,
    after: datetime | None = None,
    before: datetime | None = None,
) -> EvalSet:
    """`a.docx`(주어진 갱신일)를 기대 근거로 하는 질의에 기간 필터를 붙인 세트."""
    base = _eval_set()
    documents = (_document("a.docx", document_updated_at), base.documents[1])
    queries = QueryList(
        name="human",
        style=QueryStyle.QUESTION,
        queries=(
            EvalQuery(
                evidence_id="q1",
                query="연차는 언제 생기나요",
                filter=EvalFilter(groups=None, updated_after=after, updated_before=before),
            ),
        ),
    )
    return replace(base, documents=documents, query_lists=(queries,))


def _reasons(problems: tuple[EvalProblem, ...]) -> str:
    return "\n".join(str(problem) for problem in problems)


def test_문제가_없는_세트는_빈_목록을_낸다() -> None:
    assert check_eval_set(_eval_set()) == ()


def test_기대_근거의_id가_겹치면_까닭과_함께_거부한다() -> None:
    base = _eval_set()
    duplicated = replace(base, evidence=(*base.evidence, base.evidence[0]))

    reasons = _reasons(check_eval_set(duplicated))

    assert "q1" in reasons
    assert "겹친다" in reasons


def test_질의의_evidence_id에_맞는_기대_근거가_없으면_거부한다() -> None:
    base = _eval_set()
    orphan = QueryList(
        name="human",
        style=QueryStyle.QUESTION,
        queries=(EvalQuery(evidence_id="없는-id", query="질문", filter=None),),
    )

    reasons = _reasons(check_eval_set(replace(base, query_lists=(orphan,))))

    assert "없는-id" in reasons
    assert "기대 근거가 없다" in reasons


def test_한_질의_목록_안의_같은_evidence_id는_거부한다() -> None:
    twice = QueryList(
        name="human",
        style=QueryStyle.QUESTION,
        queries=(
            EvalQuery(evidence_id="q1", query="처음", filter=None),
            EvalQuery(evidence_id="q1", query="다시", filter=None),
        ),
    )

    reasons = _reasons(check_eval_set(replace(_eval_set(), query_lists=(twice,))))

    assert "human" in reasons
    assert "q1" in reasons
    assert "한 번만" in reasons


def test_다른_질의_목록에_같은_evidence_id가_있는_것은_받는다() -> None:
    # 기본 세트의 두 질의 목록이 모두 q1을 질의한다.
    assert check_eval_set(_eval_set()) == ()


def test_모르는_유형_표지는_거부한다() -> None:
    base = _eval_set()
    tagged = replace(base.evidence[0], tags=("table", "diagram"))

    reasons = _reasons(check_eval_set(replace(base, evidence=(tagged, base.evidence[1]))))

    assert "diagram" in reasons
    assert "유형 표지" in reasons


def test_groups가_든_필터는_거부한다() -> None:
    base = _eval_set()
    grouped = QueryList(
        name="human",
        style=QueryStyle.QUESTION,
        queries=(
            EvalQuery(
                evidence_id="q1",
                query="질문",
                filter=EvalFilter(groups=("팀",), updated_after=None, updated_before=None),
            ),
        ),
    )

    reasons = _reasons(check_eval_set(replace(base, query_lists=(grouped,))))

    assert "groups" in reasons
    assert "그룹 필터" in reasons


def test_기대_근거가_목록에_없는_문서를_가리키면_거부한다() -> None:
    base = _eval_set()
    missing = EvidenceItem(id="q1", evidence=(PageEvidence(document="없는.pdf", page=1),), tags=())

    reasons = _reasons(check_eval_set(replace(base, evidence=(missing, base.evidence[1]))))

    assert "없는.pdf" in reasons
    assert "목록에 없는 문서" in reasons


def test_문서_목록의_같은_key는_거부한다() -> None:
    base = _eval_set()

    reasons = _reasons(
        check_eval_set(replace(base, documents=(*base.documents, base.documents[0])))
    )

    assert "a.docx" in reasons
    assert "겹친다" in reasons


def test_문서의_날짜가_updated_before와_같으면_거부한다() -> None:
    boundary = datetime(2026, 1, 15, tzinfo=KST)

    reasons = _reasons(check_eval_set(_filtered(boundary, before=boundary)))

    assert "a.docx" in reasons
    assert "updated_before" in reasons


def test_문서의_날짜가_updated_after와_같으면_받는다() -> None:
    boundary = datetime(2026, 1, 15, tzinfo=KST)

    assert check_eval_set(_filtered(boundary, after=boundary)) == ()


def test_문서의_날짜가_updated_after보다_앞서면_거부한다() -> None:
    boundary = datetime(2026, 1, 15, tzinfo=KST)

    reasons = _reasons(check_eval_set(_filtered(boundary - timedelta(seconds=1), after=boundary)))

    assert "updated_after" in reasons


def test_기간은_오프셋이_다른_시각과도_같은_순간으로_견준다() -> None:
    # 2026-01-15 00:00 +09:00는 2026-01-14 15:00 UTC와 같은 순간이다.
    updated_at = datetime(2026, 1, 15, tzinfo=KST)
    same_instant_in_utc = datetime(2026, 1, 14, 15, tzinfo=UTC)

    assert check_eval_set(_filtered(updated_at, after=same_instant_in_utc)) == ()
    assert "updated_before" in _reasons(
        check_eval_set(_filtered(updated_at, before=same_instant_in_utc))
    )


def test_기대_근거의_문서가_하나라도_기간_밖이면_거부한다() -> None:
    base = _eval_set()
    both = replace(
        base.evidence[0],
        evidence=(
            PageEvidence(document="a.docx", page=1),
            PageEvidence(document="b.pdf", page=1),
        ),
    )
    filtered = QueryList(
        name="human",
        style=QueryStyle.QUESTION,
        queries=(
            EvalQuery(
                evidence_id="q1",
                query="질문",
                # a.docx(1월 15일)는 안이고 b.pdf(3월 1일)는 밖이다.
                filter=EvalFilter(
                    groups=None,
                    updated_after=None,
                    updated_before=datetime(2026, 2, 1, tzinfo=KST),
                ),
            ),
        ),
    )

    reasons = _reasons(
        check_eval_set(replace(base, evidence=(both, base.evidence[1]), query_lists=(filtered,)))
    )

    assert "b.pdf" in reasons
    assert "a.docx" not in reasons


def test_사람_판정이_모르는_질의_목록이나_기대_근거를_가리키면_거부한다() -> None:
    reviews = (
        MissReview(query_list="없는목록", evidence_id="q1", cause="vocabulary", confirmed=True),
        MissReview(query_list="human", evidence_id="없는-id", cause="vocabulary", confirmed=False),
    )

    reasons = _reasons(check_eval_set(_eval_set(miss_reviews=reviews)))

    assert "없는목록" in reasons
    assert "없는-id" in reasons


def test_사람_판정이_모르는_까닭_낱말을_쓰면_거부한다() -> None:
    review = MissReview(query_list="human", evidence_id="q1", cause="게을러서", confirmed=True)

    reasons = _reasons(check_eval_set(_eval_set(miss_reviews=(review,))))

    assert "게을러서" in reasons
    assert "까닭" in reasons
