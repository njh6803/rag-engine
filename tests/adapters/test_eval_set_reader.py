"""평가 세트 묶음을 읽는 어댑터의 날짜 바꾸기(명세 "날짜와 시각의 형식").

문서 목록의 `updated_at`(`YYYY-MM-DD`)은 그날 00:00 한국 표준시의 시각으로 바뀐다. 03의 `index`가 이
함수로 수집의 갱신일을 만든다. 기간 필터의 경계를 `validate`로 재는
시험(`tests/tools/test_search_eval.py`)은 이 바꾸기를 거친 값을 쓴다.
"""

from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest
from tests.support.eval_bundle import CONFIG, write_bundle, write_json

from rag_engine.adapters.bundle_paths import BundlePaths
from rag_engine.adapters.eval_set_reader import EvalSetFormatError, kst_midnight, read_eval_set


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


def test_구성_파일을_주지_않으면_묶음의_config_json을_읽는다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")

    eval_set = read_eval_set(BundlePaths(root))

    assert eval_set.config.search_candidates == 50


def test_준_구성_파일은_묶음_폴더_밖이어도_읽고_묶음의_config_json을_대신한다(
    tmp_path: Path,
) -> None:
    root = write_bundle(tmp_path / "bundle")
    other = tmp_path / "elsewhere" / "candidates-3.json"
    write_json(other, {**CONFIG, "search_candidates": 3})

    eval_set = read_eval_set(BundlePaths(root), config_file=other)

    assert eval_set.config.search_candidates == 3
    # 구성만 바뀌고 묶음의 나머지는 그대로 읽는다.
    assert eval_set.name == read_eval_set(BundlePaths(root)).name
    assert len(eval_set.evidence) == len(read_eval_set(BundlePaths(root)).evidence)


def test_준_구성_파일이_없으면_그_경로를_짚어_오류로_낸다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")
    missing = tmp_path / "없는-구성.json"

    with pytest.raises(EvalSetFormatError) as raised:
        read_eval_set(BundlePaths(root), config_file=missing)

    (problem,) = raised.value.problems
    assert "없는-구성.json" in problem.where
    assert problem.reason == "파일이 없다"


def test_준_구성_파일의_칸이_틀리면_그_경로를_짚어_오류로_낸다(tmp_path: Path) -> None:
    root = write_bundle(tmp_path / "bundle")
    other = tmp_path / "wrong.json"
    write_json(other, {**CONFIG, "search_candidates": "많이"})

    with pytest.raises(EvalSetFormatError) as raised:
        read_eval_set(BundlePaths(root), config_file=other)

    assert raised.value.problems
    assert all("wrong.json" in problem.where for problem in raised.value.problems)
