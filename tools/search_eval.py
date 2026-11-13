"""검색 평가 도구의 명령줄 입구(명세 `.scratch/search-eval/spec.md`의 "자리와 층").

    uv run python tools/search_eval.py validate <묶음 폴더>

인자 해석과 조립만 한다. 묶음의 파일을 읽고 쓰는 코드는 `rag_engine.adapters`에, 값과 판정은
`rag_engine.domain`과 `rag_engine.app`에 있다. `tools/`는 이미지에 실리지 않으므로(`.dockerignore`)
이 입구는 관리자 페이지가 평가를 열기 전까지 제품 이미지에 없다. 하위 명령은 받는 티켓이 더한다.

`validate`는 데이터베이스 없이 묶음의 형식과 목록을 본다. 틀린 곳을 까닭과 함께 표준 오류에 한 줄씩
적는다.

종료 코드. 0은 문제 없음, 1은 묶음의 오류(없는 폴더도 든다), 2는 잘못된 인자다.
"""

import argparse
import sys
from collections.abc import Sequence
from pathlib import Path
from typing import Final

from rag_engine.adapters.eval_validate import validate_bundle

TOOL: Final = "tools/search_eval.py"
EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
EXIT_USAGE: Final = 2


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog=TOOL, description="검색 평가 도구")
    commands = parser.add_subparsers(dest="command", required=True)
    validate = commands.add_parser("validate", help="묶음의 형식과 목록을 본다(데이터베이스 없이)")
    validate.add_argument("bundle", type=Path, help="묶음 폴더")
    return parser


def main(argv: Sequence[str]) -> int:
    try:
        args = _parser().parse_args(list(argv))
    except SystemExit as stop:
        # argparse가 사용법을 출력하고 낸 종료다. 도움말은 0이고 잘못된 인자는 2다.
        return stop.code if isinstance(stop.code, int) else EXIT_USAGE
    bundle: Path = args.bundle
    return _validate(bundle)


def _validate(bundle: Path) -> int:
    if not bundle.is_dir():
        print(f"묶음 폴더가 없다: {bundle}", file=sys.stderr)
        return EXIT_FAILED
    problems = validate_bundle(bundle)
    if not problems:
        print(f"문제 없음: {bundle}")
        return EXIT_OK
    for problem in problems:
        print(problem, file=sys.stderr)
    print(f"묶음의 오류 {len(problems)}건", file=sys.stderr)
    return EXIT_FAILED


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
