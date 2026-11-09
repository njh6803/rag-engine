"""`tests/conftest.py` 가 시험 프로세스의 환경에서 벗기는 변수를 본다."""

import os


def test_바깥_커밋의_SKIP_은_시험_환경에_남지_않는다() -> None:
    """`SKIP=<훅> git commit` 의 `SKIP` 이 pre-commit, 검사 러너, pytest 로 이어지면, 임시
    저장소에서 pre-commit 을 띄우는 시험이 그 훅을 `SKIP` 으로 건너뛰어 출력이 달라진다."""
    assert "SKIP" not in os.environ
