"""검색 평가 도구의 명령줄 입구(명세 `.scratch/search-eval/spec.md`의 "자리와 층").

    uv run python tools/search_eval.py validate <묶음 폴더> [--indexed]
    uv run python tools/search_eval.py index <묶음 폴더> [--config <파일>] [기록 옵션]
    uv run python tools/search_eval.py run --through fused|rerank --out <폴더> <묶음 폴더>
        [--config <파일>] [기록 옵션]
    uv run python tools/search_eval.py judge --through fused|rerank [--yes] [--prune] <묶음 폴더>
        [--config <파일>]
    uv run python tools/search_eval.py inspect <묶음 폴더> <질의 목록 이름> <기대 근거 id>
        [--through fused|rerank] [--config <파일>]
    uv run python tools/search_eval.py compare --gate fast|full <보고서> <묶음 폴더>

기록 옵션은 `--records read|write|off`(기본 `read`)와 `--tei-device cpu|gpu`다. 장치는 `write`가
반드시 받고 다른 방식에서는 쓰지 않는다. `index`와 `run`만 받고 `inspect`와 `judge`는 기록 옵션을
받지 않는다. `judge`는 기록을 읽지도 쓰지도 않아 `--records off`로 `run`을 돌린 것과 같은 평가를
돈다.

인자 해석과 조립만 한다. 묶음의 파일을 읽고 쓰는 코드는 `rag_engine.adapters`에, 값과 판정은
`rag_engine.domain`과 `rag_engine.app`에 있다. `tools/`는 이미지에 실리지 않으므로(`.dockerignore`)
이 입구는 관리자 페이지가 평가를 열기 전까지 제품 이미지에 없다. 하위 명령은 받는 티켓이 더한다.

`validate`는 데이터베이스 없이 묶음의 형식과 목록을 본다. `--indexed`를 주면 평가 전용
데이터베이스에서 묶음의 모든 문서가 색인되어 있는지와 글귀가 그 문서의 본문에 있는지까지 본다. 틀린
곳을 까닭과 함께 표준 오류에 한 줄씩 적고, 한 문서 안에서 두 번 이상 나오는 글귀는 `경고`로
적는다(종료 코드는 그대로).

`index`는 `compose.eval.yml`로 띄운 평가 전용 데이터베이스에 묶음의 문서를 제품과 같은 길로
색인한다. 작업자를 따로 띄우지 않는다. 문서를 넣은 뒤 작업자의 한 번 돌기 입구를 직접 불러 작업을
끝까지 처리한다.

`run`은 색인된 묶음을 평가해 `--out` 폴더에 `report.json`과 `report.md`를 쓴다. `--through`는
`fused`(빠른 실행. 벡터만, 키워드만, 합친 뒤)와 `rerank`(전체 실행. 합친 뒤의 후보 전부를 리랭크한
뒤까지와 리랭크 점수의 분포 `score_distribution`) 가운데 하나를 반드시 받는다. 빠지거나 둘 다 주면
종료 코드 2다. 시작할 때 `index`와 같은 판정(평가 전용 이름, 데이터베이스 이름, 이 묶음의
데이터베이스인지)을 지나야 돈다. 기록을 끈(`--records off`) 전체 실행은 리랭커 끝점
`RAG_EVAL_RERANKER_URL`이 없으면 그 이름을 알리고 종료 코드 1이다.

`run`은 판정 파일 `judgments.jsonl`이 있으면 그 줄로 보고서의 `llm` 칸(LLM 관련성 판정의 참고
숫자)을 센다. 판정기를 부르지 않으므로 판정기의 설정은 읽지 않는다.

`judge`는 `run`과 같은 평가를 돌려 마지막 단계의 상위 10개 조각과 질의의 쌍 가운데 판정 파일에 없는
것만 Claude 판정기로 판정해 판정 파일에 쌓는다. 판정기의 설정 `RAG_JUDGE_URL`, `RAG_JUDGE_MODEL`,
`RAG_JUDGE_API_KEY`를 셋 모두 환경 변수에 둬야 돌고, `RAG_JUDGE_MODEL`과 지시문의 판이
구성(`config.json`이나 `--config`로 준 파일)의 `judge_model`, `judge_prompt_version`과 같아야 한다.
`--yes`가 없으면 부를 건수와 비용의 어림만 찍고 부르지 않는다. `--prune`은 지금의 모델과 지시문 판에
맞지 않는 줄을 판정 파일에서 지운다.

`inspect`는 질의 하나를 `run`과 같은 길로 돌려 그 질의의 글, 기대 근거, 단계마다의 상위 조각의 글을
표준 출력에만 찍는다. 파일은 쓰지 않는다. `--through`는 `fused`(기본)와 `rerank` 가운데 하나다.

`--config <파일>`은 `index`, `run`, `judge`, `inspect`가 받는다. 주지 않으면 묶음의
`config.json`이다. 준 구성 파일은 부르는 사람이 고른 자리라 묶음 폴더 밖이어도 된다. 보고서의
`config`와 내용 해시는 쓴 구성으로 계산한다. 후보 수를 바꿔 같은 평가를 도는 일이 그 쓰임이다.
임베딩 모델, 차원, 청킹을 바꾼 구성은 그 구성으로 색인한 데이터베이스에서만 돈다(`index`에도 같은
파일을 준다). 판정 파일의 열쇠가 되는 `judge_model`과 `judge_prompt_version`도 쓴 구성에서 읽으므로,
`judge`와 `run`에는 같은 구성을 준다.

데이터베이스에 붙는 하위 명령(`index`, `run`, `judge`, `inspect`, `validate --indexed`)은 평가 전용
환경 변수 `RAG_EVAL_DATABASE_URL`, `RAG_EVAL_DATA_DIR`, `RAG_EVAL_EMBEDDING_URL`(과 있으면
`RAG_EVAL_RERANKER_URL`. 기록을 끈 전체 실행만 이것이 반드시 있어야 하고, 기록 옵션이 없는 `judge`의
전체 실행도 그렇다)만 읽는다. 제품의 `RAG_*`(판정기의 `RAG_JUDGE_*`는 빼고)와 작업 폴더의 `.env`는
읽지 않는다.

추론 기록(`--records`)은 모델이 계산한 임베딩과 리랭크 점수를 묶음의 `records/`에 저장해 다시 쓴다.
`read`는 기록 파일을 고치지 않고, 기록에 있는 글은 모델을 부르지 않는다. 기록에 없어 새로 계산한
임베딩이 100개를 넘으면 계산을 멈추고 1로 끝나며, 어느 명령을 `--records write`로 다시 돌려
어느 파일을 커밋하는지 알린다. 리랭커 끝점이 없는 전체 실행도 기록에 없는 쌍 하나에서 같은 식으로
끝난다. `write`는 종료 코드 0일 때만 그 명령이 주인인 파일(`index`는 조각, `run`은 질의, 전체
실행은 리랭크도)을 이번 실행이 쓴 열쇠 전부로 다시 쓴다. `index --records write`는 문서가 없는
데이터베이스에서만 돈다. `off`는 기록을 읽지도 쓰지도 않는다. 어느 장치(CPU나 GPU)의 TEI가
계산했는지 평가 도구가 알아내는 길은 두지 않았다(TEI의 `/info`로 알 수 있는지는 재 보지 않았다).
그래서 `write`는 `--tei-device`로 장치를 받아 `records.json`에 적는다. `validate`는 기록의 크기와
판, 요청 지문, TEI의 판을 본다.

`compare`는 데이터베이스와 TEI 없이 `run`이 쓴 보고서(`report.json`이나 그것이 든 폴더)를 묶음
폴더의 기준 보고서와 견준다. `--gate fast`는 `baseline-fast.json`의 합친 뒤 줄과, `--gate full`은
`baseline-full.json`의 리랭크 뒤 줄과 본다. 질의 목록마다 상위 5 적중률이 2%p, MRR이 0.02를 넘어
떨어지면 1로 끝나고 표준 오류에 질의 목록, 지표, 기준값, 새 값, 차의 표를 찍는다(정확히 그만큼은
통과한다). 묶음의 내용 해시, 구성(`judge_model`과 `judge_prompt_version`을 뺀 칸), 그 게이트가 읽는
기록 파일(조각과 질의의 임베딩, 전체 게이트는 리랭크 점수도)의 해시가 다르거나 기준 보고서가 없으면
숫자를 견주지 않고 1로 끝나며 기준 보고서를 갱신해야 한다고 알린다. 하락폭 넘게 오른 숫자는
통과시키되 기준 보고서를 갱신하라고 알린다. 보고서의 `meta`는 견주지 않는다. `compare`는 기록 파일의
해시만 견주고 요청 지문과 TEI 판의 불일치는 보지 않는다. 그것은 `validate`의 몫이라 빠른 게이트는
`validate`를 `run`보다 앞에 둔다.

종료 코드. 0은 문제 없음, 1은 묶음이나 색인의 오류(없는 폴더, 빠진 환경 변수도 든다)나 게이트 실패,
2는 잘못된 인자다.
"""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from rag_engine.adapters.eval_compare import compare_command
from rag_engine.adapters.eval_environment import EvalEnvironmentError, read_eval_environment
from rag_engine.adapters.eval_index import index_bundle
from rag_engine.adapters.eval_inspect import inspect_evaluation
from rag_engine.adapters.eval_judge import run_judge
from rag_engine.adapters.eval_run import current_commit, run_evaluation
from rag_engine.adapters.eval_validate import validate_bundle, validate_bundle_indexed
from rag_engine.adapters.inference_records import RecordMode, RecordsOptions
from rag_engine.app.eval_compare import Gate
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.errors import ConfigurationError
from rag_engine.domain.eval_set import EvalProblem
from rag_engine.worker.assembly import run_once_with_settings

TOOL: Final = "tools/search_eval.py"
EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_USAGE: Final = 2
THROUGH_CHOICES: Final = ("fused", "rerank")
RECORDS_CHOICES: Final = tuple(mode.value for mode in RecordMode)
DEVICE_CHOICES: Final = ("cpu", "gpu")
GATE_CHOICES: Final = tuple(gate.value for gate in Gate)
REPOSITORY: Final = Path(__file__).resolve().parent.parent
COMPOSE_FILE: Final = REPOSITORY / "compose.eval.yml"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=TOOL, description="검색 평가 도구")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="묶음의 형식과 목록을 본다")
    validate.add_argument("bundle", type=Path, help="묶음 폴더")
    validate.add_argument(
        "--indexed",
        action="store_true",
        help="평가 전용 데이터베이스에서 모든 문서가 색인되어 있는지와"
        " 글귀가 본문에 있는지까지 본다",
    )
    index = commands.add_parser("index", help="묶음의 문서를 평가 전용 데이터베이스에 색인한다")
    index.add_argument("bundle", type=Path, help="묶음 폴더")
    _add_records_options(index)
    _add_config(index)
    run = commands.add_parser("run", help="색인된 묶음을 평가해 보고서를 쓴다")
    run.add_argument("bundle", type=Path, help="묶음 폴더")
    _add_records_options(run)
    run.add_argument(
        "--through",
        action="append",
        choices=THROUGH_CHOICES,
        default=[],
        help="fused(합친 뒤까지, 빠른 실행)와 rerank(리랭크 뒤까지, 전체 실행) 가운데 하나",
    )
    run.add_argument("--out", type=Path, required=True, help="보고서를 쓰는 폴더")
    _add_config(run)
    judge = commands.add_parser(
        "judge", help="상위 10개 조각과 질의의 쌍을 LLM으로 판정해 판정 파일에 쌓는다"
    )
    judge.add_argument("bundle", type=Path, help="묶음 폴더")
    judge.add_argument(
        "--through",
        action="append",
        choices=THROUGH_CHOICES,
        default=[],
        help="fused(합친 뒤)와 rerank(리랭크 뒤) 가운데 하나. 그 단계의 상위 10개를 판정한다",
    )
    judge.add_argument(
        "--yes",
        action="store_true",
        help="부를 건수와 비용의 어림을 보고 승인한다. 없으면 어림만 찍고 부르지 않는다",
    )
    judge.add_argument(
        "--prune",
        action="store_true",
        help="지금의 모델과 지시문 판에 맞지 않는 줄을 판정 파일에서 지운다",
    )
    _add_config(judge)
    inspect = commands.add_parser(
        "inspect", help="질의 하나의 글, 기대 근거, 단계별 상위 조각을 표준 출력에 찍는다"
    )
    inspect.add_argument("bundle", type=Path, help="묶음 폴더")
    inspect.add_argument("query_list", help="질의 목록 이름(queries/ 아래 파일 이름)")
    inspect.add_argument("evidence_id", help="기대 근거 id")
    inspect.add_argument(
        "--through",
        choices=THROUGH_CHOICES,
        default="fused",
        help="fused(기본)나 rerank(리랭커 끝점이 필요하다)",
    )
    _add_config(inspect)
    compare = commands.add_parser(
        "compare", help="보고서를 기준 보고서와 견줘 하락폭을 넘으면 실패한다"
    )
    compare.add_argument(
        "--gate",
        required=True,
        choices=GATE_CHOICES,
        help="fast(baseline-fast.json의 합친 뒤 줄)나 full(baseline-full.json의 리랭크 뒤 줄)",
    )
    compare.add_argument("report", type=Path, help="견줄 보고서(report.json이나 그것이 든 폴더)")
    compare.add_argument("bundle", type=Path, help="기준 보고서가 든 묶음 폴더")
    return parser


def _add_records_options(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--records",
        choices=RECORDS_CHOICES,
        default=RecordMode.READ.value,
        help="추론 기록의 방식. read(기본)는 기록을 읽기만 하고, write는 그 명령이 주인인"
        " 기록 파일을 다시 쓰며, off는 기록을 읽지도 쓰지도 않는다",
    )
    command.add_argument(
        "--tei-device",
        choices=DEVICE_CHOICES,
        default=None,
        help="--records write가 records.json에 적을 TEI의 장치(write는 반드시 준다)",
    )


def _records_options(args: argparse.Namespace) -> RecordsOptions | None:
    """`--records`와 `--tei-device`를 읽는다. `write`인데 장치가 없으면 알리고 `None`을 낸다."""
    mode = RecordMode(str(args.records))
    device = None if args.tei_device is None else str(args.tei_device)
    if mode is RecordMode.WRITE and device is None:
        print(
            f"{TOOL}: --records write는 --tei-device cpu|gpu를 받아야 한다(records.json에 적을"
            " 장치를 도구가 알아내지 않고 직접 받는다). 아무것도 쓰지 않았다",
            file=sys.stderr,
        )
        return None
    return RecordsOptions(mode=mode, device=device)


def _add_config(command: argparse.ArgumentParser) -> None:
    command.add_argument(
        "--config",
        type=Path,
        default=None,
        help="묶음의 config.json 대신 쓸 구성 파일(후보 수를 바꿔 돌아 볼 때 쓴다)",
    )


def main(argv: Sequence[str]) -> int:
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as stop:
        # argparse가 사용법을 출력하고 낸 종료다. 도움말은 0이고 잘못된 인자는 2다.
        return stop.code if isinstance(stop.code, int) else EXIT_USAGE
    bundle: Path = args.bundle
    if args.command == "compare":
        report: Path = args.report
        return compare_command(report, bundle, Gate(str(args.gate)), TOOL)
    if args.command == "validate":
        indexed: bool = args.indexed
        return _validate(bundle, indexed=indexed)
    if args.command == "judge":
        approved: bool = args.yes
        prune: bool = args.prune
        return _judge(bundle, args.through, args.config, approved=approved, prune=prune)
    if args.command == "inspect":
        return inspect_evaluation(
            bundle,
            args.query_list,
            args.evidence_id,
            os.environ,
            through=_stage_of(args.through),
            config_file=args.config,
        )
    records = _records_options(args)
    if records is None:
        return EXIT_USAGE
    if args.command == "run":
        return _run(bundle, args.out, args.through, args.config, records)
    # 설정 오류는 `index_bundle`이 안에서 잡아 종료 코드로 낸다.
    return index_bundle(
        bundle, os.environ, run_once_with_settings, records=records, config_file=args.config
    )


def _stage_of(through: str) -> Stage:
    return Stage.RERANK if through == "rerank" else Stage.FUSED


def _single_stage(command: str, through: list[str]) -> Stage | None:
    """`--through`의 값이 하나가 아니면 사용법을 알리고 `None`이다."""
    if len(through) != 1:
        choices = " 또는 ".join(THROUGH_CHOICES)
        print(
            f"{TOOL} {command}: --through는 {choices} 가운데 하나를 한 번만 받는다", file=sys.stderr
        )
        return None
    return _stage_of(through[0])


def _run(
    bundle: Path, out: Path, through: list[str], config_file: Path | None, records: RecordsOptions
) -> int:
    stage = _single_stage("run", through)
    if stage is None:
        return EXIT_USAGE
    return run_evaluation(
        bundle,
        out,
        os.environ,
        through=stage,
        commit=current_commit(REPOSITORY),
        records=records,
        config_file=config_file,
    )


def _judge(
    bundle: Path, through: list[str], config_file: Path | None, *, approved: bool, prune: bool
) -> int:
    stage = _single_stage("judge", through)
    if stage is None:
        return EXIT_USAGE
    return run_judge(
        bundle,
        os.environ,
        through=stage,
        approved=approved,
        prune=prune,
        config_file=config_file,
    )


def _validate(bundle: Path, *, indexed: bool) -> int:
    if not bundle.is_dir():
        print(f"묶음 폴더가 없다: {bundle}", file=sys.stderr)
        return EXIT_FAILED
    warnings: tuple[EvalProblem, ...] = ()
    if indexed:
        try:
            environment = read_eval_environment(os.environ)
            report = validate_bundle_indexed(bundle, environment, COMPOSE_FILE)
        except (EvalEnvironmentError, ConfigurationError) as error:
            print(f"설정 오류: {error}", file=sys.stderr)
            return EXIT_FAILED
        problems, warnings = report.problems, report.warnings
    else:
        problems = validate_bundle(bundle, COMPOSE_FILE)
    for warning in warnings:
        print(f"경고\t{warning}", file=sys.stderr)
    if not problems:
        print(f"문제 없음: {bundle}")
        return EXIT_OK
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"묶음의 오류 {len(problems)}건", file=sys.stderr)
    return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
