"""Claude 관련성 판정기의 실제 호출을 작은 표본으로 한 번 확인한다(티켓 search-eval 12, ADR 0019).

보는 것:
1. 어댑터(`ClaudeRelevanceJudge`)가 실제 Messages API에서 도는지. 손으로 쓴 질의와 조각의 쌍 여섯에
   기대한 판정(참 셋, 거짓 셋)이 나오는지, 실패 없이 끝나는지.
2. 응답의 모양. 같은 요청을 SDK로 한 번 더 보내 `stop_reason`, 내용 블록의 종류, 글 블록의 길이,
   `usage`의 토큰 수를 찍는다. 어댑터가 가정한 모양(글 블록 하나에 `{"relevant": 참거짓}`)과 같은지,
   `max_tokens` 4096이 넉넉한지 본다. 응답의 글은 이 프로브의 표본에서 나온 것이라 찍는다.

비밀. 키는 환경 변수 `RAG_JUDGE_API_KEY`에서만 읽고 찍지 않는다. 표본의 글은 이 파일에 적힌
공개된 예문이고 사용자의 문서가 아니다.

비용. `--yes`가 없으면 부를 건수와 비용의 어림만 찍고 끝난다. 부르는 수는 표본 여섯과 응답 모양을
보는 한 번이다. 어림은 ADR 0019의 3,000건 약 26달러에 건수를 비례시킨 값이다.

실행(저장소 루트, 워크트리의 `.venv`):
  RAG_JUDGE_URL=https://api.anthropic.com RAG_JUDGE_MODEL=<모델> RAG_JUDGE_API_KEY=<키> \\
    uv run python .scratch/search-eval/probes/judge-call/judge_call.py [--env-file <파일>] [--yes]
`RAG_JUDGE_MODEL`은 부를 모델의 이름이다. `--env-file`을 주면 그 파일(`.env` 꼴)의 `RAG_JUDGE_URL`,
`RAG_JUDGE_MODEL`, `RAG_JUDGE_API_KEY` 세 줄만 읽어 셸의 환경 위에 얹는다. 출력은
`judge_call_out.txt`에 옮긴다.
"""

import asyncio
import os
import sys
from importlib.metadata import version
from pathlib import Path

from anthropic import AsyncAnthropic

from rag_engine.adapters.claude_judge import (
    INSTRUCTION,
    MAX_TOKENS,
    PROMPT_VERSION,
    RESPONSE_SCHEMA,
    ClaudeRelevanceJudge,
)
from rag_engine.adapters.judge_settings import (
    API_KEY_ENV,
    MODEL_ENV,
    URL_ENV,
    JudgeSettingsError,
    read_judge_settings,
)
from rag_engine.app.eval_judgments import estimate_dollars

# (질의, 조각의 글, 기대한 판정)
SAMPLES = (
    (
        "비밀번호를 잊어버렸을 때 어떻게 재설정하나요?",
        "로그인 화면에서 '비밀번호 찾기'를 누르고 가입한 이메일을 입력하면 재설정 링크가 전송된다."
        " 링크는 30분 동안 유효하다.",
        True,
    ),
    (
        "연차는 입사 후 몇 일이 생기나요?",
        "입사 1년 미만의 직원에게는 한 달 개근 시 연차 1일이 발생하며, 최대 11일까지 쌓인다.",
        True,
    ),
    (
        "서버 로그는 며칠 보관하나요?",
        "접속 로그는 90일 동안 보관한 뒤 자동으로 삭제한다. 감사 로그는 별도로 1년을 보관한다.",
        True,
    ),
    (
        "비밀번호를 잊어버렸을 때 어떻게 재설정하나요?",
        "사내 식당은 평일 11시 30분부터 13시 30분까지 운영하며, 금요일에는 도시락을 제공한다.",
        False,
    ),
    (
        "연차는 입사 후 몇 일이 생기나요?",
        "출장비는 출장 종료 후 7일 안에 정산 시스템에 영수증과 함께 제출해야 한다.",
        False,
    ),
    (
        "서버 로그는 며칠 보관하나요?",
        "서버실 출입은 보안팀이 발급한 출입증이 있어야 하며, 출입 기록은 담당자가 확인한다.",
        False,
    ),
)


def _environment(env_file: Path | None) -> dict[str, str]:
    """셸의 환경에, `--env-file`이 있으면 그 파일의 판정기 설정 세 줄만 얹는다. 파일의 다른 줄은
    읽어도 쓰지 않고, 값은 어디에도 찍지 않는다."""
    environ = dict(os.environ)
    if env_file is None:
        return environ
    for line in env_file.read_text(encoding="utf-8").splitlines():
        name, separator, value = line.partition("=")
        name = name.strip().removeprefix("export ").strip()
        if separator and name in (URL_ENV, MODEL_ENV, API_KEY_ENV):
            environ[name] = value.strip().strip("'\"")
    return environ


async def main(*, approved: bool, env_file: Path | None) -> int:
    try:
        settings = read_judge_settings(_environment(env_file))
    except FileNotFoundError:
        print(f"--env-file의 파일이 없다: {env_file}")
        return 1
    except JudgeSettingsError as error:
        print(error)
        return 1
    calls = len(SAMPLES) + 1
    print(f"anthropic {version('anthropic')}, 모델 {settings.model}, 지시문의 판 {PROMPT_VERSION}")
    dollars = estimate_dollars(calls)
    print(f"부를 건수 {calls}건(표본 {len(SAMPLES)}, 응답 모양 1), 비용 어림 약 {dollars:.3f}달러")
    if not approved:
        print("부르지 않았다. 부르려면 --yes를 붙여 다시 친다")
        return 0
    judge = ClaudeRelevanceJudge(settings)
    matched = 0
    try:
        for query, text, expected in SAMPLES:
            verdict = await judge.judge(query, text)
            matched += verdict == expected
            outcome = "일치" if verdict == expected else "불일치"
            print(f"판정 {verdict!s:5} 기대 {expected!s:5} {outcome}")
    finally:
        await judge.aclose()
    print(f"기대와 일치 {matched}/{len(SAMPLES)}")
    await _shape(settings.url, settings.model, settings.api_key)
    return 0


async def _shape(url: str, model: str, api_key: str) -> None:
    """어댑터와 같은 요청을 SDK로 한 번 보내 응답의 모양을 찍는다."""
    query, text, _ = SAMPLES[0]
    prompt = f"<query>\n{query}\n</query>\n\n<passage>\n{text}\n</passage>"
    client = AsyncAnthropic(base_url=url, api_key=api_key, max_retries=0)
    try:
        response = await client.messages.create(
            model=model,
            max_tokens=MAX_TOKENS,
            system=INSTRUCTION,
            messages=[{"role": "user", "content": prompt}],
            output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
        )
    finally:
        await client.close()
    print(f"stop_reason {response.stop_reason}")
    print(f"내용 블록 종류 {[block.type for block in response.content]}")
    for block in response.content:
        if block.type == "text":
            print(f"글 블록 {len(block.text)}자: {block.text}")
    print(f"usage 입력 {response.usage.input_tokens}, 출력 {response.usage.output_tokens}")


if __name__ == "__main__":
    arguments = sys.argv[1:]
    given = arguments.index("--env-file") + 1 if "--env-file" in arguments else None
    path = Path(arguments[given]) if given is not None and given < len(arguments) else None
    sys.exit(asyncio.run(main(approved="--yes" in arguments, env_file=path)))
