# dev-release-pr-step: 출시 PR을 여는 순서를 옮기고 main의 strict를 그대로 둔다 · 2026-11-13

`next-session`이 낸 지시문을 사용자가 붙여 넣어 연 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/dev-branch/issues/05-dev-release-pr-step.md`이고, 브랜치는 `feature/05-dev-release-pr-step`, 작업은 `EnterWorktree`로 들어간 워크트리 `05-dev-release-pr-step`에서 했다. 이번 요청 범위는 "PR과 병합까지"다. 준비, 한 것, 셀프 리뷰, PR 직전 리뷰, 회고, 검증, 다음을 차례로 둔다. 이 티켓이 하네스 기능 `dev-branch`의 마지막 티켓이다.

## 준비

- 세션 제목을 브랜치 이름으로 바꾼 뒤 Skill 도구로 `tidy-checkouts`를 돌았다. 루트는 main이고 추적하지 않는 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 당기지 않고 두었다(루트가 11f91c9). 판정에서 병합된 `03-dev-base-skills-docs`는 쥔 프로세스가 쉬는 세션의 것뿐이라 `end-holders`로 끄고 `remove`로 워크트리와 브랜치를 지웠다. 휴지통의 `.venv` 한 곳이 다른 체크아웃의 `python.exe` 열세 개가 올린 `.pyd` 때문에 `empty-trash`로도 비워지지 않아 그대로 남겼다(다음 정리가 비운다). `04-dev-branch-create`(그 세션이 돈다)와 `search-eval-design`(병합된 PR 없음)은 남겼다.
- `EnterWorktree`가 만든 브랜치 이름(`worktree-05-dev-release-pr-step`)을 `git branch -m`으로 `feature/05-dev-release-pr-step`에 옮겼다. 새 워크트리의 `HEAD`는 `origin/dev`(`0caa20f`)와 같았고 `origin/main`(`bcd5613`)과 달랐다. 04가 넘긴 `EnterWorktree` 기준 확인이 이것이다(ADR 0016 Consequences "다른 세션"의 서술과 같다). 그 뒤 형제 PR 27이 dev에 병합돼(`bf5a0ad`) `git merge --ff-only origin/dev`로 받았다.
- 읽은 것: 일지 `2026-11-12-2250-dev-branch-create`의 "다음", 티켓 05, ADR 0016, `merge.md` 전체, `SKILL.md`의 결정표, `operations.md`의 가드레일·브랜치와 병합, agent-os의 `dev-release-pr-step` 티켓 파일(`origin/dev`에서 `Status: done`, 병합 커밋 `fba36f78a`, PR 546)과 그 커밋이 바꾼 `SKILL.md`·`merge.md`·`operations.md`·`issue-tracker.md`·헌법 README·ADR 0043의 diff. 일지 "다음"의 헌법 판 계획(1.2.1을 1.3.1로 옮긴다)은 낡았다. 형제 PR 27이 먼저 병합돼 헌법이 1.3.0이었고 이 변경이 1.3.1로 올렸다.

## 한 것

- 사용자에게 `AskUserQuestion`으로 main의 strict와 `verify`의 출처를 물었다. 답은 "strict 유지 + 병합 뒤 되돌려 합치기 (Recommended)"와 "그대로 둔다 (Recommended)"다. 원격의 보호 설정은 바꾸지 않았고(PUT 없음) `gh api`의 GET으로 읽은 값만 티켓에 적었다.
- `SKILL.md` 결정표에 "출시 PR" 줄을 더했다(계기는 끝 줄 커밋이 dev에만 있고 열린 출시 PR이 없는 것. 열린 PR이 끊긴 것이면 이어받기로 잇는다). `merge.md`에 "## 출시 PR" 절(이어받기, 계기, 전제 확인, 열기, 기다리고 병합한다, 병합 뒤)을 더하고, "병합 방법" 표와 보호 설정 문단과 "되돌려 합치기"의 1·3·끝 줄을 맞췄다. agent-os의 결정표 "되돌려 합치기" 줄은 03이 이미 같은 판정(`--is-ancestor`)으로 옮겨 두어 건드리지 않았다.
- `operations.md`의 "그때까지 출시 PR은 열지 않는다" 줄을 "출시 PR을 여는 때"와 "main의 strict" 두 줄로 바꾸고, 23행의 병합 문장을 맞췄다. `issue-tracker.md`의 끝 줄 문장에 출시 계기와 하네스 기능이 계기가 아니라는 것을 한 문장씩 더했다. 헌법 판을 1.3.0에서 1.3.1로 올렸다.
- ADR 0016에 이력 "2026-11-13 출시 PR을 여는 순서를 옮기고 main의 strict를 그대로 둔다"를 더하고 본문 세 곳에 포인터를 달았다. `.scratch/plan-head.md`의 "하네스 기능" 문단에서 dev-branch를 지우고 `uv run python tools/plan_table.py`로 `.scratch/plan.md`를 다시 만들었다. 이 하네스 기능의 기능 계획에는 `**슬라이스:**` 줄이 없어 `**끝:**` 줄을 적지 않았다.
- 티켓 05에 옮긴 곳과 옮기지 않은 곳과 까닭의 표를 적었다. 첫 출시 PR은 이 티켓이 열지 않았다. 계기(끝 줄을 적은 커밋이 dev에 있다)가 아직 없다.

## 셀프 리뷰

`code-review` 두 축. base `bf5a0ad`, 커밋 0, 바뀐 추적 파일 아홉(작업 트리), 미추적 0. 표준 축은 Sonnet 5.5 / high, 명세 축은 이 세션의 모델로 돌았다. 두 축 모두 임시 저장소나 `gh api`의 GET으로 대 봤다.

- 표준 축: Major 둘, Minor 셋, Nit 하나와 주장 검증의 Major 하나, Minor 하나.
  - Major. 출시 PR 절에 병합 전(봇 회차, 일지, `headRefOid` 대조)을 하지 않는다는 문장이 없다. `hook_pr_next_session`이 `gh pr create` 직후 넣는 계기와 `SKILL.md` 순서 1이 병합 전 1~4를 먼저 읽게 한다. → 고쳤다. 절 머리에 "이 PR에는 위 병합 전의 봇 회차와 일지를 하지 않는다 … 머리 SHA는 병합 직전 `gh pr view`로 읽은 값"을 더했다.
  - Major. 열린 출시 PR이 끊기면 결정표의 어느 줄도 잇지 않는다(되돌려 합치기 줄에는 있는 끊긴 PR 잇기가 출시 줄에는 없다). → 고쳤다. 출시 줄의 조건에 "열린 PR이 진행하다 끊긴 것이다"를 더하고(되돌려 합치기 줄과 같은 판정) 이어받기로 잇게 했다. agent-os는 두 세션이 한 PR을 함께 잇지 않게 하려고 이 갈래를 뺐고, 이 저장소는 그 위험보다 고아 PR을 더 크게 봤다.
  - Minor. 이어받기의 "일지에 적어 두고"는 출시 세션에 커밋할 브랜치와 PR이 없어 둘 곳이 없다. → 고쳤다. 번호는 보고에 적고 `gh pr list`·`gh pr view`로 다시 읽게 했다. 병합 뒤 되살리기가 쓰는 SHA도 병합한 PR의 `headRefOid`로 바꿨다.
  - Minor. `SKILL.md` 출시 줄에 `git fetch origin`이 없다. → 고쳤다. Minor. 05 티켓의 "검사 넷"이 비었다. → PR을 열기 전에 채운다. Nit. `.scratch/dev-branch/plan.md` 7행의 "그때까지 출시 PR은 열지 않는다". → 고쳤다. 05가 순서를 옮겼다는 괄호를 더했다.
  - Major(주장 검증). ADR 0016 본문의 "main이 출시된 기능만 든 머리가 되게 하기 위해서다"와 새 절의 "진행 중 기능의 조각도 함께 오른다"가 부딪친다. → 고쳤다. 그 문장 뒤에 포인터를 달고 이력에 불릿 하나("출시 때 진행 중 기능의 조각도 함께 오른다")를 더했다.
  - Minor(주장 검증). 헌법 판 patch의 근거("두 문서가 규칙을 더한다")가 거버넌스의 patch와 어긋나 보인다. → 고쳤다. "새 원칙이나 새 절 없이 기존 절의 줄을 바꾸고 더해"로 맞췄다.
  - 확인한 것. `ci.yml`의 잡 이름(`python`, `image`, `ticket`, `verify`), `gh run list … --event push`의 실제 실행(`headSha`가 `origin/main`과 같고 `success`), 계기 명령의 모양(`-G'^\*\*슬라이스:\*\*'`는 `9f1ee79`를 찾고 `끝` 줄 커밋은 이 저장소 이력에 아직 없다)이다.
- 명세 축: Major 하나, Minor 다섯, Nit 하나와 범위 넘침 둘, 틀려 보이는 것 다섯.
  - Major. 위 표준 축의 열린 출시 PR 고아 갈래와 같다. 같이 고쳤다.
  - Minor. `merge.md` "되돌려 합치기" 끝 줄의 "diff가 계속 1이다"가 남았다. → 고쳤다("`--is-ancestor` 판정이 계속 1이다"). Minor. 출시 절은 `wait_ci`의 종료를 4만 정상이라 적고 되돌려 합치기는 0이거나 4라 적었다. → 고쳤다(출시 절에 "0일 수도 있다").
  - Minor. 병합 뒤 dev가 지워진 채 끊기면 신호가 없다(두 결정표 줄이 모두 `origin/dev`를 요구한다). → 고쳤다. 병합한 직후 같은 턴에 확인한다는 문장을 더했다. 이 갈래는 밟은 적이 없고, dev가 삭제 금지로 보호돼 일어날 확률이 낮아 줄을 더 만들지 않았다.
  - Minor. ADR "거부한 두 길"의 까닭이 사용자 답에 없다. → 고쳤다. "고르지 않은 두 길"로 바꾸고 선택지에 적힌 까닭이라고 밝혔다. Minor. ADR "옮기지 않은 것"이 "도구와 시험 틀이 없어"라고 적었는데 `tests/tools/`와 `tools/mutate.py`가 있다. → 고쳤다. 카나리아는 도구가 없어서, 보호 JSON 값 시험은 이 저장소의 요구가 아니어서로 가렸다. Minor. `operations.md` 23행의 "1~3"이 출시 절의 "1~2, 3은 건너뛴다"와 어긋난다. → 고쳤다. Minor. `issue-tracker.md`가 하네스 기능을 끝 줄 계기에서 빼지 않는다. → 고쳤다. Nit. 사용자 답의 따옴표가 원문 라벨과 다르다. → 고쳤다(ADR과 티켓 모두 원문 라벨).
  - Nit. `operations.md`의 "이 줄이나 보호 설정을 바꾸면 … 같이 고친다"는 agent-os에도 명세에도 없다. → 남겼다. 04 일지의 "다음"이 05에 넘긴 봇 지적 (2)를 옮긴 것이다. Nit. `plan.md`의 원천 목록과 ADR "티켓 다섯"에 `dev-release-pr-step`이 없다. → 남겼다. 그 시점의 셈이고 이 티켓이 하네스 기능의 마지막이다.
- 다시 돌린 명령: `uv run ruff check .`와 `uv run ruff format --check .` 0, `uv run python tools/check_adr_pointers.py` 0, `uv run python tools/plan_table.py` 0, `uv run python tools/sibling_overlap.py` 0. `uv run python tools/run_checks.py`는 수정 전 트리에서 0이었고 수정 뒤의 전체는 커밋이 부르는 pre-commit이 돈다(아래 "검증").

## PR 직전 리뷰

CodeRabbit CLI는 diff를 외부 서비스로 보내서 돌리지 않고, 운영 문서 "리뷰 파이프라인"의 대체인 `bug-perf-review`를 돌렸다(기준 `bf5a0ad`, 커밋 0, 문서·스킬·티켓·ADR 아홉 파일). 셀프 리뷰 반영으로 새로 쓴 문장 여섯 곳(출시 줄의 조건, 이어받기, 병합 전 생략, 병합한 PR의 `headRefOid`, ADR 새 이력, 운영 문서 새 두 줄)을 밀 주장으로 넘겼다. 내장 `/security-review`는 돌리지 않았다. 코드 변경이 없고 비밀이 없다.

- Critical·Major 없음. Minor 셋, Nit 둘. 성능 축은 해당 없음(병합 뒤 한 번 도는 절차다).
- Minor. 출시 PR을 열면 `hook_pr_next_session`이 `gh pr create` 자체에 반응해 `merge.md`를 처음부터 읽게 하는데, 병합 전 건너뜀 단서가 출시 PR 절 안에만 있다. → 고쳤다. "병합 전" 머리에 머리가 dev나 main인 PR은 그 절을 건너뛴다는 문장을 더했다.
- Minor. 이어받기에 `git fetch origin`이 없고 `wait_ci --head`가 로컬 `origin/dev`를 쓰면 옛 값이 어긋난다. → 고쳤다. 이어받기 첫머리에 `git fetch origin`을 넣고, 이어받을 때의 `--head`는 `gh pr view <번호> --json headRefOid`의 값으로 했다.
- Minor. 출시 세션은 일지를 못 남겨 사용자에게 넘긴 PR을 다음 세션이 끊긴 것으로 읽고 되집는다. → 고쳤다. 넘길 때 PR 코멘트 `사용자에게 넘김: <까닭>`을 남기게 하고 결정표 출시 줄의 판정이 그 코멘트를 읽게 했다.
- Nit. `merge.md` 18행이 출시 PR 병합을 "1~3"으로 적었다. → 고쳤다. Nit. `출시 보류` 뒤의 "원래 줄로 돌아간다"가 조건이 계속 참이라 같은 줄을 다시 고르게 한다. → 고쳤다. 그 세션에서는 출시 줄을 건너뛰고 다음 줄에서 고른다고 적었다.
- 밀어 본 주장 가운데 맞은 것: 병합한 PR도 `gh pr view 28 --json headRefOid`가 `ae30cdf…`를 내고(PR 28), 보호 설정의 GET 값이 ADR 이력의 값과 같다. 두 결정표 줄(`--is-ancestor` 1과 0)은 겹치지 않는다. 이 저장소에서 계기 명령의 양성 쪽(끝 줄 커밋을 찾는 것)은 `**끝:**`을 적은 기능이 없어 아직 재 보지 못했다.

반영으로 새로 쓴 사실 문장(원문): "머리가 dev나 main인 PR(출시 PR, 되돌려 합치기 PR)은 이 절을 건너뛰고 아래 "출시 PR"과 "되돌려 합치기"의 절차를 따른다."(`merge.md` 병합 전), "출시 세션은 일지를 못 남기므로 사용자에게 넘길 때는 PR 코멘트에 `사용자에게 넘김: <까닭>`을 남기고 …, 그 코멘트가 있는 열린 PR은 결정표가 고르지 않는다."(`merge.md` 이어받기).

## 회고

후보 여섯. 승인 0, 기각 4, 일지에만 2, 넘김 없음. 새 훅·검사가 문턱을 지난 것이 없어 `tools/hook_report.py`는 돌리지 않았다. `uv run python tools/queue_open_rows.py`는 열린 항목 36개, 만료할 항목 없음, 회차 5 이상은 `spec-review-transition-crossing`과 `gate-pipe-read-status`로 이 세션과 무관하다.

1. 기각. 맨 `python`, 다른 체크아웃으로의 `cd`, `git -C <다른 경로>`, `.env`에 닿는 Grep glob, Git Bash의 경로 변환(`origin/dev:.scratch/…`)을 훅 다섯이 그 자리에서 막거나 알렸다. 있는 훅이 막은 사건이다.
2. 기각. 열린 출시 PR이 고아가 되는 갈래와 병합 전 단계가 출시 PR에 섞이는 갈래를 두 리뷰 축이 모두 잡았다. `code-review` 브리프의 "갈래 밟기"가 잡도록 둔 기준이고 리뷰가 제 몫을 했다.
3. 기각. 옮기는 문서의 "agent-os에서 본 것"과 "이 저장소에서 본 것"을 섞어 적을 위험은 주장 검증의 근거 종류 항목(5)이 잡는다. 이번에는 섞인 곳이 없었다.
4. 기각. `EnterWorktree`가 만든 브랜치 이름을 `git branch -m`으로 옮겨야 한다는 것은 `implement` 스킬이 이미 적고 있고 이번에 그대로 했다.
5. 일지에만. `tidy-checkouts`의 `empty-trash`가 다른 체크아웃의 `python.exe`가 올린 `.pyd`로 비우지 못하고 `.venv` 한 곳을 휴지통에 남겼다. 스킬이 예상한 종류(다음 정리가 비운다)이고 새 사건이 아니다.
6. 일지에만. 검사 러너(`tools/run_checks.py`)가 문서만 바뀐 변경에서도 pytest 전체를 돌아 15분 안팎이 걸리고, 여러 세션이 함께 도는 부하에서 시간 시험 둘(`tests/adapters/test_parse_runner.py`의 멈춘 자식, `tests/test_serve_command.py`의 30초 기동)이 빨갰다. 단독으로는 38개가 지났다. 앞 일지(`2026-11-12-2250-dev-branch-create`)가 받아들여 닫은 종류(부하에서만 빨간 시간 시험)의 새 사례라 항목을 잇지 않는다(retro 5단계). 같은 종류의 닫힌 항목은 `token-expiry-test-load-margin`이다.

## 검증

- `uv run ruff check .`와 `uv run ruff format --check .` 0, `uv run python tools/check_adr_pointers.py` 0, `uv run python tools/plan_table.py` 0, `uv run python tools/sibling_overlap.py` 0(헌법 1.3.1, 형제 최고 판 1.3.0).
- `uv run python tools/run_checks.py`: 셀프 리뷰 반영 전의 트리는 종료 0이었다. 최종 트리(PR 직전 리뷰 반영까지)는 test-db, check-ticket, zizmor, lint-imports, check-type-escapes, check-instructions, pyright-linux, pyright, run-hooks가 Passed이고 pytest가 3823개 통과에 2개 실패(901초)였다. 실패는 `tests/adapters/test_parse_runner.py`의 멈춘 자식 시험(Windows에서 기대하는 `PARSE_FAILED` 대신 `PARSE_TIMEOUT`이 왔다)과 `tests/test_serve_command.py`의 "serve가 30초 안에 뜨지 않았다"다. 이 브랜치는 문서·스킬·티켓·ADR만 바꿔 두 시험이 닿는 코드가 없고, 두 파일을 테스트 DB 주소를 주고 단독으로 돌리자 38 passed(45초)였다. 다른 세션이 함께 도는 부하에서만 빨갰다.

## 다음

- 이 PR은 base dev, 머리 `feature/05-dev-release-pr-step`이다. 병합하면 하네스 기능 `dev-branch`의 티켓 다섯이 모두 done이다. 이 PR이 병합된 뒤 main은 dev보다 `0caa20f`, `bf5a0ad`와 이 PR만큼 뒤처진다. 그 변경은 하네스·문서뿐이라 계기가 아니고 다음 기능의 출시 PR에 실려 오른다.
- 다음 작업은 core의 마지막 티켓 `16-search-latency-probe`(`ready-for-agent`)다. core의 마지막 티켓을 닫는 커밋이 기능 계획에 `**끝:**` 줄을 적으므로, 그 PR이 dev에 병합된 뒤 `next-session` 결정표의 "출시 PR" 줄이 처음으로 실제 계기가 된다. 그 세션이 `merge.md`의 "출시 PR"을 처음 밟으므로 그 절의 명령과 판정(전제 확인의 `gh run list`, 서식, `wait_ci`의 종료 4, 병합 뒤 `ls-remote`)을 이 저장소에서 처음 보게 된다. 어긋나면 그 절과 ADR 0016 이력을 고친다. 둘째 출시 PR이 실제로 `BEHIND`로 막히는지는 그다음 출시에서 본다.
- 사용자에게 남은 일. 루트 체크아웃(`C:\project\rag-engine`)은 main에 추적하지 않는 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 `tidy-checkouts`가 루트를 dev로 옮기지 못한다. 두 파일을 지우거나 옮기면 주 체크아웃 세션의 `/tidy-checkouts`가 루트를 dev로 옮긴다. 그때까지 루트의 훅과 스킬이 옛 사본으로 돈다.
- 사용자 수준 스킬(`git-pr`, `git-pr-merge`, `git-pr-feedback`, `git-branch`)은 이 저장소가 고치지 않았다. 기본 브랜치가 dev가 되어 base를 주지 않은 `gh pr create`는 dev로 가고, 핫픽스는 `gh pr create --base main`으로 연다. 출시 PR과 base가 dev인 PR의 병합은 `git-pr-merge`를 쓰지 않고 `merge.md`의 "워크트리에서 병합할 때" 1~3으로 한다.
- 뒤로 넘긴 것: `tools/hook_push_behind_main.py`가 dev에서도 뒤처진 푸시를 막을지는 정하지 않았다(agent-os도 같다). 첫 핫픽스 PR에서 CodeRabbit 수동 호출과 `/security-review` 범위를 재 보는 일(04 일지 "다음"의 (1))도 남는다.
- 주 체크아웃 미갱신: 루트는 main(11f91c9). 이 세션은 주 체크아웃을 당기지 않는다.
