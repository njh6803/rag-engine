# meaning-change-grep-scope-hook: 결정이 뜻을 바꾸면 옛 말을 저장소 전체에서 찾게 한다 · 2026-11-25

next-session 지시문으로 연 새 세션의 기록이다(Sonnet 5.5). 시작 프롬프트는 "대기열 decision-word-residue를 티켓 .scratch/harness/issues/meaning-change-grep-scope-hook.md로 쓰고 한다"이고, 브랜치는 `chore/meaning-change-grep-scope-hook`, 작업은 워크트리 `meaning-change-grep-scope-hook`에서 했다. 요청 범위는 PR과 병합까지다. 이 일은 나란히 여는 다섯 티켓 가운데 넷째다.

## 준비

- 읽은 것: 대기열 항목 `decision-word-residue`(1~9회차), `docs/agents/issue-tracker.md`(harness 티켓 서식), `.claude/rules/tools.md`(계기 훅과 막는 훅의 가름), `.claude/rules/adr.md`, `CLAUDE.md` 작업 규약 4, `grilling` 스킬, 선례 티켓 `to-spec-grep-probe-output`(지침 한 곳만 고치고 훅을 더하지 않은 모양).
- 지시문이 시킨 순서: 이 세션은 묶음의 첫 세션이 아니라 `tidy-checkouts`를 돌지 않았다. `EnterWorktree`로 새 워크트리에 들어가 브랜치 이름을 `chore/meaning-change-grep-scope-hook`으로 바꿨고, `tools/sibling_overlap.py`는 번호·헌법 버전 겹침 없음(1.5.9)으로 끝났다.

## 층을 정한 것

계기를 훅으로 더할지 지침으로 둘지 판정했고 지침 두 곳으로 갔다. 이유는 티켓의 "어느 층으로 가는가"에 있다. 요약하면 이렇다.

- 훅이 사용자의 답이 뜻을 바꾸는 선택인지 가를 규칙이 없다. 낱말로 거르면 설계 인터뷰의 거의 모든 답에서 울릴 것으로 보인다(어림, 재지 않았다).
- 대기열 본문을 읽고 나누면(어림) 사용자의 답이 계기로 보이는 사건은 1·5·8회차 셋이고 나머지는 구현, 리뷰 반영, 명세 쓰기에서 났다. 매 세션 실리는 작업 규약 4에 닿아야 여섯이 덮인다.
- 작업 규약 4에는 범위가 적힌 적이 없었다. `.claude/rules/adr.md`에 ADR을 grep하라는 문장이 이미 있으나 `docs/adr/**`를 열 때만 실려 8·9회차 세션에는 실리지 않았다.

## 지은 것

- **`CLAUDE.md` 작업 규약 4.** grep을 저장소 전체의 살아 있는 문서에서 하게 했다. 명령은 `git grep --untracked -n -F '<옛 말>' -- . ':!docs/journal' ':!.scratch/retro-queue'`이고(손으로 쳐서 `docs/adr/`의 ADR 0007·0011과 `.scratch/plan-head.md`가 나오고 일지·대기열 경로의 줄이 없는 것을 봤다), 같은 뜻의 다른 말까지 찾기, 범위(`docs/adr/`, `docs/constitution/`, `docs/PRD.md`, `.scratch/plan-head.md`), 그 문서들을 고치는 일은 승인 뒤, ADR 본문은 포인터만, 생성 파일 `.scratch/plan.md`는 입력을 고쳐 도구를 다시 돌리기를 적었다.
- **`.claude/skills/grilling/SKILL.md`.** 사용자의 답이 번호나 이름의 뜻을 바꾸면 합의 요약 전에 작업 규약 4의 명령과 범위로 옛 말을 찾아 "고칠 곳"으로 올리고, 승인받은 목록을 설계 일지에 옮기게 하는 문단을 더했다. 첫머리 `프로젝트 사본` 주석에 출처를 덧붙였다(센티널 낱말은 그대로).
- **티켓과 대기열.** 티켓 `.scratch/harness/issues/meaning-change-grep-scope-hook.md`를 썼고, 대기열 항목 `decision-word-residue`를 닫았다(닫힘 줄에 훅을 더하지 않은 이유와 안 닿은 자리를 적었다).

## 겪은 것

- 티켓을 쓸 때 상태를 `done`, 체크박스를 모두 `[x]`로 적어 고치기 전에 완료로 보이게 했다. 쓰자마자 `in-progress`와 `[ ]`로 되돌렸고, PR 전에 다시 `done`으로 바꾼다.
- `git grep`은 추적하지 않는 새 파일을 훑지 않아 이 PR이 새로 만든 티켓을 놓친다. `--untracked`를 더해 같은 명령이 새 파일도 훑는 것을 손으로 봤다(이 티켓 파일이 나왔다).

## 셀프 리뷰(`/code-review`, base `61847dd`, 수정 3·미추적 2·커밋 0)

표준 축은 Major 4, Minor 3을, 명세 축은 (a) 3, (c) 4를 냈다. 겹치는 지적이 많았다.

**고친 것**
- Major. 작업 규약 4가 `docs/adr/`·`docs/constitution/`·`docs/PRD.md`를 범위에 넣고 잔존 0까지 가라면서 승인 갈래가 `grilling`에만 있었다. 규약 4에 그 문서들을 고치는 일은 승인 뒤(지도표, 작업 규약 5)라는 문장과 ADR 본문은 포인터만이라는 문장을 더했다.
- Major. `grilling`의 옛 ADR의 문장을 고치거나 `(바뀜: ADR NNNN)` 이력을 다는 일이라는 서술이 `.claude/rules/adr.md`(본문 글자는 고치지 않고 포인터만, 이력은 `## 이력`)와 어긋났다. 문장을 ADR·헌법·PRD를 고치는 일은 승인 뒤로 줄이고 고치는 방식은 규약 4와 adr.md를 가리키게 했다.
- Major. 티켓 이유 3의 범위가 지침에 적힌 적이 없었다는 문장은 닫힌 주장이었고 adr.md에 반례가 있었다. 작업 규약 4에는 범위가 적히지 않았다로 좁히고, adr.md는 열 때만 실려 이 사건들에는 실리지 않았다는 것을 적었다.
- Major. 사건 가름이 대기열 본문과 맞지 않았다(대기열 6회차는 앞의 다섯을 결정이라고 썼다. 3회차는 대상 말이 아니라 폴더 문제였다). 가름을 폴더(2·3·5·6), 같은 뜻의 말을 한 가지로만 찾음(1·4·7), ADR 포인터(8·9)로 고쳐 어림이라 적고, 닫힘 줄의 단정에 어림 표시를 달았다. 따옴표 안에 든 풀어 쓴 문구와 규약 4의 문장 인용을 평문으로 바꿨다.
- Minor. 명령이 미추적 파일을 못 찾는 것(`--untracked`), 생성 파일 `.scratch/plan.md`를 손으로 고치지 않는 것, 같은 뜻의 다른 말(1·4·7회차), 명세 쓰기(9회차)를 규약 4와 `grilling`에 반영했다.
- Minor. 예시 "첫 티켓"이 규약 4와 `grilling` 자신에 걸려 잔존 0이 안 서는 것을 막으려 두 곳에서 예시를 다른 말로 바꾸거나 뺐다.
- Minor. 티켓 이유 1의 "훅은 대화를 읽지 못한다"는 틀렸다(`hook_scratch_probe_reread`가 `transcript_path`를 읽는다). "가를 규칙이 없다"로 고쳤다. 이유 4의 사용 보고서 서술은 지시문이 전한 것이고 이 세션이 다시 돌리지 않았다고 적었다.
- 중복(Duplicated Code). `grilling`이 명령과 경로 목록을 따로 적던 것을 작업 규약 4를 가리키게 줄였다.

**남긴 것과 이유**
- 표준 축 Minor: 두 보고가 지적한 "고칠 곳"의 모양을 별도 서식으로 정하지 않았다. `grilling` 문단에 파일과 줄, 고치는 방식이라고만 적었다. 서식을 더하면 지침 문장이 늘고, 이 지침 뒤에도 같은 사건이 나면 그때 정한다.
- 명세 축 (c)3이 든 계기 알림은 세션과 이유마다 처음 한 번만 낸다는 `tools.md`의 문장은 래퍼가 훅 파일이 없을 때 내는 알림에 관한 것이다. 훅이 낸 문맥 자체는 호출마다 간다. 또 `hook_choice_facts`는 `.claude/rules/tools.md`가 이름을 들지만 이 저장소 `tools/`에 파일이 없다(`ls tools`로 보았고, 같은 이름이 `tools/check_instructions.py`의 독스트링에만 나온다). 이 두 사실은 티켓의 층 판정을 바꾸지 않아 티켓 이유 1은 수십 번 쌓인다는 문장을 어림으로 낮추는 데서 그쳤다.
- 일지와 대기열 항목을 명령에서 뺀다는 문장에서, 열린 대기열 항목과 일지의 "다음" 절은 읽는 자료라는 반례가 있다는 지적(Minor 6)은 "명령에서 뺀다"로 말을 좁혀 두었다. 잔존으로 세지 않는 것은 닫은 티켓과 ADR 이력까지다.

**PR 직전 리뷰에 밀 주장(이 반영으로 새로 쓴 문장)**
- `CLAUDE.md` 규약 4: "`docs/adr/`, `docs/constitution/`, `docs/PRD.md`, `.scratch/plan-head.md`는 어느 결정에서나 범위에 든다." 이 넷이 모든 결정의 범위라는 닫힌 주장이다.
- `CLAUDE.md` 규약 4: 명령 `git grep --untracked -n -F '<옛 말>' -- . ':!docs/journal' ':!.scratch/retro-queue'`가 "추적하지 않는 새 파일도 훑는다". 이 저장소에서 손으로 쳐 이 PR의 새 티켓이 나오는 것을 봤다.
- 티켓 이유 3: `.claude/rules/adr.md`는 `docs/adr/**`를 열 때만 실린다(`paths`). 그 파일의 머리 `paths`를 읽은 것이고 8·9회차 세션이 그 폴더를 열지 않았는지는 보지 않았다.

**다시 돌린 것.** `uv run python tools/check_instructions.py`와 `uv run python tools/queue_open_rows.py --search decision-word-residue`가 반영 뒤에 통과했다(두 명령 모두 오류 없이 끝났고 후자는 닫힌 항목 1개를 냈다). 나머지 검증 명령은 지침 파일 둘과 마크다운만 바꾼 이 PR에서 커밋이 부르는 pre-commit의 검사 러너가 돈다.

## 검증

- 첫 커밋 시도(커밋 `2e24734` 전)의 pre-commit 검사 러너: pytest가 2598.1초 돌고 17건이 실패했다. 실패는 응답 시간 초과(`httpx.ReadTimeout`)와 시험 저장소의 `git fetch`가 낸 `bad pack header` 오류였고, 이 PR이 바꾼 문서를 읽는 시험은 없었다. 그때 이 PC에는 검사 프로세스가 14개 돌고 있었고(손으로 `Get-CimInstance`로 셌다) 가상 메모리 여유는 26.2GB였다. 같은 부하의 선례는 대기열 항목 `concurrent-checks-exhaust-memory`다(그 항목의 회차를 이 사건으로 세지는 않았다. 이 세션은 메모리 부족 오류 자체를 보지 못했다).
- 사용자가 이번 커밋만 pytest를 건너뛰기로 골라 `SKIP=pytest`로 커밋했다. 나머지 검사(`check-ticket`, `check-notes`, `lint-imports`, `zizmor`, `check-instructions`, `check-type-escapes`, `run-hooks`, `pyright`, `pyright-linux`)는 통과했다. 첫 시도에서 pytest 밖의 검사도 모두 통과했다.
- 커밋 메시지 검사가 제목 86자를 72자 한도로 막아 제목을 줄였다.
- PR을 열면 CI의 `python` 잡이 같은 pytest를 다시 돈다.

## PR 직전 리뷰(`coderabbit-review`, CodeRabbit CLI 0.7.5, 커밋 `2e24734`과 커밋하지 않은 일지 수정)

`review_completed`로 끝났고(좌석은 `Seat: not assigned`) CLI 지적 3건을 서브에이전트가 트리아지해 유효 1(Minor), 오탐 1, 중복 1로 가렸다. 서브에이전트가 밀 주장 셋을 직접 쟀고 모두 참이었다(규약 4의 네 경로가 있고 명령이 일지와 대기열 경로를 빼는 것, 이 워크트리에 추적하지 않는 새 파일이 없어 `--untracked`는 재현하지 못한 것, adr.md의 `paths`).

**고친 것**
- Minor. 규약 4의 명령이 `.scratch/retro-queue` 전체와 일지 전체를 빼는데, 열린 대기열 항목과 최신 일지의 다음 절은 앞으로의 지시를 담는다. 규약 4에 그 둘은 옛 말이 남았는지 따로 훑는다는 문장을 더했다.

**남긴 것과 이유**
- 오탐. 티켓 29행의 `grilling` 문단이 합의 요약 뒤에 실행될 수 있다는 지적(CLI는 Major). 문단이 합의 요약을 올리기 전에 찾게 하고 "고칠 곳"을 요약에 올려 승인받게 하므로 순서가 정해져 있다.

**다시 돌린 것.** 이 수정은 `CLAUDE.md`와 일지만 바꾸므로 커밋의 pre-commit이 pytest를 문서를 읽는 시험 여섯으로 좁혀 돈다(`tools/run_checks.py`의 `docs_only`). 결과는 커밋 뒤 PR 본문에 적는다.

## 회고

후보 둘을 냈고 판정은 승인 0, 기각 2, 넘김 0이다.

- **티켓을 쓰며 상태를 `done`, 체크박스를 `[x]`로 미리 적은 것.** 기각. 쓰자마자 내가 알아채고 되돌렸고 PR 전에 상태 판정이 있는 `tools/check_ticket.py`가 `done`인데 체크가 비면 잡는지는 이 세션에서 보지 않았다. 같은 실수가 처음이라 대기열에 잇지 않는다. 다음에 같은 모양이 나오면 이 줄이 첫 회차다.
- **셀프 리뷰 두 축이 같은 근거(대기열 본문, `adr.md`)를 대 보고 잡은 일.** 기각. 리뷰가 제 몫을 한 사건이라 회차로 세지 않는다.

## 다음

- 이 PR이 병합되면 `decision-word-residue`는 닫힌 상태로 남는다. 같은 사건(결정이 번호나 이름의 뜻을 바꿨는데 옛 말이 ADR·헌법·계획표 머리글에 남은 일)이 또 나면 10회차로 세고 훅 후보로 올린다. 그때 먼저 볼 것은 이 지침이 실린 세션에서도 어겨졌는지다.
- 나란히 여는 나머지 티켓(`claim-evidence-rule-in-issue-tracker`, `review-report-to-journal-on-receipt`, `commit-title-check-before-slow-checks`, `session-asks-extractor`)와 이 PR이 같은 파일을 고치는지는 `tools/sibling_overlap.py`가 시작 때 함께 고친 파일 없음으로 냈고(그때 다른 워크트리는 아직 변경이 없었다), 그 뒤는 보지 않았다.
