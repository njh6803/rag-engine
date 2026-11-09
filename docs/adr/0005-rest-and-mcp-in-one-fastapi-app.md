---
status: accepted
date: 2026-11-09
---

# REST와 MCP는 한 FastAPI 앱이 열고, MCP는 공식 SDK 2.x의 Streamable HTTP를 `/mcp`에 붙인다

임베딩 모델과 색인을 한 번 올려 여러 요청을 받는 상주 서버이므로, 관리 API와 수집 API(REST)와 MCP를 한 프로세스의 한 FastAPI 앱이 연다. MCP는 공식 파이썬 SDK `mcp`의 `MCPServer.streamable_http_app()`이 내는 ASGI 앱을 `/mcp`에 마운트하고, SDK는 major 2로 묶는다. 2026-11-09에 PyPI의 최신은 2.3.0(2026-10-02)이고 3.x는 없으며 1.x는 유지보수만 한다(서브에이전트가 PyPI JSON을 읽었다). 단독 compose에서 밖으로 여는 포트 하나를 경로로 나누는 release-image의 규칙과도 맞는다.

## Considered Options

- MCP를 별도 프로세스(또는 stdio)로 연다: 임베딩 모델과 색인을 두 번 올리거나 프로세스 사이 통신을 하나 더 두어야 한다. stdio는 설치형 서버의 원격 클라이언트를 받지 못한다.
- SDK 1.x(`<2`)에 머문다: 자료는 더 많지만 언젠가 2.x로 옮기는 비용(클래스 이름 `FastMCP`에서 `MCPServer`로 등)을 다시 치른다.

## Consequences

- 마운트한 하위 앱의 lifespan은 돌지 않으므로, 최상위 FastAPI의 lifespan이 `session_manager.run()`을 돌려야 한다. 빠뜨리면 첫 요청에서 `RuntimeError: Task group is not initialized`가 난다(SDK v2.3.0 `docs/run/asgi.md`와 `streamable_http_manager.py`를 읽었다. 돌려 보지는 않았다).
- `transport_security`를 주지 않으면 localhost Host만 받아, 실제 호스트명으로 배포하면 `421 Invalid Host header`가 난다(같은 소스를 읽었다). 허용할 호스트는 설정으로 받는다. 세부는 core 설계 인터뷰가 정한다.
- 2.x는 출시 몇 달 된 판이라 minor 판에서 API가 바뀔 수 있다(어림). 판을 올릴 때 계약 시험이 형식을 본다.
