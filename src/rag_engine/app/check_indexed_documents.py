"""`validate --indexed`의 색인된 문서 판정(명세 search-eval "평가 세트의 형식"의 `validate`가 보는
것).

묶음의 모든 문서가 데이터베이스에 색인되어 있어야 하고(색인되지 않은 문서가 하나라도 있으면
실패한다), 글귀마다 그 문서의 본문에 들어 있어야 한다. 색인된 문서는 데이터베이스의 문서 내용 해시가
문서 목록의 `sha256`과 같고, 현재 판의 색인 상태가 `indexed`이며 그 상태가 지금 내용으로 지은
것이고, 파싱 결과가 지금 내용의 것이다. 이 가운데 하나라도 아니면 그 문서는 색인되어 있지 않은
것으로 센다.

본문은 문서의 최신 파싱 결과에서 짓는다(`document_body`). 제목 블록의 토큰 수는 현재 판의 모델로
센다. 센 끝점은 호출하는 쪽이 건넨 자가 정한다. 평가는 판에 적힌 끝점이 아니라 환경의 끝점을 쓴다.
"""

from collections.abc import Callable

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.app.eval_passages import check_passages, document_body
from rag_engine.domain.entities import IndexStateStatus, IndexVersion
from rag_engine.domain.eval_set import EvalProblem, EvalSet
from rag_engine.domain.ports import TokenMeter, UnitOfWork

_NOT_INDEXED = "색인되어 있지 않다"


async def check_indexed_documents(
    unit_of_work: UnitOfWork, eval_set: EvalSet, meter_for: Callable[[IndexVersion], TokenMeter]
) -> tuple[tuple[EvalProblem, ...], tuple[EvalProblem, ...]]:
    """색인된 문서와 글귀를 본다. (오류, 경고)를 낸다."""
    problems: list[EvalProblem] = []
    bodies: dict[str, str] = {}
    async with unit_of_work.begin() as transaction:
        catalog = transaction.catalog
        source = await catalog.get_source(DEFAULT_NAME)
        knowledge_base = await catalog.get_knowledge_base(DEFAULT_NAME)
        version = (
            None
            if knowledge_base is None or knowledge_base.current_index_version_id is None
            else await catalog.get_index_version(knowledge_base.current_index_version_id)
        )
        if source is None or version is None:
            return (
                tuple(
                    EvalProblem(document.key, f"{_NOT_INDEXED}(기본 지식베이스의 현재 판이 없다)")
                    for document in eval_set.documents
                ),
                (),
            )
        meter = meter_for(version)
        for listed in eval_set.documents:
            document = await transaction.documents.get_by_key(source.id, listed.key)
            if document is None or document.deleted_at is not None:
                problems.append(EvalProblem(listed.key, _NOT_INDEXED))
                continue
            if document.content_hash != listed.sha256:
                problems.append(
                    EvalProblem(
                        listed.key,
                        f"{_NOT_INDEXED}(데이터베이스의 문서의 내용 해시가 문서 목록과 다르다)",
                    )
                )
                continue
            state = await transaction.index.get_state(document.id, version.id)
            content = await transaction.documents.get_content(document.id)
            if (
                state is None
                or state.status is not IndexStateStatus.INDEXED
                or state.built_content_hash != document.content_hash
                or content is None
                or content.parsed_content_hash != document.content_hash
            ):
                problems.append(EvalProblem(listed.key, _NOT_INDEXED))
                continue
            bodies[listed.key] = await document_body(
                content.blocks, version.chunking.max_tokens, meter
            )
    passage_problems, warnings = check_passages(eval_set, bodies)
    return (*problems, *passage_problems), warnings
