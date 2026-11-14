"""평가 데이터베이스가 이 묶음의 것인지 보는 판정(명세 search-eval "자리와 층"의 `index` 항목과
"평가 전용 데이터베이스" 항목). 스키마를 올리기 전에 한다.

둘을 본다. 데이터베이스에 든 문서의 키가 모두 묶음의 문서 목록에 있고 그 내용 해시가 목록의
`sha256`과 글자 그대로 같은지(수집이 내는 내용 해시는 원본 바이트의 sha256 16진 소문자 글이다),
그리고 기본 지식베이스가 이미 있으면 그 현재 판의 요소(스키마 판, 임베딩 모델과 차원, 청킹 설정
해시, 토크나이저 판)가 구성(묶음의 `config.json`이나 `--config`로 준 파일)에서 계산한 것과
같은지다. 앞의 것은 `judge`가 상위 조각의 글을
바깥에 보내고 `index --records write`가 조각의 벡터를 공개 저장소에 커밋하는 파일에 쓰므로, 묶음
밖의 문서가 든 데이터베이스에서 그 내용이 밖으로 나가는 것을 막는다. 뒤의 것은 `migrate`와 같은
코드가 기본 지식베이스의 설정을 덮어써 이미 쓰는 데이터베이스에서 판 전환을 일으키는 것을 막는다.

오류 문장은 묶음 밖의 문서의 키를 싣지 않고 수만 싣는다. 데이터베이스에 든 남의 문서의 이름도
드러내지 않기 위해서다.
"""

from rag_engine.app.default_records import DEFAULT_NAME
from rag_engine.domain.entities import (
    MAX_EMBEDDING_DIMENSIONS,
    ChunkingConfig,
    DocumentQuery,
    IndexElements,
    IndexVersion,
)
from rag_engine.domain.errors import ConfigurationError
from rag_engine.domain.eval_set import EvalProblem, EvalSet
from rag_engine.domain.ports import ComputeIndexElements, UnitOfWork

_PAGE = 200
DATABASE_SUBJECT = "데이터베이스"


async def check_eval_database(
    unit_of_work: UnitOfWork, eval_set: EvalSet, compute_elements: ComputeIndexElements
) -> tuple[EvalProblem, ...]:
    """문서의 소속과 현재 판의 요소를 보고 오류를 모두 낸다. 문제가 없으면 빈 튜플이다."""
    expected = {document.key: document.sha256 for document in eval_set.documents}
    foreign = 0
    changed: list[str] = []
    problems: list[EvalProblem] = []
    async with unit_of_work.begin() as transaction:
        after = None
        while True:
            page = await transaction.documents.list_documents(
                DocumentQuery(state=None, group_id=None, key=None, limit=_PAGE, after=after)
            )
            for document in page:
                wanted = expected.get(document.key)
                if wanted is None:
                    foreign += 1
                elif document.content_hash != wanted:
                    changed.append(document.key)
            if len(page) < _PAGE:
                break
            after = page[-1].id
        knowledge_base = await transaction.catalog.get_knowledge_base(DEFAULT_NAME)
        version: IndexVersion | None = None
        if knowledge_base is not None and knowledge_base.current_index_version_id is not None:
            version = await transaction.catalog.get_index_version(
                knowledge_base.current_index_version_id
            )
    if foreign:
        problems.append(
            EvalProblem(
                DATABASE_SUBJECT,
                f"묶음에 없는 문서가 {foreign}건 들어 있다."
                " 이 묶음의 평가 전용 데이터베이스가 아니다",
            )
        )
    problems.extend(
        EvalProblem(
            key,
            "데이터베이스의 문서와 내용 해시가 문서 목록과 다르다."
            " 묶음이 바뀌었으면 데이터베이스를 새로 만든다",
        )
        for key in changed
    )
    if version is not None:
        differing = _differing_elements(version, eval_set, compute_elements)
        if differing:
            problems.append(
                EvalProblem(
                    "기본 지식베이스",
                    f"현재 판의 요소({', '.join(differing)})가 config.json과 다르다."
                    " 구성을 바꾼 실험은 데이터베이스를 새로 만들어 돌린다",
                )
            )
    return tuple(problems)


def check_default_records_input(
    eval_set: EvalSet, compute_elements: ComputeIndexElements
) -> tuple[EvalProblem, ...]:
    """`ensure_default_records`가 스키마를 올린 뒤에야 거부하는 구성(차원 상한 초과, 모르는 청킹
    전략)을 스키마를 올리기 전에 거부한다. 데이터베이스를 읽지 않는다."""
    if eval_set.config.embedding_dimensions > MAX_EMBEDDING_DIMENSIONS:
        return (
            EvalProblem(
                "config.json",
                f"임베딩 차원은 {MAX_EMBEDDING_DIMENSIONS} 이하여야 한다"
                f"(구성은 {eval_set.config.embedding_dimensions})",
            ),
        )
    try:
        _wanted_elements(eval_set, compute_elements)
    except ConfigurationError as error:
        return (EvalProblem("config.json", str(error)),)
    return ()


def _wanted_elements(eval_set: EvalSet, compute_elements: ComputeIndexElements) -> IndexElements:
    config = eval_set.config
    return compute_elements(
        config.embedding_model,
        config.embedding_dimensions,
        ChunkingConfig(
            strategy=config.chunking.strategy,
            max_tokens=config.chunking.max_tokens,
            overlap_tokens=config.chunking.overlap_tokens,
        ),
    )


def _differing_elements(
    version: IndexVersion, eval_set: EvalSet, compute_elements: ComputeIndexElements
) -> list[str]:
    wanted = _wanted_elements(eval_set, compute_elements)
    pairs = (
        ("스키마 판", version.schema_version, wanted.schema_version),
        ("임베딩 모델", version.embedding_model, wanted.embedding_model),
        ("임베딩 차원", version.embedding_dimensions, wanted.embedding_dimensions),
        ("청킹 설정", version.chunking_hash, wanted.chunking_hash),
        ("토크나이저 판", version.tokenizer_version, wanted.tokenizer_version),
    )
    return [name for name, actual, expected in pairs if actual != expected]
