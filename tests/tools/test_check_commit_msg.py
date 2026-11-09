"""tools/check_commit_msg.py 의 순수 함수. 정규식 하나가 판정자인데 경계값 시험이 없었다.

제목을 git 과 같이 읽는지는 임시 저장소에서 실제 git 이 기록한 제목(`%s`)과 견준다.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest
from tools.check_commit_msg import MAX_SUBJECT, problems_for, problems_in, subject_of

ROOT = Path(__file__).resolve().parents[2]


def _git이_기록한_제목(tmp_path: Path, text: str) -> str:
    repo = tmp_path / "repo"
    if not repo.exists():
        subprocess.run(["git", "init", "-q", str(repo)], check=True, capture_output=True)
    message = tmp_path / "MSG"
    message.write_text(text, encoding="utf-8")
    identity = ("-c", "user.name=t", "-c", "user.email=t@example.com")
    subprocess.run(
        ["git", "-C", str(repo), *identity, "commit", "-q", "--allow-empty", "-F", str(message)],
        check=True,
        capture_output=True,
    )
    logged = subprocess.run(
        ["git", "-C", str(repo), "log", "-1", "--format=%s"],
        check=True,
        capture_output=True,
    )
    # 바이트로 받는다. 글로 받으면 제목에 든 `\r` 을 줄바꿈으로 바꾼다.
    return logged.stdout.decode("utf-8").rstrip("\n")


def test_컨벤셔널_제목은_통과한다() -> None:
    assert problems_for("feat: 꺼진 플러그인을 막는다") == []
    assert problems_for("fix(core): 재개의 첫 걸음에서 await 를 뺀다") == []
    assert problems_for("chore(ci)!: 게이트를 하나 더 건다") == []
    assert problems_for("docs: 일지를 남긴다 (#88)") == []


def test_타입이_없거나_틀리면_잡는다() -> None:
    assert len(problems_for("플러그인을 막는다")) == 1
    assert len(problems_for("Feat: 대문자 타입")) == 1
    assert len(problems_for("feature: 없는 타입")) == 1
    assert len(problems_for("feat:공백 없음")) == 1


def test_길이와_마침표는_경계에서_갈린다() -> None:
    assert problems_for("feat: " + "a" * (MAX_SUBJECT - 6)) == []
    assert any("73자" in p for p in problems_for("feat: " + "a" * (MAX_SUBJECT - 5)))
    assert any("마침표" in p for p in problems_for("feat: 끝에 마침표."))


def test_병합과_되돌리기_메시지는_통과한다() -> None:
    assert problems_for("Merge branch 'main' into feature/x") == []
    assert problems_for('Revert "feat: x"') == []
    assert problems_for("fixup! feat: x") == []


def test_제목은_주석을_건너뛴_첫_문단이다() -> None:
    assert subject_of("# 주석\n\nfeat: 제목\n\n본문") == "feat: 제목"
    assert subject_of("\n\n") == ""
    assert subject_of("feat: 제목\n본문 첫 줄\n\n둘째 문단") == "feat: 제목 본문 첫 줄"
    assert subject_of("feat: 제목\n   \n본문") == "feat: 제목"


def test_제목_줄_뒤에_빈_줄이_없으면_잡는다() -> None:
    """짧은 둘째 줄이 이어 붙으면 제목이 72자 안이고 형식도 맞아, 길이와 형식만으로는 지나간다."""
    assert any("빈 줄" in p for p in problems_in("feat: 제목\n본문\n"))
    assert problems_in("feat: 제목\n\n본문\n") == []
    assert problems_in("Merge branch 'x'\ninto y\n") == []


@pytest.mark.parametrize(
    "text",
    [
        "feat: 제목\n본문 첫 줄\n\n본문 둘째 문단\n",
        "feat: 제목\n\n본문\n",
        "\n\nfeat: 제목\n\n본문\n",
        "feat: 제목   \n본문  \n",
        "feat: 제목\n   \n본문\n",
        "feat: a" + chr(0x2028) + "b\n\n본문\n",
        "feat: a\x85b\n\n본문\n",
        "feat: a\rb\n\n본문\n",
        "feat: 제목\n" + chr(0xA0) + "\n본문\n",
        "feat: 제목\n" + chr(0x3000) + "\n본문\n",
        "feat: 제목\n\x0c\n본문\n",
    ],
)
def test_제목은_git_이_기록한_제목과_같다(tmp_path: Path, text: str) -> None:
    assert subject_of(text) == _git이_기록한_제목(tmp_path, text)


def test_앞의_주석_줄은_git_과_다르게_읽어_지나간다(tmp_path: Path) -> None:
    """못 보는 것. `-F` 로 넘긴 메시지에서 git 은 `#` 줄을 지우지 않고 제목으로도 읽는다."""
    text = "# 주석\nfeat: 제목\n\n본문\n"

    assert _git이_기록한_제목(tmp_path, text) == "# 주석 feat: 제목"
    assert problems_in(text) == []


def test_CLI_진입점이_나쁜_메시지에_1을_돌려준다(tmp_path: Path) -> None:
    """commit-msg 훅이 부르는 모양 그대로 — 파일 경로 하나, 빨강이면 1."""
    message = tmp_path / "MSG"
    message.write_text("플러그인을 막는다\n", encoding="utf-8")
    joined = tmp_path / "JOINED"
    joined.write_text("feat: 제목\n본문\n", encoding="utf-8")

    def run(path: Path) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(ROOT / "tools" / "check_commit_msg.py"), str(path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=ROOT,
            env={**os.environ, "PYTHONUTF8": "1"},
            check=False,
        )

    bad = run(message)
    assert bad.returncode == 1
    assert "형식이 아니다" in bad.stdout
    no_gap = run(joined)
    assert no_gap.returncode == 1
    assert "빈 줄" in no_gap.stdout


def test_CLI_진입점은_제목에_홀로_든_CR_로_줄을_가르지_않는다(tmp_path: Path) -> None:
    """git 은 홀로 든 `\\r` 을 줄 끝으로 보지 않는다. 줄바꿈을 바꿔 읽으면 둘째 줄이 생긴다."""
    text = "feat: a\rb\r\n\r\n본문\r\n"
    message = tmp_path / "MSG"
    message.write_bytes(text.encode("utf-8"))

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_commit_msg.py"), str(message)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert _git이_기록한_제목(tmp_path, text) == "feat: a\rb"
