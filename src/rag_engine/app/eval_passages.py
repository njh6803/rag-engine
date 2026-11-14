"""평가 세트의 글귀 판정(명세 search-eval "적중의 단위", "평가 세트의 형식"의 `validate`).

글귀는 문서의 본문에 들어 있어야 한다. 본문은 최신 파싱 결과에서 조각 글에 드는 블록의 글을 이은
것이다. 절을 가르는 제목 블록은 조각 글이 아니라 절 경로로만 가므로 뺀다. 글이 조각 상한의 4분의 1을
넘는 제목 블록은 청커가 문단으로 다루므로 본문에 든다(`StructureFirstChunker._sections`의 규칙
일곱). 글귀의 비교는 양쪽을 NFC로 정규화하고 공백류를 모두 지운 뒤 부분 문자열로 본다.

본문에 없는 글귀는 세트의 오류이고 검색의 실패로 세지 않는다. 한 문서 안에서 두 번 이상 나오는
글귀는 경고다. 어느 자리에 닿아도 닿은 것으로 세기 때문이다.
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence

from rag_engine.domain.entities import Block, BlockKind
from rag_engine.domain.eval_set import EvalProblem, EvalSet, PassageEvidence
from rag_engine.domain.index_text import section_token_limit
from rag_engine.domain.ports import TokenMeter

_WHITESPACE = re.compile(r"\s+")
_BLOCK_JOINER = "\n\n"


def normalize_text(text: str) -> str:
    """NFC로 정규화하고 공백류(공백, 탭, 줄바꿈)를 모두 지운다. 조각과 글귀를 견주는 쪽도 같은
    함수를 쓴다."""
    return _WHITESPACE.sub("", unicodedata.normalize("NFC", text))


async def document_body(blocks: Sequence[Block], max_tokens: int, tokens: TokenMeter) -> str:
    """파싱 결과의 블록에서 본문을 짓는다. `max_tokens`는 색인 판의 조각 상한이다."""
    texts = [block.text.strip() for block in blocks]
    candidates = [
        index
        for index, block in enumerate(blocks)
        if texts[index] and block.kind is BlockKind.HEADING and block.level is not None
    ]
    counted = (
        await tokens.count_tokens([texts[index] for index in candidates]) if candidates else []
    )
    limit = section_token_limit(max_tokens)
    sectioning = {index for index, count in zip(candidates, counted, strict=True) if count <= limit}
    kept = [text for index, text in enumerate(texts) if text and index not in sectioning]
    return _BLOCK_JOINER.join(kept)


def check_passages(
    eval_set: EvalSet, bodies: Mapping[str, str]
) -> tuple[tuple[EvalProblem, ...], tuple[EvalProblem, ...]]:
    """글귀마다 그 문서의 본문에 드는지 본다. (오류, 경고)를 낸다. `bodies`에 없는 문서(색인되지
    않은 것)는 이 판정이 보지 않는다."""
    normalized = {key: normalize_text(body) for key, body in bodies.items()}
    problems: list[EvalProblem] = []
    warnings: list[EvalProblem] = []
    for item in eval_set.evidence:
        for expectation in item.evidence:
            if not isinstance(expectation, PassageEvidence):
                continue
            body = normalized.get(expectation.document)
            if body is None:
                continue
            needle = normalize_text(expectation.passage)
            where = f"evidence {item.id}"
            first = body.find(needle)
            if first < 0:
                problems.append(EvalProblem(where, f"글귀가 {expectation.document}의 본문에 없다"))
            elif body.find(needle, first + 1) >= 0:
                warnings.append(
                    EvalProblem(
                        where,
                        f"글귀가 {expectation.document} 안에서 두 번 이상 나온다."
                        " 어느 자리에 닿아도 닿은 것으로 센다",
                    )
                )
    return tuple(problems), tuple(warnings)
