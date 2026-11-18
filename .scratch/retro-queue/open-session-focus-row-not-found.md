# open-session-focus-row-not-found: 새 세션을 연 뒤 `open_session.ps1 -Action focus`가 두 번(90초, 60초) 사이드바에서 그 세션의 제목 행을 찾지 못했다

**상태:** 열림
**어디로:** `tools/open_session.ps1`의 `focus`(사이드바 행을 찾는 길). 원인을 먼저 가른다. 도구의 결함이면 고침이라 사건 하나로 반영한다
**승인:** 자체 승인 2026-11-18, 1회차(고침인지 아직 가르지 못해 대기열에 둔다), 일지 2026-11-18-1444-glossary-release-names.md, ADR 불필요

release-image 명세 세션(`docs/release-image-spec`)을 열 때 `send`와 `split`은 됐고 `focus`만 두 번 제한 시간을 넘겼다. 그사이 `list_sessions`에는 그 제목의 세션이 도는 중으로 있었다(새 세션이 스스로 이름을 붙였다). 그래서 이름이 늦게 붙은 것이 아니라 사이드바 행을 찾는 길이 그 행을 보지 못한 것으로 보인다(어림이다). 같은 스크립트가 모델 메뉴에서 바뀐 이름을 찾지 못한 일은 대기열 model-menu-name-drift가 따로 센다.
