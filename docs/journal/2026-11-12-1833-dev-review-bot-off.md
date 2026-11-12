# dev-review-bot-off: 리뷰 봇이 dev→main 출시 PR을 건너뛴다 · 2026-11-12

`next-session` 지시문으로 연 새 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/dev-branch/issues/02-dev-review-bot-off.md`이고, 브랜치는 `feature/02-dev-review-bot-off`, 작업은 워크트리 `02-dev-review-bot-off`에서 했다. 나란히 여는 3 중 2이고 01(`dev-base-tools`)과 03(`dev-base-skills-docs`)이 다른 세션에서 도는 중이다. 준비, 확인한 것과 정한 것, 셀프 리뷰, PR 직전 리뷰, 검증, 회고, 다음을 차례로 둔다.

## 준비

- 세션 제목을 브랜치 이름으로 바꾸고 `EnterWorktree`로 들어간 뒤 앱이 만든 브랜치(`worktree-02-dev-review-bot-off`)를 `feature/02-dev-review-bot-off`로 바꿨다. 워크트리는 `origin/main`(e95006c)에서 섰고 `uv sync`를 쳤다.
- 이 세션은 묶음의 첫 세션이 아니라 `tidy-checkouts`를 돌지 않았다.
- agent-os는 읽기만 했다(`git -C C:/project/agent show origin/dev:<경로>`). 읽은 것은 그 저장소의 `.scratch/harness/issues/dev-review-bot-off.md`와 `.github/workflows/claude-code-review.yml`이다. 작업 폴더를 옮기는 명령은 앱의 훅이 거부해서 `-C`로 경로를 줬다.

## 확인한 것과 정한 것

- **조건식.** agent-os `origin/dev`의 잡 `if` 식과 글자가 같은 식을 더했다. 여덟 경우(출시 PR, hotfix, feature·chore·docs, 포크의 dev, 되돌려 합치기, 기본 브랜치 전환 전 feature→main 등)를 일회용 스크립트(세션 스크래치패드의 `eval_if.py`, 커밋하지 않았다)로 돌렸고 모두 기대와 같았다. 파이썬 식으로 옮긴 것이라 GitHub의 식 평가기로 잰 값은 아니다.
- **되돌려 합치기 PR(머리 `main`, base `dev`)은 건너뛰지 않는다.** 충돌을 푼 줄은 새 코드인데 갈래를 더하면 가드 없이 지나간다.
- **기본 브랜치가 dev인 동안의 갈래.** 액션 v1.0.244의 `src/github/token.ts`를 커밋 주소에서 내려받아 읽었다. 앱 토큰 교환이 `workflow_not_found_on_default_branch` 코드나 401의 `workflow validation failed`로 실패하면 경고를 찍고 건너뛴다. 비교는 서버가 한다는 것은 추론이다. 가드는 풀지 않고 알려진 빨강으로 두기로 했다(코드를 실은 hotfix PR이 리뷰 없이 초록이 되는 착시를 막으려고). 오류 메시지에만 그 경우일 수 있다는 문구를 더했다. 근거와 03에 넘길 것은 티켓 끝에 있다.
- 사용자에게 묻지 않고 정했다. 이 티켓이 "정한다"고 맡겼고 가드를 푸는 쪽이 아니라 두는 쪽이라 가드레일을 느슨하게 하지 않는다.

## 셀프 리뷰

범위는 base e95006c, 파일 둘, 커밋 0개(작업 트리 변경), 미추적 0개. 표준 축(sonnet·high)과 명세 축(세션의 모델)을 병렬로 돌렸다.

- 표준 축 Major 1(워크플로가 ADR 0016에 없는 내용을 ADR 이름으로 댄다): → 고쳤다. 주석과 오류 메시지의 출처를 티켓 02로 바꾸고 "ADR 본문에는 티켓 03이 옮긴다"를 적었다.
- 표준 축 Major 2("티켓 PR마다 이미 리뷰를 받았다"는 보편 주장이 이 PR 같은 반례에 걸린다): → 고쳤다. "리뷰를 거치게 돼 있다"로 낮추고 이 파일을 바꾼 PR은 PR 직전 리뷰와 셀프 리뷰가 맡는다고 적었다.
- 표준 축 Minor(주석 안에서 hotfix가 "그대로 돈다"와 "건너뛰어질 수 있다"가 부딪친다): → 고쳤다. 앞의 것을 "이 조건으로는 건너뛰지 않는다(잡이 돈다)"로 가렸다.
- 표준 축 Minor(티켓의 근거 종류가 섞였고, 액션 소스 서술이 발췌까지만 확인됐다): → 고쳤다. 표의 근거를 코드 읽기, 손으로 돌림, 어림으로 가르고, `token.ts` 원문을 직접 읽어 줄 번호와 조건을 대 본 뒤 서버 비교는 추론이라고 적었다.
- 명세 축(닫힌 주장 "달라진 때뿐"이 한쪽 방향만 말한다): → 고쳤다. main의 핫픽스가 이 파일을 먼저 바꾼 경우를 더했다.
- 명세 축(오류 메시지 고침은 요구하지 않은 변경): → 티켓이 이미 밝혔다. 동작은 그대로이고 같은 파일 안이라 "다른 워크플로·도구를 건드리지 않는다"를 어기지 않는다.
- 명세 축(03 티켓에 02가 넘긴 세 줄을 수용 기준으로 더하자): → 보류. 03을 다른 세션이 나란히 고치는 중이라 이 PR이 그 파일을 건드리면 충돌한다. 받는 쪽은 03 티켓 11행과 02 티켓의 "03에 넘긴다" 절이고, 아래 "다음"과 PR 본문 "남긴 위험"에도 적었다. 03 세션이 이 PR을 읽으면 받게 된다.
- 표준 축 냄새(같은 설명이 주석, 오류 메시지, 티켓에 모양이 같게 있다, Duplicated Code): → 보류. 03 뒤에는 운영 문서가 원천이 되고, 이 PR에서는 운영 문서를 고칠 수 없다(가드).
- 표준 축 Nit(가드 오류 메시지가 한 줄에 세 문장이다): → 보류. 로그에서 읽을 수 있고 문장을 가르는 것은 동작을 바꾸지 않는다.

반영으로 새로 쓴 사실 문장(원문, 다음 리뷰가 겨냥할 밀 주장):

1. 워크플로 머리 주석: "기본 브랜치가 dev인 동안 dev와 main의 이 파일이 다르면(dev에서 바뀌고 아직 출시되지 않았거나, main의 핫픽스가 바꾸고 아직 되돌려 합치지 않았으면) base가 main인 hotfix PR이 액션의 워크플로 검증에 걸려 건너뛰어질 수 있다"
2. 티켓: "`pull_request` 이벤트는 병합 결과 커밋의 워크플로를 쓴다고 알고 있어(GitHub 동작에 대한 기억, 이 저장소에서 보지 않았다)"
3. 티켓: "액션 `anthropics/claude-code-action@58985842…`(v1.0.244)의 `src/github/token.ts`를 그 커밋 주소(`raw.githubusercontent.com`)에서 내려받아 읽었다(원문 5111바이트, 코드 읽기)"

## PR 직전 리뷰

`coderabbit review --agent --include-untracked --base origin/main`(CLI 0.7.5, `Seat: not assigned`)이 `review_completed`로 끝까지 돌았다. 지적 0건. 서브에이전트가 워크플로 diff를 읽어, `if` 식에 외부 입력이 보간되는 곳이 없고 포크의 `dev`는 조건에 걸리지 않으며 트리거가 `pull_request`라 포크 PR에 비밀이 주어지지 않는다고 보고했다(CLI의 출력이 아니라 읽은 것).

## 검증

- `uv run ruff check . && uv run ruff format --check .` 초록. `uv run zizmor .github/workflows/claude-code-review.yml` 지적 없음(손으로 돌렸다).
- `uv run python tools/run_checks.py`(종료 코드 0)와 커밋의 pre-commit(480초)에서 `test-db`, `zizmor`, `check-ticket`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright` 둘, `run-hooks`, `pytest`가 통과했다.
- 첫 커밋 시도는 제목 타입 `ci`가 허용 목록에 없어 `commit-msg` 훅이 막았다. 검사가 480초 돈 뒤였다. `chore`로 고쳐 다시 커밋했다(아래 회고).
- 실제 dev→main PR에서 건너뛰는 모습은 dev가 서고 첫 출시 PR이 열릴 때 처음 본다.

## 회고

후보 여섯, 승인 둘, 기각 넷, 넘김 없음.

- **commit-msg-after-slow-checks**(도구 경제, 자동 검사): 승인. 사건은 위 검증의 첫 커밋 시도(480초를 쓴 뒤 막힘). 층은 훅이다(`commit-msg` 단계는 pre-commit 단계 뒤라 훅 설정으로 앞당길 수 없고, 메시지는 `-m`에 있어 PreToolUse 훅이 `tools/check_commit_msg.py`를 먼저 부르면 된다). 되돌림은 PR 하나다. 더하는 것이라 다섯 번째에 반영하고 1회차로 대기열에 썼다: `.scratch/retro-queue/commit-msg-after-slow-checks.md`.
- **python-i-utf8**(승인된 항목에 회차): 이 세션에서도 `PYTHONUTF8=1 uv run python -I eval_if.py …`가 한글을 깨뜨렸다(`-I`가 환경 변수를 읽지 않는다). 항목을 찾아(`--search`) 승인 줄을 3회차로 올렸다: `.scratch/retro-queue/python-i-utf8.md`.
- 작업 폴더를 옮기는 `cd` 명령을 훅이 거부한 것(두 번): 기각. 이미 있는 훅이 그 자리에서 막았고 `-C`와 경로 인자로 바로 풀렸다.
- 인용 대조 경고(`check-quotes`가 원문과 다른 따옴표 인용 하나를 알렸다): 기각. 이미 있는 훅이 알렸고 따옴표를 떼어 풀었다. 서브에이전트 보고가 준 따옴표 인용(ADR 문장)을 티켓에 옮기기 전에 grep으로 대 보고 글자가 다르면 풀어 썼다. 이 지침은 `code-review`의 주장 검증 2에 이미 있다.
- WebFetch 요약을 근거로 쓰려던 것: 기각. 훅의 알림이 받은 본문을 내려받아 대 보라고 했고 그대로 했다.
- 같은 파일을 두 세션이 고치는 충돌 위험(03 티켓): 기각. 사건이 나지 않았고 보류 판단으로 피했다.

## 다음

- 이 PR(#24)을 병합한다. 병합 뒤 새 세션을 열 일은 없다. 같은 기능의 01(`dev-base-tools`)과 03(`dev-base-skills-docs`)은 다른 세션이 지금 돌고 있고(워크트리 `01-dev-base-tools`, `03-dev-base-skills-docs`), 04는 01·02·03이 병합된 뒤, 05는 04와 agent-os `dev-release-pr-step` 병합 뒤라 아직 열 수 없다(`.scratch/plan-head.md`의 "하네스 기능" 문단).
- 03 세션이 받을 것은 02가 넘긴 두 몫이다. (1) `docs/constitution/operations.md` "리뷰 파이프라인"에 적을 줄: 출시 PR은 봇이 건너뜀, 기본 브랜치가 dev인 동안 dev와 main의 `claude-code-review.yml`이 다르면 base가 main인 hotfix PR의 Claude Code Review가 알려진 빨강일 수 있음(필수 검사 아님, PR 직전 리뷰와 셀프 리뷰가 대신함), 되돌려 합치기 PR은 봇이 돎. 24행 "Claude Code Review 워크플로가 함께 돈다"도 출시 PR에서는 맞지 않다. (2) ADR 0016 Consequences "리뷰 봇 두 갈래"를 이 결정과 근거의 종류(코드를 읽은 추론, 서버 비교는 보지 못함)로 고치고, 되돌려 합치기 PR이 건너뛴다고 적은 문장도 맞추고, `## 이력`에 적는다. 02 티켓에는 03 티켓을 고치지 않은 까닭을 적었다.
- 주 체크아웃 미갱신: 루트는 main(11f91c9). 이 세션은 주 체크아웃을 당기지 않는다. 묶음의 첫 세션이나 다음에 여는 세션이 `tidy-checkouts`로 당긴다.
- 대기열: 회차 5 이상은 `spec-review-transition-crossing`, `gate-pipe-read-status`이다. 이 기능은 아직 마지막 티켓이 아니라 chore 배치 계기가 아니다.
