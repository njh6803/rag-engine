# 02: 계약: 다섯 층, 포트 열셋, 예외, 출력 모델, 파서 인터페이스, 스키마

**What to build:** core의 계약이 코드로 선다. 다섯 층과 그 경계 계약, 포트 열셋, 예외와 오류 코드, 파서 인터페이스 1.0.0, MCP 도구 셋의 출력 모델과 `format_version`, 수집 API의 모델, 색인 형식(alembic 첫 판)이다. 뒤의 core 티켓은 모두 이 위에 선다. 이 티켓이 계약 티켓이다. `docs/agents/issue-tracker.md`는 계약 티켓을 그 기능의 첫 티켓으로 두는데, 사용자가 테스트 데이터베이스 러너를 01로 골라(명세 Further Notes) 02가 되었고 01을 뺀 모든 core 티켓을 막는다.

**Blocked by:** 01 (테스트 데이터베이스 러너)

**Status:** done

- [x] 다섯 패키지 `rag_engine.main` > `rag_engine.server`·`rag_engine.worker` > `rag_engine.adapters` > `rag_engine.app` > `rag_engine.domain`이 모두 있고, `pyproject.toml`의 import-linter에 layers 계약(server와 worker는 독립 형제)과 forbidden 계약(domain·app이 서드파티 열여섯을 import하지 못한다. uuid6만 쓴다)이 있다(명세 "층, 패키지, 조립" 절). `uv run lint-imports`가 초록이고, 금지를 어기는 import를 넣으면 빨개지는 것을 손으로 한 번 보고 일지에 적는다.
- [x] 같이 고치는 문서 넷: `CLAUDE.md` 레이어 절, `.scratch/plan-head.md` 목표 배치(고친 뒤 `uv run python tools/plan_table.py`), `README.md` 트리, `server`가 패키지가 되면 `.claude/rules/server.md`의 `paths`.
- [x] ADR 0007 Consequences의 두 문장("`CLAUDE.md`는 면제 파일이 아니라 core의 첫 티켓이 고친다", "계약(포트와 인터페이스 판)을 바꾸는 티켓은 기능의 첫 티켓이고 다른 티켓을 막는다")은 core 01이 생겨 이 티켓을 가리키게 되었다. 이력이나 포인터의 문구를 사용자에게 제안하고, 승인받으면 단다(ADR은 승인 뒤에 고친다. 티켓 세션은 승인 밖이라 두었다).
- [x] `domain`에 엔티티(불변 데이터클래스, 식별자는 `uuid.UUID`), 포트 열셋의 Protocol(`UnitOfWork`의 모양은 명세 "포트 열셋과 그 값" 절. 열셋 가운데 Connector와 Transform은 명세 Further Notes가 source-sync의 몫으로 정해 만들지 않았고, `ports.py` 독스트링이 그렇게 적는다), 예외 계층(영구·일시 실패가 오류 코드를 든다)이 있다. 오류 코드는 명세의 작업 코드 열넷(`internal_error` 포함)과 HTTP·도구 코드 전부를 한 자리에서 정의하고, 뒤 티켓은 그 자리의 이름만 쓴다.
- [x] 파서 인터페이스 `interface_version` `"1.0.0"`: 받는 MIME 목록과, 바이트·MIME·한도 값 객체(`max_pages`)를 받아 블록 목록을 내는 메서드, 인터페이스 예외 둘(암호 문서, 쪽 수 초과). 블록 모양(종류 넷, 제목 수준, 쪽 번호 1부터, 순번 0부터)은 명세 데이터 모델 절이다.
- [x] `server` 층에 MCP 도구 셋의 출력 모델(pydantic)과 `format_version` 상수 `"1.0.0"`, 도구 오류 JSON 모양, 수집 API 요청·응답 모델(`action` 다섯, `job_id`는 null일 수 있음), Problem Details 모델이 있다. `location`의 뜻(명세 "청킹과 토큰 세기" 절의 근거 위치)이 모델의 설명에 든다.
- [x] alembic 첫 판이 표 열둘과 칸·제약을 만든다(명세 "데이터 모델과 스키마" 절): (원천, 키) 유일, 기본 지식베이스 부분 유일, 같은 문서의 `queued` 작업 부분 유일, (색인 판, 문서, 순번) 유일, 차원 없는 `vector` 열, `tsvector` 열과 표 전체의 GIN 하나. 판마다의 HNSW 색인은 판을 만드는 쪽(03, 14)이 만든다.
- [x] SQLAlchemy(asyncio)·alembic·psycopg를 의존성으로 들일 때 Windows 개발 기계에서 `uv sync`가 greenlet 휠을 설치하는지 보고 일지에 적는다(ADR 0011 Consequences의 마지막 항목이 첫 티켓에 맡겼다. 01이 먼저 들였으면 01의 일지를 가리킨다).
- [x] 테스트 데이터베이스에서 `alembic upgrade head`가 오르는 시험이 있다. 기존 계약 시험 `tests/contract/test_mcp_tools.py`는 그대로 초록이다(도구 구현은 07, 09).
- [x] 검사 넷이 초록이다. 원칙 II(`Any`, `cast`, `type: ignore`, `pyright: ignore` 금지)를 `tools/check_type_escapes.py`가 판정한다.
