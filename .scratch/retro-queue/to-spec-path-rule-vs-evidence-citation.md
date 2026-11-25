# to-spec-path-rule-vs-evidence-citation: to-spec은 명세에 구현 파일의 경로를 적지 말라고 하고 issue-tracker는 코드를 읽은 근거에 파일과 판을 적으라고 해, 파일 없는 "코드를 읽었다"가 셀프 리뷰에 걸렸다

**상태:** 닫힘 (.scratch/harness/issues/claim-evidence-rule-in-issue-tracker.md, 2026-11-25, `.claude/skills/to-spec/SKILL.md` Implementation Decisions의 경로 문장에 코드를 읽었다고 적은 사실의 근거 파일은 Further Notes에 읽은 커밋과 함께 모아 적는다는 말을 달았고, 같은 말을 규칙의 원천인 `docs/agents/issue-tracker.md` 프로브와 근거 절에도 글머리로 더했다. 짝 항목 `measured-claim-outside-to-spec`과 한 티켓에서 함께 반영했다)
**어디로:** `.claude/skills/to-spec/SKILL.md`(경로를 적지 않는다는 문장에, 코드를 읽었다고 적은 사실의 근거가 된 파일은 Further Notes에 읽은 커밋과 함께 모아 적는다는 갈래를 단다. 근거 규칙은 `docs/agents/issue-tracker.md`의 프로브와 근거 절)
**승인:** 자체 승인 2026-11-21, 17회차(`measured-claim-beyond-probe`의 17회차. 두 지침이 어긋나는 자리를 고치는 것이라 사건 하나로 반영한다. 사건이 난 PR은 명세만 담아 그 PR에는 싣지 않았다), 일지 2026-11-21-1358-source-sync-spec.md, ADR 불필요

source-sync 명세는 머리에 구현 파일의 경로를 적지 않는다고 적고 본문에서 "코드를 읽었다"를 파일과 판 없이 썼다. 셀프 리뷰 표준 축이 Major로 냈고, 근거가 된 파일만 Further Notes에 읽은 커밋과 함께 모아 적는 것으로 풀었다. 앞선 명세 둘(release-image, search-eval)도 근거로 읽은 파일의 경로를 적었다.

같은 닫힌 항목(measured-claim-beyond-probe)의 18회차는 처방을 `to-spec` 밖으로 넓히는 일이라 `measured-claim-outside-to-spec`이 센다. 반영할 때 두 항목을 함께 본다.
