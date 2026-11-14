"""전체 계획(`.scratch/plan.md`)을 기능 계획과 티켓과 손 파일에서 만드는 도구(agent-os ADR 0045
결정 3에서 옮겼다. 규칙의 원천은 `docs/agents/issue-tracker.md` 의 전체 계획 절).

    uv run python tools/plan_table.py            # `.scratch/plan.md`를 쓴다
    uv run python tools/plan_table.py --check    # 쓰지 않고, 디스크에서 만든 결과가 커밋할 파일과
                                                 # 다르면 1로 끝난다
    uv run python tools/plan_table.py --root <폴더>   # 그 폴더를 저장소 루트로 본다(시험이 쓴다)

기능 계획, 손 파일, 티켓의 상태를 고친 세션이 이 도구를 손으로 돌리고 결과를 같은 커밋에 싣는다.
잊으면 `tests/test_plan_status.py`의 저장소 대조 시험이 빨개지고 그 실패 문장이 이 명령을 알려
준다. pre-commit 훅이 다시 쓰게 하지는 않는다. 세션이 모르는 사이 표가 바뀌기 때문이다. 이
파일의 병합 충돌은 이 도구를 다시 돌려 푼다. 생성 파일은 읽지 않으므로 충돌 표지가 든 채로도 돈다.

입력.
- 손 파일 `.scratch/plan-head.md`: 표 밖의 글(제목, 머리말, 목표 배치, 첫 슬라이스의 범위). 생성
  파일의 주석 줄 뒤에 그대로 붙는다.
- 기능 계획 `.scratch/<slug>/plan.md`: 첫 줄 `# <slug>: <한 줄 요약>`(slug는 폴더 이름), 이어서
  첫 문단(바로 뒤의 빈 줄은 건너뛴다)에 `**슬라이스:** N`, `**Blocked by:** <slug>, …`(없으면
  `없음`), 있을 때만 `**설계:** …`과 `**끝:** YYYY-MM-DD`.
  그 뒤 본문은 표에 들지 않는다. `**슬라이스:**` 줄이 없는 기능 계획(하네스 기능)은 전체 계획에 들지
  않는다.
- 티켓 `.scratch/<slug>/issues/*.md`: 상태는 줄 머리가 `Status:` 나 `**Status:**` 인 첫 줄의 첫
  낱말이다(`tools/check_ticket.py`의 `status_of`, 커밋 검사와 같은 규칙 하나).

판정.
- 상태: `**끝:**` 줄이 있으면 done, 없고 그 폴더 티켓에 done 이 있으면 in-progress, 아니면 todo.
  티켓이 모두 닫혔는데 끝 줄이 없는 모양을 막는 일은 저장소 상태 시험의 몫이다.
- 행 순서: 슬라이스 번호의 숫자 순, 그다음 slug 순.
- 프론티어: done 이 아니고, Blocked by 가 비었거나 막는 기능이 모두 done 인 기능. Blocked by 는
  이 저장소의 기능만 가리킨다. agent-os 가 문서 검색 서버(이 저장소)의 기능을 가리키던
  `rag-engine:<slug>` 접두와 "다른 저장소를 기다리는 기능" 절은 옮기지 않았고, 그 꼴은 없는 기능을
  가리키는 Blocked by 로 깨진 입력이다. 다른 저장소의 일을 기다리는 기능은 기능 계획 본문에 그
  대기를 적는다(release-image).
- 종료 코드: 쓰기는 0. `--check` 는 같으면 0, 다르면 1. 기능 계획이나 티켓이 깨졌으면 그 경로와
  까닭을 찍고 2. 깨진 입력은 `PlanError` 를 내는 자리 모두다(첫 줄 꼴, slug 불일치, 슬라이스가
  숫자가 아님, Blocked by 줄 없음·비어 있음·`없음`과 다른 항목의 혼용, 없는 기능을 가리키는 Blocked
  by, 끝 날짜의 꼴, 티켓의 `Status:` 줄 없음·모르는 값, 손 파일 없음).

못 보는 것. 기능 계획 본문의 내용, 티켓 본문의 수용 기준, 설계 줄이 가리키는 ADR 이나 일지가
있는지는 보지 않는다. `**설계:**` 줄은 읽지 않고 표에 싣지도 않는다(설계 인터뷰의 계기를 가르는
표지라서, 읽는 쪽은 설계 인터뷰를 도는 모델과 스킬이다. `hook_grill_design_check` 는 파일을 열지
않고 호출마다 같은 문장을 낸다). 필드 줄은 첫 줄 뒤의 첫 문단에서만 읽어서 본문에 적은 `**끝:**`
줄은 무시한다. 키의 철자가 틀려 `**슬라이스:**` 줄이 없어지면 하네스 기능으로 읽혀 오류 없이
표에서 빠진다. 자기 자신이나 서로를 막는 순환 Blocked by 와 달력에 없는 끝 날짜(`2026-13-99`)는
거르지 않는다.
"""

from __future__ import annotations

import argparse
import re
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path

if __package__ in (None, ""):  # 스크립트로 부르면 저장소 루트가 import 경로에 없다
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from tools.check_ticket import status_of  # noqa: E402

SCRATCH = ".scratch"
PLAN = "plan.md"
HEAD = "plan-head.md"
TOOL = "tools/plan_table.py"
NONE = "없음"
BANNER = (
    "<!-- 이 파일은 도구가 만든다. 기능 계획(`.scratch/<slug>/plan.md`)이나 "
    f"`.scratch/plan-head.md`를 고치고 `uv run python {TOOL}`를 돌린다. -->"
)
HEADER = "| 슬라이스 | 기능 | 내용 | Blocked by | Status |"
TICKET_STATUSES = frozenset({"ready-for-agent", "in-progress", "done", "wontfix"})

_TITLE = re.compile(r"^# (?P<slug>[^:\s]+): (?P<summary>\S.*)$")
_FIELD = re.compile(r"^\*\*(?P<key>[^*:]+):\*\* ?(?P<value>.*)$")
_DATE = re.compile(r"^\d{4}-\d{2}-\d{2}$")


class PlanError(Exception):
    """기능 계획이나 티켓이 깨졌다. 종료 코드 2 로 경로와 까닭을 찍는다."""

    def __init__(self, path: str, reason: str) -> None:
        super().__init__(f"{path}: {reason}")


@dataclass(frozen=True)
class Feature:
    slug: str
    summary: str
    slice_no: int
    blocked: tuple[str, ...]
    end: str | None
    status: str
    tickets: tuple[str, ...]


def _rel(root: Path, path: Path) -> str:
    return path.relative_to(root).as_posix()


def _fields(text: str) -> dict[str, str]:
    """첫 줄 뒤의 첫 문단(첫 줄 바로 뒤의 빈 줄은 건너뛴다)에 든 `**키:** 값` 줄."""
    fields: dict[str, str] = {}
    lines = text.splitlines()[1:]
    start = next((index for index, line in enumerate(lines) if line.strip()), len(lines))
    for line in lines[start:]:
        if not line.strip():
            break
        match = _FIELD.match(line)
        if match is not None:
            fields.setdefault(match["key"], match["value"].strip())
    return fields


def _ticket_state(root: Path, folder: Path) -> list[str]:
    """그 폴더 `issues/*.md` 의 상태 값. 줄이 없거나 모르는 값이면 PlanError."""
    values: list[str] = []
    for ticket in sorted((folder / "issues").glob("*.md")):
        value = status_of(ticket.read_text(encoding="utf-8"))
        where = _rel(root, ticket)
        if value is None:
            raise PlanError(where, "`Status:` 줄이 없다")
        if value not in TICKET_STATUSES:
            raise PlanError(where, f"티켓의 상태 `{value}`를 모른다")
        values.append(value)
    return values


def _parse(root: Path, plan: Path) -> Feature | None:
    """기능 계획 하나. `**슬라이스:**` 줄이 없는 하네스 기능이면 None."""
    where = _rel(root, plan)
    text = plan.read_text(encoding="utf-8")
    title = _TITLE.match(text.splitlines()[0] if text else "")
    if title is None:
        raise PlanError(where, "첫 줄이 `# <slug>: <한 줄 요약>` 꼴이 아니다")
    if title["slug"] != plan.parent.name:
        raise PlanError(where, f"slug `{title['slug']}`가 폴더 이름 `{plan.parent.name}`과 다르다")
    fields = _fields(text)
    if "슬라이스" not in fields:
        return None
    slice_text = fields["슬라이스"]
    if not slice_text.isascii() or not slice_text.isdigit():
        raise PlanError(where, f"`**슬라이스:**` 값 `{slice_text}`이 숫자가 아니다")
    if "Blocked by" not in fields or not fields["Blocked by"]:
        raise PlanError(where, "`**Blocked by:**` 줄이 없거나 비었다(없으면 `없음`)")
    end = fields.get("끝")
    if end is not None and _DATE.match(end) is None:
        raise PlanError(where, f"`**끝:**` 값 `{end}`이 YYYY-MM-DD 꼴이 아니다")
    blocked = tuple(item.strip() for item in fields["Blocked by"].split(","))
    if NONE in blocked and blocked != (NONE,):
        raise PlanError(where, "`없음`은 다른 막는 기능과 함께 적지 않는다")
    values = _ticket_state(root, plan.parent)
    status = "done" if end else ("in-progress" if "done" in values else "todo")
    return Feature(
        title["slug"],
        title["summary"],
        int(slice_text),
        () if blocked == (NONE,) else blocked,
        end,
        status,
        tuple(values),
    )


def features(root: Path) -> list[Feature]:
    """전체 계획에 드는 기능, 슬라이스 숫자 순 그다음 slug 순."""
    found: list[Feature] = []
    for plan in sorted((root / SCRATCH).glob(f"*/{PLAN}")):
        feature = _parse(root, plan)
        if feature is not None:
            found.append(feature)
    known = {feature.slug for feature in found}
    for feature, plan in ((f, root / SCRATCH / f.slug / PLAN) for f in found):
        for item in feature.blocked:
            if item not in known:
                raise PlanError(
                    _rel(root, plan), f"Blocked by `{item}`는 전체 계획에 든 기능이 아니다"
                )
    return sorted(found, key=lambda feature: (feature.slice_no, feature.slug))


def _cell(text: str) -> str:
    return text.replace("|", "\\|")


def _row(feature: Feature) -> str:
    blocked = ", ".join(feature.blocked) if feature.blocked else NONE
    return (
        f"| {feature.slice_no} | [{feature.slug}]({feature.slug}/{PLAN}) | "
        f"{_cell(feature.summary)} | {blocked} | {feature.status} |"
    )


def _frontier(found: Sequence[Feature]) -> list[str]:
    """done 이 아니고 막는 기능이 모두 done 인 기능."""
    done = {feature.slug for feature in found if feature.status == "done"}
    return [
        feature.slug
        for feature in found
        if feature.status != "done" and all(item in done for item in feature.blocked)
    ]


def _list(slugs: Sequence[str]) -> str:
    return ", ".join(f"`{slug}`" for slug in slugs) if slugs else "(없음)"


def render(root: Path) -> str:
    """디스크의 손 파일과 기능 계획과 티켓에서 만든 `.scratch/plan.md` 의 글."""
    head_path = root / SCRATCH / HEAD
    if not head_path.is_file():
        raise PlanError(_rel(root, head_path), "손 파일이 없다")
    found = features(root)
    frontier = _frontier(found)
    head = head_path.read_text(encoding="utf-8").rstrip("\n")
    parts = [
        BANNER,
        head,
        "",
        HEADER,
        "|---|---|---|---|---|",
        *(_row(feature) for feature in found),
        "",
        "## 프론티어",
        "",
        "done 이 아니고, Blocked by 가 비었거나 막는 기능이 모두 done 인 기능이다. "
        f"{_list(frontier)}",
        "",
    ]
    return "\n".join(parts)


def main(argv: Sequence[str]) -> int:
    parser = argparse.ArgumentParser(
        prog=TOOL, description="전체 계획을 기능 계획과 티켓에서 만든다"
    )
    parser.add_argument("--check", action="store_true", help="쓰지 않고 커밋할 파일과 견준다")
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parent.parent)
    args = parser.parse_args(list(argv))
    root: Path = args.root
    try:
        text = render(root)
    except PlanError as error:
        print(f"{TOOL}: {error}")
        return 2
    target = root / SCRATCH / PLAN
    if args.check:
        current = target.read_text(encoding="utf-8") if target.is_file() else None
        if current == text:
            return 0
        print(
            f"{SCRATCH}/{PLAN}가 기능 계획과 티켓에서 만든 표와 다르다. "
            f"`uv run python {TOOL}`를 쳐서 다시 만들고 같은 커밋에 싣는다."
        )
        return 1
    target.write_text(text, encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
