"""`anthropic` 2.x 로 쓴 관련성 판정기 어댑터의 꼴이 pyright strict 와 원칙 II 를 지나는지 본다.

보는 것:
1. 포트(Protocol)와 그 구현의 꼴로 쓴 코드가 pyright strict 에서 오류 0 인지. 쓰는 SDK 의 면은
   클라이언트 생성(`base_url`, `api_key`), `messages.create`(`model`, `max_tokens`, `messages`),
   응답의 내용 블록을 `type` 으로 가르기, 오류 클래스 둘(`APIStatusError`,
   `APIConnectionError`)이다. 쓰는 법은 `claude-api` 스킬 문서의
   `python/claude-api/README.md`(Claude Code 2.1.321 에 실린 판)를 읽고 옮겼다.
2. 원칙 II 가 막는 넷(`Any`, `cast`, `type: ignore`, `pyright: ignore`)을 쓰지 않는지. 이것은 이
   스크립트가 재지 않는다. `tools/check_type_escapes.py` 의 `escapes_in` 을 이 파일의 글에 손으로
   불러 본다(그 도구의 명령줄은 `src`, `tests`, `tools` 만 훑는다). 명령은 README 에 있다.
3. 설치한 판에서 모듈이 import 되고 클라이언트가 만들어지는지(`main`).

보지 않는 것: 실제 호출. `judge` 는 부르지 않는다. 호출에는 키와 비용이 들어 사용자 승인 뒤에 첫
구현 티켓이 잰다. 그래서 요청과 응답이 실제 API 에서 이 꼴대로 도는지는 이 프로브가 말하지 않는다.

실행. 저장소 `.venv` 에는 `anthropic` 이 없어 임시 가상환경 `<env>` 를 쓴다(대기열
uv-with-windows-lock). 아래의 `<py>` 는 `<env>/Scripts/python.exe` 다.
  uv venv <env>
  uv pip install --python <py> "anthropic>=2.8,<3"
  <py> -X utf8 .scratch/search-eval/probes/llm-sdk/judge_adapter_types.py
  uv run pyright -p <cfg> --pythonpath <py> --outputjson <이 파일의 경로>
`<cfg>` 는 임시 pyrightconfig.json 이다. exclude 는 빈 목록, typeCheckingMode 는 strict 이고
include 는 두지 않는다(절대 경로의 include 는 pyright 가 무시해 볼 파일을 인자로 준다).
저장소 설정으로는 기본 exclude 가 `.scratch` 를 0개 파일로 지나가게 한다(대기열
pyright-scratch-vacuous). 이 설정이 strict 로 도는지는 타입 표기가 없는 함수 하나만 둔
대조 파일을 같은 명령으로 돌려 봤고 오류 넷이 났다(손으로 봤다).

2026-11-12에 돌렸다(출력 `judge_adapter_types_out.txt`, pyright 의 JSON 은
`judge_adapter_types_pyright_out.json`). 결과 요약은 같은 폴더의 README 표에 있다.
"""

from __future__ import annotations

from dataclasses import dataclass
from importlib.metadata import version
from typing import Protocol

import anthropic
from anthropic import Anthropic

INSTRUCTION = (
    "Decide whether the passage is relevant to the query."
    " Answer with exactly one word: relevant or irrelevant."
)


class RelevanceJudge(Protocol):
    def judge(self, query: str, chunk_text: str) -> bool: ...


class JudgeError(Exception):
    pass


@dataclass(frozen=True)
class JudgeSettings:
    base_url: str
    model: str
    api_key: str


class ClaudeRelevanceJudge:
    def __init__(self, settings: JudgeSettings) -> None:
        self._client = Anthropic(base_url=settings.base_url, api_key=settings.api_key)
        self._model = settings.model

    def judge(self, query: str, chunk_text: str) -> bool:
        prompt = f"{INSTRUCTION}\n\nQuery:\n{query}\n\nPassage:\n{chunk_text}"
        try:
            response = self._client.messages.create(
                model=self._model,
                max_tokens=16,
                messages=[{"role": "user", "content": prompt}],
            )
        except anthropic.APIStatusError as exc:
            raise JudgeError(f"status {exc.status_code}") from exc
        except anthropic.APIConnectionError as exc:
            raise JudgeError("unreachable") from exc
        answer = "".join(block.text for block in response.content if block.type == "text")
        return answer.strip().lower().startswith("relevant")


def main() -> None:
    print("anthropic", version("anthropic"))
    settings = JudgeSettings(
        base_url="http://127.0.0.1:9", model="claude-opus-5-5", api_key="probe-placeholder"
    )
    judge: RelevanceJudge = ClaudeRelevanceJudge(settings)
    print("판정기를 만들었다:", type(judge).__name__, "(호출하지 않았다)")


if __name__ == "__main__":
    main()
