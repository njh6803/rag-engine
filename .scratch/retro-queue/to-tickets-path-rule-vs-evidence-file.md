# to-tickets-path-rule-vs-evidence-file: to-tickets도 구현 파일의 경로를 적지 말라고 해 티켓에서 코드를 읽은 근거 파일을 적을 자리가 없고, spec-reviewer는 Further Notes를 열어 둔 결정의 자리로 읽는다

**상태:** 열림
**어디로:** `.claude/skills/to-tickets/SKILL.md`(구현 파일의 경로를 적지 않는다는 문장에, 코드를 읽었다고 적은 사실의 근거 파일은 예외라는 갈래를 단다)와 `.claude/agents/spec-reviewer.md`(Further Notes를 명세가 정하지 않고 둔 것의 자리로 읽는 문장에, 코드를 읽은 근거 파일 목록도 그 자리에 든다는 말을 단다). 근거 규칙의 원천은 `docs/agents/issue-tracker.md`의 프로브와 근거 절이다
**승인:** 자체 승인 2026-11-26, 18회차(`to-spec-path-rule-vs-evidence-citation`의 18회차. 두 지침이 어긋나는 자리를 고치는 것이라 사건 하나로 반영한다. 이 사건이 난 PR은 그 어긋남을 `to-spec` 쪽만 풀었고, `.claude/` 아래를 더 고치면 전체 시험을 한 번 더 통과해야 해서 그 PR에는 싣지 않았다), 일지 2026-11-25-1635-claim-evidence-rule-in-issue-tracker.md, ADR 불필요

`claim-evidence-rule-in-issue-tracker` PR의 PR 직전 리뷰(`bug-perf-review`)가 Minor로 냈다. 새 규칙은 코드를 읽었다고 적은 사실의 근거 파일을 명세의 Further Notes에 모으게 하는데, `to-tickets`는 같은 꼴로 명세가 고칠 자리로 정하지 않은 구현 파일의 경로를 티켓에 적지 않게 한다. 티켓에 코드를 읽었다는 근거를 적는 세션은 파일을 빼면 새 규칙을, 적으면 `to-tickets`를 어긴다. `spec-reviewer`는 Further Notes를 명세가 정하지 않고 둔 것의 자리로 읽어, 근거 파일 목록이 들어가면 두 용도가 섞인다.

반영할 때 두 문장을 같이 본다.
