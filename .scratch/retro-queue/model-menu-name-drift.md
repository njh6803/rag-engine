# model-menu-name-drift: 결정표가 적은 모델 이름이 앱의 모델 메뉴에서 바뀌자 설계·명세 지시문의 세션 열기가 멈췄다

**상태:** 열림
**어디로:** `tools/open_session.ps1`(모델 메뉴에서 이름을 찾지 못해 멈출 때 오류문에 메뉴의 라디오 항목 이름들을 싣는다)과 `.claude/skills/open-session/SKILL.md` 3단계의 모델 오류 부탁 문장(그 이름을 사람에게 옮긴다)
**승인:** 자체 승인 2026-11-13, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-13-0124-session-model-fable-5-2.md, ADR 불필요

값은 harness 티켓 `.scratch/harness/issues/session-model-fable-5-2.md`가 고쳤고, 이 항목은 이름이 다시 바뀔 때의 비용을 든다. 멈춘 열기의 오류문은 찾던 이름만 적어, 부탁을 받은 사람이 모델만 고쳐 보냈고 세션은 지시문의 `xhigh`가 아닌 `medium`으로 열렸다. 저장소의 검사와 CI는 앱의 메뉴를 보지 못하므로 처방의 자리는 그 메뉴를 읽는 스크립트다. 스크립트는 agent-os 판과 해시를 맞춰 옮긴 것이라(harness 티켓 `open-session-env-button`) 반영할 때 두 저장소의 판을 함께 정한다. 셀프 리뷰 표준 축은 같은 값이 `.claude/skills/next-session/SKILL.md`와 `.claude/skills/next-session/directive.md`의 네 곳에 흩어진 것도 짚었고, 값을 한 곳으로 모으는 것은 이 항목의 다른 처방이다.
