# harness-feature-off-plan: 하네스 기능이 전체 계획에 들지 않아, 외부 조건을 기다리는 마지막 티켓을 다시 집을 계기가 없었다

**상태:** 열림
**어디로:** `tools/plan_table.py`(`**슬라이스:**` 줄이 없는 기능 계획 가운데 done이 아닌 티켓이 남은 것을 `.scratch/plan.md`에 하네스 기능 목록으로 낸다. 그러면 `.scratch/plan-head.md`의 손 문단 "하네스 기능"을 걷는다)와 `docs/agents/issue-tracker.md` 전체 계획 절의 하네스 기능 문장
**승인:** 자체 승인 2026-11-12, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-12-1419-dev-branch-model.md, ADR 불필요

dev-branch 설계 PR의 셀프 리뷰 명세 축 Major 3. 티켓 05가 agent-os의 harness 티켓 병합을 기다리는데, 하네스 기능은 전체 계획의 표와 프론티어에 들지 않고 `next-session`은 같은 기능의 묶음만 고른다(`.claude/skills/next-session/SKILL.md` 28행). 그 PR은 `.scratch/plan-head.md`에 "하네스 기능" 문단을 손으로 두고 05를 닫는 커밋이 지우게 했다. 손 문단은 잊으면 낡은 줄이 남거나 새 하네스 기능이 빠진다. 끝 줄 규칙의 고침(대기열 harness-end-line-rule)과 대상 파일 하나가 같다. 외부 조건을 기다리는 제품 기능이 프론티어에 시작할 수 있는 기능으로 오르는 같은 뿌리의 일은 대기열 cross-repo-wait-on-frontier이고, 대상 파일 `tools/plan_table.py`가 같다.
