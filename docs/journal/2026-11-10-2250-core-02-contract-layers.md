# core 02 계약 티켓 일지 · 2026-11-10

티켓 `.scratch/core/issues/02-contract-layers-ports-schema.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/02-contract-layers-ports-schema`다. 지시문의 이번 요청 범위는 PR과 병합까지다. 읽은 것, 정한 것, 손으로 본 것, 사용자가 승인한 것, 리뷰, 검증, 남긴 것, 다음을 차례로 둔다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 명세(`.scratch/core/spec.md`)의 데이터 모델과 스키마·포트·오류 코드·MCP 출력·수집 API 절, ADR 0006~0015, `docs/agents/issue-tracker.md`, 직전 일지(`2026-11-10-2047-core-01-test-db-runner.md`)의 "다음", `tools/mutate.py` 독스트링.
- 작업 폴더는 `C:\project\rag-engine`이었고 이 체크아웃에서 브랜치를 땄다. 티켓은 첫 편집으로 `in-progress`로 바꿨다.
- 의존성을 런타임으로 올렸다: SQLAlchemy(asyncio), alembic, psycopg(dev에서 이동), pgvector, uuid6, pydantic. 설치된 판은 명세와 ADR 0011이 근거로 든 프로브의 판과 모두 같은 major·minor였다(`uv.lock`과 `pyproject.toml` 주석에 적었다).
- **greenlet 휠(수용 기준 8).** Windows에서 `uv sync`가 SQLAlchemy asyncio의 greenlet을 휠로 설치했고 빌드 도구 없이 끝났다. Linux 쪽은 CI의 `verify`가 판정한다.

## 정한 것

- **`server`가 패키지가 되었다.** `server.py`를 `server/app.py`로 옮기고(내용 그대로) `server/__init__.py`가 `create_app`을 내보낸다. `main.py`와 기존 계약 시험(`tests/contract/test_mcp_tools.py`)은 `from rag_engine.server import create_app`을 그대로 쓰고 고치지 않았다.
- **오류 코드는 한 `ErrorCode`에 든다.** 작업 코드 열넷, HTTP 코드, 도구 코드 다섯, `invalid_argument`를 한 enum에 두고 집합 상수(`JOB_ERROR_CODES`, `PROBLEM_ERROR_CODES`, `TOOL_ERROR_CODES`, `PERMANENT_FAILURE_CODES`, `TRANSIENT_FAILURE_CODES`)로 가른다. `internal_error`는 작업 코드와 Problem Details 코드가 함께 쓴다. 예외마다 자기 갈래가 아닌 코드를 받으면 `ValueError`를 낸다.
- **`invalid_argument`는 422다.** 도구 입력의 검증 실패이고 REST의 `validation_error`와 같은 상태로 맞췄다. `search_unavailable`은 503이다.
- **`effective_date`는 `date | None`이다.** 갱신일이 아니라 문서에 적힌 효력일이라 시각이 필요 없다.
- **`jobs.request_id`는 NOT NULL이다.** 작업이 어느 요청에서 비롯됐는지를 로그와 맞추는 열이라 비어 있을 자리가 없다.
- **수집 `updated_at`은 `AwareDatetime`이다.** 오프셋이 없는 시각은 거절한다.
- **UnitOfWork는 `commit()`이 없다.** `begin()`의 비동기 컨텍스트가 예외 없이 나가면 커밋이고 예외면 롤백이다. 한 트랜잭션을 공유하는 포트는 Catalog, DocumentStore, VectorIndex, JobQueue 넷이고 TokenStore는 밖이다(ADR 0007 이력 둘).
- **Connector와 Transform 포트는 두지 않았다.** 명세 Further Notes가 source-sync의 몫으로 정했다. 파서 인터페이스(`interface_version "1.0.0"`)만 이 티켓이 둔다.
- **차원 CHECK는 두지 않았다.** `chunks.embedding`은 차원 없는 `vector`이고 판마다의 HNSW 부분 색인은 03·14가 만든다. 시험이 서로 다른 차원(3과 5)이 한 열에 들어가는 것을 고정한다.
- **Windows 이벤트 루프.** psycopg 비동기는 Proactor 루프를 못 쓰므로 alembic `env.py`가 `asyncio.Runner(loop_factory=asyncio.SelectorEventLoop)`로 돈다. 엔진은 `hide_parameters=True`라 오류 메시지에 값이 실리지 않는다(원칙 V).
- **제약 이름은 이름 규칙이 짓는다.** `NAMING_CONVENTION`(pk_, uq_, fk_, ck_, ix_)을 `metadata`에 두고 `env.py`가 `target_metadata`로 넘긴다. `compare_metadata`로 `tables.py`와 마이그레이션의 차이가 0임을 시험이 본다.

## 손으로 본 것

- **금지 import(수용 기준 1).** 임시 파일을 만들어 세 경우를 넣고 `uv run lint-imports`가 빨개지는 것을 봤다: worker가 server를 import, domain이 adapters를 import, domain이 sqlalchemy를 import. 세 경우 모두 계약이 깨졌다고 나왔고 임시 파일은 지웠다. 되돌린 뒤 초록(계약 2 kept)이다.
- **변이(`.scratch/core/probes/contract_mutations.toml`).** 구현 뒤에 쓴 시험이라 빨강을 본 적이 없어 변이 여덟을 넣었다. 전부 기대대로 빨개졌다: 대기 작업 부분 유일 색인의 조건 바꾸기, 기본 지식베이스 유일 색인에서 유일 빼기, 벡터 열에 차원 적기, 작업 코드 이름 바꾸기, 블록 순번 하한 풀기, 도구 오류가 Problem Details 코드까지 받기, metadata 폼 칸의 JSON 풀이 건너뛰기, `format_version` 올리기.
  - 처음 표는 두 곳이 어긋났다. 표지(`expect_output`)가 시험 원문에 글자 그대로 있어 도구가 거부했고(대기열 417), 일곱째 변이는 값 검증이 `TypeAdapter`와 필드 타입 둘에 걸려 있어 어댑터만 바꿔서는 의도한 단언이 아니라 메시지 비교가 빨개졌다. 표지를 출력에만 나오는 문구로 바꾸고 일곱째는 풀이 자체를 건너뛰게 고쳐 다시 돌려 통과했다.
## 승인받은 것

ADR 0007 Consequences의 두 문장("`CLAUDE.md`는 … core의 첫 티켓이 고친다", "계약을 바꾸는 티켓은 기능의 첫 티켓이고 다른 티켓을 막는다")은 core 01이 생겨 가리키는 대상이 어긋났다. 이력과 포인터 문구를 선택 화면으로 제안했다.

> 사용자: "ADR 0007 Consequences의 두 문장에 아래 이력과 포인터를 달까요?" → "이 문구로 단다 (Recommended)" — 설명: "이력 한 건을 더하고 두 문장 뒤에 포인터를 단다. 결정은 그대로이고 '첫 티켓'이라는 낱말의 가리킴만 바로잡는다."

이력 `2026-11-10 계약 티켓은 core 02이고 core 01(테스트 DB 러너)이 그 앞에 선다`를 더하고 본문 두 문장 뒤에 포인터를 달았다. `domain-modeling` 스킬을 이 세션에서 한 번 불렀고 `GLOSSARY.md`에 더할 용어는 없었다.

## 같이 고친 문서

- `CLAUDE.md` 레이어 절을 다섯 층으로.
- `.scratch/plan-head.md` 목표 배치(`server/`, `worker/`, `adapters/`, `app/`, `domain/`)와 `uv run python tools/plan_table.py`로 만든 `.scratch/plan.md`.
- `README.md` 트리(소스와 새 시험 디렉터리).
- `.claude/rules/server.md`의 `paths`를 `src/rag_engine/server/**`로. `.claude/rules/tests.md`는 `tests/**`라 넓힐 것이 없었다.
- `.coderabbit.yaml`의 `src/rag_engine/server.py` 블록을 `src/rag_engine/server/**`로(티켓이 적지 않은 네 번째 자리를 grep으로 찾았다).
- 옛 표현 잔존: `docs/`(일지 제외), `.claude/`, `tools/`에서 `server.py`를 grep해 0건을 확인했다.

## 검증

- `uv run ruff check .`, `uv run ruff format --check .`: 초록(303개 파일).
- `uv run python tools/run_checks.py`: `check-ticket`을 뺀 모든 검사가 초록이었다(test-db, zizmor, lint-imports, check-instructions, check-type-escapes, pyright, pyright-linux, run-hooks, pytest 334초). `check-ticket`은 티켓 파일이 스테이지되지 않아 빨갰고 커밋을 만들 때 해소된다.
- 새 시험: `tests/domain`과 `tests/server` 70건, `tests/adapters` 16건(테스트 PostgreSQL에 빈 데이터베이스를 시험마다 만들고 지운다).

## 코드 리뷰

`/code-review`로 두 축(표준 Sonnet 5.5 high, 명세)을 돌렸다. 범위는 기준 SHA 87e981c 이후 변경 파일 11개(수정 10, 이름 바꿈 1)와 미추적 12묶음, 커밋 0개였다. Critical은 없었고 Major급은 명세 축의 `format_version` 선택 칸 하나였다.

고친 것:
- **`format_version`이 outputSchema의 `required`에 없었다**(명세 축, 클라이언트가 선택으로 읽는다). 세 출력 모델에서 기본값을 지워 필수로 만들었고, 도구가 `FORMAT_VERSION`을 직접 넣는다. 시험은 검증·직렬화 두 모드의 스키마에서 `required`를 본다.
- **`updated_at`이 "(UTC)"라 적었는데 `+09:00`을 그대로 냈다**(표준 축이 실행으로 확인). `UtcDatetime` 형이 UTC로 맞춰 `Z`로 나간다. 변이로 빨강을 봤다.
- **`metadata`가 `NaN`·`Infinity`·`1e999`를 받았다**(두 축). pydantic 파서가 받는 값이라 `ValidationError`를 거치지 않고 jsonb 단계에서 오류가 날 자리였다. 재귀 검사 `_is_finite`로 거절한다.
- **오류 모델이 `status`와 `code`의 짝을 보지 않았다**(두 축). `ProblemDetails(status=200, code=UNAUTHENTICATED)`가 통했다. `ERROR_STATUS`로 짝을 검증한다.
- **`SearchLocation`이 `page=0`과 `block_range=(5, 2)`를 받았다**(Nit). 검증을 더했다.
- **닫힌 주장 셋.** "서드파티는 uuid6 하나"는 계약이 열여섯 목록이라 목록 밖 서드파티는 막지 못한다. `CLAUDE.md`, `README.md`, 두 `__init__` 독스트링, import-linter 계약 이름을 고쳤다. `LockMode`의 "수집은 SHARE"는 명세 잠금 규칙대로 그룹이 바뀌어 문서가 빠지는 지식베이스는 UPDATE라고 고쳤다. `tables.py`의 "어긋나지 않는지 시험이 본다"는 `compare_type=False`라 타입·기본값·CHECK는 보지 않는다고 적었다.
- **옛 경로 잔존.** `.github/PULL_REQUEST_TEMPLATE.md`가 `server.py`를 가리켰다(내 잔존 grep은 `docs/`, `.claude/`, `tools/`만 봤다). 고쳤다.
- **실패의 까닭 미단언**(표준 지침 9). 마이그레이션 시험 일곱이 예외 클래스만 봤다. `diag.constraint_name`까지 단언한다.
- **호출 길.** `upgrade_to_head`가 실행 중인 루프 안에서 불리면 `coroutine was never awaited` 경고를 남겼다. 루프를 먼저 확인해 알린 메시지로 `RuntimeError`를 내고, `asyncio.to_thread`로 넘기는 길을 시험이 밟는다.
- **무시험 분기.** `Block`의 제목 수준 하한(`level < 1`)에 시험이 없었다. 시험과 변이를 더했다. 변이 표는 열둘이 되었고 리뷰 반영 넷도 기대대로 빨개졌다.
- 이름: `_source_and_group` → `_source`, `pg_indexes` 조회 순서를 정렬해 단언.

남긴 것과 이유:
- **포트가 열셋이 아니다**(명세 L81은 열셋, L272는 "커넥터와 변환의 Protocol은 source-sync가 만든다"). 코드는 L272를 따라 열한 개와 `Transaction`을 두었다. Transform의 메서드 모양은 ADR 0012가 명세에 맡겼고 core에 변환이 없으며 Connector 구현도 source-sync가 처음 쓴다. 티켓에 한 줄 적었다.
- **포트 메서드가 명세 흐름에 못 미친다는 지적**(검색 후보 SQL, 상태 행 삭제, 보관 조각 복원 등): 뒤 티켓이 더한다. 티켓 03이 "`documents`·`jobs`는 05가, 조각 쓰기와 검색 질의는 07이 더한다"고 이미 정했고, 포트 안의 메서드는 원칙 VII가 판을 붙이는 계약(검색 도구 형식, 수집 API, 커넥터·변환·파서 인터페이스, 색인 형식)이 아니다.
- **ERROR_STATUS의 503·500·422(`invalid_argument`)와 CHECK 제약, `ix_*_document_id`는 명세에 상태가 없다.** 근거 없는 것은 아니지만 이 티켓이 정한 것이므로 "정한 것"에 적었다. `sources.kind IN ('push')`는 source-sync가 종류를 더할 때 마이그레이션이 필요하다. 그 티켓이 어차피 마이그레이션을 쓴다.
- **ADR 0007 본문 8행** "계약을 … 고치는 일은 core의 첫 구현 티켓이 패키지를 만들 때 하고, 그때까지 계약은 킥오프의 둘 그대로다"에는 포인터를 달지 않았다. 사용자가 승인한 것은 Consequences 두 문장이고, 이 문장은 core 02로 이루어진 계획이라 글자 그대로 거짓이 되지는 않는다(확신 낮음). 사용자가 달라고 하면 이력 제목 그대로 단다.
- 냄새 판단 항목: `ErrorCode` 가드 여섯 곳의 되풀이(`ClassVar`로 모을 수 있다), `KnowledgeBase`·`IndexVersion`의 임베딩 세 칸과 `Document`·`Chunk`의 복사 칸. 이 크기에서는 값이 작고, 03 이후 쓰임이 드러난 뒤에 묶는 편이 낫다. `server/app.py`와 층 이름 `rag_engine.app`의 겹침은 층 이름이 명세·ADR이 정한 것이라 두었다.

다시 돌린 명령: `ruff format`, `ruff check .`, `pyright src tests`(0 오류), `lint-imports`(2 kept), `pytest tests/server tests/domain tests/adapters tests/contract`(96건 통과). 전체 `run_checks`는 커밋 훅이 다시 돈다.
