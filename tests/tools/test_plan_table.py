"""전체 계획 도구(`tools/plan_table.py`)의 임시 폴더 시험.

도구는 기능 계획(`.scratch/<slug>/plan.md`)과 티켓과 손 파일(`.scratch/plan-head.md`)에서
`.scratch/plan.md`를 만든다(agent-os ADR 0045 결정 3). 상태를 정하는 규칙마다 사례 하나, 순서,
프론티어, 이스케이프, 깨진 기능 계획의 종료 2, 병합 충돌 표지가 든 생성 파일 곁의 쓰기를 임시 폴더에
깔아 본다. 저장소 자신의 표가 최신인지는 `tests/test_plan_status.py`가 본다.
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

from tools import plan_table

ROOT = Path(__file__).resolve().parent.parent.parent
HEAD = "# 전체 계획\n\n손으로 쓴 머리말\n"


def _scratch(root: Path) -> Path:
    scratch = root / ".scratch"
    scratch.mkdir(exist_ok=True)
    if not (scratch / "plan-head.md").exists():
        (scratch / "plan-head.md").write_text(HEAD, encoding="utf-8")
    return scratch


def _feature(
    root: Path,
    slug: str,
    *,
    summary: str = "한 줄 요약",
    slice_no: str | None = "1",
    blocked: str | None = "없음",
    end: str | None = None,
    design: str | None = None,
    tickets: dict[str, str] | None = None,
) -> Path:
    """기능 계획 하나와 티켓들을 깐다. `slice_no`나 `blocked`를 None 으로 주면 그 줄이 빠진다."""
    folder = _scratch(root) / slug
    folder.mkdir(parents=True, exist_ok=True)
    lines = [f"# {slug}: {summary}"]
    if slice_no is not None:
        lines.append(f"**슬라이스:** {slice_no}")
    if blocked is not None:
        lines.append(f"**Blocked by:** {blocked}")
    if design is not None:
        lines.append(f"**설계:** {design}")
    if end is not None:
        lines.append(f"**끝:** {end}")
    lines += ["", "본문은 표에 들지 않는다.", ""]
    plan = folder / "plan.md"
    plan.write_text("\n".join(lines), encoding="utf-8")
    for name, status in (tickets or {}).items():
        issues = folder / "issues"
        issues.mkdir(exist_ok=True)
        (issues / name).write_text(f"# {name}\n\n**Status:** {status}\n", encoding="utf-8")
    return plan


def _generate(root: Path) -> str:
    code = plan_table.main(["--root", str(root)])
    assert code == 0
    return (root / ".scratch" / "plan.md").read_text(encoding="utf-8")


def _rows(text: str) -> list[list[str]]:
    rows = [line for line in text.splitlines() if line.startswith("| ") and "---" not in line]
    return [[cell.strip() for cell in line.strip("|").split(" | ")] for line in rows[1:]]


def _status_of(root: Path, slug: str) -> str:
    for cells in _rows(_generate(root)):
        if f"[{slug}](" in cells[1]:
            return cells[4]
    raise AssertionError(f"{slug} 행이 없다")


def test_끝_줄이_있으면_done이다(tmp_path: Path) -> None:
    _feature(tmp_path, "a", end="2026-11-01", tickets={"01-x.md": "ready-for-agent"})

    assert _status_of(tmp_path, "a") == "done"


def test_done_티켓만_있으면_in_progress다(tmp_path: Path) -> None:
    _feature(tmp_path, "a", tickets={"01-x.md": "done", "02-y.md": "ready-for-agent"})

    assert _status_of(tmp_path, "a") == "in-progress"


def test_아무것도_없으면_todo다(tmp_path: Path) -> None:
    _feature(tmp_path, "a")
    _feature(tmp_path, "b", tickets={"01-x.md": "ready-for-agent", "02-y.md": "in-progress"})

    assert _status_of(tmp_path, "a") == "todo"
    assert _status_of(tmp_path, "b") == "todo"


def test_끝_줄이_있는_기능의_열린_고침_티켓은_done을_바꾸지_않는다(tmp_path: Path) -> None:
    _feature(
        tmp_path,
        "a",
        end="2026-11-01",
        tickets={"01-x.md": "done", "02-fix.md": "ready-for-agent"},
    )

    assert _status_of(tmp_path, "a") == "done"


def test_티켓이_모두_닫혔어도_끝_줄이_없으면_in_progress다(tmp_path: Path) -> None:
    """끝 줄을 막는 일은 저장소 상태 시험의 몫이고 도구는 상태를 끝 줄에서만 읽는다."""
    _feature(tmp_path, "a", tickets={"01-x.md": "done", "02-y.md": "wontfix"})

    assert _status_of(tmp_path, "a") == "in-progress"


def test_티켓의_Status_줄은_굵은_꼴과_맨_꼴을_모두_읽는다(tmp_path: Path) -> None:
    _feature(tmp_path, "a")
    issues = tmp_path / ".scratch" / "a" / "issues"
    issues.mkdir()
    (issues / "01-x.md").write_text("# x\n\nStatus: done (2026-11-01 설명)\n", encoding="utf-8")

    assert _status_of(tmp_path, "a") == "in-progress"


def test_막는_기능은_Blocked_by_칸에_적힌_그대로_적힌다(tmp_path: Path) -> None:
    _feature(tmp_path, "a", end="2026-11-01")
    _feature(tmp_path, "core")
    _feature(tmp_path, "b", slice_no="2", blocked="a, core")

    row = next(cells for cells in _rows(_generate(tmp_path)) if "[b](" in cells[1])

    assert row[3] == "a, core"
    assert row[1] == "[b](b/plan.md)"
    assert row[2] == "한 줄 요약"


def test_행은_슬라이스_숫자_순_그다음_slug_순이다(tmp_path: Path) -> None:
    _feature(tmp_path, "zeta", slice_no="2")
    _feature(tmp_path, "alpha", slice_no="10")
    _feature(tmp_path, "beta", slice_no="2")
    _feature(tmp_path, "omega", slice_no="1")

    slugs = [cells[1] for cells in _rows(_generate(tmp_path))]

    assert slugs == [
        "[omega](omega/plan.md)",
        "[beta](beta/plan.md)",
        "[zeta](zeta/plan.md)",
        "[alpha](alpha/plan.md)",
    ]


def test_요약의_파이프는_이스케이프한다(tmp_path: Path) -> None:
    _feature(tmp_path, "a", summary="발급자|sub 를 묶는다")

    text = _generate(tmp_path)

    assert "| 발급자\\|sub 를 묶는다 |" in text


def test_슬라이스_줄이_없는_기능_계획은_표에_들지_않는다(tmp_path: Path) -> None:
    _feature(tmp_path, "product")
    _feature(tmp_path, "harness-feature", slice_no=None, blocked=None)

    text = _generate(tmp_path)

    assert "harness-feature" not in text
    assert "[product](" in text


def test_첫_줄_뒤에_빈_줄이_끼어도_필드_줄을_읽어_표에_든다(tmp_path: Path) -> None:
    plan = _feature(tmp_path, "a", slice_no="3", end="2026-11-01")
    plan.write_text(plan.read_text(encoding="utf-8").replace("\n", "\n\n", 1), encoding="utf-8")

    row = next(cells for cells in _rows(_generate(tmp_path)) if "[a](" in cells[1])

    assert row[0] == "3"
    assert row[4] == "done"


def test_본문에_적은_끝_줄은_읽지_않는다(tmp_path: Path) -> None:
    plan = _feature(tmp_path, "a")
    plan.write_text(plan.read_text(encoding="utf-8") + "\n**끝:** 2026-11-01\n", encoding="utf-8")

    assert _status_of(tmp_path, "a") == "todo"


def test_설계_줄은_읽지_않고_표에도_싣지_않는다(tmp_path: Path) -> None:
    _feature(tmp_path, "a", design="ADR 0045 결정 4", tickets={"01-x.md": "ready-for-agent"})

    text = _generate(tmp_path)

    assert "ADR 0045" not in text
    assert _status_of(tmp_path, "a") == "todo"


def test_프론티어는_done이_아니고_막는_기능이_모두_done인_기능이다(tmp_path: Path) -> None:
    _feature(tmp_path, "root", end="2026-11-01")
    _feature(tmp_path, "open-root", blocked="없음")
    _feature(tmp_path, "ready", slice_no="2", blocked="root")
    _feature(tmp_path, "waiting", slice_no="2", blocked="open-root, root")
    _feature(tmp_path, "finished", slice_no="2", blocked="root", end="2026-11-02")

    frontier = _section(_generate(tmp_path), "프론티어")

    assert "open-root" in frontier
    assert "ready" in frontier
    assert "waiting" not in frontier
    assert "finished" not in frontier
    assert "`root`" not in frontier


def test_생성_파일_첫_줄은_도구가_만든다는_주석이고_손_파일이_뒤따른다(tmp_path: Path) -> None:
    _feature(tmp_path, "a")

    text = _generate(tmp_path)

    first, _, rest = text.partition("\n")
    assert first.startswith("<!--")
    assert "tools/plan_table.py" in first
    assert rest.startswith("# 전체 계획\n\n손으로 쓴 머리말\n")


def test_check는_쓰지_않고_다르면_1_같으면_0으로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _feature(tmp_path, "a")
    target = tmp_path / ".scratch" / "plan.md"

    assert plan_table.main(["--root", str(tmp_path), "--check"]) == 1
    assert not target.exists()
    assert "plan_table.py" in capsys.readouterr().out

    _generate(tmp_path)
    assert plan_table.main(["--root", str(tmp_path), "--check"]) == 0

    target.write_text(target.read_text(encoding="utf-8") + "손으로 더한 글\n", encoding="utf-8")
    assert plan_table.main(["--root", str(tmp_path), "--check"]) == 1


def test_병합_충돌_표지가_든_생성_파일_곁에서도_같은_파일을_쓴다(tmp_path: Path) -> None:
    _feature(tmp_path, "a")
    target = tmp_path / ".scratch" / "plan.md"
    target.write_text("<<<<<<< HEAD\n| 1 | 옛 |\n=======\n| 1 | 다른 |\n>>>>>>> main\n", "utf-8")

    text = _generate(tmp_path)

    assert "<<<<<<<" not in text
    assert "[a](a/plan.md)" in text


def _broken(tmp_path: Path, capsys: pytest.CaptureFixture[str], expected: str) -> str:
    assert plan_table.main(["--root", str(tmp_path)]) == 2
    out = capsys.readouterr().out
    assert expected in out
    assert not (tmp_path / ".scratch" / "plan.md").exists()
    return out


def test_기능_계획의_줄이_빠지면_경로와_까닭을_찍고_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _feature(tmp_path, "a", blocked=None)

    out = _broken(tmp_path, capsys, "Blocked by")

    assert ".scratch/a/plan.md" in out


def test_slug가_폴더_이름과_다르면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    plan = _feature(tmp_path, "a")
    plan.write_text(plan.read_text(encoding="utf-8").replace("# a:", "# other:"), encoding="utf-8")

    _broken(tmp_path, capsys, "other")


def test_Blocked_by가_없는_기능을_가리키면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _feature(tmp_path, "a", blocked="ghost")

    _broken(tmp_path, capsys, "ghost")


def test_다른_저장소_접두를_단_막는_기능도_없는_기능이라_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    """agent-os 가 따로 적던 `rag-engine:<slug>` 꼴을 rag-engine 은 옮기지 않았다. 그 꼴은
    프론티어 밖의 목록으로 가지 않고 전체 계획에 없는 기능을 가리키는 깨진 입력이다."""
    _feature(tmp_path, "local-done", end="2026-11-01")
    _feature(tmp_path, "remote", slice_no="2", blocked="local-done, rag-engine:core")

    _broken(tmp_path, capsys, "rag-engine:core")


def test_티켓의_상태_값을_모르면_티켓_경로와_함께_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _feature(tmp_path, "a", tickets={"01-x.md": "finished"})

    out = _broken(tmp_path, capsys, "finished")

    assert "01-x.md" in out


def test_티켓에_Status_줄이_없으면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _feature(tmp_path, "a")
    issues = tmp_path / ".scratch" / "a" / "issues"
    issues.mkdir()
    (issues / "01-x.md").write_text("# x\n\n본문만 있다\n", encoding="utf-8")

    _broken(tmp_path, capsys, "01-x.md")


def test_끝_줄의_날짜가_날짜_꼴이_아니면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _feature(tmp_path, "a", end="어제")

    _broken(tmp_path, capsys, "어제")


@pytest.mark.parametrize("value", ["둘", "１"])
def test_슬라이스가_ASCII_숫자가_아니면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str], value: str
) -> None:
    _feature(tmp_path, "a", slice_no=value)

    out = _broken(tmp_path, capsys, value)

    assert ".scratch/a/plan.md" in out


def test_Blocked_by_값이_비었으면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _feature(tmp_path, "a", blocked="")

    _broken(tmp_path, capsys, "Blocked by")


def test_없음을_다른_막는_기능과_함께_적으면_2로_끝난다(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _feature(tmp_path, "root", end="2026-11-01")
    _feature(tmp_path, "a", slice_no="2", blocked="없음, root")

    _broken(tmp_path, capsys, "없음")


# --- 거르지 않는다고 독스트링이 적은 입력(못 보는 것). 거르게 바꾸면 이 시험을 함께 고친다 ---


def test_자기_자신을_막는_기능은_오류_없이_어느_목록에도_들지_않는다(tmp_path: Path) -> None:
    _feature(tmp_path, "loop", blocked="loop")

    text = _generate(tmp_path)

    assert "loop" not in _section(text, "프론티어")


def test_서로_막는_두_기능은_오류_없이_어느_목록에도_들지_않는다(tmp_path: Path) -> None:
    _feature(tmp_path, "left", blocked="right")
    _feature(tmp_path, "right", blocked="left")

    text = _generate(tmp_path)

    assert "left" not in _section(text, "프론티어")
    assert "right" not in _section(text, "프론티어")


def test_달력에_없는_끝_날짜도_꼴만_맞으면_done으로_읽는다(tmp_path: Path) -> None:
    _feature(tmp_path, "a", end="2026-13-99")

    assert _status_of(tmp_path, "a") == "done"


def test_슬라이스_키의_철자가_틀린_기능은_오류_없이_표에서_빠진다(tmp_path: Path) -> None:
    plan = _feature(tmp_path, "typo")
    plan.write_text(
        plan.read_text(encoding="utf-8").replace("**슬라이스:**", "**슬라이드:**"), "utf-8"
    )
    _feature(tmp_path, "other")

    text = _generate(tmp_path)

    assert "[typo](" not in text
    assert "[other](" in text


def test_티켓이_모두_wontfix이고_끝_줄이_없으면_todo로_프론티어에_남는다(tmp_path: Path) -> None:
    _feature(tmp_path, "dropped", tickets={"01-x.md": "wontfix"})

    text = _generate(tmp_path)

    assert _status_of(tmp_path, "dropped") == "todo"
    assert "dropped" in _section(text, "프론티어")


def test_손_파일이_없으면_2로_끝난다(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    folder = tmp_path / ".scratch" / "a"
    folder.mkdir(parents=True)
    (folder / "plan.md").write_text("# a: 요약\n**슬라이스:** 1\n**Blocked by:** 없음\n", "utf-8")

    _broken(tmp_path, capsys, "plan-head.md")


def test_CLI_진입점이_스크립트로_돌아_파일을_쓴다(tmp_path: Path) -> None:
    """`uv run python tools/plan_table.py` 로 부르는 길에서 import 가 풀리는지 본다."""
    _feature(tmp_path, "a")

    result = subprocess.run(
        [sys.executable, str(ROOT / "tools" / "plan_table.py"), "--root", str(tmp_path)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=60,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "[a](a/plan.md)" in (tmp_path / ".scratch" / "plan.md").read_text(encoding="utf-8")


def _section(text: str, title: str) -> str:
    """`## <title>` 아래부터 다음 `## ` 앞까지."""
    _, _, after = text.partition(f"## {title}\n")
    assert after, f"{title} 절이 없다"
    return after.split("\n## ", 1)[0]
