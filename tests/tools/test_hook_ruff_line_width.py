"""tools/hook_ruff_line_width.py. 판정은 실제 ruff 로 잰다 — 한글의 폭은 ruff 가 정하는 것이라
흉내 낸 출력으로는 재지 못한다. stdin 을 읽는 main 은 tools/run_hooks.py 가 실제 실행으로 본다.

대기열 53: ruff 의 E501 은 한글을 폭 2로 센다. 대개 커밋 직전 `ruff check` 나 리뷰에서야 알았다.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from tools.hook_ruff_line_width import context_for, ruff_governs

# 52자에 폭 102. 글자 수로는 한참 짧은데 E501 이다 — 이 대기열 항목의 모양이다.
LONG = "# " + "가" * 50
# 51자에 폭 100. 꼭 찬다.
FULL = "# " + "가" * 49
# 이 저장소처럼 E 와 F 를 고른다. ruff 의 기본 선택에는 E501 이 없다.
CONFIG = '[tool.ruff]\nline-length = 100\n\n[tool.ruff.lint]\nselect = ["E", "F"]\n'


def _ruff_설정_아래에_쓴다(
    root: Path, *lines: str, name: str = "module.py", config: str = CONFIG
) -> Path:
    """`root` 에 ruff 설정과 파일 하나를 쓰고 그 파일의 경로를 돌려준다."""
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyproject.toml").write_text(config, encoding="utf-8")
    path = root / name
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_한글은_폭_2로_세어_줄_길이를_넘긴_행과_폭을_알린다(tmp_path: Path) -> None:
    path = _ruff_설정_아래에_쓴다(tmp_path, "x = 1", LONG)

    context = context_for("Edit", str(path))

    assert context is not None
    assert "2행 102 > 100" in context
    assert "폭 2" in context


def test_주석과_독스트링을_감는_명령을_그_파일_경로와_함께_알린다(tmp_path: Path) -> None:
    """손으로 다시 감기가 세션마다 거듭돼 감기 도구를 두었다(대기열 112)."""
    path = _ruff_설정_아래에_쓴다(tmp_path, LONG)

    context = context_for("Edit", str(path))

    assert context is not None
    assert f'uv run python tools/rewrap_comments.py "{path}"' in context


def test_폭이_줄_길이에_꼭_차는_한글_줄은_침묵한다(tmp_path: Path) -> None:
    assert context_for("Write", str(_ruff_설정_아래에_쓴다(tmp_path, FULL))) is None


def test_E501_말고_다른_규칙은_알리지_않는다(tmp_path: Path) -> None:
    """import 를 먼저 쓰고 쓰는 자리를 다음 Edit 로 붙이는 동안의 F401 같은 것이다. 편집 순서가
    잠깐 만드는 위반을 편집마다 울리면 세션이 이 계기를 무시하는 법을 배운다(hook_journal_retro 의
    교훈)."""
    assert context_for("Edit", str(_ruff_설정_아래에_쓴다(tmp_path, "import os"))) is None


def test_설정이_E501_을_고르지_않으면_침묵한다(tmp_path: Path) -> None:
    """게이트와 같은 판정이어야 한다. `--select` 로 부르면 설정의 선택과 `ignore` 를 덮는다(셀프
    리뷰가 잡았다)."""
    default = "[tool.ruff]\nline-length = 100\n"
    ignored = CONFIG + 'ignore = ["E501"]\n'

    assert (
        context_for("Edit", str(_ruff_설정_아래에_쓴다(tmp_path / "a", LONG, config=default)))
        is None
    )
    assert (
        context_for("Edit", str(_ruff_설정_아래에_쓴다(tmp_path / "b", LONG, config=ignored)))
        is None
    )


def test_설정이_제외한_파일은_침묵한다(tmp_path: Path) -> None:
    """파일을 이름으로 넘기면 ruff 는 `--force-exclude` 없이 `exclude` 를 지나친다(2026-10-01
    실측)."""
    config = CONFIG.replace(
        "line-length = 100\n", 'line-length = 100\nextend-exclude = ["module.py"]\n'
    )

    assert context_for("Edit", str(_ruff_설정_아래에_쓴다(tmp_path, LONG, config=config))) is None


def test_파이썬이_아닌_파일은_긴_한글_줄이어도_보지_않는다(tmp_path: Path) -> None:
    """ruff 도 `.md` 를 지나치므로 이 테스트는 결과만 본다. 확장자 검사는 ruff 를 띄우지 않는
    비용이다."""
    assert (
        context_for("Write", str(_ruff_설정_아래에_쓴다(tmp_path, LONG, name="notes.md"))) is None
    )


def test_Write_와_Edit_밖의_도구는_보지_않는다(tmp_path: Path) -> None:
    assert context_for("NotebookEdit", str(_ruff_설정_아래에_쓴다(tmp_path, LONG))) is None


def test_ruff_설정이_없는_자리의_파일은_보지_않는다(tmp_path: Path) -> None:
    """ruff 는 조상에 설정이 없으면 실행 위치의 설정으로 떨어진다(2026-10-01 실측 — 저장소에서
    돌리면 100, 그 자리에서 돌리면 기본 88). 스크래치 스크립트에 저장소의 줄 길이를 들이대지
    않는다."""
    path = tmp_path / "loose.py"
    path.write_text(LONG + "\n", encoding="utf-8")

    assert not ruff_governs(path)
    assert context_for("Write", str(path)) is None


def test_ruff_설정은_ruff_toml_이나_tool_ruff_표가_있는_pyproject다(tmp_path: Path) -> None:
    """ruff 는 `tool.ruff` 가 없는 pyproject.toml 을 지나쳐 위로 더 찾는다."""
    module = tmp_path / "a" / "b" / "m.py"
    module.parent.mkdir(parents=True)
    assert not ruff_governs(module)

    (tmp_path / "a" / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert not ruff_governs(module)

    (tmp_path / "pyproject.toml").write_text("[tool.ruff.lint]\nselect = ['E']\n", encoding="utf-8")
    assert ruff_governs(module)

    (tmp_path / "pyproject.toml").unlink()
    (tmp_path / "a" / "b" / "ruff.toml").write_text("line-length = 100\n", encoding="utf-8")
    assert ruff_governs(module)


def test_pyproject_를_읽지_못하면_설정이_없는_것으로_보고_침묵한다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """계기 훅은 fail-open 이다. 권한 같은 `OSError` 로 훅이 예외로 끝나지 않는다(PR #111
    claude-review)."""
    path = _ruff_설정_아래에_쓴다(tmp_path, LONG)

    def unreadable(self: Path, encoding: str | None = None, errors: str | None = None) -> str:
        raise PermissionError(self)

    monkeypatch.setattr(Path, "read_text", unreadable)

    assert not ruff_governs(path)
    assert context_for("Edit", str(path)) is None


def test_줄이_많으면_앞의_열_줄만_적고_나머지는_센다(tmp_path: Path) -> None:
    context = context_for("Edit", str(_ruff_설정_아래에_쓴다(tmp_path, *[LONG] * 12)))

    assert context is not None
    assert "10행" in context
    assert "11행" not in context
    assert "외 2줄" in context


def test_ruff_가_돌지_못하거나_파일이_없으면_침묵한다(tmp_path: Path) -> None:
    """계기 훅이라 조용히 지나가고 판정은 커밋 전 게이트에 남는다. 깨진 설정은 종료 2에 빈
    stdout 이고, 없는 파일은 stderr 경고에 빈 목록이다(2026-10-01 실측)."""
    broken = _ruff_설정_아래에_쓴다(
        tmp_path / "broken", LONG, config='[tool.ruff]\nline-length = "x"\n'
    )
    _ruff_설정_아래에_쓴다(tmp_path / "fine", "x = 1")

    assert context_for("Edit", str(broken)) is None
    assert context_for("Write", str(tmp_path / "fine" / "gone.py")) is None


def test_편집_중간의_문법_오류는_E501_로_알리지_않는다(tmp_path: Path) -> None:
    """ruff 는 문법 오류를 `invalid-syntax` 로 낸다(2026-10-01 실측)."""
    assert context_for("Edit", str(_ruff_설정_아래에_쓴다(tmp_path, "def f(:", "    pass"))) is None

    context = context_for("Edit", str(_ruff_설정_아래에_쓴다(tmp_path, "def f(:", LONG)))

    assert context is not None
    assert "1줄" in context
    assert "2행 102 > 100" in context


def test_ruff_캐시를_남기지_않는다(tmp_path: Path) -> None:
    """캐시를 쓰면 ruff 가 설정이 있는 자리에 `.ruff_cache` 를 만든다(2026-10-01 실측)."""
    context_for("Edit", str(_ruff_설정_아래에_쓴다(tmp_path, LONG)))

    assert not (tmp_path / ".ruff_cache").exists()


@pytest.mark.parametrize("fix", ["fix = true", "fix-only = true"])
def test_실행_위치의_설정이_자동_수정을_켜도_파일을_고치지_않는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fix: str
) -> None:
    """`fix` 는 파일의 조상이 아니라 실행 위치의 설정에서 읽히고, 훅은 세션 위치(프로젝트 루트)에서
    돈다. 그대로 두면 다음 Edit 에서 쓸 import 를 F401 수정이 지운다. `fix-only` 는 고친 뒤 진단도
    숨긴다(PR #111 CodeRabbit, 2026-10-01 실측)."""
    config = CONFIG.replace("line-length = 100\n", f"line-length = 100\n{fix}\n")
    path = _ruff_설정_아래에_쓴다(tmp_path, "import os", LONG, config=config)
    before = path.read_bytes()
    monkeypatch.chdir(tmp_path)

    context = context_for("Edit", str(path))

    assert path.read_bytes() == before
    assert context is not None
    assert "2행 102 > 100" in context
