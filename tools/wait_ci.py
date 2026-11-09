"""PR의 검사와 리뷰 봇이 모두 끝날 때까지 기다렸다가 결과를 한 번 찍고 끝난다.

Bash 도구의 `run_in_background`로 띄운다. 그 도구는 띄운 명령이 끝나면 세션을 다시 부르므로
(2026-10-13 데스크톱 앱 세션에 실린 Bash 도구 설명을 읽었다), 사람이 "CI 끝났어"로 깨우던
자리를 이 도구의 종료가 맡는다. 기다리는 동안 모델은 돌지 않는다.

왜 앱의 감시로 안 되나. 앱의 PR 감시(auto_fix)가 세션을 깨우는 계기로 도구 설명이 드는 것은 CI
실패, 충돌, 리뷰 코멘트이고 초록 완료는 들지 않는다(같은 날 읽은 `set_monitor` 도구 설명). PR
구독은 연 지 몇 분 뒤에 생겨 그 전에 끝난 첫 푸시의 CI는 알림이 없었다(대기열 37의 4회차). 앱 지침은
세션이 CI를 스케줄하거나 `gh`로 폴링하지 말라고 하는데, 이 도구는 그 지침과 어긋난다. 사용자가 자동
대기를 요청해 들였다(일지 2026-10-13-38). 앱의 감시가 초록 완료로도 깨우게 되면 이 도구를 걷어 낸다.

CodeRabbit의 상태. 푸시마다 리뷰 없이 `success`와 설명 `Review skipped: …`를 먼저 달고,
`@coderabbitai review`를 남기면 `pending`(`Review in progress`)을 거쳐 `success`의 `Review rate
limited`(한도 초과, 리뷰 없음)나 `Review completed`로 끝난다. 롤업의 상태만 보면 셋 다 SUCCESS라
설명을 함께 읽는다. 시간과 빈도는 `.scratch/harness/probes/ci_wait/check_timing.py`와 그 README 행이
원천이다.

CodeRabbit은 2026-10-26 무렵부터 결과를 상태가 아니라 체크 런으로 내기도 한다. combined status는
비고, 설명 자리에는 체크 런의 `output.title`이 온다. 건너뜀은 `skipped`와 `Review skipped: …`,
한도는 `neutral`과 `Review rate limited`, 리뷰를 마치면 `success`와 `Finished`다(PR #489·#401·#405
의 헤드에서 `gh api …/commits/<헤드>/check-runs`로 손으로 봤다, 대기열 499). 롤업의 CheckRun에는
`output`이 없어 `fetch_pr`가 그 목록(`check_runs`)도 읽고, 제목이 비지 않은 체크 런은 제목을
설명으로, `status`와 `conclusion`을 상태로 읽는다. 제목이 없어도 `status`가 `completed`가
아니면 진행 중으로 읽는다. 롤업의 건너뜀과 목록의 진행 중이 함께 오면 통과로 읽히기 때문이다.

판정. `gh pr view <N> --json headRefOid,mergeable,statusCheckRollup`과 그 헤드의 combined
status(`gh api repos/{owner}/{repo}/commits/<헤드>/status`, 맥락마다 마지막 상태와 설명), 그
헤드의 체크 런 목록(`gh api repos/{owner}/{repo}/commits/<헤드>/check-runs?per_page=100`)을
`interval`초마다 읽는다. gh와 git 호출 하나는 `CALL_TIMEOUT`초에서 끊고 실패로 센다. 멈춘 호출은
돌아오지 않아 대기의 시간 제한에도 걸리지 않는다(PR 직전 버그 리뷰). StatusContext의 상태는
설명과 같은 combined status에서 읽는다. 따로 읽은 롤업은 시각이 달라, 롤업의 건너뜀 SUCCESS와
combined의 `Review in progress`가 함께 오면 통과로 읽힌다.
- PR 헤드가 로컬 `HEAD`(`--head`로 바꾼다)와 다르면 기다린다. 푸시 직후에는 PR이 옛 헤드를
  가리켜, 옛 헤드의 초록을 보고 끝나면 초록 착시다. 처음부터 다른 채 `head_grace`초가 지나면
  기다릴 수 없다고 끝나고(푸시하지 않았거나 다른 커밋을 푸시했다), 같다가 바뀌면 새 푸시라 곧바로
  끝난다.
- 기대 이름(`EXPECTED`, `--expect`로 바꾼다)이 모두 나타났고, 나타난 검사가 모두 끝났고, 설명이
  `UNREQUESTED_PREFIX`로 시작하는 상태가 없으면 끝이다. 나타난 것만 보면 푸시 직후의 빈 목록이나
  아직 붙지 않은 검사 앞에서 끝났다고 한다. `verify`는 CI 잡을 모으는 잡이다.
- 나머지가 다 끝났는데 대기를 띄운 지 `request_grace`초(90)가 지나도 건너뜀 상태가 남았으면 리뷰를
  요청하지 않은 것이라 기다리지 않는다. 요청이 닿아 `Review in progress`가 되기까지 수십 초가
  걸려(같은 프로브), 요청하고 곧바로 다시 띄운 대기의 첫 조회는 아직 건너뜀을 볼 수 있다.
  `verify`는 needs가 끝난 뒤에야 롤업에 나타났다(PR #223에서 `gh pr checks`로 손으로 봤다).
- 나머지가 다 끝났고 실패가 있으면 리뷰 요청을 기다리지 않고 실패로 끝난다. 고쳐서 다시 푸시할
  헤드라 요청은 한도만 쓴다.
- 충돌이면 기다리지 않는다. 충돌한 PR에는 `pull_request` 워크플로가 돌지 않고(일지 2026-10-12-34),
  끝난 검사가 있어도 main을 합쳐야 병합할 수 있다.
- 끝난 검사의 결과가 `PASSING`이면 통과, 그 밖은 실패다. 같은 이름이 둘이면 끝나지 않은 쪽,
  다음으로 실패한 쪽을 든다.
- 예외는 계정 한도로 빨간 claude-review다. 그 실행은 리뷰를 시작하지 못하고 끝나, 그 빨강은
  지적이 아니라 리뷰 없음이다(`docs/constitution/operations.md` 리뷰 파이프라인 3, 대기열 327).
  claude-review가 빨가면 롤업의 `detailsUrl`에서 잡 번호를 꺼내 `gh run view --job <잡> --log`를
  잡마다 한 번 읽는다. 결과 블록(`"type": "result"`)이 `"is_error": true`, `"terminal_reason":
  "api_error"`이고 `result`가 `LIMIT_PREFIX`로 시작하면 실패로 세지 않는다. 그러면 위의 갈래대로
  CodeRabbit과 나머지 검사를 마저 기다리고, 통과 줄 끝에 한도로 리뷰 없음이라는 것과 그 문구(풀리는
  시각이 든다)를 적는다. 다른 실패나 시간 초과로 끝나면 그 사실은 끝 줄 앞의 줄에 남는다. 같은
  이름의 빨간 잡이 여럿이면 모두 한도일 때만 빼고, 하나라도 한도가 아니면 실패로 센다. 로그
  읽기가 실패하면 PR 조회처럼 모두 `max_fetch_errors`번까지 다음 조회에서 다시 읽고, 그래도 읽지
  못했거나 잡 주소가 없으면 가르지 못한 것이라 실패로 세며 그 이유를 끝 줄 앞에 적는다. 가르지
  못한 잡은 다른 검사를 기다리는 동안에도 다시 읽지 않는다. 한도로
  잘못 읽어 통과시키면 리뷰 없는 병합으로 이어져, 모를 때는 실패 쪽이다. 이 모양은 PR #292의 실행
  39047880157(한도)과 PR #278의 실행 38878140947(리뷰를 마친 초록)의 잡 로그로 손으로 봤다.

종료 코드는 0 통과, 1 실패나 충돌, 2 인자 오류, 3 시간 초과, 4 기다릴 수 없음(gh가 연달아
실패했다, 헤드가 다르거나 바뀌었다, 리뷰가 요청되지 않았다, 로컬 HEAD를 읽지 못했다)이다. 출력의
마지막 줄은 `끝:`으로 시작하는 결과와 다음 할 일 한 줄이다. 통과면 상태의 설명(리뷰를 했는지)을
붙인다. 예외는 argparse가 직접 찍는 인자 오류다.

못 보는 것.
- 기대 이름 밖에서 늦게 붙는 검사. 다른 검사가 다 끝난 뒤에 나타나면 그 전에 끝났다고 한다.
- 이름이 바뀐 기대 검사. 끝내 나타나지 않아 시간 초과로 끝나고, 출력에 빠진 이름을 적는다.
- 요청이 늦게 닿은 리뷰. 나머지 검사가 끝나고 요청 유예가 지날 때까지 건너뜀 상태면 요청이 없다고
  끝난다.
- 리뷰가 진행 중일 때의 체크 런 제목. 보지 못했다. 진행 중은 제목이 아니라 `status`가
  `completed`가 아닌 것으로 판정한다.
- 파일 수 한도(`Review skipped: … files exceed the limit …`)의 체크 런 모양. 보지 못했다. 제목이
  `Review skipped`로 시작하면 요청 전의 건너뜀과 같이 읽혀, 이 도구는 다시 요청하라고 끝낸다
  (대기열 374는 만료됐고 이 변경이 고치지 않았다).
- 체크 런 목록의 쪽. 한 번에 100개까지만 읽는다. 그 헤드의 검사는 열 개 안팎이다.
- 충돌은 한 번의 조회로 판정한다. 충돌을 풀고 푸시한 직후의 조회가 옛 헤드 기준의 `CONFLICTING`을
  읽는지는 재지 않았다. 틀리면 대기를 한 번 더 띄운다.
- 리뷰 코멘트의 내용. 끝났다는 것만 알리고, 코멘트는 깨어난 세션이 읽는다
  (`docs/constitution/operations.md` 리뷰 파이프라인 3).
- 주간 한도 밖의 한도 문구. `LIMIT_PREFIX`로 시작하지 않는 결과(다른 한도의 문구를 포함해)는
  진짜 실패로 센다. 실행 로그에서 본 한도 문구는 `LIMIT_PREFIX` 주석의 실행 셋에 나온 주간 한도의
  것뿐이다.
- 결과 블록 밖의 한도 문구. Claude가 읽은 파일이나 다른 단계의 출력에만 그 문구가 있으면 실패로
  센다.
- 클라우드 세션의 `gh run view`. 거기서 돌려 본 기록이 없다(`.claude/rules/tools.md` 클라우드
  항목). 실패하면 가르지 못한 것이라 claude-review를 실패로 세어, 이 변경 전과 같이 끝난다.
- 같은 이름의 재실행. 실패 뒤 다시 돌아 통과한 검사가 옛 실패와 함께 남으면 실패로 든다.
- 세션이 꺼진 뒤의 완료. 대기는 그 세션의 백그라운드 작업이다. 세션을 닫은 뒤 대기가 어떻게
  되는지는 재지 않았다.

쓰임: `uv run python tools/wait_ci.py <PR 번호>`를 Bash 도구의 `run_in_background`로 띄운다.
`--expect`는 이 도구를 복사한 저장소(KICKOFF.md)가 자기 검사 이름을 줄 때, `--interval`은 손으로
돌려 볼 때 쓴다.
"""

from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import time
from collections.abc import Callable, Collection, Sequence
from dataclasses import dataclass
from enum import Enum, auto

type Json = dict[str, Json] | list[Json] | str | int | float | bool | None

EXPECTED = ("verify", "claude-review", "CodeRabbit")
PASSING = frozenset({"SUCCESS", "NEUTRAL", "SKIPPED"})
# StatusContext 의 끝나지 않은 상태. CheckRun 은 status 가 COMPLETED 인지로 본다.
PENDING_STATES = frozenset({"PENDING", "EXPECTED"})
# 리뷰를 요청받기 전의 CodeRabbit 상태 설명. 상태는 SUCCESS 라 결과만 보면 끝난 것으로 읽힌다.
UNREQUESTED_PREFIX = "Review skipped"
# 외부 명령(gh, git) 하나의 시간 제한(초). 멈춘 호출은 돌아오지 않아 대기의 시간 제한에도 걸리지
# 않는다.
CALL_TIMEOUT = 60.0
# 계정 한도로 빨갤 수 있는 리뷰 검사와, 그 잡 로그의 결과 블록이 한도일 때 `result` 의 머리.
# 실행 38120400317(PR #172)·39045944809·39047880157(PR #292)에서 이 문구였다.
REVIEW_CHECK = "claude-review"
LIMIT_PREFIX = "You've hit your weekly limit"
LIMIT_REASON = "api_error"
JOB_URL = re.compile(r"/actions/runs/\d+/job/(\d+)")
# `gh run view --job <잡> --log` 의 줄마다 붙은 "<잡>\t<단계>\t<시각> " 접두.
# tools/gh_run_summary.py 의 PREFIX 와 같다. 이 도구는 스크립트로 돌아 그 모듈을 import 하지 못한다.
LOG_PREFIX = re.compile(r"^[^\t]*\t[^\t]*\t\S*\s?")

EXIT_PASSED = 0
EXIT_FAILED = 1
EXIT_USAGE = 2
EXIT_TIMED_OUT = 3
EXIT_CANNOT_WAIT = 4


class FetchError(Exception):
    """gh 가 PR 이나 상태를 읽지 못했다."""


@dataclass(frozen=True)
class Snapshot:
    """한 번 읽은 PR.

    checks 는 이름에서 결과로 가고, 끝나지 않은 검사는 None 이다. notes 는 StatusContext 의
    이름에서 마지막 상태의 설명으로, 제목이 있는 CheckRun 은 이름에서 `output.title` 로 간다.
    failed_jobs 는 CheckRun 의 이름에서, 끝나서 빨간 그 이름의 실행마다 `detailsUrl` 의 잡
    번호(주소가 없으면 None)로 간다.
    """

    head: str
    conflicting: bool
    checks: dict[str, str | None]
    notes: dict[str, str]
    failed_jobs: dict[str, tuple[str | None, ...]]


@dataclass(frozen=True)
class Verdict:
    done: bool
    failed: tuple[str, ...]
    pending: tuple[str, ...]
    missing: tuple[str, ...]
    unrequested: tuple[str, ...]


@dataclass(frozen=True)
class Options:
    expected: tuple[str, ...]
    timeout: float
    interval: float
    head_grace: float
    request_grace: float
    max_fetch_errors: int


def _text(value: Json) -> str:
    return value if isinstance(value, str) else ""


def _result(check: dict[str, Json]) -> tuple[str, str | None]:
    if _text(check.get("__typename")) == "StatusContext":
        state = _text(check.get("state"))
        return _text(check.get("context")), None if state in PENDING_STATES else state
    # 진행 중인 CheckRun 의 completedAt 은 비지 않고 0001-01-01T00:00:00Z 라 보지 않는다.
    name = _text(check.get("name"))
    if _text(check.get("status")) != "COMPLETED":
        return name, None
    return name, _text(check.get("conclusion")) or "UNKNOWN"


def _worse(left: str | None, right: str | None) -> str | None:
    if left is None or right is None:
        return None
    return right if left in PASSING else left


def parse_snapshot(payload: Json) -> Snapshot:
    """`fetch_pr` 의 출력(PR 의 세 칸, 그 헤드의 `statuses` 와 `check_runs`)을 읽는다."""
    if not isinstance(payload, dict):
        raise FetchError(f"PR 응답이 객체가 아니다: {payload!r}")
    rollup = payload.get("statusCheckRollup")
    checks: dict[str, str | None] = {}
    failed_jobs: dict[str, tuple[str | None, ...]] = {}
    for check in rollup if isinstance(rollup, list) else []:
        if not isinstance(check, dict):
            continue
        name, result = _result(check)
        checks[name] = _worse(checks[name], result) if name in checks else result
        if result is not None and result not in PASSING:
            job = JOB_URL.search(_text(check.get("detailsUrl")))
            failed_jobs[name] = (*failed_jobs.get(name, ()), job.group(1) if job else None)
    notes: dict[str, str] = {}
    # CodeRabbit 은 결과를 체크 런의 `output.title` 로 내기도 한다. 롤업의 CheckRun 에는 제목이
    # 없어 헤드의 check-runs 에서 읽는다. 상태도 그 목록에서 읽는다. 롤업은 따로 읽어 시각이
    # 달라, 롤업의 건너뜀 SKIPPED 와 목록의 진행 중이 함께 오면 통과로 읽힌다. 제목이 없는 체크
    # 런(GitHub Actions 의 것)은 끝난 것이면 롤업의 것을 그대로 두고, 끝나지 않았으면 제목이 있든
    # 없든 진행 중으로 읽는다.
    listed = payload.get("check_runs")
    for run in listed if isinstance(listed, list) else []:
        if not isinstance(run, dict):
            continue
        output = run.get("output")
        title = _text(output.get("title")).strip() if isinstance(output, dict) else ""
        name = _text(run.get("name"))
        completed = _text(run.get("status")) == "completed"
        if title:
            notes[name] = title
        elif completed:
            continue
        checks[name] = (_text(run.get("conclusion")).upper() or "UNKNOWN") if completed else None
    # StatusContext 의 상태는 설명과 같은 combined status 에서 읽는다. 롤업은 따로 읽어 시각이
    # 달라, 롤업의 건너뜀 SUCCESS 와 combined 의 Review in progress 가 함께 오면 통과로 읽힌다.
    statuses = payload.get("statuses")
    for status in statuses if isinstance(statuses, list) else []:
        if not isinstance(status, dict):
            continue
        name = _text(status.get("context"))
        state = _text(status.get("state")).upper()
        notes[name] = _text(status.get("description"))
        if state:
            checks[name] = None if state in PENDING_STATES else state
    return Snapshot(
        head=_text(payload.get("headRefOid")),
        conflicting=payload.get("mergeable") == "CONFLICTING",
        checks=checks,
        notes=notes,
        failed_jobs=failed_jobs,
    )


def limit_message(lines: Sequence[str]) -> str | None:
    """잡 로그의 결과 블록이 API 오류이고 `result` 가 한도 문구면 그 문구를 낸다. 아니면 None.

    결과 블록은 들여 쓴 JSON 객체라, 접두를 뗀 줄이 `{` 인 데서 `}` 인 데까지를 객체 하나로
    읽는다(tools/gh_run_summary.py 의 `_blocks` 와 같은 모양). 객체 밖의 줄은 보지 않는다.
    """
    buffer: list[str] | None = None
    for raw in lines:
        line = LOG_PREFIX.sub("", raw, count=1).rstrip()
        if line == "{":
            buffer = [line]
            continue
        if buffer is None:
            continue
        buffer.append(line)
        if line != "}":
            continue
        try:
            block: Json = json.loads("\n".join(buffer))
        except ValueError:
            block = None
        buffer = None
        if not isinstance(block, dict) or block.get("type") != "result":
            continue
        result = block.get("result")
        failed = block.get("is_error") is True and block.get("terminal_reason") == LIMIT_REASON
        if failed and isinstance(result, str) and result.startswith(LIMIT_PREFIX):
            return result
    return None


def judge(snapshot: Snapshot, expected: Sequence[str], excused: Collection[str] = ()) -> Verdict:
    """excused 는 계정 한도로 빨개 실패로 세지 않을 이름이다."""
    pending = tuple(name for name, result in snapshot.checks.items() if result is None)
    failed = tuple(
        name
        for name, result in snapshot.checks.items()
        if result is not None and result not in PASSING and name not in excused
    )
    missing = tuple(name for name in expected if name not in snapshot.checks)
    unrequested = tuple(
        name for name, note in snapshot.notes.items() if note.startswith(UNREQUESTED_PREFIX)
    )
    return Verdict(
        done=not pending and not missing and not unrequested,
        failed=failed,
        pending=pending,
        missing=missing,
        unrequested=unrequested,
    )


def _report(number: str, snapshot: Snapshot) -> list[str]:
    lines = [f"PR #{number} 헤드 {snapshot.head[:7]}"]
    for name, result in sorted(snapshot.checks.items()):
        note = f" ({snapshot.notes[name]})" if snapshot.notes.get(name) else ""
        lines.append(f"  {name} {'진행 중' if result is None else result}{note}")
    return lines


def _settle(
    number: str,
    snapshot: Snapshot,
    elapsed: float,
    options: Options,
    review: Review,
) -> tuple[int, list[str]] | None:
    """헤드가 맞는 PR 로 끝낼지 정한다. 더 기다리면 None. review 는 빨간 리뷰 검사를 가른 것이다."""
    limited = review.outcome is Outcome.LIMIT
    verdict = judge(snapshot, options.expected, excused=(REVIEW_CHECK,) if limited else ())
    lines = _report(number, snapshot)
    if limited:
        lines.append(f"  {REVIEW_CHECK} 은 계정 한도로 리뷰 없음: {review.detail}")
    if review.outcome is Outcome.UNCLEAR:
        lines.append(f"  {REVIEW_CHECK} 이 한도인지 가르지 못했다: {review.detail}")
    if snapshot.conflicting:
        return EXIT_FAILED, [*lines, "끝: 충돌. main 을 합치고 푸시한 뒤 다시 띄운다"]
    settled = not verdict.pending and not verdict.missing
    # 실패가 있으면 리뷰 요청을 기다리지 않는다. 고쳐서 다시 푸시할 헤드라 요청은 한도만 쓴다.
    if settled and verdict.failed:
        return EXIT_FAILED, [*lines, f"끝: 실패 {', '.join(verdict.failed)}"]
    if verdict.done:
        notes = "".join(f". {name}: {note}" for name, note in sorted(snapshot.notes.items()))
        reviewless = f". {REVIEW_CHECK}: 계정 한도로 리뷰 없음({review.detail})" if limited else ""
        return EXIT_PASSED, [*lines, f"끝: 모두 통과{notes}{reviewless}"]
    # 요청 직후에 띄운 대기의 첫 조회는 아직 건너뜀을 볼 수 있어 요청 유예를 둔다.
    if settled and elapsed >= options.request_grace:
        names = ", ".join(verdict.unrequested)
        return EXIT_CANNOT_WAIT, [
            *lines,
            f"끝: {names} 리뷰가 요청되지 않았다. `@coderabbitai review` 를 남기고 다시 띄운다",
        ]
    if elapsed < options.timeout:
        return None
    waiting = [
        *verdict.pending,
        *(f"{name}(나타나지 않음)" for name in verdict.missing),
        *(f"{name}(요청되지 않음)" for name in verdict.unrequested),
    ]
    minutes = options.timeout / 60
    return EXIT_TIMED_OUT, [
        *lines,
        f"끝: 시간 초과 {minutes:.0f}분. 남은 것 {', '.join(waiting)}. "
        "`gh pr checks` 로 멈춘 잡인지 보고 사람에게 알린다",
    ]


class Outcome(Enum):
    """빨간 리뷰 검사를 가른 갈래."""

    NOT_LIMIT = auto()  # 한도가 아니거나 빨갛지 않다
    LIMIT = auto()  # detail 은 계정 한도의 문구
    UNCLEAR = auto()  # detail 은 가르지 못한 이유
    RETRYING = auto()  # 로그 읽기가 실패해 다음 조회에서 다시 읽는다


@dataclass(frozen=True)
class Review:
    """빨간 리뷰 검사를 가른 것."""

    outcome: Outcome = Outcome.NOT_LIMIT
    detail: str = ""


class ReviewLimits:
    """claude-review 의 빨간 잡이 계정 한도인지 잡 로그로 가른다.

    끝난 잡의 로그는 바뀌지 않아 잡마다 한 번만 읽는다. 읽기가 `max_errors`번째로 실패하기
    전까지는 다시 읽으라고 내고, `max_errors`번째 실패에서 가르지 못한 것으로 정해 그 잡은 다시
    읽지 않는다. 다른 검사를 기다리는 동안 다시 읽으면 낸 판정이 뒤집힌다.
    """

    def __init__(self, classify: Callable[[str], str | None], max_errors: int) -> None:
        self._classify = classify
        self._max_errors = max_errors
        self._known: dict[str, str | None] = {}
        self._errors: dict[str, int] = {}
        self._unclear: dict[str, str] = {}

    def review(self, snapshot: Snapshot) -> Review:
        jobs = snapshot.failed_jobs.get(REVIEW_CHECK, ())
        # 빨간 잡이 모두 한도일 때만 LIMIT 이다. 하나라도 한도가 아니면 그 자리에서 NOT_LIMIT 을
        # 내므로, 루프를 끝까지 돈 limit 은 모든 잡이 한도였을 때의 마지막 문구다.
        limit = ""
        for job in jobs:
            if job is None:
                return Review(Outcome.UNCLEAR, "롤업에 잡 주소(detailsUrl)가 없다")
            if job in self._unclear:
                return Review(Outcome.UNCLEAR, self._unclear[job])
            if job not in self._known:
                try:
                    self._known[job] = self._classify(job)
                except FetchError as error:
                    return self._failed(job, error)
            known = self._known[job]
            if known is None:
                return Review()
            limit = known
        return Review(Outcome.LIMIT, limit) if jobs else Review()

    def _failed(self, job: str, error: FetchError) -> Review:
        """읽기 실패를 세고, `max_errors`번째면 그 잡을 가르지 못한 것으로 기억한다."""
        self._errors[job] = self._errors.get(job, 0) + 1
        if self._errors[job] < self._max_errors:
            return Review(Outcome.RETRYING)
        self._unclear[job] = f"잡 {job} 로그를 {self._errors[job]}번 읽지 못했다: {error}"
        return Review(Outcome.UNCLEAR, self._unclear[job])


def wait(
    number: str,
    head: str,
    options: Options,
    fetch: Callable[[str], Json],
    sleep: Callable[[float], None],
    clock: Callable[[], float],
    classify: Callable[[str], str | None],
) -> tuple[int, list[str]]:
    """검사가 끝날 때까지 PR 읽기와 `interval`초 잠자기를 되풀이한다. 종료 코드와 찍을 줄을 낸다.

    classify 는 잡 번호를 받아 그 잡이 계정 한도로 빨갰으면 한도 문구를, 아니면 None 을 낸다.
    """
    started = clock()
    errors: list[str] = []
    seen_head = False
    limits = ReviewLimits(classify, options.max_fetch_errors)
    while True:
        elapsed = clock() - started
        try:
            snapshot = parse_snapshot(fetch(number))
        except FetchError as error:
            errors.append(str(error))
            if len(errors) >= options.max_fetch_errors:
                return EXIT_CANNOT_WAIT, [
                    *errors,
                    f"끝: gh 가 연달아 {len(errors)}번 실패했다. 위 오류를 사람에게 알린다",
                ]
        else:
            errors.clear()
            if snapshot.head == head:
                seen_head = True
                review = limits.review(snapshot)
                # 로그를 다시 읽을 동안은 끝내지 않는다. 읽기는 잡마다 모두 max_fetch_errors 번으로
                # 끝난다.
                retrying = review.outcome is Outcome.RETRYING
                settled = None if retrying else _settle(number, snapshot, elapsed, options, review)
                if settled is not None:
                    return settled
            elif seen_head:
                return EXIT_CANNOT_WAIT, [
                    f"끝: PR #{number} 헤드가 {head[:7]} 에서 {snapshot.head[:7]} 로 바뀌었다. "
                    "새 푸시면 새 헤드로 대기를 다시 띄운다"
                ]
            elif elapsed >= options.head_grace:
                return EXIT_CANNOT_WAIT, [
                    f"끝: PR #{number} 헤드 {snapshot.head[:7]} 가 로컬 {head[:7]} 와 "
                    f"{elapsed:.0f}초 동안 다르다. 푸시했는지 본다"
                ]
        sleep(options.interval)


def _gh_text(*args: str) -> str:
    try:
        completed = subprocess.run(
            ["gh", *args],
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            timeout=CALL_TIMEOUT,
        )
    except subprocess.TimeoutExpired as error:
        raise FetchError(f"gh 가 {CALL_TIMEOUT:.0f}초 안에 돌아오지 않았다") from error
    except OSError as error:
        raise FetchError(f"gh 를 띄우지 못했다: {error}") from error
    if completed.returncode != 0:
        raise FetchError(completed.stderr.strip() or f"gh 종료 코드 {completed.returncode}")
    return completed.stdout


def _gh(*args: str) -> Json:
    stdout = _gh_text(*args)
    try:
        payload: Json = json.loads(stdout)
    except json.JSONDecodeError as error:
        raise FetchError(f"gh 출력이 JSON 이 아니다: {error}") from error
    return payload


def fetch_pr(number: str) -> Json:
    """PR 의 세 칸에 그 헤드의 combined status 의 `statuses` 와 `check_runs` 를 붙여 낸다."""
    pr = _gh("pr", "view", number, "--json", "headRefOid,mergeable,statusCheckRollup")
    if not isinstance(pr, dict):
        raise FetchError(f"PR 응답이 객체가 아니다: {pr!r}")
    head = _text(pr.get("headRefOid"))
    commit = f"repos/{{owner}}/{{repo}}/commits/{head}"
    combined = _gh("api", f"{commit}/status")
    statuses = combined.get("statuses") if isinstance(combined, dict) else None
    # 한 쪽에 100개를 넘는 검사는 없다고 본다. 롤업의 검사 이름이 열 안팎이다.
    runs = _gh("api", f"{commit}/check-runs?per_page=100")
    check_runs = runs.get("check_runs") if isinstance(runs, dict) else None
    return {
        **pr,
        "statuses": statuses if isinstance(statuses, list) else [],
        "check_runs": check_runs if isinstance(check_runs, list) else [],
    }


def job_limit(job: str) -> str | None:
    """잡 하나의 로그를 읽어 계정 한도로 빨갰으면 그 문구를 낸다. gh 가 실패하면 FetchError."""
    return limit_message(_gh_text("run", "view", "--job", job, "--log").split("\n"))


def local_head() -> str:
    completed = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        capture_output=True,
        encoding="utf-8",
        check=True,
        timeout=CALL_TIMEOUT,
    )
    return completed.stdout.strip()


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="PR 의 검사가 모두 끝날 때까지 기다린다.")
    parser.add_argument("number", help="PR 번호")
    parser.add_argument("--head", help="기다릴 헤드 커밋. 없으면 로컬 HEAD")
    parser.add_argument(
        "--expect", action="append", help="나타나야 끝인 검사 이름. 주면 기본값을 갈음한다"
    )
    parser.add_argument("--timeout", type=float, default=30.0, help="분. 기본 30")
    parser.add_argument("--interval", type=float, default=30.0, help="초. 기본 30")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    number: str = args.number
    head_arg: str | None = args.head
    expect_arg: list[str] | None = args.expect
    timeout_minutes: float = args.timeout
    interval: float = args.interval
    # isdigit 만으로는 '²' 같은 비ASCII 숫자가 지나가 gh 실패 세 번 뒤에야 끝난다.
    if not (number.isascii() and number.isdigit()):
        print(f"끝: PR 번호가 숫자가 아니다: {number}")
        return EXIT_USAGE
    if interval <= 0 or timeout_minutes <= 0:
        print(f"끝: --interval 과 --timeout 은 0보다 커야 한다: {interval}, {timeout_minutes}")
        return EXIT_USAGE
    # PR 헤드는 40자 SHA 라 짧은 SHA 는 끝내 같지 않고 헤드 유예 뒤에 끝난다.
    if head_arg is not None and len(head_arg) != 40:
        print(f"끝: --head 는 40자 SHA 로 준다: {head_arg}")
        return EXIT_USAGE
    if head_arg is None:
        try:
            head_arg = local_head()
        except (OSError, subprocess.SubprocessError) as error:
            print(f"끝: 로컬 HEAD 를 읽지 못했다: {error}. `--head` 로 준다")
            return EXIT_CANNOT_WAIT
    options = Options(
        expected=tuple(expect_arg) if expect_arg else EXPECTED,
        timeout=timeout_minutes * 60,
        interval=interval,
        head_grace=120.0,
        request_grace=90.0,
        max_fetch_errors=3,
    )
    code, lines = wait(number, head_arg, options, fetch_pr, time.sleep, time.monotonic, job_limit)
    print("\n".join(lines))
    return code


if __name__ == "__main__":
    # 한글을 찍는다. PYTHONUTF8 이 없는 윈도 파이프에서는 cp949 로 나간다(대기열 228).
    for stream in (sys.stdout, sys.stderr):
        if isinstance(stream, io.TextIOWrapper):
            stream.reconfigure(encoding="utf-8")
    raise SystemExit(main())
