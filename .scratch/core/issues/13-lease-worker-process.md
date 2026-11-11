# 13: 임대와 인수, 작업자 프로세스

**What to build:** 운영자가 `rag-engine worker`를 서버와 따로 띄우면 작업자가 `NOTIFY`로 바로 깨어나 작업을 여럿 함께 처리하고, 종료 신호를 받으면 진행 중인 작업을 끝낸 뒤 나간다. 작업자가 죽으면 임대가 끝난 뒤 다른 작업자가 그 작업을 가져가고, 늦기만 한 작업자의 시도는 문서에도 작업 행에도 쓰지 못한다.

**Blocked by:** 12 (재시도와 오류 번역)

**Status:** ready-for-agent

**07이 넘긴 것:** 작업 꺼내기(`PostgresJobQueue.claim`: `FOR UPDATE SKIP LOCKED`, 임대가 끝난 `running` 포함, 시도 횟수 +1, 올린 세대 비움)와 끝내기(`finish`), 작업 행 조건(`JobQueue.hold_attempt`가 작업 행을 잠그고 작업자 ID와 시도 횟수의 일치를 보며, 어긋나면 `AttemptLostError`로 작업 단위를 롤백한다)은 07이 구현했다. `hold_attempt`(12가 `app/job_attempt.py`의 함수로 옮겼다)는 `index_document`의 네 쓰기 단위와 12가 더한 다시 예약하기·재시도 소진(`app/job_failure.py`)의 두 작업 단위가 모두 부른다. 이 티켓은 임대 연장(`extend_lease`는 아직 `NotImplementedError`)과 인수의 소진 갈래(`worker_lost`), 작업자 프로세스를 더한다. 07의 한 번 돌기(`run_once`)는 작업을 하나씩 차례로 처리하는 입구라 동시 처리와 임대 연장이 없다. 청킹의 문장 분리와 `tokenize_keywords`는 동기 CPU 호출이라 07은 스레드로 넘기지 않고 이벤트 루프 안에서 그대로 부른다(`kiwipiepy`의 스레드 안전성을 확인하지 못해 어댑터가 호출을 잠금으로 직렬화한다. 스레드로 넘겨도 인스턴스를 동시에 쓰지는 않지만 호출이 차례로 돌아 속도는 늘지 않는다). 큰 문서에서 이 호출이 이벤트 루프를 막으면 같은 루프의 임대 연장 작업이 늦어져 임대를 잃을 수 있으므로, 이 티켓이 동시 처리를 넣을 때 스레드로 넘길지 정한다. Kiwi 모델은 작업자 조립이 기동할 때 `tokenize_keywords("준비")`로 한 번 불러 예열한다(`worker/assembly.py`). 작업자 ID는 `worker/assembly.py`의 `worker_id()`가 호스트 이름과 PID로 만든다. `finish`는 작업 행 조건에 막혀 0행이 갱신되어도 알리지 않아서, 마지막 쓰기 단위 뒤 끝내기 전에 임대를 잃으면 `process_job`이 `job_finished`의 `result`를 `succeeded`로 남긴다(작업 행은 새 작업자의 것으로 남아 데이터는 어긋나지 않는다). 임대 연장과 인수를 넣는 이 티켓이 `finish`가 갱신 여부를 알리게 하고 그 경우의 로그를 `lost`로 맞춘다. 작업자가 서버 없이 도는 입구(`run_once_with_settings`)는 07이 `configure_logging`을 부르게 해 두었으니, 상시 작업자 프로세스도 같은 조립을 거친다.

- [ ] 임대: 처리 중 `RAG_JOB_LEASE_SECONDS`의 삼분의 일마다 임대를 늘린다. 임대 연장도 작업 행 조건(작업자 ID와 시도 횟수가 꺼낼 때 값 그대로)을 지나고, 아니면 그 시도를 버린다(명세 "수집 파이프라인과 작업" 절의 잠금 규칙). 작업자 ID는 호스트 이름과 PID다.
- [ ] 인수: 임대가 끝난 `running` 작업을 다른 작업자가 꺼내면 시도 횟수를 올리고 올린 세대를 비운다. 시도 횟수가 이미 `RAG_JOB_MAX_ATTEMPTS` 이상이면 다시 돌리지 않고, 꺼낸 작업 단위를 커밋한 뒤 이어지는 작업 단위가 잠금 순서대로 잠가 재시도 소진과 같이 `worker_lost`로 끝낸다.
- [ ] 작업자 프로세스: `LISTEN rag_jobs`로 깨어나고 `RAG_WORKER_POLL_SECONDS`마다 폴링하며 `RAG_WORKER_CONCURRENCY`개를 비동기로 함께 처리한다. SIGTERM·SIGINT(Windows는 SIGBREAK)를 받으면 새 작업을 꺼내지 않고 진행 중인 작업을 끝낸 뒤 나간다. `worker` 명령은 인자 없이 설정만 읽는다.
- [ ] 킥오프의 Dockerfile 하나에서 `rag-engine worker`가 돈다(이미지를 둘로 가르는 것은 release-image).
- [ ] 어댑터 시험: 두 작업자가 같은 작업을 꺼내지 않는다, 임대 만료 뒤 다른 작업자의 인수(`RAG_JOB_LEASE_SECONDS=1`).
- [ ] 작업자 프로세스를 실제로 띄우는 시험 하나: `rag-engine worker`를 하위 프로세스로 띄워 `NOTIFY`로 깨어나 작업을 처리하고 종료 신호에 끝나는 것을 본다(리눅스는 SIGTERM, Windows는 `CTRL_BREAK_EVENT`를 보내는 플랫폼 갈래이고 skip이 아니다). `RAG_WORKER_POLL_SECONDS`는 단언의 기한보다 크게 두어 폴링으로 지나가지 않게 한다(스토리 28, 34).
- [ ] 교차 시험(메모리 안 가짜 포트는 09도 10도 만들지 않았다. 10의 `tests/support/interleaving.py` 끼어들기 훅과 실제 테스트 PostgreSQL로 한다): 임대가 끝나 다른 작업자가 같은 작업을 가져가면 처음 작업자는 문서에도 작업 행에도 쓰지 않는다, 임대를 잃은 뒤에야 첫째 단계에 든 시도가 세대를 올리지 않는다, 시도 횟수를 다 쓴 작업을 임대 인수로 꺼내면 다시 돌리지 않고 `worker_lost`로 끝낸다(늦은 시도와 같은 프로세스가 꺼내도 늦은 시도는 쓰지 않는다).
- [ ] 검사 넷이 초록이다.
