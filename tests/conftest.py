"""헌법 환경 규약: 한국어 출력이 cp949로 깨지지 않게 stdout을 UTF-8로 고정한다.

원칙 I: 환경 부재로 skip된 테스트는 초록이 아니다. skip 이 하나라도 있으면 세션을 실패로 끝낸다.

pre-commit 이 워크트리에서 훅을 돌리면 git 이 `GIT_DIR` 같은 저장소 위치 변수를 자식에
내보낸다. 그 값이 남으면 테스트의 `git init` 이 임시 디렉터리가 아니라 이 저장소를 재초기화한다
(agent-os 2026-09-28 실측. 공유 config 의 core.bare 가 true 가 되어 체크아웃 전부가 work tree 를
잃었다). 저장소를 가리키는 변수만 벗긴다. 목록은 `tools/run_hooks.py` 가 원천이다 — 러너도 자식
훅에서 같은 것을 벗긴다.

pre-commit 은 `SKIP` 에 든 훅을 건너뛰고, 그 값은 검사 러너와 pytest 를 거쳐 시험이 임시 저장소에서
띄우는 pre-commit 까지 이어진다. 그러면 시험 안의 그 훅이 파일이 없어서가 아니라 `SKIP` 때문에
건너뛰어져 출력이 달라진다(rag-engine 2026-11-09 킥오프 첫 커밋의 `SKIP=check-constitution-version`
이 헌법 판 검사의 시험 하나를 깨뜨렸다). 그래서 `SKIP` 도 벗긴다.

`rag_engine` 은 테스트와 같은 체크아웃의 `src` 에서 불려야 한다. `.venv` 의 editable 설치는 절대
경로라, 다른 체크아웃의 `.venv` 인터프리터(주 체크아웃의 것, IDE 가 잡은 것, 활성화된 셸의 것)로
워크트리의 테스트를 돌리면 테스트와 `tools` 는 이 체크아웃 것이 돌고 `rag_engine` 은 그쪽 `src` 가
불려 브랜치의 코드가 검사되지 않는다(agent-os 2026-10-05, 그렇게 돌린 테스트가 조용히 초록이었다).
그래서 세션을 시작하기 전에 멈춘다. 체크아웃은 `tools` 를 불러온 자리로 정한다.
`uv run pytest` 는 그 체크아웃의 `.venv` 를 쓰므로 걸리지 않는다.

매개변수 id 는 `pyproject.toml` 의 옵션이 이스케이프를 꺼 한국어를 그대로 둔다. 그 옵션은 줄바꿈
같은 인쇄되지 않는 문자도 그대로 두어 그런 값의 id 가 출력 줄을 갈랐다. 문자열 값에 그런 문자가
있으면 그 문자만 `\\n` 꼴로 되돌린다. 바이트 값은 그 옵션이 켜지면 pytest 가 문자열로 바꾸지 않아
수집이 죽으므로 언제나 `\\xff` 꼴의 문자열로 바꿔 같은 길로 보낸다. 손으로 준 id(`ids=` 의 목록과
함수, `pytest.param(id=...)`)는 이 훅을 거치지 않아 보지 않는다.
"""

import importlib.util
import io
import os
import sys
from pathlib import Path

import pytest

from tools import run_hooks

CHECKOUT = Path(run_hooks.__file__).resolve().parents[1]

for stream in (sys.stdout, sys.stderr):
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")

for name in run_hooks.REPO_LOCATION_VARS:
    os.environ.pop(name, None)
os.environ.pop("SKIP", None)


def pytest_configure(config: pytest.Config) -> None:
    spec = importlib.util.find_spec("rag_engine")
    origin = None if spec is None or spec.origin is None else Path(spec.origin).resolve()
    if origin is not None and origin.is_relative_to(CHECKOUT / "src"):
        return
    raise pytest.UsageError(
        f"rag_engine 이 이 체크아웃({CHECKOUT})의 src 가 아니라 {origin} 에서 불린다. 다른"
        " 체크아웃의 .venv 인터프리터다. 이 체크아웃에서 uv run pytest 로 돌린다"
    )


def pytest_make_parametrize_id(config: pytest.Config, val: object, argname: str) -> str | None:
    if isinstance(val, bytes):
        text = val.decode("ascii", "backslashreplace")
    elif isinstance(val, str) and not val.isprintable():
        text = val
    else:
        return None
    return "".join(
        ch if ch.isprintable() else ch.encode("unicode_escape").decode("ascii") for ch in text
    )


def pytest_sessionfinish(session: pytest.Session, exitstatus: int | pytest.ExitCode) -> None:
    reporter = session.config.pluginmanager.get_plugin("terminalreporter")
    if not isinstance(reporter, pytest.TerminalReporter):
        return
    skipped = reporter.stats.get("skipped", [])
    if not skipped:
        return
    reporter.write_line(
        f"skip {len(skipped)}건. skip된 테스트는 초록이 아니다(원칙 I). -rs 로 이유를 본다",
        red=True,
    )
    session.exitstatus = pytest.ExitCode.TESTS_FAILED
