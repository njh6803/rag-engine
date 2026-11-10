---
paths:
  - "src/rag_engine/server/**"
---

# HTTP 표면 규칙

원천은 ADR 0005(REST와 MCP를 한 FastAPI 앱이 연다)와 ADR 0001(MCP로는 읽기 도구만), 그리고 `tests/contract/`의 계약 시험이다. 코드와 다르면 코드를 고치거나 ADR을 남긴다. 층의 import 경계는 `pyproject.toml`의 import-linter 계약이 판정한다.

- MCP 하위 앱(`MCPServer.streamable_http_app()`)은 자기 안에 `/mcp` 경로를 두므로 `"/"`에 마운트하고, REST 경로를 모두 더한 뒤 마지막에 마운트한다. `"/"` 마운트는 모든 경로를 받는다.
- 마운트한 하위 앱의 lifespan은 돌지 않는다. 최상위 FastAPI의 lifespan이 `session_manager.run()`을 연다(ADR 0005 결과).
- `transport_security`를 주지 않으면 MCP는 localhost Host만 받는다. 허용할 호스트를 설정으로 받는 방식은 core 설계 인터뷰가 정한다(ADR 0005 결과).
- MCP로 여는 도구는 읽기 도구뿐이고, 계약 시험이 도구마다 읽기 전용 표지(`read_only_hint`)를 본다. 그 표지는 보안 장치가 아니라 계약의 표시다. 쓰기는 관리 API와 수집 API로 연다(ADR 0001).
