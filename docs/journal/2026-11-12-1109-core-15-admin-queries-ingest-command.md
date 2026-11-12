# core 15 작업·문서 조회와 ingest 명령 일지 · 2026-11-12

티켓 `.scratch/core/issues/15-admin-queries-ingest-command.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/15-admin-queries-ingest-command`, 작업은 워크트리 `admin-queries-ingest-command`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다. 구현 도중 컨텍스트가 한 번 압축되었다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 12 일지의 다음, 명세의 관리 API·관리 명령·수집 파이프라인 절, 형제 티켓 13.
- 지시문대로 워크트리에 먼저 들어가 브랜치를 따라 세션 이름을 맞췄다. `tidy-checkouts`는 묶음의 첫 세션이 도는 몫이라 이 세션에서는 돌지 않았다.
- 테스트 PostgreSQL은 `compose.test.yml`의 컨테이너를 쓰고 명령마다 `RAG_TEST_DATABASE_URL`과 `PYTHONUTF8=1`을 내보냈다.
- 티켓을 첫 변경에서 `in-progress`로 두었다.
- 12가 넘긴 것 가운데 삭제 키의 422를 명세의 수집 API 절에 적는 일은 사용자 승인이 필요해서 이 티켓에서 건드리지 않았다.

## 정한 것

- **문서의 결과 판정을 한 자리로**(`app/document_outcome.py`의 `index_failure_code`). 문서 상태가 `failed`이거나 살아 있는 판의 색인 상태가 `failed`이면 그 오류 코드(없으면 `internal_error`)를 낸다. 수집의 `requeued` 판정(`ingest._index_failed`)과 `--wait`의 종료 코드가 같은 함수를 부른다. 관리 API의 작업 조회와 문서 조회는 이 판정을 거치지 않고 문서 상태와 판마다의 색인 상태를 그대로 낸다.
- **도메인**. `DocumentState`(받음, 파싱됨, 실패, 삭제됨), `Document.state`, `DocumentQuery`. 포트에 `DocumentStore.list_documents`, `JobQueue.list_jobs`, `JobQueue.has_active_job`을 더했다. 목록은 ID 내림차순이고 커서는 `id <` 비교다. 지움 상태는 `deleted_at IS NOT NULL`이고, 다른 상태는 `deleted_at IS NULL`과 문서 상태의 곱이다.
- **조회 유스케이스**(`app/admin_queries.py`). 작업 조회는 작업 행에 그 문서의 결과(문서 보고)와 `active_jobs_remain`을 더한다. 문서 보고는 원천·그룹 이름과 지식베이스 이름 순, 한 지식베이스 안에서는 현재 판이 건설 중인 판보다 앞인 색인 상태 목록(`IndexReport`)을 낸다. 지운 문서는 색인 상태를 내지 않는다. 없는 그룹 이름으로 거른 문서 목록은 오류가 아니라 빈 목록이다(검색의 그룹 필터와 같다).
- **기다림**(`app/await_documents.py`의 `wait_for_documents`). 넣은 문서마다 대기·실행 중 작업이 없어질 때까지 폴링하고, 끝난 문서는 `index_failure_code`로 실패를 가른다. 지워졌거나 없는 문서는 끝난 것으로 보고 실패로 세지 않는다. 잠과 시계는 호출하는 쪽이 건넨다. 제한 시간이 0 이하면 끝날 때까지 기다리고, 시간 초과로 돌아와도 그때까지 끝난 문서의 실패를 든다.
- **REST**(`server/admin_api.py`, `server/admin_models.py`). 네 경로가 `/api/v1/admin` 아래에 있다. 목록의 `limit`은 기본 50, 상한 200이고 범위 밖, 잘못된 UUID, 모르는 `status`는 422 `errors`다. 응답의 시각은 UTC `Z`로 직렬화한다. 도메인의 `JsonValue`와 pydantic의 `JsonValue`는 다른 별칭이라 메타데이터는 기존 `tool_support.METADATA`를 거쳐 옮긴다.
- **ingest 명령**(`adapters/ingest_command.py`, `main.py`의 `ingest` 하위 명령). 폴더면 지원 확장자의 파일을 재귀로 걷고 키는 폴더 기준 상대 POSIX 경로, 파일 하나면 파일 이름이 키다. 파일마다 수집 유스케이스를 직접 불러 `action<탭>키`를 표준 출력에 찍는다. 실행마다 UUIDv7 요청 ID 하나를 만들어 `request_id_var`(로그)와 넣은 작업에 쓴다. 없는 그룹은 아무 파일도 넣기 전에 가려 종료 코드 1이다. `--wait`는 작업자가 따로 떠 있어야 한다는 안내를 표준 오류에 찍고 기다리며, 실패한 문서는 `실패<탭>키<탭>코드`로 표준 오류에 낸다. 종료 코드는 0, 1(없는 경로, 없는 그룹, 거부된 파일, 색인이 실패한 문서), 2(`--timeout`이 지남)다.
- **명세에 적히지 않은 결정**(사용자 승인 없이는 명세에 적지 않으므로 PR 본문에서 묻는다). (1) 거부된 파일(`upload_too_large`, `unsupported_media_type`)은 `거부<탭>키<탭>코드`를 표준 오류에 찍고 나머지를 이어 넣으며 종료 코드 1로 끝낸다. (2) 수집할 파일이 없는 폴더는 안내만 하고 종료 코드 0이다. (3) 없는 경로는 종료 코드 1이다. (4) 목록의 `limit` 기본 50과 상한 200.
- **로그와 표준 출력**. 로그 핸들러는 설계상 표준 출력에 쓴다(서버와 공유). 그래서 이 명령의 로그 줄(드물게 `orphan_blob_left` 경고)이 동작 줄과 같은 스트림에 섞일 수 있다. 시험은 같은 프로세스의 스텁 서버 로그가 섞이는 것을 보고서야 알았고, 동작 줄은 탭이 든 줄만 읽도록 했다.

## 손으로 본 것

- 어댑터, 유스케이스, HTTP 시험은 포트 메서드나 모듈이 없어 빨간 것을 먼저 본 뒤 구현했다. 기다림과 명령 시험 몇은 쓰는 시점에 구현이 있었다.
- 시험 개수: `tests/adapters/test_admin_list_queries.py` 6, `tests/app/test_admin_queries.py` 11, `tests/app/test_await_documents.py` 13, `tests/server/test_admin_api.py` 16, `tests/test_ingest_command.py` 17.
- 구현 뒤에 쓰거나 처음부터 초록이던 시험은 변이 표 `.scratch/core/probes/admin_queries_mutations.toml`의 열여덟 변이로 잰다. 기다림(지운 문서를 바쁜 것으로 셈, 남은 작업을 보지 않음, 마지막 잠이 줄지 않음, 제한 시간 0), 판정(문서 상태 `failed`), 작업 조회(남은 작업을 작업 자신의 상태로 셈, 건설 중인 판의 순서, 지운 문서의 색인 상태), 어댑터(작업 목록의 순서와 커서, 남은 작업 판정에 실행 중 빠짐, 상태 필터의 지운 문서), 명령(없는 그룹을 거르지 않음, 시간 초과 종료 코드, 상대 경로 키, 거부 종료 코드, `unchanged`를 기다리지 않음, 요청 ID를 로그 문맥에 싣지 않음)이다. 열여덟 모두 기대한 표지로 빨강이다.
- 첫 실행에서 한 변이가 살아남았다. 기다림이 지운 문서를 바쁜 것으로 세는 변이였다. 지운 문서의 대기 작업은 삭제가 취소해서 그 검사를 거치지 않았기 때문이다. `running` 작업이 남은 채 지운 문서의 시험(`test_지운_문서에_실행_중인_작업이_남아도…`)을 더하고 제한 시간을 둬 변이가 무한히 돌지 않게 했다. 이 시험을 더하자 변이는 빨강이 되었다.
- 코드 리뷰를 반영하며 더한 명령 시험의 변이(`unchanged`를 기다림 대상에서 뺌)도 첫 판은 살아남았다. 시험이 `with` 블록을 나간 뒤 상태를 읽어서, 블록을 나갈 때 작업자 스레드가 남은 작업을 마저 처리하기 때문이다. 명령이 돌아온 바로 그때 블록 안에서 상태를 읽도록 고치자 빨강이 되었다.
- `index_failure` 판정을 `document_outcome.py`로 옮겨 기존 표 `ingest_updates_mutations.toml`의 변이 둘(문서 상태 `failed`, 살아 있는 판의 `failed`)의 원문이 0번이 되었다. 새 위치와 새 반환 꼴로 고치고 둘을 다시 돌려 빨강을 확인했다. 둘째의 표지는 `pipeline.py:100`에서 `pipeline.py:185`로 옮겨 갔다(같은 `assert job is not None`이 다른 호출 경로에서 난다).
- 코드를 옮겼으므로 변이 표 열두 개 전부를 `--check`했다.
- 한 번 틀린 것: 시험에 `# type: ignore`를 두 번 썼다가 원칙 II에 걸려 `LiteralString`과 타입을 붙인 도우미 시그니처로 바꿨다. 시험 이름과 필드 설명이 ruff의 줄 길이(한글 폭 2)에 걸려 여러 번 감았다.

## 코드 리뷰

`/code-review`를 돌렸다. 범위는 base `20b38c7`, 수정한 파일 9개, 추적하지 않는 새 파일 12개, 커밋 0개다. 표준 축(sonnet / high)과 명세 축(세션 모델)이 따로 보았다. 표준 축은 Critical과 Major 없이 Minor 하나와 Nit, 냄새 몇이고, 명세 축은 Critical과 Major 없이 Minor 넷이다. 근거는 내가 코드에서 다시 열어 확인했다.

**고친 것**

- 표준 축 Minor: `await_documents.py`와 `document_outcome.py` 독스트링이 관리 API의 작업 조회가 `index_failure`를 쓴다고 적었으나 `admin_queries.py`는 그 함수를 부르지 않는다(grep 0건). 두 독스트링을 고쳤다.
- 이름: 함수 `document_outcome.index_failure`가 기존 모듈 `app/index_failure.py`(`mark_version_failed`)와 같은 이름이라 `index_failure_code`로 바꿨다.
- 질의와 명령 분리: `ensure_group_exists`는 예외를 던지고 유일한 호출자가 `try`/`except`로 불리언으로 바꿨다. 질의 `group_exists`로 바꿔 도우미를 없앴다.
- 시험의 군더더기(`assert kept.document_id is not None`과 쓰이지 않는 `kept`)를 지웠다.
- 명세 축 (a)1: 티켓의 관리 명령 시험 항목이 `--wait` 종료 코드의 세 갈래를 명령 층에서 요구하나 유스케이스 층 시험만 있었다. 명령 시험을 둘 더했다(`unchanged`가 앞선 작업을 기다림, 기다리는 사이 뒤 수집이 문서를 깨뜨려 색인이 실패하면 1). 세 갈래 가운데 "`failed`로 끝나도 뒤 작업이 색인하면 0"과 넣은 작업이 세대 대조로 `succeeded`가 되는 정확한 모양은 명령 층에서 결정적으로 짜기 어려워 유스케이스 시험이 잰다. 티켓 14번 항목에 이 나눔을 적었다.
- 명세 축 (a)2: 요청 ID가 로그 문맥에 쓰이는 쪽의 시험과 변이가 없었다. 시험(`test_한_실행의_요청_ID는…`)과 변이를 더했다.
- 명세 축 (a)4: README의 트리와 사용 안내에 `ingest`와 새 모듈을 적었다.
- 표준 축 Nit: `ingest_command.py` 독스트링에 빈 폴더가 종료 코드 0이라는 갈래와 `--timeout`의 의미(`--wait`와 함께 쓰고, 0 이하면 끝날 때까지, 없으면 무시)를 적었고 도움말도 맞췄다.

**PR 직전 리뷰에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `app/document_outcome.py` 독스트링: 관리 API의 작업 조회와 문서 조회는 `index_failure_code`를 거치지 않고 문서 상태와 판마다의 색인 상태를 그대로 낸다.
- `app/await_documents.py` 독스트링: 기다림의 판정은 수집의 `requeued` 조건과 같다(`index_failure_code`).
- `adapters/ingest_command.py` 독스트링: `--timeout`은 `--wait`와 함께 쓰고 없으면 무시하며 0 이하면 끝날 때까지 기다린다. 수집할 파일이 없는 폴더는 안내만 하고 0이다.
- 티켓 15의 14번 항목: 세대 대조 갈래 둘은 유스케이스 시험이 재고, 명령 시험은 `unchanged` 기다림과 뒤 수집이 문서를 깨뜨리는 갈래를 잰다.
- 이 일지의 "로그와 표준 출력": 로그 핸들러는 표준 출력에 쓰므로 이 명령의 로그 줄이 동작 줄과 섞일 수 있다.

**남긴 것과 이유**

- 표준 축 냄새: `_utc` 직렬화 도우미가 `admin_models`, `token_api`, `tool_models`에 세 벌이다. 합치려면 서버 공용 모듈이 필요하고 이 티켓의 요구가 아니다. 네 번째가 생기면 합친다.
- 시험 상수(`휴가`·`출장` DOCX, `DEFAULT_DIMENSIONS`)가 새 파일에도 반복된다. 기존 파일에도 여럿 있는 관행이라 두었다.
- `await_documents`의 `_is_busy`와 `_failure`가 같은 문서를 두 번 읽는다. 한 트랜잭션 안의 읽기 두 번이라 비용이 작고, 합치면 변이 표 둘의 원문이 모두 바뀐다.
- `ingest_command._ingest_with`가 걷기, 출력, 기다림, 종료 코드를 한 함수에 쥔다. 일곱 갈래의 조립이라 둔다. 길어지면 나눈다.
- `wait_timeout_seconds: float | None`이 없음, 무한, 양수 세 갈래를 한 값에 싣는다. 열거로 바꿀 수 있으나 호출처가 하나라 두었다.
- `DocumentState`와 `DocumentStatus`의 값 일치와 쿼리 매개변수 `status` 대 내부 `state` 이름은 명세의 어휘(쿼리는 `status`)와 도메인의 어휘를 맞춘 것이다.
- 명세 축 (a)3: 05 일지가 CLI가 유스케이스를 직접 부르면 NUL 검사를 유스케이스에서도 하겠다고 했으나, 이 명령의 입력(운영 체제가 NUL을 허용하지 않는 인자, 파일 이름, 그것에서 만든 상대 경로)으로는 NUL이 들어갈 수 없다. 도달할 수 없어 유스케이스에 검사를 더하지 않는다.
- 명세 축 (b): 명세에 적히지 않은 결정 넷은 위 "정한 것"에 적었고 PR 본문에서 사용자 승인을 묻는다. 승인 전에는 명세를 고치지 않았다.
- 문서 목록의 "최근 순"은 생성 순(문서 ID 내림차순)이다. 갱신·되살림 시각순이 아니고 명세의 "커서는 ID 비교"와 맞다.

**다시 돌린 명령**

- `ruff check .`, `ruff format --check .`, `pyright`, `lint-imports`, `check_type_escapes.py`가 통과이고(반영 전후 모두), 새 표의 열여덟 변이와 옮긴 변이 둘이 기대대로 빨강이다. 반영 뒤 변이 표 열두 개 전부의 `--check`도 통과다.
- 반영 뒤 `uv run python tools/run_checks.py`가 `test-db`, `zizmor`, `check-ticket`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright-linux`, `pyright`, `run-hooks`, `pytest`(285.9초) 모두 통과다. 일지, 회고 대기열 항목, 티켓의 마지막 체크는 그 실행이 시작된 뒤에 썼으므로 커밋이 부르는 pre-commit이 그 파일들을 다시 본다.

## PR 직전 리뷰

커밋 `1ff131e` 위에서 내장 보안 리뷰와 `bug-perf-review` 에이전트를 돌렸다. 보안 축은 취약점이 없다. SQL은 모두 SQLAlchemy 표현식으로 바인딩되고, 새 라우터는 인증 미들웨어 안쪽이라 `reader`는 403이며, `ingest`의 경로는 명령줄 인자(신뢰된 입력)다. 버그·성능 축은 Critical 없이 Major 하나와 Minor 다섯이다. 근거는 내가 코드에서 다시 열어 확인했다.

**고친 것**

- Major: `jobs.document_id`에 `has_active_job`(`document_id = ? AND status IN ('queued', 'running')`)을 받는 색인이 없었다. 0001의 부분 유일 색인은 `status = 'queued'`일 때만 쓰인다. 프로브(`.scratch/core/probes/jobs_active_index_plan.py`)로 쟀다. head에서는 `Index Scan using ix_jobs_document_id_active`가 나오고, 그 색인을 지우면 `enable_seqscan = off`여도 `Seq Scan`에 `Disabled: true`뿐이다(대안 계획이 없다). 새 판 `0002`로 `ix_jobs_document_id_active`를 더했다(술어는 질의의 `IN` 목록과 같고 `tables.py`에도 같은 색인을 적어 `compare_metadata` 시험이 0 차이를 본다). 칸과 제약은 바꾸지 않는다. 마이그레이션 시험은 head 판을 상수 `HEAD_REVISION`으로 보고 색인의 열과 술어를 재는 시험을 더했다.
- Minor: 파일을 읽다가 `OSError`(권한, 잠금, 사라진 파일)가 나면 루프가 트레이스백으로 죽어 앞서 넣은 문서를 기다리지도 못했다. `OSError`를 `거부<탭>키<탭>읽기 실패`로 세고 나머지를 이어 넣는다. 사유 문구에 운영체제의 메시지(경로)를 싣지 않는다. 시험을 먼저 썼고 빨강을 본 뒤 고쳤다.
- Minor: `--timeout nan`은 모든 비교가 거짓이라 제한 시간이 오지 않았다(보고가 `False 1.0 False`를 재 보았다). argparse의 `type`(`_seconds`)이 `nan`을 거부해 아무 파일도 넣지 않고 인자 오류(종료 코드 2)로 끝난다.
- Minor: 시간 초과(2)가 거부된 파일(1)을 가리는 우선순위를 `ingest_command.py` 독스트링에 적었다.

**PR 봇에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `0002_jobs_active_document_index.py` 독스트링: 0001의 부분 유일 색인은 `status = 'queued'`일 때만 쓰여 `IN ('queued', 'running')` 질의를 받지 못하고, 외래 키 열에는 색인이 자동으로 생기지 않아 작업 표를 처음부터 끝까지 읽는다. 새 색인은 진행 중인 작업만 담으므로 끝난 작업이 쌓여도 커지지 않는다.
- `adapters/ingest_command.py` 독스트링: 읽지 못한 파일은 사유 `읽기 실패`와 키를 표준 오류에 적고 나머지를 이어 넣으며 종료 코드 1이다. 거부된 파일과 시간 초과가 겹치면 2가 앞선다.
- `main.py` `_seconds`: `nan`은 모든 비교가 거짓이라 제한 시간이 영영 오지 않으므로 인자 단계에서 거른다.

**남긴 것과 이유**

- 문서 목록이 문서마다 질의를 약 아홉 번 내는 N+1(`limit=200`이면 1800번 안팎)이다. 관리자 전용이고 한 트랜잭션 안의 읽기이며 지연을 재지 않았다. 같은 그룹의 원천·그룹·지식베이스·판을 한 호출 안에서 메모하면 줄지만, 변이 표 18개의 원문이 바뀌고 이 티켓의 요구가 아니라서 두었다.
- `wait_for_documents`가 폴링마다 끝나지 않은 문서 수만큼 질의를 낸다. `has_active_job`에 색인이 생겼으므로 한 바퀴 비용은 질의 수에 비례할 뿐이다. 묶은 질의(`document_id = ANY(:ids)`)는 문서가 수천을 넘을 때 하자.
- `documents`에 `key` 단독, `group_id`, `deleted_at`, `status` 색인이 없어 맞는 행이 드문 필터(`status=deleted`, 없는 `key`)는 표를 끝까지 훑을 수 있다. `ORDER BY id DESC LIMIT n`이라 맞는 행이 최근에 있으면 빨리 끝난다. 규모를 보고 정할 일이라 알려진 한계로 둔다.

**다시 돌린 명령**

- `ruff check .`, `ruff format`, `pyright`가 통과이고, 마이그레이션·`ingest` 명령·unit of work 시험 48개가 통과이며, 변이 표 둘의 `--check`도 통과다. 전체 검사는 커밋 직전 pre-commit이 다시 돈다.

## 회고

후보 여섯을 냈고 승인 하나, 기각 다섯, 넘김 없음이다.

- **승인: 변이 표의 표지는 실제 출력을 본 뒤에야 고를 수 있다**(대기열 `mutate-marker-discovery`, 2회차). 사건: 이 세션이 임시 표지를 열여섯 변이에 넣어 일부러 어긋나게 돌린 뒤 찍힌 출력에서 표지를 골랐고, 12 세션도 짐작한 표지 여섯이 어긋나 표를 다시 돌렸다. 층: 도구(`tools/mutate.py`)가 어긋난 변이의 출력을 한 번에 보여 주는 쪽이 지침보다 강하다. 되돌림: PR 하나. 더하는 것이라 다섯 번째에 반영하고 지금은 대기열에 둔다.
- 기각: `ruff` 줄 길이(한글 폭 2)에 시험 이름과 필드 설명이 여러 번 걸렸다. `hook_ruff_line_width`가 매번 알렸고 그 알림대로 고쳤다. 이미 있는 훅이 그 자리에서 알렸다.
- 기각: 시험에 `# type: ignore`를 두 번 썼다. `check_type_escapes.py`가 잡았다. 이미 있는 검사가 막았다.
- 기각: 명세 축 리뷰가 티켓의 관리 명령 시험 항목을 명령 층에서 채우지 않았다고 짚었다. 티켓의 수용 기준은 `code-review`의 명세 축이 겨냥하도록 둔 기준이라 리뷰가 제 몫을 한 것이다(4단계의 회차 셈에서 뺀다).
- 기각: 변이 하나가 살아남았다(`with` 블록을 나간 뒤 상태를 읽는 시험, 지운 문서의 `running` 작업을 다루지 않는 시험). 변이 표가 바로 그 빈틈을 찾으려고 있고, 이번에도 찾아 시험을 고쳤다.
- 기각: `tools/mutate.py` 독스트링(약 140줄)을 표 형식을 알려고 읽었다. 대기열 `mutate-usage-dump`는 `--check`를 인자 없이 쳐서 독스트링 전체를 찍은 사건이고 이번 읽기는 일부러 연 것이라 같은 사건이 아니다. 표의 앞 몇 줄(`retries_mutations.toml`)이 형식을 이미 보여 주었다.

## 다음

- core의 프론티어는 13(임대와 작업자)이다. 14(재색인과 판 전환)는 13이 막고, 16(검색 지연 프로브)은 14가 막는다(15는 이 PR로 닫힌다). 열린 티켓이 남아 있어 이 PR은 기능 계획의 `**끝:**` 줄을 더하지 않았다.
- 15가 각 티켓에 넘기는 것:
  - 13: 상시 작업자 반복이 일시 실패를 받아 다음 반복으로 넘어가는 일은 그대로 13의 몫이다. `ingest --wait`는 작업자가 따로 떠 있어야 끝나므로, 13이 만드는 작업자 프로세스가 이 명령의 짝이다.
  - 14: 재색인이 건설 중인 판을 만들면 `admin_queries`의 색인 상태 목록이 그 판을 `building`으로 따로 낸다(시험이 있다). `index_failure_code`는 살아 있는 판 모두를 보므로, 건설 중인 판의 실패도 `--wait`의 종료 코드 1에 든다.
- 열린 일:
  - 명세 관리 명령 절에 거부된 파일, 빈 폴더, 없는 경로, 목록 한도의 결정을 적을지는 사용자 승인이 필요하다.
  - 삭제 키의 422를 명세의 수집 API 절에 적는 것도 11이 넘긴 대로 사용자 승인이 필요하다.
  - `읽기 실패`로 거부된 파일도 명세에 적히지 않은 결정이다(앞의 넷과 같이 종료 코드 1이고 나머지를 이어 넣는다). 승인을 PR 본문에서 묻는다.
  - 마이그레이션 `0002`는 첫 후속 판이다. 색인만 더하고 칸과 제약은 바꾸지 않아 이 PR에서 더했으나, 판 규약(색인 형식에 판을 붙인다)에 닿는 첫 사례이므로 PR 본문에서 사용자가 확인한다. 13의 작업자 워크트리는 같은 `job_queue.py`를 고치므로 그쪽이 마이그레이션을 더하면 판 번호가 겹칠 수 있다.
  - 로그 줄이 표준 출력에 섞이는 것을 막으려면 로그 핸들러의 스트림을 고르는 길이 필요하다. 이 명령의 요구가 아니라 남겼다.
