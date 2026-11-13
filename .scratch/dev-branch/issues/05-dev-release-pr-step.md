# 05: 출시 PR을 여는 순서와 main의 strict를 agent-os에 맞춘다

**What to build:** 출시 PR(dev→main)을 누가 언제 어떤 순서로 여는지와, main이 strict라서 둘째 출시 PR부터 뒤처짐(BEHIND)이 날 것이라는 어림을 agent-os가 harness 티켓 `dev-release-pr-step`에서 정하는 중이다(설계 세션 때 병합 전). 그 결과가 agent-os의 `origin/dev`에 병합된 뒤 그 티켓 파일과 바뀐 스킬·문서(`next-session` `merge.md`, `docs/constitution/operations.md`, 보호 설정 파일)를 읽어 이 저장소에 옮긴다. main 보호의 strict는 그 결과를 보고 사용자에게 다시 묻고 정한다. 그때까지 출시 PR은 열지 않는다(ADR 0016).

- 옮긴 결정을 ADR 0016의 이력에 더하고, 이력이 본문 문장("출시 PR을 여는 순서와 main의 strict는 아직 정하지 않는다")을 거짓으로 만들면 그 문장 뒤에 포인터를 단다(`.claude/rules/adr.md`).
- main의 strict를 바꾸면 `tools/protection.json`을 고쳐 PUT하고, 사용자의 승인을 받은 뒤에 한다. 이때 필수 검사 `verify`의 출처도 함께 본다. main은 `app_id` null이고 dev는 15368(GitHub Actions)이다(04 티켓과 ADR 0016 이력 2026-11-12 "원격 설정을 걸고 dev를 땄다"). 맞추려면 두 JSON을 `checks`로 쓰고, 맞추지 않으면 그대로 둔다고 적는다.
- 이 기능의 마지막 티켓이다. 끝 줄 시험은 `**슬라이스:**` 줄이 없는 기능 계획을 보지 않고, 하네스 기능은 티켓이 모두 done이면 끝난 것이다(`tests/test_plan_status.py` 머리 독스트링). 그래서 기능 계획에 `**끝:**` 줄을 적지 않는다. 닫는 커밋이 `.scratch/plan-head.md`의 "하네스 기능" 문단에서 dev-branch를 지우고 `uv run python tools/plan_table.py`를 돌아 결과를 같은 커밋에 싣는다.
- 시작할 때 dev가 main보다 앞서 있으면(04가 `EnterWorktree`의 기준을 구분하지 못했다. 그때 dev와 main이 같은 커밋이었다) `EnterWorktree`로 만든 새 워크트리에서 `git fetch origin` 뒤 `git rev-parse HEAD origin/dev origin/main`을 쳐 HEAD가 `origin/dev`와 같은지(main과 다른지) 보고, ADR 0016 Consequences "다른 세션"의 서술과 다르면 이력에 적는다.
- 첫 출시 PR을 이 티켓이 열지, 옮긴 순서를 따르는 다음 세션에 맡길지는 옮긴 순서대로 한다.

**Blocked by:** 04, 그리고 agent-os의 harness 티켓 `dev-release-pr-step`이 그 저장소의 `origin/dev`에 병합됨(`git -C <agent-os 클론> show origin/dev:.scratch/harness/issues/dev-release-pr-step.md`의 `Status:`가 done)

**Status:** done

- [x] agent-os `dev-release-pr-step`의 결과(그 티켓 파일, 바뀐 스킬·문서·보호 설정 파일)를 읽었고, 옮긴 곳과 옮기지 않은 곳과 까닭의 표가 티켓 끝에 있다
- [x] 출시 PR을 여는 순서가 `next-session`과 운영 문서에 적혀 있다
- [x] main의 strict를 사용자에게 다시 물었고 답과 반영(바꿨으면 응답 값)을 티켓 끝에 적었다
- [x] ADR 0016에 이력이 있고, `tools/check_adr_pointers.py`가 통과한다
- [x] `.scratch/plan-head.md`의 "하네스 기능" 문단에서 dev-branch가 빠졌고 `uv run python tools/plan_table.py`의 결과가 같은 커밋에 실렸다
- [x] 검사 넷이 초록이다(`ruff check`·`ruff format --check` 0, `pyright`·`lint-imports`는 러너에서 Passed. 러너의 pytest는 3823개 통과에 2개 실패였고 둘 다 부하에서만 빨간 시간 시험이다. 단독으로 돌리면 38 passed이며 이 변경은 코드를 바꾸지 않았다. 일지 `2026-11-13-0144-dev-release-pr-step`의 검증 절)

## 결과

2026-11-13. agent-os의 `dev-release-pr-step`은 그 저장소의 `origin/dev`에서 `Status: done`이고 병합 커밋은 `fba36f78a`(PR 546)다. 그 티켓 파일의 결과 13항과 `fba36f78a`가 바꾼 파일 열여덟을 읽었다(`MSYS_NO_PATHCONV=1 git -C <agent-os 클론> show origin/dev:<경로>`). 시작할 때 `EnterWorktree`가 만든 워크트리는 `HEAD`가 `origin/dev`(`0caa20f`)와 같고 `origin/main`(`bcd5613`)과 달랐다(ADR 0016 Consequences "다른 세션"의 서술과 같다). 그 뒤 `origin/dev`가 형제 PR 27(`bf5a0ad`)로 앞서 `git merge --ff-only origin/dev`로 받았다. 그 PR이 헌법 1.3.0과 ADR 0016의 고침을 실었다.

사용자 답(2026-11-13, `AskUserQuestion`). main의 strict는 "strict 유지 + 병합 뒤 되돌려 합치기 (Recommended)", `verify`의 출처는 "그대로 둔다 (Recommended)". 원격의 보호 설정은 바꾸지 않아 PUT은 없다. 읽은 값(`gh api`의 GET)은 main이 strict true, 선형 이력 강제 false, `verify`의 `app_id` null이고, dev가 strict false, 선형 이력 강제 false, `verify`의 `app_id` 15368이다.

옮긴 곳과 옮기지 않은 곳과 까닭.

| agent-os의 것 | 이 저장소 | 까닭 |
|---|---|---|
| `next-session/SKILL.md` 결정표의 "출시 PR" 줄 | 옮겼다 | 계기를 스킬 한 곳에 둔다. 조건은 `--is-ancestor`가 0이고, 끝 줄 커밋이 dev에만 있고, 열린 출시 PR이 없는 것이다 |
| 같은 표의 "되돌려 합치기" 줄(`--is-ancestor`로 바꾼 판정) | 옮기지 않았다 | 03이 이미 같은 판정으로 옮겨 두었다(끊긴 열린 PR을 잇는 갈래까지) |
| `merge.md`의 "출시 PR" 절(이어받기, 계기, 전제 확인, 열기, 기다림, 병합 뒤) | 옮겼다 | 명령과 판정은 agent-os에서 본 것이라고 절 머리에 적었다. 검사 잡 이름은 이 저장소의 `ci.yml`(`python`, `image`, `ticket`, `verify`)로 바꿨다 |
| `merge.md`의 "병합 방법" 표와 보호 설정 문단 | 옮겼다 | 출시 PR의 병합 뒤 처리를 표에 더하고, "그때까지 출시 PR은 열지 않는다"를 사용자의 결정으로 바꿨다. `--admin`을 쓰지 않는다는 것과 `verify` 출처를 그대로 둔다는 것을 적었다 |
| `merge.md` "되돌려 합치기" 1·3(dev가 지워진 때의 갈래, `wait_ci`의 종료 4) | 옮겼다 | 출시 PR 병합 직후의 판정이 그 갈래를 쓴다 |
| `operations.md` 병합 문단의 되돌려 합치기 문장 | 옮겼다(두 줄로 나눴다) | 이 저장소의 운영 문서는 병합 줄이 짧고 나뉘어 있어 "출시 PR을 여는 때"와 "main의 strict" 두 줄로 썼다 |
| `docs/agents/issue-tracker.md`의 끝 줄 문장 | 옮겼다 | 끝 줄이 출시 계기라는 한 문장이다 |
| ADR 0043 이력과 본문 포인터 | 이 저장소의 ADR 0016 이력으로 옮겼다 | 이 저장소의 결정은 ADR 0016이 적는다. 본문 두 문장에 포인터를 달았다 |
| 헌법 판 3.0.87에서 3.0.93 | 옮기지 않았다 | 이 저장소의 판은 따로 센다. 1.3.0에서 1.3.1로 올렸다 |
| 카나리아 명세 넷(`.scratch/harness/probes/canary/`)과 `probes/README.md` 줄 | 옮기지 않았다 | 이 저장소에 카나리아 도구가 없다(`sibling_overlap`이 그 저장소를 따로 판정한다) |
| `tests/tools/test_protection_json.py`와 변이 여섯(`protection_json_mutations.toml`) | 옮기지 않았다 | 보호 JSON 값 시험은 agent-os가 04의 봇 Nit을 받아 더한 것이고 이 저장소의 요구가 아니다. 이 저장소의 보호 JSON은 값을 바꾸지 않았다 |
| `pr-merge/SKILL.md` 한 줄, `CONTEXT.md` | 옮기지 않았다 | 이 저장소에는 `/pr-merge`가 없고(사용자 수준 스킬을 쓴다), 용어는 `operations.md`가 정의한다(ADR 0016) |
| agent-os가 첫 출시 PR(542)과 되돌려 합치기 PR(543)을 실제로 연 것 | 하지 않았다 | 계기(끝 줄 커밋이 dev에 있다)가 아직 없다. 이 기능은 하네스 기능이라 끝 줄을 적지 않는다. 첫 출시는 끝 줄을 적는 첫 기능의 마지막 티켓을 병합한 세션이 연다 |
| 보호 설정 JSON(`protection.json`, `protection-dev.json`) | 바꾸지 않았다 | agent-os도 바꾸지 않았다(같은 값). 사용자도 strict와 `verify` 출처를 그대로 두기로 했다 |

재 보지 않은 것. 둘째 출시 PR이 실제로 `BEHIND`로 막히는지(어림), 저장소의 자동 삭제가 머리 dev를 지우지 않는다는 것(값이 꺼짐이고 삭제 금지라는 것만 읽었다), 출시 PR의 검사 줄(CodeRabbit과 `claude-review`가 건너뜀이고 `wait_ci`가 종료 4로 끝나는 것). 모두 첫 출시 PR에서 본다. 그 절은 같은 말을 적었다.
