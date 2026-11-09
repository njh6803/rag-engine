"""tools/check_instructions.py 의 검사들. 변이로 본 빨강은 일회성이라 회귀는 여기서 막는다.

`npx skills update -p` 가 덧댄 사본을 되돌리면 리뷰 범위와 반영 절차가 조용히 사라진다. 경로 참조가
아무것도 가리키지 않게 되면 훅은 요란하게, rules 는 조용히 실패한다(PR #52). 문장 속 `@경로` 는 줄
머리의 것과 같은 임포트인데 2026-09-28 까지 검사가 줄 머리만 봤다.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from collections.abc import Callable, Container
from pathlib import Path

import pytest
from tools.check_instructions import (
    CALL_TIMEOUT,
    OPTIONAL_BOOL_ROOTS,
    PATCHED_SKILLS,
    ROOT,
    SENTINEL,
    at_imports,
    calls_without_timeout,
    claude_md_problems,
    hooks_reading_text_stdin,
    hooks_with_relative_paths,
    imported_files_with_dead_paths,
    imports_outside_claude_md,
    local_settings_with_guards,
    nested_instruction_files,
    optional_bool_annotations,
    optional_bool_lines,
    optional_bool_sources,
    patched_skills_without_sentinel,
    rules_with_dead_paths,
    rules_without_paths,
    skills_with_sentinel_not_listed,
    text_stdin_lines,
    tool_sources,
    untimed_call_lines,
)
from tools.check_type_escapes import scanned_roots
from tools.run_hooks import REPO_LOCATION_VARS


def _사본을_만든다(root: Path, *, 센티널을_넣을_스킬: Container[str]) -> None:
    for name in PATCHED_SKILLS:
        path = root / ".claude" / "skills" / name / "SKILL.md"
        path.parent.mkdir(parents=True, exist_ok=True)
        주석 = f"<!-- {SENTINEL}. 원본에 무엇을 더했는지 -->\n"
        머리말 = 주석 if name in 센티널을_넣을_스킬 else ""
        path.write_text(f"{머리말}본문\n", encoding="utf-8")


def test_사본마다_센티널이_있으면_문제가_없다(tmp_path: Path) -> None:
    _사본을_만든다(tmp_path, 센티널을_넣을_스킬=set(PATCHED_SKILLS))

    assert patched_skills_without_sentinel(tmp_path) == []


def test_센티널이_사라진_사본을_잡는다(tmp_path: Path) -> None:
    _사본을_만든다(tmp_path, 센티널을_넣을_스킬=set(PATCHED_SKILLS) - {"code-review"})

    problems = patched_skills_without_sentinel(tmp_path)

    assert len(problems) == 1
    assert "code-review" in problems[0]


def test_사본_파일이_통째로_사라진_것도_잡는다(tmp_path: Path) -> None:
    _사본을_만든다(tmp_path, 센티널을_넣을_스킬=set(PATCHED_SKILLS))
    (tmp_path / ".claude" / "skills" / "retro" / "SKILL.md").unlink()

    problems = patched_skills_without_sentinel(tmp_path)

    assert len(problems) == 1
    assert "retro" in problems[0]


def test_이_저장소의_사본들은_지금_온전하다() -> None:
    assert patched_skills_without_sentinel() == []


# 역방향. 목록은 손으로 유지되는데, 사본을 새로 덧대며 주석은 붙이고 목록은 잊으면 그 사본은 앞 검사
# 밖이라 되돌려져도 초록이다. 주석을 붙이는 커밋에서 걸리게 한다(2026-09-28 하네스 감사).


def test_센티널이_있는데_목록에_없는_사본을_잡는다(tmp_path: Path) -> None:
    _사본을_만든다(tmp_path, 센티널을_넣을_스킬=set(PATCHED_SKILLS))
    path = tmp_path / ".claude" / "skills" / "tdd" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text(f"<!-- {SENTINEL}. 시임 어휘 포인터 -->\n본문\n", encoding="utf-8")

    problems = skills_with_sentinel_not_listed(tmp_path)

    assert len(problems) == 1
    assert "tdd" in problems[0]
    assert "PATCHED_SKILLS" in problems[0]


def test_목록_밖_사본에_센티널이_없으면_문제가_없다(tmp_path: Path) -> None:
    _사본을_만든다(tmp_path, 센티널을_넣을_스킬=set(PATCHED_SKILLS))
    path = tmp_path / ".claude" / "skills" / "tdd" / "SKILL.md"
    path.parent.mkdir(parents=True)
    path.write_text("원본 그대로\n", encoding="utf-8")

    assert skills_with_sentinel_not_listed(tmp_path) == []


def test_이_저장소의_센티널_사본은_전부_목록에_있다() -> None:
    assert skills_with_sentinel_not_listed() == []


# 경로 참조가 아무것도 가리키지 않게 되는 것. 훅은 요란하게(PreToolUse 에서 스크립트를 못 찾은
# 파이썬이 종료 코드 2 로 끝나 모든 Bash 호출을 막는다), rules 는 조용히(그 규칙이 영영 안 실린다)
# 실패한다. 2026-09-23 티켓 03 세션이 앞의 것을 실제로 겪었다(PR #52).


def _설정을_쓴다(root: Path, *명령: str) -> None:
    hooks = [{"type": "command", "command": c} for c in 명령]
    settings = {"hooks": {"PreToolUse": [{"matcher": "Bash", "hooks": hooks}]}}
    path = root / ".claude" / "settings.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings), encoding="utf-8")


def _파일을_둔다(root: Path, 상대_경로: str, 내용: str = "") -> None:
    path = root / 상대_경로
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(내용, encoding="utf-8")


def test_저장소_파일을_상대_경로로_부르는_훅을_잡는다(tmp_path: Path) -> None:
    """#52 이전의 명령 그대로다. 세션이 저장소 루트를 벗어나면 스크립트를 못 찾는다."""
    _파일을_둔다(tmp_path, "tools/hook_bash_heredoc.py")
    _설정을_쓴다(tmp_path, "uv run --no-sync python tools/hook_bash_heredoc.py")

    problems = hooks_with_relative_paths(tmp_path)

    assert len(problems) == 1
    assert "tools/hook_bash_heredoc.py" in problems[0]
    assert "CLAUDE_PROJECT_DIR" in problems[0]


def test_CLAUDE_PROJECT_DIR_로_부르는_훅은_통과한다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "tools/hook_bash_heredoc.py")
    _설정을_쓴다(
        tmp_path,
        'uv run --project "${CLAUDE_PROJECT_DIR}" --no-sync'
        ' python "${CLAUDE_PROJECT_DIR}/tools/hook_bash_heredoc.py"',
    )

    assert hooks_with_relative_paths(tmp_path) == []


def test_저장소_파일을_부르지_않는_훅은_건드리지_않는다(tmp_path: Path) -> None:
    """모든 훅에 CLAUDE_PROJECT_DIR 을 요구하면 이런 훅이 거짓 양성으로 커밋을 막는다."""
    _설정을_쓴다(tmp_path, "echo hi", "jq -r '.tool_input.command' >> ~/.claude/log.txt")

    assert hooks_with_relative_paths(tmp_path) == []


def test_훅_설정이_없으면_문제가_없다(tmp_path: Path) -> None:
    assert hooks_with_relative_paths(tmp_path) == []


def test_이_저장소의_훅은_지금_작업_디렉터리에_묶이지_않는다() -> None:
    assert hooks_with_relative_paths() == []


# local 설정의 가드. `.claude/settings.local.json` 은 추적하지 않아 손으로 판 워크트리에는 없고,
# EnterWorktree 는 만들 때 한 번 복사한다. 거기 둔 가드는 워크트리 세션에서 조용히 빠진다(2026-10-05
# 워크트리 감사 8).


# 실제 훅 항목 하나를 든 local 설정. 이벤트 이름만 있고 항목이 없으면 가드가 아니다.
_훅_하나: dict[str, object] = {
    "hooks": {"Stop": [{"hooks": [{"type": "command", "command": "echo x"}]}]}
}


def _local_설정을_쓴다(root: Path, 설정: dict[str, object]) -> None:
    path = root / ".claude" / "settings.local.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(설정), encoding="utf-8")


def test_local_설정의_deny_와_ask_를_잡는다(tmp_path: Path) -> None:
    _local_설정을_쓴다(
        tmp_path,
        {"permissions": {"allow": ["Bash(git log *)"], "deny": ["Read(x)"], "ask": ["Bash(rm *)"]}},
    )

    problems = local_settings_with_guards(tmp_path)

    assert len(problems) == 1
    assert ".claude/settings.local.json" in problems[0]
    assert "permissions.deny" in problems[0]
    assert "permissions.ask" in problems[0]
    assert "settings.json" in problems[0]


def test_local_설정의_hooks_를_잡는다(tmp_path: Path) -> None:
    _local_설정을_쓴다(tmp_path, _훅_하나)

    problems = local_settings_with_guards(tmp_path)

    assert len(problems) == 1
    assert "hooks" in problems[0]


def test_local_설정에_allow_만_있으면_문제가_없다(tmp_path: Path) -> None:
    _local_설정을_쓴다(tmp_path, {"permissions": {"allow": ["Bash(git log *)"]}})

    assert local_settings_with_guards(tmp_path) == []


# 이벤트 이름은 있어도 실제 훅 항목이 없는 모양들. 가드가 아니다.
_빈_훅들: tuple[dict[str, object], ...] = ({}, {"Stop": []}, {"Stop": [{"hooks": []}]})


def test_빈_가드_목록은_가드가_아니다(tmp_path: Path) -> None:
    """빠져도 잃는 것이 없다. 잡으면 거짓 양성으로 커밋을 막는다. 훅은 이벤트 이름이 아니라 실제
    훅 항목이 있어야 가드다(PR #138 CodeRabbit)."""
    for hooks in _빈_훅들:
        _local_설정을_쓴다(tmp_path, {"permissions": {"deny": [], "ask": []}, "hooks": hooks})

        assert local_settings_with_guards(tmp_path) == [], hooks


def test_깨진_local_설정은_트레이스백이_아니라_문제로_낸다(tmp_path: Path) -> None:
    """주 체크아웃의 local 까지 읽으므로 깨진 파일 하나가 예외로 모든 커밋을 막으면 원인을 찾기
    어렵다(PR #138 claude-review). 다른 검사처럼 경로와 함께 문제로 돌려준다."""
    path = tmp_path / ".claude" / "settings.local.json"
    path.parent.mkdir(parents=True)
    path.write_text("{not json", encoding="utf-8")

    problems = local_settings_with_guards(tmp_path)

    assert len(problems) == 1
    assert ".claude/settings.local.json" in problems[0]
    assert "읽을 수 없다" in problems[0]


def test_GIT_접두사를_벗기면_저장소_위치_변수를_모두_벗긴다() -> None:
    """`_main_checkout` 은 스크립트로 돌아 `REPO_LOCATION_VARS` 를 import 하지 못하고 `GIT_`
    접두사로 벗긴다. 두 목록이 갈리지 않게 여기서 잰다(PR #138 claude-review)."""
    assert all(name.startswith("GIT_") for name in REPO_LOCATION_VARS)


def test_local_설정이_없으면_문제가_없다(tmp_path: Path) -> None:
    assert local_settings_with_guards(tmp_path) == []


def test_이_체크아웃의_local_설정에는_가드가_없다() -> None:
    assert local_settings_with_guards() == []


def _git(cwd: Path, *args: str) -> None:
    subprocess.run(["git", *args], cwd=cwd, check=True, capture_output=True)


def test_워크트리에서는_주_체크아웃의_local_가드도_잡는다(tmp_path: Path) -> None:
    """손으로 판 워크트리에는 local 이 없어 그 체크아웃만 보면 늘 빈 판정이다(2026-10-06 수정 검증).
    가드를 잃는 것은 주 체크아웃의 local 이므로 그것을 본다."""
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    _git(
        main,
        *("-c", "user.name=t", "-c", "user.email=t@t"),
        *("commit", "-q", "--allow-empty", "-m", "x"),
    )
    _git(main, "worktree", "add", "-q", str(tmp_path / "wt"))
    _local_설정을_쓴다(main, _훅_하나)

    problems = local_settings_with_guards(tmp_path / "wt")

    assert len(problems) == 1
    assert "주 체크아웃" in problems[0]
    assert "hooks" in problems[0]


def test_주_체크아웃에서는_local_을_한_번만_본다(tmp_path: Path) -> None:
    _git(tmp_path, "init", "-q")
    _local_설정을_쓴다(tmp_path, {"permissions": {"deny": ["Read(x)"]}})

    assert len(local_settings_with_guards(tmp_path)) == 1


def _규칙을_쓴다(root: Path, 이름: str, *경로: str) -> None:
    목록 = "".join(f'  - "{p}"\n' for p in 경로)
    path = root / ".claude" / "rules" / f"{이름}.md"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(f"---\npaths:\n{목록}---\n\n# 규칙\n", encoding="utf-8")


def test_아무_파일도_가리키지_않는_paths_를_잡는다(tmp_path: Path) -> None:
    """파일을 옮기거나 나누면 그 이름을 적은 규칙이 조용히 안 실린다. 아무도 모른다."""
    _파일을_둔다(tmp_path, "tests/test_server.py")
    _규칙을_쓴다(tmp_path, "admin", "tests/test_server.py", "tests/test_gone.py")

    problems = rules_with_dead_paths(tmp_path)

    assert len(problems) == 1
    assert "tests/test_gone.py" in problems[0]
    assert "admin.md" in problems[0]


def test_디렉터리_glob_과_파일_경로가_살아_있으면_통과한다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "src/pkg/admin/http.py")
    _파일을_둔다(tmp_path, "openapi.json")
    _규칙을_쓴다(tmp_path, "admin", "src/pkg/admin/**", "openapi.json")

    assert rules_with_dead_paths(tmp_path) == []


def test_이_저장소의_rules_paths_는_지금_다_살아_있다() -> None:
    assert rules_with_dead_paths() == []


def test_저장소에_없는_경로_모양은_잡지_않는다(tmp_path: Path) -> None:
    """실재하는 파일만 잡는다는 조건을 고정한다. 빠지면 경로처럼 생긴 모든 글자가 걸린다."""
    _설정을_쓴다(tmp_path, "echo a/b", "grep -q not/a/file")

    assert hooks_with_relative_paths(tmp_path) == []


def test_따옴표나_점_슬래시로_불러도_상대_경로면_잡는다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "tools/hook_x.py")
    _설정을_쓴다(tmp_path, 'python "tools/hook_x.py"', "python ./tools/hook_x.py")

    assert len(hooks_with_relative_paths(tmp_path)) == 2


def test_항목_없는_paths_는_없는_것으로_잡는다(tmp_path: Path) -> None:
    """키만 있고 항목이 없으면 두 검사를 모두 빠져나가던 자리다."""
    path = tmp_path / ".claude" / "rules" / "empty.md"
    path.parent.mkdir(parents=True)
    path.write_text("---\npaths:\n---\n\n# 규칙\n", encoding="utf-8")

    assert [p.name for p in rules_without_paths(tmp_path)] == ["empty.md"]


def test_프론트매터가_없는_rules_파일도_잡는다(tmp_path: Path) -> None:
    path = tmp_path / ".claude" / "rules" / "bare.md"
    path.parent.mkdir(parents=True)
    path.write_text("# 규칙\n\n- 아무 것\n", encoding="utf-8")

    assert [p.name for p in rules_without_paths(tmp_path)] == ["bare.md"]


def test_paths_의_뒷주석은_패턴이_아니다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "src/pkg/a.py")
    path = tmp_path / ".claude" / "rules" / "src.md"
    path.parent.mkdir(parents=True)
    path.write_text('---\npaths:\n  - "src/**"  # 설명\n---\n', encoding="utf-8")

    assert rules_with_dead_paths(tmp_path) == []


def test_glob_으로_읽을_수_없는_패턴은_트레이스백이_아니라_이유를_낸다(tmp_path: Path) -> None:
    _규칙을_쓴다(tmp_path, "abs", "/abs/**")

    problems = rules_with_dead_paths(tmp_path)

    assert len(problems) == 1
    assert "읽을 수 없다" in problems[0]


# Claude Code 는 `.claude/rules/` 를 재귀로 찾고, `paths` 를 블록 목록 말고도 흐름 목록과
# 쉼표로 가른 문자열로 받는다(공식 memory 문서, 2026-09-29 확인). 한 층과 블록 목록만 보던
# 검사는 하위 폴더의 규칙을 못 보고, 다른 두 모양을 "paths 없음" 으로 잘못 잡았다.


def _규칙_본문을_쓴다(root: Path, 상대_경로: str, 본문: str) -> None:
    _파일을_둔다(root, f".claude/rules/{상대_경로}", 본문)


def test_하위_폴더의_규칙도_paths_가_있어야_한다(tmp_path: Path) -> None:
    _규칙_본문을_쓴다(tmp_path, "frontend/bare.md", "# paths 없는 규칙\n")

    assert [p.relative_to(tmp_path).as_posix() for p in rules_without_paths(tmp_path)] == [
        ".claude/rules/frontend/bare.md"
    ]


def test_하위_폴더_규칙의_죽은_paths_도_잡는다(tmp_path: Path) -> None:
    _규칙_본문을_쓴다(tmp_path, "frontend/web.md", '---\npaths:\n  - "web/**"\n---\n')

    problems = rules_with_dead_paths(tmp_path)

    assert len(problems) == 1
    assert ".claude/rules/frontend/web.md" in problems[0]


def test_흐름_목록과_쉼표_문자열의_paths_도_paths_다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "src/a.py")
    _파일을_둔다(tmp_path, "tests/test_a.py")
    _규칙_본문을_쓴다(tmp_path, "flow.md", '---\npaths: ["src/**", "tests/**"]\n---\n')
    _규칙_본문을_쓴다(tmp_path, "comma.md", '---\npaths: "src/**, tests/**"\n---\n')

    assert rules_without_paths(tmp_path) == []
    assert rules_with_dead_paths(tmp_path) == []


def test_흐름_목록의_죽은_항목을_하나씩_잡는다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "src/a.py")
    _규칙_본문을_쓴다(tmp_path, "flow.md", '---\npaths: ["src/**", "gone/**"]\n---\n')

    problems = rules_with_dead_paths(tmp_path)

    assert len(problems) == 1
    assert "'gone/**'" in problems[0]


def test_paths_키_뒤의_주석은_패턴이_아니다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "src/a.py")
    _규칙_본문을_쓴다(tmp_path, "c.md", '---\npaths:  # 설명\n  - "src/**"\n---\n')

    assert rules_without_paths(tmp_path) == []
    assert rules_with_dead_paths(tmp_path) == []


def test_들여쓰지_않은_블록_목록도_paths_다(tmp_path: Path) -> None:
    """YAML 은 목록 항목을 키와 같은 깊이에 둬도 받는다."""
    _파일을_둔다(tmp_path, "src/a.py")
    _규칙_본문을_쓴다(tmp_path, "flat.md", '---\npaths:\n- "src/**"\n---\n')

    assert rules_without_paths(tmp_path) == []
    assert rules_with_dead_paths(tmp_path) == []


def test_paths_의_항목_앞과_사이의_주석과_빈_줄을_넘는다(tmp_path: Path) -> None:
    """YAML 은 키와 첫 항목 사이, 항목 사이의 주석 줄과 빈 줄을 받는다(PR #100 리뷰)."""
    _파일을_둔다(tmp_path, "src/a.py")
    본문 = '---\npaths:\n  # 설명\n\n  - "src/**"\n  # 둘째\n  - "gone/**"\n---\n'
    _규칙_본문을_쓴다(tmp_path, "c.md", 본문)

    assert rules_without_paths(tmp_path) == []
    assert [p.split("'")[1] for p in rules_with_dead_paths(tmp_path)] == ["gone/**"]


def test_따옴표_안의_샵은_뒷주석이_아니다(tmp_path: Path) -> None:
    """` #` 로 자르면 `"docs/ #gone/**"` 가 살아 있는 `docs/` 가 되어 죽은 glob 이 숨는다."""
    _파일을_둔다(tmp_path, "docs/a.md")
    _규칙_본문을_쓴다(tmp_path, "block.md", '---\npaths:\n  - "docs/ #gone/**"  # 설명\n---\n')
    _규칙_본문을_쓴다(tmp_path, "flow.md", '---\npaths: ["docs/**", "docs/ #gone/**"]\n---\n')
    _규칙_본문을_쓴다(tmp_path, "string.md", '---\npaths: "docs/**, docs/ #gone/**"  # 설명\n---\n')

    assert [p.split("'")[1] for p in rules_with_dead_paths(tmp_path)] == [
        "docs/ #gone/**",
        "docs/ #gone/**",
        "docs/ #gone/**",
    ]


def test_낱말_속_작은따옴표는_뒷주석을_감추지_않는다(tmp_path: Path) -> None:
    """`it's` 의 `'` 를 따옴표로 열면 뒤의 쉼표와 `# 설명` 이 패턴에 붙는다."""
    _파일을_둔다(tmp_path, "src/it's/a.md")
    _규칙_본문을_쓴다(tmp_path, "c.md", "---\npaths: src/it's/**, gone/**  # 설명\n---\n")

    assert [p.split("'")[1] for p in rules_with_dead_paths(tmp_path)] == ["gone/**"]


def test_빈_paths_뒤의_다른_키_목록은_paths_가_아니다(tmp_path: Path) -> None:
    """주석과 빈 줄을 넘어가도 다른 키의 항목까지 먹지는 않는다."""
    _파일을_둔다(tmp_path, "src/a.py")
    _규칙_본문을_쓴다(tmp_path, "c.md", '---\npaths:\n# 설명\n\ntags:\n  - "src/**"\n---\n')

    assert [p.name for p in rules_without_paths(tmp_path)] == ["c.md"]


def test_중괄호_안의_쉼표는_패턴을_가르지_않는다(tmp_path: Path) -> None:
    _규칙_본문을_쓴다(tmp_path, "brace.md", '---\npaths: "src/**/*.{ts,tsx}, gone/**"\n---\n')

    problems = rules_with_dead_paths(tmp_path)

    assert [p.split("'")[1] for p in problems] == ["src/**/*.{ts,tsx}", "gone/**"]


# CLAUDE.md 의 줄 수와 `@` 임포트. 2026-09-28 까지 이 둘에는 회귀 테스트가 없었고 함수가 ROOT 를
# 직접 읽어 시험할 수도 없었다.


def _클로드_파일을_쓴다(root: Path, 본문: str) -> None:
    (root / "CLAUDE.md").write_text(본문, encoding="utf-8")


def test_줄_머리_임포트_하나뿐이면_문제가_없다(tmp_path: Path) -> None:
    _클로드_파일을_쓴다(tmp_path, "# 프로젝트\n\n@docs/constitution/principles.md\n\n본문\n")

    assert claude_md_problems(tmp_path) == []


def test_문장_속_임포트도_임포트다(tmp_path: Path) -> None:
    """공식 문서: `@` 구문은 어디서든 임포트다. 줄 머리만 보면 이 구절이 파일을 통째로 싣는다."""
    _클로드_파일을_쓴다(
        tmp_path,
        "@docs/constitution/principles.md\n\n범위가 헷갈리면 @docs/PRD.md 를 본다.\n",
    )

    problems = claude_md_problems(tmp_path)

    assert len(problems) == 1
    assert "@docs/PRD.md" in problems[0]


def test_백틱과_펜스_안의_at_은_임포트가_아니다() -> None:
    본문 = (
        "@docs/constitution/principles.md\n\n"
        '`@`를 쓰지 않는다. 훅은 `"${CLAUDE_PROJECT_DIR}"` 로.\n'
        "```\n@docs/PRD.md\n```\n"
        "~~~\n@docs/constitution/tech.md\n~~~\n"
        "- 목록 안:\n  ```bash\n  cat @docs/adr/README.md\n  ```\n"
        "문의는 noreply@anthropic.com 으로.\n"
    )

    assert at_imports(본문) == ["@docs/constitution/principles.md"]


def test_임포트가_늘어나면_잡는다(tmp_path: Path) -> None:
    _클로드_파일을_쓴다(tmp_path, "@docs/constitution/principles.md\n@docs/constitution/tech.md\n")

    problems = claude_md_problems(tmp_path)

    assert len(problems) == 1
    assert "tech.md" in problems[0]


def test_이백_한_줄이면_잡는다(tmp_path: Path) -> None:
    _클로드_파일을_쓴다(tmp_path, "@docs/constitution/principles.md\n" + "줄\n" * 200)

    problems = claude_md_problems(tmp_path)

    assert len(problems) == 1
    assert "201줄" in problems[0]


def test_이_저장소의_CLAUDE_md_는_지금_문제가_없다() -> None:
    assert claude_md_problems() == []


def test_조사가_붙거나_괄호로_감싼_at_경로는_임포트가_아니다() -> None:
    """조사가 붙은 것과 괄호로 감싼 것은 실리지 않았다(2026-09-29 `claude -p` 2.1.281 실측)."""
    본문 = "자세한 것은 @docs/PRD.md를 본다. (@docs/x.md)\n"

    assert at_imports(본문) == []


def test_경로_글자가_아닌_문장부호가_든_at_경로도_임포트로_센다() -> None:
    """재지 않은 모양은 보수적으로 센다. 실리는 파일을 놓치는 것보다 백틱으로 옮기는 것이 싸다."""
    본문 = "@docs/c++.md 와 @docs/a(1).md 와 @docs/x.md, 를 본다.\n"

    assert at_imports(본문) == ["@docs/c++.md", "@docs/a(1).md", "@docs/x.md,"]


def test_허용된_임포트가_주석이나_들여쓴_코드_블록_안에만_있으면_잡는다(tmp_path: Path) -> None:
    """두 자리의 `@경로` 는 실리지 않는다.

    둘 다 2026-09-29 실측이다(블록 HTML 주석은 공식 문서도 지운다고 한다).

    허용된 임포트는 한 줄에 단독으로, 들여쓰지 않고 적혀야 헌법이 실린다.
    """
    for 본문 in (
        "# 프로젝트\n\n<!-- @docs/constitution/principles.md -->\n",
        "# 프로젝트\n\n    @docs/constitution/principles.md\n",
    ):
        _클로드_파일을_쓴다(tmp_path, 본문)

        problems = claude_md_problems(tmp_path)

        assert any("한 줄에 단독으로" in problem for problem in problems), 본문


# Claude Code 는 marked 렉서의 토큰에서 임포트를 찾는다. 펜스와 코드 스팬은 건너뛰고, 닫힌 HTML
# 주석 안의 `@` 는 블록이든 문단 속이든 따라가지 않는다. 사례 id 는 탐침의 것이고 기대는 그
# 실측이다(2026-09-29 claude 2.1.281, `.scratch/harness/probes/import_comments/`). c23 만은 운반
# 파일이 실리지 않아 재지 못했고 CommonMark 로 추론했다(폼피드는 줄 끝이 아니다). 줄 단독 검사
# 만으로는 여러 줄 주석 속의 단독 줄을 못 잡았다(PR #100 리뷰).
_헌법 = "@docs/constitution/principles.md"
_다른 = "@docs/PRD.md"


@pytest.mark.parametrize(
    "본문",
    [
        pytest.param(f"# P\n\n<!--\n{_헌법}\n-->\n", id="c01"),
        pytest.param(f"원칙:\n<!--\n{_헌법}\n-->\n", id="c05"),
        pytest.param(f"# P\n\n<!--\n{_헌법}\n", id="c06"),
        pytest.param(f"# P\n\n```\n{_헌법}\n", id="c07"),
        pytest.param(f"# P\n\n````\n{_헌법}\n````\n", id="c08"),
        pytest.param(f"원칙은 `\n{_헌법}\n` 에 있다.\n", id="c10"),
        pytest.param(f"# P\n\n<div>\n{_헌법}\n</div>\n", id="c11"),
        pytest.param(f"<!--\f{_헌법}\f-->\n", id="c23"),
        pytest.param(f"메모 <!--\n{_헌법}\n-->\n", id="c28"),
        pytest.param(f"원칙:\n    <!--\n{_헌법}\n-->\n", id="c48"),
        pytest.param(f"원칙:\n    ```\n{_헌법}\n    ```\n", id="c49"),
        pytest.param(f"# P\n\n- ```\n  {_헌법}\n  ```\n", id="c56"),
    ],
)
def test_허용된_임포트가_실리지_않는_자리에만_있으면_잡는다(tmp_path: Path, 본문: str) -> None:
    _클로드_파일을_쓴다(tmp_path, 본문)

    problems = claude_md_problems(tmp_path)

    assert problems
    assert all("principles.md" in problem for problem in problems)


@pytest.mark.parametrize(
    "본문",
    [
        pytest.param(f"# P\n\n    <!--\n{_헌법}\n-->\n", id="c04"),
        pytest.param(f"<details>\n\n{_헌법}\n\n</details>\n", id="c12"),
        pytest.param(f"<!--\n```\n-->\n{_헌법}\n```\n", id="c25"),
        pytest.param(f"```\n<!--\n```\n{_헌법}\n\n<!-- 끝 -->\n", id="c26"),
        pytest.param(f"<!-- a -->\n{_헌법}\n<!-- b -->\n", id="c27"),
        pytest.param(f"{_헌법}\n\n<!--\n{_다른}\n-->\n", id="c33"),
        pytest.param(f"<!-- 메모 -->\n{_헌법}\n", id="c47"),
        pytest.param(f"<!-- a --> <!--\n{_헌법}\n-->\n", id="c53"),
        pytest.param(f"<!-->\n{_헌법}\n-->\n", id="c54"),
        pytest.param(f"# P\n\n- ```\n  x\n  ```\n\n{_헌법}\n", id="c58"),
    ],
)
def test_허용된_임포트가_실리는_자리에_있고_주석_속_경로뿐이면_통과한다(
    tmp_path: Path, 본문: str
) -> None:
    _클로드_파일을_쓴다(tmp_path, 본문)

    assert claude_md_problems(tmp_path) == []


@pytest.mark.parametrize(
    "본문",
    [
        pytest.param(f"{_헌법}\n\n``코드`` {_다른} `a`\n", id="c39"),
        pytest.param(f"{_헌법}\n\n    ```\n{_다른}\n    ```\n", id="c40"),
        pytest.param(f"{_헌법}\n\n```\n코드\n````\n{_다른}\n```\n", id="c41"),
        pytest.param(f"{_헌법}\n\n- ```\n  x\n  ```\n\n{_다른}\n", id="c50"),
        pytest.param(f"{_헌법}\n\n<div>\n```\n</div>\n\n{_다른}\n", id="c51"),
        pytest.param(f"{_헌법}\n\n메모 <!-- a\n\n{_다른}\n\n끝 -->\n", id="c52"),
        pytest.param(f"{_헌법}\n\n메모 <!-- a --> {_다른} <!-- b -->\n", id="c55"),
        pytest.param(f"{_헌법}\n\n- ```\n  x\n  ```\n\n{_다른}\n\n```\ny\n```\n", id="c57"),
        pytest.param(f"{_헌법}\n\n- ```\n  x\n    ```\n\n{_다른}\n", id="c59"),
        pytest.param(f"{_헌법}\n\n<span>참고</span> {_다른}\n", id="c60"),
    ],
)
def test_실리는_다른_경로는_펜스나_주석으로_잘못_가리지_않고_센다(본문: str) -> None:
    """세는 쪽은 좁게 벗긴다. 짝이 어긋난 표지나 닫히지 않은 것이 뒤의 임포트를 숨기지 않게 한다."""
    assert at_imports(본문) == [_헌법, _다른]


def test_허용된_임포트가_마침표로_끝나면_헌법이_실리지_않아_잡는다(tmp_path: Path) -> None:
    """끝의 마침표를 떼어 허용 목록과 맞추면, 헌법이 실리지 않는데 검사는 초록이 된다."""
    _클로드_파일을_쓴다(tmp_path, "# 프로젝트\n\n원칙은 @docs/constitution/principles.md.\n")

    problems = claude_md_problems(tmp_path)

    # 사유가 둘이다. 허용 목록에 없는 토큰(`…principles.md.`)이고,
    # 허용된 임포트가 한 줄 단독이 아니다.
    assert len(problems) == 2
    assert all("principles.md" in problem for problem in problems)


# 임포트는 CLAUDE.md 에서만 일어나지 않는다. rules 파일과 임포트된 파일 안의 `@경로` 도 따라가서
# 실린다(2026-09-29 실측, 공식 문서: 임포트는 최대 네 단계까지 재귀). 루트 CLAUDE.md 의 허용 목록만
# 보면 그 문이 열려 있다.


def test_rules_안의_at_임포트를_잡는다(tmp_path: Path) -> None:
    _규칙_본문을_쓴다(
        tmp_path, "web.md", '---\npaths:\n  - "web/**"\n---\n자세한 것은 @docs/x.md 를 본다.\n'
    )

    problems = imports_outside_claude_md(tmp_path)

    assert len(problems) == 1
    assert ".claude/rules/web.md" in problems[0]
    assert "@docs/x.md" in problems[0]


def test_임포트된_파일_안의_at_임포트를_잡는다(tmp_path: Path) -> None:
    _헌법을_쓴다(tmp_path, "# 원칙\n\n세부는 @docs/constitution/tech.md 에 있다.\n")

    problems = imports_outside_claude_md(tmp_path)

    assert len(problems) == 1
    assert "docs/constitution/principles.md" in problems[0]


def test_백틱_안의_at_은_rules_에서도_임포트가_아니다(tmp_path: Path) -> None:
    _규칙_본문을_쓴다(
        tmp_path, "web.md", '---\npaths:\n  - "web/**"\n---\n`@docs/x.md` 처럼 쓰지 않는다.\n'
    )
    _헌법을_쓴다(tmp_path, "가리키려면 `@README` 처럼 백틱에 넣는다.\n")

    assert imports_outside_claude_md(tmp_path) == []


def test_HTML_주석_안의_at_은_rules_와_헌법에서도_임포트가_아니다(tmp_path: Path) -> None:
    """rules 와 임포트된 파일도 CLAUDE.md 와 같은 흐름이다(2026-09-29 실측, 사례 r01·r02)."""
    _규칙_본문을_쓴다(
        tmp_path, "web.md", '---\npaths:\n  - "web/**"\n---\n<!--\n@docs/x.md\n-->\n본문\n'
    )
    _헌법을_쓴다(tmp_path, "# 원칙\n\n<!-- @docs/x.md -->\n")

    assert imports_outside_claude_md(tmp_path) == []


def test_이_저장소의_rules_와_헌법에는_at_임포트가_없다() -> None:
    assert imports_outside_claude_md() == []


# 임포트된 파일 안의 백틱 경로. 모델이 루트 기준으로 읽어 형제 파일을 이름만으로 가리키면 깨진다
# (대기열 32, PR #43 이 헌법 버전을 못 찾았다). `@` 임포트의 상대 경로는 담은 파일 기준으로 풀린다.


def _헌법을_쓴다(root: Path, 본문: str) -> None:
    _파일을_둔다(root, "docs/constitution/principles.md", 본문)


def test_임포트된_파일의_형제_상대_경로를_잡는다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "docs/constitution/tech.md")
    _헌법을_쓴다(tmp_path, "스택은 `tech.md`, 색인은 `docs/constitution/README.md`.\n")
    _파일을_둔다(tmp_path, "docs/constitution/README.md")

    problems = imported_files_with_dead_paths(tmp_path)

    assert len(problems) == 1
    assert "`tech.md`" in problems[0]


def test_전체_경로와_glob_과_디렉터리는_통과한다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, ".claude/rules/core.md")
    _파일을_둔다(tmp_path, "docs/adr/0001-x.md")
    _헌법을_쓴다(
        tmp_path, "세부는 `.claude/rules/*.md`, 결정은 `docs/adr/`, 판정은 `tools/x.py`.\n"
    )
    _파일을_둔다(tmp_path, "tools/x.py")

    assert imported_files_with_dead_paths(tmp_path) == []


def test_경로가_아닌_백틱은_보지_않는다(tmp_path: Path) -> None:
    _헌법을_쓴다(
        tmp_path, "`Any`, `cast`, `type: ignore`, `agent_os.core`, `main → sdk`, `run_id`.\n"
    )

    assert imported_files_with_dead_paths(tmp_path) == []


def test_임포트_대상_파일이_없으면_그것부터_잡는다(tmp_path: Path) -> None:
    problems = imported_files_with_dead_paths(tmp_path)

    assert len(problems) == 1
    assert "principles.md" in problems[0]


def test_이_저장소의_임포트된_파일_경로는_지금_다_살아_있다() -> None:
    assert imported_files_with_dead_paths() == []


# 루트 밖의 지침 파일. `next dev` 는 에이전트를 감지하면 앱 폴더에 AGENTS.md 와
# `@AGENTS.md` 한 줄짜리 CLAUDE.md 를 만든다(ADR 0021). 지침을 `.claude/rules/*.md` + `paths`
# 에 둔다는 결정(ADR 0004)이 조용히 우회된다. 원인과 무관하게 결과를 본다.


def test_루트_밖의_CLAUDE_md_와_AGENTS_md_를_잡는다(tmp_path: Path) -> None:
    _클로드_파일을_쓴다(tmp_path, "# 루트\n")
    _파일을_둔다(tmp_path, "web/apps/admin/AGENTS.md", "# Next 가 만든 것\n")
    _파일을_둔다(tmp_path, "web/apps/admin/CLAUDE.md", "@AGENTS.md\n")
    _파일을_둔다(tmp_path, "docs/CLAUDE.md", "# 지역 지침\n")

    problems = nested_instruction_files(tmp_path)

    assert [p.split(":", 1)[0] for p in problems] == [
        "docs/CLAUDE.md",
        "web/apps/admin/AGENTS.md",
        "web/apps/admin/CLAUDE.md",
    ]
    assert ".claude/rules" in problems[0]


def test_node_modules_와_워크트리_아래의_지침_파일은_보지_않는다(tmp_path: Path) -> None:
    """패키지가 싣고 온 AGENTS.md 와 다른 체크아웃의 루트 CLAUDE.md 는 이 저장소의 지침이 아니다."""
    _파일을_둔다(tmp_path, "web/node_modules/next/AGENTS.md")
    _파일을_둔다(tmp_path, "web/node_modules/.pnpm/pkg/node_modules/pkg/CLAUDE.md")
    _파일을_둔다(tmp_path, ".claude/worktrees/02-x/CLAUDE.md")
    _파일을_둔다(tmp_path, ".venv/Lib/site-packages/pkg/AGENTS.md")

    assert nested_instruction_files(tmp_path) == []


def test_이_저장소의_루트_밖에는_지침_파일이_없다() -> None:
    assert nested_instruction_files() == []


def _CLI_로_검사한다(root: Path) -> subprocess.CompletedProcess[str]:
    """다른 검사는 통과하는 최소 트리를 깔고 CLI 진입점을 부른다. 루트는 첫 인자다."""
    _클로드_파일을_쓴다(root, "@docs/constitution/principles.md\n")
    _헌법을_쓴다(root, "# 원칙\n")
    _사본을_만든다(root, 센티널을_넣을_스킬=set(PATCHED_SKILLS))
    return subprocess.run(
        [sys.executable, str(ROOT / "tools" / "check_instructions.py"), str(root)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
        env={**os.environ, "PYTHONUTF8": "1"},
        check=False,
    )


def test_CLI_진입점이_임시_트리의_rules_임포트를_출력한다(tmp_path: Path) -> None:
    _규칙_본문을_쓴다(
        tmp_path, "web.md", '---\npaths:\n  - "CLAUDE.md"\n---\n@docs/x.md 를 본다.\n'
    )

    process = _CLI_로_검사한다(tmp_path)

    assert process.returncode == 1
    assert ".claude/rules/web.md: @ 임포트" in process.stdout


def test_CLI_진입점이_임시_트리의_local_가드를_출력한다(tmp_path: Path) -> None:
    _local_설정을_쓴다(tmp_path, {"permissions": {"deny": ["Read(x)"]}})

    process = _CLI_로_검사한다(tmp_path)

    assert process.returncode == 1
    assert ".claude/settings.local.json:" in process.stdout


def test_CLI_진입점이_임시_트리의_중첩_지침_파일을_출력한다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "web/apps/admin/AGENTS.md")

    process = _CLI_로_검사한다(tmp_path)

    assert process.returncode == 1
    assert "web/apps/admin/AGENTS.md:" in process.stdout


# 훅의 stdin. 훅 환경은 cp949 라 텍스트 stdin 은 한글을 깨뜨리고 조용히 exit 0 이 된다(대기열 25).


def test_텍스트_stdin_을_읽는_줄을_잡는다() -> None:
    source = "import json\nimport sys\n\npayload = json.load(sys.stdin)\nraw = sys.stdin.read()\n"

    assert text_stdin_lines(source) == [4, 5]


def test_from_import_한_stdin_도_잡는다() -> None:
    source = "from sys import stdin\n\nraw = stdin.read()\n"

    assert text_stdin_lines(source) == [1]


def test_바이트_stdin_은_통과한다() -> None:
    source = "import json\nimport sys\n\npayload = json.load(sys.stdin.buffer)\n"

    assert text_stdin_lines(source) == []


def test_독스트링의_stdin_낱말은_세지_않는다() -> None:
    source = (
        '"""stdin 으로 받는다. sys.stdin 이 텍스트면 깨진다."""\nimport sys\nx = sys.stdin.buffer\n'
    )

    assert text_stdin_lines(source) == []


def test_텍스트_stdin_훅을_파일과_줄로_보고한다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "tools/hook_x.py", "import sys\nraw = sys.stdin.read()\n")
    _파일을_둔다(tmp_path, "tools/hook_y.py", "import sys\nraw = sys.stdin.buffer.read()\n")

    problems = hooks_reading_text_stdin(tmp_path)

    assert len(problems) == 1
    assert problems[0].startswith("tools/hook_x.py:2:")


def test_이_저장소의_훅은_지금_전부_바이트로_읽는다() -> None:
    assert hooks_reading_text_stdin() == []


# 외부 명령의 시간 제한. 멈춘 호출은 루프의 시간 제한으로 끊지 못한다(대기열 342,
# `.claude/rules/tools.md` 의 기다리는 도구 항목).


def test_시간_제한_없는_subprocess_호출을_잡는다() -> None:
    source = (
        "import subprocess\n"
        "subprocess.run(['git'])\n"
        "subprocess.call(['git'])\n"
        "subprocess.check_call(['git'])\n"
        "subprocess.check_output(['git'])\n"
    )

    assert untimed_call_lines(source) == [
        (2, "subprocess.run"),
        (3, "subprocess.call"),
        (4, "subprocess.check_call"),
        (5, "subprocess.check_output"),
    ]


def test_시간_제한_없는_communicate_와_wait_를_잡는다() -> None:
    source = "out, err = process.communicate()\nprocess.wait()\n"

    assert untimed_call_lines(source) == [(1, "process.communicate"), (2, "process.wait")]


def test_시간_제한을_준_호출은_통과한다() -> None:
    source = (
        "import subprocess\n"
        "subprocess.run(['git'], timeout=60)\n"
        "process.communicate(b'', 5)\n"
        "process.communicate(timeout=5)\n"
        "process.wait(5)\n"
        "process.wait(timeout=limit)\n"
    )

    assert untimed_call_lines(source) == []


def test_timeout_None_은_시간_제한이_아니다() -> None:
    source = (
        "import subprocess\n"
        "subprocess.run(['git'], timeout=None)\n"
        "process.communicate(b'', None)\n"
        "process.wait(None)\n"
    )

    assert [line for line, _ in untimed_call_lines(source)] == [2, 3, 4]


def test_별칭과_from_import_로_부른_것도_잡는다() -> None:
    source = (
        "import subprocess as sp\n"
        "from subprocess import check_output, run as launch\n"
        "sp.run(['git'])\n"
        "launch(['git'])\n"
        "check_output(['git'])\n"
    )

    assert untimed_call_lines(source) == [(3, "sp.run"), (4, "launch"), (5, "check_output")]


def test_subprocess_가_아닌_모듈의_같은_이름은_보지_않는다() -> None:
    source = "import asyncio\nasyncio.run(main())\nrun(['git'])\n"

    assert untimed_call_lines(source) == []


def test_키워드_펼치기는_시간_제한으로_보지_않는다() -> None:
    """`**` 안에 timeout 이 있는지 모른다. 모르는 것은 없는 것으로 잡는다(잘못 막는 쪽)."""
    source = "import subprocess\nsubprocess.run(['git'], **options)\n"

    assert untimed_call_lines(source) == [(2, "subprocess.run")]


def test_위치_인자_펼치기도_시간_제한으로_보지_않는다() -> None:
    """`*` 로 펼친 인자가 timeout 자리에 닿는지 모른다(독스트링의 잘못 막는 것)."""
    source = "process.wait(*limits)\nprocess.communicate(*pair)\n"

    assert untimed_call_lines(source) == [(1, "process.wait"), (2, "process.communicate")]


def test_다른_형의_wait_도_잡는다() -> None:
    """받는 쪽의 형을 모른다. `threading.Event.wait()` 도 끝없이 기다리므로 같게 본다."""
    source = "import threading\nthreading.Event().wait()\n"

    assert untimed_call_lines(source) == [(2, "threading.Event().wait")]


def test_까닭을_적은_표지가_있으면_뺀다() -> None:
    source = (
        "import subprocess\n"
        "process.wait()  # 시간 제한 없음: 끝낸 자식을 거둔다\n"
        "subprocess.run(  # 시간 제한 없음: 지우는 git 을 도중에 끊지 않는다\n"
        "    ['git'],\n"
        ")\n"
    )

    assert untimed_call_lines(source) == []


def test_communicate_는_표지로_빼지_않는다() -> None:
    """끝낸 뒤의 `communicate()` 도 트리를 떠난 손자가 파이프를 쥐면 돌아오지 않는다(대기열 342의
    사건). 표지가 아니라 timeout 으로 거둔다."""
    source = "process.communicate()  # 시간 제한 없음: 끝낸 자식을 거둔다\n"

    assert untimed_call_lines(source) == [(1, "process.communicate")]


def test_까닭_없는_표지는_빼지_않는다() -> None:
    source = "process.wait()  # 시간 제한 없음:\n"

    assert untimed_call_lines(source) == [(1, "process.wait")]


def test_주석_머리가_아닌_표지는_빼지_않는다() -> None:
    source = "process.wait()  # 까닭: 시간 제한 없음: 머리가 아니다\n"

    assert untimed_call_lines(source) == [(1, "process.wait")]


def test_문자열_속_표지는_빼지_않는다() -> None:
    source = "import subprocess\nsubprocess.run(['echo', '# 시간 제한 없음: 글자'])\n"

    assert untimed_call_lines(source) == [(2, "subprocess.run")]


def test_못_보는_것_변수에_담아_부른_것과_with_의_Popen() -> None:
    """독스트링의 못 보는 것. 변수에 담은 함수, `getattr` 으로 꺼낸 것, 다른 이름에 대입한 모듈,
    `from subprocess import *` 뒤의 이름, `getoutput`·`getstatusoutput`, `with Popen` 이
    빠져나갈 때의 암묵 wait, `os.system`·`os.popen`, 값이 None 인 변수를 준 timeout 은
    지나간다."""
    source = (
        "import os\n"
        "import subprocess\n"
        "from subprocess import *\n"
        "runner = subprocess.run\n"
        "runner(['git'])\n"
        "getattr(subprocess, 'run')(['git'])\n"
        "sp = subprocess\n"
        "sp.run(['git'])\n"
        "run(['git'])\n"
        "subprocess.getoutput('git status')\n"
        "subprocess.getstatusoutput('git status')\n"
        "with subprocess.Popen(['git']) as process:\n"
        "    pass\n"
        "os.system('git status')\n"
        "os.popen('git status')\n"
        "limit = None\n"
        "subprocess.run(['git'], timeout=limit)\n"
    )

    assert untimed_call_lines(source) == []


def test_못_보는_것_파이프_읽기와_waitpid_와_partial_과_None_이_되는_식() -> None:
    """독스트링의 못 보는 것. `Popen` 의 파이프를 직접 읽는 것, `os.waitpid`, `functools.partial`
    로 감싼 함수, None 이 될 수 있는 식을 준 timeout 은 지나간다."""
    source = (
        "import functools\n"
        "import os\n"
        "import subprocess\n"
        "process = subprocess.Popen(['git'], stdout=subprocess.PIPE)\n"
        "process.stdout.read()\n"
        "for line in process.stdout:\n"
        "    pass\n"
        "os.waitpid(process.pid, 0)\n"
        "functools.partial(subprocess.run, ['git'])()\n"
        "subprocess.run(['git'], timeout=None if slow else 5)\n"
    )

    assert untimed_call_lines(source) == []


def test_못_보는_것_표지는_그_줄의_다른_호출도_뺀다() -> None:
    source = (
        "import subprocess\nprocess.wait(); subprocess.run(['git'])  # 시간 제한 없음: 거둔다\n"
    )

    assert untimed_call_lines(source) == []


def test_잘못_막는_것_asyncio_의_wait_와_communicate_도_잡는다() -> None:
    """asyncio 의 둘은 timeout 을 받지 않아 `wait_for` 로 감싸도 잡힌다(독스트링의 잘못 막는 것)."""
    source = (
        "import asyncio\n"
        "async def go(process):\n"
        "    await asyncio.wait_for(process.wait(), 5)\n"
        "    await process.communicate()\n"
    )

    assert untimed_call_lines(source) == [(3, "process.wait"), (4, "process.communicate")]


def test_시간_제한_없는_호출을_파일과_줄로_보고한다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "tools/x.py", "import subprocess\nsubprocess.run(['git'])\n")
    _파일을_둔다(tmp_path, "tools/y.py", "import subprocess\nsubprocess.run(['git'], timeout=9)\n")
    _파일을_둔다(tmp_path, "tools/sub/z.py", "process.wait()\n")
    _파일을_둔다(tmp_path, "tests/tools/test_x.py", "import subprocess\nsubprocess.run(['git'])\n")

    problems = calls_without_timeout(tmp_path)

    assert len(problems) == 2
    assert problems[0].startswith("tools/sub/z.py:1: process.wait 에 timeout 이 없다")
    assert problems[1].startswith("tools/x.py:2: subprocess.run 에 timeout 이 없다")


def test_이_저장소의_tools_에는_시간_제한_없는_호출이_없다() -> None:
    # 범위가 비면 위반 0 으로 조용히 초록이다(tests.md). 문턱은 rag-engine 킥오프 때 tools/ 의
    # 파이썬 45개에 맞췄다(agent-os 의 문턱은 50 이었다)
    assert len(tool_sources()) >= 40
    assert calls_without_timeout() == []


# 세 값으로 출력을 고르는 `bool | None` 주석(대기열 423). ruff FBT 는 키워드 전용 매개변수를
# 보지 않아 `output_for(..., first: bool | None)` 이 셀프 리뷰까지 지나갔다.


def test_bool_과_None_의_합_주석을_세_모양_모두_잡는다() -> None:
    source = (
        "from typing import Optional\n"
        "def a(x: bool | None) -> int: ...\n"
        "def b(x: None | bool) -> int: ...\n"
        "def c(x: Optional[bool]) -> int: ...\n"
        "def d(x: bool | None | None) -> int: ...\n"
    )

    assert optional_bool_lines(source) == [
        (2, "a 의 x"),
        (3, "b 의 x"),
        (4, "c 의 x"),
        (5, "d 의 x"),
    ]


def test_키워드_전용과_가변_인자와_반환도_잡는다() -> None:
    source = (
        "def f(a: bool | None, /, b: bool | None, *args: bool | None,\n"
        "      c: bool | None, **kwargs: bool | None) -> bool | None: ...\n"
        "class K:\n"
        "    async def g(self, *, first: bool | None = None) -> None: ...\n"
    )

    assert optional_bool_lines(source) == [
        (1, "f 의 a"),
        (1, "f 의 b"),
        (1, "f 의 args"),
        (2, "f 의 c"),
        (2, "f 의 kwargs"),
        (2, "f 의 반환"),
        (4, "g 의 first"),
    ]


def test_typing_속성과_Union_과_문자열_주해도_잡는다() -> None:
    source = (
        "import typing\n"
        "import typing as tp\n"
        "def a(x: typing.Optional[bool]) -> None: ...\n"
        "def b(x: tp.Union[bool, None]) -> None: ...\n"
        "def c(x: 'bool | None') -> 'Optional[bool]': ...\n"
    )

    assert optional_bool_lines(source) == [
        (3, "a 의 x"),
        (4, "b 의 x"),
        (5, "c 의 x"),
        (5, "c 의 반환"),
    ]


@pytest.mark.parametrize(
    "annotation",
    [
        "Optional[Optional[bool]]",
        "Optional[bool | None]",
        "Union[bool, Optional[bool]]",
        "Optional['bool']",
        "bool | 'None'",
        "' bool | None '",
    ],
)
def test_안쪽_합과_갈래_안의_문자열도_펴서_잡는다(annotation: str) -> None:
    source = f"def f(x: {annotation}) -> None: ...\n"

    assert optional_bool_lines(source) == [(1, "f 의 x")]


def test_잘못_막는_것_typing_이_아닌_Optional_도_잡는다() -> None:
    """독스트링의 잘못 막는 것. 이름이 어디서 왔는지는 보지 않는다."""
    source = "def Optional() -> None: ...\ndef f(x: Optional[bool]) -> None: ...\n"

    assert optional_bool_lines(source) == [(2, "f 의 x")]


@pytest.mark.parametrize(
    "parameter",
    [
        pytest.param("seen: bool | None = None", id="모듈_변수"),
        pytest.param("class K:\n    seen: bool | None = None", id="클래스_칸"),
        pytest.param("Flag = bool | None\ndef a(x: Flag) -> None: ...", id="별칭"),
        pytest.param("def a(x: list[bool | None]) -> None: ...", id="감싼_주석"),
        pytest.param(
            "from typing import Annotated\ndef a(x: Annotated[bool | None, 'm']) -> None: ...",
            id="Annotated",
        ),
        pytest.param("def a(x: builtins.bool | None) -> None: ...", id="builtins_bool"),
        pytest.param("def a(x: bool | NoneType) -> None: ...", id="NoneType"),
    ],
)
def test_못_보는_것은_지나간다(parameter: str) -> None:
    """독스트링의 못 보는 것. 함수의 매개변수와 반환의 주석만, 이름 `bool` 과 None 상수로 본다."""
    assert optional_bool_lines(parameter + "\n") == []


@pytest.mark.parametrize(
    "annotation",
    [
        "bool",
        "int | None",
        "bool | int",
        "bool | int | None",
        "Optional[int]",
        "Literal[True, None]",
        "'not a type ('",
    ],
)
def test_세_값이_아닌_주석은_지나간다(annotation: str) -> None:
    source = f"def f(x: {annotation}) -> {annotation}: ...\n"

    assert optional_bool_lines(source) == []


def test_bool_None_주석을_파일과_줄로_보고하고_probes_는_보지_않는다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "src/agent_os/x.py", "def f(*, x: bool | None) -> None: ...\n")
    _파일을_둔다(tmp_path, "tests/test_x.py", "def g() -> bool | None: ...\n")
    _파일을_둔다(tmp_path, "tools/y.py", "def h(x: bool) -> None: ...\n")
    _파일을_둔다(tmp_path, ".scratch/a/probes/p.py", "def p(x: bool | None) -> None: ...\n")

    problems = optional_bool_annotations(tmp_path)

    assert len(problems) == 2
    assert problems[0].startswith("src/agent_os/x.py:1: f 의 x 가 bool | None 이다")
    assert problems[1].startswith("tests/test_x.py:1: g 의 반환이 bool | None 이다")


def test_bool_None_검사가_훑는_범위는_pyright_의_include_다() -> None:
    assert OPTIONAL_BOOL_ROOTS == scanned_roots()


def test_이_저장소에는_bool_None_주석이_없다() -> None:
    # 범위가 비면 위반 0 으로 조용히 초록이다(tests.md). 문턱은 rag-engine 킥오프 때 src·tests·tools
    # 의 파이썬 99개에 맞췄다(agent-os 의 문턱은 200 이었다)
    assert len(optional_bool_sources()) >= 90
    assert optional_bool_annotations() == []


def test_CLI_진입점이_bool_None_주석을_출력한다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "tools/x.py", "def f(*, first: bool | None) -> None: ...\n")

    process = _CLI_로_검사한다(tmp_path)

    assert "tools/x.py:1: f 의 first 가 bool | None 이다" in process.stdout
    assert process.returncode == 1


def test_CLI_진입점이_시간_제한_없는_호출을_출력한다(tmp_path: Path) -> None:
    _파일을_둔다(tmp_path, "tools/x.py", "import subprocess\nsubprocess.run(['git'])\n")

    process = _CLI_로_검사한다(tmp_path)

    assert "tools/x.py:2: subprocess.run 에 timeout 이 없다" in process.stdout
    assert process.returncode == 1


def _멈춘_git(seen: list[object]) -> Callable[..., subprocess.CompletedProcess[str]]:
    def stuck(args: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        seen.append(kwargs.get("timeout"))
        raise subprocess.TimeoutExpired(args, 1)

    return stuck


def test_주_체크아웃을_찾는_git_이_시간을_넘기면_이_체크아웃의_local_만_본다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _파일을_둔다(tmp_path, ".claude/settings.local.json", '{"permissions": {"deny": ["Bash"]}}')
    monkeypatch.setattr(subprocess, "run", _멈춘_git([]))

    problems = local_settings_with_guards(tmp_path)

    assert [problem.split(":")[0] for problem in problems] == [".claude/settings.local.json"]


def test_주_체크아웃을_찾는_git_에_시간_제한을_준다(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    seen: list[object] = []
    monkeypatch.setattr(subprocess, "run", _멈춘_git(seen))

    local_settings_with_guards(tmp_path)

    assert seen == [CALL_TIMEOUT]


def test_CLI_진입점이_임시_트리의_빨강을_출력한다(tmp_path: Path) -> None:
    """검사 열을 모으는 main 의 배관을 한 번은 실제로 부른다(tests.md). 루트는 첫 인자."""
    _파일을_둔다(tmp_path, ".claude/rules/nopaths.md", "# paths 없는 규칙\n")

    process = _CLI_로_검사한다(tmp_path)

    assert process.returncode == 1
    assert "paths 프론트매터 없음" in process.stdout
