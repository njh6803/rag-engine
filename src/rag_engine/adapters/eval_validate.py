"""묶음의 `validate` 조립(티켓 search-eval 02). 파일을 읽고, 목록을 판정하고, 파일을 본다.

읽기가 틀리면 그 오류만 낸다. 읽은 값이 없으면 목록과 파일을 판정할 수 없기 때문이다. 읽기를 지나면
목록의 오류(`check_eval_set`)와 파일의 오류(`check_bundle_files`)를 함께 낸다. 데이터베이스를 쓰지
않는다. 색인된 데이터베이스에서 글귀까지 보는 `--indexed`는 이 함수 밖의 일이다.
"""

from pathlib import Path

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.adapters.eval_bundle_files import check_bundle_files
from rag_engine.adapters.eval_set_reader import EvalSetFormatError, read_eval_set
from rag_engine.app.check_eval_set import check_eval_set
from rag_engine.domain.eval_set import EvalProblem


def validate_bundle(folder: Path) -> tuple[EvalProblem, ...]:
    """묶음 폴더의 오류를 모두 낸다. 문제가 없으면 빈 튜플이다."""
    paths = BundlePaths(folder)
    try:
        eval_set = read_eval_set(paths)
    except EvalSetFormatError as error:
        return error.problems
    return (*check_eval_set(eval_set), *check_bundle_files(paths, eval_set))
