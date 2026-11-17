"""판정기의 설정 셋(티켓 search-eval 12, 명세 "LLM 관련성 판정").

셋 모두 기본값이 없다. 모두 있을 때만 조립하고 일부만 있거나 없으면 빠진 이름만 알린다. 값은 오류
문장에도 객체의 repr에도 싣지 않는다(원칙 V, 키는 비밀이다).
"""

import pytest

from rag_engine.adapters.judge_settings import (
    API_KEY_ENV,
    MODEL_ENV,
    URL_ENV,
    JudgeSettings,
    JudgeSettingsError,
    read_judge_settings,
)

FULL = {URL_ENV: "http://127.0.0.1:9", MODEL_ENV: "claude-opus-5-5", API_KEY_ENV: "sk-secret"}


def test_셋이_모두_있으면_설정을_낸다() -> None:
    assert read_judge_settings(FULL) == JudgeSettings(
        url="http://127.0.0.1:9", model="claude-opus-5-5", api_key="sk-secret"
    )


def test_이름은_명세가_정한_셋이다() -> None:
    assert (URL_ENV, MODEL_ENV, API_KEY_ENV) == (
        "RAG_JUDGE_URL",
        "RAG_JUDGE_MODEL",
        "RAG_JUDGE_API_KEY",
    )


@pytest.mark.parametrize("missing", [URL_ENV, MODEL_ENV, API_KEY_ENV])
def test_일부가_빠지면_빠진_이름만_알리고_값은_싣지_않는다(missing: str) -> None:
    environ = {name: value for name, value in FULL.items() if name != missing}

    with pytest.raises(JudgeSettingsError) as caught:
        read_judge_settings(environ)

    message = str(caught.value)
    assert missing in message
    assert all(name not in message for name in FULL if name != missing)
    assert all(value not in message for value in FULL.values())


def test_모두_없으면_세_이름을_모두_알린다() -> None:
    with pytest.raises(JudgeSettingsError) as caught:
        read_judge_settings({})

    assert all(name in str(caught.value) for name in FULL)


@pytest.mark.parametrize("blank", ["", "  "])
def test_빈_값은_없는_것으로_본다(blank: str) -> None:
    with pytest.raises(JudgeSettingsError, match=API_KEY_ENV):
        read_judge_settings({**FULL, API_KEY_ENV: blank})


def test_설정의_repr에는_키가_없다() -> None:
    settings = read_judge_settings(FULL)

    assert "sk-secret" not in repr(settings)
    assert "sk-secret" not in str(settings)
