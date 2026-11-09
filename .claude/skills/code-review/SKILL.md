---
name: code-review
description: "Review the changes since a fixed point (commit, branch, tag, or merge-base) along two axes: Standards (does the code follow this repo's documented coding standards?) and Spec (does the code match what the originating issue/spec asked for?). Runs both reviews in parallel sub-agents and reports them side by side. Use when the user wants to review a branch, a PR, work-in-progress changes, or asks to \"review since X\"."
---

<!-- 프로젝트 사본. agent-os가 원본(mattpocock/skills)에 덧댄 판을 2026-11-09 킥오프에서 옮겼다. 이 주석과 본문의 괄호 속 ADR·대기열·일지 번호는 agent-os의 기록이고(이 저장소의 ADR과 대기열 항목이 아니다), 이 저장소에 맞춰 고친 곳은 계약의 목록, 경계와 냄새의 예, 손으로 치는 검사의 수, 이 저장소에 없는 문서를 가리키던 포인터다. 원본에 더한 것: 4단계의 표준 축 모델과 노력(언제나 sonnet·high, ADR 0033. 처음 규칙은 일지 2026-09-20 첫 회고), 1단계의 미커밋·미추적 범위와 5단계의 범위 한 줄, 6단계의 반영(일지 2026-09-21 리뷰 반영 루프), 2단계의 요구·참고 가름(대기열 26), 2단계 명세 출처의 브랜치가 가리키는 티켓 파일(ADR 0037), 4단계 두 브리프의 주장 검증 목록(대기열 20, 15회차. 근거 문장의 종류는 대기열 45·124, 목록 모양은 대기열 76, 부르는 쪽의 길은 대기열 60, 잔존을 세는 문서는 대기열 87), 6단계 4의 받는 쪽 확인(대기열 3), 2단계의 사용자 답과 옮기는 변경의 옛 판정(대기열 46·181), 4단계의 외부 근거 발췌(대기열 156), 6단계 1의 고친 문장의 근거(대기열 154), 2와 4의 보류·넘김의 책임 근거(대기열 151), 5의 pre-commit 갈음(대기열 180), 4단계 두 브리프의 갈래 밟기(대기열 229), 6단계 1의 반례를 일반 조항으로 올리기(대기열 213)와 새로 쓴 문장을 PR 직전 리뷰에 밀 주장으로 넘기기(대기열 260), 4단계 주장 검증 목록의 코드의 동작을 불러 대 보기(대기열 305), 6단계 끝의 보고를 받은 턴에 일지로 옮기기(대기열 244)와 그 번호 받기의 2 갈래를 도구의 `할 일:` 줄로 줄이기(대기열 251. 일지가 번호를 받지 않게 되며 2026-11-07에 그 문장이 걷혔다). 이 주석이 `tools/check_instructions.py`의 센티널이라 지우면 검사가 빨강이 된다. -->

Two-axis review of the diff between `HEAD` and a fixed point the user supplies:

- **Standards**: does the code conform to this repo's documented coding standards?
- **Spec**: does the code faithfully implement the originating issue / spec?

Both axes run as **parallel sub-agents** so they don't pollute each other's context, then this skill aggregates their findings.

The issue tracker should have been provided to you. If `docs/agents/issue-tracker.md` is missing, tell the user to run `/setup-matt-pocock-skills`.

## Process

### 1. Pin the fixed point

Whatever the user said is the fixed point (a commit SHA, branch name, tag, `main`, `HEAD~5`, etc.). If they didn't specify one, ask for it.

`git merge-base <fixed-point> HEAD`로 base SHA를 한 번 구해 고정하고, 아래 명령과 서브에이전트 둘에 ref가 아니라 그 SHA를 넘긴다. ref도 동작하지만 `main`은 세션 중 전진하고, 두 축이 각자 merge-base를 다시 구하면 서로 다른 나무를 본다.

주 용도가 커밋 전 셀프 리뷰이므로 범위는 커밋된 것에서 끝나지 않는다. 셋을 잡는다.

- `git diff <BASE>`: base 이후의 커밋과 staged·unstaged 작업. 세 점 diff(`<BASE>...HEAD`)는 아직 커밋하지 않은 작업을 빼므로 쓰지 않는다. `implement`는 리뷰한 뒤 커밋하므로 리뷰 시점의 작업은 대개 미커밋이다.
- `git status --porcelain`의 `??` 항목: 미추적 파일. 어떤 diff에도 안 잡힌다. 새 어댑터나 새 테스트가 통째로 리뷰에서 빠지는 자리다. 경로 목록을 서브에이전트에 넘겨 파일 전체를 새 코드로 읽게 한다.
- `git log <BASE>..HEAD --oneline`: 커밋 목록.

Before going further, confirm the fixed point resolves (`git rev-parse <fixed-point>`). diff와 미추적 목록이 **둘 다** 비면 여기서 실패한다. 빈 diff 하나로는 실패하지 않는다. 미추적 파일만 있는 상태가 이 스킬이 닫으려는 갭이기 때문이다. A bad ref should fail here, not inside two parallel sub-agents.

### 2. Identify the spec source

Look for the originating spec, in this order:

1. Issue references in the commit messages (`#123`, `Closes #45`, GitLab `!67`, etc.), fetched via the workflow in `docs/agents/issue-tracker.md`.
2. A path the user passed as an argument.
3. 브랜치가 가리키는 티켓 파일. 브랜치 이름의 stem이 티켓 파일 이름이다. `feature/<NN>-<slug>`이면 이 브랜치의 변경에 든 `.scratch/<기능>/issues/<NN>-<slug>.md`이고 그 기능 디렉터리의 `spec.md`도 명세다. `chore/<slug>`이면 `.scratch/harness/issues/<slug>.md`다(`docs/agents/issue-tracker.md`).
4. A spec file under `docs/`, `specs/`, or `.scratch/` matching the branch name or feature.
5. If nothing is found, ask the user where the spec is. If they say there isn't one, the **Spec** sub-agent will skip and report "no spec available".

티켓 없이 사용자 요청을 명세로 쓸 때는 **요구**와 **리뷰어 참고**를 다른 절로 적는다. 참고 절에는 "요구가 아니다 — 빠뜨렸다고 내지 마라"를 붙인다. 가르지 않으면 명세 축이 "이 세션이 한 것" 목록을 요구로 읽어 표준 축이 지우라고 한 문장을 누락으로 낸다(대기열 26).

명세가 티켓이든 사용자 요청이든 요구에 넣는 것이 둘 더 있다.

- **사용자의 답.** `AskUserQuestion`의 답은 라벨과 함께 고른 선택지의 설명을 글자 그대로 옮기고, 요약을 확인받은 질문이면 그 요약도 옮긴다. 결정의 조건은 설명과 요약에 있다. 라벨만 넘기자 명세 축이 설명과 공유 이해 요약에 있던 결정 셋을 범위 넘침으로 냈고, "거절은 429"로 줄여 옮기자 설명의 "요청 크기 초과는 기존 422"가 빠져 Major가 났다(대기열 46).
- **옮기는 변경의 옛 판정.** 손으로 지은 스크립트를 도구나 명세로 대신하는 것처럼 옛 구현을 옮기는 변경이면, 옛 구현이 판정하던 것과 계약을 하나씩 목록으로 적는다. 새 경우를 받으려고 넓힌 판정이 옛 경우까지 풀었는지를 명세 축이 그 목록으로 잡는다(대기열 181).

### 3. Identify the standards sources

Anything in the repo that documents how code should be written, such as `CODING_STANDARDS.md` or `CONTRIBUTING.md`.

On top of whatever the repo documents, the Standards axis always carries the **smell baseline** below: a fixed set of Fowler code smells (_Refactoring_, ch.3) that applies even when a repo documents nothing. Two rules bind it:

- **The repo overrides.** A documented repo standard always wins; where it endorses something the baseline would flag, suppress the smell.
- **Always a judgement call.** Each smell is a labelled heuristic ("possible Feature Envy"), never a hard violation. Like any standard here, skip anything tooling already enforces.

Each smell reads *what it is* → *how to fix*; match it against the diff:

- **Mysterious Name**: a function, variable, or type whose name doesn't reveal what it does or holds. → rename it; if no honest name comes, the design's murky.
- **Duplicated Code**: the same logic shape appears in more than one hunk or file in the change. → extract the shared shape, call it from both.
- **Feature Envy**: a method that reaches into another object's data more than its own. → move the method onto the data it envies.
- **Data Clumps**: the same few fields or params keep travelling together (a type wanting to be born). → bundle them into one type, pass that.
- **Primitive Obsession**: a primitive or string standing in for a domain concept that deserves its own type. → give the concept its own small type.
- **Repeated Switches**: the same `switch`/`if`-cascade on the same type recurs across the change. → replace with polymorphism, or one map both sites share.
- **Shotgun Surgery**: one logical change forces scattered edits across many files in the diff. → gather what changes together into one module.
- **Divergent Change**: one file or module is edited for several unrelated reasons. → split so each module changes for one reason.
- **Speculative Generality**: abstraction, parameters, or hooks added for needs the spec doesn't have. → delete it; inline back until a real need shows.
- **Message Chains**: long `a.b().c().d()` navigation the caller shouldn't depend on. → hide the walk behind one method on the first object.
- **Middle Man**: a class or function that mostly just delegates onward. → cut it, call the real target direct.
- **Refused Bequest**: a subclass or implementer that ignores or overrides most of what it inherits. → drop the inheritance, use composition.

### 4. Spawn both sub-agents in parallel

Spawn the Standards sub-agent with `model: sonnet` and `effort: high`, whatever kind of change the diff is (source, docs, config, harness; agent-os ADR 0033). Give the Spec sub-agent neither, so it inherits the main session's model (and, by agent-os ADR 0033's estimate, its effort). 문서만 바뀐 변경도 리뷰는 한다. 지침과 하네스는 다음 실행에 바로 영향을 주므로 면제 대상이 아니다. When there is no spec (step 2), the Spec sub-agent is skipped.

**Standards sub-agent prompt** should include:

- The full diff command, the untracked file list, and the commit list.
- The list of standards-source files you found in step 3, **plus the smell baseline from step 3** pasted in full (the sub-agent has no other access to it).
- The brief: "Report, per file/hunk where relevant, (a) every place the diff violates a documented standard: cite the standard (file + the rule); and (b) any baseline smell you spot: name it and quote the hunk. Distinguish hard violations from judgement calls: documented-standard breaches can be hard, but baseline smells are always judgement calls, and a documented repo standard overrides the baseline. Skip anything tooling enforces. Under 400 words."
- 두 축 모두에 넣는 **주장 검증** 목록(대기열 20, 15회차까지의 처방. 근거 문장의 종류는 대기열 45·124, 목록 모양은 대기열 76, 부르는 쪽의 길은 대기열 60, 잔존을 세는 문서는 대기열 87, 코드의 동작은 대기열 305). 아래 머리 문장과 항목을 두 브리프에 그대로 붙여 넣는다. 밀 주장은 브리프에 나열하되 "나열 밖도 잰다"를 붙인다.

  diff가 담은 문서·주석·독스트링·ADR의 사실 주장을 하나하나 잰다.

  1. **닫힌 주장.** 수를 세어 닫는 주장('둘뿐', '유일하다', '전부')과 보편 주장('~은 ~가 아니다')은 반례를 찾아 민다.
  2. **인용.** **모든** 따옴표 인용은 원문과 글자 그대로인지 grep으로 본다 — 목록으로 주면 목록 밖은 운이다.
  3. **계약 변경.** 계약 변경이 거짓으로 만드는 문장은 옛 말이 아니라 바뀐 값으로 grep한다.
  4. **미래형.** 틈을 닫는 티켓은 앞 티켓이 미래형으로 쓴 문장('다음 티켓', '판정 티켓')을 grep한다.
  5. **잔존.** 잔존 grep은 옛 결정의 논증이 쓴 말도 찾는다. 잔존은 살아 있는 문서에서만 센다. 무엇이 기록인지는 `docs/constitution/operations.md` 문서 위치 절이 정한다.
  6. **근거 찾기.** 근거를 찾을 때는 그 근거가 쓰일 수 있는 말들로 grep한다('프로브'만이 아니라 '실측'·'쟀다').
  7. **근거의 종류.** '쟀다'·'실측'이 프로브를 가리키면 그 스크립트가 그 항목을 실제로 재는지 코드로 확인한다. 손으로 본 것·코드를 읽은 것·어림·웹 요약(WebFetch가 준 수와 인용)이 측정이나 원문처럼 적혔으면 낸다.
  8. **기점.** 변경을 세는 기점은 날짜가 아니라 커밋이다.
  9. **부르는 쪽의 길.** 독스트링·메모가 부르는 쪽에 안내하는 길(닫기, 취소, 재시도)은 테스트가 그 길을 그대로 밟는지 본다. 안내한 호출로 실제로 닫히거나 끊기는지, 기다리는 도중에 불러도 그런지 잰다.
  10. **코드의 동작.** 문서가 코드의 동작(받는 입력의 꼴, 든 예, 막는 것)을 서술하거나 선례로 들면 그 함수를 불러 서술의 경계 입력(받는다는 꼴, 받지 않는다는 꼴, 그 사이)으로 대 본다. 코드를 읽어 맞는 것으로는 닫지 않는다.

- diff가 저장소 밖의 문서(공식 문서, 표준, 상류 소스)를 근거로 들면 그 절의 짧은 발췌와 URL을 두 브리프에 싣는다. 본 세션이 받아 둔 사본을 두 축이 읽으려 하자 권한 분류기가 거부해, 둘 다 그 근거를 대조 불가로 남겼다(대기열 156).
- diff가 에이전트가 단계대로 따르는 절차를 바꾸면(스킬, 서브에이전트 정의, 훅이 넣는 문구, 지침의 진행 규율이 그 예다) 아래 **갈래 밟기** 문단을 두 브리프에 그대로 붙여 넣는다. 두 브리프에 이 문단이 없던 동안, 진행 규율을 바꾼 변경의 Major 둘(첫 PR을 연 직후의 훅 계기가 회고 전에 병합까지 간다, 회고 도중에 끊기면 이어 가기가 회고를 건너뛴다)이 셀프 리뷰를 지나 PR 직전 `bug-perf-review`에서야 나왔다(대기열 229).

  **갈래 밟기.** 바뀐 절차를 처음부터 끝까지 한 번에 따르는 길만 보지 않는다. 절차의 중간으로 들어오는 갈래(끊긴 뒤 다시 읽을 때, 컨텍스트 압축 뒤, 한 단계가 실패했을 때, 훅이 계기를 넣을 때 등)를 하나씩 밟아 보고, 틀린 동작(건너뛰는 단계, 두 번 하는 단계, 앞당겨지는 병합, 끊긴 단계를 잘못 가르는 상태 판정 등)이 나는 자리를 낸다. 두 괄호는 예시이고, 중간으로 들어오는 갈래는 모두 밟으며 그 갈래에서 절차가 시키는 대로 했을 때 어긋나는 동작은 모두 낸다.

**Spec sub-agent prompt** should include:

- The diff command, the untracked file list, and the commit list.
- The path or fetched contents of the spec.
- The brief: "Report: (a) requirements the spec asked for that are missing or partial; (b) behaviour in the diff that wasn't asked for (scope creep); (c) requirements that look implemented but where the implementation looks wrong. Quote the spec line for each finding. Under 400 words."

If the spec is missing, skip the Spec sub-agent and note this in the final report.

### 5. Aggregate

Present the two reports under `## Standards` and `## Spec` headings, verbatim or lightly cleaned. Do **not** merge or rerank findings, because the two axes are deliberately separate (see _Why two axes_).

End with a one-line summary: total findings per axis, and the worst issue _within each axis_ (if any). Don't pick a single winner across axes: that's the reranking the separation exists to prevent.

그 앞에 본 범위를 한 줄 적는다. base SHA, 파일 몇 개, 커밋 몇 개, 미추적 몇 개. 범위가 어긋난 리뷰는 실패하지 않고 초록으로 끝나므로, 보고만 보고도 무엇을 봤는지 알 수 있어야 한다.

### 6. 반영

보고로 끝내지 않는다. 주 용도가 커밋 전 셀프 리뷰이고 다음 단계가 커밋이므로, 그 사이가 여기다. 심각도의 원천은 `CODING_STANDARDS.md`다.

1. **고친다.** 문서화된 표준 위반, 명세의 누락·부분 구현, 요청하지 않은 범위 추가는 고친다. Critical·Major는 커밋 전에 고친다. 건너뛰지 않는다. 고치며 새로 쓰는 사실 문장은 그 근거(일지, 코드, `gh`, 상류 소스)를 끝까지 열고 쓴다. 근거를 끝까지 열지 않고 쓴 새 문장이 두 번 틀렸고, 두 번 모두 다른 리뷰가 잡았다(대기열 154). 지적이 문서·지침의 닫힌 주장이나 목록(수로 센 기준, 이름을 나열한 자리, '~은 ~가 아니다' 같은 보편 주장 등)의 반례이면 그 반례만 덧붙이지 않는다. 그 목록이 거르려는 성질을 일반 조항으로 적고 목록은 그 조항의 예시로 둔다. retro 넘김 목록에 표준 축이 낸 첫 반례를 덧붙이기만 하자, PR 직전 `bug-perf-review`와 PR 봇 claude-review가 차례로 같은 목록의 새 반례를 냈다(대기열 213). 반영으로 새로 쓴 사실 문장은 PR 직전 `bug-perf-review`(`docs/constitution/operations.md` 리뷰 파이프라인 2)의 브리프에 밀 주장으로 나열해, 다음 층이 그 문장을 겨냥하게 한다. CLI가 도는 PR에는 아직 넘기는 길이 없다. `coderabbit-review`가 부르는 명령에는 주장을 넘기는 인자가 없다. 나열할 문장은 일지의 고친 것 줄에 원문으로 옮겨, 컨텍스트 압축 뒤에도 목록이 남게 한다. 근거를 끝까지 열었는지는 검사로 판정할 수 없고, 154의 "끝까지 열고 쓴다" 지침 뒤에도 셀프 리뷰 지적을 고치며 새로 쓴 문장이 두 번 다시 어긋나 PR 직전 리뷰가 잡았다(대기열 260).
2. **근거를 먼저 본다.** 지적이 불분명하거나 기술적으로 맞지 않아 보이면 그대로 구현하지 않는다. 코드와 명세에서 근거를 확인한 뒤 수정 여부를 정한다. 서브에이전트 둘은 격리된 컨텍스트에서 diff와 표준 문서만 봤고 ADR도 주변 코드도 모른다. 특히 smell baseline은 스스로 judgement call이라고 말하는 휴리스틱이라, 서드파티를 경계에서 감싸는 층(`CODING_STANDARDS.md`)이 Middle Man으로, 플러그인 자리 셋(커넥터·변환·파서, ADR 0003)의 인터페이스가 Speculative Generality로 보인다. 오탐을 그대로 고치면 수정이 원칙을 깬다. 봇의 초록을 믿지 않는 것과 같은 이유로 봇의 빨강도 그대로 믿지 않는다(`docs/constitution/operations.md` 리뷰 파이프라인). PR 직전 축의 트리아지에 대응하는 것이 이 단계다. 지적을 쓰는 쪽(부르는 쪽)이나 다른 층의 몫으로 보고 보류하려면 그 책임을 정한 표준이나 계약(MCP 표준이나 WAI-ARIA 같은 명세, ADR, 인터페이스의 독스트링)을 근거로 든다. 들 수 없으면 고친다. agent-os에서 근거 없이 쓰는 쪽의 몫으로 둔 `aria-valuenow` 범위를 PR 봇이 다시 냈는데, WAI-ARIA 1.2는 범위 밖의 값을 무효로 정해 두어 그 속성을 다는 컴포넌트의 몫이었다(`https://www.w3.org/TR/wai-aria-1.2/#aria-valuenow`, 대기열 151).
3. **먼저 묻는다.** 수정 방법이 아키텍처 결정이거나 계약(검색 도구의 형식, 수집 API, 커넥터·변환·파서 인터페이스, 색인 형식, 헌법. 원칙 VII)에 닿으면 고치기 전에 사용자 판단을 받고, ADR이 필요한지 같이 묻는다(`CLAUDE.md` 작업 규약 5).
4. **남긴다.** Minor·Nit과 근거를 보고 보류한 지적은 별도 티켓이나 회고 후보로 빼고 이유를 한 줄 남긴다. 판단 항목만으로 커밋을 막지 않는다. 다른 층이나 다음 티켓에 넘기는 것("HTTP 층에서 재확인")은 2의 책임 근거를 들어 **받는 쪽**(그 티켓의 수용 기준, 그 기능의 기능 계획 `.scratch/<slug>/plan.md` 본문)에 적고, 받는 쪽의 Blocked by가 넘기는 쪽을 포함하는지 본다 — 미루는 쪽은 적지만 받는 쪽이 읽는다는 보장이 없고, 받는 쪽이 먼저 돌 수 있다(대기열 3, 세 번).
5. **다시 돌린다.** 고쳤으면 `CLAUDE.md`의 검증 명령을 모두 다시 돌린다. 다음이 커밋이면 그중 손으로 치는 다섯(테스트, 린트, 포맷 검사, 타입체크, import 경계)은 커밋이 부르는 pre-commit의 결과로 갈음한다. pre-commit이 같은 명령을 돌린다(무엇이 갈음되는지는 `CLAUDE.md` 검증 명령 절, 대기열 180). 전체 리뷰는 다시 돌리지 않는다.

보고 끝에 세 줄을 더한다. 고친 것, 남긴 것과 이유, 다시 돌린 명령과 결과(pre-commit으로 갈음하면 그렇게 적고, 결과는 커밋 뒤 일지와 PR 본문에 적는다).

자기 작업을 리뷰해 일지를 쓰는 세션이면, 보고는 받은 턴에 일지에 옮긴다. 세 줄 가운데 고친 것과 남긴 것은 지적마다 판정한 턴에, 다시 돌린 명령의 결과는 그 명령이 끝난 턴에 옮긴다(pre-commit으로 갈음하면 위 괄호대로 커밋 뒤에). PR 직전 리뷰(`docs/constitution/operations.md` 리뷰 파이프라인 2)의 보고와 반영도 같다. 일지 파일이 아직 없으면 `docs/journal/<날짜>-<HHMM>-<슬러그>.md`를 머리 한 줄 파일로 먼저 만든다. 앞부분은 Bash의 `date +%Y-%m-%d-%H%M`이나 PowerShell의 `Get-Date -Format yyyy-MM-dd-HHmm`으로 짓는다(`next-session` `merge.md` 3의 이름 규칙과 같은 길이다). 옮기기를 미룬 세션은 컨텍스트 압축 뒤 요약에 요지만 남아, PR 직전 리뷰 절을 쓰느라 서브에이전트 보고를 트랜스크립트에서 스크립트 둘로 네 번 뒤졌다(대기열 244).

## Why two axes

A change can pass one axis and fail the other:

- Code that follows every standard but implements the wrong thing → **Standards pass, Spec fail.**
- Code that does exactly what the issue asked but breaks the project's conventions → **Spec pass, Standards fail.**

Reporting them separately stops one axis from masking the other.
