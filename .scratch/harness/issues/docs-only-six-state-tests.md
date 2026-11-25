# docs-only-six-state-tests: 문서만 바꾼 커밋이 도는 시험에 문서를 읽는 시험 둘을 더해 여섯으로 늘린다

**What to build:** 앞선 티켓 `docs-only-commit-narrow-pytest`(PR 109)는 문서만 바꾼 커밋의 pre-commit이 도는 pytest를 문서를 읽는 시험 넷으로 좁혔다. 그 티켓의 감사(파일을 열 때마다 시험 이름을 적는 훅을 붙여 전체 pytest를 한 번 돌렸다)가 목록 밖에서 문서를 읽는 시험 둘을 더 찾았고, 승인한 목록이 넷이라 넷으로 두고 "남긴 위험"에 적었다. 사용자가 2026-11-24에 "여섯으로 늘리기"를 골라 이 티켓이 그 둘을 목록에 더한다. 문서 커밋에서는 이 둘이 CI에서야 빨개졌다.

**더하는 시험 둘.**
- `tests/tools/test_hook_prompt_directive.py::test_알림의_규약_낱말은_원천_문서에_있다`: 첫 턴 알림의 규약 낱말이 `docs/agents/issue-tracker.md`에 그대로 있는지 본다. 그 문서의 브랜치 모양, 상태 값, 면제 브랜치 이름을 고친 문서 커밋이 알림과 어긋나게 만들 수 있다.
- `tests/tools/test_hook_grill_design_check.py::test_알림이_드는_용어집은_이_저장소의_용어집이다`: 설계 인터뷰 알림이 든 용어집 이름이 `docs/agents/domain.md`와 맞는지 본다.

**데이터베이스를 쓰지 않는지.** 두 시험을 `uv run pytest -q <둘>`로 손으로 돌려 둘이 0.35초에 통과했다(데이터베이스 없이, 이 PC에서 한 번). 시험 코드는 문서 파일 하나를 `read_text`로 읽고 알림을 만드는 함수(`first_turn_context`와 `context_for`)를 부를 뿐 데이터베이스 픽스처를 받지 않는다(코드를 읽었다. 한 시험은 대화 기록 경로로 없는 파일을 넘긴다).

**고치는 곳.**
- `tools/run_checks.py`: `DOC_STATE_TESTS`에 위 둘을 더하고, 독스트링과 주석의 "넷" 표현을 여섯 기준으로 고친다. "좁힌 길이 못 보는 것 (1)"은 목록 밖의 시험 둘을 못 본다고 적고 있어, 이제 그 둘을 남기는 시험으로 적고 못 보는 것은 감사의 한계(데이터베이스 없이 돌려 데이터베이스를 쓰는 시험은 보지 못했다, 자식 프로세스의 읽기는 못 봤다)로 줄인다.
- `tests/tools/test_run_checks.py`: 개수 단언(`len(DOC_STATE_TESTS) == 4`)을 6으로 먼저 고쳐 빨갛게 하고(시험 먼저), 독스트링과 주석의 "넷"을 맞춘다.
- `.pre-commit-config.yaml` 머리 주석: "문서 시험 넷"을 맞춘다.
- `.claude/skills/next-session/SKILL.md`와 `.scratch/plan-head.md`(생성 파일 `.scratch/plan.md`): 이 문서들이 "넷"을 말하면 맞춘다. 옛 표현은 grep으로 잔존이 0인지 본다(`CLAUDE.md` 작업 규약 4). 병합된 앞선 티켓과 일지는 기록이므로 고치지 않는다.

**ADR을 쓰지 않는 까닭.** 앞선 티켓과 같다. 어떤 시험을 남기는지는 ADR이 아니라 `tools/run_checks.py`가 정하고, 헌법과 계약은 건드리지 않는다. 승인은 사용자의 "여섯으로 늘리기"다.

**이번에 바꾸지 않는 것.**
- 문서 범위(`is_doc_path`), 시간 제한 900초, `-n` 없음, 시험 데이터베이스 준비 건너뛰기. 그대로다.
- 감사로 나온 나머지 시험(줄 구분 문자, 표, 인용 명령줄 둘, 지침 검사). 따로 도는 검사가 같은 일을 해서 남기지 않는다.

**대기열:** 없음

**Status:** done

- [x] `DOC_STATE_TESTS`가 여섯이고, 이름을 바꾸거나 지우면 목록의 시험이 먼저 빨개진다(개수 단언이 6이다)
- [x] 여섯을 `uv run pytest -q <여섯>`으로 손으로 돌려 통과하고 걸린 시간을 `## Comments`에 적는다
- [x] `tools/run_checks.py` 독스트링과 주석, `tests/tools/test_run_checks.py`, `.pre-commit-config.yaml` 주석이 여섯 기준이다. 살아 있는 문서에서 옛 "넷" 표현의 잔존이 0이다
- [x] 검증 명령이 초록이다: `uv run pytest`(전체), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`
- [x] 일지가 있고 이 PR의 셀프 리뷰 결과를 담는다

## Comments

- 2026-11-24, 손으로 본 것. 시험 먼저: 개수 단언을 6으로 고치고 `uv run pytest -q tests/tools/test_run_checks.py -k 남길_문서_시험`을 쳐 `assert 4 == 6`으로 빨간 것을 본 뒤 목록에 둘을 더했다. 여섯을 `uv run pytest -q <여섯>`으로 쳐 107건이 pytest가 찍은 15.16초에 통과했다(한 번, 다른 세션이 돌던 때다. 표준 축 리뷰 에이전트가 같은 명령을 다시 쳐 13.16초를 얻었다). 둘만 따로 친 값은 pytest가 찍은 0.35초이고 uv 시작은 빠졌다.
