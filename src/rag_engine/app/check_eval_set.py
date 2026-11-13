"""읽어 온 평가 세트의 목록 판정(명세 "평가 세트의 형식"의 `validate`가 보는 것).

파일을 열지 않고 값끼리만 견준다. `id`와 `evidence_id`의 짝, 한 질의 목록 안의 같은 `evidence_id`,
유형 표지의 낱말, `groups`가 든 필터, 목록에 없는 문서, 기간 필터가 기대 근거의 문서를 거르는지,
사람 판정이 가리키는 곳이다. 파일의 존재와 해시와 경로와 용량은 어댑터가 본다.

기간 필터의 경계는 검색의 필터와 같다. `updated_after`는 그 시각을 포함하고 `updated_before`는
포함하지 않는다(`SearchFilter`). 기대 근거가 가리키는 문서는 모두 그 기간 안이어야 한다. 재현율과
nDCG의 분모가 기대 근거의 수이기 때문이다.
"""

from collections import Counter
from collections.abc import Iterable, Mapping

from rag_engine.domain.eval_set import (
    EVIDENCE_TAGS,
    MISS_CAUSES,
    EvalDocument,
    EvalFilter,
    EvalProblem,
    EvalQuery,
    EvalSet,
    EvidenceItem,
    MissReview,
    QueryList,
)


def check_eval_set(eval_set: EvalSet) -> tuple[EvalProblem, ...]:
    """목록의 오류를 모두 낸다. 문제가 없으면 빈 튜플이다."""
    documents = {document.key: document for document in eval_set.documents}
    evidence = {item.id: item for item in eval_set.evidence}
    problems = [
        *_duplicate_problems(
            "documents.json", "문서의 key", (document.key for document in eval_set.documents)
        ),
        *_duplicate_problems("evidence.jsonl", "기대 근거의 id", (i.id for i in eval_set.evidence)),
        *(p for item in eval_set.evidence for p in _evidence_problems(item, documents)),
        *(
            p
            for query_list in eval_set.query_lists
            for p in _query_list_problems(query_list, evidence, documents)
        ),
        *(p for review in eval_set.miss_reviews for p in _review_problems(review, eval_set)),
    ]
    return tuple(problems)


def _duplicate_problems(where: str, what: str, values: Iterable[str]) -> list[EvalProblem]:
    counts = Counter(values)
    return [
        EvalProblem(where, f"{what} {value}이(가) 겹친다") for value, n in counts.items() if n > 1
    ]


def _evidence_problems(
    item: EvidenceItem, documents: Mapping[str, EvalDocument]
) -> list[EvalProblem]:
    where = f"기대 근거 {item.id}"
    problems: list[EvalProblem] = []
    if not item.evidence:
        problems.append(EvalProblem(where, "기대 근거가 하나도 없다. 하나 이상 필요하다"))
    problems.extend(
        EvalProblem(
            where, f"유형 표지 {tag}은(는) 모르는 낱말이다. {_words(EVIDENCE_TAGS)} 중 하나"
        )
        for tag in item.tags
        if tag not in EVIDENCE_TAGS
    )
    problems.extend(
        EvalProblem(where, f"문서 목록에 없는 문서 {expectation.document}를 가리킨다")
        for expectation in item.evidence
        if expectation.document not in documents
    )
    return problems


def _query_list_problems(
    query_list: QueryList,
    evidence: Mapping[str, EvidenceItem],
    documents: Mapping[str, EvalDocument],
) -> list[EvalProblem]:
    problems: list[EvalProblem] = []
    for evidence_id, count in Counter(q.evidence_id for q in query_list.queries).items():
        if count > 1:
            problems.append(
                EvalProblem(
                    f"질의 목록 {query_list.name}",
                    f"같은 evidence_id {evidence_id}가 {count}번 나온다. 한 번만 나와야 한다",
                )
            )
    for position, query in enumerate(query_list.queries, start=1):
        where = f"질의 목록 {query_list.name}의 {position}번째 질의"
        problems.extend(_query_problems(where, query, evidence, documents))
    return problems


def _query_problems(
    where: str,
    query: EvalQuery,
    evidence: Mapping[str, EvidenceItem],
    documents: Mapping[str, EvalDocument],
) -> list[EvalProblem]:
    item = evidence.get(query.evidence_id)
    problems: list[EvalProblem] = []
    if item is None:
        problems.append(EvalProblem(where, f"evidence_id {query.evidence_id}의 기대 근거가 없다"))
    if query.filter is None:
        return problems
    if query.filter.groups is not None:
        problems.append(
            EvalProblem(
                where,
                "filter의 groups는 이 판에서 쓰지 못한다. 그룹 필터는 아무 문서에도 맞지 않거나 "
                "거르지 않는 것과 같다",
            )
        )
    if item is not None:
        problems.extend(_period_problems(where, query.filter, item, documents))
    return problems


def _period_problems(
    where: str,
    query_filter: EvalFilter,
    item: EvidenceItem,
    documents: Mapping[str, EvalDocument],
) -> list[EvalProblem]:
    """기대 근거의 문서 가운데 필터의 기간 밖인 것마다 하나를 낸다. 목록에 없는 문서는 건너뛴다."""
    problems: list[EvalProblem] = []
    after, before = query_filter.updated_after, query_filter.updated_before
    for key in dict.fromkeys(expectation.document for expectation in item.evidence):
        document = documents.get(key)
        if document is None:
            continue
        if after is not None and document.updated_at < after:
            problems.append(
                EvalProblem(
                    where,
                    f"기대 근거의 문서 {key}(갱신 {document.updated_at.isoformat()})는 "
                    f"updated_after {after.isoformat()}보다 앞이라 필터가 거른다",
                )
            )
        if before is not None and document.updated_at >= before:
            problems.append(
                EvalProblem(
                    where,
                    f"기대 근거의 문서 {key}(갱신 {document.updated_at.isoformat()})는 "
                    f"updated_before {before.isoformat()} 이후라 필터가 거른다."
                    " updated_before는 그 시각을 포함하지 않는다",
                )
            )
    return problems


def _review_problems(review: MissReview, eval_set: EvalSet) -> list[EvalProblem]:
    where = f"miss-review.jsonl {review.query_list}/{review.evidence_id}"
    problems: list[EvalProblem] = []
    if all(query_list.name != review.query_list for query_list in eval_set.query_lists):
        problems.append(EvalProblem(where, f"질의 목록 {review.query_list}이(가) 없다"))
    if all(item.id != review.evidence_id for item in eval_set.evidence):
        problems.append(EvalProblem(where, f"evidence_id {review.evidence_id}의 기대 근거가 없다"))
    if review.cause not in MISS_CAUSES:
        problems.append(
            EvalProblem(
                where, f"까닭 {review.cause}은(는) 모르는 낱말이다. {_words(MISS_CAUSES)} 중 하나"
            )
        )
    return problems


def _words(words: Iterable[str]) -> str:
    return ", ".join(sorted(words))
