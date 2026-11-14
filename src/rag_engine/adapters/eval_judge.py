"""`judge --through fused|rerank <묶음 폴더> [--yes] [--prune]`의 조립(티켓 search-eval 12, 명세
"LLM 관련성 판정").

`run`과 같은 평가를 돌려 마지막 단계의 상위 10개 조각과 질의의 쌍을 얻고, 판정 파일에 아직 없는
쌍만 Claude 판정기로 판정해 `judgments.jsonl`에 쌓는다. 아래를 하나라도 어기면 판정기를 부르지
않고 1을 낸다. 순서는 이렇다.

1. 평가 전용 환경(전체 실행은 리랭커 끝점도), 묶음의 목록과 문서 파일(`run`과 같은
   `prepare_evaluation`. 구성은 `--config`로 준 파일이거나 묶음의 `config.json`이다), 판정기의
   설정 셋(`RAG_JUDGE_*`. 일부만 있으면 빠진 이름만 알린다).
2. `RAG_JUDGE_MODEL`이 `config.json`의 `judge_model`과, 어댑터의 지시문 판이
   `judge_prompt_version`과 같은지. 어긋난 둘의 이름을 알린다. 판정 파일의 열쇠가 이 둘이라, 어긋난
   채 쌓으면 `run`이 읽지 못하는 줄이 쌓인다.
3. 판정 파일의 경로(묶음 밖을 가리키는 링크는 쓰기를 돌릴 수 있어 읽는 파일과 같이 판정한다)와
   줄이 형식에 맞는지(줄 번호만 알린다).
4. 데이터베이스가 이 묶음의 것인지와 문서가 모두 색인되어 있는지(`run`과 같은 판정). 판정기에는
   조각의 글이 나가므로 묶음 밖 문서가 든 데이터베이스에서는 아무것도 부르지 않는다(원칙 V).

`--prune`은 4 뒤에 바로, 지금의 모델과 지시문 판에 맞지 않는 줄을 지운다. `--yes`가 있든 없든
지우고, 뒤이은 평가가 실패해도 이미 지운 뒤다(사람이 고른 명령이라 승인을 따로 묻지 않는다).
`--yes`가 없으면 부를 건수와 비용의 어림만 찍고 0으로 끝나며 판정기를 부르지 않는다. 판정을
끝낸 뒤에는 판정 파일을 열쇠 순으로 정렬해 다시 쓴다.

오류 문장은 값(키, 주소, 질의와 조각의 글)을 싣지 않는다. 판정기의 실패 메시지는 이 저장소가 쓴
글이다(`RelevanceJudge`의 약속).
"""

import sys
from collections.abc import Mapping
from datetime import UTC, datetime
from pathlib import Path

from sqlalchemy.exc import SQLAlchemyError

from rag_engine.adapters.bundle_paths import BundlePathError
from rag_engine.adapters.claude_judge import PROMPT_VERSION, ClaudeRelevanceJudge
from rag_engine.adapters.eval_assembly import (
    EXIT_FAILED,
    EXIT_OK,
    PreparedEvaluation,
    check_ready,
    evaluate,
    prepare_evaluation,
    report_problems,
)
from rag_engine.adapters.eval_environment import EvalEnvironmentError
from rag_engine.adapters.eval_judgments_file import (
    JudgmentFileError,
    append_judgment,
    judgments_path,
    prune_judgments,
    read_judgments,
    rewrite_sorted,
)
from rag_engine.adapters.judge_settings import (
    MODEL_ENV,
    JudgeSettings,
    JudgeSettingsError,
    read_judge_settings,
)
from rag_engine.adapters.postgres.engine import run_in_selector_loop
from rag_engine.app.eval_judgments import (
    JUDGMENTS_FILE,
    JudgeOutcome,
    JudgeRunError,
    Judgment,
    JudgmentPair,
    estimate_dollars,
    judge_pairs,
    pending_pairs,
)
from rag_engine.app.eval_run import JUDGED_TOP, EvalRunError
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.errors import ConfigurationError, RagEngineError
from rag_engine.domain.eval_set import EvalConfig


def run_judge(
    folder: Path,
    environ: Mapping[str, str],
    *,
    through: Stage,
    approved: bool,
    prune: bool,
    config_file: Path | None = None,
) -> int:
    """`judge`의 종료 코드를 낸다. `approved`는 `--yes`, `config_file`은 `--config`로 준 구성
    파일이다. 이벤트 루프를 스스로 열므로 실행 중인 루프 안에서는 부를 수 없다."""
    prepared = prepare_evaluation(folder, environ, through=through, config_file=config_file)
    if prepared is None:
        return EXIT_FAILED
    try:
        judge_settings = read_judge_settings(environ)
    except JudgeSettingsError as error:
        print(error, file=sys.stderr)
        return EXIT_FAILED
    mismatches = _mismatches(judge_settings, prepared.eval_set.config)
    if mismatches:
        for mismatch in mismatches:
            print(mismatch, file=sys.stderr)
        return EXIT_FAILED
    try:
        return _judge_bundle(prepared, judge_settings, approved=approved, prune=prune)
    except JudgmentFileError as error:
        print(error, file=sys.stderr)
        return EXIT_FAILED
    except EvalRunError as error:
        print(f"평가를 끝내지 못했다: {error}", file=sys.stderr)
        return EXIT_FAILED
    except (EvalEnvironmentError, ConfigurationError) as error:
        print(f"설정 오류: {error}", file=sys.stderr)
        return EXIT_FAILED
    except (OSError, BundlePathError, SQLAlchemyError, RagEngineError) as error:
        # 접속 실패의 메시지와 스택은 호스트와 사용자 이름을 싣는다(원칙 V). 오류의 종류만 알린다.
        print(f"판정하지 못했다({type(error).__name__})", file=sys.stderr)
        return EXIT_FAILED


def _judge_bundle(
    prepared: PreparedEvaluation, settings: JudgeSettings, *, approved: bool, prune: bool
) -> int:
    """판정 파일을 읽고, 데이터베이스를 점검하고, 평가를 돌려 판정할 쌍을 정한 뒤 판정한다."""
    config = prepared.eval_set.config
    model, version = config.judge_model, config.judge_prompt_version
    path = judgments_path(prepared.paths)
    existing = read_judgments(path) or []
    problems = run_in_selector_loop(
        check_ready(prepared.environment.database_url, prepared.eval_set)
    )
    if problems:
        report_problems(problems)
        return EXIT_FAILED
    if prune:
        removed = prune_judgments(path, model=model, prompt_version=version)
        print(f"{JUDGMENTS_FILE}에서 지금의 모델과 지시문 판에 맞지 않는 {removed}줄을 지웠다")
        existing = [
            item for item in existing if item.model == model and item.prompt_version == version
        ]
    pairs, total = _pending(prepared, existing)
    _print_plan(pairs, total=total, model=model)
    if not pairs:
        return EXIT_OK
    if not approved:
        print("부르지 않았다. 부르려면 --yes를 붙여 다시 친다")
        return EXIT_OK
    return _judge_and_record(settings, pairs, path, model=model, version=version)


def _pending(
    prepared: PreparedEvaluation, existing: list[Judgment]
) -> tuple[list[JudgmentPair], int]:
    """평가를 돌려 판정 파일에 없는 쌍과 마지막 단계의 상위 조합의 수를 낸다."""
    config = prepared.eval_set.config
    result = run_in_selector_loop(evaluate(prepared))
    pairs = pending_pairs(
        result.outcomes,
        existing,
        model=config.judge_model,
        prompt_version=config.judge_prompt_version,
    )
    return pairs, sum(len(outcome.top) for outcome in result.outcomes)


def _mismatches(settings: JudgeSettings, config: EvalConfig) -> list[str]:
    """`RAG_JUDGE_MODEL`과 어댑터의 지시문 판이 `config.json`의 열쇠와 어긋난 곳. 값은 비밀이 아니라
    싣는다(모델 이름과 판 번호)."""
    found: list[str] = []
    if settings.model != config.judge_model:
        found.append(
            f"{MODEL_ENV}={settings.model}이(가) config.json의 judge_model={config.judge_model}과"
            " 다르다. 어느 쪽을 고쳐 같게 한 뒤에 다시 친다"
        )
    if str(PROMPT_VERSION) != config.judge_prompt_version:
        found.append(
            f"어댑터의 지시문 판 {PROMPT_VERSION}이 config.json의 judge_prompt_version="
            f"{config.judge_prompt_version}과 다르다. 판을 올렸으면 config.json도 올린다"
        )
    return found


def _print_plan(pairs: list[JudgmentPair], *, total: int, model: str) -> None:
    """부를 건수와 비용의 어림. 비용은 ADR 0019의 3,000건 약 26달러(Opus 5.5)에 건수를 비례시킨
    값이라 다른 모델이면 맞지 않는다."""
    print(
        f"판정할 쌍 {len(pairs)}건(마지막 단계의 상위 {JUDGED_TOP}개 조합 {total}건 가운데"
        f" {JUDGMENTS_FILE}에 없는 것)"
    )
    if pairs:
        print(
            f"비용 어림 약 {estimate_dollars(len(pairs)):.2f}달러(모델 {model}."
            " ADR 0019의 3,000건 약 26달러에서 건수에 비례시킨 값이다)"
        )
    else:
        print("부를 쌍이 없다")


def _judge_and_record(
    settings: JudgeSettings, pairs: list[JudgmentPair], path: Path, *, model: str, version: str
) -> int:
    """쌍을 판정해 받는 대로 판정 파일에 덧붙이고, 끝나면(실패해도) 열쇠 순으로 정렬해 다시 쓴다.
    영구 실패로 건너뛴 쌍은 판정 없음으로 남고 다시 돌리면 다시 부른다. 판정을 하나도 받지 못한
    채 끝나면 1이다."""
    try:
        outcome = run_in_selector_loop(_judge_all(settings, pairs, path, model, version))
    except JudgeRunError as error:
        print(f"판정을 끝내지 못했다: {error}", file=sys.stderr)
        return EXIT_FAILED
    finally:
        rewrite_sorted(path)
    print(f"판정 {outcome.received}건을 {JUDGMENTS_FILE}에 썼다")
    if not outcome.skipped:
        return EXIT_OK
    reasons = "; ".join(outcome.skip_reasons)
    print(
        f"판정기가 받아들이지 않아 건너뛴 쌍 {outcome.skipped}건({reasons})."
        " 판정 없음으로 남고 다시 돌리면 다시 부른다",
        file=sys.stderr,
    )
    return EXIT_OK if outcome.received else EXIT_FAILED


async def _judge_all(
    settings: JudgeSettings, pairs: list[JudgmentPair], path: Path, model: str, version: str
) -> JudgeOutcome:
    judge = ClaudeRelevanceJudge(settings)
    try:
        return await judge_pairs(
            judge,
            pairs,
            model=model,
            prompt_version=version,
            today=datetime.now(UTC).date(),
            record=lambda judgment: append_judgment(path, judgment),
        )
    finally:
        await judge.aclose()
