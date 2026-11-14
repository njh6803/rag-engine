"""평가 구성의 값(티켓 search-eval 06, 명세 "보고서"의 구성 항목).

내용 해시와 `compare`의 구성 비교는 판정 칸을 뺀 값을 쓰고, 보고서의 `config` 칸은 판정 칸까지
싣는다. 두 값은 불리언 인자 없이 다른 함수로 낸다.
"""

from rag_engine.domain.eval_set import (
    ChunkingConfig,
    EvalConfig,
    config_values,
    search_config_values,
)

CONFIG = EvalConfig(
    embedding_model="intfloat/multilingual-e5-large",
    embedding_dimensions=1024,
    reranker_model="BAAI/bge-reranker-v2-m3",
    chunking=ChunkingConfig(strategy="structure_first", max_tokens=512, overlap_tokens=64),
    search_candidates=50,
    tei_version="1.9",
    judge_model="claude-판정",
    judge_prompt_version="1",
)


def test_검색_구성의_값은_판정_칸을_싣지_않는다() -> None:
    values = search_config_values(CONFIG)

    assert "judge_model" not in values
    assert "judge_prompt_version" not in values
    assert values["search_candidates"] == 50
    assert values["chunking"] == {
        "strategy": "structure_first",
        "max_tokens": 512,
        "overlap_tokens": 64,
    }


def test_보고서의_구성_값은_검색_구성의_값에_판정_칸을_더한다() -> None:
    values = config_values(CONFIG)

    assert {name: value for name, value in values.items() if not name.startswith("judge_")} == (
        search_config_values(CONFIG)
    )
    assert values["judge_model"] == "claude-판정"
    assert values["judge_prompt_version"] == "1"
