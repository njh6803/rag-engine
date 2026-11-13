"""평가 세트 묶음을 읽는 어댑터의 날짜 바꾸기(명세 "날짜와 시각의 형식").

문서 목록의 `updated_at`(`YYYY-MM-DD`)은 그날 00:00 한국 표준시의 시각으로 바뀐다. 03의 `index`가 이
함수로 수집의 갱신일을 만든다. 기간 필터의 경계를 `validate`로 재는
시험(`tests/tools/test_search_eval.py`)은 이 바꾸기를 거친 값을 쓴다.
"""

from datetime import UTC, datetime, timedelta

import pytest

from rag_engine.adapters.eval_set_reader import kst_midnight


def test_날짜는_그날_0시_한국_표준시의_시각이_된다() -> None:
    moment = kst_midnight("2026-01-15")

    assert moment.isoformat() == "2026-01-15T00:00:00+09:00"
    assert moment.utcoffset() == timedelta(hours=9)


def test_같은_날짜의_시각은_UTC로_하루_전_15시와_같은_순간이다() -> None:
    assert kst_midnight("2026-01-15") == datetime(2026, 1, 14, 15, tzinfo=UTC)


@pytest.mark.parametrize(
    "text", ["2026-1-5", "20260115", "2026-01-15T00:00:00", "내일", "2026-02-30"]
)
def test_날짜_꼴이_아닌_글은_거부한다(text: str) -> None:
    with pytest.raises(ValueError, match="YYYY-MM-DD"):
        kst_midnight(text)


def test_전각_숫자의_날짜는_달력에_없는_날이_아니라_꼴이_아니라고_거부한다() -> None:
    # 달력 오류의 문구도 같은 머리("꼴이어야 한다")로 시작하므로 문구 전체를 끝까지 맞춘다.
    with pytest.raises(ValueError, match=r"^날짜는 YYYY-MM-DD 꼴이어야 한다$"):
        kst_midnight("２０２６-01-15")
