# triage-dismissed-crossing: 두 기능이 함께 끝나는 경우를 짚은 PR 직전 리뷰의 지적을 계획에 이미 적혀 있다며 오탐으로 닫았다가 PR 봇이 같은 자리를 다시 냈다

**상태:** 열림
**어디로:** `.claude/agents/coderabbit-review.md`와 `.claude/agents/bug-perf-review.md`의 트리아지 기준, `.claude/skills/code-review/SKILL.md` 6단계 2(지적이 두 일의 차례나 겹침을 짚으면, 이미 적혀 있다는 이유로 닫기 전에 지적이 든 경우를 그 글이 시키는 대로 한 번 밟아 빠지는 일이 없는지 본다)
**승인:** 자체 승인 2026-11-26, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-26-1534-admin-design.md, ADR 불필요

admin 설계 PR(#125)의 PR 직전 리뷰에서 CodeRabbit CLI가 backup-upgrade 계획의 넘김 문단을 Major로 짚었다. admin과 backup-upgrade는 나란히 가고 뒤에 끝나는 쪽이 백업 안내와 시험을 맞춘다는 문단이다. 서브에이전트는 양쪽 계획이 그 규칙을 이미 적는다며 오탐으로 트리아지했고 본 세션도 따랐다. PR 봇(CodeRabbit 첫 회차)이 admin 계획의 같은 규칙을 Minor로 다시 냈다. 두 기능의 마지막 티켓이 서로 병합되기 전에 함께 끝나면 어느 쪽도 자기가 뒤라고 보지 않아 맞추는 일이 빠진다는 것이다. 규칙에는 어느 쪽이 뒤인지를 가르는 기준이 없었다. 지적이 든 경우를 한 번 밟았으면 보였을 틈이다.

닫은 지적을 PR 봇이 다시 낸 꼴은 대기열 triage-write-path-without-repro와 같다. 그 항목은 파일을 옮겨 쓰는 경로의 재현을 처방하고, 이 항목은 문서가 정한 차례 규칙에서 지적이 든 경우를 밟는 것을 처방한다. 반영할 때 두 항목을 함께 본다.
