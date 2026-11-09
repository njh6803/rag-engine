"""헌법 파일을 고친 가지가 헌법의 판을 올렸는지 커밋 전에 본다(대기열 31).

`principles.md` 거버넌스는 헌법 파일의 어느 변경이든 판을 올리라고 적는데, 그 문장이 있는데도 PR
열하나(#19~#50)가 판을 올리지 않았다(일지 2026-09-25-01). `tools/sibling_overlap.py` 가 같은 판정을
알림(종료 1)으로 내지만(대기열 224) 막지는 않는다. 이 검사는 pre-commit 에서 막는다.

사용: uv run python -m tools.check_constitution_version [저장소 루트]
      (`tools.sibling_overlap` 을 import 해서 `-m` 으로 띄운다. 루트를 주지 않으면 이 도구의
      체크아웃)

판정. 커밋에 들 판(색인)의 헌법 파일(`principles.md`·`tech.md`·`operations.md`) 가운데 이 가지가
고친 것이 있으면, 색인의 헌법 README(`docs/constitution/README.md`)의 판이 `origin/main` 의 판과도
merge-base 의 판과도 달라야 한다. 이 가지가 고친 파일은 merge-base 와 다르고 `origin/main` 과도 다른
것이다. main 과 같은 파일은 main 이 들여온 것이라, main 을 합치는 커밋이 main 의 변경을 이 가지의
것으로 세지 않는다(거르는 규칙은 `tools/sibling_overlap.py` 의 `_own_changes` 와 같고, 그 도구는
작업 트리와 추적하지 않는 파일을, 이 검사는 색인을 견준다). 판 줄이 main 이나
merge-base 의 것이어도, 판 줄이 main 의 판 줄과 같고 main 의 헌법 README 가 이 가지 몫으로 비워 둔
판의 문장을 이 가지가 지웠으면 그 판으로 올린 것이다(대기열 279, retro-queue-per-item 06,
`reserved_version`). 판은 가지마다 한 번 올리면 되어, 앞 커밋에서
올렸으면 다른 헌법 파일만 고친 뒤 커밋도 지나간다. 형제 가지와 번호가 겹치는지는 보지 않는다. 그것은
`tools/sibling_overlap.py` 가 본다.

종료 코드: 지나가면 0, 판을 올리지 않았으면 1, 판정하지 못했으면(git 저장소 밖, `origin/main` 이
없다, merge-base 가 없는 얕은 클론) 2. pre-commit 에서는 셋째도 막는다. 건너뛰려면
`SKIP=check-constitution-version` 이다.

못 보는 것: 판정이 커밋 단위라, 헌법 파일을 고친 커밋과 판을 올린 커밋을 나누면 가지 전체로는 맞아도
앞 커밋이 막힌다(잘못 막는다, 대기열 31의 자리 후보 (1)). 판을 올리는 문장은 같은 커밋에 둔다. CI 는
이 검사를 돌리지 않는다(pre-commit 에만 있다). 판을 올렸는지는 판 줄이 달라졌는지만 보고,
크기(patch, minor, major)가 맞는지와 판을 올린 까닭을 그 변경의 ADR 이력이나 일지에 적었는지는 보지
않는다(헌법 README 에는 이력 문단이 없다). 헌법 파일을 지우기만 한
커밋은 pre-commit 이 지운 파일을 훅의 `files` 거르기에 넘기지 않아 이 검사가 돌지 않는다(놓친다.
도구를 바로 부르면 막는다). 모든 커밋에 띄우면(`always_run`) 커밋마다 수 초에서 십수 초(이 PC 에서
`uv run` 의 시작까지 손으로 본 값이 4.5~17초, 다른 세션이 함께 돌 때)가 더 들어 두지 않았다.
`origin/main` 은 로컬의 것이라, 받지 않은 main 이 같은 판을 먼저 매겼어도 모른다(놓친다. 합칠 때 판
줄이 겹치고, 형제 번호는 `tools/sibling_overlap.py` 가 본다). 비워 둔 판은 브랜치 이름으로 찾아,
분리 HEAD 에서 비워 둔 판을 쓴 커밋은 막힌다(잘못 막는다. `git rebase --continue` 가 커밋을 옮길
때는 pre-commit 이 돌지 않아, 손으로 분리 HEAD 에서 `git commit` 을 칠 때만 난다).
"""

from __future__ import annotations

import io
import sys
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from pathlib import Path

from tools.sibling_overlap import (
    CONSTITUTION,
    CONSTITUTION_TEXTS,
    MAIN,
    VERSION,
    SurveyError,
    Tree,
    current_branch,
    git,
    merge_base,
    reserved_version,
)

ROOT = Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Judged:
    """판정에 쓰는 것. 판은 `**Version**` 줄의 번호이고 없으면 None 이다."""

    changed: list[str]  # 이 가지가 고친 헌법 파일(색인 기준)
    ours: str | None  # 색인의 판
    main: str | None  # origin/main 의 판
    base: str | None  # merge-base 의 판
    reserved: str | None  # main 이 이 가지 몫으로 비워 둔 판 가운데 이 가지가 문장을 지운 것

    @property
    def passes(self) -> bool:
        """지나간다. 고친 헌법 파일이 없거나, 판 줄이 main 과 merge-base 의 것과 다르거나, 비워 둔
        판을 썼다."""
        if not self.changed:
            return True
        if self.ours is None:
            return False
        return self.ours not in (self.main, self.base) or self.reserved is not None


def _version(text: str) -> str | None:
    found = VERSION.search(text)
    return found.group(1) if found else None


def _index_text(root: Path, path: str) -> str:
    """색인의 그 파일. 색인에 없으면 빈 글이다."""
    if not git(root, "ls-files", "--", path).strip():
        return ""
    return git(root, "show", f":{path}")


def _staged_against(root: Path, commit: str) -> frozenset[str]:
    """색인이 `commit` 과 다른 헌법 파일."""
    listing = git(root, "diff", "--cached", "--name-only", "--no-renames", commit, "--")
    return frozenset(listing.splitlines()) & CONSTITUTION_TEXTS


def judge(root: Path) -> Judged:
    """`root` 의 색인을 `origin/main` 과 merge-base 에 견준다. 판정하지 못하면 `SurveyError`."""
    try:
        git(root, "rev-parse", "--git-dir")
    except SurveyError as error:
        raise SurveyError(f"{root} 가 git 저장소 안이 아니다 ({error})") from error
    try:
        main_sha = git(root, "rev-parse", "--verify", "--quiet", f"{MAIN}^{{commit}}").strip()
    except SurveyError as error:
        raise SurveyError(f"{MAIN} 이 없다. `git fetch origin` 으로 받는다 ({error})") from error
    base = merge_base(root, "HEAD", main_sha)
    if base is None:
        raise SurveyError(
            f"HEAD 와 {MAIN} 의 merge-base 가 없다."
            " 얕은 클론이면 `git fetch --unshallow origin` 으로 이력을 모두 받는다"
        )
    changed = sorted(_staged_against(root, base) & _staged_against(root, main_sha))
    ours_text = _index_text(root, CONSTITUTION)
    main_text = Tree(root, main_sha).text(CONSTITUTION)
    judged = Judged(
        changed,
        _version(ours_text),
        _version(main_text),
        _version(Tree(root, base).text(CONSTITUTION)),
        None,
    )
    if judged.passes:
        return judged
    reserved = reserved_version(current_branch(root), main_text, ours_text)
    return replace(judged, reserved=reserved)


def _report(judged: Judged, out: Callable[[str], None]) -> None:
    if not judged.changed:
        out("헌법 판: 이 가지가 고친 헌법 파일이 없다")
        return
    if judged.passes:
        reserved = f", 비워 둔 판 {judged.reserved}" if judged.reserved is not None else ""
        out(
            f"헌법 판: 이 가지가 고친 헌법 파일 {len(judged.changed)}, 판 {judged.ours}"
            f" ({MAIN} {judged.main}{reserved})"
        )
        return
    out(f"!! 헌법 파일을 고쳤는데 판을 올리지 않았다: {', '.join(judged.changed)}")
    ours = "판 줄이 없다" if judged.ours is None else f"판 {judged.ours}"
    out(f"   {ours} — {MAIN} 의 판 {judged.main}, merge-base 의 판 {judged.base}")
    out(
        f"   {CONSTITUTION} 의 판 줄을 같은 커밋에서 올린다(principles.md 거버넌스의 semver)."
        " 판을 올린 까닭은 이 변경의 ADR 이력이나 일지에 적고 README 에는 적지 않는다."
        " main 이 이 가지 몫으로 비워 둔 판을 쓰려면 판 줄은 main 의 것 그대로 두고 README 에서"
        " 그 비워 둔 문장을 지운다."
        " 형제 가지와 겹치지 않는 번호는 `uv run python tools/sibling_overlap.py` 가 알린다"
    )


def main(argv: Sequence[str], *, out: Callable[[str], None] = print) -> int:
    if len(argv) > 1:
        out("사용: uv run python -m tools.check_constitution_version [저장소 루트]")
        return 2
    root = Path(argv[0]) if argv else ROOT
    try:
        judged = judge(root)
    except SurveyError as error:
        out(
            "헌법 판을 판정하지 못했다(막는다. 건너뛰려면 SKIP=check-constitution-version):"
            f" {error}"
        )
        return 2
    _report(judged, out)
    return 0 if judged.passes else 1


if __name__ == "__main__":
    # pre-commit 훅 환경에 PYTHONUTF8 이 있다고 가정하지 않는다. 없으면 윈도우의 파이프는 cp949 다
    stream = sys.stdout
    if isinstance(stream, io.TextIOWrapper):
        stream.reconfigure(encoding="utf-8")
    raise SystemExit(main(sys.argv[1:]))
