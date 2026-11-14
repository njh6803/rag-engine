"""`compare --gate fast|full <보고서> <묶음 폴더>`의 조립(티켓 search-eval 08, 명세 "CI 게이트와
기준 보고서").

보고서 파일과 묶음 폴더의 기준 보고서(`baseline-fast.json`이나 `baseline-full.json`)를 읽어
`app.eval_compare`의 판정에 넘기고, 결과를 종료 코드와 표로 낸다. 0은 통과이고(하락폭 넘게 오른
숫자가 있으면 기준 보고서를 갱신하라는 안내를 표준 출력에 더한다), 1은 하락폭을 넘는 하락이거나 견줄
수 없는 보고서, 읽지 못하는 파일이다. 숫자를 견줄 수 없는 까닭은 모두 표준 오류에 적는다.

기준 보고서는 묶음 폴더의 경로 판정(`BundlePaths`)을 지나 읽는다. 새 보고서는 부르는 사람이 인자로
고른 자리라 그 판정의 대상이 아니다. 보고서 자리에 폴더를 주면 그 안의 `report.json`을 읽는다.

묶음 폴더에서 읽는 것은 기준 보고서 하나뿐이다. 기록 파일의 요청 지문과 TEI의 판이 지금 구성과
다른지는 `validate`가 보고하고(빠른 게이트의 잡이 `validate`를 `run`보다 앞에 두는 것은 명세가
정하고 티켓 11이 짓는다), `compare`는 보고서에 적힌 기록 파일의 해시만 견준다. 그래서 `run
--records read`가 불일치한 기록을 읽어 만든 보고서도 `compare` 혼자서는 막지 못한다.

보고서의 숫자가 NaN이나 무한대이면 `run`이 쓴 보고서가 아니라서 형식이 맞지 않는 파일로 읽는다.
"""

import sys
from pathlib import Path
from typing import Final

from pydantic import BaseModel, ConfigDict, Field, ValidationError

from rag_engine.adapters.bundle_paths import BundlePathError, BundlePaths
from rag_engine.app.eval_compare import (
    ComparableReport,
    CompareResult,
    Gate,
    MetricChange,
    MetricRow,
    compare_reports,
)
from rag_engine.domain.entities import JsonValue

EXIT_OK: Final = 0
EXIT_FAILED: Final = 1
REPORT_FILE: Final = "report.json"


class _Row(BaseModel):
    model_config = ConfigDict(extra="ignore")

    query_list: str
    stage: str
    hit_at_5: float = Field(allow_inf_nan=False)
    mrr: float = Field(allow_inf_nan=False)


class _EvalSet(BaseModel):
    model_config = ConfigDict(extra="ignore")

    content_hash: str


class _Records(BaseModel):
    model_config = ConfigDict(extra="ignore")

    files: dict[str, str]


class _Report(BaseModel):
    """`compare`가 읽는 칸만 든 보고서. 모르는 칸(`meta` 포함)은 버린다."""

    model_config = ConfigDict(extra="ignore")

    eval_set: _EvalSet
    config: dict[str, JsonValue]
    rows: list[_Row]
    records: _Records

    def comparable(self) -> ComparableReport:
        return ComparableReport(
            content_hash=self.eval_set.content_hash,
            config=self.config,
            record_files=self.records.files,
            rows=tuple(MetricRow(r.query_list, r.stage, r.hit_at_5, r.mrr) for r in self.rows),
        )


class _CompareFailed(Exception):
    """견줄 보고서를 얻지 못해 멈춘다. 메시지가 표준 오류에 오른다."""


def compare_command(report: Path, bundle: Path, gate: Gate, tool: str) -> int:
    """`report`(파일이나 `report.json`이 든 폴더)를 `bundle`의 기준 보고서와 `gate`로 견준 종료
    코드. `tool`은 오류 문장의 머리다."""
    try:
        return _compare(report, bundle, gate)
    except _CompareFailed as error:
        print(f"{tool} compare: {error}", file=sys.stderr)
        return EXIT_FAILED


def _compare(report: Path, bundle: Path, gate: Gate) -> int:
    if not bundle.is_dir():
        raise _CompareFailed(f"묶음 폴더가 없다: {bundle}")
    new_path = report / REPORT_FILE if report.is_dir() else report
    new = _read(new_path, f"보고서({new_path})")
    baseline = _read(_baseline_path(bundle, gate), f"기준 보고서({gate.baseline_file})")
    result = compare_reports(baseline.comparable(), new.comparable(), gate)
    return _report_result(result, gate)


def _baseline_path(bundle: Path, gate: Gate) -> Path:
    try:
        path = BundlePaths(bundle).resolve(gate.baseline_file)
    except BundlePathError as error:
        raise _CompareFailed(f"기준 보고서를 읽지 않는다: {error}") from error
    if not path.is_file():
        raise _CompareFailed(
            f"기준 보고서가 없다: {gate.baseline_file}. 견줄 값이 없어 실패한다. {_made_by(gate)}"
        )
    return path


def _made_by(gate: Gate) -> str:
    run = "빠른 실행(`run --through fused`)" if gate is Gate.FAST else "전체 실행"
    return (
        f"첫 기준 보고서는 {run}이 낸 report.json을 사용자의 승인을 받은 뒤 그대로"
        f" {gate.baseline_file}로 커밋해 만든다"
    )


def _read(path: Path, label: str) -> _Report:
    """파일을 읽어 필요한 칸을 푼다. 읽지 못하거나 형식이 맞지 않으면 `_CompareFailed`다. 까닭에
    파일의 내용은 싣지 않는다."""
    try:
        data = path.read_bytes()
    except OSError as error:
        raise _CompareFailed(f"{label}를 읽지 못했다({type(error).__name__})") from error
    try:
        return _Report.model_validate_json(data)
    except ValidationError as error:
        raise _CompareFailed(f"{label}를 읽지 못했다(`run`이 쓴 보고서의 형식이 아니다)") from error


def _report_result(result: CompareResult, gate: Gate) -> int:
    if result.incomparable:
        print(
            f"게이트 {gate.value}: 기준 보고서와 견줄 수 없어 숫자를 견주지 않았다.",
            file=sys.stderr,
        )
        for reason in result.incomparable:
            print(f"- {reason}", file=sys.stderr)
        print(
            f"기준 보고서를 갱신해야 한다: {gate.baseline_file}. 바뀐 숫자의 앞뒤 차이를 사용자에게"
            " 보이고 승인을 받은 뒤 새 보고서를 그 이름으로 커밋한다",
            file=sys.stderr,
        )
        return EXIT_FAILED
    if result.drops:
        print(
            f"게이트 {gate.value}: 하락폭을 넘어 떨어진 숫자가 {len(result.drops)}개 있다."
            " 하락폭은 상위 5 적중률 2%p, MRR 0.02이고 정확히 그만큼은 통과한다",
            file=sys.stderr,
        )
        for line in _table(result.drops):
            print(line, file=sys.stderr)
        return EXIT_FAILED
    print(
        f"통과: 게이트 {gate.value}에서 {gate.baseline_file}보다 하락폭을 넘어 떨어진 숫자가 없다"
    )
    if result.rises:
        print(
            f"기준 보고서를 갱신하라: 아래 숫자가 하락폭을 넘어 올랐다. {gate.baseline_file}을"
            " 새 보고서로 바꾸는 커밋은 숫자의 앞뒤 차이를 사용자에게 보이고 승인을 받는다"
        )
        for line in _table(result.rises):
            print(line)
    return EXIT_OK


def _table(changes: tuple[MetricChange, ...]) -> list[str]:
    """질의 목록, 지표, 기준값, 새 값, 기준값에서 새 값을 뺀 차의 표."""
    header = ("질의 목록", "지표", "기준값", "새 값", "차")
    rows = [
        (change.query_list, change.metric, *map(repr, (change.baseline, change.new)))
        + (repr(change.difference),)
        for change in changes
    ]
    return [
        "| " + " | ".join(header) + " |",
        "|" + "|".join("---" for _ in header) + "|",
        *("| " + " | ".join(cells) + " |" for cells in rows),
    ]
