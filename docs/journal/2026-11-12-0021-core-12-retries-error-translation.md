# core 12 재시도와 오류 번역 일지 · 2026-11-12

티켓 `.scratch/core/issues/12-retries-error-translation.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/12-retries-error-translation`, 작업은 워크트리 `retries-error-translation`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다. 구현 도중 컨텍스트가 한 번 압축되었다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 11 일지의 다음, 명세의 수집 파이프라인과 작업 절(오류 번역, 재시도, 재시도 소진, 잠금 규칙), ADR 0009.
- 지시문대로 `tidy-checkouts`를 먼저 돌고 워크트리에 들어가 브랜치를 따라 이름을 맞췄다.
- 테스트 PostgreSQL은 `compose.test.yml`의 컨테이너를 쓰고 명령마다 `RAG_TEST_DATABASE_URL`과 `PYTHONUTF8=1`을 내보냈다.
- 티켓을 첫 변경에서 `in-progress`로 두었다.

## 정한 것

- **오류 번역**(`adapters/postgres/error_translation.py`). SQLSTATE 클래스 `08`, `40001`, `40P01`, `57P01`~`57P03`은 `TransientFailure(database_unavailable)`로 바꾼다. SQLSTATE가 없는 psycopg의 `OperationalError`와 `InterfaceError`는 연결 실패로 보아 일시다. SQLSTATE가 없는 `DataError`(NUL 문자)나 `IntegrityError` 같은 나머지는 일시가 아니라 원래 예외 그대로다. 메시지는 옮기지 않는다(원칙 V). 번역 자리는 `PostgresUnitOfWork.begin()` 하나로, 연결, 본문, 커밋과 롤백에서 난 오류를 모두 같은 길로 받는다. 파일 저장소의 `blob_store_error`는 05가 이미 구현했고 이 티켓은 바꾸지 않았다.
- **재시도 정책**(`app/retry_policy.py`). `RetryPolicy(max_attempts, backoff_base_seconds)`가 소진 판정(`attempts >= max_attempts`)과 백오프(`base × 4^(attempts−1)`, 한 시간 상한)를 가진다. 필수 인자로 두어 숨은 기본값이 없다. 시험 도우미가 기본 정책을 건넨다.
- **다시 예약하기**(`app/job_failure.py`의 `reschedule`). 문서 행, 지식베이스 행(`FOR SHARE`), 작업 행 순으로 잠그고 `JobQueue.reschedule`로 `queued`, `run_after`, 마지막 오류 코드, 임대 해제, 올린 세대 비움을 한 문장으로 쓴다. 같은 문서에 다른 대기 작업이 있으면 `NOT EXISTS`가 거절해 0행이 되고, 그때는 이번 오류 코드로 작업만 `failed`로 끝낸다. 문서 쪽은 쓰지 않는다.
- **재시도 소진**(`exhaust`). 문서 행, 지식베이스 행(`FOR UPDATE`), 작업 행 순으로 잠근다. 문서가 지워지지 않았고, 처음부터 맡을 다른 작업이 없고(`JobQueue.has_other_job_from_start`: 대기 작업이거나 올린 세대가 빈 실행 중 작업), 올린 세대가 없거나 문서의 세대와 같을 때만, 지금 내용으로 색인되지 않은 살아 있는 판(색인 상태가 없거나 `pending`이거나 만든 내용 해시가 다른 `indexed`)에서 조각을 지우고 `failed`를 쓴다. 문서 상태는 바꾸지 않는다.
- **색인 실패의 한 자리**(`app/index_failure.py`의 `mark_version_failed`). 조각 지우기, `failed` 색인 상태 쓰기, 건설 중인 판이면 전환 검사 부르기를 한 함수로 모았다. 파싱의 영구 실패, 임베딩의 영구 실패, 재시도 소진이 모두 부른다.
- **작업 행 조건의 자리**(`app/job_attempt.py`의 `hold_attempt`). `index_document`의 비공개 `_hold`를 옮겨, 다시 예약하기와 재시도 소진도 같은 함수로 작업 행 조건을 본다.
- **갈래 정하기**(`worker/processing.py`). `AttemptLostError`는 `lost`, `TransientFailure`는 `settle_transient_failure`(남았으면 다시 예약, 다 썼으면 소진), 그 밖의 `RagEngineError`는 재시도 없이 `failed`, 어느 갈래에도 들지 않는 예외는 `job_crashed`를 남기고 `internal_error`로 소진과 같이 끝낸다. 다시 예약하기와 소진은 자기 작업 단위 안에서 작업 행을 이미 쓰므로 `_Settled.recorded`로 `process_job`이 한 번 더 끝내지 않게 했다.
- **임베딩의 영구 실패**(`_replace_chunks`). 영구 실패한 판은 건너뛰고 남은 판을 계속 처리해, 세대 대조를 지난 같은 작업 단위에서 그 판에 `failed`를 쓰고 나머지 판에 조각을 쓴다. 작업은 마지막 영구 실패의 코드로 `failed`가 된다. 남은 판에서 일시 실패가 나면 아무것도 쓰기 전에 예외가 올라가 시도 전체가 일시 실패다.
- **08이 넘긴 것**. `IndexTimer`(공개)를 부르는 쪽이 만들어 `index_document`에 건네므로 예외로 끝난 시도도 그때까지의 지연을 `job_finished`에 싣는다.
- **시험 도우미**. `Pipeline.job_rows`·`states`·기본 `RetryPolicy`, 끼어들기 훅의 `FlakyUnitOfWork`(앞 몇 번의 `begin()`이 일시 실패)와 `rejecting_embedder_for`(고른 판의 임베딩이 영구 실패).

## 손으로 본 것

- 어댑터와 앱 시험은 구현 앞에 썼다. 포트 메서드나 모듈이 없어 빨간 것을 먼저 보고 구현으로 초록을 만들었다. 교차 시험 몇은 쓰는 시점에 구현이 있어 처음부터 초록이었다.
- 처음부터 초록이던 시험은 `tools/mutate.py`의 표(`.scratch/core/probes/retries_mutations.toml`)로 변이를 돌렸다. 백오프 상한과 증가율, 소진 판정의 경계, 다시 예약하기의 `NOT EXISTS`, 소진의 다른 작업 검사와 세대 대조와 지운 문서 검사와 색인된 판 보존과 해시 비교, 지식베이스 잠금 모드 셋, `internal_error`의 재시도, 임베딩 영구 실패의 판별 쓰기와 작업 종결, 실패한 시도의 파싱 지연, 올린 세대 조건, SQLSTATE 번역 넷과 메시지 미전달이 그것이다. 처음 스물둘은 모두 빨강이었다.
- 첫 실행은 표지 문구 넷이 시험 원문에 글자 그대로 있다는 검증에서 아무 파일도 쓰지 않고 멈췄다. 실패 출력에서만 나오는 문구(`Left contains 1 more item` 같은 pytest 풀이 줄)로 바꿔 다시 돌렸다. 다음 실행에서 표지 문구가 실제 출력과 다른 여섯이 어긋났고, 그 가운데 하나는 `if` 본문을 통째로 지워 문법 오류가 난 변이였다(`pass`로 바꿨다). 어긋난 여섯을 고쳐 다시 돌려 모두 기대대로 빨강이었다.
- 코드가 옮겨 가서 기존 표의 변이 다섯(`ingest_updates_mutations.toml`의 셋째 단계 세대 대조, `first_round_trip_mutations.toml`의 임베딩 사이 세대·작업 행 조건·임대를 잃은 시도, `first_round_trip_adapter_mutations.toml`의 꺼낼 때 올린 세대 비움)의 원문이 0번이거나 두 번이 되었다. 새 원문으로 고치고 `--check`를 통과시킨 뒤 다섯을 다시 돌려 모두 빨강을 확인했다.
- 한 번 틀린 것: 지운 뒤 되살린 교차 시험이 첫째 작업 행을 보았다(앞서 성공한 작업). 마지막 행으로 고쳤다. 지식베이스 잠금 시험은 처음에 1초 시간 제한으로 쓰여, 파싱이 느려서 초록이 되는 약한 시험이었다. `pg_stat_activity`에서 잠금 대기가 보일 때까지 기다린 뒤 잠금을 푸는 방식으로 다시 썼고, `FOR SHARE`는 대기하지 않는다는 시험을 하나 더했다.
- 연결이 닿지 않는 데이터베이스 시험은 연결 기한이 길어 130초가 걸렸다. 연결 문자열에 `connect_timeout=2`를 넣어 줄였다.
- 전체 검사 실행기(`tools/run_checks.py`)의 pytest는 3548개 가운데 3개가 실패했다. 하나는 이 변경의 것이다(영구 실패의 전환 검사 호출이 `index_failure`로 옮겨 가 `index_document`의 이름을 바꿔치던 옛 시험이 빨개졌다. 바꿔치는 모듈을 옮겨 고쳤다). 나머지 둘은 `test_parse_runner`의 기한 2초 시험과 `serve`가 30초 안에 뜨는지 보는 시험이다. 이 변경은 파서와 서버 기동을 건드리지 않았고, `serve` 시험은 단독으로 돌리면 통과한다. `test_parse_runner` 시험은 11 일지가 이미 적은 대로 윈도에서 `parse_failed` 대신 `parse_timeout`이 나는 경쟁이고, 이번에는 단독으로 돌려도 한 번 실패했다.
- 코드 리뷰 반영(`_replace_chunks`의 `try`/`finally`로 들여쓰기가 바뀌고 `_record_permanent_failure`가 `mark_version_failed`를 쓰게 된 것)이 변이 표 네 항목의 원문을 깼다. 반영 직후에는 내가 다섯 표만 `--check`해 `parsers_isolation_mutations.toml`을 빠뜨렸고, 첫 커밋 시도가 pre-commit의 변이 표 검사(`check-mutations`)에서 막혔다. 네 항목(`first_round_trip`의 임베딩 사이 세대, `ingest_updates`의 셋째 단계 세대, `parsers_isolation`의 옛 조각 지우기와 전환 검사)을 새 위치와 들여쓰기에 맞게 고치고 넷을 다시 돌려 모두 빨강을 확인했다. 코드를 옮기면 표 전부를 한 번에 `--check`해야 한다.

## 코드 리뷰

`/code-review`를 돌렸다. 범위는 base `06d5513`, 수정한 파일 16개, 추적하지 않는 새 파일 9개, 커밋 0개다. 표준 축(sonnet / high)과 명세 축(세션 모델)이 따로 보았다. 표준 축은 Critical 없이 Major 하나, Minor 여섯, 냄새 몇이고, 명세 축은 지연 누락 하나, 낡은 문장 다섯, 낮은 확신 하나다. 근거는 내가 코드에서 다시 열어 확인했고, 백오프 넘침은 직접 불러 재현했다.

**고친 것**

- Major(표준 축): `app/job_attempt.py` 머리글이 색인 작업의 작업 단위는 모두 지식베이스 행을 잠근다고 적었으나 `index_document`의 작업 단위는 잠그지 않는다. 문서 행을 먼저, 작업 행을 마지막에 잠근다고 고치고, 지식베이스 행을 잠그는 작업 단위는 지금 다시 예약하기와 재시도 소진뿐이라고 적었다.
- 백오프 넘침(표준 축 Minor, 명세 축 누락): `RetryPolicy(…).backoff(n)`은 시도 횟수 513 이상에서 `OverflowError`가 난다. 시험(`test_시도_횟수가_아무리_커도…`)을 먼저 써서 빨강을 보고 지수를 64로 막아 고쳤다. 변이 표에 지수 상한 변이를 더했다.
- 실패한 시도의 지연(명세 축 누락): 임베딩 서버가 일시 실패하면 `embedding_ms`가 0이었다. 시험(`test_임베딩이_일시_실패해…`)을 먼저 써서 빨강을 보고 임베딩과 쓰기 지연을 `try`/`finally`로 더하게 고쳤다. 변이 표에 임베딩 지연 변이를 더했다.
- `worker/processing.py`의 `_settle(..., retry: bool)`는 표준의 불리언 플래그 규칙에 걸려 마무리 함수(`settle_transient_failure` 또는 `exhaust`)를 인자로 받게 바꿨다.
- 낡은 문장: `app/index_document.py` 머리글(영구 실패 문장), `adapters/postgres/job_queue.py`의 `_attempt_of` 독스트링, `domain/ports.py`의 `JobOutcome` 독스트링, 티켓 14의 07이 넘긴 것(`_hold`가 `hold_attempt`가 되었고, 재시도 소진이 지식베이스 행을 잠근 채 전환 검사를 부른다), 티켓 13의 `hold_attempt` 호출처, 티켓 12의 13이 받을 것(`process_job` 안의 작업 단위와 `run_once`의 꺼내기까지 넓혔다)과 14가 받을 것.
- 줄 끝: 내 Python 쓰기가 티켓 12, 변이 표, 시험 파일, `unit_of_work.py`를 CRLF로 만들었다. `.gitattributes`가 `eol=lf`라 LF로 되돌렸다.

**PR 직전 리뷰에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `app/job_attempt.py`: 지식베이스 행을 잠그는 작업 단위는 지금 `job_failure`의 다시 예약하기와 재시도 소진뿐이고, 색인 작업 자신의 작업 단위가 잠그는 일은 14가 한다.
- `app/retry_policy.py`: 지수를 64로 막아도 한 시간 상한 때문에 값은 같고, 시도 횟수가 아무리 커도 넘치지 않는다.
- `app/index_document.py` 머리글: 파싱과 임베딩의 영구 실패는 세대가 달라 문서와 색인에 쓰지 않을 때도 그 실패를 작업의 결과로 올려 작업이 `failed`로 끝난다.
- 티켓 14의 07이 넘긴 것: 재시도 소진이 전환 검사를 부를 때는 문서 행, 지식베이스 행(`FOR UPDATE`), 작업 행(`hold_attempt`) 순으로 모두 잠겨 있다. 파싱과 임베딩의 영구 실패가 부를 때는 `index_document`의 경우와 같다.
- 티켓 13: `hold_attempt`는 `index_document`의 네 쓰기 단위와 `job_failure`의 두 작업 단위가 부른다.

**남긴 것과 이유**

- Minor(표준 축): `index_document(deps, job, timer)`가 받은 `IndexTimer`를 바꾸는 출력 인자다. 예외로 끝난 시도의 지연도 부른 쪽이 읽어야 하므로 반환값으로는 줄 수 없다. 객체를 부르는 쪽이 쥐는 것이 가장 작은 모양이라 둔다.
- Minor(표준 축): `JobQueue.reschedule`이 쓰면서 bool을 돌려주고 `_lock_knowledge_bases`가 잠그면서 판 목록을 돌려준다. 앞의 것은 독스트링이 적은 원자성(같은 문장 안에서 다른 대기 작업을 보고 쓴다) 때문이고 선례 `hold_attempt`가 있다. 뒤의 것은 잠근 지식베이스의 판만 읽어야 하는 성질이라 한 함수로 둔다.
- 냄새(표준 축): `job_failure._live_versions`가 `live_index_versions`를 쪼갠 꼴이고 지식베이스를 ID 순으로 잠그는 논리가 `ingest`, `delete_document`, `job_failure`에 세 벌이다. 둘이 같이 바뀌어야 하는 일이 생기면 합친다.
- 냄새: `IndexDocumentDeps.retry`는 `index_document` 자신이 읽지 않고 `job_failure`와 작업자가 읽는다. 07이 정한 대로 작업자 입구가 하나의 deps를 쓰는 조립을 따른다. 이름이 모호한 `_Settled.outcome=None`(임대를 잃음)과 `job_failure.reschedule`이 `JobQueue.reschedule`과 이름이 같은 것은 Nit이다.
- 시험 결합(내가 알림): 쓰기 단계가 실패한 시도도 `write_ms`를 싣도록 `finally`를 두었으나 그 경로를 막는 시험이 없다. 쓰기 단계에서 일시 실패를 내려면 두 번째 `begin()`에서 실패시키는 도우미가 필요해 이 티켓에서는 하지 않았다.
- 명세 축 낮은 확신: `token_store`는 `engine.begin()`과 `connect()`를 직접 써서 오류를 번역하지 않는다. 이 티켓의 번역 대상은 작업 대기열과 색인 파이프라인이 쓰는 작업 단위이고, 인증 경로의 결과는 이전과 같은 500이라 바꾸지 않았다. 인증 쪽 일시 실패를 다르게 다룰 요구가 생기면 그 티켓이 연다.
- 명세 축 (b): `begin()`의 번역은 서버 요청 경로에도 적용되나 결과는 여전히 500이다(`on_unhandled`).

**다시 돌린 명령**

- 반영 뒤 `ruff check`, `ruff format --check`, `pyright`가 통과이고 변이 표 다섯(`retries`, `first_round_trip`, `first_round_trip_adapter`, `ingest_updates`, `delete_restore`)의 `--check`가 통과다.
- 반영 뒤 변이 표 `retries_mutations.toml`의 스물네 변이를 전부 다시 돌려 모두 기대한 표지로 빨강이다(스물네째는 문법이 틀린 변이 정의를 고쳐 따로 돌렸다).
- 반영 뒤 `uv run python tools/run_checks.py`가 `test-db`, `check-ticket`, `zizmor`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright-linux`, `pyright`, `run-hooks`, `pytest`(282.5초) 모두 통과다. 앞선 실행에서 빨갛던 `test_parse_runner`의 기한 2초 시험과 `serve` 기동 시험도 이번에는 통과했다. 둘은 이 변경과 무관하게 부하에서 갈리는 시험이다.

## PR 직전 리뷰

내장 보안 리뷰와 `bug-perf-review`를 커밋 `175a6dd` 위에서 돌렸다. 보안 리뷰는 확신 7 이상의 취약점이 없다고 보고했다. `bug-perf-review`는 Critical과 Major 없이 Minor 넷을 냈고, 근거는 코드에서 다시 열어 확인했다.

**고친 것**

- 티켓 14의 07이 넘긴 것과 일지의 "다음"이 재시도 소진은 전환 검사를 부를 때 작업 행이 아직 잠기지 않았다고 적었으나 `exhaust`는 `hold_attempt`로 작업 행을 `mark_version_failed`보다 먼저 잠근다(`app/job_failure.py`). 문서 행, 지식베이스 행, 작업 행 순으로 모두 잠겨 있다고 고쳤다.
- 티켓 13과 일지가 `hold_attempt`를 부르는 `index_document`의 쓰기 단위를 셋이라고 적었으나 `_raise_generation`, `_ensure_parsed`의 저장, `_record_permanent_failure`, `_replace_chunks`로 넷이다. 넷으로 고쳤다.
- 파싱이 일시 실패하거나 파싱 뒤 쓰기 단위가 실패한 시도는 `parse_ms`를 싣지 못했다(`_ensure_parsed`가 정상 종료, 영구 실패, 세대 대조 탈락 갈래마다 따로 더해, 그 밖의 예외는 더하지 못했다). 시험(`test_파싱이_일시_실패해…`)을 먼저 써서 `assert 0.0 > 0` 빨강을 본 뒤, 파싱과 쓰기를 `_parse_and_save`로 나누고 `_ensure_parsed`가 `try`/`finally`로 시간을 더하게 고쳤다. 시험 도우미 `TransientFailingRunner`와 변이 표의 변이 하나(스물다섯째)를 더했다.

**남긴 것과 이유**

- `PostgresUnitOfWork.begin()`의 `raise transient from None`은 그대로 둔다. 로그 형식기(`adapters/log_format.py`)는 맨 위 예외의 종류와 프레임만 적고(메시지는 `rag_engine` 예외만) `__cause__`를 따라가지 않으므로 `from error`로 바꿔도 로그는 늘지 않는다. 오히려 다른 처리기가 체인을 찍으면 드라이버 메시지(접속 정보가 섞일 수 있다)가 새므로 원칙 V를 구조로 지키려고 끊어 둔다. SQLSTATE를 진단에 남기려면 상수 문자열인 SQLSTATE만 별도 필드로 싣는 일이 따로 필요하고, 이 티켓의 요구가 아니다.

**다시 돌린 명령**

- `ruff check .`, `ruff format --check .`, `pyright`가 통과이고(`ruff check`는 처음에 시험 파일의 임포트 정렬 하나로 빨갛다가 `--fix` 뒤 통과했다), 변이 표 열하나 모두의 `--check`가 통과다.
- `tests/app`, `tests/contract/test_first_round_trip.py`, `tests/adapters/test_job_queue_reschedule.py`, `tests/adapters/test_postgres_error_translation.py`가 200개 통과다.
- 변이 표 `retries_mutations.toml`의 스물다섯 변이를 전부 다시 돌려 모두 기대한 표지로 빨강이다. 돌린 뒤 `git status`가 의도한 파일만 바뀐 것으로 보여 변이가 원상태로 되돌려졌다.
- 커밋이 부르는 pre-commit(검사 러너)의 결과는 커밋 뒤에 PR 본문에 적는다.

**PR 직전 리뷰 뒤에 새로 쓴 사실 문장**(PR 봇 회차가 겨냥할 것)

- `app/index_document.py`의 `_parse_and_save` 독스트링: 어떻게 끝나든 호출한 쪽(`_ensure_parsed`)이 걸린 시간을 `parse_ms`에 더한다.
- 위 "남긴 것"의 형식기 서술: 맨 위 예외의 종류와 프레임만 적고 `__cause__`를 따라가지 않는다.

## 다음

- core의 프론티어는 13(임대와 작업자)과 15(조회와 `ingest` 명령)다. 둘 다 12를 막는 쪽으로 두었고 12가 닫혀 바로 시작할 수 있다. 14(재색인과 판 전환)는 13이 막고, 16(검색 지연 프로브)은 14와 15가 막는다. 열린 티켓이 남아 있어 이 PR은 기능 계획의 `**끝:**` 줄을 더하지 않았다.
- 12가 각 티켓에 넘긴 것:
  - 13: `process_job` 안의 작업 단위(다시 예약하기, 재시도 소진, 끝내기)와 `run_once`의 꺼내기에서 데이터베이스가 끊기면 `TransientFailure(database_unavailable)`가 호출한 쪽까지 올라간다. 상시 작업자 반복이 그 예외를 받아 로그를 남기고 다음 반복으로 넘어가야 하고, 그 작업은 임대가 끝난 뒤 다른 작업자가 가져간다. `hold_attempt`는 `app/job_attempt.py`로 옮겼고 `job_failure`의 두 작업 단위도 부른다. 티켓 13의 해당 문장을 고쳤다.
  - 14: 파싱과 임베딩의 영구 실패와 재시도 소진이 건설 중인 판에 `failed`를 쓰면 `app/index_failure.py`의 `mark_version_failed`가 `check_version_switch`를 부른다. 재시도 소진은 문서 행과 지식베이스 행(`FOR UPDATE`)을 잠근 채, 두 영구 실패는 지식베이스 행을 잠그지 않은 채 부른다. 14가 지식베이스 행 잠금을 `index_document`의 셋째 단계로 올리면 두 영구 실패 경로의 잠금도 같이 맞춘다. 티켓 14의 07이 넘긴 것에 적었다.
- 열린 일:
  - 쓰기 단계가 실패한 시도도 `write_ms`를 싣도록 둔 `finally`를 막는 시험이 없다. 두 번째 `begin()`에서 실패시키는 시험 도우미가 필요해 이 티켓에서 하지 않았다.
  - `token_store`의 `engine.begin()`과 `connect()`는 오류를 번역하지 않는다. 인증 경로가 일시 실패를 다르게 다뤄야 하는 요구가 생기면 그 티켓이 연다.
  - 이 세션이 남긴 Minor(`IndexTimer` 출력 인자, 지식베이스 ID 순 잠금의 세 벌, `_live_versions`의 중복 꼴)는 둘이 같이 바뀌어야 하는 일이 생기면 합친다.
  - 11이 넘긴 둘(`delete_document`가 문서 행을 잠근 뒤 `purged_at`을 다시 보지 않는 것은 묘비 행을 만드는 정리 작업을 쓰는 티켓이 닫고, 삭제 키의 422를 명세의 수집 API 절에 적는 것은 사용자 승인이 필요하다)는 12의 범위가 아니라 그대로다.
  - `test_parse_runner`의 기한 2초 시험과 `serve` 기동 30초 시험은 부하에서 갈린다. 11 일지의 회고가 사용자가 다시 열지 정한다고 적은 것과 같은 종류이고 이번에도 고치지 않았다.
