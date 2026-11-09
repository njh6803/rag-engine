"""tools/wait_ci.py의 순수 함수와 대기 루프 검증. gh와 git을 부르는 부분은 실제 실행으로 확인한다.

검사 조각은 `gh pr view <N> --json headRefOid,mergeable,statusCheckRollup`의 실제 모양을 따른다
(PR #215·#219, 2026-10-13). 진행 중인 CheckRun도 `completedAt`이 `0001-01-01T00:00:00Z`로 차 있다.
`statuses`는 `fetch_pr`가 헤드의 combined
status(`gh api repos/{owner}/{repo}/commits/<헤드>/status`) 에서 옮겨 붙이는 칸이다. 항목마다
`context`, 소문자 `state`, `description`이 있다(PR #220에서 봤다). 설명 문구는 PR #196~#220의
CodeRabbit 상태 이력에 나온 그대로다 (`.scratch/harness/probes/ci_wait/check_timing.py`).
"""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence

import pytest
from tools.wait_ci import (
    CALL_TIMEOUT,
    EXIT_CANNOT_WAIT,
    EXIT_FAILED,
    EXIT_PASSED,
    EXIT_TIMED_OUT,
    EXIT_USAGE,
    LOG_PREFIX,
    FetchError,
    Json,
    Options,
    fetch_pr,
    job_limit,
    judge,
    limit_message,
    main,
    parse_snapshot,
    wait,
)

from tools import gh_run_summary

HEAD = "1c98d6400000000000000000000000000000000a"
OLD_HEAD = "88038b8000000000000000000000000000000000"
NEW_HEAD = "b067ed7000000000000000000000000000000000"
EXPECTED = ("verify", "claude-review", "CodeRabbit")
SKIPPED = "Review skipped: manual review required for this OSS repository"
COMPLETED = "Review completed"
RATE_LIMITED = "Review rate limited"


def run(
    name: str, status: str = "COMPLETED", conclusion: str = "SUCCESS", job: str = "117440173217"
) -> Json:
    return {
        "__typename": "CheckRun",
        "name": name,
        "status": status,
        "conclusion": conclusion if status == "COMPLETED" else "",
        "startedAt": "2026-10-13T04:41:24Z",
        "completedAt": "2026-10-13T04:44:17Z" if status == "COMPLETED" else "0001-01-01T00:00:00Z",
        "detailsUrl": f"https://github.com/njh6803/agent-os/actions/runs/39047880157/job/{job}",
    }


def context(name: str, state: str) -> Json:
    return {"__typename": "StatusContext", "context": name, "state": state}


def coderabbit(
    state: str = "SUCCESS", description: str = COMPLETED, rollup_state: str | None = None
) -> list[Json]:
    """롤업의 CodeRabbit 칸과 combined status 의 그 항목을 함께 낸다.

    rollup_state 를 주면 롤업만 그 상태로 둔다. 두 조회가 다른 시각의 것일 때다.
    """
    combined: Json = {"context": "CodeRabbit", "state": state.lower(), "description": description}
    return [context("CodeRabbit", rollup_state or state), combined]


def coderabbit_run(
    conclusion: str = "NEUTRAL",
    title: str = RATE_LIMITED,
    status: str = "COMPLETED",
    rollup_status: str | None = None,
    rollup_conclusion: str | None = None,
) -> list[Json]:
    """롤업의 CodeRabbit CheckRun 과 헤드의 check-runs 의 그 항목을 함께 낸다.

    CodeRabbit 은 결과를 상태의 설명이 아니라 체크 런의 `output.title` 로 낸다(PR #401·#405·#489,
    2026-11-08 손으로 봤다). 롤업의 CheckRun 에는 `output` 이 없다. rollup_status 와
    rollup_conclusion 을 주면 롤업만 그 값으로 둔다. 두 조회가 다른 시각의 것일 때다.
    """
    finished = status == "COMPLETED"
    listed: Json = {
        "name": "CodeRabbit",
        "status": status.lower(),
        "conclusion": conclusion.lower() if finished else None,
        "output": {"title": title},
    }
    rollup = run(
        "CodeRabbit",
        status=rollup_status or status,
        conclusion=rollup_conclusion or conclusion,
    )
    return [rollup, listed]


def payload(*checks: Json, head: str = HEAD, mergeable: str = "MERGEABLE") -> Json:
    dicts = [c for c in checks if isinstance(c, dict)]
    rollup: list[Json] = [c for c in dicts if "__typename" in c]
    check_runs: list[Json] = [c for c in dicts if "output" in c]
    statuses: list[Json] = [c for c in dicts if "__typename" not in c and "output" not in c]
    return {
        "headRefOid": head,
        "mergeable": mergeable,
        "statusCheckRollup": rollup,
        "statuses": statuses,
        "check_runs": check_runs,
    }


def green(head: str = HEAD, description: str = COMPLETED) -> Json:
    return payload(
        run("python"),
        run("verify"),
        run("claude-review"),
        *coderabbit(description=description),
        head=head,
    )


def test_기대한_이름이_모두_끝나고_실패가_없으면_통과다() -> None:
    verdict = judge(parse_snapshot(green()), EXPECTED)
    assert verdict.done
    assert verdict.failed == ()


def test_기대한_이름이_빠졌으면_나머지가_끝나도_끝나지_않았다() -> None:
    # 나타난 것만 보면 푸시 직후의 빈 목록이나 아직 붙지 않은 검사 앞에서 끝났다고 한다.
    snapshot = parse_snapshot(payload(run("python"), run("verify"), run("claude-review")))
    verdict = judge(snapshot, EXPECTED)
    assert not verdict.done
    assert verdict.missing == ("CodeRabbit",)


def test_진행_중인_CheckRun은_completedAt이_차_있어도_끝나지_않았다() -> None:
    snapshot = parse_snapshot(payload(run("python", status="IN_PROGRESS")))
    assert snapshot.checks == {"python": None}


def test_StatusContext의_PENDING은_끝나지_않았고_SUCCESS는_끝났다() -> None:
    pending = parse_snapshot(payload(context("CodeRabbit", "PENDING")))
    done = parse_snapshot(payload(context("CodeRabbit", "SUCCESS")))
    assert pending.checks == {"CodeRabbit": None}
    assert done.checks == {"CodeRabbit": "SUCCESS"}


def test_리뷰를_요청하기_전의_건너뜀_상태는_SUCCESS여도_끝나지_않았다() -> None:
    # CodeRabbit 은 푸시마다 리뷰 없이 SUCCESS "Review skipped" 를 먼저 단다(PR #196~#220 모두).
    snapshot = parse_snapshot(
        payload(run("verify"), run("claude-review"), *coderabbit(description=SKIPPED))
    )
    verdict = judge(snapshot, EXPECTED)
    assert not verdict.done
    assert verdict.unrequested == ("CodeRabbit",)
    assert verdict.pending == ()


def test_StatusContext의_상태는_설명과_같은_combined_status에서_읽는다() -> None:
    # 롤업과 combined status 는 따로 읽어 시각이 다르다. 롤업이 건너뜀의 SUCCESS 를 보는 사이
    # combined status 가 이미 진행 중이면, 롤업을 믿으면 통과로 끝난다(PR 직전 버그 리뷰).
    snapshot = parse_snapshot(
        payload(
            run("verify"),
            run("claude-review"),
            *coderabbit(state="PENDING", description="Review in progress", rollup_state="SUCCESS"),
        )
    )
    assert snapshot.checks["CodeRabbit"] is None
    assert not judge(snapshot, EXPECTED).done


def test_체크_런_모양의_CodeRabbit_건너뜀_제목도_요청하기_전으로_센다() -> None:
    # CodeRabbit 은 결과를 체크 런의 제목으로 내게 바뀌어 combined status 가 비었다. 롤업만
    # 보면 SKIPPED 라 통과로 끝나 리뷰를 기다리지 않았다(PR #489, 대기열 499).
    snapshot = parse_snapshot(
        payload(run("verify"), run("claude-review"), *coderabbit_run("SKIPPED", SKIPPED))
    )
    verdict = judge(snapshot, EXPECTED)
    assert snapshot.notes == {"CodeRabbit": SKIPPED}
    assert verdict.unrequested == ("CodeRabbit",)
    assert not verdict.done


def test_체크_런의_상태는_제목과_같은_check_runs에서_읽는다() -> None:
    # 롤업과 check-runs 는 따로 읽어 시각이 다르다. 롤업이 건너뜀을 보는 사이 체크 런이 이미
    # 진행 중이면, 롤업을 믿으면 통과로 끝난다(StatusContext 와 같은 시각 차).
    snapshot = parse_snapshot(
        payload(
            run("verify"),
            run("claude-review"),
            *coderabbit_run(
                "",
                "Review in progress",
                status="IN_PROGRESS",
                rollup_status="COMPLETED",
                rollup_conclusion="SKIPPED",
            ),
        )
    )
    assert snapshot.checks["CodeRabbit"] is None
    assert not judge(snapshot, EXPECTED).done


def test_제목이_없는_진행_중_체크_런도_끝나지_않은_것으로_읽는다() -> None:
    # 리뷰가 진행 중일 때의 제목은 보지 못했다. 제목이 비어 있어도 status 가 completed 가 아니면
    # 롤업의 건너뜀 SKIPPED 를 믿고 통과로 끝나면 안 된다.
    snapshot = parse_snapshot(
        payload(
            run("verify"),
            run("claude-review"),
            *coderabbit_run(
                "",
                "",
                status="IN_PROGRESS",
                rollup_status="COMPLETED",
                rollup_conclusion="SKIPPED",
            ),
        )
    )
    assert snapshot.checks["CodeRabbit"] is None
    assert "CodeRabbit" not in snapshot.notes
    assert not judge(snapshot, EXPECTED).done


def test_제목이_없는_체크_런은_설명으로_읽지_않는다() -> None:
    # GitHub Actions 의 체크 런은 `output.title` 이 null 이다. 통과 줄에 이름만 늘면 안 된다.
    untitled: Json = {"name": "verify", "status": "completed", "output": {"title": None}}
    no_output: Json = {"name": "python", "status": "completed", "output": None}
    blank: Json = {"name": "lint", "status": "completed", "output": {"title": "  "}}
    snapshot = parse_snapshot(
        payload(
            run("verify"), run("python"), run("lint"), untitled, no_output, blank, *coderabbit_run()
        )
    )
    assert snapshot.notes == {"CodeRabbit": RATE_LIMITED}
    assert snapshot.checks["verify"] == "SUCCESS"
    assert snapshot.checks["python"] == "SUCCESS"
    assert snapshot.checks["lint"] == "SUCCESS"


@pytest.mark.parametrize("conclusion", ["SKIPPED", "NEUTRAL"])
def test_건너뛴_검사와_중립은_통과로_센다(conclusion: str) -> None:
    # 초안 PR의 claude-review는 잡의 if로 건너뛰어 SKIPPED로 남는다.
    snapshot = parse_snapshot(
        payload(run("verify"), run("claude-review", conclusion=conclusion), *coderabbit())
    )
    assert judge(snapshot, EXPECTED).failed == ()


@pytest.mark.parametrize(
    "check",
    [
        run("python", conclusion="FAILURE"),
        run("python", conclusion="CANCELLED"),
        run("python", conclusion="TIMED_OUT"),
        context("python", "ERROR"),
    ],
)
def test_실패와_취소와_시간_초과는_실패로_센다(check: Json) -> None:
    snapshot = parse_snapshot(payload(check, run("verify"), run("claude-review"), *coderabbit()))
    verdict = judge(snapshot, EXPECTED)
    assert verdict.done
    assert verdict.failed == ("python",)


def test_같은_이름이_둘이면_끝나지_않은_쪽과_실패한_쪽을_든다() -> None:
    pending = parse_snapshot(payload(run("python"), run("python", status="QUEUED")))
    failed = parse_snapshot(payload(run("python", conclusion="FAILURE"), run("python")))
    assert pending.checks == {"python": None}
    assert failed.checks == {"python": "FAILURE"}


class Script:
    """조회마다 정해 둔 응답을 차례로 내고(마지막 것은 되풀이한다), 잠든 시간만큼 시계를 민다."""

    def __init__(
        self,
        *responses: Json | FetchError,
        limits: Sequence[str | FetchError | None] = (None,),
    ) -> None:
        self.responses = list(responses)
        self.limits = list(limits)
        self.now = 0.0
        self.sleeps: list[float] = []
        self.fetched: list[str] = []
        self.classified: list[str] = []

    def classify(self, job: str) -> str | None:
        """claude-review 잡의 한도 문구. 정해 둔 것을 차례로 낸다(마지막 것은 되풀이한다)."""
        self.classified.append(job)
        limit = self.limits.pop(0) if len(self.limits) > 1 else self.limits[0]
        if isinstance(limit, FetchError):
            raise limit
        return limit

    def fetch(self, number: str) -> Json:
        self.fetched.append(number)
        response = self.responses.pop(0) if len(self.responses) > 1 else self.responses[0]
        if isinstance(response, FetchError):
            raise response
        return response

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds

    def clock(self) -> float:
        return self.now


def options(**overrides: float) -> Options:
    return Options(
        expected=EXPECTED,
        timeout=overrides.get("timeout", 600.0),
        interval=overrides.get("interval", 30.0),
        head_grace=overrides.get("head_grace", 120.0),
        request_grace=overrides.get("request_grace", 60.0),
        max_fetch_errors=3,
    )


def waited(script: Script, opts: Options | None = None) -> tuple[int, str]:
    """기다린 결과를 낸다. 어느 길로 끝나든 마지막 줄이 `끝:` 인지 함께 본다.

    깨어난 세션은 그 줄을 결과와 다음 할 일로 읽는다(next-session merge.md 2).
    """
    fetch: Callable[[str], Json] = script.fetch
    code, lines = wait(
        "221", HEAD, opts or options(), fetch, script.sleep, script.clock, script.classify
    )
    assert lines[-1].startswith("끝:")
    return code, "\n".join(lines)


def test_끝나지_않았으면_간격만큼_자고_다시_본다() -> None:
    script = Script(payload(run("python", status="IN_PROGRESS")), green())
    code, out = waited(script)
    assert code == EXIT_PASSED
    assert script.sleeps == [30.0]
    assert script.fetched == ["221", "221"]
    assert out.endswith(f"끝: 모두 통과. CodeRabbit: {COMPLETED}")


def test_한도에_걸린_리뷰는_통과로_끝나되_끝_줄에_적는다() -> None:
    # PR #196~#219의 마지막 헤드에서 요청 스물둘 가운데 스물하나가 몇 초 만에 이 상태였다.
    script = Script(green(description=RATE_LIMITED))
    code, out = waited(script)
    assert code == EXIT_PASSED
    assert out.endswith(f"CodeRabbit: {RATE_LIMITED}")


@pytest.mark.parametrize(
    ("conclusion", "title"), [("NEUTRAL", RATE_LIMITED), ("SUCCESS", "Finished")]
)
def test_체크_런_모양의_CodeRabbit이_끝나면_통과_줄에_제목을_적는다(
    conclusion: str, title: str
) -> None:
    # 한도에 걸린 것(neutral)과 리뷰한 것(success)이 같은 통과 줄이면 사람이 코멘트를 열어 봐야
    # 갈린다. PR #489 의 대기가 리뷰 여부 없이 끝났다(대기열 499).
    script = Script(
        payload(run("verify"), run("claude-review"), *coderabbit_run(conclusion, title), head=HEAD)
    )
    code, out = waited(script)
    assert code == EXIT_PASSED
    assert out.endswith(f"끝: 모두 통과. CodeRabbit: {title}")


def test_체크_런_모양의_CodeRabbit이_건너뜀이면_요청_유예_뒤에_기다릴_수_없다() -> None:
    script = Script(
        payload(run("verify"), run("claude-review"), *coderabbit_run("SKIPPED", SKIPPED))
    )
    code, out = waited(script)
    assert code == EXIT_CANNOT_WAIT
    assert "@coderabbitai review" in out.splitlines()[-1]
    assert script.sleeps == [30.0, 30.0]


def test_체크_런_모양의_CodeRabbit이_건너뜀에서_진행을_거쳐_끝날_때까지_기다린다() -> None:
    script = Script(
        payload(run("verify"), run("claude-review"), *coderabbit_run("SKIPPED", SKIPPED)),
        payload(
            run("verify"),
            run("claude-review"),
            *coderabbit_run("", "Review in progress", status="IN_PROGRESS"),
        ),
        payload(run("verify"), run("claude-review"), *coderabbit_run("SUCCESS", "Finished")),
    )
    code, out = waited(script)
    assert code == EXIT_PASSED
    assert script.sleeps == [30.0, 30.0]
    assert out.endswith("CodeRabbit: Finished")


def test_리뷰가_요청되면_건너뜀에서_진행을_거쳐_끝날_때까지_기다린다() -> None:
    script = Script(
        payload(
            run("verify", status="IN_PROGRESS"),
            run("claude-review"),
            *coderabbit(description=SKIPPED),
        ),
        payload(
            run("verify"),
            run("claude-review"),
            *coderabbit(state="PENDING", description="Review in progress"),
        ),
        green(),
    )
    code, _ = waited(script)
    assert code == EXIT_PASSED
    assert script.sleeps == [30.0, 30.0]


def test_나머지가_끝났는데_리뷰가_요청되지_않았으면_요청_유예_뒤에_기다릴_수_없다() -> None:
    # PR #208·#214의 마지막 헤드는 요청이 없어 건너뜀 상태에 머물렀다.
    script = Script(green(description=SKIPPED))
    code, out = waited(script)
    assert code == EXIT_CANNOT_WAIT
    assert "@coderabbitai review" in out.splitlines()[-1]
    assert script.sleeps == [30.0, 30.0]


def test_요청_직후에_다시_띄우면_건너뜀이_진행으로_바뀌기를_유예_안에서_기다린다() -> None:
    # 건너뜀에서 Review in progress 까지 7~40초였다. 요청하고 곧바로 띄운 대기의 첫 조회는
    # 아직 건너뜀을 볼 수 있다(PR 직전 버그 리뷰).
    script = Script(
        green(description=SKIPPED),
        payload(
            run("verify"),
            run("claude-review"),
            *coderabbit(state="PENDING", description="Review in progress"),
        ),
        green(),
    )
    code, _ = waited(script)
    assert code == EXIT_PASSED
    assert script.sleeps == [30.0, 30.0]


def test_실패가_있으면_리뷰가_요청되지_않았어도_실패로_곧바로_끝난다() -> None:
    # 고쳐서 다시 푸시할 헤드에 리뷰를 요청하면 한도만 쓴다.
    script = Script(
        payload(
            run("verify", conclusion="FAILURE"),
            run("claude-review"),
            *coderabbit(description=SKIPPED),
        )
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert out.splitlines()[-1].startswith("끝: 실패 verify")
    assert script.sleeps == []


def test_실패가_있으면_1이고_실패한_이름을_찍는다() -> None:
    script = Script(
        payload(
            run("python", conclusion="FAILURE"),
            run("verify", conclusion="FAILURE"),
            run("claude-review"),
            *coderabbit(),
        )
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert "python FAILURE" in out
    assert out.endswith("끝: 실패 python, verify")


LIMIT = "You've hit your weekly limit · resets Oct 18, 9pm (UTC)"


def job_log(*body: str) -> list[str]:
    """`gh run view --job <잡> --log` 의 줄 모양. 실행 39047880157(PR #292)의 claude-review 잡에서
    결과 블록의 판정에 쓰는 키만 남겼다."""
    prefix = "claude-review\tRun Claude Code Review\t2026-10-17T16:05:46.9839275Z "
    return [f"{prefix}{line}" for line in body]


def result_block(*, is_error: str, result: str, reason: str = "api_error") -> list[str]:
    return job_log(
        "{",
        '  "permission_denials": [],',
        f'  "terminal_reason": "{reason}",',
        f'  "is_error": {is_error},',
        '  "num_turns": 1,',
        '  "subtype": "success",',
        '  "api_error_status": 429,',
        f'  "result": {result},',
        '  "type": "result"',
        "}",
    )


def test_결과_블록이_오류이고_주간_한도_문구면_그_문구를_낸다() -> None:
    lines = [
        *job_log("##[group]Run anthropics/claude-code-action@v1"),
        *result_block(is_error="true", result=f'"{LIMIT}"'),
        *job_log(
            "##[error]Action failed with error: Claude execution failed: result is_error:true"
        ),
    ]
    assert limit_message(lines) == LIMIT


@pytest.mark.parametrize(
    "lines",
    [
        # 리뷰를 마친 뒤 다른 단계에서 빨갰다. 결과 블록은 오류가 아니다.
        result_block(is_error="false", result=f'"{LIMIT}"'),
        # 오류이고 한도 문구지만 API 오류로 끝나지 않았다(본 한도 실행 셋은 모두 api_error 였다).
        result_block(is_error="true", result=f'"{LIMIT}"', reason="completed"),
        # 한도가 아닌 API 오류.
        result_block(is_error="true", result='"API Error: 500 Internal server error"'),
        # 주간 한도 밖의 한도 문구는 진짜 실패로 센다(독스트링의 못 보는 것). 지어낸 문구다.
        result_block(is_error="true", result='"You\'ve hit your session limit · resets 3pm"'),
        # 결과가 문자열이 아니다.
        result_block(is_error="true", result="null"),
        # Claude 단계 전에 끝났다(체크아웃 실패 등).
        job_log("##[error]Process completed with exit code 128."),
        # 한도 문구가 결과 블록 밖(Read 로 읽은 파일 원문 등)에만 있다.
        job_log(f"  {LIMIT}"),
    ],
)
def test_한도가_아닌_빨강은_문구를_내지_않는다(lines: list[str]) -> None:
    assert limit_message(lines) is None


def test_잡_로그의_접두는_gh_run_summary와_같은_모양으로_뗀다() -> None:
    # 이 도구는 스크립트로 돌아 tools.gh_run_summary 를 import 하지 못해 같은 패턴을 다시 짰다.
    assert LOG_PREFIX.pattern == gh_run_summary.PREFIX.pattern


def test_빨간_CheckRun의_detailsUrl에서_잡_번호를_읽는다() -> None:
    snapshot = parse_snapshot(
        payload(
            run("claude-review", conclusion="FAILURE", job="111"),
            run("claude-review", conclusion="FAILURE", job="222"),
            run("verify"),
            *coderabbit(),
        )
    )
    # 같은 이름의 빨간 실행은 모두 담고, 통과한 검사는 담지 않는다.
    assert snapshot.failed_jobs == {"claude-review": ("111", "222")}


def test_claude_review가_한도로_빨가면_실패로_세지_않고_CodeRabbit을_마저_기다린다() -> None:
    # PR #292 에서 리뷰를 요청한 직후 띄운 대기가 `끝: 실패 claude-review` 로 끝났다(대기열 327).
    limited = run("claude-review", conclusion="FAILURE")
    script = Script(
        payload(run("verify"), limited, *coderabbit(description=SKIPPED)),
        payload(
            run("verify"), limited, *coderabbit(state="PENDING", description="Review in progress")
        ),
        payload(run("verify"), limited, *coderabbit()),
        limits=[LIMIT],
    )
    code, out = waited(script)
    assert code == EXIT_PASSED
    assert script.sleeps == [30.0, 30.0]
    last = out.splitlines()[-1]
    assert "claude-review" in last
    assert "리뷰 없음" in last
    assert LIMIT in last
    assert f"CodeRabbit: {COMPLETED}" in last
    # 같은 잡의 로그는 한 번만 읽는다.
    assert script.classified == ["117440173217"]


def test_claude_review의_진짜_빨강은_곧바로_실패로_끝난다() -> None:
    script = Script(
        payload(
            run("verify"),
            run("claude-review", conclusion="FAILURE"),
            *coderabbit(description=SKIPPED),
        ),
        limits=[None],
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert out.splitlines()[-1] == "끝: 실패 claude-review"
    assert script.sleeps == []


def test_한도인지_가르지_못하면_실패로_세고_이유를_적는다() -> None:
    script = Script(
        payload(
            run("verify"),
            run("claude-review", conclusion="FAILURE"),
            *coderabbit(description=SKIPPED),
        ),
        limits=[FetchError("gh 가 60초 안에 돌아오지 않았다")],
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert out.splitlines()[-1] == "끝: 실패 claude-review"
    assert "가르지 못했다: 잡 117440173217 로그를 3번 읽지 못했다" in out
    assert "gh 가 60초 안에 돌아오지 않았다" in out
    # PR 조회처럼 max_fetch_errors(3) 번까지 읽어 본다.
    assert script.classified == ["117440173217"] * 3
    assert script.sleeps == [30.0, 30.0]


def test_가르지_못한_잡은_다른_검사를_기다리는_동안_다시_읽지_않는다() -> None:
    # 다른 검사가 아직 돌면 가르지 못한 뒤에도 대기가 이어진다. 그동안 조회마다 다시 읽으면
    # 실패마다 CALL_TIMEOUT 을 쓰고, 나중에 읽히면 낸 판정이 뒤집힌다(PR 직전 bug-perf-review).
    red = run("claude-review", conclusion="FAILURE")
    running = payload(run("verify", status="IN_PROGRESS"), red, *coderabbit())
    script = Script(
        running,
        running,
        running,
        running,
        running,
        payload(run("verify"), red, *coderabbit()),
        limits=[FetchError("gh 가 60초 안에 돌아오지 않았다")] * 3 + [LIMIT],
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert out.splitlines()[-1] == "끝: 실패 claude-review"
    assert "가르지 못했다: 잡 117440173217 로그를 3번 읽지 못했다" in out
    assert script.classified == ["117440173217"] * 3


def test_잡_로그_읽기가_한_번_실패해도_다음_조회에서_다시_읽어_한도를_가른다() -> None:
    # 나머지 검사가 모두 끝나 있어도 한 번의 gh 실패로 곧바로 실패로 끝나지 않는다.
    script = Script(
        payload(run("verify"), run("claude-review", conclusion="FAILURE"), *coderabbit()),
        limits=[FetchError("gh 가 60초 안에 돌아오지 않았다"), LIMIT],
    )
    code, out = waited(script)
    assert code == EXIT_PASSED
    assert f"claude-review: 계정 한도로 리뷰 없음({LIMIT})" in out.splitlines()[-1]
    assert script.sleeps == [30.0]


def test_잡_주소가_없으면_가르지_못한_것으로_실패로_센다() -> None:
    no_url = run("claude-review", conclusion="FAILURE")
    assert isinstance(no_url, dict)
    del no_url["detailsUrl"]
    script = Script(payload(run("verify"), no_url, *coderabbit()), limits=[LIMIT])
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert out.splitlines()[-1] == "끝: 실패 claude-review"
    assert "가르지 못했다: 롤업에 잡 주소(detailsUrl)가 없다" in out
    assert script.classified == []


@pytest.mark.parametrize("limits", [[None, LIMIT], [LIMIT, None]])
def test_같은_이름의_빨간_잡이_둘이면_모두_한도일_때만_뺀다(
    limits: list[str | None],
) -> None:
    # 진짜 실패와 한도로 빨간 재실행이 함께 남으면, 롤업의 순서와 상관없이 실패다.
    script = Script(
        payload(
            run("verify"),
            run("claude-review", conclusion="FAILURE", job="111"),
            run("claude-review", conclusion="FAILURE", job="222"),
            *coderabbit(),
        ),
        limits=limits,
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert out.splitlines()[-1] == "끝: 실패 claude-review"
    assert "리뷰 없음" not in out


def test_같은_이름의_빨간_잡이_모두_한도면_뺀다() -> None:
    script = Script(
        payload(
            run("verify"),
            run("claude-review", conclusion="FAILURE", job="111"),
            run("claude-review", conclusion="FAILURE", job="222"),
            *coderabbit(),
        ),
        limits=[LIMIT],
    )
    code, _ = waited(script)
    assert code == EXIT_PASSED
    assert script.classified == ["111", "222"]


def test_claude_review가_한도여도_다른_실패가_있으면_그것만_실패로_든다() -> None:
    script = Script(
        payload(
            run("verify", conclusion="FAILURE"),
            run("claude-review", conclusion="FAILURE"),
            *coderabbit(),
        ),
        limits=[LIMIT],
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert out.splitlines()[-1] == "끝: 실패 verify"
    assert LIMIT in out


def test_다른_검사가_빨가면_한도를_가르지_않는다() -> None:
    # 로그를 읽는 것은 claude-review 뿐이다. 다른 검사의 빨강은 한도 문구가 있어도 실패다.
    script = Script(
        payload(
            run("verify", conclusion="FAILURE"), run("claude-review"), *coderabbit(), head=HEAD
        ),
        limits=[LIMIT],
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert out.splitlines()[-1] == "끝: 실패 verify"
    assert script.classified == []


def test_잡_로그는_시간_제한을_두고_읽고_실패하면_조회_실패로_센다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: list[object] = []

    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, CALL_TIMEOUT)

    monkeypatch.setattr(subprocess, "run", stuck)
    with pytest.raises(FetchError):
        job_limit("117440173217")
    assert seen == [CALL_TIMEOUT]


def test_PR_헤드가_로컬_HEAD로_바뀌기를_기다린다() -> None:
    # 푸시 직후 PR이 아직 옛 헤드를 가리키면 옛 헤드의 초록을 보고 끝나면 안 된다.
    script = Script(green(head=OLD_HEAD), green())
    code, _ = waited(script)
    assert code == EXIT_PASSED
    assert script.sleeps == [30.0]


def test_헤드가_유예를_넘겨도_다르면_기다릴_수_없다() -> None:
    script = Script(green(head=OLD_HEAD))
    code, out = waited(script, options(head_grace=60.0))
    assert code == EXIT_CANNOT_WAIT
    assert script.sleeps == [30.0, 30.0]
    assert OLD_HEAD[:7] in out
    assert HEAD[:7] in out


def test_기다리던_헤드가_바뀌면_곧바로_끝난다() -> None:
    # 새 푸시가 있으면 앞 대기는 유예를 기다리지 않고 바뀐 헤드를 알리며 끝난다.
    script = Script(payload(run("verify", status="IN_PROGRESS")), green(head=NEW_HEAD))
    code, out = waited(script)
    assert code == EXIT_CANNOT_WAIT
    assert script.sleeps == [30.0]
    assert NEW_HEAD[:7] in out.splitlines()[-1]


def test_시간_제한을_넘기면_남은_이름을_찍는다() -> None:
    script = Script(payload(run("python", status="IN_PROGRESS"), run("verify")))
    code, out = waited(script, options(timeout=90.0))
    assert code == EXIT_TIMED_OUT
    assert script.sleeps == [30.0, 30.0, 30.0]
    last = out.splitlines()[-1]
    assert "python" in last
    assert "claude-review" in last
    assert "CodeRabbit" in last


def test_충돌이면_검사를_기다리지_않는다() -> None:
    # 충돌한 PR에는 pull_request 워크플로가 돌지 않아, 기다리면 시간 제한까지 간다
    # (일지 2026-10-12-34).
    script = Script(payload(mergeable="CONFLICTING"))
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert "충돌" in out.splitlines()[-1]
    assert script.sleeps == []


def test_충돌이면_검사가_다_끝났어도_1이다() -> None:
    script = Script(
        payload(
            run("python"),
            run("verify"),
            run("claude-review"),
            *coderabbit(),
            mergeable="CONFLICTING",
        )
    )
    code, out = waited(script)
    assert code == EXIT_FAILED
    assert "충돌" in out.splitlines()[-1]


def test_gh가_한_번_실패하면_다시_본다() -> None:
    script = Script(FetchError("HTTP 502"), green())
    code, _ = waited(script)
    assert code == EXIT_PASSED


def test_gh_실패는_사이에_성공이_끼면_처음부터_센다() -> None:
    pending = payload(run("verify", status="IN_PROGRESS"))
    script = Script(
        FetchError("HTTP 502"),
        FetchError("HTTP 502"),
        pending,
        FetchError("HTTP 502"),
        FetchError("HTTP 502"),
        green(),
    )
    code, _ = waited(script)
    assert code == EXIT_PASSED
    assert len(script.fetched) == 6


def test_gh가_연달아_실패하면_기다릴_수_없다() -> None:
    script = Script(FetchError("HTTP 502"))
    code, out = waited(script)
    assert code == EXIT_CANNOT_WAIT
    assert "HTTP 502" in out
    assert len(script.fetched) == 3


def test_gh_호출이_멈추면_시간_제한으로_끊고_조회_실패로_센다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # 멈춘 gh 는 subprocess.run 에서 돌아오지 않아 대기의 시간 제한에도 걸리지 않는다
    # (PR 직전 버그 리뷰). 호출 하나에 시간 제한을 두고, 넘기면 연속 실패로 센다.
    seen: list[object] = []

    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, CALL_TIMEOUT)

    monkeypatch.setattr(subprocess, "run", stuck)
    with pytest.raises(FetchError):
        fetch_pr("221")
    assert seen == [CALL_TIMEOUT]


def test_fetch_pr은_헤드의_check_runs를_읽어_check_runs_칸으로_붙인다(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    listed: Json = {"name": "CodeRabbit", "status": "completed", "output": {"title": SKIPPED}}
    commit = f"repos/{{owner}}/{{repo}}/commits/{HEAD}"
    answers: dict[str, Json] = {
        "pr": {"headRefOid": HEAD, "mergeable": "MERGEABLE", "statusCheckRollup": []},
        f"{commit}/status": {"statuses": []},
        f"{commit}/check-runs?per_page=100": {"check_runs": [listed]},
    }
    calls: list[list[str]] = []
    timeouts: list[object] = []

    def gh(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(args)
        timeouts.append(kwargs.get("timeout"))
        key = "pr" if args[1] == "pr" else args[2]
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(answers[key]), stderr="")

    monkeypatch.setattr(subprocess, "run", gh)
    fetched = fetch_pr("221")
    assert isinstance(fetched, dict)
    assert fetched["check_runs"] == [listed]
    assert fetched["statuses"] == []
    assert len(calls) == 3
    assert timeouts == [CALL_TIMEOUT] * 3


def test_check_runs_조회가_실패하면_조회_실패로_센다(monkeypatch: pytest.MonkeyPatch) -> None:
    def gh(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        if "check-runs" in args[2]:
            return subprocess.CompletedProcess(args, 1, stdout="", stderr="HTTP 502")
        body: Json = {"headRefOid": HEAD, "statuses": []}
        return subprocess.CompletedProcess(args, 0, stdout=json.dumps(body), stderr="")

    monkeypatch.setattr(subprocess, "run", gh)
    with pytest.raises(FetchError, match="HTTP 502"):
        fetch_pr("221")


def test_gh를_띄우지_못하면_조회_실패로_센다(monkeypatch: pytest.MonkeyPatch) -> None:
    def denied(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise PermissionError(args[0])

    monkeypatch.setattr(subprocess, "run", denied)
    with pytest.raises(FetchError):
        fetch_pr("221")


def test_로컬_HEAD를_읽는_git이_멈추면_끝_줄을_찍고_기다릴_수_없다(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # claude-review 가 짚었다. gh 에만 시간 제한을 두면 git 이 멈출 때 대기가 시작도 못 한다.
    seen: list[object] = []

    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, CALL_TIMEOUT)

    monkeypatch.setattr(subprocess, "run", stuck)
    code = main(["221"])
    assert code == EXIT_CANNOT_WAIT
    assert seen == [CALL_TIMEOUT]
    assert capsys.readouterr().out.splitlines()[-1].startswith("끝:")


@pytest.mark.parametrize(
    "argv",
    [
        ["abc"],
        ["²"],  # isdigit 은 참이지만 gh 가 받지 못한다
        ["221", "--interval", "0"],
        ["221", "--head", "abc1234"],  # 짧은 SHA 는 PR 헤드와 끝내 같지 않다
    ],
)
def test_인자가_잘못되면_gh를_부르기_전에_끝_줄을_찍고_2로_끝난다(
    argv: list[str], capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    def forbidden(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise AssertionError(f"부르지 않아야 한다: {args}")

    monkeypatch.setattr(subprocess, "run", forbidden)
    code = main(argv)
    assert code == EXIT_USAGE
    assert capsys.readouterr().out.splitlines()[-1].startswith("끝:")
