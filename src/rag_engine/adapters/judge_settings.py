"""관련성 판정기의 설정 셋(티켓 search-eval 12, 명세 "LLM 관련성 판정", ADR 0019).

`RAG_JUDGE_URL`(끝점 주소), `RAG_JUDGE_MODEL`, `RAG_JUDGE_API_KEY`가 모두 있을 때만 판정기를
조립한다. 셋 모두 기본값이 없다. 일부만 있거나 하나도 없으면 빠진 이름을 알리고 값은 알리지 않는다.
키는 비밀이라 설정 객체의 `repr`에도 싣지 않는다(원칙 V). 제품의 설정 객체(`Settings`)와 작업
폴더의 `.env`는 읽지 않는다. 호출하는 쪽이 건넨 환경 매핑만 읽는다(평가 도구의 환경 규칙과 같다).
"""

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

URL_ENV: Final = "RAG_JUDGE_URL"
MODEL_ENV: Final = "RAG_JUDGE_MODEL"
API_KEY_ENV: Final = "RAG_JUDGE_API_KEY"
_NAMES: Final = (URL_ENV, MODEL_ENV, API_KEY_ENV)


class JudgeSettingsError(Exception):
    """판정기의 설정이 모자란 까닭. 메시지는 빠진 이름만 싣고 값은 싣지 않는다."""


@dataclass(frozen=True, slots=True)
class JudgeSettings:
    url: str
    model: str
    api_key: str = field(repr=False)


def read_judge_settings(environ: Mapping[str, str]) -> JudgeSettings:
    """셋이 모두 있으면 설정을 낸다. 비었거나 공백만 든 값은 없는 것으로 본다."""
    missing = [name for name in _NAMES if not environ.get(name, "").strip()]
    if missing:
        raise JudgeSettingsError(
            f"판정기의 설정이 모자란다. 셋이 모두 있어야 판정기를 조립한다: {', '.join(missing)}"
        )
    return JudgeSettings(
        url=environ[URL_ENV], model=environ[MODEL_ENV], api_key=environ[API_KEY_ENV]
    )
