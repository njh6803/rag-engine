"""tools/check_quotes.py — 인용을 뽑는 것과 원문 대조. 저장소 전체를 도는 스모크 하나."""

from __future__ import annotations

import os
import subprocess
import sys
from collections.abc import Callable
from pathlib import Path

import pytest
from tools.check_quotes import (
    CALL_TIMEOUT,
    ROOT,
    Quote,
    added_lines,
    added_lines_from_diff,
    check,
    default_files,
    quotes_in,
    tracked_text_files,
)

원문 = "지침을 쓰는 사람이 그 지침을 가장 먼저 어긴다는 것이 이 저장소가 훅을 위에 두는 이유다"


def _저장소를_만든다(root: Path, 문서: str, 원천: str = 원문) -> Path:
    (root / "docs").mkdir()
    (root / "docs" / "source.md").write_text(f"# 원천\n\n{원천}\n", encoding="utf-8")
    quoting = root / "docs" / "quoting.md"
    quoting.write_text(문서, encoding="utf-8")
    return quoting


def _git(root: Path, *args: str) -> None:
    # CI 러너에는 git 신원이 없다. 커밋은 여기서 주는 신원으로 한다.
    subprocess.run(
        ["git", "-C", str(root), "-c", "user.name=t", "-c", "user.email=t@t", *args],
        check=True,
        capture_output=True,
    )


def _덧붙인다(path: Path, 줄: str) -> None:
    with path.open("a", encoding="utf-8", newline="\n") as file:
        file.write(줄)


def test_원문이_다른_파일에_있으면_경고가_없다(tmp_path: Path) -> None:
    quoting = _저장소를_만든다(tmp_path, f'감사가 말한 "{원문}"가 여기 적용된다.\n')

    assert check([quoting], tmp_path).warnings == []


def test_원문이_어디에도_없으면_파일과_줄을_들어_경고한다(tmp_path: Path) -> None:
    문서 = '첫 줄\n감사가 말한 "지침을 쓰는 사람이 그 지침을 나중에야 어긴다는 것"이라는 말.\n'
    quoting = _저장소를_만든다(tmp_path, 문서)

    warnings = check([quoting], tmp_path).warnings

    assert len(warnings) == 1
    assert warnings[0].startswith("docs/quoting.md:2:")
    assert "글자 그대로 없다" in warnings[0]


def test_같은_파일_안의_원문도_두_번째_자리다(tmp_path: Path) -> None:
    문서 = f'{원문}\n\n위 문장, 곧 "{원문}"를 다시 든다.\n'
    quoting = _저장소를_만든다(tmp_path, 문서, 원천="다른 것")

    assert check([quoting], tmp_path).warnings == []


def test_인용문_줄과_코드_안은_보지_않는다() -> None:
    markdown = (
        '> 사용자: "이것은 사용자가 말한 긴 문장이라 저장소에 원문이 없다"\n'
        '`"코드 스팬 안의 긴 문장도 인용이 아니라 문자열이다"`\n'
        '```\nprint("펜스 안의 긴 문장도 인용이 아니라 문자열이다")\n```\n'
        '산문의 "이것만 산문의 진짜 인용이고 스무 자를 넘는다".\n'
    )

    assert quotes_in(markdown) == [Quote(6, "이것만 산문의 진짜 인용이고 스무 자를 넘는다", None)]


def test_코드_스팬과_강조는_벗기고_대조한다(tmp_path: Path) -> None:
    """원문에 `itemSchema`가 백틱으로 있고 인용은 백틱을 뗐거나 강조를 더한 경우가 잦다."""
    quoting = _저장소를_만든다(
        tmp_path,
        '명세는 "스트림의 항목 스키마는 itemSchema로 계약에 **실린다**"고 적는다.\n',
        원천="스트림의 항목 스키마는 `itemSchema`로 계약에 실린다.",
    )

    assert check([quoting], tmp_path).warnings == []


def test_따옴표_쌍이_어긋나_잡힌_조각은_버린다() -> None:
    앞 = '앱이 지은 제목("첫 인용 스무 자를 넘기는 문장이다 정말로")가 붙어 왔다. '
    markdown = 앞 + '로 지은 것("둘째")도.\n'

    assert quotes_in(markdown) == [Quote(1, "첫 인용 스무 자를 넘기는 문장이다 정말로", None)]


def test_diff_헝크_머리에서_더한_줄을_읽는다() -> None:
    diff = (
        "--- a/x.md\n+++ b/x.md\n@@ -1,2 +3,4 @@\n+a\n+b\n+c\n+d\n"
        "@@ -9 +12 @@\n+e\n@@ -20,3 +20,0 @@\n-x\n"
    )

    assert added_lines_from_diff(diff) == {3, 4, 5, 6, 12}


def test_더한_줄만_볼_때_diff_가_없으면_전체를_본다(tmp_path: Path) -> None:
    """저장소 밖(테스트)에서는 diff 가 없어 None 이고 전체가 대상이다. 조용히 비지 않는다."""
    문서 = '첫 줄\n감사가 말한 "지침을 쓰는 사람이 그 지침을 나중에야 어긴다는 것"이라는 말.\n'
    quoting = _저장소를_만든다(tmp_path, 문서)

    filtered = check([quoting], tmp_path, line_filter=lambda p: added_lines(p, tmp_path)).warnings

    assert len(filtered) == 1


def test_더한_줄은_스테이지와_상관없이_작업_트리가_HEAD_에_더한_줄이다(tmp_path: Path) -> None:
    """스테이지된 줄만 보면 부분 스테이지된 파일의 나머지 편집을 조용히 건너뛴다(대기열 55)."""
    quoting = _저장소를_만든다(
        tmp_path, '옛 줄 "커밋된 옛 줄의 틀린 인용은 이번 변경이 아니라 보지 않는다"\n'
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "처음")
    _덧붙인다(quoting, '스테이지한 줄 "스테이지한 줄의 틀린 인용도 스무 자를 넘어 잡혀야 한다"\n')
    _git(tmp_path, "add", ".")
    _덧붙인다(quoting, '안 한 줄 "스테이지하지 않은 줄의 틀린 인용도 스무 자를 넘어 잡혀야 한다"\n')

    warnings = check([quoting], tmp_path, line_filter=lambda p: added_lines(p, tmp_path)).warnings

    assert [warning.split(":")[1] for warning in warnings] == ["2", "3"]


def test_이름을_바꾼_파일은_옛_경로와_짝지어_바뀐_줄만_본다(tmp_path: Path) -> None:
    """새 경로 하나로 diff 하면 파일 전체가 더한 줄이라 옮겨 온 옛 줄까지 다시 대조된다(대기열
    377)."""
    채움 = "".join(f"채움 줄 {n}번은 인용이 없고 옮겨도 그대로다\n" for n in range(8))
    _저장소를_만든다(
        tmp_path, f'옛 줄 "커밋된 옛 줄의 틀린 인용은 이름을 바꿔도 다시 보지 않는다"\n{채움}'
    )
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "처음")
    _git(tmp_path, "mv", "docs/quoting.md", "docs/moved.md")
    moved = tmp_path / "docs" / "moved.md"
    _덧붙인다(moved, '새 줄 "옮긴 뒤 더한 줄의 틀린 인용은 스무 자를 넘어 잡혀야 한다"\n')
    _git(tmp_path, "add", ".")

    warnings = check([moved], tmp_path, line_filter=lambda p: added_lines(p, tmp_path)).warnings

    assert [warning.split(":")[:2] for warning in warnings] == [["docs/moved.md", "10"]]


def test_이름을_바꾸지_않은_새_파일은_모든_줄이_더한_줄이다(tmp_path: Path) -> None:
    """옮긴 것이 아니면 짝지을 옛 경로가 없다. 지운 파일이 없으니 git 도 이름 바꾸기로 읽지
    않는다."""
    _저장소를_만든다(tmp_path, "첫 줄\n")
    _git(tmp_path, "init", "-q")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "처음")
    new = tmp_path / "docs" / "new.md"
    _덧붙인다(new, "하나\n둘\n셋\n")
    _git(tmp_path, "add", ".")

    assert added_lines(new, tmp_path) == {1, 2, 3}


def test_이름_바꾸기를_묻는_git_이_시간을_넘기면_새_파일_그대로_본다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """넘김은 git 이 실패한 갈래로 센다(대기열 342). 옛 경로를 모르니 파일 전체가 더한 줄이다."""
    새_파일 = "new file mode 100644\n--- /dev/null\n+++ b/x.md\n@@ -0,0 +1,2 @@\n+a\n+b\n"
    seen: list[list[str]] = []

    def run(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen.append(args)
        if "--name-status" in args:
            raise subprocess.TimeoutExpired(args, 1)
        return subprocess.CompletedProcess(args, 0, 새_파일.encode(), b"")

    monkeypatch.setattr(subprocess, "run", run)

    assert added_lines(tmp_path / "x.md", tmp_path) == {1, 2}
    assert [("--name-status" in args) for args in seen] == [False, True]


def test_감긴_독스트링과_주석을_한_줄로_옮긴_인용도_원문을_찾는다(tmp_path: Path) -> None:
    """독스트링과 주석은 폭 100 으로 감긴다. 한 줄로 옮긴 인용이 없다고 경고됐다(대기열 345)."""
    (tmp_path / "tool.py").write_text(
        'def f() -> None:\n    """감긴 독스트링의 첫 줄은 여기서 끊기고\n'
        '    다음 줄에서 이어지는 문장이다."""\n'
        "# 감긴 주석의 첫 줄은 여기서 끊기고\n#   다음 줄에서 이어지는 문장이다\n",
        encoding="utf-8",
    )
    quoting = _저장소를_만든다(
        tmp_path,
        '독스트링은 "감긴 독스트링의 첫 줄은 여기서 끊기고 다음 줄에서 이어지는 문장이다"라 '
        "한다.\n\n"
        '주석은 "감긴 주석의 첫 줄은 여기서 끊기고 다음 줄에서 이어지는 문장이다"라 한다.\n',
    )

    assert check([quoting], tmp_path).warnings == []


def test_슬래시_주석으로_감긴_원문을_한_줄로_옮긴_인용도_원문을_찾는다(tmp_path: Path) -> None:
    """TS·JS 의 `//` 주석도 폭 100 으로 감긴다. 다음 줄 머리의 `//` 를 벗기지 않아 경고됐다(대기열
    436)."""
    (tmp_path / "tool.mjs").write_text(
        "// 감긴 슬래시 주석의 첫 줄은 여기서 끊기고\n//   다음 줄에서 이어지는 문장이다\n",
        encoding="utf-8",
    )
    quoting = _저장소를_만든다(
        tmp_path,
        '주석은 "감긴 슬래시 주석의 첫 줄은 여기서 끊기고 다음 줄에서 이어지는 문장이다"라 한다.\n',
    )

    assert check([quoting], tmp_path).warnings == []


@pytest.mark.parametrize("차례", [(0, 1), (1, 0)])
def test_넘겨받은_미추적_파일은_차례와_상관없이_서로의_원문이다(
    tmp_path: Path, 차례: tuple[int, int]
) -> None:
    """대조하는 차례에 하나씩 말뭉치에 더하면 앞 파일은 뒤 파일의 원문을 보지 못한다(대기열 398)."""
    _git(tmp_path, "init", "-q")
    (tmp_path / "base.md").write_text("# 바탕\n", encoding="utf-8")
    _git(tmp_path, "add", ".")
    _git(tmp_path, "commit", "-q", "-m", "처음")
    adr = tmp_path / "adr.md"
    일지 = tmp_path / "journal.md"
    adr.write_text(
        '사용자가 "일지에 적은 사용자의 원문 한 줄이 여기 그대로 옮겨진다"고 했다.\n'
        "ADR 이 정한 문장은 이 결정이 다음 세션에도 그대로 이어진다는 것이다.\n",
        encoding="utf-8",
    )
    일지.write_text(
        "일지에 적은 사용자의 원문 한 줄이 여기 그대로 옮겨진다.\n"
        'ADR 은 "이 결정이 다음 세션에도 그대로 이어진다는 것이다"라 적었다.\n',
        encoding="utf-8",
    )
    파일 = [adr, 일지]

    report = check([파일[차례[0]], 파일[차례[1]]], tmp_path)

    assert (report.warnings, report.quotes_checked) == ([], 2)


def test_빈_줄로_나뉜_두_문단을_이은_인용은_원문으로_세지_않는다(tmp_path: Path) -> None:
    """줄을 펴는 것은 감긴 줄만이다. 빈 줄은 이음매가 둘이라 문단을 넘어 맞지 않는다."""
    quoting = _저장소를_만든다(
        tmp_path,
        '"앞 문단의 끝 문장이다 그리고 뒤 문단의 첫 문장이다"\n',
        원천="앞 문단의 끝 문장이다\n\n그리고 뒤 문단의 첫 문장이다",
    )

    assert len(check([quoting], tmp_path).warnings) == 1


def test_상대_경로로_넘어온_파일도_한_번만_센다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """pre-commit 은 상대 경로를 넘긴다. 같은 파일이 두 키로 들어가면 인용이 두 번 세어진다."""
    문서 = '첫 줄\n감사가 말한 "지침을 쓰는 사람이 그 지침을 나중에야 어긴다는 것"이라는 말.\n'
    _저장소를_만든다(tmp_path, 문서)
    monkeypatch.chdir(tmp_path)

    assert len(check([Path("docs/quoting.md")], tmp_path).warnings) == 1


def test_추적되지_않은_새_파일의_옳은_인용은_자기_자리를_센다(tmp_path: Path) -> None:
    """corpus 는 git ls-files 인데 새 파일은 거기 없다. 그러면 옳은 인용도 한 자리 모자란다."""
    quoting = _저장소를_만든다(tmp_path, f'감사가 말한 "{원문}"가 여기 적용된다.\n')

    assert check([quoting], tmp_path).warnings == []


def test_가운데가_생략된_인용은_조각마다_찾는다(tmp_path: Path) -> None:
    quoting = _저장소를_만든다(
        tmp_path,
        '헌법은 "플러그인은 sdk만 import한다. … import-linter가 판정한다"고 적었다.\n',
        원천="플러그인은 sdk만 import한다. 의존 방향은 여섯이다. import-linter가 판정한다.",
    )

    assert check([quoting], tmp_path).warnings == []


def test_코드_스팬_안의_셸_인용은_인용이_아니다() -> None:
    markdown = '`uv run --project "${DIR}" python "${DIR}/tools/hook.py"` 로 돈다.\n'

    assert quotes_in(markdown) == []


def test_스무_자_미만은_보지_않는다() -> None:
    assert quotes_in('짧은 "열여덟 자짜리 인용문은 세지 않아"와 "an agent OS"\n') == []
    assert len(quotes_in('"꼭 스무 자가 되는 인용은 본다. 여기가 스무 자"\n')) == 1


def test_ADR_가까이의_인용은_그_ADR_파일에서_찾는다(tmp_path: Path) -> None:
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0009-resume.md").write_text(
        "### 2026-09-22 결정은 정책이 아니라 멈춘 호출에 묶인다. 마스킹의 범위는 인자뿐이다\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "adr" / "0010-server.md").write_text(
        "### 2026-09-22 조립은 서버가\n", encoding="utf-8"
    )
    quoting = tmp_path / "docs" / "note.md"
    quoting.write_text(
        'ADR 0009의 2026-09-22 이력 "결정은 정책이 아니라 멈춘 호출에 묶인다"가 원천이다.\n'
        'ADR 0009("정책이 결정을 정한다")는 틀린 인용이다.\n'
        'ADR 0099("없는 ADR 의 인용")도 잡는다.\n'
        'ADR 0009("결정은 정책이 … 인자뿐이다")처럼 생략된 것은 조각으로 본다.\n'
        'ADR 0009의 이력과 ADR 0010("조립은 서버가")는 뒤의 ADR 것이다.\n',
        encoding="utf-8",
    )

    warnings = check([quoting], tmp_path).warnings

    assert len(warnings) == 2
    assert "ADR 0009 에 이 문구가 글자 그대로 없다" in warnings[0]
    assert "ADR 0099 파일이 없다" in warnings[1]


def test_ADR_가까이_적혔을_뿐_다른_자리에_있는_인용은_경고하지_않는다(tmp_path: Path) -> None:
    (tmp_path / "docs" / "adr").mkdir(parents=True)
    (tmp_path / "docs" / "adr" / "0009-resume.md").write_text("### 이력\n", encoding="utf-8")
    (tmp_path / "docs" / "spec.md").write_text(
        "명세는 재개를 트레이스 재생으로 정한다.\n", encoding="utf-8"
    )
    quoting = tmp_path / "docs" / "note.md"
    quoting.write_text(
        'ADR 0009 뒤에 명세가 "재개를 트레이스 재생으로 정한다"고 했다.\n', encoding="utf-8"
    )

    assert check([quoting], tmp_path).warnings == []


def test_생략된_인용의_조각도_두_번째_자리를_요구한다(tmp_path: Path) -> None:
    """조각을 인용 파일 자신에서 찾으면 생략 인용은 영영 경고하지 않는다(2026-09-28 적대 검증)."""
    quoting = _저장소를_만든다(
        tmp_path, '없는 말을 "이 조각은 어디에도 없다 … 이 조각도 어디에 없다"고 적었다.\n'
    )

    assert len(check([quoting], tmp_path).warnings) == 1


def test_코드_스팬_안의_홑_따옴표_하나가_줄의_인용을_지우지_않는다() -> None:
    markdown = '`"` 하나 뒤의 "이것은 스무 자를 넘는 진짜 인용이고 잡혀야 한다"는 인용이다.\n'

    assert quotes_in(markdown) == [
        Quote(1, "이것은 스무 자를 넘는 진짜 인용이고 잡혀야 한다", None)
    ]


def test_목록_안의_인용문과_펜스도_뺀다() -> None:
    markdown = (
        '- > 사용자: "목록 안 인용문의 긴 문장은 원문이 없어도 본다면 거짓 양성"\n'
        '- ````\n  "네 백틱 펜스 안의 긴 문장도 코드라서 인용이 아니다"\n  ````\n'
        '```\n"닫히지 않은 펜스 뒤는 전부 코드라서 인용이 아니다 정말로"\n'
    )

    assert quotes_in(markdown) == []


def test_닫는_펜스가_여는_것보다_길어도_닫힌다() -> None:
    """PR #92 리뷰: ``` 를 ```` 로 닫으면 열린 펜스로 봐서 뒤의 산문을 전부 코드로 버렸다."""
    markdown = '```python\n코드\n````\n"펜스 뒤의 산문 인용은 스무 자를 넘고 잡혀야 한다"\n'

    assert quotes_in(markdown) == [
        Quote(4, "펜스 뒤의 산문 인용은 스무 자를 넘고 잡혀야 한다", None)
    ]


def test_굽은_따옴표도_인용이다() -> None:
    assert quotes_in("그가 “굽은 따옴표로 감싼 스무 자 넘는 인용문이다 정말로”라 했다\n") == [
        Quote(1, "굽은 따옴표로 감싼 스무 자 넘는 인용문이다 정말로", None)
    ]


@pytest.mark.parametrize(
    "표지",
    [
        "한 줄: ",
        "한 줄 후보: ",
        "한 구절: ",
        "한 구절 후보: ",
        "한 구절 더: ",
        "한 줄의 문구: ",
        "문구 후보: ",
    ],
)
def test_제안_표지_뒤의_따옴표는_인용이_아니다(표지: str) -> None:
    """대기열·일지의 한 줄 후보는 아직 없는 문장이다. 원문을 찾으면 늘 거짓 경고다(대기열 51)."""
    markdown = (
        f'implement 스킬에 **{표지.strip()}** "이 티켓의 체크박스가 요구하는 것만 쓰고 넘긴다"\n'
    )

    assert quotes_in(markdown) == []


@pytest.mark.parametrize("표지", ["옛 문구: ", "경고 문구: ", "로그의 한 줄: ", "일지의 한 구절: "])
def test_있는_글을_가리키는_표지_뒤의_인용은_본다(표지: str) -> None:
    """옛 문구를 인용하는 것이 이 검사가 잡으려는 바로 그 모양이다(셀프 리뷰 표준 축)."""
    원문_인용 = "스무 자를 넘는 진짜 원문 인용이라 대조되어야 한다"

    assert quotes_in(f'검사의 {표지}"{원문_인용}"\n') == [Quote(1, 원문_인용, None)]


def test_제안_표지가_없는_같은_줄의_인용은_그대로_본다() -> None:
    markdown = (
        '한 구절 후보: "아직 없는 제안 문장은 스무 자를 넘어도 보지 않는다", '
        '브리프의 "제안 표지가 없는 인용은 스무 자를 넘으면 본다"\n'
    )

    assert quotes_in(markdown) == [Quote(1, "제안 표지가 없는 인용은 스무 자를 넘으면 본다", None)]


def test_줄을_넘는_인용의_닫는_따옴표는_다음_인용과_짝짓지_않는다() -> None:
    """닫는 따옴표를 여는 것으로 읽으면 사이의 산문이 인용이 되어 거짓 경고가 난다(대기열 67)."""
    markdown = (
        '- **67.** 닫는 따옴표가 다음 인용과 짝지어진다. 독스트링은 "못\n'
        '  본다"고만 적었고 그 뒤에 긴 산문이 스무 자를 넘게 이어진 다음에야 '
        '"둘째 줄의 진짜 인용은 스무 자를 넘고 잡혀야 한다"가 온다.\n'
    )

    assert quotes_in(markdown) == [
        Quote(2, "둘째 줄의 진짜 인용은 스무 자를 넘고 잡혀야 한다", None)
    ]


def test_짝은_목록_항목과_문단_안에서만_짓는다() -> None:
    """짝이 없는 따옴표 하나(인치 표시 등)가 다음 항목의 짝을 모두 뒤집지 않는다."""
    markdown = (
        '- 27" 모니터 하나\n'
        '- "다음 목록 항목의 인용은 스무 자를 넘고 잡혀야 한다"\n'
        "\n"
        '문단의 짝 없는 " 하나\n'
        "\n"
        '"다음 문단의 인용도 스무 자를 넘고 잡혀야 한다 정말로"\n'
    )

    assert quotes_in(markdown) == [
        Quote(2, "다음 목록 항목의 인용은 스무 자를 넘고 잡혀야 한다", None),
        Quote(6, "다음 문단의 인용도 스무 자를 넘고 잡혀야 한다 정말로", None),
    ]


진짜_인용 = "스무 자를 넘는 진짜 인용은 여기에 있다 정말로"


@pytest.mark.parametrize(
    ("markdown", "줄"),
    [
        (f'## 27" 모니터\n본문 "{진짜_인용}" 끝\n', 2),
        (f'1) 27" 모니터\n2) "{진짜_인용}"\n', 2),
        (f'제목 27" 모니터\n===\n본문 "{진짜_인용}"\n', 3),
    ],
    ids=["ATX 제목은 한 줄", "괄호 번호 목록", "setext 밑줄에서 끝난다"],
)
def test_묶음은_제목과_번호_목록에서도_끊긴다(markdown: str, 줄: int) -> None:
    """제목 다음 줄과 `1)` 목록이 앞 묶음에 붙으면 짝 없는 따옴표가 뒤의 짝을 뒤집는다."""
    assert quotes_in(markdown) == [Quote(줄, 진짜_인용, None)]


def test_인용문의_게으른_이어짐도_인용문이라_보지_않는다() -> None:
    """`>` 없이 이어진 줄도 CommonMark 에서는 그 인용문의 문단이다."""
    markdown = (
        "> 사용자가 한 말의 첫 줄\n"
        '게으른 줄 "게으른 이어짐도 인용문이라 스무 자를 넘어도 보지 않는다"\n'
        "\n"
        f'인용문 밖 "{진짜_인용}"\n'
    )

    assert quotes_in(markdown) == [Quote(4, 진짜_인용, None)]


@pytest.mark.parametrize("확장자", [".ts", ".tsx", ".mjs", ".js"])
def test_TS_와_JS_의_원문도_찾는다(tmp_path: Path, 확장자: str) -> None:
    """일지가 web 테스트 이름이나 변이 이름을 인용하면 원문은 TS·JS 에 있다(대기열 66)."""
    이름 = "관리 토큰이 없으면 플러그인 목록 대신 토큰 입력을 보인다"
    (tmp_path / "web").mkdir()
    (tmp_path / "web" / f"page.test{확장자}").write_text(
        f'it("{이름}", () => {{}});\n', encoding="utf-8"
    )
    quoting = tmp_path / "note.md"
    quoting.write_text(f'테스트 "{이름}"가 초록이다.\n', encoding="utf-8")

    assert check([quoting], tmp_path).warnings == []


def test_독스트링이_못_본다고_적은_것은_정말_못_본다(tmp_path: Path) -> None:
    """못 본다는 주장도 잰다(.claude/rules/tools.md). 잡게 되면 독스트링을 고친다."""
    홑따옴표 = "'홑따옴표로 감싼 스무 자 넘는 인용은 보지 않는다 정말로'\n"
    줄바꿈 = '"줄바꿈을 넘는 인용은 첫 줄에서 끊겨\n보지 않는다 정말로 스무 자를 넘어도"\n'
    제안_표지_뒤의_원문 = '반영한 한 줄: "지침을 쓰는 사람이 그 지침을 가장 먼저 어긴다는 것이"\n'
    짝_없는_따옴표_뒤 = '27" 모니터와 "뒤의 인용은 스무 자를 넘어도 짝이 뒤집혀 못 본다 정말로"\n'
    번호처럼_보이는_줄 = f'브리프가 "줄을 넘는 인용이\n42. 로 시작하는 줄" 뒤에 "{진짜_인용}"\n'
    줄을_넘는_코드_스팬 = f'`a "\nb` 뒤 "{진짜_인용}"\n'
    assert quotes_in(홑따옴표) == []
    assert quotes_in(줄바꿈) == []
    assert quotes_in(제안_표지_뒤의_원문) == []
    assert quotes_in(짝_없는_따옴표_뒤) == []
    assert quotes_in(번호처럼_보이는_줄) == []
    assert quotes_in(줄을_넘는_코드_스팬) == []

    같은_틀린_인용 = f'하나 "{원문[:-3]} 까닭이다"\n둘 "{원문[:-3]} 까닭이다"\n'
    quoting = _저장소를_만든다(tmp_path, 같은_틀린_인용, 원천="다른 것")
    assert check([quoting], tmp_path).warnings == []

    # 줄을 편 사본은 줄 머리의 `#` 를 주석 표지로 지워, 마크다운 제목과 앞 줄을 잇는다.
    제목_자리 = tmp_path / "제목"
    제목_자리.mkdir()
    제목과_이어진_인용 = _저장소를_만든다(
        제목_자리,
        '"앞 문단의 마지막 줄 끝 제목의 낱말들이 이어진다"\n',
        원천="앞 문단의 마지막 줄 끝\n## 제목의 낱말들이 이어진다",
    )
    assert check([제목과_이어진_인용], 제목_자리).warnings == []

    # 줄 머리의 `//` 도 주석 표지로 지워, 주석이 아니었던 `//` 줄과 앞 줄을 잇는다(대기열 436).
    슬래시_자리 = tmp_path / "슬래시"
    슬래시_자리.mkdir()
    슬래시_줄과_이어진_인용 = _저장소를_만든다(
        슬래시_자리,
        '"앞 문단의 마지막 줄 끝 경로처럼 보이는 낱말들이 이어진다"\n',
        원천="앞 문단의 마지막 줄 끝\n// 경로처럼 보이는 낱말들이 이어진다",
    )
    assert check([슬래시_줄과_이어진_인용], 슬래시_자리).warnings == []

    # 같은 사본은 감긴 문장과 서로 무관한 이웃 줄을 가르지 못해, 한 줄의 끝과 다음 줄의 머리를
    # 잇는다.
    이웃_자리 = tmp_path / "이웃"
    이웃_자리.mkdir()
    이웃_줄이_이어진_인용 = _저장소를_만든다(
        이웃_자리,
        '"다른 이야기로 끝나고 무관한 이야기로 시작한다"\n',
        원천="첫 줄은 다른 이야기로 끝나고\n무관한 이야기로 시작한다 둘째 줄은",
    )
    assert check([이웃_줄이_이어진_인용], 이웃_자리).warnings == []


def test_이_저장소_전체를_돌려도_끝난다() -> None:
    """경고 수는 고정하지 않는다 — 경고만 내는 검사라 초록의 기준이 없다. 다 읽었는지만 본다."""
    files = default_files(ROOT)

    assert files
    assert all("/.claude/skills/" not in path.as_posix() for path in files)
    assert check(files, ROOT).files_read == len(files)


def test_CLI_진입점이_알려진_빨강을_출력한다(tmp_path: Path) -> None:
    """순수 함수만 재면 main 의 배관이 조용히 비어도 초록이다(corpus 키 중복, 2026-09-28)."""
    없는_말 = "저장소 어디에도 없는 " + "시험용 인용문이다 정말로 " * 2
    doc = tmp_path / "note.md"
    doc.write_text(f'감사가 말한 "{없는_말.strip()}"이라는 말.\n', encoding="utf-8")

    process = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_quotes.py"), "--all-lines", str(doc)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )

    assert process.returncode == 0
    assert "글자 그대로 없다" in process.stdout


def test_CLI_는_경고가_없어도_본_인용_수를_출력한다(tmp_path: Path) -> None:
    """무출력 초록은 '다 맞았다'와 '아무것도 안 봤다'를 가르지 못한다(대기열 55)."""
    문장 = "같은 파일 안에서 두 번 적힌 문장이라 원문을 찾는 인용이다"
    doc = tmp_path / "note.md"
    doc.write_text(f'{문장}\n\n다시 "{문장}"를 든다.\n', encoding="utf-8")
    없는_파일 = tmp_path / "없는.md"

    process = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_quotes.py"), str(doc), str(없는_파일)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )

    assert process.returncode == 0
    # 넘긴 인자는 둘이지만 읽은 파일은 하나다. 저장소 밖이라 diff 가 없어 전체를 봤다.
    assert "파일 1개(그중 전체를 본 것 1개)에서 인용 1건" in process.stdout
    assert "경고 없음" in process.stdout


def _멈춘_git(seen: list[object]) -> Callable[..., subprocess.CompletedProcess[bytes]]:
    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[bytes]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, 1)

    return stuck


def test_git_목록이_시간을_넘기면_저장소_밖처럼_트리를_걷는다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """넘김은 git 이 실패한 갈래로 센다(대기열 342)."""
    (tmp_path / "a.md").write_text("본문\n", encoding="utf-8")
    seen: list[object] = []
    monkeypatch.setattr(subprocess, "run", _멈춘_git(seen))

    assert tracked_text_files(tmp_path) == [tmp_path / "a.md"]
    assert seen == [CALL_TIMEOUT]


def test_git_diff_가_시간을_넘기면_전체를_본다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    (tmp_path / "a.md").write_text("본문\n", encoding="utf-8")
    seen: list[object] = []
    monkeypatch.setattr(subprocess, "run", _멈춘_git(seen))

    assert added_lines(tmp_path / "a.md", tmp_path) is None
    assert seen == [CALL_TIMEOUT]
