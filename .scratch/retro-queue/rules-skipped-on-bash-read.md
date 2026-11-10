# rules-skipped-on-bash-read: ADR 파일을 Bash로 읽어 경로 규칙(`.claude/rules/adr.md`)이 실리지 않았고, 명세가 거짓으로 만든 ADR 본문의 이력을 다음 세션으로 넘기려 했다

**상태:** 열림
**어디로:** `tools/hook_rules_on_bash_read.py`(새 계기 훅). PreToolUse(Bash)에서 명령이 읽는 경로가 `.claude/rules/*.md`의 `paths`에 맞으면 그 규칙 파일을 Read로 열라고 알린다(`CLAUDE.md` 지도의 rules 줄이 Bash로 읽으면 안 실린다고 적은 틈)
**승인:** 자체 승인 2026-11-10, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-10-0118-core-spec.md, ADR 불필요

PR #3 봇 8회차에서 claude-review Minor(ADR 0013 본문과 명세의 원본 경로)를 일지 `## 다음`으로 넘기려 했다. 그 세션은 파일을 Bash(`cat`, `sed`)로 읽었고, 그래서 `docs/adr/**`에 걸린 규칙이 실리지 않았다. 셀프 리뷰 표준 축이 그 규칙의 같은 작업 요구와 어긋난다고 잡았고, 이력 초안을 보여 승인받아 같은 PR에서 고쳤다.
