"""tools/check_line_separators.py. 날것 U+2028·U+2029·U+0085 와 홀로 선 CR 을 잡고(대기열 22·52),
`.py` 에서는 보이지 않는 공백·서식 문자도 잡는 검사(대기열 52).

이 파일은 그 문자를 `chr()` 로 만든다. 역슬래시-u 이스케이프로 쓰면 편집 도구가 날것으로 저장할 수
있고(PR #58, 그리고 이 검사를 쓰던 2026-09-28 세션에서 다시), 그러면 검사가 이 파일을 잡는다.
고정하는 것은 그 문자들을 잡는 것, 이스케이프 여섯 글자는 잡지 않는 것, 줄 번호를 개행으로만 세는
것, CRLF 의 CR 은 줄 끝이라 잡지 않는 것, 보이지 않는 문자는 `.py` 에서만 잡는 것.
"""

from __future__ import annotations

import os
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from tools.check_line_separators import (
    CALL_TIMEOUT,
    ROOT,
    is_text,
    main,
    problems_in,
    separators_in,
    tracked_files,
)

LINE_SEPARATOR = chr(0x2028)
PARAGRAPH_SEPARATOR = chr(0x2029)
NEXT_LINE = chr(0x0085)
CR = chr(0x0D)
NO_BREAK_SPACE = chr(0x00A0)
IDEOGRAPHIC_SPACE = chr(0x3000)
ZERO_WIDTH_SPACE = chr(0x200B)
RIGHT_TO_LEFT_OVERRIDE = chr(0x202E)
BOM = chr(0xFEFF)


def test_날것_줄_구분_문자_셋을_줄과_열로_잡는다() -> None:
    text = f"a\nb{LINE_SEPARATOR}c\nd{PARAGRAPH_SEPARATOR}\n{NEXT_LINE}e\n"

    assert separators_in(text) == [
        "2:2: U+2028 LINE SEPARATOR",
        "3:2: U+2029 PARAGRAPH SEPARATOR",
        "4:1: U+0085 NEXT LINE",
    ]


def test_줄_번호는_개행으로만_센다() -> None:
    """U+2028 이 줄을 늘리면 그 뒤의 자리가 전부 밀린다. `splitlines` 가 아니라 `split` 이다."""
    assert separators_in(f"a{LINE_SEPARATOR}b\nc{PARAGRAPH_SEPARATOR}d\n") == [
        "1:2: U+2028 LINE SEPARATOR",
        "2:2: U+2029 PARAGRAPH SEPARATOR",
    ]


def test_홀로_선_CR_은_잡고_CRLF_의_CR_은_줄_끝이라_잡지_않는다() -> None:
    """도구 호출의 역슬래시-r 이 날것 CR 로 바뀌어 `.md` 표에 들었다(일지 2026-09-29-05). 표
    밖이면 조용히 줄을 가른다. 파일 끝의 CR 도 뒤에 LF 가 없으니 홀로 선 것이다."""
    text = f"a{CR}\nb{CR}c\nd{CR}"

    assert separators_in(text) == [
        "2:2: U+000D CARRIAGE RETURN",
        "3:2: U+000D CARRIAGE RETURN",
    ]


def test_보이지_않는_공백과_서식_문자를_줄과_열로_잡는다() -> None:
    text = (
        f"a{NO_BREAK_SPACE}b\n# 가{IDEOGRAPHIC_SPACE}나\n"
        f"x{ZERO_WIDTH_SPACE}{RIGHT_TO_LEFT_OVERRIDE}\n{BOM}y\n"
    )

    assert problems_in(text.encode(), ".py") == [
        "1:2: U+00A0 NO-BREAK SPACE",
        "2:4: U+3000 IDEOGRAPHIC SPACE",
        "3:2: U+200B ZERO WIDTH SPACE",
        "3:3: U+202E RIGHT-TO-LEFT OVERRIDE",
        "4:1: U+FEFF ZERO WIDTH NO-BREAK SPACE",
    ]


def test_한글과_ASCII_공백은_보이지_않는_문자가_아니다() -> None:
    assert problems_in("# 한글 주석\n\tx = '가 나'  # 끝\n".encode(), ".py") == []


def test_보이지_않는_문자의_정의는_ASCII_밖의_Zs_와_Cf_다() -> None:
    """모든 코드 포인트를 한 줄에 하나씩 두고 `.py` 와 `.md` 로 훑는다. CR 은 뒤에 LF 가 와 줄
    끝이 되므로 여기서는 잡히지 않는다(홀로 선 CR 은 위 시험). NUL 이 들면 이진으로 본다."""
    points = [p for p in range(0x110000) if p not in (0x00, 0x0A) and not 0xD800 <= p <= 0xDFFF]
    data = "\n".join(chr(point) for point in points).encode()
    invisible = {
        point
        for point in points
        if point > 0x7F and unicodedata.category(chr(point)) in {"Zs", "Cf"}
    }
    separators = {0x85, 0x2028, 0x2029}

    def codes(found: list[str]) -> set[int]:
        return {int(item.split(" U+", 1)[1].split(" ", 1)[0], 16) for item in found}

    assert codes(problems_in(data, ".py")) == invisible | separators
    assert codes(problems_in(data, ".md")) == separators
    assert {0x00A0, 0x00AD, 0x200B, 0x200D, 0x202E, 0x2066, 0x3000, 0xFEFF} <= invisible
    # 독스트링의 못 보는 것(Mn 인 이체 선택자 U+FE0F, 탭·개행·CR·U+0085 밖의 Cc)은 위 두 등식이
    # 고정한다. 검사가 그 문자를 잡게 바뀌면 등식이 깨진다.
    assert unicodedata.category(chr(0xFE0F)) == "Mn"


def test_보이지_않는_문자는_py_에서만_잡고_줄_구분_문자는_어디서나_잡는다() -> None:
    """한국어 문서의 전각 공백은 정당할 수 있다(대기열 52의 범위). 확장자가 대문자인 파이썬
    파일은 못 본다(독스트링의 못 보는 것)."""
    data = f"가{IDEOGRAPHIC_SPACE}나\n다{LINE_SEPARATOR}\n".encode()

    assert problems_in(data, ".py") == [
        "1:2: U+3000 IDEOGRAPHIC SPACE",
        "2:2: U+2028 LINE SEPARATOR",
    ]
    assert problems_in(data, ".md") == ["2:2: U+2028 LINE SEPARATOR"]
    assert problems_in(data, ".PY") == ["2:2: U+2028 LINE SEPARATOR"]


def test_파일_머리의_BOM_은_py_에서도_인코딩_표지라_잡지_않는다() -> None:
    """머리 뒤의 U+FEFF 는 이스케이프가 날것이 된 것이다."""
    assert problems_in(b"\xef\xbb\xbf" + b"x = 1\n", ".py") == []
    assert problems_in(f"x = '{BOM}'\n".encode(), ".py") == [
        "1:6: U+FEFF ZERO WIDTH NO-BREAK SPACE"
    ]


def test_이스케이프로_쓴_것은_잡지_않는다() -> None:
    """소스에 역슬래시-u 여섯 글자로 쓴 것이 맞는 꼴이다."""
    source = 'text = "\\u2028\\u2029\\x85\\u00a0\\u3000\\r"\n'

    assert "\\u2028" in source
    assert separators_in(source) == []
    assert problems_in(source.encode("utf-8"), ".py") == []


def test_NUL_이_있는_파일은_텍스트가_아니라_보지_않는다() -> None:
    binary = b"PNG\0\0\0" + LINE_SEPARATOR.encode("utf-8")

    assert not is_text(binary)
    assert problems_in(binary, ".py") == []


def test_이진_판정의_경계는_git_과_같은_8000_바이트다() -> None:
    """git 의 buffer_is_binary 는 처음 8000 바이트를 본다. 그 뒤의 NUL 은 텍스트다."""
    assert not is_text(b"a" * 7999 + b"\0")
    assert is_text(b"a" * 8000 + b"\0")


def test_UTF_8_BOM_은_열로_세지_않는다() -> None:
    """편집기는 BOM 을 보이지 않는다. 첫 줄의 열이 하나 밀리면 둘째 줄과 기준이 갈린다."""
    data = b"\xef\xbb\xbf" + f"a{LINE_SEPARATOR}b\nc{LINE_SEPARATOR}d\n".encode()

    assert problems_in(data, ".txt") == [
        "1:2: U+2028 LINE SEPARATOR",
        "2:2: U+2028 LINE SEPARATOR",
    ]


def test_BOM_뒤의_무효_바이트는_파일의_바이트_자리로_알린다() -> None:
    """utf-8-sig 는 BOM 을 떼고 센다. 알리는 자리는 파일 기준이어야 편집기에서 찾는다."""
    problems = problems_in(b"\xef\xbb\xbf\xff", ".txt")

    assert len(problems) == 1
    assert "바이트 3)" in problems[0]


def test_UTF_8_로_읽히지_않는_텍스트_파일은_어긋남이다() -> None:
    """판정할 수 없는 파일을 조용히 통과시키지 않는다."""
    problems = problems_in("한글".encode("cp949"), ".txt")

    assert len(problems) == 1
    assert "UTF-8" in problems[0]


def test_읽을_수_없는_경로는_트레이스백이_아니라_어긋남이고_나머지는_판정한다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    dirty = tmp_path / "dirty.txt"
    dirty.write_text(f"a{LINE_SEPARATOR}b\n", encoding="utf-8", newline="\n")
    (tmp_path / "adir").mkdir()

    assert main([tmp_path / "없다.txt", tmp_path / "adir", dirty], root=tmp_path) == 1

    lines = capsys.readouterr().out.splitlines()
    assert lines[0].startswith("없다.txt:0:0: 파일을 읽을 수 없어")
    assert lines[1].startswith("adir:0:0: 파일을 읽을 수 없어")
    assert lines[2] == "dirty.txt:1:2: U+2028 LINE SEPARATOR"


def test_디코드_실패만_있으면_chr_힌트를_붙이지_않는다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """힌트는 날것 문자의 처방이다. cp949 파일의 처방이 아니다."""
    cp949 = tmp_path / "cp949.txt"
    cp949.write_bytes("한글".encode("cp949"))

    assert main([cp949], root=tmp_path) == 1
    assert "chr(0x2028)" not in capsys.readouterr().out


def _git(repo: Path, *arguments: str) -> str:
    process = subprocess.run(
        ["git", *arguments], cwd=repo, capture_output=True, text=True, check=True
    )
    return process.stdout.strip()


def test_인자_없이_부르면_지운_파일과_서브모듈은_건너뛴다(tmp_path: Path) -> None:
    """인덱스에는 있고 작업 트리에서 지운 파일, gitlink(160000)가 트레이스백을 내지 않는다."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8", newline="\n")
    (tmp_path / "b.txt").write_text("b\n", encoding="utf-8", newline="\n")
    _git(tmp_path, "add", "a.txt", "b.txt")
    commit = _git(tmp_path, "hash-object", "-w", "a.txt")
    _git(tmp_path, "update-index", "--add", "--cacheinfo", f"160000,{commit},sub")
    (tmp_path / "sub").mkdir()
    (tmp_path / "b.txt").unlink()

    assert tracked_files(tmp_path) == [tmp_path / "a.txt"]
    assert main(root=tmp_path) == 0


def test_git_목록이_시간을_넘기면_예외로_멈춘다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """빈 범위로 읽어 초록으로 지나가지 않는다. `check=True` 의 실패와 같은 갈래다(대기열 342)."""
    seen: list[object] = []

    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, 1)

    monkeypatch.setattr(subprocess, "run", stuck)

    with pytest.raises(subprocess.TimeoutExpired):
        tracked_files(tmp_path)
    assert seen == [CALL_TIMEOUT]


def test_이_저장소의_추적_파일에_날것_줄_구분_문자가_없다() -> None:
    assert main() == 0


def test_날것_문자가_있는_파일이_섞이면_실패한다(tmp_path: Path) -> None:
    clean = tmp_path / "clean.txt"
    clean.write_text("a\nb\n", encoding="utf-8", newline="\n")
    dirty = tmp_path / "dirty.py"
    dirty.write_text(f'x = "a{LINE_SEPARATOR}b"\n', encoding="utf-8", newline="\n")

    assert main([clean]) == 0
    assert main([clean, dirty]) == 1


def test_파일마다_확장자로_보이지_않는_문자의_범위를_가른다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    code = tmp_path / "code.py"
    code.write_text(f"x = 1{NO_BREAK_SPACE}\n", encoding="utf-8", newline="\n")
    doc = tmp_path / "doc.md"
    doc.write_text(f"가{IDEOGRAPHIC_SPACE}나\n", encoding="utf-8", newline="\n")

    assert main([doc], root=tmp_path) == 0
    assert main([code, doc], root=tmp_path) == 1
    assert capsys.readouterr().out.splitlines()[0] == "code.py:1:6: U+00A0 NO-BREAK SPACE"


def test_CLI_진입점이_인자로_받은_파일의_날것_문자를_출력한다(tmp_path: Path) -> None:
    """pre-commit 이 부르는 진입점 그대로 — 파일 경로를 인자로 받는다(tests.md)."""
    dirty = tmp_path / "dirty.py"
    dirty.write_text(f'x = "a{LINE_SEPARATOR}b"\n', encoding="utf-8", newline="\n")
    invisible = tmp_path / "invisible.py"
    invisible.write_text(f"x = 1{ZERO_WIDTH_SPACE}\n", encoding="utf-8", newline="\n")

    process = subprocess.run(
        [
            sys.executable,
            str(ROOT / "tools" / "check_line_separators.py"),
            str(dirty),
            str(invisible),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )

    assert process.returncode == 1
    assert "dirty.py:1:7: U+2028 LINE SEPARATOR" in process.stdout
    assert "invisible.py:1:6: U+200B ZERO WIDTH SPACE" in process.stdout
    assert "chr(0x2028)" in process.stdout
