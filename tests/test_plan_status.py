"""전체 계획 `.scratch/plan.md`의 저장소 상태 시험 둘(ADR 0045 결정 3·10).

하나는 생성 파일 대조다. `.scratch/plan.md`는 도구 `tools/plan_table.py`가 기능 계획
(`.scratch/<slug>/plan.md`)과 티켓과 손 파일(`.scratch/plan-head.md`)에서 만든다. 디스크에서 만든
표와 커밋한 파일이 글자 그대로 같지 않으면 빨갛고, 실패 문장이 도구 명령과 손으로 고칠 자리를 알려
준다. 선례는 `tests/tools/test_export_openapi.py`다. 기능의 상태는 사람이 바꾸지 않고 도구가 끝 줄과
티켓에서 읽으므로, 상태가 티켓과 어긋나는 일은 이 대조가 함께 막는다(옛 시험이 막던 일이다. 첫
티켓이 병합됐는데 행이 todo 였던 사건 등, 대기열 546).

다른 하나는 끝 줄 시험이다. 기능 계획의 폴더 `issues/`에 든 티켓이 모두 닫혔고(`done` 또는
`wontfix`) `done`이 하나 이상인데 `**끝:**` 줄이 없으면 빨갛다. 기능의 마지막 티켓을 닫는 커밋이 그
줄을 적는다(빠뜨리면 그 커밋의 pre-commit 이 막는다). 나란히 돈 마지막 티켓 둘은 main 보호가
strict 라 늦게 병합되는 PR 이 main 을 합친 뒤의 CI 에서 막히고 그 PR 이 적는다. 규칙의 원천은
`docs/agents/issue-tracker.md`의 전체 계획 절이다.

막지 못하는 것: 관리자 우회 병합과 main 직접 푸시(그 뒤로는 main 의 push CI 와 뒤따르는 PR 이 모두
빨갛다). 끝 줄을 보지 않는 것: `**슬라이스:**` 줄이 없는 기능 계획(하네스 기능은 티켓이 모두
done 이면 끝난 것이다, ADR 0037)과 기능 계획이 없는 폴더. done 티켓이 하나도 없이 닫힌 기능도 보지
않는다. `끝` 줄이 있는데 열린 티켓이 있는 기능은 정상이다. 기능 밖에서 제품 코드를 고치는 일은 그
기능 폴더의 새 티켓으로 더하고 상태는 done 그대로 두기 때문이다(`docs/agents/issue-tracker.md`).
"""

from __future__ import annotations

import datetime
from pathlib import Path

from tools import plan_table

ROOT = Path(__file__).resolve().parent.parent
PLAN = ROOT / ".scratch" / "plan.md"
CLOSED = frozenset({"done", "wontfix"})
COMMAND = "uv run python tools/plan_table.py"


def drift_message(root: Path) -> str | None:
    """커밋한 `.scratch/plan.md`가 디스크에서 만든 표와 다르면 실패 문장, 같으면 None."""
    committed = root / ".scratch" / "plan.md"
    current = committed.read_text(encoding="utf-8") if committed.is_file() else None
    if current == plan_table.render(root):
        return None
    return (
        ".scratch/plan.md가 기능 계획과 티켓에서 만든 표와 다르다. "
        f"`{COMMAND}`를 쳐서 다시 만들고 같은 커밋에 싣는다. "
        "손으로 고칠 글은 기능 계획(`.scratch/<slug>/plan.md`)이나 `.scratch/plan-head.md`에 있다."
    )


def end_line_problems(root: Path, today: str) -> list[str]:
    """티켓이 모두 닫혔고 done 이 하나 이상인데 `**끝:**` 줄이 없는 기능 계획의 실패 문장."""
    problems: list[str] = []
    for feature in plan_table.features(root):
        closed = bool(feature.tickets) and all(value in CLOSED for value in feature.tickets)
        if closed and "done" in feature.tickets and feature.end is None:
            path = f".scratch/{feature.slug}/plan.md"
            problems.append(
                f"`{path}`의 티켓이 모두 닫혔는데 `**끝:**` 줄이 없다. 마지막 티켓을 닫는 "
                f"커밋에서 그 파일에 `**끝:** {today}`(그 커밋의 로컬 날짜)를 적고 "
                f"`{COMMAND}`를 돈다. 규칙은 `docs/agents/issue-tracker.md`의 전체 계획 절에 "
                "있다."
            )
    return problems


# --- 이 저장소 -----------------------------------------------------------------------


def test_이_저장소의_전체_계획은_기능_계획과_티켓에서_만든_표와_같다() -> None:
    assert drift_message(ROOT) is None, drift_message(ROOT)


def test_이_저장소에서_기능_계획과_끝_줄을_하나는_읽는다() -> None:
    """읽은 것이 없는데 어긋남 0 으로 초록이 되는 것을 막는다(tests.md, 대기열 98)."""
    found = plan_table.features(ROOT)

    assert found, ".scratch/*/plan.md 에서 읽은 기능 없음"
    # rag-engine 킥오프(2026-11-09)에는 끝난 기능도 done 티켓도 아직 없어, agent-os 의 두 단언
    # ("끝 줄이 있는 기능 없음", "done 티켓이 있는 기능 없음")을 뺐다. 첫 기능을 닫는 커밋이
    # 되살린다
    rows = [line for line in PLAN.read_text(encoding="utf-8").splitlines() if line.startswith("| ")]
    assert len(rows) - 1 == len(found), "표 행 수가 읽은 기능 수와 다르다"


def test_이_저장소의_기능_계획은_티켓이_모두_닫히면_끝_줄을_든다() -> None:
    today = datetime.datetime.now(tz=datetime.UTC).astimezone().date().isoformat()

    assert end_line_problems(ROOT, today) == []


# --- 임시 폴더 -----------------------------------------------------------------------


def _feature(root: Path, slug: str, *, end: str | None, tickets: dict[str, str]) -> None:
    scratch = root / ".scratch"
    folder = scratch / slug
    (folder / "issues").mkdir(parents=True, exist_ok=True)
    (scratch / "plan-head.md").write_text("# 전체 계획\n", encoding="utf-8")
    lines = [f"# {slug}: 요약", "**슬라이스:** 1", "**Blocked by:** 없음"]
    if end is not None:
        lines.append(f"**끝:** {end}")
    (folder / "plan.md").write_text("\n".join([*lines, "", "본문", ""]), encoding="utf-8")
    for name, status in tickets.items():
        (folder / "issues" / name).write_text(f"# t\n\n**Status:** {status}\n", encoding="utf-8")


def test_마지막_티켓이_done인데_끝_줄이_없으면_빨갛다(tmp_path: Path) -> None:
    _feature(tmp_path, "feat", end=None, tickets={"01-a.md": "done", "02-b.md": "done"})

    problems = end_line_problems(tmp_path, "2026-11-07")

    assert len(problems) == 1
    assert ".scratch/feat/plan.md" in problems[0]
    assert "**끝:** 2026-11-07" in problems[0]
    assert "docs/agents/issue-tracker.md" in problems[0]


def test_끝_줄이_있으면_초록이다(tmp_path: Path) -> None:
    _feature(tmp_path, "feat", end="2026-11-07", tickets={"01-a.md": "done"})

    assert end_line_problems(tmp_path, "2026-11-07") == []


def test_마지막_티켓을_wontfix로_닫아도_done이_하나_이상이면_빨갛다(tmp_path: Path) -> None:
    _feature(tmp_path, "feat", end=None, tickets={"01-a.md": "done", "02-b.md": "wontfix"})

    assert len(end_line_problems(tmp_path, "2026-11-07")) == 1


def test_done이_하나도_없이_닫힌_기능은_끝_줄을_요구하지_않는다(tmp_path: Path) -> None:
    _feature(tmp_path, "feat", end=None, tickets={"01-a.md": "wontfix"})

    assert end_line_problems(tmp_path, "2026-11-07") == []


def test_끝_줄이_있는_기능의_열린_고침_티켓은_초록이다(tmp_path: Path) -> None:
    _feature(
        tmp_path,
        "feat",
        end="2026-11-07",
        tickets={"01-a.md": "done", "02-fix.md": "ready-for-agent"},
    )

    assert end_line_problems(tmp_path, "2026-11-07") == []


def test_티켓이_모두_열린_기능은_초록이다(tmp_path: Path) -> None:
    _feature(tmp_path, "feat", end=None, tickets={"01-a.md": "ready-for-agent"})
    _feature(tmp_path, "other", end=None, tickets={"01-a.md": "done", "02-b.md": "in-progress"})

    assert end_line_problems(tmp_path, "2026-11-07") == []


def test_슬라이스_줄이_없는_기능_계획은_보지_않는다(tmp_path: Path) -> None:
    _feature(tmp_path, "harnessy", end=None, tickets={"01-a.md": "done"})
    plan = tmp_path / ".scratch" / "harnessy" / "plan.md"
    plan.write_text(
        plan.read_text(encoding="utf-8").replace("**슬라이스:** 1\n", ""), encoding="utf-8"
    )

    assert end_line_problems(tmp_path, "2026-11-07") == []


def test_기능_계획이_없는_폴더는_보지_않는다(tmp_path: Path) -> None:
    _feature(tmp_path, "feat", end="2026-11-07", tickets={"01-a.md": "done"})
    orphan = tmp_path / ".scratch" / "orphan" / "issues"
    orphan.mkdir(parents=True)
    (orphan / "01-a.md").write_text("# t\n\n**Status:** done\n", encoding="utf-8")

    assert end_line_problems(tmp_path, "2026-11-07") == []


def test_생성_파일이_없거나_다르면_실패_문장이_명령과_고칠_자리를_알려_준다(
    tmp_path: Path,
) -> None:
    _feature(tmp_path, "feat", end=None, tickets={})

    missing = drift_message(tmp_path)
    assert missing is not None
    assert COMMAND in missing
    assert "같은 커밋" in missing
    assert ".scratch/<slug>/plan.md" in missing
    assert ".scratch/plan-head.md" in missing

    assert plan_table.main(["--root", str(tmp_path)]) == 0
    assert drift_message(tmp_path) is None

    (tmp_path / ".scratch" / "feat" / "plan.md").write_text(
        "# feat: 다른 요약\n**슬라이스:** 1\n**Blocked by:** 없음\n", encoding="utf-8"
    )
    assert drift_message(tmp_path) is not None


def test_티켓_상태를_바꾸고_도구를_잊으면_생성_파일_대조가_잡는다(tmp_path: Path) -> None:
    """옛 시험이 막던 사건(첫 티켓이 병합됐는데 행이 todo)이 생성 파일 대조로 막힌다."""
    _feature(tmp_path, "feat", end=None, tickets={"01-a.md": "ready-for-agent"})
    assert plan_table.main(["--root", str(tmp_path)]) == 0
    assert drift_message(tmp_path) is None

    ticket = tmp_path / ".scratch" / "feat" / "issues" / "01-a.md"
    ticket.write_text("# t\n\n**Status:** done\n", encoding="utf-8")

    assert drift_message(tmp_path) is not None
