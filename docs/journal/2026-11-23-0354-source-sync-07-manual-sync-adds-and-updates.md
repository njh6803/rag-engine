# source-sync 07: 지금 동기화로 새 파일과 바뀐 파일 넣기 · 2026-11-23

source-sync 티켓 06을 닫은 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/source-sync/issues/07-manual-sync-adds-and-updates.md`이고, 브랜치는 `feature/07-manual-sync-adds-and-updates`, 작업은 워크트리 `07-manual-sync-adds-and-updates`에서 했다. 요청 범위는 PR과 병합까지다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 준비

- 읽은 것: 티켓 07, 명세 `.scratch/source-sync/spec.md`의 "동기화의 차례", "수집 정책", "동기화 기록", "작업 대기열", "가져오는 원천의 문서 색인", "관리 API", 06 일지의 "다음"과 "봇 회차", 05의 호출 장치와 04의 서버 경로 커넥터.
- 시험용 PostgreSQL은 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`로 붙여 돌렸다.
- 하위 작업 둘을 썼다. 관리 API와 응답 모델 쪽(`POST /sources/{name}/sync`, 동기화 기록 두 조회, 원천 응답의 `last_sync`)과 막힌 호출 시험(`test_sync_hung_calls.py`, 가짜 커넥터 `hanging_connectors.py`)을 맡겼고, 결과는 이 세션이 코드와 시험을 읽고 다시 돌려 확인했다.

## 지은 것

- **도메인.** 작업 엔티티의 문서 칸을 비울 수 있게 하고(원천 단위 작업은 `source_id`와 `options`를 든다), 작업 종류를 다섯으로 늘렸다(`index_document`, `sync_source`, `delete_source`, `restore_source`, `cleanup`). 오류 코드 다섯(`source_unreadable`, `source_changed`, `source_path_rejected`, `connector_unavailable`, `connector_error`)과 Problem Details 코드 둘(`sync_in_progress`, `sync_record_not_found`)을 더해 작업 코드는 열아홉, HTTP 코드는 스물이다. `SyncRecordStore` 포트를 작업 단위 안의 다섯째 포트로 더했다.
- **어댑터.** `PostgresSyncRecordStore`(`sync_record_store.py`)가 기록을 넣고 읽고 고치고 작업으로 찾고 원천마다 최근 것부터 나누어 읽는다. 대기열이 원천 단위 작업을 `ON CONFLICT`와 문장 글자로 적은 조건(`uq_jobs_source_id_kind_active`)으로 하나만 넣고, `claim`이 색인 작업이 아닌 것을 먼저 묻고 없을 때만 색인 작업을 묻는다. 설정 `RAG_SOURCE_READ_TIMEOUT_SECONDS`(기본 600)를 더했다.
- **유스케이스.** `app/ingest_policy.py`(수집 정책), `app/sync_requests.py`(지금 동기화 요청), `app/sync_source.py`(동기화 작업 한 번)를 새로 지었다. 동기화는 목록을 끝까지 받은 뒤 정책을 적용하고, 후보마다 변경 확인값이나 내용 해시로 대조해 새 문서와 바뀐 문서만 수집 유스케이스로 넣는다. `index_document`는 원본 경로가 빈 문서의 원본을 커넥터로 읽는다.
- **작업자.** `worker/processing.py`가 작업 종류로 갈라 처리하고, 동기화가 도는 동안 작업 담당 기록의 기한을 늘린다.
- **서버.** `POST /sources/{name}/sync`(202, `{sync_record_id, job_id}`), `GET .../sync-records`, `GET .../sync-records/{id}`, 원천 응답의 `last_sync`, 작업 조회 응답의 `source` 칸.
- **시험.** 새 시험 파일: `tests/app/test_ingest_policy.py`, `test_sync_source.py`, `test_sync_source_formats.py`, `test_sync_source_connector_faults.py`, `test_sync_hung_calls.py`, `tests/adapters/test_job_queue_source_jobs.py`, `test_sync_record_store.py`, `tests/server/test_admin_sync.py`, `test_sync_round_trip.py`. 시험 도우미 `tests/support/` 아래 `scripted_connectors.py`, `sync_world.py`, `leaky_connectors.py`, `hanging_connectors.py`. 변이 표는 `.scratch/source-sync/probes/sync_mutations.toml`이다.

## 이 세션이 정한 것

- **제외 패턴의 glob은 정규식으로 옮기지 않고 직접 맞춘다.** 처음에는 glob을 정규식으로 바꿨다. 셀프 리뷰가 `*a*a*a…*b` 꼴에서 정규식이 되짚기로 지수 시간이 걸린다고 짚었다. 이 세션이 `"a"*60+".pdf"`에 `*a`를 되풀이해 재 보니 다섯 번에 0.178초였고 한 번 늘 때마다 약 10배였다. 명세 축은 `*a`를 여덟 번 되풀이하면 1분을 넘겼다고 보고했다(이 세션이 그 값을 다시 재지는 않았다). 동기화는 이 대조를 이벤트 루프 위에서 돌리고(작업 담당 기록의 기한을 늘리는 일도 같은 루프에 있다), 명세는 패턴 50개 200자까지 받는다. 지금은 맞을 수 있는 패턴 위치의 집합을 글자마다 밀고 가서 비용이 글 길이와 패턴 길이의 곱으로 묶인다. 같은 패턴의 시험은 별 열두 개와 글자 60개로 정규식이면 사실상 끝나지 않는 크기를 준다.
- **패턴과 키는 맞춰 볼 때만 NFC로 맞춘다.** 명세는 키를 정규화하지 않는다고 하므로 키 자체는 디스크의 이름 그대로 둔다. 풀어 적은 한글 폴더(`임시`가 풀려 적힌 것)에 합쳐 적은 패턴이 맞지 않는 것을 명세 축 리뷰가 짚었고, 대조하는 자리에서만 둘을 NFC로 맞췄다.
- **`reread` 옵션은 받아 기록에만 남긴다.** 티켓 12번째 항목이 뜻은 08과 09가 붙이고 이 티켓은 받아 기록의 옵션 칸에 남기라고 했다. 처음에는 동기화 안에서 변경 확인값이 같아도 읽게 했는데, 실패하거나 건너뛴 문서의 색인 작업을 다시 넣지 않는 반쪽 동작이었다. 셀프 리뷰 뒤에 이 동작과 시험, 변이를 걷어 냈다. 뜻은 09가 붙인다.
- **잠금 순서는 동기화 기록 행이 먼저이고 작업 행이 마지막이다.** `_exhaust_source_job`이 작업 행을 먼저 잠그고 기록을 고치던 것을 순서를 바꿨다. 아래 "셀프 리뷰"에 이유를 적었다.
- **한도가 큰 `list()`의 상한 없는 큐는 이 티켓에서 상한을 두지 않는다.** 티켓 19번째 항목이 04의 서버 경로 커넥터가 걷는 스레드와 이벤트 루프 사이에 둔 상한 없는 큐를 동기화가 목록을 소비하는 속도를 보고 판단하라고 했다. 동기화는 목록 항목마다 딕셔너리에 한 칸을 넣을 뿐이고 데이터베이스나 파일 읽기를 하지 않는다. 그래서 소비 쪽이 생산 쪽(디스크를 걷는 스레드)보다 느려지는 일이 없다고 따져서 상한을 더하지 않았다. 이 판단은 따져서 낸 것이고 큰 폴더로 재 본 값이 아니다. 끝없는 목록의 상한은 db-source가 받는다(명세의 "받는 것" 목록).
- **원천이 지워졌거나 없는 동기화는 지금 `RuntimeError`다.** 지움 표시를 보는 자리는 티켓 11이 더한다고 티켓이 적었다. 그 전까지 지운 원천에도 `POST .../sync`가 202로 답한다.

## 겪은 것

- python-docx가 파일에 만든 시각(초 단위)을 넣어서 "내용은 같고 변경 확인값만 바뀐" 시험이 가끔 빨개졌다. 같은 바이트 객체를 한 번만 만들어 쓰게 고쳤다.
- 변이 도구가 `expect_output = ["assert"]`를 거절했다. 시험 소스에 그 글자가 그대로 있어서다. 변이마다 그 단언이 빨개질 때만 찍히는 출력 글을 골랐다.
- 시험 안의 `type: ignore`와 `ConnectorError.__new__` 우회를 `UUID`와 정식 생성자 호출로 고쳤다(원칙 II).
- 편집기의 진단이 여러 번 낡은 값(없는 import, 모르는 타입)을 띄웠다. 판정은 `uv run pyright`의 종료 코드로만 했다.
- 왕복 시험의 첫 실행이 빨갰다. 문서 제목은 파일 이름에서 확장자를 뗀 것(`지침`)이라 내가 본문의 제목을 기대한 것이 틀렸다. 갱신된 내용이 검색에 닿았는지는 검색 조각의 본문으로 보게 고쳤다.

## 셀프 리뷰

`/code-review`를 고정점 `origin/dev`(base `39e4c61`)로 돌렸다. 본 범위는 고친 추적 파일 30개, 미추적 파일 18개, 커밋 0이다. 표준 축은 Sonnet(노력 high), 명세 축은 이 세션의 모델로 돌렸다. 명세 축에는 상태와 동시 요청이 있어 전이 교차 (d)를 붙였다.

### 보고(요약)

- **표준 축.**
  - **Major.** 제외 패턴 정규식의 지수 시간(위 "정한 것").
  - **주장 검증의 거짓.** `SourceReader` 독스트링이 "올리는 예외는 다섯"이라 쓰고 넷을 나열했다. `ConnectorUnavailableError` 독스트링이 동기화의 `connector_unavailable`을 뒤의 티켓이 옮긴다고 미래형으로 썼다(이 티켓이 옮겼다). `EntryPointConnectorRegistry` 독스트링이 "그때 부르는 티켓이 캐시를 더한다"는 미래형을 썼다. 대기열 `claim`의 주석이 프로브 `schedule-once`의 F를 근거로 들었는데 프로브의 질의와 실제 질의의 조건이 글자가 다르다.
  - **Minor.** 같은 키 두 번에서 반복자를 닫지 않는 것, `_open`의 `invalid_config`와 색인 작업의 `not_found`·`too_large`를 직접 보는 시험이 없는 것.
- **명세 축.**
  - **(c) Major.** 제외 패턴 정규식이 되짚기로 폭발한다(위와 같다). 명세 축이 직접 재서 `*a*a*a*a*a*a*b`에 60자 이름이 1.6초, `*a` 여덟 번이면 60초를 넘겼다. 동기화 대조가 이벤트 루프를 막은 채 돌아 기한 연장도 멈추고, 그 시도는 작업 담당 기록을 잃는다.
  - **(a) Major.** 폴더에 PDF, DOCX, HWPX를 두고 동기화한다는 주 이음매 시험이 가짜 폴더와 유스케이스 직접 호출로만 돈다. 명세 "Testing Decisions"는 HTTP 표면과 `RAG_SOURCES_DIR` 임시 폴더를 요구한다.
  - **(c) Minor.** 패턴 `임시`가 풀어 적은 한글 폴더에 맞지 않는다. `**/x.docx`가 맨 위의 `x.docx`에 맞지 않는다.
  - **(a) Minor.** 일시 실패 재예약, 작업 행 조건으로 시도를 버리는 것, 메타데이터 `title`과 NFC 제목, `invalid_config`가 `connector_unavailable`로 끝나는 것을 직접 보는 시험이 없다.
  - **(a) Minor.** 티켓이 04의 상한 없는 큐를 "이 티켓이 보고 판단"하라고 했는데 diff에 판단의 흔적이 없다.
  - **(b) Minor.** `reread`가 동기화 안에서 읽기를 강제한다(뜻은 09의 몫).
  - **(d) Minor.** 동기화가 넣은 문서의 색인이 일시 실패로 재시도를 다 쓰거나, `source_changed` 뒤 파일이 원래 내용으로 돌아와 `_refresh_marker`가 같은 값을 다시 적으면 문서가 `failed`로 남고 값이 같아 읽지도 다시 넣지도 않는다.
  - **(d) Minor.** 잠금 순서가 둘이다. `_mark_running`과 `_close`는 동기화 기록을 먼저 고치고 작업 행을 잠그고, `_exhaust_source_job`은 작업 행을 잠근 뒤 기록을 고친다.
  - **(c) Nit.** 재시도를 다 쓴 동기화의 기록 `failure_code`에 명세가 든 값 밖(`worker_lost`, `internal_error`, `database_unavailable`)이 들 수 있다. `connectors.py`의 미래형 문장 하나.
- **맞게 닫힌 주장.** 오류 코드 수(작업 코드 열아홉, HTTP 코드 스물), 포트 "다섯뿐", `42P10` 주장과 프로브 `schedule-once`의 D3, 변이 표의 `old` 문자열이 소스에 한 번씩 있는 것.

### 판정과 반영

고친 것(코드가 바뀌는 것은 먼저 실패하는 시험을 쓰고 고쳤다).

- 정규식 Major(두 축). 정규식을 걷고 되짚지 않는 매처로 바꿨다(`_tokens`, `_skip_wildcards`, `_advance`, `_glob_matches`). 시험은 `test_별_사이에_같은_글자가_끼어도_지수_시간으로_느려지지_않는다`와 기존 `*`가 이어진 시험이다. 길이 시간 단언은 두지 않았다. 정규식이면 사실상 끝나지 않는 크기를 주어 느린 기계에서 흔들리지 않게 했다. 이 시험의 첫 판은 맞는 쪽 입력의 끝을 `.pdf`로 써서 내가 틀렸고, 고쳤다.
- 풀어 적은 한글(명세 Minor). 맞춰 볼 때만 패턴과 키를 NFC로 맞춘다. 시험 `test_풀어_적은_한글_폴더에도_합쳐_적은_패턴이_맞는다`, 변이를 더했다.
- 명세 (a) Major. `tests/server/test_sync_round_trip.py`를 더했다. 실제 uvicorn 서버와 실제 `server_path` 커넥터와 `RAG_SOURCES_DIR` 임시 폴더, 실제 작업자, MCP `search`로 PDF·DOCX·HWPX 세 문서가 검색에 나오는 것, 숨김 파일과 `.txt`가 `not_accepted`에 드는 것, 파일 하나를 고친 두 번째 동기화가 `updated` 1과 `unchanged` 2이고 검색에 고친 내용만 있는 것을 본다.
- 명세 (b) `reread`. 동기화 안의 처리와 그 시험, 변이 하나를 걷어 냈다. 요청 쪽이 기록의 옵션 칸에 남기는 것만 남았다(`test_admin_sync.py`가 본다).
- 명세 (d) 잠금 순서. `_exhaust_source_job`을 기록 먼저, `hold_attempt` 마지막으로 바꿨다. 작업 담당 기록을 잃은 시도는 `hold_attempt`의 예외로 작업 단위째 되돌려지므로 기록을 먼저 고쳐도 남지 않는다. 시험 `test_작업_담당_기록을_잃은_시도가_재시도_소진으로_끝내려_해도_동기화_기록은_바뀌지_않는다`가 a가 꺼낸 뒤 b가 인수한 장면에서 a의 소진이 `AttemptLostError`로 끝나고 기록이 `queued`인 채인 것을 본다. 교착 자체(두 연결이 서로의 행을 기다리는 것)는 시험으로 재현하지 않았고, 순서를 읽어서 같은 순서로 맞춘 것이다. 이 시험은 순서를 지키지 못한다. `hold_attempt` 호출을 지운 변이도 초록이었다. `jobs.finish`의 `UPDATE`가 작업자와 시도 횟수를 조건으로 걸어 스스로 `AttemptLostError`를 올려서 결과가 같은 동등 변이였고, 그래서 표에서 뺐다. 이 시험이 지키는 것은 "잃은 시도가 기록을 바꾸지 못한다"까지다.
- 명세 (a) Minor 시험. `invalid_config`가 `connector_unavailable`로 끝나는 시험, 색인 작업이 읽을 때 파일이 없어졌거나 `too_large`가 나오면 `source_changed`로 실패하고 변경 확인값이 비는 시험 둘을 더했다.
- 주장 검증. `SourceReader` 독스트링의 "다섯"을 "넷"으로, `ConnectorUnavailableError`의 미래형을 현재형으로, `EntryPointConnectorRegistry`의 캐시 미래형을 지금 상황(동기화는 커넥터를 하나, 색인 작업은 문서마다 한 번 만든다)으로, `claim` 주석의 프로브 근거를 프로브의 질의와 글자가 다르고 이 저장소 시험이 재지 않았다는 말로 고쳤다. `job_attempt.py` 머리에 동기화 작업의 잠금 순서를 더했다.

남긴 것과 이유.

- 같은 키를 두 번 낸 목록에서 반복자를 닫지 않는 것: `SourceReader.list()`의 반환형이 `AsyncIterator`라 `aclose`가 인터페이스에 없다. 버려진 비동기 제너레이터는 이벤트 루프의 마무리 훅이 닫는다. 고치지 않는다.
- `**/x.docx`가 맨 위의 `x.docx`에 맞지 않는 것: 명세 164행은 `/`가 든 패턴을 키 전체에 대고 `**`를 `/`를 넘는 글자 여럿으로 정했다. 문서의 글 그대로의 결과라 고치지 않는다. 맨 위 파일까지 빼려면 패턴을 `x.docx`로 적는다.
- 색인이 재시도를 다 쓰거나 `source_changed` 뒤 같은 값이 다시 적히면 `failed`인 문서가 읽히지도 다시 들어가지도 않는 것: 티켓 09의 세 번째와 열 번째 항목이 이 둘을 정확히 받는다(임베딩 서버가 꺼져 재시도를 다 쓴 문서가 다음 동기화에서 다시 색인된다는 것, `source_changed`로 실패한 문서를 다음 동기화가 다시 읽고 같은 내용이면 색인 작업을 다시 넣는 것). 09가 닫기 전까지는 이 상태가 남는다.
- 기록의 `failure_code`에 명세가 든 값 밖(`worker_lost`, `internal_error`, `database_unavailable`)이 들 수 있는 것: 재시도를 다 쓴 작업의 오류 코드를 그대로 옮기는 설계다. 명세 "동기화 기록"의 실패 사유 목록을 넓히는 일이라 to-spec이 정한다.
- 일시 실패로 다시 예약되는 동안 기록이 `running`으로 남는 것: 다시 예약된 작업이 다음 시도에서 `_mark_running`으로 개수를 비우고 처음부터 돈다. 기록이 `queued`로 돌아가는 상태는 명세에 없다.
- 지운 원천의 동기화가 `internal_error`로 끝나는 것과 지운 원천에 202가 나가는 것: 11이 더한다(위).

밀 주장(PR 직전 리뷰가 겨냥할 새 사실 문장).

- `ingest_policy.py` 머리와 `_glob_matches` 독스트링: 비용이 글 길이와 패턴 길이의 곱이 한계이고 `**`는 이어진 별 둘 이상을 하나로 묶는다. `_matches_pattern` 독스트링: 키는 그대로 두고 맞춰 볼 때만 NFC로 맞춘다.
- `job_failure._exhaust_source_job` 독스트링: 잠금 순서가 동기화 본문과 같고, 잃은 시도는 `hold_attempt`의 예외로 작업 단위째 되돌려져 기록에 남지 않는다.
- `job_attempt.py` 머리: 동기화 작업의 작업 단위는 동기화 기록 행을 먼저 잠그고 작업 행을 마지막에 잠근다.
- `job_queue.claim` 주석: 프로브 F의 수치(1.6ms, 193ms)와 실제 질의의 조건은 `kind IN (…)`이라 글자가 다르고 재지 않았다는 것.
- `EntryPointConnectorRegistry` 독스트링: 동기화 작업은 한 번에 커넥터를 하나, 색인 작업은 원본을 읽을 때 문서마다 한 번 만든다.
- `sync_source._reconcile` 독스트링: `reread`는 기록에만 남고 여기서는 보지 않는다.
- 이 일지의 "큐에 상한을 더하지 않은 판단": 동기화는 항목마다 딕셔너리 한 칸만 넣고 데이터베이스나 파일 읽기를 하지 않아 소비가 생산보다 느려지지 않는다(따져서 낸 것이고 재지 않았다).

다시 돌린 명령(반영 뒤).

- `uv run ruff format src tests`(387개 그대로), `uv run ruff check .`, `uv run pyright`, `uv run lint-imports`, `uv run python tools/check_type_escapes.py`가 모두 종료 코드 0이다.
- 이 티켓이 건드린 시험(`tests/app`, 대기열·기록 어댑터, 관리 API 동기화, 왕복)을 한 번에 돌려 모두 통과했다.
- 변이 표는 아래 "검증"에 적는다. 전체 시험은 커밋이 부르는 pre-commit의 검사 러너가 돌리므로 그 결과로 갈음한다. 결과는 커밋 뒤 PR 본문에 적는다.

## PR 직전 리뷰

보안 축은 내장 `/security-review`로, 버그·성능 축은 CodeRabbit CLI(0.7.5, `--base origin/dev`, 파일 53개)로 봤다. 코드는 지적마다 파일을 열어 호출부까지 따라가며 판정했다.

- 보안: 신뢰도 8 이상의 후보가 없었다. 하위 작업이 SQL 주입, 경로 탐색, 인증과 권한(`reader` 토큰의 403, 다른 원천의 기록 막기), 로그와 기록에 남는 값을 살폈다.
- CodeRabbit: 일곱 건이 나왔고 유효 셋(모두 Minor), 오탐 넷이다.
- 고친 것:
  - `registry.py`의 `_GuardedReader.list()`가 `self._connector.list()`와 `aiter(...)`를 `try` 밖에서 불렀다. `Connector.list`는 일반 함수로 선언돼 있어(`domain/connectors.py`), 반복자를 돌려주기 전에 예외를 올리는 구현도 계약이 허용한다. 그 예외는 `connector_error`가 아니라 `internal_error`로 끝났다. 시험을 먼저 써서 빨강(`'internal_error' == 'connector_error'`)을 보고, 두 호출을 `try` 안으로 옮겼다. 변이 표에 되돌리는 변이(19번)를 더해 빨강을 확인했다.
  - 독스트링 넷을 코드에 맞췄다. `SourceReader.list()`, `job_attempt.py` 머리, `job_failure.py` 머리, `_reconcile`이다. 아래 "밀 주장"에 원문을 적는다.
- 남긴 것과 이유:
  - `_refresh_marker`가 `source_changed` 뒤에 같은 변경 확인값을 다시 적는 길은 이 티켓이 새로 만든 결함이 아니고 위 "남긴 것"의 두 번째 상태다. 티켓 09의 항목이 이 상태를 닫는다.
  - 같은 키를 두 번 내서 `SyncFailure`가 날 때 반복자를 닫지 않는 것은 가드가 일부러 안쪽 반복자를 닫지 않는 설계(끊긴 폴더에서 닫기가 돌아오지 않을 수 있다) 때문이라 옳다. 코드가 아니라 독스트링이 반대로 적혀 있었고 그것을 고쳤다.
  - 오탐: `__context__`로 연결 정보가 샌다는 지적(로그 포매터는 이 저장소 밖 예외의 메시지를 싣지 않고, 소비자는 모두 `from None`으로 닫힌 코드로 바꾼다), `fetch`에 크기 상한이 없다는 지적(처음에는 오탐으로 가렸으나 PR 봇이 같은 지적을 다시 냈고, 상한이 동기화 뒤에 낮아지는 경우를 놓친 판정이라 아래 "봇 회차"에서 고쳤다), 문서 없는 `SYNC_SOURCE`의 일시 실패가 다시 실패한다는 지적(`reschedule`은 `document_id`가 있을 때만 문서를 잠그고 `exhaust`는 원천 갈래로 간다), 시험 서버 환경 변수의 설정 순서(`RAG_SOURCES_DIR`는 요청마다 읽는다).
  - 일시 실패한 동기화 작업이 다시 예약되는 흐름을 직접 보는 시험은 여전히 없다. 위 "남긴 것"의 (a)와 같은 내용이다.
- 다시 돌린 명령(반영 뒤): `uv run ruff format --check .`, `uv run ruff check .`, `uv run pyright`, `uv run lint-imports`, `uv run python tools/check_type_escapes.py`가 종료 코드 0이다. 영향받은 시험(`tests/app/test_sync_source_connector_faults.py`, `test_sync_source.py`, `test_job_retry.py`, `tests/adapters`)이 모두 통과했다. 변이 표 셋의 `--check`가 종료 코드 0이다.
- 밀 주장(고치며 새로 쓴 사실 문장의 원문):
  - `SourceReader.list()`: "원천의 항목을 하나씩 낸다. 받는 쪽이 끝까지 받지 않고 멈춰도 안쪽 반복자는 닫지 않는다. 끊긴 폴더에서는 닫는 호출도 돌아오지 않을 수 있어서, 남은 반복자는 이벤트 루프가 치울 때 닫힌다." 근거는 `guard.py`의 `iterate` 독스트링이다.
  - `job_attempt.py` 머리: "문서를 가리키지 않는 동기화 작업이 기록을 쓰는 작업 단위는 문서 행 대신 동기화 기록 행을 먼저 잠그고 작업 행을 마지막에 잠근다. 파일 하나를 처리하는 작업 단위(변경 확인값 갱신, 가져온 문서 넣기)는 기록 행을 잠그지 않고 색인 작업과 같이 문서 행을 먼저 잠근다." 근거는 `sync_source.py`의 221→238, 429·438→454(기록이 먼저)와 414→420, `ingest.py` 339(문서가 먼저)다.
  - `job_failure.py` 머리: 문서가 있는 작업의 두 작업 단위는 모두 잠금 순서(문서 행, 그 문서의 그룹이 든 지식베이스 행, 작업 행)를 따르고, 문서가 없는 원천 단위 작업은 `_exhaust_source_job`이 맡으며 그 순서는 그 함수의 독스트링에 있다.
  - `_reconcile`: "`reread`는 작업과 기록의 옵션 칸에만 남고 이 함수는 보지 않는다."
  - `registry.py`의 주석: "`list`는 일반 함수로 선언돼 있어, 반복자를 돌려주기 전에 예외를 올릴 수도 있다."

## 봇 회차

PR 105번의 첫 회차다. claude-review는 지적 없음(경계, 계약, 제목 접두를 확인했다고 적었다)이고, CodeRabbit이 Minor 둘을 냈다. 첫 회차라 지적마다 고칠지 판단했고, 둘 다 코드와 티켓으로 확인해 유효로 판정해 고쳤다. 시험을 먼저 써서 빨강을 본 뒤 고쳤다.

- `registry.py`의 `_GuardedReader.list()`가 `connector.list()`를 호출 장치의 막힘 판정 밖에서 불렀다. 일반 함수로 선언된 `list`는 반복자를 돌려주기 전에 원천을 부를 수 있어서, 같은 설정이 한도를 넘긴 호출로 막혀 있어도 다시 불렸다. 반복자를 만드는 일을 `fetch`처럼 장치의 첫 호출로 옮겼다(`_open_iterator`). 앞 회차에 고친 동기 예외 번역은 그대로 지켜진다.
- `index_document.py`의 `_read_original`이 읽은 바이트의 크기를 현재 상한에 대 보지 않았다. 티켓은 "상한을 넘으면 `source_changed`"를 요구하는데, 코드는 커넥터가 `too_large`를 올릴 때만 그렇게 했다. 동기화 뒤에 운영자가 상한을 낮춰 다시 띄우면 해시가 맞는 큰 파일이 파서까지 갔다. 해시 비교 전에 `len(data) > max_upload_bytes`를 보고 `source_changed`로 끝낸다. 앞서 CodeRabbit CLI의 같은 지적을 오탐으로 가렸는데, 그때는 동기화가 해시 전에 길이를 거른다는 점만 보고 상한이 달라지는 경우를 놓쳤다. 이 판정은 고쳐 적는다.
- 시험: `tests/adapters/test_guarded_reader.py`(막힌 설정에서 일반 함수 `list`가 불리지 않는다)와 `tests/app/test_sync_source.py`의 상한 시험(색인 첫 읽기를 일시 실패로 다시 예약시키고 시계를 돌린 뒤 상한을 낮춘 설정으로 한 번 더 돈다)을 더했다. 변이 표 19번(원문을 새 코드에 맞춤), 20번, 21번을 더하거나 고쳐 모두 기대한 빨강을 확인했다.
- 밀 주장(이 회차에 새로 쓴 사실 문장의 원문):
  - `registry.py`의 주석: `list`는 일반 함수로 선언돼 있어 반복자를 돌려주기 전에 원천을 부르거나 예외를 올릴 수도 있고, 그래서 반복자를 만드는 일도 `fetch`처럼 장치의 첫 호출로 태운다.
  - `index_document.py`의 주석: 동기화 뒤에 운영자가 상한을 낮췄을 수 있고, 커넥터가 제 상한을 지킨다는 보장은 없다.
  - `tests/support/plain_list_connectors.py`의 머리: `Connector.list`의 선언이 이 꼴을 허용하고, 이 꼴은 반복자를 돌려주기 전에 원천을 부를 수 있다.

둘째 회차(커밋 7a6b0b8). claude-review가 Critical·Major 없이 Minor 둘과 Nit 하나를 냈고 CodeRabbit은 한도에 걸려 리뷰가 없었다. 둘째 회차 규칙대로 고치지 않고 이유를 PR 코멘트에 남겼다.

- Minor: `/jobs` 응답의 `document_id`와 `document`가 널을 받게 된 것은 사실이라 PR 본문의 계약 영향 절을 고쳤다(코드 변경 없음).
- Minor: 동기화의 `NOT_FOUND`(`source_unreadable`로 센다)와 색인의 `NOT_FOUND`(`source_changed`)가 다르다는 지적은 보류했다. 명세가 동기화 때의 `NOT_FOUND`를 정하지 않아 이 티켓이 정할 수 없다. 아래 "다음"에 to-spec의 물음으로 적었다.
- Nit: `job_failure`가 `sync_source`의 `fail_record`를 import하는 방향은 같은 층이고 순환이 없어 미뤘다. 기록을 닫는 함수가 늘면 따로 뺀다.
- CI의 `python` 잡이 15분 제한에 걸려 한 번 취소됐고(pytest 단계가 앞 성공 실행은 13분 7초, 이번은 14분 20초쯤에 끊겼다) 실패한 잡만 다시 돌려 초록이 됐다. 마진이 약 2분이라 같은 취소가 다시 날 수 있다. 아래 "다음"에 후속으로 적었다.

## 검증

- 변이 표 19개를 한 번에 돌려 모두 기대한 빨강이었다(`PYTHONUTF8=1 uv run python tools/mutate.py .scratch/source-sync/probes/sync_mutations.toml`). 반영 도중 더한 변이 둘 가운데 하나(제외 패턴을 맞출 때 키를 NFC로 맞추지 않는다)는 빨강으로 잡혔고, 다른 하나(재시도 소진 끝에서 `hold_attempt`를 지운다)는 위 "판정과 반영"에 적은 동등 변이라 표에서 뺐다. `reread` 동작과 함께 변이 하나도 걷었다. PR 직전 리뷰 뒤에 변이 하나(목록을 여는 호출을 예외 번역 밖에서 부른다)를 19번으로 끼워 넣어 표는 20개가 됐고, 그 하나만 따로 돌려 빨강을 확인했다. 봇 회차에서 변이 둘을 더해 표는 22개가 됐고(19번의 원문은 새 코드에 맞춰 고쳤다), 19~21번을 따로 돌려 모두 빨강을 확인했다. 22개를 한 번에 다시 돌리지는 않았다.
- 이 PC는 Windows라 리눅스 전용 갈래(파일 서술자 판 디렉터리)는 CI가 처음 돌린다. 동기화 쪽 시험은 경로 판 위에서 돈다.

## 회고

- 정규식으로 옮긴 glob이 지수 시간이 되는 것은 첫 사건이다. 이 저장소에서 사용자가 준 문자열을 정규식으로 컴파일하는 곳은 이 패턴 하나다. 새 규칙이나 훅은 더하지 않았다(`CLAUDE.md` 교정 루프의 다섯 번째나 손상이 아니다).
- 에이전트가 직접 지은 시험이 "맞는 쪽"까지 틀렸다(왕복 시험의 제목, 정책 시험의 `.pdf`). 둘 다 첫 실행에서 빨갰고 코드가 아니라 시험의 기대가 틀린 것이었다. 새 시험의 맞는 쪽 입력은 코드를 부르지 않고 손으로 한 번 따져 보면 걸러진다. 첫 사건이다.
- 하위 작업이 쓴 시험은 파일마다 하나씩 읽고 직접 돌렸다. 하위 작업이 "초록"이라 보고한 것을 그대로 옮기지 않았다.

## 다음

- 07은 끝났다. 08(동기화의 지움 반영과 빈 목록 보호)이 열린다. 10(일정)도 07 뒤에 열린다.
- 08이 알아야 할 것: 동기화의 목록은 `sync_source._list`가 끝까지 받아 딕셔너리로 갖고, 정책 적용 뒤 후보는 `_candidates`가 만든다. 지움 반영은 "목록에 없거나 정책에 걸린 문서"를 후보 밖으로 가려 `deleted` 칸에 센다. `SyncRecord.deleted`와 옵션 `apply_empty`는 이 티켓이 받아 기록에 남기기만 한다.
- 09가 알아야 할 것: `reread` 옵션은 이 티켓이 기록에만 남긴다. 위 "남긴 것"의 두 상태(재시도를 다 쓴 문서, `source_changed` 뒤 같은 값이 다시 적힌 문서)를 09가 닫아야 한다.
- 10이 알아야 할 것: 일정이 넣는 작업은 `enqueue_source_job`(같은 원천의 같은 종류가 대기 중이면 `None`)을 쓰고 새 요청 ID를 붙인다. 동기화 기록의 `trigger`는 `manual`과 `schedule`이다.
- 11이 알아야 할 것: 지운 원천에도 `POST /sources/{name}/sync`가 202로 답하고 작업자가 그 작업을 만나면 `RuntimeError`가 난다(`sync_source`의 `_open` 앞). 지움 표시를 보는 자리를 `request_sync`와 `sync_source` 둘에 더해야 한다. 끝없는 목록의 상한도 11과 db-source가 본다.
- to-spec으로 넘길 것: 동기화 기록의 `failure_code`가 가질 수 있는 값의 목록(명세 "동기화 기록")이 `worker_lost`, `internal_error`, `database_unavailable`을 포함하는지 정한다. 동기화가 파일을 읽을 때 `NOT_FOUND`를 어떻게 셀지도 정한다. 지금은 `source_unreadable` 실패로 세고 문서는 그대로 두며, 색인 때의 `NOT_FOUND`는 `source_changed`다. 08의 삭제 반영이 다음 동기화에서 그 문서를 지우므로 결과는 같지만, 기록의 `failed` 개수가 그 사건을 어떻게 보이게 할지는 명세가 침묵한다.
- 하네스로 따로 할 일(이 PR 범위 밖): `.github/workflows/ci.yml`의 `python` 잡 시간 제한 15분이 pytest 약 13분 대비 마진이 약 2분뿐이라, 시험이 늘면 제한에 걸려 취소되고 필수 검사 `verify`가 빨개진다. 제한을 올리거나 시험 시간을 줄이는 일이다. 이 PR에서는 한 번 걸려 다시 돌렸다.
