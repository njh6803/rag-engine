---
name: to-tickets
description: Break a plan, spec, or the current conversation into a set of tracer-bullet tickets, each declaring its blocking edges, published to the configured tracker (edges as text in one file per ticket locally, or native blocking links on a real tracker).
disable-model-invocation: true
---

<!-- 프로젝트 사본. agent-os가 덧댄 판을 2026-11-09 킥오프에서 옮겼고, 이 주석과 본문의 괄호 속 ADR·대기열 번호는 agent-os의 기록이다. 원본(mattpocock/skills)에 다섯을 더했다. 1단계의 기능 실행 순서(대기열 7 — 그 순서가 런북에만 있었다), 5단계의 받는 쪽 확인(대기열 3)과 옮기는 테스트의 이음매 확인(대기열 106), 5단계 로컬 파일의 stem이 구현 브랜치가 된다는 것(agent-os ADR 0037), 템플릿 뒤 문단의 경로 규칙을 저장소 관행에 맞춘 것(대기열 400). 이 주석이 `tools/check_instructions.py`의 센티널이라 지우면 검사가 빨강이 된다. -->

# To Tickets

Break a plan, spec, or conversation into a set of **tickets**: tracer-bullet vertical slices, each declaring the tickets that **block** it.

The issue tracker and triage label vocabulary should have been provided to you. If not, tell the user to run `/setup-matt-pocock-skills`.

## Process

### 1. Gather context

Work from whatever is already in the conversation context. If the user passes a reference (a spec path, an issue number or URL) as an argument, fetch it and read its full body and comments.

기능 하나의 순서는 이렇고 이 스킬은 넷째다. 설계 인터뷰(`/grill-with-docs`, 용어는 `GLOSSARY.md`, 결정은 `docs/adr/`) → 명세(`/to-spec`) → 명세 검토(`spec-reviewer` 서브에이전트, 읽기 전용) → **티켓(이 스킬)** → 구현(`/implement`, 티켓마다 새 세션과 `feature/<NN>-<slug>` 브랜치) → 커밋 전 셀프 리뷰(`/code-review`) → PR 직전 CLI(`coderabbit-review`. 못 돌면 `/security-review`와 `bug-perf-review`) → PR·반영·병합(`/git-pr`, `/git-pr-feedback`, `/git-pr-merge`, 계기는 `next-session`). 명세 검토가 안 됐으면 그것부터 한다. 건너뛸지의 기준은 "몇 개를 건드리나"가 아니라 "건드리는 곳마다 새로 정할 것이 있나"다. 첫 기능 전에는 공통 규약(식별자 형식, 에러 봉투, 시간대, 색인 형식의 판)을 정한다.

### 2. Explore the codebase (optional)

If you have not already explored the codebase, do so to understand the current state of the code. Ticket titles and descriptions should use the project's domain glossary vocabulary, and respect ADRs in the area you're touching.

Look for opportunities to prefactor the code to make the implementation easier. "Make the change easy, then make the easy change."

### 3. Draft vertical slices

Break the work into **tracer bullet** tickets.

<vertical-slice-rules>

- Each slice cuts a narrow but COMPLETE path through every layer (schema, API, UI, tests): vertical, NOT a horizontal slice of one layer
- A completed slice is demoable or verifiable on its own
- Each slice is sized to fit in a single fresh context window
- Any prefactoring should be done first

</vertical-slice-rules>

Give each ticket its **blocking edges**: the other tickets that must complete before it can start. A ticket with no blockers can start immediately.

**Wide refactors are the exception to vertical slicing.** A **wide refactor** is one mechanical change (rename a column, retype a shared symbol) whose **blast radius** fans across the whole codebase, so a single edit breaks thousands of call sites at once and no vertical slice can land green. Don't force it into a tracer bullet; sequence it as **expand–contract**. First expand: add the new form beside the old so nothing breaks. Then migrate the call sites over in batches sized by blast radius (per package, per directory), each batch its own ticket blocked by the expand, keeping CI green batch to batch because the old form still exists. Finally contract: delete the old form once no caller remains, in a ticket blocked by every migrate batch. When even the batches can't stay green alone, keep the sequence but let them share an integration branch that all block a final integrate-and-verify ticket; green is promised only there.

### 4. Quiz the user

Present the proposed breakdown as a numbered list. For each ticket, show:

- **Title**: short descriptive name
- **Blocked by**: which other tickets (if any) must complete first
- **What it delivers**: the end-to-end behaviour this ticket makes work

Ask the user:

- Does the granularity feel right? (too coarse / too fine)
- Are the blocking edges correct: does each ticket only depend on tickets that genuinely gate it?
- Should any tickets be merged or split further?

Iterate until the user approves the breakdown.

### 5. Publish the tickets to the configured tracker

Publish the approved tickets. **How** depends on the tracker `/setup-matt-pocock-skills` configured; the tickets are the same either way, only the shape of the blocking edges changes:

- **Local files** → write one file per ticket under `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01` in dependency order (blockers first). Each file's "Blocked by" lists the numbers/titles it depends on. Use the per-ticket file template below: one ticket per file, never a single combined file. 파일 이름의 stem(`<NN>-<slug>`)이 그 티켓을 구현하는 브랜치 `feature/<NN>-<slug>`가 된다. 브랜치 이름만 보고 티켓을 찾으므로 slug는 브랜치로 읽어도 그 일을 가리키게 짓는다(`docs/agents/issue-tracker.md`).
- **A real issue tracker (GitHub, Linear, …)** → publish one issue per ticket in dependency order (blockers first) so each ticket's blocking edges can reference real identifiers. Use the platform's native blocking / sub-issue relationship where it has one; otherwise set each ticket's "Blocked by" to the blocking issues. Apply the `ready-for-agent` triage label unless instructed otherwise; the tickets are agent-grabbable by construction.

Work the **frontier**: any ticket whose blockers are all done. For a purely linear chain that means top to bottom.

명세나 리뷰가 다른 티켓·기능에 넘긴 것("그 층에서 재확인", 측정)은 받는 티켓의 수용 기준이나 받는 기능의 기능 계획(`.scratch/<받는 slug>/plan.md`) 본문에 적는다. 기능 계획의 한 줄 요약은 전체 계획 표의 내용 칸이 되므로 넘긴 것은 요약이 아니라 본문에 둔다. 받는 쪽의 Blocked by가 넘기는 쪽을 포함하는지 본다 — 받는 쪽이 먼저 돌 수 있다(대기열 3, 세 번).

명세 검토나 리뷰가 제안한 테스트 문장을 수용 기준으로 옮길 때는 그 테스트를 지금 이음매(주입되는 포트, 시계)로 잴 수 있는지 코드로 본다. 잴 수 없는 테스트는 어떤 구현에서도 초록이다. agent-os에서 명세 검토의 "가짜 시계를 `exp` 너머로"를 그대로 옮겼는데, 그때의 인증 미들웨어는 시계 포트를 받지 않았고 PyJWT는 벽시계를 읽었다(대기열 106, 검토의 문구를 뜻을 되짚지 않고 옮긴 세 번째).

Do NOT close or modify any parent issue.

<local-ticket-template>

# <NN>: <Ticket title>

**What to build:** the end-to-end behaviour this ticket makes work, from the user's perspective, not a layer-by-layer implementation list.

**Blocked by:** the numbers/titles of the tickets that gate this one, or "None (can start immediately)".

**Status:** ready-for-agent

- [ ] Acceptance criterion 1
- [ ] Acceptance criterion 2

</local-ticket-template>

<issue-template>

## Parent

A reference to the parent issue on the tracker (if the source was an existing issue, otherwise omit this section).

## What to build

The end-to-end behaviour this ticket makes work, from the user's perspective, not layer-by-layer implementation.

## Acceptance criteria

- [ ] Criterion 1
- [ ] Criterion 2

## Blocked by

- A reference to each blocking ticket, or "None (can start immediately)".

</issue-template>

어느 꼴이든 코드 조각과, 명세가 고칠 자리로 정하지 않은 구현 파일의 경로는 적지 않는다. 금방 낡는다. 규칙 문서(`.claude/rules/*.md`)·ADR·테스트 선례의 경로와 명세가 정한 고칠 자리의 경로는 적는다. agent-os의 티켓이 그 경로를 들어 왔는데 원본 문언("avoid specific file paths")이 남아, 셀프 리뷰 표준 축이 그 경로를 Nit으로 냈다(대기열 400. to-spec 사본의 같은 문장은 대기열 30). Exception: if a prototype produced a snippet that encodes a decision more precisely than prose can (state machine, reducer, schema, type shape), inline it and note briefly that it came from a prototype. Trim to the decision-rich parts, not a working demo, just the important bits.
