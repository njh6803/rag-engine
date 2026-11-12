# core 13 임대와 인수, 작업자 프로세스 일지 · 2026-11-12

티켓 `.scratch/core/issues/13-lease-worker-process.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/13-lease-worker-process`, 작업은 워크트리 `lease-worker-process`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다. 구현 도중 컨텍스트가 한 번 압축되었다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 12 일지의 다음, 명세의 수집 파이프라인과 작업 절(잠금 규칙, 작업자, 임대), ADR 0009와 ADR 0011.
- 지시문대로 `tidy-checkouts`를 먼저 돌고 워크트리에 들어가 브랜치를 따라 이름을 맞췄다. 주 체크아웃은 이미 main이었다.
- 테스트 PostgreSQL은 `compose.test.yml`의 컨테이너를 쓰고 명령마다 `RAG_TEST_DATABASE_URL`과 `PYTHONUTF8=1`을 내보냈다.
- 티켓을 첫 변경에서 `in-progress`로 두었다.
- 나란히 도는 티켓 15가 `job_queue.py`, `ports.py`, `main.py`를 함께 고친다(`sibling_overlap.py`가 알렸다). 병합 순서에 따라 나중에 병합하는 쪽이 글자 충돌을 푼다.

## 정한 것

- **임대 연장**(`worker/processing.py`). `process_job(deps, job, lease_seconds=…)`가 유스케이스와 연장 작업(`_keep_lease`)을 한 이벤트 루프에서 나란히 돌린다. 간격은 임대 기간의 삼분의 일이고 공개 함수 `extension_interval_seconds`가 정한다. 연장이 작업 행 조건에 걸리면 연장 작업이 돌아오고 `_index`가 유스케이스를 취소한 뒤 `AttemptLostError`를 올린다. 데이터베이스가 잠시 닿지 않아 연장하지 못하면 `lease_extension_failed` 경고를 남기고 다음 간격에 다시 한다. 일시 실패 갈래에 들지 않는 예기치 않은 예외도 같은 이벤트를 오류 수준으로 남기고 다시 한다(PR 직전 리뷰가 짚은 것이다. 연장이 죽으면 건강한 작업이 `internal_error`로 재시도 없이 실패한다). 간격은 앞 연장이 끝난 뒤부터 세므로, 연장 한 번이 임대 기간의 삼분의 일 안에 실패로 돌아올 때만 임대가 끝나기 전에 다시 시도한다. `lease_seconds`가 `None`이면 연장하지 않는다. 한 번에 끝나는 기존 시험 약 사십 곳을 위한 갈래이고 작업자는 항상 임대 기간을 준다.
- **`finish`와 `extend_lease`는 예외로 알린다**(`domain/ports.py`, `adapters/postgres/job_queue.py`). 처음에는 갱신 여부를 `bool`로 돌려주었으나 코드 리뷰가 `CODING_STANDARDS.md`의 CQS(쓰면서 성공 여부를 돌려주면 실패가 조용히 묻힌다)에 걸린다고 짚었다. 이 둘은 `reschedule`과 달리 한 문장으로 묶어야 할 까닭(부분 유일 색인)이 없다. 작업 행 조건에 걸리면 아무것도 쓰지 않고 `AttemptLostError`를 올리고, 부른 쪽(`process_job`의 `_finish`, `_keep_lease`)이 받는다. `hold_attempt`와 같은 신호다. 끝내기 직전에 임대를 잃은 시도는 `job_finished`의 `result`가 `lost`다.
- **인수의 `worker_lost` 갈래**. `RetryPolicy.is_overrun(attempts)`는 `attempts > max_attempts`다. 꺼낼 때 시도 횟수가 1 오르므로 꺼내기 전 값이 `max_attempts` 이상이었다는 뜻이고 티켓의 문장과 같다. `_run`이 맨 앞에서 보고 유스케이스를 돌리지 않고 `worker_lost`로 재시도 소진과 같이 끝낸다(`exhaust`).
- **상시 작업자**(`worker/service.py`). `serve(deps, config, stop=…, listener=…)`가 `concurrency`개의 슬롯을 `TaskGroup`으로 돌린다. 슬롯은 작업을 꺼내 처리하고, 없으면 알림이나 폴링 시각이나 종료 신호를 기다린다. 알림을 놓치지 않으려고 깨움을 순번(`_Wakeups.sequence`)으로 센다. 슬롯은 꺼내기를 시작하기 전의 순번을 기억하고, 꺼낼 작업이 없었는데 그사이 순번이 바뀌었으면 기다리지 않고 바로 다시 꺼낸다. 듣기를 꺼내기보다 먼저 시작하고, 듣기가 서기를 기다리는 동안에도 종료 신호를 본다(리뷰가 짚은 틈이다). `TransientFailure`는 `worker_database_unavailable` 경고를 남기고 다음 반복으로 넘어간다. 듣기가 연결 오류 밖의 예외로 죽으면 `job_listener_failed`를 남기고 폴링으로 계속 돈다.
- **작업 알림 듣기**(`adapters/postgres/notifications.py`). `JobNotificationListener`는 자기 연결로 `LISTEN rag_jobs`를 하고, 연결이 끊기면 `retry_seconds` 뒤 다시 붙으며 다시 붙은 직후 한 번 깨운다(끊긴 사이의 알림을 메우려는 것이다).
- **종료 신호**(`worker/signals.py`). SIGTERM, SIGINT, Windows는 SIGBREAK를 받는다. `asyncio.add_signal_handler`는 Windows에서 쓸 수 없어 `signal.signal`로 처리기를 달고 `call_soon_threadsafe`로 표지를 세운다. Selector 루프는 소켓을 기다리는 동안 신호로 깨지 않으므로 소켓 쌍과 `set_wakeup_fd`로 루프를 깨운다. 신호 처리기는 조립(Kiwi 예열이 수 초 걸린다)보다 먼저 단다.
- **연결 풀 크기**(`adapters/postgres/engine.py`, `worker/assembly.py`). 슬롯 하나가 작업 단위 하나와 임대 연장 하나로 연결을 둘까지 동시에 쥔다. `RAG_WORKER_CONCURRENCY`에 상한이 없어 8 이상이면 기본 풀 상한(15)을 넘고, 모자라면 30초 기다린 뒤 SQLAlchemy의 `TimeoutError`로 슬롯이 죽어 작업자 전체가 멈춘다. `create_engine(url, at_least_connections=…)`로 상한을 넓히고 작업자 조립이 `concurrency × 2`를 준다.
- **청킹을 스레드로 넘기지 않기로 했다**. 문장 분리와 키워드 토큰화는 동기 CPU 호출이고 Kiwi 호출은 어댑터가 잠금으로 직렬화해 스레드로 넘겨도 속도가 늘지 않는다. 임대를 잃은 시도는 작업 행 조건에 걸려 쓰지 못하므로 데이터는 어긋나지 않는다. 다만 인수마다 시도 횟수가 오르므로 임대보다 오래 루프를 막는 문서는 인수가 되풀이되다 `worker_lost`로 끝날 수 있다(기본 임대가 600초라 드물다). `worker/assembly.py` 독스트링과 티켓에 적었다.
- **`worker` 명령**(`main.py`). 인자 없이 설정만 읽고 `run_in_selector_loop(run_worker(settings))`로 돈다.
- **로그 이벤트**. 명세 235행의 목록은 `http_request`, `search`, `job_started`, `job_finished`를 예로 든다. 작업자 수명을 운영자가 보도록 `worker_started`, `worker_stopped`, `worker_database_unavailable`, `job_listener_disconnected`, `job_listener_failed`, `lease_extension_failed`를 더했다. 12가 `job_crashed`를 더한 것과 같은 방식이고 명세는 고치지 않았다. 연결 오류의 메시지는 싣지 않는다(원칙 V).

## 손으로 본 것

- 어댑터와 앱 시험은 구현 앞에 썼다. `finish`와 `extend_lease`를 예외로 바꿀 때도 시험을 먼저 바꿔 `DID NOT RAISE AttemptLostError` 빨강을 본 뒤 구현했다.
- 처음부터 초록이던 시험은 `tools/mutate.py`의 표(`.scratch/core/probes/lease_worker_mutations.toml`)로 변이를 돌렸다. 표는 스물두 개다(스물두 번째는 PR 직전 리뷰 뒤에 더했다). 연장 간격, 임대를 잃은 시도의 취소, 소진 판정의 경계, `worker_lost` 코드, 끝내기와 연장이 쓰지 못한 것을 알리는 둘, 연장의 일시 실패 처리, 연장의 예기치 않은 오류 처리, 재접속 직후의 깨움, 꺼내기의 일시 실패, 슬롯 수, 종료 신호가 쉬는 슬롯을 깨우는 것, 종료 신호 뒤 새 작업을 꺼내지 않는 것, 듣기가 서기 전의 종료 신호, 폴링, 듣기가 죽은 것의 알림, 풀 상한, 깨움 fd다.
- 첫 실행은 표지 문구 넷이 시험 원문에 글자 그대로 있다는 검증에서 아무 파일도 쓰지 않고 멈췄다. 실패 출력에서만 나오는 문구로 바꿨다. 다음 실행에서 표지가 실제 출력과 다른 셋이 어긋났고 고쳐 다시 돌렸다.
- **깨움 fd 변이가 초록이었다**. `set_wakeup_fd`를 끈 변이가 실제 프로세스 시험에서 통과했다. 작은 프로브(스크래치)로 재 보니 psycopg 연결(`LISTEN`)이 없는 Selector 루프는 `CTRL_BREAK_EVENT`로 20초가 지나도 깨지 않았고, `LISTEN` 연결이 하나 있으면 0.16초 만에 깼다. 실제 작업자에는 연결이 항상 있어 그 시험이 깨움 fd를 가려내지 못한다. 깨움 fd가 필요한 때는 듣기가 끊겨 재접속을 기다리는 동안이다. 그래서 `stop_on_signals`만 놓고 다른 스레드에서 신호를 일으켜 루프가 소켓 대기에 든 채 깨는지 보는 시험(`test_worker_signals.py`)을 더했고 변이가 빨강이 되었다. 처음 시도한 "작업이 끝나고 몇 초 쉰 뒤에 신호를 보낸다"는 고침은 근거가 틀려 되돌렸다.
- **변이 표 전체를 돌리자 기준선이 빨갰다**. 임대를 잃은 시도를 취소하는 시험(`test_임대를_잃은_것이_드러나면_…`)이 단독 열 번에 한 번꼴로 빨갰다. 원인이 둘이었고 둘 다 측정으로 확인했다.
  - 첫째는 Kiwi 첫 호출이다. 새 프로세스에서 `tokenize_keywords("준비")`가 이 PC에서 4.7~5.3초 걸렸다(어댑터 주석의 1초쯤과 다르다). 시험이 `process_job`을 직접 부르므로 이 적재가 `time.monotonic() - started < 5` 안에 들어갔다(실패 때 5.47초). 작업자 조립은 기동 때 예열하지만 시험은 조립을 거치지 않는다. 같은 원인을 `tests/conftest.py`의 서버 fixture가 이미 고친 선례가 있어 `build_pipeline`에서 같은 예열을 한다. 고친 뒤 호출 시간은 1초쯤이다.
  - 둘째는 `FOR UPDATE SKIP LOCKED`다. 끼어들기 함수가 `Pipeline.claim("worker-2", later=…)`를 부르는 순간 `_keep_lease`의 연장 트랜잭션이 작업 행을 잠그고 있으면 꺼내기가 그 행을 건너뛰어 `None`을 돌려주고, `assert job is not None`이 `job_crashed`를 만들었다. 제품의 올바른 동작이고 시험이 그 경합을 가정하지 않은 것이다. `Pipeline.claim`이 5초 기한 안에서 다시 시도한다. 끼어들기 함수 세 곳이 이 공용 함수를 부른다.
  - 고친 뒤 같은 시험을 단독으로 스무 번 돌려 모두 초록이었다.
- **변이 12(종료 신호가 쉬는 슬롯을 깨우지 않는다)가 초록이었다**. 시험이 듣기가 선 직후 곧바로 `stop`을 켜서, 슬롯이 첫 꺼내기를 하기도 전에 `while not stop.is_set()`에서 반복을 마칠 수 있었다. 쉬는 자리에 든 적이 없으니 `poke()`를 지워도 통과했다. `WatchedUnitOfWork`(`tests/support/interleaving.py`)로 첫 꺼내기의 작업 단위가 끝난 것을 기다린 뒤 종료를 건다. 슬롯은 그 작업 단위가 끝나면 멈추는 지점 없이 쉬는 자리로 들어간다. 시험을 열 번 반복해 초록이었고 변이 12는 66초 뒤 `TimeoutError`로 빨강이 되었다. 변이 표 스물한 개가 모두 기대대로이고, 열두 표를 `--check`했다.
- **Dockerfile**. Dockerfile은 바꾸지 않았다(CMD는 `serve`이고 `worker`는 명령 덮어쓰기로 돈다). 이미지를 짓고 테스트 PostgreSQL에 임시 데이터베이스를 만들어 이미지 안에서 `rag-engine migrate`와 `rag-engine worker`를 띄운 뒤 `docker stop`(SIGTERM)을 보냈다. 종료 코드 0과 `worker_started`, `worker_stopped` 로그를 보았고 리눅스 갈래의 우아한 종료도 이로써 한 번 본 셈이다. 임베딩 끝점 설정(`RAG_DEFAULT_EMBEDDING_URL`)이 빠지면 칸 이름만 알리고 종료 코드 1로 끝나는 것도 이미지에서 보았다. 임시 컨테이너, 데이터베이스, 이미지는 지웠다. CI의 `image` 잡은 `serve`와 `/health`만 보므로 이 확인은 손으로 한 것이다.
- 코드가 옮겨 가서 기존 표 `retries_mutations.toml`의 변이 하나(실패한 시도의 파싱 지연)의 원문이 0번이 되었다. `_index`로 옮겨 간 새 위치로 고치고 다시 돌려 빨강을 확인했다. 변이 표 열두 개 전부를 `--check`했다.
- **검사 러너**. 첫 전체 실행(리뷰 반영 전 코드)은 전부 초록이었다(pytest 329초). PR 직전 리뷰의 고침을 넣은 뒤 다시 돌린 전체 실행은 3593개 통과, 1개 실패였다. 실패는 `tests/adapters/test_parse_runner.py`의 멈춘 자식 기한 시험(Windows 기대 `parse_failed`에 `parse_timeout`이 옴)이고, 단독으로 세 번 돌리면 모두 초록이다. 이 브랜치는 파서 쪽 파일을 바꾸지 않았다. 12가 열린 일로 적어 둔 `test_parse_runner`의 부하 민감성 그대로이고, 부하에서만 빨간 시간 시험은 대기열의 닫힌 항목이 받아들인 종류라 일지에만 적는다. 커밋 훅이 같은 러너를 한 번 더 돈다.

## 코드 리뷰

`/code-review`를 돌렸다. 범위는 base `20b38c7`, 수정한 파일 8개, 추적하지 않는 새 파일 10개, 커밋 0개다. 표준 축(sonnet / high)과 명세 축(세션 모델)이 따로 보았다. 둘 다 Critical과 Major는 없었고 Minor가 여럿이었다. 근거는 코드에서 다시 열어 확인했다.

**고친 것**

- `finish`와 `extend_lease`의 `bool` 반환(표준 축이 근거 틀림, 명세 축이 CQS 위반으로 지적). 위 "정한 것"의 예외로 바꾸었다.
- 시작 도중 종료 신호가 듣기 서기를 기다리느라 무시되었다(명세 축 실측: 가짜 듣기와 폴링 5초에서 0.5초에 신호를 세웠더니 5.01초에 끝남). `_until_any`로 듣기와 종료 표지를 함께 기다린다. 신호 처리기도 조립 앞으로 옮겼다.
- 듣기가 연결 오류 밖의 예외로 죽으면 로그 없이 폴링만 남았다(양 축). `job_listener_failed`를 남긴다. 예외의 메시지는 싣지 않는다.
- 풀 크기(명세 축): 위 "정한 것"의 `at_least_connections`.
- "삼분의 일"이 시험으로 고정되지 않았다(양 축): `extension_interval_seconds`를 공개해 시험으로 고정하고 변이를 더했다. 연장의 일시 실패 갈래(`lease_extension_failed`)와 폴링만으로 깨어나는 경로도 시험과 변이가 없어 더했다.
- 낡은 문장: `app/index_document.py` 머리글의 "임대 연장(13)은 뒤 티켓이 채운다", 티켓 13의 `run_once`가 임대 연장이 없다는 문장, "정확성은 지켜지고 처리량만 잃는다"(`processing.py`, `assembly.py`, 티켓)는 반만 맞아서 고쳤다. `_EXTENSIONS_PER_LEASE` 주석의 "한두 번 실패해도"는 한 번만 맞아서 고쳤다(둘이 연속 실패하면 셋째 시도가 만료 시각에 온다). `signals.py`의 Windows SIGTERM 서술은 Python의 `os.kill`과 `send_signal`이 `TerminateProcess`를 부르는 동작이라고 고쳤다.
- `signals.py`: 소켓 쌍을 닫지 않고 새는 경로가 있었다(`add_reader`가 `NotImplementedError`를 내면 정리가 안 된다. 리뷰가 `ResourceWarning`으로 재현했다). 등록을 `try` 안으로 옮겼고 Selector 루프에서만 부를 수 있다고 적었다.
- `README.md`의 구조 줄에 `worker` 명령과 `worker/` 파일을 적었다. `test_worker_command.py` 머리글은 시험이 실제로 보는 것(종료 코드 0)에 맞췄다.

**남긴 것과 이유**

- `process_job(lease_seconds=None)` 갈래(표준 축 Speculative Generality, 명세 축 범위 넘침 가벼움): 기존 시험 약 사십 곳이 임대 없이 한 번에 끝나는 처리를 쓴다. 독스트링이 시험용이라고 밝혔다. 임대 기간을 필수로 하고 그 시험이 값을 주면 사라지며, 지금 그것을 하면 이 티켓과 무관한 시험 변경이 크다.
- `(worker_id, lease_seconds)`가 `run_once`, `claim`, `process_job`, `WorkerConfig`로 따로 다니고 `run_once`와 `_slot`에 꺼내기 꼴이 반복된다(표준 축 냄새). `run_once`는 07의 시험과 첫 왕복 입구라 그대로 둔다. 둘이 같이 바뀌어야 하는 일이 생기면 합친다.
- 종료 경합(명세 축): `while not stop.is_set()` 검사와 꺼내기 사이에 신호가 오면 새 작업 하나를 꺼내 끝까지 처리한다. 창이 좁고 처리는 끝까지 마치므로 데이터는 어긋나지 않는다.
- `_slot`이 `TransientFailure`만 받는다(명세 축): `finish`의 `IntegrityError` 같은 예기치 않은 예외는 `process_job`이 `job_crashed`로 받는다. 꺼내기의 비일시 예외(스키마 없음 등)는 작업자가 떠들썩하게 죽는 것이 맞다고 보았다. 풀 고갈은 위 풀 크기로 막았다.
- `signals.py`의 신호 처리기를 조립 앞에 단 것과 `try` 안의 등록 순서는 단위 시험으로 보이기 어려워 시험을 더하지 못했다. 실제 프로세스 시험과 이미지 확인이 정상 경로를 본다.

**PR 직전 리뷰에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `worker/signals.py` 머리글: Python은 Windows에서 다른 프로세스에 SIGTERM을 보낼 때 신호를 전달하지 않고 `TerminateProcess`로 끝낸다. Selector 루프가 아니면(Windows의 기본 ProactorEventLoop) `add_reader`가 `NotImplementedError`를 낸다. Windows의 Selector 루프는 연결이 없으면 신호로 깨지 않는다(프로브로 20초 넘게 멈춤을 보았고, `LISTEN` 연결이 있으면 0.16초 만에 깼다).
- `worker/processing.py`와 `worker/assembly.py` 머리글: 임대를 잃은 시도는 문서에도 작업 행에도 쓰지 못하고, 인수마다 시도 횟수가 오르므로 임대보다 오래 루프를 막는 문서는 `worker_lost`로 끝날 수 있다.
- `_EXTENSIONS_PER_LEASE` 주석: 간격은 앞 연장이 끝난 뒤부터 세고, 연장 한 번이 임대 기간의 삼분의 일 안에 실패로 돌아오면 임대가 끝나기 전에 한 번 더 시도한다(PR 직전 리뷰가 앞 문장의 반례 `d > L/3`을 짚어 조건을 붙였다).
- `domain/ports.py`: `finish`와 `extend_lease`는 작업 행 조건에 걸리면 `AttemptLostError`를 올린다.
- `adapters/postgres/engine.py`: 동시에 쥘 수 있는 연결의 기본 상한은 15(풀 크기 5와 넘침 10, SQLAlchemy의 기본값과 같다)이다.
- 티켓 13의 07이 넘긴 것 단락: `run_once`는 동시 처리가 없고 임대 연장은 `process_job`이 한다.

## PR 직전 리뷰

보안은 내장 `security-review`(지적 없음), 버그·성능은 `bug-perf-review` 에이전트가 봤다. 범위는 base `20b38c7`, 파일 24개(추적 14, 미추적 10), 커밋 0개다. 보안 쪽은 `LISTEN` 문의 식별자가 상수이고 알림 페이로드를 읽지 않는 것, 예외 메시지가 서드파티 예외면 로그에 실리지 않는 것(`log_format.py`의 `_exception_payload`)을 코드에서 확인해 지적 없음으로 끝냈다. 버그·성능 쪽 보고는 Major 하나와 Minor 넷이고, 근거를 코드에서 다시 열어 판정했다.

**고친 것**

- **Major, `_keep_lease`가 예기치 않은 예외로 죽으면 건강한 작업이 영구 실패한다**. `_index`의 `keeper.result()`가 그 예외를 다시 올리고 `finally`가 작업을 취소하며 `_run`의 `except Exception`이 `internal_error`로 재시도 없이 끝낸다. 코드를 읽어 맞는 경로임을 확인했고, 시험(`test_임대_연장이_예기치_않게_실패해도_…`)을 먼저 써서 `['job_started', 'job_crashed', 'job_finished']`로 빨강을 본 뒤 `_keep_lease`가 `Exception`을 받아 `lease_extension_failed`를 오류 수준으로 남기고 다음 간격에 다시 하게 했다. 연장이 계속 실패하면 임대가 끝나 다른 작업자가 인수하고 그 시도는 `AttemptLostError`로 정리된다. 변이 22번이 이 갈래를 지킨다(`except`를 다른 예외로 바꾸면 `job_crashed`로 빨강). `FlakyUnitOfWork.fail_next`가 `error=`로 예기치 않은 예외를 받는다.
- **Minor, `_EXTENSIONS_PER_LEASE` 주석의 조건**. 간격은 앞 연장이 끝난 뒤부터 세므로 재시도 시각이 `2L/3 + d`이고 `d > L/3`이면 임대가 끝난 뒤다. 위 "밀 주장"의 문장을 조건부로 고쳤다.
- **Minor, Kiwi 적재 시간 서술의 어긋남**. `assembly.py`의 "약 1초"와 `pipeline.py`의 "4.7~5.3초"가 달랐고 새 프로세스에서 다시 재니 2.6초였다. 다른 검사가 도는 정도에 따라 흔들리므로 `assembly.py`는 "수 초", `pipeline.py`는 "2.6~5.3초(부하에 따라)"로 맞췄다. 어댑터(`kiwi.py`)의 "1초쯤" 주석은 07의 것이라 이 티켓에서 건드리지 않았다.
- **Minor, `signals.py` 머리글**. "Windows의 Selector 루프는 신호로 깨지 않는다"에서 조건(열린 소켓 연결이 하나도 없으면)이 빠져 있었다. 조건을 넣었고, 처리기가 표지를 세우는 것뿐이라 두 번째 신호도 같다는 것과 강제로 끊은 작업이 임대 기간 동안 `running`으로 남다 인수된다는 것을 적었다.

**남긴 것과 이유**

- **Minor, `_slot`이 `TransientFailure`만 받아 비일시 DBAPI 오류가 TaskGroup을 통째로 무너뜨린다**(보류로 보고). 위 코드 리뷰의 "남긴 것"에서 이미 정했다. 꺼내기의 비일시 예외(스키마 없음 같은 것)는 작업자가 큰 소리로 죽는 것이 맞다고 보았고, 죽어도 작업은 `running`으로 임대가 끝나면 다른 작업자가 인수한다. 보고가 짚은 `_finish`·`_settle`의 비일시 실패도 같은 길이다.

**밀 주장 대조**: 보고가 1(SIGTERM과 Proactor는 확인, Selector 조건은 위에서 고침), 2, 4, 5, 6, 7을 코드에서 맞다고 보았다.

## 회고

낸 후보는 아홉이고 판정은 승인 0, 기각 9, 넘김 0이다. 대기열은 열린 항목이 26개이고 만료할 항목이 없었다. 후보 4는 같은 일을 다룬 항목을 `queue_open_rows.py --search`로 찾았으나 없었다. 후보 6은 닫힌 항목 `token-expiry-test-load-margin`이 맞았다.

1. **변이 표의 표지 문구가 시험 원문에 글자 그대로 있었다**(첫 실행이 아무 파일도 쓰지 않고 멈춤). 기각. `tools/mutate.py`가 쓰기 전에 그 자리에서 막았고 고칠 것이 도구에 남지 않았다(이미 있는 검사가 막음).
2. **101줄 heredoc, `.env`에 닿는 Grep glob**. 기각. 각각 `PreToolUse` 훅이 그 자리에서 막았다(이미 있는 훅이 막음).
3. **`finish`와 `extend_lease`가 쓰면서 `bool`을 돌려주었다**(CQS). 기각. 표준 축 리뷰가 `CODING_STANDARDS.md`의 기준으로 잡았으니 리뷰가 제 몫을 한 것이라 회차로 세지 않는다. 반환 모양의 의미는 린터가 판정할 수 없다.
4. **낡은 미래형 문장("임대 연장(13)은 뒤 티켓이 채운다")과 "처리량만 잃는다"의 과장**. 기각. 두 축 리뷰가 잡았고 `code-review`의 주장 검증 목록(1 닫힌 주장, 4 미래형)이 이미 겨누는 자리다. 이 일을 다룬 열린 항목은 없었다.
5. **깨움 fd 변이가 실제 프로세스 시험에서 초록이었다**. 처음 고침(작업 뒤에 쉬었다 신호를 보낸다)은 측정 없이 경합을 원인으로 가정했다. 프로브로 재 보니 원인은 `LISTEN` 연결이 루프를 깨우는 것이었고, 고침을 되돌린 뒤 단위 시험을 더했다. 기각. 변이 단계가 시험의 판별력 부족을 드러낸 것이니 `implement` 스킬이 의도한 대로 돈 사건이고, 추측 수정을 멈추라는 작업 규약 6이 이미 있다. 같은 실수의 첫 사건이다.
6. **시험의 시간 단언 안에 Kiwi 첫 적재가 들어 있었다**(단독 열 번에 한 번 5.47초). 기각. 대기열의 닫힌 항목 `token-expiry-test-load-margin`이 "부하에서만 빨간 시간 시험"을 받아들이고 닫았다(끝이 열린 결함 종류의 닫기. 다시 열지는 사용자가 정한다). 규칙대로 새 사례는 잇지 않고 일지에만 적는다. 원인(앱이 아니라 시험 공장이 Kiwi를 예열하지 않음)은 그 항목이 고친 것과 같다. 세션 전체에 자동 예열을 거는 길은 Kiwi가 필요 없는 시험까지 5초씩 늘려 택하지 않았다.
7. **변이 12가 초록이었다**(시험이 슬롯이 쉬기도 전에 종료를 걸었다). 기각. 변이 단계가 시험의 판별력 부족을 드러내 `implement` 스킬이 의도한 대로 돈 사건이다. 후보 5와 같은 종류(변이가 시험의 구멍을 드러냄)의 둘째 사건이지만 이미 있는 변이 검사가 그 자리에서 알렸으므로 회차로 세지 않는다.
8. **`Pipeline.claim`이 `SKIP LOCKED`로 건너뛴 순간을 실패로 읽었다**. 기각. 시험 공용 함수의 결함이고 같은 시험을 열 번 반복하는 손 확인이 잡았다. 자동 검사로 옮길 수 있는 꼴이 아니다(경합 창이 좁아 한 번 돌려서는 안 보인다).
9. **연장 작업이 받지 않은 예외로 죽어 건강한 작업이 실패로 끝나는 길**. 기각. PR 직전 `bug-perf-review`가 잡았고 리뷰 파이프라인이 제 몫을 한 것이다. 예외 갈래를 빠뜨린 실수는 린터나 타입이 판정할 수 없고 `CODING_STANDARDS.md`에 더할 새 판단 기준도 아니다(어느 예외를 삼킬지는 사례마다 다르다). 시험과 변이 22번을 더해 고쳤다.

## 다음

- 티켓 13은 이 PR로 닫힌다. core의 열린 티켓은 14(재색인과 판 전환)와 15(조회와 `ingest` 명령), 16(검색 지연 프로브)이다. 14는 이제 막힌 곳이 없고 16은 14와 15가 막는다. 열린 티켓이 남아 있어 기능 계획의 `**끝:**` 줄을 더하지 않았다.
- 13이 각 티켓에 넘긴 것:
  - 14: `process_job`이 `lease_seconds`를 받아 임대를 늘리며, 14가 지식베이스 행 잠금을 `index_document`의 셋째 단계로 올릴 때 연장 작업은 작업 행 하나만 쓰므로 잠금 순서를 거스르지 않는다(`extend_lease`의 독스트링). 재색인 작업이 오래 걸려도 연장이 임대를 지킨다.
  - 15: `main.py`에 `worker` 서브파서와 `_worker()`가 들어갔다(티켓 15의 명령들과 같은 파일이라 병합 때 글자 충돌 후보다). `ingest` 명령이 만든 작업은 `LISTEN rag_jobs`로 작업자를 바로 깨운다.
- 열린 일:
  - `FlakyUnitOfWork.fail_next`를 더했으나 12의 열린 일(쓰기 단계가 실패한 시도의 `write_ms` 시험)은 여전히 두 번째 `begin()`을 고르는 도우미가 필요해 하지 않았다. `fail_next`로 이제 쓸 수 있는 길이 생겼다.
  - 위 "남긴 것"의 `lease_seconds=None` 갈래와 `run_once`의 꺼내기 중복은 시험 변경이 큰 정리라 따로 둔다.
  - 12가 남긴 열린 일(`token_store`의 오류 번역, 지식베이스 ID 순 잠금 세 벌, `test_parse_runner`의 기한 시험과 `serve` 기동 시험의 부하 민감성)은 이 티켓의 범위가 아니라 그대로다.
