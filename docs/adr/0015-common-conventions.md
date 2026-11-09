---
status: accepted
date: 2026-11-09
---

# 공통 규약: UUIDv7 식별자, RFC 9457 에러 봉투, UTC 시각, REST 경로 접두, pydantic-settings, JSON Lines 로그, 계약의 `format_version`

첫 기능 전에 정하는 규약 일곱이다. 하나씩은 작지만 데이터베이스 열과 계약 형식에 박혀 되돌리기 어렵고, 저장소마다 다르게 하는 자리라 적어 둔다.

- **식별자**는 UUIDv7이고 파이썬에서 만든다(uuid6 MIT 또는 uuid-utils BSD, py.typed를 보고 명세가 하나를 고른다). PostgreSQL 열은 `uuid`다. PostgreSQL 18의 `uuidv7()`는 쓰지 않아 식별자 생성이 데이터베이스 판과 무관하다.
- **에러 봉투**는 RFC 9457 Problem Details에 우리 `code` 칸을 더한 모양이다. FastAPI의 422도 같은 모양으로 바꾸고, MCP 도구 오류도 같은 `code`를 쓴다.
- **시각**은 UTC `timestamptz`로 저장하고 ISO 8601 `Z`로 낸다.
- **REST 경로**는 `/api/v1/admin/…`(관리 API)와 `/api/v1/ingest/…`(수집 API)이고, `/health`와 `/mcp`는 접두 밖이다.
- **설정**은 pydantic-settings로 환경 변수 `RAG_*`, `.env`, 비밀 파일을 읽는다.
- **로그**는 표준 라이브러리 logging에 우리 포매터를 붙여 JSON Lines를 stdout으로 낸다. 필드는 `time`(UTC), `level`, `logger`, `event`, `request_id`, `duration_ms`이고 예외는 스택을 필드로 싣는다. `RAG_LOG_FORMAT=text`가 사람용 모드다. 무엇을 남기지 않는지는 원칙 V와 ADR 0004다.
- **검색 도구 형식의 판**(원칙 VII)은 결과 객체의 `format_version` 칸(semver 문자열)이고, 형식은 MCP 도구 목록의 outputSchema로 공개하며, 도구 이름은 고정한다. 칸 추가는 minor, 칸 삭제와 뜻 변경은 major이고, MCP 클라이언트로 접속하는 계약 시험이 판과 스키마를 판정한다. SDK 2.3.0이 outputSchema를 싣고 structuredContent를 돌려주는 것은 프로브 `mcp-sdk/probe_sdk.py` 3절에서 확인했다(프로토콜 2026-07-28).

## Considered Options

- PostgreSQL `uuidv7()`: 18 전용이라 생성이 데이터베이스에 묶인다. 설치가 동봉 18 하나뿐이라(ADR 0002 이력) 가능했지만 파이썬 생성이 테스트와 작업자에서 더 단순하다.
- 자체 에러 모양: 클라이언트마다 파서를 또 쓰게 한다.
- 도구 이름에 판(`search_v1`, `search_v2` 나란히): 옛 클라이언트가 한동안 살지만 도구 목록이 늘고 두 판을 함께 유지해야 한다.
- 서버 수준 판 하나(`/health`와 instructions에만): 결과만 받은 쪽이 판을 모르고 도구마다 판을 따로 올릴 수 없다.

## Consequences

- 계약 시험(`tests/contract/`)이 `format_version`과 outputSchema를 본다.
- 422를 Problem Details로 바꾸는 예외 처리기와 로그 포매터는 server와 worker가 공유하는 모듈이다.
- `request_id`는 REST와 MCP 요청마다 만들고 작업에 넘겨 작업자 로그까지 잇는다.
