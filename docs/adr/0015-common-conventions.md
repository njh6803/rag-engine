---
status: accepted
date: 2026-11-09
---

# 공통 규약: UUIDv7 식별자, RFC 9457 에러 봉투, UTC 시각, REST 경로 접두, pydantic-settings, JSON Lines 로그, 계약의 `format_version`

첫 기능 전에 정하는 규약 일곱이다. 하나씩은 작지만 데이터베이스 열과 계약 형식에 박혀 되돌리기 어렵고, 저장소마다 다르게 하는 자리라 적어 둔다.

- **식별자**는 UUIDv7이고 파이썬에서 만든다(uuid6 MIT 또는 uuid-utils BSD, py.typed를 보고 명세가 하나를 고른다). PostgreSQL 열은 `uuid`다. PostgreSQL 18의 `uuidv7()`는 쓰지 않아 식별자 생성이 데이터베이스 판과 무관하다.
- **에러 봉투**는 RFC 9457 Problem Details에 우리 `code` 칸을 더한 모양이다. FastAPI의 422도 같은 모양으로 바꾸고, MCP 도구 오류도 같은 `code`를 쓴다. 어느 오류든 `detail`에 질문 내용이나 문서 내용을 넣지 않는다(원칙 V. 응답 본문의 규칙이고, 로그에 무엇을 싣는지는 아래 로그 항목이다).
- **시각**은 UTC `timestamptz`로 저장하고 ISO 8601 `Z`로 낸다.
- **REST 경로**는 `/api/v1/admin/…`(관리 API)와 `/api/v1/ingest/…`(수집 API)이고, `/health`와 `/mcp`는 접두 밖이다.
- **설정**은 pydantic-settings로 환경 변수 `RAG_*`, `.env`, 비밀 파일을 읽는다.
- **로그**는 표준 라이브러리 logging에 우리 포매터를 붙여 JSON Lines를 stdout으로 낸다. 필드는 `time`(UTC), `level`, `logger`, `event`, `request_id`, `duration_ms`이고 예외는 스택을 필드로 싣는다. 그 필드에 싣는 것은 예외의 타입과 프레임(파일, 줄, 함수)과 이 저장소가 정의한 예외의 메시지뿐이고, 서드파티 예외의 메시지는 싣지 않는다. 서드파티 예외의 메시지에는 입력 값이 실릴 수 있기 때문이다. SQLAlchemy의 `StatementError`는 메시지에 SQL과 바인딩 값을 붙이고(ADR 0011이 엔진을 `hide_parameters=True`로 만들어 값을 가린다), 그 바인딩 값에는 조각 본문과 검색 질의가 든다. 어댑터가 서드파티 예외를 이 저장소의 예외로 바꿀 때도 메시지를 옮기지 않는다. `RAG_LOG_FORMAT=text`가 사람용 모드다. 무엇을 남기지 않는지는 원칙 V와 ADR 0004다.
- **검색 도구 형식의 판**(원칙 VII)은 결과 객체의 `format_version` 칸(semver 문자열)이고, 형식은 MCP 도구 목록의 outputSchema로 공개하며, 도구 이름은 고정한다. 칸 추가는 minor, 칸 삭제와 뜻 변경은 major이고, MCP 클라이언트로 접속하는 계약 시험이 판과 스키마를 판정한다(바뀜: 이력 2026-11-12 "검색 도구의 입력 인자를 더하는 것도 minor로 올린다"). SDK 2.3.0이 outputSchema를 싣고 structuredContent를 돌려주는 것은 프로브 `mcp-sdk/probe_sdk.py` 3절에서 확인했다(프로토콜 2026-07-28).

## Considered Options

- PostgreSQL `uuidv7()`: 18 전용이라 생성이 데이터베이스에 묶인다. 설치가 동봉 18 하나뿐이라(ADR 0002 이력) 가능했지만 파이썬 생성이 테스트와 작업자에서 더 단순하다.
- 자체 에러 모양: 클라이언트마다 파서를 또 쓰게 한다.
- 도구 이름에 판(`search_v1`, `search_v2` 나란히): 옛 클라이언트가 한동안 살지만 도구 목록이 늘고 두 판을 함께 유지해야 한다.
- 서버 수준 판 하나(`/health`와 instructions에만): 결과만 받은 쪽이 판을 모르고 도구마다 판을 따로 올릴 수 없다.

## Consequences

- 계약 시험(`tests/contract/`)이 `format_version`과 outputSchema를 본다.
- 422를 Problem Details로 바꾸는 예외 처리기와 로그 포매터는 server와 worker가 공유하는 모듈이다.
- `request_id`는 REST와 MCP 요청마다 만들고 작업에 넘겨 작업자 로그까지 잇는다.

## 이력

### 2026-11-12 검색 도구의 입력 인자를 더하는 것도 minor로 올린다

본문은 결과 객체의 칸만 말했다. 검색 도구의 입력도 같은 `format_version`으로 센다. 선택 인자를 더하면 minor를 올리고, 필수 인자를 더하거나 인자를 지우거나 인자의 뜻을 바꾸면 major를 올린다. 입력 인자를 처음 더하는 티켓이 계약 시험에 도구 목록의 inputSchema를 보는 시험을 더한다. 지금 계약 시험은 inputSchema를 보지 않는다(손으로 봤다. `tests/`를 `inputSchema`와 `input_schema`로 grep해 0건이었다).

까닭은 옛 서버가 모르는 인자를 조용히 버리기 때문이다. mcp 2.3.0의 도구는 선언하지 않은 인자를 받아도 `isError`가 거짓인 정상 결과를 내고 값을 버린다. 최상위 인자와 중첩 모델 안의 키가 모두 그랬고, SDK 클라이언트의 요청과 raw HTTP 요청이 같았으며, inputSchema에는 `additionalProperties`가 실리지 않았다(쟀다. 프로브 `.scratch/search-eval/probes/mcp-args/probe_unknown_args.py`). 그래서 새 인자를 보낸 클라이언트는 응답의 모양만으로는 그 인자가 적용됐는지 알 수 없고, 결과의 `format_version`이나 도구 목록의 inputSchema를 보고 가려야 한다. 인자를 더하면서 판을 올리지 않으면 결과에서는 가릴 길이 없고 도구 목록의 inputSchema만 남는다.

모르는 인자를 버리는 지금 동작은 그대로 둔다. 거부로 바꾸면 여분의 인자를 보내던 클라이언트가 깨지므로 그것은 뜻 변경이고 major의 일이다. 원칙 VII의 "칸을 더하는 것은 같은 판에서"는 본문이 major 안의 minor로 읽었고 이 이력도 그 안이다. 첫 적용은 최소 점수 인자(ADR 0017)이고, 그 인자가 구현되는 커밋에서 `1.0.0`이 `1.1.0`이 된다. 사용자가 2026-11-12 search-eval 설계 인터뷰에서 골랐다(`docs/journal/2026-11-12-2108-search-eval-design.md`).
