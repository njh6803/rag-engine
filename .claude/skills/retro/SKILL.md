---
name: retro
description: "세션 회고. 사용자가 /retro를 치거나 마무리를 말할 때, 일지의 '다음' 절을 갱신하며 단계를 닫을 때 돌린다."
---

<!-- 프로젝트 사본, model-invoked. 원본(mattpocock/skills)은 disable-model-invocation: true. agent-os가 덧댄 판을 2026-11-09 킥오프에서 옮겼고, 이 주석과 본문의 괄호 속 ADR·대기열·일지 번호와 사례 번호(308, 101, 306, 238 등)는 agent-os의 기록이다. 이 저장소의 대기열에는 번호 항목이 없어 번호 항목을 다루던 문장은 뺐다. 근거는 일지 2026-09-20. 5단계(승인분을 대기열에 적는다)를 더했다. 근거는 일지 2026-09-22-10의 승인 2. 5단계의 행 형식과 번호 규칙은 2026-09-28 하네스 감사(대기열이 40KB 넘는 둘째 일지가 되고 재번호로 일지 참조 넷이 틀어졌다). 5단계의 `## 회고` 절은 대기열 78(retro 계기 훅이 그 제목을 읽는다). 4단계(후보를 에이전트가 판정한다), 5단계의 판정 기록과 승인 칸의 표지, 머리 문단의 끝 문장은 사용자 요청이다(일지 2026-10-12-41). 원본에서는 사용자가 후보를 고른다. 4단계의 회차로 세는 것과 좁힌 기각은 대기열 335(사용자 승인), 5단계의 같은 일을 다룬 행 찾기는 대기열 230이고, 다시 들어온 회고의 회차 거르기와 회고 절에 적는 회차 수, 닫힌 행을 이은 열린 행의 우선은 그 변경의 셀프 리뷰와 PR 직전 리뷰가 더했다(일지 2026-10-17-07). 4단계의 더하는 것의 문턱과 훅 발동 확인, 5단계의 행의 종류와 만료는 ADR 0036이다. 4단계의 회고 반영 줄(지금 PR의 티켓, 면제 PR의 harness 티켓, 병합 뒤의 새 harness 티켓)과 5단계의 티켓 경로로 닫기는 ADR 0037이다. 5단계가 대기열을 항목마다 파일 하나인 폴더로 쓰는 것과 새 항목의 영어 제목은 ADR 0045 결정 1이다. -->

You are running a **retrospective** for this session, either because the user asked or because a stage just closed (the journal's "다음" section was updated, or the user said they are wrapping up). You are suggesting improvements to the coding agent's **environment** to improve future runs. You judge each candidate yourself (step 4); the user is asked only about the candidates step 4 hands to them.

## Steps

1. Call the Skill tool with `writing-for-agents` for the writing style guide.

2. Read the primary sources. In this repo the primary source is this branch's journal (its "번복" and "갈린 곳" sections first), the path that `uv run python tools/sibling_overlap.py --journal` prints (the newest of the journals this branch added since the merge-base together with its untracked new ones; exit 1 means the branch has added none, then ask which journal to read), plus the current session. If the user names another session, search the session logs on this machine.

3. Look for candidates for improvement in these categories.

- **Navigation**: how easy was it for the agent to find the right files? Are there hidden dependencies between files? Would a **navigation pointer** make it easier? _Use when_ the session took a long time to find a piece of information.
- **Automated checks**: are there automated checks that could catch errors the agent made? Linting, typing, tests, filesystem linters? Read the repo's own check command first (its `package.json`/build-tool `lint`/`check` scripts, its CI workflow), so a check that already exists but sits unwired or silently broken is the finding, not a reinvention. A repo with no **guardrail** (no pre-commit hook and no CI job running its lint/typecheck/test command) is itself a finding: an un-linted repo is a standing missed opportunity, not a neutral default. _Use when_ the agent made a mistake an automated check could have caught, or the repo has no guardrail at all.
- **Coding standards**: should the **reviewer agent** be given a new rule to enforce? Should an existing rule be removed or clarified? Classify the violation first: a **mechanical** one (a fixed syntactic pattern, a banned API, an import shape, a file-location rule) gets a deterministic check, full stop: a custom rule in the repo's own linter, a new pre-commit hook, or a new CI job, whichever the repo's language and existing guardrail make cheapest. Default to building the check over writing the rule. Reserve `CODING_STANDARDS.md` for genuine **judgement calls** (cross-file consistency, "matches the surrounding style," anything no guardrail could ever substitute for). _Use when_ the reviewer agent failed to catch a mistake.
- **Global AGENTS.md**: are there any steering instructions that should be moved to coding standards (or automated checks) instead? _Use when_ the AGENTS.md file is particularly large - in the repo OR the user's global scope.
- **Tool economy**: did the agent make expensive tool calls that could be streamlined? Is there any custom tooling (CLI's, MCP's) that is particularly token-inefficient? _Use when_ the agent made an expensive tool call.
- **No-ops**: look for instructions in steering files that don't modify the agent's behavior. _Use when_ the steering files are large and unwieldy.
- **Information access**: look for opportunities to increase the agent's access to information. Teeing dev server logs, readonly access to third-party services. _Use when_ a crucial piece of information was not available to the agent.

4. **후보마다 판정한다.** 판정은 승인, 기각, 넘김의 셋이고, 사용자에게 묻지 않고 에이전트가 정한다. 넘김은 판정을 사람에게 넘기는 것이고, 넘길 것부터 거른다.

   - **넘김**은 아래 다섯이다. 이 밖이라도 어느 판정인지 서지 않으면 넘긴다.
     - ADR이 필요한 것(`CLAUDE.md` 작업 규약 5).
     - 사용자 승인으로 쓰는 문서(`docs/PRD.md`, 헌법)와 계약(검색 도구의 형식, 수집 API, 커넥터·변환·파서 인터페이스, 색인 형식. 원칙 VII)에 닿는 것.
     - 가드레일이나 사람의 확인을 느슨하게 하는 것. 검사·훅·권한 거부를 빼거나 좁히는 것, 권한 허용(`settings.json`의 allow)을 넓히는 것, 리뷰의 기준이나 범위를 좁히는 것, 게이트에 예외를 두는 것, 스킬이 사용자에게 묻거나 확인받는 단계를 빼는 것이다.
     - 스스로 승인하는 기준을 바꾸거나 넓히는 것. 이 retro 스킬과, 그 기준을 옮겨 적거나 가리키는 모든 자리(지침, 런북, 표준, README, 대기열 폴더의 README와 항목)가 대상이다.
     - 사람만 할 수 있는 것(외부 계정, 결제, 권한 부여).
   - **승인**은 나머지 가운데 셋을 모두 지나는 것이다.
     - 사건: 이 세션이나 일지에 실제로 난 실수나 비용을 하나 든다.
     - 층: `CLAUDE.md` 교정 루프의 사다리에서 강제력이 가장 높은 층으로 고쳐 쓴 꼴로 승인한다. 검사가 잡을 수 있는 것은 검사로 승인한다.
     - 되돌림: PR 하나로 되돌릴 수 있다.
   - **반영할 때**는 승인한 것의 종류가 정한다. 지금 반영하지 않는 것은 5단계대로 대기열에 둔다.
     - 고침(도구·훅·스킬의 버그, 틀린 사실, 깨진 경로)은 사건 하나로 반영한다.
     - 더하는 것(새 훅·검사, 스킬·rules·지침에 더하는 문장, `CODING_STANDARDS.md`의 줄)은 같은 실수의 다섯 번째이거나 손상이 한 번 났을 때 반영한다. 손상은 작업이나 데이터를 잃은 것, 비밀이 밖으로 나간 것, main이 깨진 것(병합 뒤 main의 검사가 빨갛다), 다른 세션이나 체크아웃의 상태를 망가뜨린 것이다. 그 전에는 회차를 세는 항목으로 대기열에 둔다. 단계를 닫는 순간의 지침에 붙이는 계기 훅은 따로 세지 않고 그 지침과 함께 간다. agent-os에서 문장을 사건 하나로 더하던 동안 하네스 chore가 다음 하네스 chore를 불렀다(agent-os ADR 0036).
     - 어느 종류든 이 세션에서 반영하면 지금 PR의 티켓에 수용 기준 한 줄 `회고 반영: <한 것>, 일지 <파일>`을 더해 같은 PR에 싣는다. 티켓이 없는 면제 PR(`docs/<slug>`)이면 harness 티켓 한 장을 같은 PR에 쓰고 브랜치는 그대로 둔다. 지금 PR이 이미 병합됐으면 반영은 새 PR이라 새 harness 티켓을 쓰고(이름은 그 반영을 보여 주는 slug) 그 stem으로 브랜치를 딴다. harness 티켓을 새로 쓰면 자리·이름·서식은 `docs/agents/issue-tracker.md`이고 번호를 받지 않는다. 새로 쓴 티켓은 쓸 때 `in-progress`이고 반영을 싣는 커밋에서 `done`이다(`docs/agents/issue-tracker.md`).
     - 새 훅·검사가 문턱을 지나면(이 세션에서 반영하든 대기열에 두든) 그 전에 저장소 루트에서 `uv run python tools/hook_report.py`를 돌린다(agent-os에서 1분 남짓 걸렸다. Bash의 `timeout`을 300000으로 준다). 출력의 "뺄 후보"에 든 훅(창 안에서 알리지도 막지도 않았다)은 빼자고 넘긴다(넘김의 가드레일을 느슨하게 하는 것). 손상을 막는 훅은 0건이어도 넘기지 않는다.
     - 막는 훅은 `.claude/rules/tools.md`의 계기 훅·막는 훅 가름을 따른다.
     - `CODING_STANDARDS.md`의 줄은 위 문턱을 지나고 자동 검사로 옮길 수 없을 때 더한다. 대기열 항목의 `**어디로:**` 줄에 `CODING_STANDARDS.md`(다섯 번째 반복에서 retro가 더할 때)라 적는다.
   - **회차로 세는 것**은 승인이다. 구현 때 실리는 지침(rules, 스킬, `CLAUDE.md` 등)을 어겨 리뷰가 잡은 사건과, 열린 항목이 이미 처방한 사건이 여기 든다. 그 지침을 낸 항목이나 처방한 항목의 승인 줄에 회차를 더하고, 그 항목이 닫혔으면 새 항목의 승인 줄에 `<식별자>의 k회차`로 잇는다. 새 항목의 처방은 위 승인의 층 조건으로 고른다(308이 닫힌 101의 4회차로 계기 훅을 든 꼴). 항목은 5단계대로 찾고, 찾아도 없으면 새 항목이다. 리뷰가 잡도록 둔 기준(`CODING_STANDARDS.md`, `code-review`의 두 브리프)을 어겨 리뷰가 잡은 사건은 리뷰가 제 몫을 한 것이라 이 셈에서 뺀다. 그 사건은 검사로 옮길 수 있으면 위 승인의 세 조건으로, 표준에 더할 새 판단 기준이면 위 "반영할 때"의 `CODING_STANDARDS.md` 줄대로 가르고, 둘 다 아니면 기각이다. 이 셈이 없던 동안 지침을 어긴 사건이 "이미 있는 지침이 잡는다"며 일지에만 남아 회차가 쌓이지 않았고, 같은 꼴을 다른 회고는 이어 세어 훅으로 올렸다(대기열 335).
   - **기각**은 위 어느 판정에도 들지 않고 남은 것이다. 이미 있는 검사·훅·앱 가드가 그 자리에서 막거나 알린 것과, 사건 없이 떠올린 것이 여기 든다.

   후보를 심각도 순으로, 판정과 그 근거가 된 조건을 붙여 보인다. 넘긴 것이 있으면 그것만 선택 화면으로 묻고 답을 받아 5단계로 간다. 넘긴 것이 없으면 답을 기다리지 않는다.

5. 결과를 이 브랜치의 일지(`uv run python tools/sibling_overlap.py --journal`이 찍는 경로. 종료 1이면 2단계처럼 어느 일지에 적을지 묻는다)의 `## 회고` 절에 적는다. 낸 후보와 판정별 수, 후보마다 판정과 그 근거가 된 4단계의 조건, 승인된 것마다 사건과 간 자리(대기열 항목의 식별자와 더한 뒤 그 항목의 회차 수, 또는 이 세션에서 반영한 자리), 일지에만 남기는 것이다. 넘긴 것에 답하거나 판정을 뒤집은 사용자의 말은 원문을 인용 블록으로 적는다. 제목은 `## 회고` 그대로 쓰고(덧붙일 것은 `## 회고 (…)`), "다음" 절 앞에 둔다. `tools/hook_journal_retro.py`가 이 제목의 절을 retro가 돈 흔적으로 읽어, 자리 표시가 아닌 그 절이 있으면 "다음"을 적는 편집에 계기를 다시 넣지 않는다.

   승인된 것 중 **이 세션에서 반영하지 않는 것**을 `.scratch/retro-queue/`에 항목 파일로 쓴다. 파일 모양(상태·어디로·승인 줄), 이름 규칙, 인용을 푸는 규칙은 그 폴더의 `README.md`가 원천이다. 새 항목은 다음 빈 번호를 받지 않고 그 사건을 가리키는 짧은 영어 제목으로 짓는다(`coderabbit-inline-size`. 소문자·숫자·하이픈이고 소문자로 시작한다). 한번 정한 제목은 바꾸지 않는다. 끊긴 뒤나 압축 뒤에 다시 들어온 회고는 새 제목을 짓기 전에 이 일지의 `## 회고` 절이 적은 식별자를 그대로 쓰고, 그 이름의 파일이 이미 있으면 새로 쓰지 않고 회차를 더한다. 새 항목을 쓰기 전에 같은 일을 다룬 항목을 찾는다. 그 사건의 낱말(대상 파일의 전체 경로, 판정의 핵심어)마다 `--search <낱말>`을 붙여 저장소 루트에서 `uv run python tools/queue_open_rows.py --search <낱말> --search <낱말>`을 친다. 낱말은 정규식이고 따옴표 없이 준다(워크트리 가드가 따옴표 인자를 거부한 적이 있다). 그래서 낱말에는 글자, 숫자, `/`, `_`, `-`, `.`만 남기고, 그 밖의 문자(공백 포함)는 아무 글자에나 맞는 `.`으로 바꾼다. `tools/`처럼 넓은 낱말은 수백 항목을 내니 전체 경로와 판정의 핵심어로 좁힌다. 닫힌 항목까지 맞은 항목마다 파일 경로, 열림·닫힘, 회차, 머리가 한 줄씩 나온다. 맞은 항목을 모두 그 줄로 보고, 같은 일로 보이거나 머리로 가리지 못한 항목은 그 파일을 Read로 열어 처방까지 대 본다. 종료 1이면 라벨 줄이 빠진 항목 파일이 맞았을 뿐 출력은 온전하고, 그 파일도 경로로 연다. Grep 도구는 긴 줄을 `[Omitted long matching line]`으로만 내어, 이 찾기를 세션마다 스크립트로 했다(대기열 425). 같은 처방을 든 열린 항목이면 새 항목 대신 그 항목의 승인 줄에 회차를 더하고, 같은 일을 다른 길로 고치는 열린 항목이면 새 항목을 쓰되 두 항목이 서로 가리키게 하며, 닫힌 항목이면 4단계의 회차대로 잇는다. 닫힌 항목이 맞았으면 `--search <식별자>의`로 그 항목을 `<식별자>의 k회차`로 이은 항목을 한 번 더 찾는다. 이은 항목은 원래 항목과 낱말을 나누지 않을 수 있다. 그 가운데 열린 항목이 있으면 새 항목을 쓰지 않고 그 열린 항목에 회차를 더한다. 찾지 않고 쓴 224가 같은 판정을 게이트로 하자는 열린 31과 겹쳤고, 두 항목이 서로를 가리키지 않았다(대기열 230). 후보와 기각은 일지에만 남고 거기 오지 않는다. 대기열이 일지 산문에만 있으면 다음 세션이 그것을 세느라 파일 열여섯 개를 읽는다. 항목은 짧게 — 머리 한 문장(`# <ID>: …`), `**상태:**`·`**어디로:**`·`**승인:**` 줄, 머리에서 못 다 한 설명이 있으면 본문. 승인 줄에 회차 수, 최근 일지 파일명, ADR 필요 여부를 적고 `자체 승인 <날짜>`로 시작한다(넘겨서 사용자가 승인했으면 `사용자 승인 <날짜>`). 만료된 항목을 새 항목이 이을 때는 새 항목의 승인 줄에 이어 센 회차(`5회차`)를 적는다. 기존 항목에 회차를 더할 때는 승인 줄에 회차 수와 일지 파일명만 더한다. 끊긴 뒤나 압축 뒤에 다시 들어온 회고는 더하기 전에 이 일지의 `## 회고` 절이 그 항목에 적은 회차 수와 항목의 회차 수를 대 보고, 항목이 이미 그 수에 이르렀으면 다시 더하지 않는다. 사건의 서술과 판정의 근거는 일지 회고 절이 원천이고 대기열은 그 파일명을 가리킨다. 이 세션에서 닫거나 사용자가 되돌린 항목은 상태 줄 하나를 고친다(`닫힘 (<티켓 경로 또는 브랜치>, <날짜>, <한 것>. …)`, 되돌림이면 `닫힘 (사용자가 되돌림 <날짜>)`). 티켓으로 닫았으면 브랜치 대신 그 티켓 경로를 적는다. 식별자는 영구하다 — 닫은 항목 파일을 지우거나 이름을 바꾸지 않는다(일지와 다른 문서가 `대기열 <식별자>` 인용으로 가리킨다). 회차 5 이상인 열린 항목(사람 몫은 뺀다)이 `next-session` 결정표의 chore 배치 조건이다. 같은 대상 파일의 항목은 계기가 아니라 chore를 고른 뒤 함께 묶을 항목이다.

   **항목의 종류**에 따라 회차와 닫기가 다르다(agent-os ADR 0036).
   - 같은 실수의 반복: 4단계의 문턱대로 다섯 번째에 반영한다.
   - 끝이 열린 결함 종류: 같은 종류의 결함이 사례마다 다른 자리에서 나오는 항목이다(306, 부하에서만 빨간 시간 시험). 사례 하나를 고치는 것은 고침이지만, 세 번째 사례부터는 사례를 고치지 않는다. 종류 전체를 없애는 고침 하나를 하거나, 그 값을 받아들인다고 일지에 적고 항목을 닫는다. 둘 가운데 게이트를 느슨하게 하는 길(혼자 다시 돌려 지나가면 막지 않기)은 넘김이다. 받아들여 닫은 종류의 새 사례는 위의 항목 찾기에 그 항목이 걸려도 잇지 않고(새 항목도 쓰지 않는다) 일지에만 적는다. 다시 열지는 사용자가 정한다. agent-os에서 사례를 고친 PR이 전체 스위트를 돌리며 다음 사례를 찾아, 306은 나흘에 9회차가 쌓였다.
   - 사람 몫: 사람만 할 수 있는 일이다. `**어디로:**` 줄을 `사람 몫:`으로 시작하고 넘김으로 한 번 묻는다. 다시 보아도 회차를 더하지 않는다. `tools/queue_open_rows.py`가 chore 계기와 만료에서 뺀다. agent-os의 238은 같은 여섯을 세션마다 다시 보며 11회차가 되어 chore 계기였다.

   **만료**. 회고마다 저장소 루트에서 `uv run python tools/queue_open_rows.py`를 돌려 "만료할 항목"(사람 몫도 회차 5 이상도 아니고, 승인 줄의 가장 늦은 날짜가 14일 넘게 지났다)을 닫는다. 워크트리에서는 `git fetch origin` 뒤 `--ref origin/main`을 붙여 한 번 더 돌리고 두 출력에 모두 든 항목만 닫는다. 다른 PR이 그 항목에 회차를 더했을 수 있다. 상태 줄을 `만료 <날짜>`로 고친다. "날짜를 찾지 못한 항목"은 그 항목의 글이 대기열에 처음 든 커밋을 git 기록에서 찾아 그 날을 승인 줄에 적는다. 회차 5 이상인 항목은 chore가 반영할 때까지 남는다. 만료는 고쳐졌다는 판정이 아니라 지금 할 일 목록에서 내리는 것이다. 그 실수가 다시 일어나면 위의 항목 찾기가 만료한 항목도 찾아 4단계대로 `<식별자>의 k회차`로 잇는다. k는 항목 찾기에 걸린 항목(만료한 항목과 그 항목을 이은 항목) 가운데 가장 큰 회차에 하나를 더한 값이다. 그래서 만료가 이어져도 회차가 끊기지 않고, 드물게 일어나는 실수도 다섯 번째에 닿는다. 회차는 세션이 적어야 생긴다. 다시 돌려 초록이 된 실패처럼 적지 않고 지나가기 쉬운 사건도 일지에 적는다.

## Reference

### Implementation vs Review

Remember that all work goes through two stages: implementation and review. The implementation agent has the most **context pressure**. They are responsible for exploration, writing code, and debugging failures.

The review agent has the least context pressure - it receives a diff, so no exploration needed. It often does not need to write code or debug.

This means that the review agent should be responsible for imposing coding standards, not the implementation agent.

### Files

You have access to several files in the repo:

- `CLAUDE.md`/`AGENTS.md`: these files are pushed to the context window of any agent working in this repo. They should be used incredibly sparingly, usually only for **navigation pointers** to other files.
- `CODING_STANDARDS.md`: this file is read during review, not implementation. Add **navigation pointers** to docs folders if the standards file gets more than 1,000 lines long.
- Docs: use docs as references files, pointed to by other files. Look for existing docs before writing new ones.
- Skills: use skills for docs (since their description goes into the agent's context window), or for user-invoked commands. Follow the advice in the `writing-for-agents` skill.
