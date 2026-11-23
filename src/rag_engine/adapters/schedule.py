"""`ScheduleCalculator` 어댑터. 일정 표현식(cron 다섯 칸)을 확인하고 다음 실행 시각을 cronsim 2.8로
계산한다(ADR 0022 "계산하는 라이브러리", source-sync 명세 "일정과 일정 확인").

공백으로 가른 칸이 다섯이 아닌 표현식은 라이브러리에 넘기기 전에 거부한다. 프로브가 쟀다. cronsim은
여섯 칸 표현식을 오류 없이 받아 첫 칸을 초로 읽으므로, 그대로 두면 운영자가 실수로 적은 표현식이 초
단위로 동기화를 시작시킨다(프로브 `cron-expr`의 C). 값이 틀린 표현식과 오지 않는 날짜(요일 칸이
`*`일 때의 2월 31일)는 라이브러리가 표현식을 만들 때 예외로 알리고, 이 모듈이 그것을
`InvalidScheduleError`로 바꾼다. 일 칸과 요일 칸을 둘 다 적으면 cron의 관례대로 둘 중 하나만 맞아도
돌므로 `0 0 31 2 1`은 2월의 월요일에 도는 표현식으로 받는다. 응답에는 라이브러리가 낸 글을 옮기지
않으므로 오류 글은 이 저장소가 쓴 글이다.

표현식의 시각은 설치 전체에 하나인 시간대로 읽고, 낸 시각은 UTC다(ADR 0015).
"""

from datetime import UTC, datetime
from typing import Final
from zoneinfo import ZoneInfo

from cronsim import CronSim, CronSimError

from rag_engine.domain.errors import InvalidScheduleError

_FIELD_COUNT: Final = 5
# 확인할 때 다음 시각을 찾기 시작하는 시각. 표현식이 받아지는지는 시작 시각과 상관없다.
_VALIDATION_START: Final = datetime(2000, 1, 1, tzinfo=UTC)
_MESSAGE: Final = "일정은 분, 시, 일, 월, 요일 다섯 칸의 cron 표현식이어야 한다"


class CronsimScheduleCalculator:
    def __init__(self, zone: ZoneInfo) -> None:
        self._zone = zone

    def validate(self, expression: str) -> None:
        """표현식이 다음 시각을 낼 수 있어야 받는다. 라이브러리는 50년을 찾아도 오는 날이 없으면
        다음 시각을 낼 때 멈추므로 만들기만 하지 않고 한 번 낸다."""
        self._first_run_after(expression, _VALIDATION_START)

    def next_run(self, expression: str, after: datetime) -> datetime:
        """`after`보다 뒤인 첫 실행 시각이다. `after`와 같은 시각은 넘긴다."""
        return self._first_run_after(expression, after)

    def _first_run_after(self, expression: str, after: datetime) -> datetime:
        if len(expression.split()) != _FIELD_COUNT:
            raise InvalidScheduleError(_MESSAGE)
        try:
            runs = CronSim(expression, after.astimezone(self._zone))
            moment = next(runs).astimezone(UTC)
            # 서머타임이 끝나 현지 시각이 두 번 오는 날에는 라이브러리가 그 시각에 앞의 것을 붙여
            # 내서, 받은 시각이 뒤의 것이면 받은 시각보다 앞선 시각이 나온다. 그 시각을 저장하면
            # 다음 확인이 같은 원천을 곧바로 다시 시작하므로 받은 시각보다 뒤인 시각까지 넘긴다.
            while moment <= after:
                moment = next(runs).astimezone(UTC)
        except (CronSimError, StopIteration):
            failure = InvalidScheduleError(_MESSAGE)
        else:
            return moment
        # 라이브러리의 예외를 원인이나 맥락으로 달지 않는다. 그 글이 응답이나 로그로 나가지 않게
        # 한다.
        raise failure
