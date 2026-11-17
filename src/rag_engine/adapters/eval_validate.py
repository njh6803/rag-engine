"""묶음의 `validate` 조립(티켓 search-eval 02, 03). 파일을 읽고, 목록을 판정하고, 파일을 본다.

읽기가 틀리면 그 오류만 낸다. 읽은 값이 없으면 목록과 파일을 판정할 수 없기 때문이다. 읽기를 지나면
목록의 오류(`check_eval_set`)와 파일의 오류(`check_bundle_files`)를 함께 낸다. `validate_bundle`은
데이터베이스를 쓰지 않는다. 색인된 데이터베이스에서 글귀까지 보는 `--indexed`는
`validate_bundle_indexed`가 맡고, 그 함수가 평가 전용 데이터베이스를 읽기만 한다. 두 함수는 묶음을
한 번만 읽고 그 값으로 모든 판정을 한다. 읽기를 판정마다 따로 하면 읽는 사이에 묶음이 바뀌었을 때
판정이 서로 다른 값을 본다. 추론 기록의 판정(`check_records`)은 파일과 이 체크아웃의 코드만 읽어
끝점도 데이터베이스도 쓰지 않는다.
"""

from dataclasses import dataclass
from pathlib import Path

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.adapters.eval_bundle_files import check_bundle_files
from rag_engine.adapters.eval_database import check_indexed
from rag_engine.adapters.eval_environment import EvalEnvironment
from rag_engine.adapters.eval_records_check import check_records
from rag_engine.adapters.eval_set_reader import EvalSetFormatError, read_eval_set
from rag_engine.adapters.postgres.engine import run_in_selector_loop
from rag_engine.app.check_eval_set import check_eval_set
from rag_engine.domain.eval_set import EvalProblem, EvalSet


@dataclass(frozen=True, slots=True)
class ValidationReport:
    """`problems`는 묶음의 오류이고 종료 코드를 1로 만든다. `warnings`는 알리기만 한다."""

    problems: tuple[EvalProblem, ...]
    warnings: tuple[EvalProblem, ...]


def _read_and_check(
    folder: Path, compose_file: Path
) -> tuple[EvalSet | None, tuple[EvalProblem, ...]]:
    """묶음을 한 번 읽고 파일 판정과 추론 기록 판정까지 한다. 읽지 못하면 값이 없고 읽기의 오류만
    낸다. `compose_file`은 `compose.eval.yml`이다(기록 판정이 TEI 이미지 태그를 견준다)."""
    paths = BundlePaths(folder)
    try:
        eval_set = read_eval_set(paths)
    except EvalSetFormatError as error:
        return None, error.problems
    return eval_set, (
        *check_eval_set(eval_set),
        *check_bundle_files(paths, eval_set),
        *check_records(paths, eval_set.config, compose_file),
    )


def validate_bundle(folder: Path, compose_file: Path) -> tuple[EvalProblem, ...]:
    """묶음 폴더의 오류를 모두 낸다. 문제가 없으면 빈 튜플이다."""
    return _read_and_check(folder, compose_file)[1]


def validate_bundle_indexed(
    folder: Path, environment: EvalEnvironment, compose_file: Path
) -> ValidationReport:
    """`validate`의 판정에 색인된 데이터베이스의 판정(모든 문서가 색인되어 있는지, 글귀가 본문에
    있는지)을 더한다. 이벤트 루프를 스스로 열므로 실행 중인 루프 안에서는 부를 수 없다. 묶음을 읽지
    못하면 데이터베이스를 보지 않는다. 글귀를 견줄 값이 없기 때문이다."""
    eval_set, problems = _read_and_check(folder, compose_file)
    if eval_set is None:
        return ValidationReport(problems, ())
    indexed_problems, warnings = run_in_selector_loop(check_indexed(environment, eval_set))
    return ValidationReport((*problems, *indexed_problems), warnings)
