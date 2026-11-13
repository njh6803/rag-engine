# code-review-transition-crossing: 셀프 리뷰 명세 축 브리프에 상태 전이의 교차·잔류 결함을 밟으라는 한 줄을 더한다 · 2026-11-13

대기열 `spec-review-transition-crossing`을 harness 티켓 `.scratch/harness/issues/code-review-transition-crossing.md`로 쓰고 반영한 기록이다. 브랜치는 `chore/code-review-transition-crossing`이고, `next-session` 지시문으로 연 새 세션이 `tidy-checkouts`를 돈 뒤 새 워크트리(HEAD가 `origin/dev`의 defc690과 같았다)에서 했다. 코드와 시험은 바꾸지 않았다.

## 한 것

- `.claude/skills/code-review/SKILL.md`의 "Spec sub-agent prompt" 절에 조건부 bullet 하나를 더했다. 본 세션이 명세와 diff를 읽고 명세나 이 변경이 상태(문서 상태, 색인 상태, 작업, 임대, 세대, 색인 판처럼 전이하며 값이 바뀌는 것)를 정하거나 바꾼다고 판정하면, 브리프 끝에 `(d) 전이마다 다른 전이와 동시에 일어나는 교차와, 실패·중단 뒤에 남는 상태를 하나씩 밟아, 지운 것이 되살아나거나 전환이 영영 막히는 자리를 낸다`를 그대로 붙이라고 시킨다.
- 대기열 항목의 상태 줄을 `닫힘 (티켓 경로, 날짜, 한 것)`으로 고쳤다.
- `uv run python tools/plan_table.py`를 돌렸고 `.scratch/plan.md`는 바뀌지 않았다(harness 티켓은 전체 계획 표에 들지 않는다).

## 셀프 리뷰

`code-review` 두 축. base `defc690`, 커밋 0, 바뀐 추적 파일 둘과 미추적 하나(티켓). 표준 축은 Sonnet 5.5 / high, 명세 축은 이 세션의 모델로 돌았다. 이 변경은 에이전트가 따르는 절차(스킬)를 바꾸므로 두 브리프에 갈래 밟기 문단과 주장 검증 목록을 넣었다.

- 명세 축: Critical·Major 없음, 범위 넘침 없음. Minor 하나. 새 bullet이 "그대로 붙여 넣는다"를 쓰지 않아 브리프의 따옴표 문자열 안 어디에 붙이는지가 열려 있다.
  - → 고쳤다. "위 브리프 끝(Under 400 words. 앞)에 한 줄을 그대로 붙여 넣는다"로 못 박았다.
- 표준 축: 문서화된 표준 위반 없음. Major 둘, Minor 넷, Nit 둘.
  - Major 1. 조건이 "명세가 상태를 정하면"이라 PR #3처럼 명세를 쓰는 변경(상태를 정한 것이 읽는 명세가 아니라 리뷰 대상 diff)에서는 (d)가 붙지 않는다. → 고쳤다. 조건을 명세나 이 변경이 상태를 정하거나 바꾼다로 넓혔다. 대기열 항목이 적은 조건("명세가 상태를 정하면")과 달라진 것이라 티켓의 What to build에 그 까닭을 적었다.
  - Major 2. 조건 판정에는 명세와 diff의 내용을 읽어야 하는데 Spec 프롬프트는 경로만 넘겨도 되고, bullet이 따옴표 브리프와 떨어져 있어 붙이는 것을 잊기 쉽다. → 고쳤다. 본 세션이 명세와 diff를 읽고 판정한다는 말과 붙이는 자리를 적었다.
  - Minor 3. bullet이 PR #3의 봇 지적 열둘 가운데 여덟이라 쓰는데 대기열 본문은 "1회차 CodeRabbit 지적 열둘 가운데 여덟"이다. → 고쳤다. "PR #3의 1회차 봇 지적"으로 고치고 근거를 "대기열 항목의 서술"로 적었다. 일지 `2026-11-10-0118-core-spec.md`가 가리킨 번호가 일곱이라는 지적은 이 변경이 그 일지를 읽어 대 본 것이 아니므로 확인하지 않았다(표준 축이 낸 것을 옮긴다).
  - Minor 5. (a)~(c)는 명세 줄 인용을 요구하지만 (d)의 결함은 명세가 침묵한 자리에서 난다. → 고쳤다. 인용 대신 어느 전이와 어느 전이가 교차하는지를 적게 했다.
  - Minor 6. 예시에 임대·세대가 없다. → 고쳤다. 두 낱말을 더하고 나열이 예시임을 적었다.
  - Minor 4. 6단계 5가 전체 리뷰를 다시 돌리지 않으므로 (d) 지적의 고침이 낳은 새 교차(대기열 8회차)는 다시 밟히지 않는다. → 남겼다. 대기열 항목이 승인한 것은 브리프에 한 줄이다. 반영 단계의 절차를 바꾸는 것은 이 티켓의 범위 밖이다. 아래 "다음".
  - Nit. `SKILL.md` 머리 주석은 괄호 속 대기열 인용이 agent-os의 기록이라고 하는데 새 인용은 이 저장소의 항목을 이름으로 가리킨다. → 남겼다. 그 주석이 `tools/check_instructions.py`의 센티널이라 건드리지 않는다.
  - Nit. 수용 기준 4번이 커밋 전에 `[x]`다. → 남겼다. 선례(`session-model-fable-5-2`)와 같다.
- 반영으로 새로 쓴 사실 문장(PR 직전 리뷰와 PR 봇이 겨냥할 것): 새 bullet의 "PR #3의 1회차 봇 지적 열둘 가운데 여덟이 이 꼴이었다(대기열 spec-review-transition-crossing의 서술)", 티켓의 What to build가 적은, 조건을 넓힌 까닭 문장.

## 검증

- `uv run python tools/sibling_overlap.py`는 0(새 번호 없음, 번호 겹침 없음, 함께 고친 파일 없음)이었다.
- 손으로 치는 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)은 커밋의 pre-commit으로 갈음한다. 이 브랜치는 파이썬 파일을 바꾸지 않았다. 커밋은 네 번 시도했다.
  - 첫 시도: 검사 러너의 pytest가 `2 failed, 3823 passed in 1143.79s`였다. 빨간 것은 `tests/app/test_job_lease.py::test_임대를_잃은_것이_드러나면_처리를_멈추고_문서에도_작업_행에도_쓰지_않는다`와 `tests/app/test_worker_service.py::test_듣기가_예기치_않은_예외로_죽어도_폴링으로_계속_처리하고_알린다`다. 두 파일만 따로 돌린 `uv run pytest tests/app/test_job_lease.py tests/app/test_worker_service.py -q -p no:cacheprovider`(`RAG_TEST_DATABASE_URL`은 `compose.test.yml`의 값)는 `21 passed in 194.81s`였다.
  - 둘째 시도: 러너의 열 전부와 pytest가 Passed(1001.5s)였고, `commit-msg` 훅이 제목 `89자 > 72자`로 막았다. 제목을 줄이고 일지의 따옴표 인용 경고(경고만 한다) 셋의 따옴표를 뗐다.
  - 셋째 시도: pytest가 `1 failed, 3824 passed in 643.74s`였고 빨간 것은 `tests/adapters/test_parse_runner.py::test_메시지를_보내다_멈춘_자식이_있어도_수신이_영영_막히지_않는다`다(Windows 기대 `parse_failed`에 `parse_timeout`이 왔다). 그 파일만 따로 돌린 것은 `36 passed in 100.71s`였다.
  - 넷째 시도: 통과했고 커밋 `0ccb07d`가 만들어졌다. 시험은 고치지 않았다. 따로 돌린 시간이 평소보다 길어(21개 194초, 36개 100초) 다른 세션의 러너와 부하를 나눈 것으로 어림한다. 프로세스 목록은 보지 않았다.

## PR 직전 리뷰

`coderabbit-review` 서브에이전트(Sonnet)가 CodeRabbit CLI 0.7.5를 한 번 돌렸다. 명령은 `coderabbit review --agent --base-commit defc690196d08f97980648444393ce5ae045e446`이고 종료 코드 0, 리뷰는 끝까지 돌아(`review_completed`) 지적이 0건이었다. 좌석은 `Seat: not assigned`(`Plan: Free`)였다. 리뷰한 파일은 넷(`SKILL.md`, 티켓, 대기열 항목, 이 일지)이다. 고친 것도 남긴 것도 없다. CLI가 보지 못한 것은 이 절과 아래 회고·검증의 이번 편집이고, CLI에는 밀 주장을 넘기는 인자가 없어 위 "반영으로 새로 쓴 사실 문장"은 PR 봇이 본다.

## 회고

낸 후보 다섯. 승인 1, 기각 4, 넘김 없음.

4. 제목이 72자를 넘는 커밋 메시지(89자)가 pre-commit의 느린 검사(`parallel-checks` 1002초)를 다 지난 뒤 `commit-msg` 훅에서야 막혔다. → 승인, 대기열 `commit-msg-after-slow-checks`에 2회차를 더했다(1회차는 허용되지 않은 타입 `ci:`가 480초 뒤에 막힌 일지 `2026-11-12-1833-dev-review-bot-off.md`). 더하는 것이라 다섯 번째에 반영한다. 사건: 위 검증의 둘째 시도. 층: 그 항목이 든 PreToolUse 훅(검사가 잡을 수 있는 것은 검사로). 되돌림: PR 하나로 되돌릴 수 있다.
5. 전체 스위트의 시간 시험이 시도마다 다른 것이 빨갰다(아래 검증). → 기각. 부하에서만 빨간 시간 시험은 닫힌 항목 `token-expiry-test-load-margin`이 받아들여 닫은 종류라 새 항목으로 잇지 않고 일지에만 적는다.

1. 처음 쓴 bullet의 조건이 PR #3처럼 명세를 쓰는 변경을 놓치고, 조건 판정의 시점과 붙이는 자리가 열려 있었다(셀프 리뷰 표준 축 Major 둘). → 기각. 리뷰가 제 몫을 한 것이고, 구현 때 실리는 지침을 어긴 사건이 아니라 새로 쓴 문장의 결함이다. 반영으로 고쳤다.
2. 복합 셸 명령(`BASE=$(git merge-base ...)`에 이어 여러 git)을 워크트리 가드가 거부해 명령을 나눠 다시 쳤다. → 기각. 앱의 가드가 그 자리에서 막았고 든 비용은 호출 한 번이다.
3. 주 체크아웃에 추적하지 않는 로그 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 `tidy-checkouts`가 루트를 당기지 않고 `주 체크아웃 미갱신`으로 보고했다. → 기각. 스킬이 정한 대로 동작했고 에이전트의 실수가 아니다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/main`을 붙인 것 모두 만료할 항목이 없었다(`--ref` 쪽은 아직 열린 `spec-review-transition-crossing`을 8회차로 세었다. 이 브랜치가 닫는 항목이다). 이 세션이 닫은 항목은 `spec-review-transition-crossing` 하나다.

## 다음

- 셀프 리뷰 Minor 4(반영 단계의 (d) 재실행)는 같은 꼴이 더 나오면 retro 후보로 올린다. 지금은 사건이 한 번뿐이라 대기열에 넣지 않았다.
