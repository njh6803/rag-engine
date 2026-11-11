# stale-checkout-at-session-start: 지시문 없이 연 세션이 origin/main보다 뒤처진 주 체크아웃의 명세를 읽고, 이미 병합된 결정을 사용자에게 다시 물었다

**상태:** 열림
**어디로:** `tools/hook_prompt_directive.py`(지시문 없이 연 세션의 첫 메시지에 계기를 넣는 훅. 다섯 번째면 그 훅이 `git fetch` 뒤 지금 체크아웃이 `origin/main`보다 뒤처진 커밋 수를 한 줄로 알린다)
**승인:** 자체 승인 2026-11-11, 1회차(더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-11-1534-doc-permission-list-filter.md, ADR 불필요

주 체크아웃의 main은 2026-11-11 08:46에 당긴 1ab024d였고, origin/main에는 12:27부터 14:23 사이에 PR 13·12·14·15의 커밋 넷이 들어와 있었다(`git reflog show main`, `git log origin/main`의 커밋 시각). 세션이 옛 판의 `.scratch/core/spec.md`를 읽고 `get_document`의 전문 크기, 제목 표시, 형식의 판을 사용자에게 물었는데 셋 다 PR 12가 정한 것이었다. 15:28에 다른 세션이 main을 68aa7e0으로 당긴 뒤 같은 파일의 다른 줄을 읽다가 알았다. 잃은 작업은 없고 사용자의 답 셋과 조사 비용을 썼다.
