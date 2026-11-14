"""검색 평가 도구의 명령줄 입구(명세 `.scratch/search-eval/spec.md`의 "자리와 층").

    uv run python tools/search_eval.py validate <묶음 폴더> [--indexed]
    uv run python tools/search_eval.py index <묶음 폴더> [--config <파일>]
    uv run python tools/search_eval.py run --through fused|rerank --out <폴더> <묶음 폴더>
        [--config <파일>]
    uv run python tools/search_eval.py inspect <묶음 폴더> <질의 목록 이름> <기대 근거 id>
        [--through fused|rerank] [--config <파일>]

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
데이터베이스인지)을 지나야 돈다. 전체 실행은 리랭커 끝점 `RAG_EVAL_RERANKER_URL`이 없으면 그 이름을
알리고 종료 코드 1이다.

`inspect`는 질의 하나를 `run`과 같은 길로 돌려 그 질의의 글, 기대 근거, 단계마다의 상위 조각의 글을
표준 출력에만 찍는다. 파일은 쓰지 않는다. `--through`는 `fused`(기본)와 `rerank` 가운데 하나다.

`--config <파일>`은 `index`, `run`, `inspect`가 받는다. 주지 않으면 묶음의 `config.json`이다. 준
구성 파일은 부르는 사람이 고른 자리라 묶음 폴더 밖이어도 된다. 보고서의 `config`와 내용 해시는 쓴
구성으로 계산한다. 후보 수를 바꿔 같은 평가를 도는 일이 그 쓰임이다. 임베딩 모델, 차원, 청킹을 바꾼
구성은 그 구성으로 색인한 데이터베이스에서만 돈다(`index`에도 같은 파일을 준다).

데이터베이스에 붙는 하위 명령(`index`, `run`, `inspect`, `validate --indexed`)은 평가 전용 환경 변수
`RAG_EVAL_DATABASE_URL`, `RAG_EVAL_DATA_DIR`, `RAG_EVAL_EMBEDDING_URL`(과 있으면
`RAG_EVAL_RERANKER_URL`. 전체 실행은 이것이 반드시 있어야 한다)만 읽는다. 제품의 `RAG_*`와 작업
폴더의 `.env`는 읽지 않는다.

종료 코드. 0은 문제 없음, 1은 묶음이나 색인의 오류(없는 폴더, 빠진 환경 변수도 든다), 2는 잘못된
인자다.
"""

import argparse
import os
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from rag_engine.adapters.eval_environment import EvalEnvironmentError, read_eval_environment
from rag_engine.adapters.eval_index import index_bundle
from rag_engine.adapters.eval_inspect import inspect_evaluation
from rag_engine.adapters.eval_run import current_commit, run_evaluation
from rag_engine.adapters.eval_validate import validate_bundle, validate_bundle_indexed
from rag_engine.app.eval_stages import Stage
from rag_engine.domain.errors import ConfigurationError
from rag_engine.domain.eval_set import EvalProblem
from rag_engine.worker.assembly import run_once_with_settings

TOOL: Final = "tools/search_eval.py"
EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_USAGE: Final = 2
THROUGH_CHOICES: Final = ("fused", "rerank")
REPOSITORY: Final = Path(__file__).resolve().parent.parent


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
    _add_config(index)
    run = commands.add_parser("run", help="색인된 묶음을 평가해 보고서를 쓴다")
    run.add_argument("bundle", type=Path, help="묶음 폴더")
    run.add_argument(
        "--through",
        action="append",
        choices=THROUGH_CHOICES,
        default=[],
        help="fused(합친 뒤까지, 빠른 실행)와 rerank(리랭크 뒤까지, 전체 실행) 가운데 하나",
    )
    run.add_argument("--out", type=Path, required=True, help="보고서를 쓰는 폴더")
    _add_config(run)
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
    return parser


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
    if args.command == "run":
        return _run(bundle, args.out, args.through, args.config)
    if args.command == "inspect":
        stage = _stage(args.through)
        return inspect_evaluation(
            bundle,
            args.query_list,
            args.evidence_id,
            os.environ,
            through=stage,
            config_file=args.config,
        )
    if args.command == "index":
        # 설정 오류는 `index_bundle`이 안에서 잡아 종료 코드로 낸다.
        return index_bundle(bundle, os.environ, run_once_with_settings, config_file=args.config)
    indexed: bool = args.indexed
    return _validate(bundle, indexed=indexed)


def _stage(through: str) -> Stage:
    return Stage.RERANK if through == "rerank" else Stage.FUSED


def _run(bundle: Path, out: Path, through: list[str], config_file: Path | None) -> int:
    if len(through) != 1:
        choices = " 또는 ".join(THROUGH_CHOICES)
        print(f"{TOOL} run: --through는 {choices} 가운데 하나를 한 번만 받는다", file=sys.stderr)
        return EXIT_USAGE
    return run_evaluation(
        bundle,
        out,
        os.environ,
        through=_stage(through[0]),
        commit=current_commit(REPOSITORY),
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
            report = validate_bundle_indexed(bundle, environment)
        except (EvalEnvironmentError, ConfigurationError) as error:
            print(f"설정 오류: {error}", file=sys.stderr)
            return EXIT_FAILED
        problems, warnings = report.problems, report.warnings
    else:
        problems = validate_bundle(bundle)
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
