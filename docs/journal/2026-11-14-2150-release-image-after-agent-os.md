# harness release-image-after-agent-os 일지 · 2026-11-14

harness 티켓 `.scratch/harness/issues/release-image-after-agent-os.md`를 한 기록이다. release-image 기능 계획에 agent-os의 첫 판 뒤로 설계 인터뷰를 미룬다는 대기를 적었다. 지시문 없이 사용자가 "설계 인터뷰 할 거 있어?"라고 물어 연 세션(Opus 5.5)이고, 작업은 워크트리 `release-image-after-agent-os`에서 했다. 브랜치는 처음에 면제 `docs/release-image-after-agent-os`였고, 셀프 리뷰가 `tools/plan_table.py` 독스트링의 잔존을 짚어 면제 밖의 파일을 고치게 되어 `chore/release-image-after-agent-os`로 바꾸고 티켓을 썼다. 사용자의 물음과 교정, 한 것, 손으로 본 것, 코드 리뷰, 회고, 다음을 차례로 둔다.

## 사용자의 물음과 교정

주 체크아웃(`dev`, 97f9914)이 `origin/dev`(a495e80)보다 다섯 커밋 뒤처져 있어 `git show origin/dev:<경로>`로 읽었다. 전체 계획의 프론티어는 `release-image`와 `search-eval`이고, search-eval은 설계 줄과 명세가 있으며 티켓 01~05가 done이다. release-image는 명세도 설계 줄도 없고, 그 인터뷰를 맡은 브랜치·워크트리·열린 PR도 없었다. 그래서 release-image의 설계 인터뷰를 지금 열 수 있다고 답했다.

> 사용자: release-image는 agent-os release-image 가 끝나고 해야하는거 아니야?

agent-os(`C:\project\agent`)를 봤다. 그 저장소의 일지 `docs/journal/2026-11-11-1532-release-image-design-round3.md`에 사용자가 2026-11-11에 정한 순서가 있다("사용자가 정했다: agent-os에서 먼저 짓고 돌려 본 뒤 옮긴다" 절). 그 저장소의 release-image 기능 계획과 명세("rag-engine에 줄 지시문(넘겨받은 것)" 절)는 첫 판 내기를 지켜본 세션이 이 저장소의 세션에 줄 지시문을 사용자에게 낸다고 적고, 지시문은 agent-os ADR 0043과 0056을 입력으로 받는 짧은 설계 인터뷰를 열게 한다. 같은 일지의 "인계한 세션에서 사용자가 정했다" 절은 이 저장소에 그 규약 ADR을 따르고 다른 점만 적는 얇은 ADR 한 장을 두라고 한다. 이 순서가 rag-engine에는 한 줄도 없었고, `tools/plan_table.py`는 다른 저장소의 기능을 Blocked by 줄에 받지 않아 프론티어가 release-image를 시작할 수 있는 기능으로 보였다. 앞 답이 틀렸다고 사용자에게 알렸고, 지금 이 저장소에서 열 설계 인터뷰는 없다고 고쳐 답했다.

교정 루프(`CLAUDE.md`)대로 자동 검사로 잡을 수 있는지 봤다. `tools/plan_table.py`가 기능 계획의 대기 줄을 읽어 그 기능을 프론티어에서 빼는 검사가 후보다. 첫 사건이고 손상이 없어 지금은 더하지 않는다고 사용자에게 말했고, 빠진 사실을 채우는 고침만 이번에 한다. 사용자가 "여기서 적기"를 골랐다.

## 한 것

- `.scratch/release-image/plan.md` 본문의 첫 문단에 대기를 적었다. 설계 인터뷰는 agent-os가 판 내기 워크플로를 짓고 돌려 본 뒤 오는 지시문으로 열고, 그 전에는 프론티어에 올라 있어도 열지 않는다. 근거(그 저장소의 일지 세 절과 명세 한 절), 지시문이 싣는 것과 얇은 ADR, 넘긴 것 문단도 인터뷰의 입력이라는 것, 그사이 이 기능을 받은 세션이 할 일, 순서를 다시 바꾸는 것은 사용자의 몫이라는 것, Blocked by 줄에 적지 못하는 까닭, 문단을 걷는 때를 함께 적었다.
- `.scratch/plan-head.md`의 순서 절에 같은 대기를 한 문단으로 적고 기능 계획 문단을 가리켰다. 다음 세션이 먼저 읽는 전체 계획에서 보이게 하려는 것이다.
- `tools/plan_table.py` 독스트링의 프론티어 항목에서 "rag-engine 은 다른 저장소의 기능에 막히지 않는다"를 "Blocked by 는 이 저장소의 기능만 가리킨다"로 고치고, 다른 저장소의 일을 기다리는 기능은 기능 계획 본문에 그 대기를 적는다는 문장을 더했다. 동작과 시험은 바꾸지 않았다. 앞 문장은 기존 시험 `test_plan_table.py`의 `rag-engine:core` 사례(깨진 입력으로 종료 2)가 받친다.
- 티켓 `.scratch/harness/issues/release-image-after-agent-os.md`를 썼다.
- `uv run python tools/plan_table.py`로 `.scratch/plan.md`를 다시 만들었다.

## 손으로 본 것

- 고치기 전: `uv run pytest tests/test_plan_status.py -q` 13 passed, `uv run python tools/check_ticket.py` 종료 코드 0(그때는 면제 모양만 바뀌었다), `uv run python tools/check_instructions.py` 출력 없이 끝났다.
- `gh pr view 569 -R njh6803/agent-os`: `OPEN`, 머리 `docs/release-image-tickets`, 제목 "docs: release-image를 티켓 열한 장으로 나눈다 (release-image)". 그 브랜치의 `.scratch/release-image/issues/`에는 01~11의 티켓 열한 개가 있다. 그 저장소의 dev에는 release-image의 `spec.md`와 ADR 0056이 있다. 이 상태는 날이 지나면 낡아 기능 계획에 적지 않고 여기에만 둔다.
- `uv run python tools/sibling_overlap.py`: 종료 코드 0, 새 번호 없음, 번호 겹침 없음. 함께 고친 파일로 워크트리 `09-public-docs-documents`의 `.scratch/plan-head.md`와 `.scratch/plan.md`가 나왔다. 그 워크트리는 `plan-head.md`의 목표 배치 블록(`evals/public-docs/` 줄)을 고쳐 이 변경의 순서 절과 hunk가 다르고, `plan.md`는 생성 파일이라 나중에 병합하는 쪽이 도구를 다시 돌려 푼다.
- 반영 뒤: `uv run pytest tests/tools/test_plan_table.py tests/test_plan_status.py -q` 48 passed, `uv run ruff check tools/plan_table.py` 통과, `uv run ruff format --check tools/plan_table.py` 통과, `uv run python tools/check_ticket.py` 출력 없이 끝났다. `git grep -n -I -E "다른 저장소의 기능에 막히지|이 기능에 닿는 넷|병합을 기다린다" -- tools .scratch docs/agents .claude/skills`는 0건이다(미추적 티켓은 git grep에 들지 않고, 그 티켓은 옛 문장을 고칠 대상으로 인용한다).

## 코드 리뷰

`/code-review`(base `a495e80`, 수정 셋, 미추적 하나(이 일지. 두 브리프에 "미추적 파일 없음"으로 잘못 적었고 표준 축이 짚었다), 커밋 없음). 리뷰 때는 면제 브랜치였고 `tools/plan_table.py`와 티켓은 반영에서 생겼다.

- 표준 축(sonnet·high): 하드 위반 없음. 판단 일곱이다. (1) 대기가 산문뿐이라 `next-session` 결정표가 search-eval 뒤 프론티어의 release-image로 가는 갈래가 남고, 기다리는 기능만 남았을 때 할 일의 줄이 없으며, `grill-with-docs` 설명과 `hook_grill_design_check`도 대기를 보지 않는다. (2) 문단을 걷는 사람과 때가 없고, 사용자가 직접 청할 때의 처리도 없다. (3) 원칙 III: "두 저장소의 판 번호 관계"의 일지 원문은 클라이언트가 이 서버의 판을 고정하는 관계이고, 그 저장소의 진행 상황이 기능 계획 본문에 실렸다. (4) 공개 시연(2027-01 초)이 release-image에 걸리는데 대기가 일정에 주는 영향이 없다. (5) "첫 판 내기를 지켜본 세션"의 출처는 그 저장소의 기능 계획이 아니라 명세 "rag-engine에 줄 지시문"이다. (6) 일지의 다섯을 넷으로 줄인 까닭이 없다. (7) 2026-11-14 상태 문장이 날짜 스냅샷이라 낡는다. 냄새 둘: 같은 대기를 두 곳에 적은 의도된 중복(포인터 있음), 약 1,000자의 긴 문단. 잰 주장: 절 제목 인용과 ADR 0016 Consequences "원칙 III" 자리가 원문과 같고, 임시 사본에서 `agent-os:release-image`, `rag-engine:x`, `core, agent-os:...`를 Blocked by에 넣으니 셋 다 종료 2였다.
- 명세 축: 요구 1·2는 들어갔고 3은 일부다. 범위 넘침은 없다. (c1) 본문에 `**설계:**`와 `**Blocked by:**`가 글자 그대로 들어가 줄 머리를 고정하지 않은 grep이 설계 줄로 읽는다. (c2) "넷만 다루고"는 출처에 없는 제한이고 같은 파일의 넘긴 것 문단(판을 내는 사건, 느린 CI 잡, SBOM)을 인터뷰에서 뺄 수 있다. (c3) 판 번호 관계 항목이 원칙 III에 걸릴 수 있다. (a4) search-eval 뒤에 next-session이 낼 작업이 없다. (a5) 대기가 풀리는 쪽의 상태와 문단을 고칠 사람이 없고, 사용자가 먼저 청하는 경우를 문단이 무조건 막는다. (a6) 잔존: `tools/plan_table.py` 30행 "rag-engine 은 다른 저장소의 기능에 막히지 않는다". 잰 주장: 인용 셋이 글자 그대로이고, 임시 루트에서 다른 저장소 꼴 셋이 종료 2, `core`만은 0이었다.
- 고친 것:
  - 명세 c1: 본문의 `**설계:**`·`**Blocked by:**`를 "설계 줄"·"Blocked by 줄"로 풀었다.
  - 명세 c2·c3, 표준 3·6: 넷의 나열을 빼고 출처(그 명세의 절과 일지의 "사용자가 물었다" 절)를 가리켰다. 넘긴 것 문단도 인터뷰의 입력이라고 적었다. 클라이언트가 서버의 판을 고정하는 관계는 이제 문단에 없다.
  - 표준 5: 지시문을 내는 세션의 출처를 그 저장소의 명세 "rag-engine에 줄 지시문(넘겨받은 것)" 절로 바꿨다(504행에서 확인했다).
  - 표준 3의 둘째·7: 2026-11-14 상태 문장을 기능 계획에서 빼고 이 일지의 손으로 본 것에만 남겼다.
  - 표준 2, 명세 a5, 명세 a4의 일부: 그사이 이 기능을 받은 세션은 인터뷰를 열지 않고 사용자에게 알린다, 순서를 다시 바꾸는 것은 사용자가 정한다, 인터뷰를 마친 세션이 설계 줄을 적으며 두 문단을 걷는다를 더했다. plan-head 문단도 그 셋을 가리키게 고쳤다.
  - 명세 a6: `tools/plan_table.py` 독스트링을 위 "한 것"대로 고쳤다. `tools/`는 면제 모양이 아니라 티켓을 쓰고 브랜치를 `chore/`로 바꿨다.
- 남긴 것과 이유:
  - 표준 1, 명세 a4의 나머지: `next-session` 결정표에 기다리는 기능만 남았을 때의 줄을 더하거나 `grill-with-docs`·`hook_grill_design_check`가 대기를 보게 하는 것은 새 지침·검사라 교정 루프의 문턱(같은 실수의 다섯 번째이거나 손상) 전이다. 회고 후보로 넘긴다. 그때까지는 `next-session`이 다른 기능의 프론티어를 읽을 것의 `plan.md`로 가리키고(`SKILL.md` 35행), 그 기능 계획의 첫 문단이 받은 세션의 할 일을 적는다.
  - 표준 4: 이정표의 원천은 `docs/PRD.md`이고 사용자 승인으로 바꾸는 자리라 문서를 고치지 않고 사용자에게 알린다.
  - 냄새 둘: 두 곳의 중복은 전체 계획에서 보이게 하려는 의도이고 포인터가 있다. 긴 문단은 나열과 상태 문장을 빼며 줄었다.
- 반영으로 새로 쓴 사실 문장(PR 직전 리뷰에 밀 주장):
  - "그 저장소의 release-image에서 첫 판 내기를 지켜본 세션이 이 저장소의 세션에 줄 지시문을 사용자에게 내고(그 저장소의 release-image 명세 "rag-engine에 줄 지시문(넘겨받은 것)" 절)"
  - "지시문은 이 저장소가 따로 정할 것(그 명세의 같은 절과 같은 일지의 "사용자가 물었다" 절)을 싣고"
  - "순서를 다시 바꾸는 것은 사용자가 정한다(같은 일지의 "사용자가 물었다" 절)."
  - "Blocked by 는 이 저장소의 기능만 가리킨다."
  - "다른 저장소의 일을 기다리는 기능은 기능 계획 본문에 그 대기를 적는다(release-image)."
- 다시 돌린 명령: 위 손으로 본 것의 "반영 뒤" 줄이다. 손으로 치는 다섯 가운데 나머지(전체 테스트, 타입체크, import 경계)는 커밋의 pre-commit으로 갈음한다.

## 회고

후보 일곱, 승인 2, 기각 5, 넘김 0. `uv run python tools/queue_open_rows.py`(작업 폴더와, `git fetch origin` 뒤 `--ref origin/dev`)의 만료할 항목은 둘 다 없었다.

1. **승인. 다른 저장소의 일을 기다리는 기능이 프론티어에 올라 설계 인터뷰를 열 수 있다고 잘못 답했다.** 사건: 사용자가 바로잡은 첫 답(위 "사용자의 물음과 교정"). 층: 판정은 `tools/plan_table.py`가 할 수 있다. 되돌림: PR 하나. 빠진 사실을 적는 고침은 이 티켓이 한 일 자체라 회고 반영 줄을 따로 더하지 않았다. 대기를 프론티어 계산에 반영하는 것은 더하는 것이라 새 항목 cross-repo-wait-on-frontier(1회차)로 대기열에 뒀다. 같은 뿌리(외부 조건을 기다리는 일이 전체 계획에 보이지 않음)를 하네스 기능 쪽에서 다루는 harness-feature-off-plan과 대상 파일이 같아, 두 항목이 서로 가리키게 했다. `next-session` 결정표와 `grill-with-docs`·`hook_grill_design_check`가 대기를 보지 못하는 갈래(셀프 리뷰 표준 1, 명세 a4)도 이 항목이 프론티어에서 빼면 함께 닫혀 따로 쓰지 않았다.
2. **승인(회차). 첫 초안이 기능 계획 본문에 agent-os의 진행 상황과 그 저장소가 이 서버의 판을 고정하는 관계를 적었다.** 셀프 리뷰 두 축이 원칙 III(항상 실리는 지침)로 짚었다. 구현 때 실리는 지침을 어겨 리뷰가 잡은 사건이라 client-name-in-spec-body에 회차를 더했다(3회차). agent-os를 판 내기 규약의 원천으로 든 것은 ADR 0016의 쓰임이라 남겼다.
3. **기각. agent-os 세션이 2026-11-11에 rag-engine의 순서를 정하고 그 사실을 rag-engine에 적지 않았다.** 그 저장소는 일을 끝낸 세션이 지시문을 내는 길을 골랐고(그 저장소의 release-image 기능 계획), 고칠 층이 이 저장소에 없다.
4. **기각. 셀프 리뷰가 잡은 첫 초안의 결함들**(본문에 글자 그대로 든 필드 표지, 출처에 없는 "넷만", 출처 귀속, 낡을 상태 문장, 문단을 걷는 때 없음, `tools/plan_table.py` 독스트링의 잔존). 두 브리프의 기준(주장 검증의 인용·잔존, 갈래 밟기)으로 리뷰가 잡은 것이라 회차 셈에서 뺀다. 검사로 옮길 꼴로는 본문의 필드 표지가 있지만, 그것을 줄 머리 없이 grep하는 읽는 쪽이 저장소에 없고 잘못 읽힌 사건도 없다.
5. **기각. 훅과 앱 가드가 막거나 알린 명령.** 다른 체크아웃으로 가는 `cd`(`hook_bash_cd_outside`), `.env`에 닿는 Grep glob 두 번(`hook_env_read`), 변수 꼴과 `-C` 꼴의 git 세 번(앱 워크트리 가드), `origin/dev:.scratch/...`의 MSYS 경로 변환(계기), 파이프 뒤의 게이트(`hook_bash_gate_pipe` 계기)다. 모두 그 자리에서 막거나 알렸다.
6. **기각. 다른 저장소에 Glob을 쳐 ripgrep이 20초에 끊겼다.** 한 번이고, 바로 `git ls-tree`와 Read로 돌았다.
7. **기각. 셀프 리뷰 뒤 브랜치를 `docs/`에서 `chore/`로 바꿨다.** 면제 밖의 파일을 고치게 될 때의 길을 `docs/agents/issue-tracker.md`와 커밋 검사가 정해 두었고, 비용은 이름 바꾸기와 제목 바꾸기 둘이었다.

## 다음

- 이 PR이 병합된 뒤 새로 열 세션은 없다. 프론티어는 그대로 `release-image`와 `search-eval`이고, release-image는 기능 계획 첫 문단대로 agent-os의 지시문을 기다린다. search-eval의 `ready-for-agent` 티켓은 06(PR 44)과 07·09·12처럼 각자 세션이 맡은 것이 있고, 그 세션들이 next-session으로 다음을 연다.
- 공개 시연(2027-01 초, `docs/PRD.md`)은 release-image에 걸려 있어, 이번 대기로 그 날짜가 agent-os release-image의 첫 판에도 걸린다. 그 저장소의 release-image는 티켓 열한 장이 병합 전이다. 일정을 다시 볼지는 사용자가 정한다.
- 워크트리 `09-public-docs-documents`가 같은 `.scratch/plan-head.md`의 목표 배치 블록을 고친다. 나중에 병합하는 쪽은 `.scratch/plan.md`를 `uv run python tools/plan_table.py`로 다시 만든다.
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)다. 병합 뒤 `tidy-checkouts`가 당긴다.
