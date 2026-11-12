---
name: implement
description: "Implement a piece of work based on a spec or set of tickets."
disable-model-invocation: true
---

<!-- 프로젝트 사본. agent-os가 덧댄 판을 2026-11-09 킥오프에서 옮겼고, 이 주석과 본문의 괄호 속 ADR·대기열·일지·티켓 번호는 agent-os의 기록이다. 이 저장소에 없는 웹 워크스페이스(pnpm, 브라우저)와 환경 규약 상세를 가리키던 대목은 뺐다. 원본(mattpocock/skills)에 아홉을 더했다. 시작 전 브랜치 규약 포인터, 워크트리 먼저(next-session directive.md와 주 체크아웃의 자기 점검, 그보다 앞선 tidy-checkouts), 티켓 맞추기(브랜치 이름이 티켓 stem, 상태의 흐름, 티켓 없이 받은 일, 마지막 티켓이 적는 기능 계획의 끝 줄과 전체 계획 도구, ADR 0037·0045), 루프 중의 린트, 끝 전체 실행의 러너(대기열 334), 빨강을 본 적 없는 테스트의 변이 도구 포인터(pytest 밖, 다른 워크트리, `--check`), 이 티켓의 몫만 쓰기(대기열 35), 설치한 판과 측정한 판의 견줌(대기열 61), 마칠 때 세션 경계(원천은 next-session 스킬). 근거는 일지 2026-09-21 첫 슬라이스 회고 뒤 대화, 인터럽트 설계 뒤 대화, 티켓 01 회고, 세션 경계 일지, 대기열 29·35·59·61·334. -->

Implement the work described by the user in the spec or tickets.

시작 전에 브랜치를 `docs/constitution/operations.md`의 규약대로 딴다. 티켓마다 브랜치 하나, PR 하나이고, 브랜치 이름은 티켓 파일 이름의 stem 그대로다(기능 디렉터리의 티켓은 `feature/<NN>-<slug>`, harness 티켓은 `chore/<slug>`. `docs/agents/issue-tracker.md`). 지시문의 "어디서" 줄이 워크트리를 말하면(조건은 next-session directive.md) 그 문장대로 워크트리에 먼저 들어가고 거기서 브랜치를 다룬다. 그 문장이 `tidy-checkouts`를 먼저 돌라고 하면 워크트리보다 그것이 먼저다 — 주 체크아웃 세션일 때만 루트를 당길 수 있다(next-session directive.md). `EnterWorktree`를 치기 직전에(`tidy-checkouts`를 먼저 돌았다면 그 뒤에) `git worktree list --porcelain`으로 그 자리나 브랜치를 쓰는 세션이 없는지 본다(agent-os ADR 0032). 지시문이 없어도, 작업 폴더가 주 체크아웃인데 `git branch --show-current`가 루트 브랜치(main이나 dev. 정하는 법은 `tidy-checkouts`)도 이 티켓의 브랜치도 아니거나, 루트 브랜치인데 `git status --porcelain`이 비지 않았으면 주 체크아웃에서 브랜치를 따지 않고 `EnterWorktree`로 간다(이 티켓의 브랜치면 주 체크아웃에서 끊은 작업을 잇는 것이다) — 같은 체크아웃의 다른 세션이 그 브랜치 전환으로 커밋 대상을 잃는다(일지 `2026-09-23-02`). 새 워크트리에 들어가면 먼저 `uv sync`를 친다(`.pre-commit-config.yaml` 머리 주석의 체크아웃·워크트리마다). 예외를 제안하려면 이유와 그 이유가 사라지는 조건을 같이 적고, 조건이 차면 규약으로 돌아간다.

워크트리와 브랜치가 선 뒤, 코드를 고치기 전에 티켓을 맞춘다. 받은 티켓이 `ready-for-agent`이면 첫 편집으로 그 `Status:`를 `in-progress`로 바꿔 첫 커밋에 싣는다. 티켓 없이 받은 일이면 먼저 티켓을 `in-progress`로 쓰고(자리·이름·서식은 `docs/agents/issue-tracker.md`. harness 티켓은 번호 없이 일을 보여 주는 slug를 직접 짓는다), 브랜치 이름을 그 stem에 맞추고(`git branch -m`) `set_session_title`에 `self`와 새 브랜치를 주어 세션 제목도 바꾼다. 형제 거르기(`next-session` 2단계의 1)와 워크트리에 들어가기 전의 세션 확인(위 첫 문단)이 제목만 보고 세션을 찾는다. 터미널이라 그 도구가 없거나 앱이 거절하면 제목은 그대로 두고 잇는다. chore 지시문이 경로를 준 일도 그 경로에 티켓부터 쓴다. PR을 열기 전에 티켓을 `done`으로 바꿔 커밋한다. 그 커밋이 기능의 마지막 열린 티켓을 닫고(done이나 wontfix로 바꾸거나 그 티켓을 지운다), 닫은 뒤 그 기능의 done 티켓이 하나 이상이고, 기능 계획 `.scratch/<slug>/plan.md`에 `**슬라이스:**` 줄이 있으면(하네스 기능은 없다) 같은 커밋에서 그 파일에 `**끝:** YYYY-MM-DD`(그 커밋의 로컬 날짜)를 적는다. 끝 줄이 이미 있는 기능(done 기능의 고침 티켓)은 그 줄을 그대로 둔다. 빠뜨리면 저장소 상태 시험이 막는다. 티켓을 `done`으로 바꾸거나 기능 계획을 고친 커밋은 `uv run python tools/plan_table.py`를 손으로 돌려 `.scratch/plan.md`까지 싣는다(상태는 도구가 `끝` 줄과 done 티켓에서 읽는다. 규칙은 `docs/agents/issue-tracker.md`의 전체 계획 절).

Use /tdd where possible, at pre-agreed seams.

이 티켓의 체크박스가 요구하는 것만 쓴다. 다음 티켓에 걸릴 것(형제 티켓이 붙일 라우트의 독스트링, "재개 라우트도 같다" 같은 미래형 문장)은 그 티켓 파일의 메모로 넘긴다. 세 번 명세 축 리뷰가 잡아 한 바퀴씩 들었다(대기열 35).

의존성을 더하거나 올리면 설치된 판을 명세·ADR이 근거로 든 측정의 판(그 프로브의 README 줄)과 견준다. major가 다르면 그 측정을 다시 돌린다(대기열 61, 규약은 `docs/agents/issue-tracker.md`의 프로브와 근거 절).

Run linting and typechecking regularly, single test files regularly, and the full test suite once at the end. 끝의 전체는 `uv run ruff check . && uv run ruff format --check .`와 `uv run python tools/run_checks.py`다. 맨 `uv run pytest -q`는 한 프로세스이고, 러너는 pytest를 나눠 돌며 타입체크·경계와 나머지 검사를 함께 띄운다(`tools/run_checks.py`의 `CHECKS`). agent-os에서는 맨 pytest가 8분을, 러너 한 바퀴가 3분을 넘겨(agent-os ADR 0035) Bash의 `timeout`을 600000으로 주거나 백그라운드로 돌렸다. 이 저장소도 러너가 2분을 넘기면 그렇게 한다. 다른 세션이 함께 돌면 600초에 닿으므로 백그라운드로 넘어가면 다시 치지 않고 끝 알림을 기다린다. red가 예상보다 넓으면 린트를 먼저 돌린다. 이름 충돌과 import 문제는 테스트 실패로 위장한다.

구현 전부터 초록인 테스트(순서나 경계를 고정하는 가드)와 구현 뒤에 쓴 테스트는 빨강을 본 적이 없다. 그 테스트가 지키는 코드에 `tools/mutate.py`로 변이를 넣어 빨강을 본다. pytest 밖의 검사도 같은 도구다. 변이마다 기대를 변이 파일(TOML)에 적는다. 수십 분 도는 변이 열은 커밋한 뒤 다른 워크트리에서 돌리고 이 체크아웃에서는 계속 일한다. 코드를 옮기거나 고쳤으면 그 코드를 겨누던 변이 파일을 `--check`로 본다. 형식과 절차는 그 도구의 독스트링이다.

Once done, use /code-review to review the work.

Commit your work to that branch.

거기서 멈춘다. 다음 티켓은 새 세션이 한다. 이유와 다음 세션 지시문은 next-session 스킬이 원천이고, 사용자가 `/git-pr`로 PR을 열면 훅이 그 계기를 넣는다.
