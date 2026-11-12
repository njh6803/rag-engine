# triage-write-path-without-repro: 리뷰 지적을 파일을 옮겨 쓰는 경로인데도 재현하지 않고 "드물다"로 보류했다가 PR 봇이 같은 자리를 Major로 다시 냈다

**상태:** 열림
**어디로:** `.claude/agents/coderabbit-review.md`와 `.claude/agents/bug-perf-review.md`의 트리아지 기준(지적이 파일을 지우거나 옮겨 쓰는 경로를 짚으면 보류하기 전에 임시 저장소에서 재현한다. 반박 시험의 기준은 `.claude/rules/tools.md`의 지우거나 덮어쓰는 도구 항목)
**승인:** 자체 승인 2026-11-12, 1회차(더하는 것이라 다섯 번째 전이거나 손상이 나기 전에는 회차만 센다), 일지 2026-11-12-1914-dev-base-tools.md, ADR 불필요

`dev-base-tools`(PR #26)의 PR 직전 리뷰에서 CodeRabbit CLI가 `tools/sibling_overlap.py`의 `inherited` 분기를 짚었다. 서브에이전트는 그 지적을 "드물다, 시험은 만들어 보지 않았다"며 보류로 트리아지했고, 본 세션도 재현하지 않고 따랐다. PR 봇(CodeRabbit 첫 회차)이 같은 자리를 Major로 다시 냈다. 임시 저장소로 재현하자 `--move`가 `main`에서 물려받은 공유 ADR 0002까지 새 번호로 옮기려 했다. 이 경로는 파일 이름과 인용을 쓰는 도구라 `.claude/rules/tools.md`가 커밋 전에 반박하라고 한 종류다.
