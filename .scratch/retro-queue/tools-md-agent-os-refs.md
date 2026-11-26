# tools-md-agent-os-refs: `.claude/rules/tools.md`가 이 저장소에 없는 훅과 agent-os의 티켓 번호를 사실처럼 적어 리뷰 둘이 걸렸다

**상태:** 열림
**어디로:** `.claude/rules/tools.md`(Write·Edit 훅 목록에서 이 저장소에 `tools/hook_*.py`가 없는 훅 항목과 agent-os의 티켓 번호 인용을 걷거나 이 저장소의 이름으로 바꾼다)
**승인:** 자체 승인 2026-11-26, 1회차(고침이라 추가 기준 횟수를 보지 않고 반영한다), 일지 2026-11-26-1805-ui-design-skill-port.md, ADR 불필요

`ui-design-skill-port` 셀프 리뷰의 표준 축과 명세 축이 둘 다 짚었다. `.claude/rules/tools.md`의 Write·Edit 시간 항목은 `hook_ui_design`을 "(harness 티켓 002)"로, `hook_web_edit_check`·`hook_journal_evidence`·`hook_probe_citing_doc`을 이 저장소에 파일이 없는 채로 든다. 킥오프가 agent-os의 규칙 파일을 옮기며 남은 것이다. `ls tools/hook_web_edit_check.py tools/hook_journal_evidence.py tools/hook_probe_citing_doc.py`가 셋 모두 없다고 답했다(2026-11-26). 이 변경은 `hook_ui_design`을 처음 들여 그 줄을 사실로 만들었지만 `tools.md`를 고치지 않기로 한 티켓이라 그대로 두었다. 항목 전체를 걷는 일이라 다음 하네스 chore가 한 번에 한다.
