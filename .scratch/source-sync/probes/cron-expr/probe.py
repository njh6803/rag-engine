"""cronsim 2.8 이 일정 표현식을 어떻게 읽는지를 소비 지점까지 잰다(ADR 0022, source-sync 명세).

ADR 0022 가 다음 실행 시각의 계산을 cronsim 2.8 에 맡겼고, 명세에 넘긴 물음이 넷이다. 초 칸이 든
여섯 칸 표현식을 받는지(받으면 명세가 거부하는 방법을 정한다), 설치 시간대(`Asia/Seoul`)로 읽은
시각이 맞는지, 틀린 표현식이 어떤 예외로 오는지, 그리고 이 라이브러리를 쓰는 코드가 타입 검사를
지나는지다. 보는 것 일곱.
A. 설치된 버전, 타입 정보(`py.typed`)가 실렸는지, 기대는 패키지.
B. ADR 0022 가 예로 든 다섯 칸 표현식 셋의 다음 실행 시각(한국 시간과 UTC).
C. 칸 수가 다섯이 아닌 표현식(여섯 칸, 일곱 칸, 네 칸, 빈 글, `@daily` 같은 줄임말)을 받는지.
D. 값이 틀린 표현식의 예외 타입.
E. 오지 않는 날짜(2월 31일)를 적은 표현식.
F. 요일을 적는 여러 꼴(0 과 7, 이름, `L`, `#`)과 일·요일을 함께 적었을 때.
G. 시간대 정보가 없는 시각을 주었을 때와, 서머타임이 있는 시간대에서 건너뛰는 시각.

소비 지점은 `next_run` 이다. 명세가 정하려는 규칙(공백으로 가른 칸이 다섯일 때만 cronsim 에
넘긴다)을 그대로 쓴 함수이고, pyright strict 가 이 파일을 0 오류로 지나는지를 함께 본다.

실행(저장소 루트에서. Windows 에는 시간대 자료가 없어 `tzdata` 를 얹는다):
    uv run --with cronsim==2.8 --with tzdata python -I -X utf8 \
        .scratch/source-sync/probes/cron-expr/probe.py
타입 검사: 저장소 설정의 기본 exclude(`**/.*`)가 `.scratch` 를 건너뛰므로 임시 pyrightconfig 로
돌린다. 그 설정은 exclude 가 빈 목록, typeCheckingMode 가 strict, pythonVersion 이 3.12 이고
include 는 두지 않는다(절대 경로의 include 는 pyright 가 무시해 볼 파일을 인자로 준다).
    uv run --with cronsim==2.8 --with tzdata pyright -p <설정> --outputjson <이 파일의 경로>
출력의 `filesAnalyzed` 가 1 인지로 파일을 실제로 봤는지 확인한다. 출력 `probe_out.txt`,
`pyright_out.json`.
"""

from __future__ import annotations

import importlib.metadata
import sys
import threading
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from cronsim import CronSim, CronSimError

SEOUL = ZoneInfo("Asia/Seoul")
# 2026-11-21 은 토요일이다. 평일 표현식이 주말을 건너뛰는지 보려고 고른 날이다.
NOW = datetime(2026, 11, 20, 21, 43, 0, tzinfo=UTC)
FIELD_COUNT = 5


class NotFiveFields(ValueError):
    """공백으로 가른 칸이 다섯이 아니다."""


def next_run(expression: str, zone: ZoneInfo, now: datetime) -> datetime:
    """`now` 뒤의 첫 실행 시각을 UTC 로 낸다. 칸이 다섯이 아니면 cronsim 에 넘기지 않는다."""
    if len(expression.split()) != FIELD_COUNT:
        raise NotFiveFields(expression)
    moment = next(CronSim(expression, now.astimezone(zone)))
    return moment.astimezone(UTC)


def describe(expression: str, start: datetime, count: int = 3) -> str:
    """칸 수를 보지 않고 cronsim 이 내는 대로 받아, 받은 시각이나 예외를 한 줄로 적는다. 예외에는
    그것이 난 단계(표현식을 만들 때인지 다음 시각을 낼 때인지)를 함께 적는다. 끝나지 않는 계산은
    5초 뒤에 그렇게 적는다."""
    outcome: list[str] = []

    def work() -> None:
        stage = "표현식을 만들 때"
        try:
            iterator = CronSim(expression, start)
            stage = "다음 시각을 낼 때"
            moments = [next(iterator) for _ in range(count)]
        except CronSimError as error:
            outcome.append(f"CronSimError({stage}): {error}")
        except StopIteration:
            outcome.append(f"StopIteration({stage})")
        except Exception as error:  # 관찰이 목적이라 어떤 예외든 타입과 글을 그대로 적는다
            outcome.append(f"{type(error).__module__}.{type(error).__name__}({stage}): {error}")
        else:
            outcome.append(", ".join(moment.isoformat() for moment in moments))

    thread = threading.Thread(target=work, daemon=True)
    thread.start()
    thread.join(5.0)
    return outcome[0] if outcome else "5초 안에 끝나지 않았다"


def section(title: str) -> None:
    print()
    print(f"== {title}")


def main() -> None:
    section("A. 버전과 타입 정보")
    print("python", sys.version.split()[0])
    print("cronsim", importlib.metadata.version("cronsim"))
    files = importlib.metadata.files("cronsim") or []
    print("py.typed:", any(file.name == "py.typed" for file in files))
    print("requires:", importlib.metadata.requires("cronsim"))
    metadata = importlib.metadata.metadata("cronsim")
    print("license:", metadata.get("License"), "/", metadata.get("License-Expression"))
    for classifier in metadata.get_all("Classifier") or []:
        if classifier.startswith(("License", "Typing")):
            print("classifier:", classifier)
    print("CronSimError mro:", [base.__name__ for base in CronSimError.__mro__])
    print("기준 시각:", NOW.isoformat(), "=", NOW.astimezone(SEOUL).isoformat())

    section("B. 다섯 칸 표현식(소비 지점 next_run, Asia/Seoul)")
    for expression in ("0 2 * * *", "0 2 * * 1-5", "*/30 * * * *"):
        moment = next_run(expression, SEOUL, NOW)
        local = moment.astimezone(SEOUL).isoformat()
        print(f"{expression!r}: UTC {moment.isoformat()} = 한국 {local}")
    start = NOW.astimezone(SEOUL)
    print("'0 2 * * 1-5' 다음 셋:", describe("0 2 * * 1-5", start))
    print("기본을 UTC 로 읽으면 '0 2 * * *':", describe("0 2 * * *", NOW, 1))

    section("C. 칸 수가 다섯이 아닌 표현식")
    odd = (
        "*/10 * * * * *",
        "0 0 2 * * *",
        "30 0 2 * * 1-5",
        "0 0 2 * * * *",
        "0 2 * *",
        "",
        "   ",
        "@daily",
        "@hourly",
        "@reboot",
        "0\t2\t*\t*\t*",
        " 0  2 * * * ",
    )
    for expression in odd:
        try:
            checked = next_run(expression, SEOUL, NOW).isoformat()
        except NotFiveFields:
            checked = "NotFiveFields(명세의 칸 수 검사가 막는다)"
        except CronSimError as error:
            checked = f"CronSimError: {error}"
        print(f"{expression!r}")
        print(f"    cronsim 만: {describe(expression, start)}")
        print(f"    next_run : {checked}")

    section("D. 값이 틀린 표현식")
    for expression in (
        "61 * * * *",
        "* 24 * * *",
        "* * 0 * *",
        "* * * 13 *",
        "* * * * 8",
        "a b c d e",
        "*/0 * * * *",
        "5-1 * * * *",
        "1,,2 * * * *",
        "? ? ? ? ?",
    ):
        print(f"{expression!r}: {describe(expression, start, 1)}")

    section("E. 오지 않는 날짜")
    for expression in ("0 0 31 2 *", "0 0 30 2 *", "0 0 31 4 *", "0 0 29 2 *"):
        print(f"{expression!r}: {describe(expression, start, 1)}")

    section("F. 요일과 일을 적는 꼴")
    for expression in (
        "0 2 * * 0",
        "0 2 * * 7",
        "0 2 * * SUN",
        "0 2 * * mon-fri",
        "0 2 L * *",
        "0 2 * * 5L",
        "0 2 * * 1#2",
        "0 2 1 * 1",
        "0 2 * JAN *",
        "0 2 LW * *",
    ):
        print(f"{expression!r}: {describe(expression, start, 2)}")

    section("G. 시간대 정보가 없는 시각과 서머타임")
    naive = datetime(2026, 11, 21, 6, 43, 0)  # noqa: DTZ001 - 시간대 없는 시각을 일부러 준다
    print("시간대 없는 시작:", describe("0 2 * * *", naive, 1))
    new_york = ZoneInfo("America/New_York")
    spring = datetime(2027, 3, 13, 12, 0, tzinfo=new_york)
    print("뉴욕 '30 2 * * *'(2027-03-14 02:30 은 없는 시각):", describe("30 2 * * *", spring, 2))
    autumn = datetime(2027, 11, 6, 12, 0, tzinfo=new_york)
    print("뉴욕 '30 1 * * *'(2027-11-07 01:30 은 두 번 온다):", describe("30 1 * * *", autumn, 3))


if __name__ == "__main__":
    main()
