# 04: 앱 조립, 토큰 인증, Problem Details, 요청 ID와 로그

**What to build:** 서버가 설정 객체로 조립되고, `/health`를 뺀 모든 REST와 `/mcp`가 토큰으로 닫힌다. 운영자는 `rag-engine bootstrap-token`으로 첫 `admin` 토큰을 만들고, 관리 API로 토큰을 발급·목록·회수한다. 응답마다 요청 ID가 붙고 로그는 JSON Lines로 남으며 토큰 원문은 어디에도 남지 않는다.

**Blocked by:** 03 (`migrate`와 기본 레코드)

**Status:** ready-for-agent

- [ ] `create_app(settings)`가 엔진, 작업 단위 공장, 어댑터를 만들고 REST와 MCP 하위 앱을 붙인다(명세 "층, 패키지, 조립" 절, `.claude/rules/server.md`). 기존 시험(`tests/test_health.py`, `tests/contract/test_mcp_tools.py`)을 설정 주입으로 고치고, CI의 `image` 잡이 컨테이너를 띄울 때 필요한 환경 변수를 넘긴다. `serve`가 같은 설정으로 앱을 띄운다.
- [ ] MCP 전송 설정 둘과 허용 호스트(ADR 0014의 두 꼴)를 조립한다. `RAG_ALLOWED_HOSTS`가 비면 기동하지 않고, 허용 호스트 판정(421)은 `/mcp`에서만 한다(명세 "인증과 권한" 절).
- [ ] `TokenStore` 어댑터와 토큰 원문 형식(`rag_` 접두, 해시 저장), 역할 둘, 지식베이스 범위(`admin`에 범위를 주면 422), 만료(지난 만료 시각은 422).
- [ ] 인증 미들웨어(FastAPI 앱 바깥의 ASGI)가 REST와 `/mcp` 둘 다에서 판정한다. 없음·모름·회수는 401 `unauthenticated`, 만료는 401 `token_expired`, `reader`의 REST는 403 `forbidden`이다. 판정한 토큰 레코드를 ASGI scope에 두고 MCP 도구가 Context로 읽는다(프로브 `.scratch/core/probes/mcp-sdk/probe_scope.py`).
- [ ] `bootstrap-token [--name 이름]`이 살아 있는 `admin` 토큰이 없을 때만 발급하고, 있으면 종료 코드 1과 안내를 낸다.
- [ ] 토큰 관리 API `POST`·`GET /api/v1/admin/tokens`, `DELETE /api/v1/admin/tokens/{id}`(명세 "관리 API" 절).
- [ ] Problem Details 봉투와 422 모양(`errors`에 `input`·`ctx` 없음), 미디어 타입 `application/problem+json`(ADR 0015).
- [ ] 요청 ID는 UUIDv7이고 응답 헤더 `X-Request-Id`로 돌려주며, 들어온 `X-Request-Id`는 쓰지 않는다.
- [ ] 로그: JSON Lines 포매터(필드 여섯, `RAG_LOG_FORMAT=text`도), `http_request` 이벤트(경로 템플릿), uvicorn `access_log=False`, uvicorn과 MCP SDK 로거가 우리 포매터를 지난다(명세 "로그, 요청 ID, 지연 기록" 절).
- [ ] 시험: 스토리 30, 31(`token_expired`, 회수된 토큰의 401, 범위를 준 `admin`의 422), 32(토큰 없는 요청과 틀린 토큰이 REST와 `/mcp` 둘 다 401, 허용 호스트 밖 421), 38(응답 헤더와 그 요청의 로그), 39, `reader`의 REST 403, 살아 있는 `admin` 토큰이 있을 때 `bootstrap-token`의 종료 코드 1, 빈 `RAG_ALLOWED_HOSTS`의 기동 거부, 로그에 토큰 원문이 없음. 만료 시험은 1초 뒤에 만료하는 토큰을 발급하고 기다린다(명세 Testing Decisions의 시간 항목).
- [ ] 검사 넷이 초록이다.
