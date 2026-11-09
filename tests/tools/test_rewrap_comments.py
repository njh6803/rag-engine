"""tools/rewrap_comments.py. 대기열 112: 한글 주석과 독스트링을 폭 100에 맞추느라 세션마다 스크래치
감기 스크립트를 새로 썼고, 그 스크립트들이 줄 끝을 CRLF 로 바꾸고, 빈 줄과 닫는 따옴표를 문단에
붙이고, 혼자 선 `사용:` 줄을 다음 문장에 붙이고, 코드 스팬을 갈랐다(일지 2026-10-01-01,
2026-10-06-01). 아래 시험이 그 넷을 하나씩 잰다. CLI 는 subprocess 로 한 번 실제로 부른다.

문자는 이스케이프가 아니라 chr() 로 짓는다. 편집 도구가 이스케이프를 날것으로 바꾼다(대기열 160).
"""

from __future__ import annotations

import stat
import subprocess
import sys
import unicodedata
from pathlib import Path

import pytest
from tools.rewrap_comments import ROOT, line_length, main, overlong, rewrap_source, width

TOOL = ROOT / "tools" / "rewrap_comments.py"


def _감는다(*lines: str, limit: int = 20) -> list[str]:
    """줄들을 LF 로 이어 감고, 감은 소스를 다시 줄로 돌려준다."""
    return rewrap_source("\n".join(lines) + "\n", limit).source.split("\n")[:-1]


def test_폭은_한글_2_결합_문자와_폭_없는_문자_0_가운뎃점_1이다() -> None:
    """ruff 의 E501 이 세는 폭이다. 이 저장소 전체와 ruff 의 대조는
    `.scratch/harness/probes/rewrap_width.py` 가 한다."""
    assert width("가나") == 4
    assert width("a·b") == 3
    assert width("e" + chr(0x0301)) == 1
    assert width("a" + chr(0x200B) + "b") == 2


def test_넘친_주석_줄의_꼬리_어절을_다음_줄_앞으로_넘긴다() -> None:
    assert _감는다("# aaa bbb ccc ddd eee", "# fff") == ["# aaa bbb ccc ddd", "# eee fff"]


def test_문단_끝에서_넘치면_같은_머리로_새_줄을_낸다() -> None:
    assert _감는다("    # aaa bbb ccc ddd") == ["    # aaa bbb ccc", "    # ddd"]


def test_넘긴_꼬리가_다음_줄을_넘치게_하면_거듭_넘긴다() -> None:
    assert _감는다("# aaa bbb ccc ddd eee", "# fff ggg hhh iii jjj") == [
        "# aaa bbb ccc ddd",
        "# eee fff ggg hhh",
        "# iii jjj",
    ]


def test_짧은_줄을_끌어올려_합치지_않는다() -> None:
    """문단을 통째로 다시 채우던 도우미가 혼자 선 `사용:` 줄을 다음 문장에 붙였다(일지
    2026-10-01-01). 넘친 꼬리만 앞으로 보내고 짧은 줄은 그대로 둔다."""
    result = rewrap_source("# aaa\n# bbb ccc ddd eee fff ggg\n# hhh\n", 20)

    assert result.source == "# aaa\n# bbb ccc ddd eee\n# fff ggg hhh\n"
    assert result.wrapped == [(2, 3)]


def test_이름표_줄과_목록_항목은_새_문단을_연다() -> None:
    """그 앞에서 넘친 꼬리는 그 줄에 붙지 않고 새 줄이 된다."""
    assert _감는다("# aaa bbb ccc ddd eee", "# 사용: `x`") == [
        "# aaa bbb ccc ddd",
        "# eee",
        "# 사용: `x`",
    ]
    assert _감는다("# aaa bbb ccc ddd eee", "# - fff") == ["# aaa bbb ccc ddd", "# eee", "# - fff"]


def test_목록_항목의_이어지는_줄은_표지_너비만큼_들여_쓴다() -> None:
    assert _감는다("# - aaa bbb ccc ddd eee") == ["# - aaa bbb ccc ddd", "#   eee"]
    assert _감는다("# - aaa bbb ccc ddd eee", "#   fff") == [
        "# - aaa bbb ccc ddd",
        "#   eee fff",
    ]


def test_독스트링의_닫는_따옴표는_문단의_끝_줄에_붙어_다닌다() -> None:
    assert _감는다("def f() -> None:", '    """aaa bbb ccc ddd."""') == [
        "def f() -> None:",
        '    """aaa bbb ccc',
        '    ddd."""',
    ]


def test_닫는_따옴표만_선_줄과_빈_줄은_문단의_경계다() -> None:
    """감기 스크립트가 빈 줄을 범위에 넣고 닫는 따옴표를 문단에 붙였다(일지 2026-10-06-01)."""
    lines = (
        "def f() -> None:",
        '    """aaa bbb ccc ddd',
        "",
        "    eee fff ggg hhh iii",
        '    """',
    )

    assert _감는다(*lines) == [
        "def f() -> None:",
        '    """aaa bbb ccc',
        "    ddd",
        "",
        "    eee fff ggg hhh",
        "    iii",
        '    """',
    ]


def test_더_들여_쓴_줄은_문단의_경계다() -> None:
    lines = ('"""aaa bbb ccc ddd eee', "    example()", '"""')

    assert _감는다(*lines) == ['"""aaa bbb ccc ddd', "eee", "    example()", '"""']


def test_코드_스팬은_가르지_않는다() -> None:
    """도우미가 코드 스팬을 줄에서 갈랐다(일지 2026-10-01-01). 공백으로만 가르면 백틱 하나가
    든 어절에서 끊긴다."""
    assert _감는다("# aaa `b c` d", limit=9) == ["# aaa", "# `b c` d"]


def test_겹_백틱_코드_스팬도_가르지_않는다() -> None:
    """백틱 하나를 담은 스팬은 겹 백틱으로 쓴다(셀프 리뷰 명세 축). 같은 수의 백틱끼리 짝짓는다."""
    assert _감는다("# aaa ``b ` c`` d", limit=13) == ["# aaa", "# ``b ` c`` d"]


def test_줄_끝은_줄마다_지킨다() -> None:
    """감기 스크립트가 쓰기에 줄 끝을 주지 않아 파일 셋을 CRLF 로 바꿨다(일지 2026-10-06-01).
    원래 줄은 제 줄 끝을 지키고, 새 줄은 원래 끝 줄의 줄 끝을 받는다."""
    crlf = "# aaa bbb ccc ddd eee\r\nx = 1\r\n"

    assert rewrap_source(crlf, 20).source == "# aaa bbb ccc ddd\r\n# eee\r\nx = 1\r\n"
    assert rewrap_source(crlf.replace("\r\n", "\n"), 20).source == (
        "# aaa bbb ccc ddd\n# eee\nx = 1\n"
    )
    assert rewrap_source("# aaa\n# bbb ccc ddd eee fff\r\n", 20).source == (
        "# aaa\n# bbb ccc ddd eee\r\n# fff\r\n"
    )


def test_홀로_선_CR_이_든_소스는_감지_않는다() -> None:
    """파이썬은 홀로 선 CR 을 줄 끝으로 읽고 이 도구는 개행으로만 가른다. 줄 번호가 갈린 채 감으면
    엉뚱한 줄을 고친다."""
    with pytest.raises(ValueError, match="CR"):
        rewrap_source("x = 1\r# aaa bbb ccc ddd eee\n", 20)


def test_못_보는_것_주석으로_막은_코드와_공백_없는_줄바꿈과_혼자_선_짧은_줄() -> None:
    """독스트링의 "못 보는 것" 셋을 잰다(.claude/rules/tools.md). 주석으로 막은 코드는 산문으로 보고
    감는다. 공백 없이 끊어 둔 자리로 꼬리를 넘기면 공백이 하나 생긴다. 이름표도 목록 표지도 아닌
    혼자 선 짧은 줄은 앞줄에서 넘친 꼬리를 받는다."""
    assert _감는다("# x = call(aaa, bbb, ccc)") == ["# x = call(aaa, bbb,", "# ccc)"]
    assert _감는다("# aaa bbb ccc ddd 훅이다", "# (대기열 1)") == [
        "# aaa bbb ccc ddd",
        "# 훅이다 (대기열 1)",
    ]
    assert _감는다('"""aaa bbb ccc ddd eee', "예시", '"""') == [
        '"""aaa bbb ccc ddd',
        "eee 예시",
        '"""',
    ]


def test_줄_끝_주석과_독스트링이_아닌_문자열과_코드는_감지_않고_남았다고_알린다() -> None:
    source = 'x = 1  # aaa bbb ccc ddd\ny = """aaa bbb ccc ddd"""\nzzz = aaa + bbb + ccc\n'

    result = rewrap_source(source, 20)

    assert result.source == source
    assert [row for row, _ in result.remaining] == [1, 2, 3]
    assert all("문단이 아니다" in reason for _, reason in result.remaining)


def test_여러_줄_문자열_안에서_샵으로_시작하는_줄은_주석이_아니다() -> None:
    """그 줄 끝에 진짜 주석이 있어도 줄의 머리는 문자열이다. 감으면 문자열이 바뀐다."""
    source = 'x = """\n# aaa bbb ccc ddd eee"""  # c\n'

    assert rewrap_source(source, 20).source == source


def test_샵_바로_뒤에_공백이_없는_주석은_문단에_넣지_않는다() -> None:
    """`##` 제목과 `#:` 속성 설명을 감으면 줄이 합쳐지고 새 줄의 `#` 뒤 공백이 사라졌다(PR 직전
    버그·성능 리뷰가 손으로 재현했다)."""
    source = "## aaa bbb ccc ddd eee\n#: fff ggg hhh iii jjj\n"

    result = rewrap_source(source, 20)

    assert result.source == source
    assert [row for row, _ in result.remaining] == [1, 2]


def test_SPDX_머리_줄은_ruff_처럼_넘친_줄이_아니고_감지도_않는다() -> None:
    """ruff 0.16.8 은 `#` 뒤에 공백이 있는 `SPDX-License-Identifier:`·`SPDX-FileCopyrightText:` 줄만
    E501 에서 뺀다(프로브 `rewrap_width.py`). 다른 SPDX 줄도 기계가 읽으므로 감지 않는다."""
    tail = " Apache-2.0 OR MIT OR BSD-3-Clause"
    source = "# SPDX-License-Identifier:" + tail + "\n# SPDX-FileContributor:" + tail + "\n"

    assert not overlong("# SPDX-License-Identifier:" + tail, 20)
    assert not overlong("#   SPDX-FileCopyrightText:" + tail, 20)
    assert overlong("# SPDX-FileContributor:" + tail, 20)
    assert overlong("#SPDX-License-Identifier:" + tail, 20)
    # 30이면 `SPDX-FileContributor:` 뒤에서 끊을 수 있다. 20이면 첫 어절만으로 차서 가르지 못한다.
    assert rewrap_source(source, 30).source == source


def test_doctest_줄과_코드_펜스_안은_문단에_넣지_않는다() -> None:
    """감으면 doctest 의 출력이 코드 줄에 붙었다(PR 직전 버그·성능 리뷰가 손으로 재현했다)."""
    lines = (
        '"""aaa',
        ">>> call(bbb, ccc, ddd, eee)",
        "... ggg(hhh, iii, jjj, kkk)",
        "fff",
        "```",
        "hhh iii jjj kkk lll mmm",
        "```",
        '"""',
    )

    assert _감는다(*lines) == list(lines)


def test_역슬래시_바로_뒤에서는_끊지_않는다() -> None:
    """비 raw 문자열에서 줄 끝 역슬래시는 다음 줄과 이어 읽혀 내용이 바뀐다. 어디서나 피한다."""
    assert _감는다("# aaa bbbbb \\ cccccccc") == ["# aaa bbbbb", "# \\ cccccccc"]


def test_지시_주석과_역슬래시로_끝나는_줄은_감지_않는다() -> None:
    """지시 주석은 도구가 읽는 꼴이고, 역슬래시는 다음 줄과 이어 읽힌다."""
    pragma = "# noqa: E501 aaa bbb ccc ddd\n#!/usr/bin/env python aaa bbb\n"
    continued = 'def f() -> None:\n    """aaa bbb ccc ddd eee \\\n    fff"""\n'

    for source in (pragma, continued):
        result = rewrap_source(source, 20)
        assert result.source == source
        assert result.remaining


def test_한_어절이_폭을_넘으면_그대로_두고_알린다() -> None:
    source = "# " + "a" * 25 + " bbb\n"

    result = rewrap_source(source, 20)

    assert result.source == source
    assert len(result.remaining) == 1
    row, reason = result.remaining[0]
    assert row == 1
    assert "어절" in reason


def test_넘친_줄이_없으면_그대로이고_두_번_감아도_같다() -> None:
    fine = "# aaa\nx = 1\n"
    result = rewrap_source(fine, 20)
    assert (result.source, result.wrapped, result.remaining) == (fine, [], [])

    once = rewrap_source('"""aaa bbb ccc ddd eee fff ggg hhh."""\n# iii jjj kkk lll mmm\n', 20)
    assert rewrap_source(once.source, 20).source == once.source


def test_감은_자리를_새_소스의_줄_번호로_알린다() -> None:
    source = "# aaa bbb ccc ddd eee\nx = 1\n# ggg hhh iii jjj kkk\n"

    assert rewrap_source(source, 20).wrapped == [(1, 2), (4, 5)]


def test_BOM_은_지키고_첫_줄의_독스트링을_감는다() -> None:
    bom = chr(0xFEFF)

    assert rewrap_source(bom + '"""aaa bbb ccc ddd eee."""\n', 20).source == (
        bom + '"""aaa bbb ccc ddd\neee."""\n'
    )


def test_URL_로_끝나는_줄과_덩어리가_하나인_줄은_넘친_줄이_아니다() -> None:
    """ruff 의 E501 의 두 예외다. ruff 와의 대조는 `.scratch/harness/probes/rewrap_width.py`."""
    url = "https://example.com/" + "a" * 30

    assert not overlong("# see " + url, 20)
    assert overlong("# " + "b" * 20 + " " + url, 20)
    assert not overlong("#" + "c" * 30, 20)
    assert overlong("# " + "c" * 30, 20)


def test_줄_끝_지시_주석은_ruff_처럼_빼고_잰다() -> None:
    """ruff 0.16.8 은 `noqa`·`pyright:` 같은 지시 주석을 폭에서 빼고 `fmt:` 는 빼지 않는다. 코드를
    들지 않은 noqa 와 E501 을 든 noqa 는 그 줄의 E501 을 끈다(프로브 `rewrap_width.py`)."""
    tail = " " + "d " * 50
    code = "x = " + "1 + " * 30 + "1"
    after = len(code) + 2

    assert not overlong("x = 1  # noqa: B010" + tail, 100, 7)
    assert not overlong("x = 1  # pyright: basic" + tail, 100, 7)
    assert overlong("x = 1  # fmt: skip" + tail, 100, 7)
    assert not overlong(code + "  # noqa", 100, after)
    assert not overlong(code + "  # noqa: E501", 100, after)
    assert overlong(code + "  # noqa: B010", 100, after)
    assert rewrap_source("x = 1  # noqa: B010" + tail + "\n", 100).remaining == []


def test_조합형_한글의_가운뎃소리와_끝소리_자모는_폭_0이다() -> None:
    """ruff 는 NFD 로 풀어 쓴 한글의 이어지는 자모를 폭 0으로 센다(셀프 리뷰 표준 축이 손으로
    쟀다. 대조는 프로브 `rewrap_width.py`)."""
    assert width(unicodedata.normalize("NFD", "한글")) == 4
    assert width(chr(0x1100) + chr(0x1161) + chr(0xD7B0)) == 2


def test_한글_주석을_폭_100에_맞춰_감는다() -> None:
    words = [f"한글{index}번" for index in range(40)]

    lines = _감는다("# " + " ".join(words), limit=100)

    assert len(lines) > 1
    assert all(width(line) <= 100 for line in lines)
    assert " ".join(line.removeprefix("# ") for line in lines) == " ".join(words)


def test_줄_길이는_그_파일을_다스리는_ruff_설정에서_읽는다(tmp_path: Path) -> None:
    """줄 폭 훅은 ruff 설정이 있는 어느 파일에서나 감기 명령을 싣는다. 도구가 이 저장소의 100만
    쓰면 다른 설정 아래에서는 넘친 줄을 못 본다(셀프 리뷰 명세 축)."""
    module = tmp_path / "a" / "b" / "m.py"
    module.parent.mkdir(parents=True)
    assert line_length(module) is None

    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 77\n", encoding="utf-8")
    assert line_length(module) == 77

    (tmp_path / "a" / "pyproject.toml").write_text("[project]\nname = 'x'\n", encoding="utf-8")
    assert line_length(module) == 77

    (tmp_path / "a" / "ruff.toml").write_text("line-length = 60\n", encoding="utf-8")
    assert line_length(module) == 60

    (tmp_path / "a" / "b" / ".ruff.toml").write_text(
        "line-length = 60\n\n[lint.pycodestyle]\nmax-line-length = 70\n", encoding="utf-8"
    )
    assert line_length(module) == 70

    (tmp_path / "a" / "b" / ".ruff.toml").write_text("[lint]\nselect = ['E']\n", encoding="utf-8")
    assert line_length(module) == 88
    assert line_length(ROOT / "tools" / "rewrap_comments.py") == 100


def _설정_아래에_쓴다(tmp_path: Path, data: bytes) -> Path:
    """줄 길이 100의 ruff 설정과 그 아래 파일 하나를 쓴다."""
    (tmp_path / "pyproject.toml").write_text("[tool.ruff]\nline-length = 100\n", encoding="utf-8")
    path = tmp_path / "module.py"
    path.write_bytes(data)
    return path


def test_감지_못한_줄이_남으면_1로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    path = _설정_아래에_쓴다(tmp_path, ("x = 1  # " + " ".join(["가나"] * 30) + "\n").encode())

    assert main([str(path)]) == 1
    assert "넘친 채 남았다" in capsys.readouterr().out


def test_고쳐_쓰지_못하면_2로_알리고_다음_파일로_간다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """쓰기가 try 밖에 있어 traceback 과 종료 1(넘친 줄이 남았다)로 끝나고 뒤의 파일을 건너뛰었다(PR
    직전 버그·성능 리뷰가 손으로 재현했다)."""
    data = ("# " + " ".join(["가나"] * 30) + "\n").encode()
    locked = _설정_아래에_쓴다(tmp_path, data)
    other = tmp_path / "other.py"
    other.write_bytes(data)
    locked.chmod(stat.S_IREAD)
    try:
        status = main([str(locked), str(other)])
    finally:
        locked.chmod(stat.S_IREAD | stat.S_IWRITE)

    assert status == 2
    assert "고쳐 쓰지 못했다" in capsys.readouterr().out
    assert locked.read_bytes() == data
    assert other.read_bytes() != data


def test_ruff_설정_밖의_파일과_읽지_못하는_설정은_고치지_않고_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    before = ("# " + " ".join(["가나"] * 30) + "\n").encode()
    loose = tmp_path / "loose" / "module.py"
    loose.parent.mkdir()
    loose.write_bytes(before)
    broken = tmp_path / "broken" / "module.py"
    broken.parent.mkdir()
    broken.write_bytes(before)
    (broken.parent / "ruff.toml").write_text('line-length = "x"\n', encoding="utf-8")

    assert main([str(loose)]) == 2
    assert "ruff 설정 밖" in capsys.readouterr().out
    assert main([str(broken)]) == 2
    assert loose.read_bytes() == before
    assert broken.read_bytes() == before


def test_CLI_는_파일을_고쳐_쓰고_감은_자리를_알린다(tmp_path: Path) -> None:
    path = _설정_아래에_쓴다(
        tmp_path, ("# " + " ".join(["가나"] * 30) + "\r\nx = 1\r\n").encode("utf-8")
    )

    completed = subprocess.run(
        [sys.executable, str(TOOL), str(path)], capture_output=True, check=False
    )

    assert completed.returncode == 0, completed.stdout.decode("utf-8", "replace")
    assert f"{path}:1: 감았다" in completed.stdout.decode("utf-8")
    data = path.read_bytes()
    assert data.count(b"\r\n") == 3
    assert b"\n" not in data.replace(b"\r\n", b"")


def test_CLI_는_구문_오류면_고치지_않고_2로_끝난다(tmp_path: Path) -> None:
    before = ("def f(:\n# " + " ".join(["가나"] * 30) + "\n").encode("utf-8")
    path = _설정_아래에_쓴다(tmp_path, before)

    completed = subprocess.run(
        [sys.executable, str(TOOL), str(path)], capture_output=True, check=False
    )

    assert completed.returncode == 2
    assert "파이썬으로 읽지 못해" in completed.stdout.decode("utf-8")
    assert path.read_bytes() == before


def test_이_저장소의_파이썬_파일에는_감을_줄이_없다() -> None:
    """게이트(ruff E501)가 초록인 저장소에서 넘친 줄을 찾으면 폭을 ruff 와 다르게 센 것이다. 모든
    파일을 파싱해 보는 시험이기도 하다."""
    listed = subprocess.run(
        ["git", "ls-files", "-z", "*.py"], cwd=ROOT, capture_output=True, check=True
    )
    files = [ROOT / name for name in listed.stdout.decode("utf-8").split("\0") if name]

    # agent-os 의 문턱은 `> 100` 이었다. rag-engine 킥오프(2026-11-09) 첫 커밋에 들 파이썬 파일은
    # 99개라(무시되지 않은 파일을 `git ls-files -c -o --exclude-standard` 로 셌다) 90 으로 내렸다
    assert len(files) >= 90
    for path in files:
        source = path.read_bytes().decode("utf-8")
        result = rewrap_source(source, 100)
        assert (path, result.source == source, result.remaining) == (path, True, [])
