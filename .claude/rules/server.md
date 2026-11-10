---
paths:
  - "src/rag_engine/server/**"
---

# HTTP 표면 규칙

원천은 ADR 0005(REST와 MCP를 한 FastAPI 앱이 연다)와 ADR 0001(MCP로는 읽기 도구만), 그리고 `tests/contract/`의 계약 시험이다. 코드와 다르면 코드를 고치거나 ADR을 남긴다. 층의 import 경계는 `pyproject.toml`의 import-linter 계약이 판정한다.

- MCP 하위 앱(`MCPServer.streamable_http_app()`)은 자기 안에 `/mcp` 경로를 두므로 `"/"`에 마운트하고, REST 경로를 모두 더한 뒤 마지막에 마운트한다. `"/"` 마운트는 모든 경로를 받는다.
- 마운트한 하위 앱의 lifespan은 돌지 않는다. 최상위 FastAPI의 lifespan이 `session_manager.run()`을 연다(ADR 0005 결과).
- `transport_security`를 주지 않으면 MCP는 localhost Host만 받는다. `create_app`이 `RAG_ALLOWED_HOSTS`와 늘 받는 `localhost`·`127.0.0.1`을 `값`과 `값:*` 두 꼴로 펼쳐 넘긴다. SDK의 `host:*`는 포트가 붙은 Host만 받아 기본 포트의 `Host: host`가 421이 되기 때문이다(ADR 0014).
- `create_app`이 FastAPI 앱 바깥에 순수 ASGI 미들웨어 둘을 씌운다. 가장 바깥이 요청 문맥(요청 ID, `X-Request-Id`, `http_request` 로그, 처리하지 못한 예외의 500 Problem), 그 안쪽이 인증(`/health`만 면제, 토큰 없음·틀림은 401, `reader`가 `/mcp` 밖을 부르면 403)이다. `BaseHTTPMiddleware`로 바꾸지 않는다. 스트리밍 응답과 예외 전파가 달라진다.
- 로그에 남기는 경로는 라우트 템플릿(`/api/v1/admin/tokens/{token_id}`)이다. 실제 값과 쿼리 문자열을 싣지 않는다. FastAPI는 `include_router`한 라우터를 `app.routes`에 펼치지 않으므로, 새 라우터를 더하면 `create_app`이 요청 문맥 미들웨어에 넘기는 라우트 목록에도 그 라우터의 `routes`를 더한다.
- MCP로 여는 도구는 읽기 도구뿐이고, 계약 시험이 도구마다 읽기 전용 표지(`read_only_hint`)를 본다. 그 표지는 보안 장치가 아니라 계약의 표시다. 쓰기는 관리 API와 수집 API로 연다(ADR 0001).
