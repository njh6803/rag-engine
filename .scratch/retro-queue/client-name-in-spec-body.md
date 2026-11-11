# client-name-in-spec-body: 명세 본문에 특정 MCP 클라이언트(agent-os)의 이름과 그 가짜 서버의 계획을 적어 셀프 리뷰가 원칙 III로 잡았다

**상태:** 열림
**어디로:** `tools/check_glossary_avoid.py`(대기열 glossary-avoid-check가 처방한 검사. 다섯 번째면 그 낱말 목록에 `agent-os`를 더해 `.scratch/*/spec.md`와 `docs/adr/`의 산문에서 경고한다. 코드 스팬과 `>` 인용 줄은 뺀다. 지침은 `docs/constitution/principles.md` 원칙 III가 이미 있다)
**승인:** 자체 승인 2026-11-11, 1회차(이미 있는 지침을 어긴 사건이라 회차를 센다. 더하는 것이라 다섯 번째에 반영한다), 일지 2026-11-11-0929-core-get-document-text-window.md, ADR 불필요

core 명세의 `[사용자 선택]` 항목(전문 창)과 머리의 근거 줄에 agent-os의 base-agent 명세가 넘긴 물음이라는 출처와 agent-os의 가짜 검색 서버가 이 모양을 따른다는 계획을 적었다. 표준 축 Nit이 특정 클라이언트의 이름과 계획을 계약의 본문에 적은 것으로 잡았고, 반영에서 한 MCP 클라이언트 쪽이 정리한 것으로 바꾸고 계획 문장을 뺐다. 두 자리의 산문에 그 낱말은 지금 0건이라 거짓 양성이 없다. 근거로 드는 문서의 이름(Claude Code 공식 문서)을 낱말 목록에 넣을지는 판정이 필요하다. PR #12의 claude-review가 그 면제는 원칙 III의 문구에서 나오지 않는다고 했고, 그 PR은 인용을 명세에서 일지로 옮겼다. 같은 모양의 검사라 glossary-avoid-check를 반영할 때 함께 묶는다.
