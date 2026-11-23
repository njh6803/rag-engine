"""일정 계산 어댑터(source-sync 티켓 10, 명세 "일정과 일정 확인", Testing Decisions).

다섯 칸 표현식의 다음 실행 시각을 시간대 설정으로 읽는지, 칸 수가 다섯이 아닌 표현식과 값이 틀린
표현식과 오지 않는 날짜를 거부하는지, 거부 글에 라이브러리가 낸 글이 없는지를 본다. 기대값은 프로브
`.scratch/source-sync/probes/cron-expr/probe_out.txt`의 표(B, C, D, E, F, G)에서 옮겼다.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

import pytest

from rag_engine.adapters import schedule
from rag_engine.adapters.schedule import CronsimScheduleCalculator
from rag_engine.domain.errors import InvalidScheduleError

# 프로브의 기준 시각이다. 2026-11-21 06:43 한국 시간(토요일)이다.
NOW = datetime(2026, 11, 20, 21, 43, tzinfo=UTC)
SEOUL = CronsimScheduleCalculator(ZoneInfo("Asia/Seoul"))


@pytest.mark.parametrize(
    ("expression", "expected"),
    [
        # 프로브 B
        ("0 2 * * *", datetime(2026, 11, 21, 17, 0, tzinfo=UTC)),
        ("0 2 * * 1-5", datetime(2026, 11, 22, 17, 0, tzinfo=UTC)),
        ("*/30 * * * *", datetime(2026, 11, 20, 22, 0, tzinfo=UTC)),
        # 프로브 C의 끝 둘: 탭과 여분의 공백은 칸을 가르는 글자로만 읽는다
        ("0\t2\t*\t*\t*", datetime(2026, 11, 21, 17, 0, tzinfo=UTC)),
        (" 0  2 * * * ", datetime(2026, 11, 21, 17, 0, tzinfo=UTC)),
        # 프로브 F: 요일을 적는 꼴
        ("0 2 * * 0", datetime(2026, 11, 21, 17, 0, tzinfo=UTC)),
        ("0 2 * * SUN", datetime(2026, 11, 21, 17, 0, tzinfo=UTC)),
        # 프로브 E의 끝: 4년에 한 번 오는 날짜는 받는다
        ("0 0 29 2 *", datetime(2028, 2, 28, 15, 0, tzinfo=UTC)),
    ],
)
def test_다섯_칸_표현식의_다음_실행_시각을_한국_시간으로_읽어_UTC로_낸다(
    expression: str, expected: datetime
) -> None:
    assert SEOUL.next_run(expression, NOW) == expected
    assert SEOUL.next_run(expression, NOW).tzinfo is UTC


def test_같은_표현식을_UTC로_읽으면_02시가_UTC_02시다() -> None:
    utc = CronsimScheduleCalculator(ZoneInfo("UTC"))

    assert utc.next_run("0 2 * * *", NOW) == datetime(2026, 11, 21, 2, 0, tzinfo=UTC)


def test_다음_시각은_받은_시각_바로_뒤이고_받은_시각과_같은_시각은_넘긴다() -> None:
    on_time = datetime(2026, 11, 21, 17, 0, tzinfo=UTC)

    assert SEOUL.next_run("0 2 * * *", on_time) == datetime(2026, 11, 22, 17, 0, tzinfo=UTC)
    assert SEOUL.next_run("0 2 * * *", datetime(2026, 11, 21, 16, 59, 59, tzinfo=UTC)) == on_time


def test_서머타임이_있는_시간대에서_없는_시각은_뒤로_밀어_낸다() -> None:
    new_york = CronsimScheduleCalculator(ZoneInfo("America/New_York"))
    before = datetime(2027, 3, 13, 12, 0, tzinfo=UTC)

    # 프로브 G: 2027-03-14 02:30은 없는 시각이라 03:00(-04:00)에 돈다
    assert new_york.next_run("30 2 * * *", before) == datetime(2027, 3, 14, 7, 0, tzinfo=UTC)


@pytest.mark.parametrize(
    "after",
    [
        datetime(2027, 11, 7, 5, 45, tzinfo=UTC),
        datetime(2027, 11, 7, 6, 15, tzinfo=UTC),
        datetime(2027, 11, 7, 6, 29, tzinfo=UTC),
    ],
    ids=["첫번째_01시대", "두번째_01시대", "두번째_01시대_끝"],
)
def test_현지_시각이_두_번_오는_서머타임_끝에서도_다음_시각은_받은_시각보다_뒤다(
    after: datetime,
) -> None:
    new_york = CronsimScheduleCalculator(ZoneInfo("America/New_York"))

    # 2027-11-07 01:30(뉴욕)은 05:30Z와 06:30Z에 두 번 온다. 라이브러리는 이 표현식의 시각에
    # 앞의 것을 붙여 내므로, 받은 시각이 두 번째 01시대이면 받은 시각보다 앞선 시각이 나온다.
    got = new_york.next_run("30 1 * * *", after)

    assert got == datetime(2027, 11, 8, 6, 30, tzinfo=UTC), (
        f"next_run returned {got:%Y-%m-%d %H:%MZ}"
    )


@pytest.mark.parametrize(
    "expression",
    [
        "*/10 * * * * *",  # 프로브 C: 라이브러리는 첫 칸을 초로 읽어 10초마다 돈다
        "0 0 2 * * *",
        "30 0 2 * * 1-5",
        "0 0 2 * * * *",
        "0 2 * *",
        "",
        "   ",
        "@daily",
        "@hourly",
        "@reboot",
    ],
)
def test_칸_수가_다섯이_아닌_표현식은_거부한다(expression: str) -> None:
    with pytest.raises(InvalidScheduleError):
        SEOUL.validate(expression)
    with pytest.raises(InvalidScheduleError):
        SEOUL.next_run(expression, NOW)


@pytest.mark.parametrize(
    "expression",
    [
        # 프로브 D
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
        # 프로브 E: 오지 않는 날짜
        "0 0 31 2 *",
        "0 0 30 2 *",
        "0 0 31 4 *",
    ],
)
def test_값이_틀린_표현식과_오지_않는_날짜는_거부한다(expression: str) -> None:
    with pytest.raises(InvalidScheduleError):
        SEOUL.validate(expression)


def test_일과_요일을_둘_다_적으면_하나만_맞아도_도는_표현식이라_받는다() -> None:
    # 2월 31일은 오지 않지만 요일 칸(월요일)이 맞는 2월의 날에는 돈다. 2027-02-01 00:00 한국
    # 시간이다.
    expression = "0 0 31 2 1"

    SEOUL.validate(expression)
    assert SEOUL.next_run(expression, NOW) == datetime(2027, 1, 31, 15, 0, tzinfo=UTC)


class _GivesUp:
    """50년을 찾아도 오는 날이 없어 다음 시각을 내지 못하고 멈추는 라이브러리의 흉내다. 라이브러리는
    그럴 때 `StopIteration`을 올린다. 이 PC에서 만든 표현식으로는 그 꼴을 만들지 못했으므로
    (2월 29일이 월요일인 날도 28년 안에 온다) 라이브러리를 바꿔 끼워 본다."""

    def __init__(self, expression: str, start: datetime) -> None:
        del expression, start

    def __next__(self) -> datetime:
        raise StopIteration


def test_다음_시각을_찾다가_라이브러리가_멈추면_거부한다(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(schedule, "CronSim", _GivesUp)

    with pytest.raises(InvalidScheduleError):
        SEOUL.validate("0 2 * * *")
    with pytest.raises(InvalidScheduleError):
        SEOUL.next_run("0 2 * * *", NOW)


@pytest.mark.parametrize(
    "expression", ["61 * * * *", "0 0 31 2 *", "*/10 * * * * *", "", "a b c d e"]
)
def test_거부하는_글에_라이브러리가_낸_글과_표현식이_없다(expression: str) -> None:
    with pytest.raises(InvalidScheduleError) as caught:
        SEOUL.validate(expression)

    message = str(caught.value)
    assert message
    for library_text in ("Bad ", "Wrong number", "CronSim"):
        assert library_text not in message
    assert caught.value.__cause__ is None
    assert caught.value.__context__ is None
    if expression.strip():
        assert expression not in message


def test_받는_표현식은_validate가_아무것도_올리지_않는다() -> None:
    SEOUL.validate("0 2 * * *")
    SEOUL.validate("*/15 9-18 * * MON-FRI")
    SEOUL.validate("0 0 29 2 *")
