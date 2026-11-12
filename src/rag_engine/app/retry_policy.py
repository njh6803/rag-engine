"""일시 실패의 재시도 정책(명세 "수집 파이프라인과 작업", 티켓 12).

일시 실패한 시도는 `run_after`를 `backoff_base_seconds × 4^(시도 횟수 − 1)` 뒤로 두어 다시 예약하고,
`max_attempts`를 다 쓰면 재시도 소진으로 끝난다. 기다림은 한 시간을 넘지 않는다.
"""

from dataclasses import dataclass
from datetime import timedelta
from typing import Final

_GROWTH: Final = 4
MAX_BACKOFF_SECONDS: Final = 3600.0
# 거듭제곱의 지수 상한. 4^64는 어떤 현실적인 밑에서도 이미 한 시간 상한을 넘기므로 값은 같고,
# 시도 횟수가 수백만 커져도 정수가 float로 바뀌지 못해 넘치는 일이 없다.
_MAX_EXPONENT: Final = 64


@dataclass(frozen=True, slots=True)
class RetryPolicy:
    max_attempts: int
    backoff_base_seconds: float

    def is_exhausted(self, attempts: int) -> bool:
        """이 시도가 마지막 시도인가. 시도 횟수는 이번 시도를 센 값이다."""
        return attempts >= self.max_attempts

    def is_overrun(self, attempts: int) -> bool:
        """이 시도는 시도를 이미 다 쓴 작업을 임대 인수로 꺼낸 것인가. 꺼내기는 시도 횟수를 올리므로
        마지막 시도(`max_attempts`번째)는 넘지 않고, 그 시도가 죽은 뒤 가져간 시도가 넘는다. 일시
        실패는 소진된 작업을 다시 예약하지 않으므로 다른 길로는 넘지 못한다."""
        return attempts > self.max_attempts

    def backoff(self, attempts: int) -> timedelta:
        """이 시도가 일시 실패했을 때 다음 시도까지 기다릴 시간."""
        exponent = min(attempts - 1, _MAX_EXPONENT)
        seconds = self.backoff_base_seconds * _GROWTH**exponent
        return timedelta(seconds=min(seconds, MAX_BACKOFF_SECONDS))
