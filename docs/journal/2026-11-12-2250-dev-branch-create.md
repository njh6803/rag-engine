# dev-branch-create: 원격 설정을 걸고 dev를 main에서 딴다 · 2026-11-12

`next-session`이 낸 지시문을 사용자가 붙여 넣어 연 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/dev-branch/issues/04-dev-branch-create.md`이고, 브랜치는 `feature/04-dev-branch-create`, 작업은 `EnterWorktree`로 들어간 워크트리 `04-dev-branch-create`에서 했다. 이번 요청 범위는 "PR과 병합까지"다. 준비, 한 것, 셀프 리뷰, PR 직전 리뷰, 회고, 검증, 다음을 차례로 둔다.

## 준비

- 세션 제목을 브랜치 이름으로 바꾼 뒤 Skill 도구로 `tidy-checkouts`를 돌았다. 루트는 main이고 추적하지 않는 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 당기지 않고 두었다(루트가 11f91c9, `origin/main`이 bcd5613). 판정에서 병합된 워크트리 `01-dev-base-tools`는 쥔 프로세스가 쉬는 세션(`feature/01-dev-base-tools`)의 것뿐이라 `end-holders`로 끄고 `remove`로 워크트리와 브랜치를 지웠다. `03-dev-base-skills-docs`(그 세션이 돈다)와 `search-eval-design`(병합된 PR 없음)은 남겼다.
- `EnterWorktree`가 만든 브랜치 이름(`worktree-04-dev-branch-create`)을 `git switch -c`로 `feature/04-dev-branch-create`에 옮기고 옛 브랜치를 지웠다. 앱의 `ExitWorktree` 안내가 옛 이름을 말한 것은 그 기록이 낡아서다.
- 읽은 것: 일지 `2026-11-12-1837-dev-base-skills-docs`의 "다음", 티켓 04·05, ADR 0016, `docs/constitution/operations.md`의 가드레일·브랜치와 병합, `next-session`의 `SKILL.md`·`merge.md`·`retro`. 01·02·03의 `Status:`는 모두 done이고 `git log origin/main`에 #26, #24, #25로 있었다.

## 한 것

- 사용자에게 `AskUserQuestion`으로 세 설정을 다시 보이고 "셋 모두 승인"을 받았다. 그 전의 원격은 기본 브랜치 main, dev 없음, 열린 PR 없음, main 보호가 `required_linear_history` true와 `strict` true였다.
- (가) `tools/protection.json`의 `required_linear_history`를 false로 고쳐 PUT(응답 linear false, strict true). dev 따기: `git push origin origin/main:refs/heads/dev`, `git ls-remote`로 둘 다 `bcd5613`. (나) 새 파일 `tools/protection-dev.json`을 PUT(strict false, linear false, `verify` 필수). (다) `default_branch`를 dev로 PATCH(`git ls-remote --symref origin HEAD`가 dev). 열린 PR은 따기 전과 옮기기 직전 두 번 모두 없어 base를 옮길 PR이 없었다. `git remote set-head origin dev`를 쳤다.
- `EnterWorktree` 기준 확인: `worktree.baseRef`는 어디에도 없다. 임시 워크트리를 만들어 봤으나 dev와 main이 같은 커밋이라 구분하지 못했다. 티켓 05에 그 확인 한 줄을 넘겼다.
- 설정이 걸려 거짓이 된 서술을 맞췄다: `docs/constitution/operations.md`(가드레일, 기준 브랜치 규칙, 병합 방법, `/security-review` 줄), `next-session`의 `merge.md`, `tidy-checkouts`의 `SKILL.md`, `CLAUDE.md`, `tools/hook_push_behind_main.py` 독스트링, `.scratch/plan-head.md`. 헌법 판 1.2.0 → 1.2.1. ADR 0016에 이력 "2026-11-12 원격 설정을 걸고 dev를 땄다"를 더했다(본문 문장이 거짓이 되지 않아 포인터는 달지 않았다).
- 읽다가 알게 된 것: dev의 필수 검사 `verify`는 `app_id` 15368(GitHub Actions)로 걸렸고 main의 것은 null이다(보호 설정의 `checks`로 읽었다). 동작은 같고 ADR 이력과 티켓 05에 적었다.
- agent-os의 `dev-release-pr-step`은 `gh api`로 읽으니 `ref=dev`에서 `Status: done`이고 병합 커밋은 `fba36f7`(#546)이다. 05의 그 조건은 찼다.

## 셀프 리뷰

`code-review` 두 축. base `bcd5613`, 커밋 0, 바뀐 추적 파일 여덟(작업 트리)과 미추적 하나(`tools/protection-dev.json`). 표준 축은 Sonnet 5.5 / high, 명세 축은 이 세션의 모델로 돌았다. 둘 다 `gh api`의 GET으로 원격 상태를 대 봤다.

- 표준 축: 하드 위반 없음, Major 둘, Minor 넷, Nit 하나.
  - Major. ADR 이력이 티켓 05의 "확인할 선행 조건"을 인용했는데 그 라벨은 `directive.md`의 칸이고 05에는 없다. → 고쳤다. "티켓 `05-dev-release-pr-step`에 그 확인을 한 줄 적었다"로 맞췄다.
  - Major. `tools/hook_push_behind_main.py` 독스트링이 "보호 설정 `tools/protection-dev.json`은 티켓 04가 만든다"로 미래형이다. → 고쳤다("만들었다"). 이 줄은 내 grep에 나왔는데 지나쳤다.
  - Minor. 헌법 1.2.1과 `operations.md` 개정이 ADR 이력에 없다. → 고쳤다. 이력에 "문서 맞춤" 불릿을 더했다.
  - Minor. 낡은 조건부 서술(`docs/agents/issue-tracker.md` 7행, `merge.md` 66·75행, `tools/base_rule.py` 10행, `tools/tidy_checkouts.py` 270행의 "dev가 없는 동안/전"). → 남겼다. 이 클론이 dev를 받기 전의 갈래라 지금도 참이고, 이 티켓의 몫이 아니다(코드 주석은 01의 것이라 고치지 않았다).
  - Minor. 헌법 판 1.2.1이 형제의 1.3.0보다 낮다(`sibling_overlap`이 알린다). → 남겼다. 이유는 아래 "다음"에 있다.
  - Nit. `Status: done`인데 체크박스가 비었다. → 고쳤다. 사유를 괄호로 적었다.
  - 냄새(판단). "티켓 04가 2026-11-12에 …" 사실이 다섯 곳에 흩어졌다. → 남겼다. 각 문서의 읽는 때가 다르다.
- 명세 축: Critical 없음, Major 하나, Minor 다섯, Nit 하나.
  - Major. 체크박스 4가 "두 줄을 지시문에 실었다"를 말하는데 지시문은 병합 뒤다. → 고쳤다. 체크를 풀고 `set-head`와 `symbolic-ref`는 했다는 사유를 적었다. 병합 뒤 `next-session` 지시문이 두 줄을 싣는다.
  - Minor. 체크박스 6(EnterWorktree)이 조건문인데 비교가 불가능해 미확인이다. → 고쳤다. 체크를 풀고 미확인과 05로 넘긴 사실을 적었다.
  - Minor 둘(훅 독스트링, `tidy-checkouts` 12행 "지금처럼 main"). → 고쳤다.
  - Minor. `.scratch/plan-head.md` 19행이 05가 agent-os 병합을 기다린다고 쓰는데 그 조건은 이미 찼다. 결과 7항 "05는 막혀 있지 않다"도 04의 병합이 남아 부정확하다. → 고쳤다. `plan_table.py`로 `plan.md`를 다시 만들었다.
  - Nit. 05의 확인 명령 앞에 `git fetch origin`이 없다. → 고쳤다.
- 다시 돌린 명령: `uv run ruff check .`와 `uv run ruff format --check .` 0, `uv run python tools/check_adr_pointers.py` 0, `uv run python tools/sibling_overlap.py` 0, `uv run python tools/run_checks.py`(백그라운드)는 pytest 하나만 빨갛고 나머지(test-db, zizmor, lint-imports, check-ticket, check-instructions, check-type-escapes, pyright, pyright-linux, run-hooks)가 Passed. 아래 "검증"에 적었다.

## PR 직전 리뷰

CodeRabbit CLI는 diff를 외부 서비스로 보내서 돌리지 않고, 운영 문서 "리뷰 파이프라인"의 대체인 `bug-perf-review`를 돌렸다(기준 `bcd5613`, 커밋 `6fbcb62`, 13파일). 셀프 리뷰 반영으로 새로 쓴 문장 여섯 곳과 JSON 모양, 보호 설정의 위험 갈래를 밀 주장으로 넘겼다. 내장 `/security-review`는 돌리지 않았다. 코드 변경이 독스트링 한 단어와 보호 설정 JSON뿐이고 비밀이 없다.

- Critical·Major 없음. 밀 주장 여섯과 JSON 모양은 모두 맞았다. 원격 GET이 파일 값과 일치하고, `ci.yml`의 `pull_request`에 base 제한이 없어 dev를 base로 한 PR도 `verify`를 받는다고 확인했다.
- Nit. 필수 검사의 출처가 다르다(main `app_id` null, dev 15368). → 고쳤다. ADR 이력과 티켓 05에 적었다. JSON은 05가 main 보호를 고칠 때 함께 본다.
- Nit. `Status: done`인데 체크박스 셋이 비었다. → 남겼다. CI와 검사 둘은 이 PR이 돈 뒤에, 지시문 몫은 병합 뒤에 닫힌다.
- 보류 하나는 main용 JSON을 다시 PUT해 멱등을 보는 것이다. GET만 쓰는 리뷰어가 못 했고, 이 세션이 같은 JSON을 PUT한 응답이 GET과 같았다.

## 회고

후보 다섯. 승인 0, 기각 3, 일지에만 2, 넘김 없음. 새 훅·검사가 문턱을 지난 것이 없어 `tools/hook_report.py`는 돌리지 않았다. `uv run python tools/queue_open_rows.py`의 만료할 항목은 없었다(열린 항목 34개, 회차 5 이상은 `spec-review-transition-crossing`과 `gate-pipe-read-status`로 이 세션과 무관하다).

1. 기각. 미래형 문장 잔존(`hook_push_behind_main.py`의 "티켓 04가 만든다")을 내 grep이 보고도 지나쳤다. `code-review` 두 브리프의 주장 검증 4(미래형)가 잡도록 둔 기준이고 리뷰가 제 몫을 했다.
2. 기각. 훅 넷이 그 자리에서 막았다: Grep glob이 `.env`에 닿는 것, 저장소 전체 grep, 사용자 설정 파일을 grep하는 것, 계산한 경로의 `git -C`(서브에이전트의 `-C ../search-eval-design`). 있는 훅이 막은 사건이다.
3. 기각. 두 갈래가 같은 사건이다. 티켓 04의 5단계가 `EnterWorktree`가 dev에서 서는지 보라고 했는데 dev와 main이 같은 커밋이라 구분할 수 없었다. 같은 커밋의 두 ref를 견주는 시험은 구분하지 못한다는 사실을 일지와 05에 넘겼고(반영 끝), 스킬·지침의 문장을 바꿀 일이 아니다.
4. 일지에만. `tests/adapters/test_parse_runner.py`의 멈춘 자식 시험(러너 한 번)과 `tests/app/test_job_lease.py`의 5초 제한 시험(첫 커밋 시도)이 여러 세션이 함께 도는 부하에서만 빨갰다. 단독으로 12개와 1개가 지났다. 앞 일지가 받아들여 닫은 종류(부하에서만 빨간 시간 시험)의 새 사례라 항목을 잇지 않는다(retro 5단계). 같은 종류의 닫힌 항목은 `token-expiry-test-load-margin`이다.
5. 일지에만. `EnterWorktree`가 만든 브랜치를 `git switch -c`로 옮기자 앱의 `ExitWorktree`가 옛 이름을 안내했다. 앱 기록이 낡은 것이고 이 세션에서 한 번 본 모양이다.

## 검증

- `uv run ruff check .`와 `uv run ruff format --check .`는 초록이었다. `uv run python tools/check_adr_pointers.py` 0, `uv run python tools/sibling_overlap.py` 0(헌법 1.2.1, 형제 최고 판 1.3.0), `uv run python tools/plan_table.py` 0.
- `uv run python tools/run_checks.py`(편집 중간의 트리): test-db, zizmor, lint-imports, check-ticket, check-instructions, check-type-escapes, pyright, pyright-linux, run-hooks가 Passed, pytest는 3824개 통과에 1개 실패(`tests/adapters/test_parse_runner.py`의 멈춘 자식 시험, 단독으로 1 passed).
- 첫 커밋 시도의 pre-commit은 `tests/app/test_job_lease.py`의 5초 제한 시험 하나로 막혔다(3824개 통과, 1개 실패, 628초). 테스트 DB 주소를 준 단독 실행은 12 passed(67.6초)였다. 파서 쪽도 임대 쪽도 이 브랜치가 바꾸지 않은 코드다. 같은 커밋의 둘째 시도가 통과해 커밋 `6fbcb62`가 섰다.
- 이 PR의 CI 결과와 병합 뒤 확인은 아래 "PR 봇 리뷰"와 "다음"에 적는다.

## 다음

- 이 PR은 base dev, 머리 `feature/04-dev-branch-create`다. 병합하면 dev가 main보다 한 커밋 앞서게 되고, 그때부터 05가 시작할 때 `EnterWorktree`로 만든 새 워크트리에서 `git fetch origin` 뒤 `git rev-parse HEAD origin/dev origin/main`을 쳐 HEAD가 `origin/dev`와 같은지 본다(티켓 05의 둘째 불릿). 다르면 ADR 0016 Consequences "다른 세션"의 서술을 고치고 이력에 적는다.
- 다음 작업은 05(`05-dev-release-pr-step`)다. 막는 조건은 04의 병합 하나이고 agent-os의 `dev-release-pr-step`은 이미 병합됐다(위 "한 것"). 05가 main의 strict를 사용자에게 다시 묻고, 출시 PR의 순서를 옮긴다. 그때 `verify`의 출처(main null, dev 15368)도 본다.
- 다른 체크아웃이 칠 두 줄: `git fetch origin`과 `git remote set-head origin dev`. 워크트리는 주 체크아웃의 `.git`을 함께 써서 한 번이면 모든 워크트리에 미친다.
- 헌법 판 충돌 후보. 형제 워크트리 `search-eval-design`(브랜치 `docs/search-eval`, 아직 PR 없음)이 1.3.0과 ADR 0016, `docs/constitution/README.md`를 고치는 중이다. 그 PR이 먼저 병합되면 이 PR은 1.2.1이 1.3.0보다 낮아 충돌하므로 이 PR을 합쳐 판을 1.3.1로 옮긴다. 이 PR이 먼저 병합되면 그쪽이 1.3.0을 그대로 쓰고 ADR 0016의 이력 끝에 자기 항목을 붙인다(글자 충돌은 이력 끝 한 자리다). 그 PR을 열 때 base는 기본 브랜치인 dev다.
- 사용자에게 남은 일. 루트 체크아웃(`C:\project\rag-engine`)은 main에 추적하지 않는 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 `tidy-checkouts`가 루트를 dev로 옮기지 못한다(루트가 깨끗하고 `git rev-list --count origin/main..HEAD`가 0일 때만 옮긴다). 두 파일을 지우거나 옮기면 주 체크아웃 세션의 `/tidy-checkouts`가 루트를 dev로 옮긴다. 그때까지 루트의 훅과 스킬이 옛 사본으로 돈다.
- 사용자 수준 스킬(`git-pr`, `git-pr-merge`, `git-pr-feedback`, `git-branch`)은 이 저장소가 고치지 않았다(일지 `2026-11-12-1837-dev-base-skills-docs`의 "다음"). 기본 브랜치가 dev가 되어 base를 주지 않은 `gh pr create`는 dev로 가고, 핫픽스는 `gh pr create --base main`으로 연다(운영 문서 병합 절).
- 앞 일지가 뒤로 넘긴 봇 지적 둘 가운데 (2)(보호 설정이나 strict의 결정을 바꾸면 운영 문서 가드레일 절과 되돌려 합치기의 필요 판정 근거 문장을 같이 고쳐 판을 올린다)는 이 PR이 했다. 가드레일 절은 맞췄고, 필요 판정의 근거 문장은 strict를 바꾸지 않아 두었다. 05가 strict를 바꿀 때 다시 본다. (1)(첫 핫픽스 PR에서 CodeRabbit 수동 호출과 `/security-review` 범위를 재 보기)는 그대로 남아 있다.
- 주 체크아웃 미갱신: 루트는 main(11f91c9). 이 세션은 주 체크아웃을 당기지 않는다.
