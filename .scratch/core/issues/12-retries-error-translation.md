# 12: 일시 실패의 재시도, 재시도 소진, 오류 번역

**What to build:** 임베딩 서버가 내려가거나 데이터베이스가 잠깐 끊기면 작업이 백오프로 다시 예약되고, 시도를 다 쓰면 `failed`로 끝나 대기열이 막히지 않는다. 시도를 다 쓴 문서는 지금 내용으로 색인되지 않은 판에서 `failed`가 되어 같은 내용을 다시 넣으면 `requeued`로 돌아온다. 어댑터는 서드파티 예외를 오류 코드가 든 도메인 예외로 바꾸고 메시지를 옮기지 않는다.

**Blocked by:** 11 (삭제·되살림. 시험이 `requeued`(10), 삭제(11), 10의 끼어들기 훅 `tests/support/interleaving.py`를 쓴다)

**Status:** done

**07이 넘긴 것:** 07의 `worker/processing.py`(`process_job`)는 영구·일시를 가르지 않는다. `RagEngineError`가 올라오면 작업을 그 오류 코드로 `failed`로 끝내고(재시도와 백오프 없음), 그 밖의 예외는 `job_crashed`를 로그에 남기고 `internal_error`로 끝낸다. 임대를 잃은 시도(`AttemptLostError`)는 작업 행을 끝내지 않고 로그의 `result`를 `lost`로 남긴다. 이 티켓이 일시 실패를 다시 예약하는 갈래와 재시도 소진 처리, 어댑터의 오류 번역을 더하며 `_run`의 `except` 순서에 끼워 넣는다. 임베딩 서버의 영구 실패(`embedding_rejected`, `embedding_dimension_mismatch`)와 일시 실패(`embedding_unavailable`)의 구분은 `TeiEmbedder`가 이미 예외 종류(`PermanentFailure`, `TransientFailure`)로 가르므로 `_run`이 그 종류로 갈라 받으면 된다. 검색 쪽은 둘 다 `search_unavailable`로 번역한다(`app/search.py`).

**08이 넘긴 것:** 파싱이 영구 실패한 작업은 `_run`이 `RagEngineError`를 받아 `_NO_TIMINGS`로 끝내므로 `job_finished`의 `parse_ms`가 실제 파싱 시간과 무관하게 0이다(`app/index_document.py`의 `_ensure_parsed`가 실패 경로에서 더한 지연은 버려진다). 이 티켓이 `_run`의 `except` 순서를 만질 때 실패한 작업에도 지연을 싣는다.

- [x] 오류 번역(명세 "수집 파이프라인과 작업" 절의 오류 번역 항목): 데이터베이스의 연결 실패(SQLSTATE `08` 갈래와 연결 끊김), `40001`, `40P01`, `57P01`~`57P03`은 `database_unavailable`(일시)이고, `DataError`·`IntegrityError` 같은 나머지는 일시가 아니다. 파일 저장소의 입출력 오류는 `blob_store_error`(일시)다. 서드파티 예외의 메시지는 옮기지 않는다(원칙 V).
- [x] 백오프: `run_after`를 `RAG_JOB_BACKOFF_BASE_SECONDS × 4^(시도 횟수 − 1)` 뒤로(한 시간 상한) 두어 다시 예약한다. 다시 예약하는 작업 단위는 문서 행, 그 그룹이 든 지식베이스 행(`FOR SHARE`), 작업 행 순으로 잠그고, 같은 문서에 다른 대기 작업이 있으면 다시 예약하지 않고 이번 오류 코드로 작업을 `failed`로 끝낸다(문서 쪽은 쓰지 않는다. 부분 유일 색인이 둘째 대기 작업을 막는다).
- [x] 재시도 소진: `RAG_JOB_MAX_ATTEMPTS`를 다 쓰면 작업 `failed`. 문서 행과 지식베이스 행(`FOR UPDATE`)을 잠근 뒤, 문서를 처음부터 맡을 다른 작업(대기 작업, 올린 세대가 빈 실행 중 작업)이 없고 세대가 마지막 시도가 올린 값 그대로이며(그 값이 없으면 다른 작업만 본다) 문서가 지워지지 않았을 때만, 지금 내용으로 색인되지 않은 살아 있는 판에서 그 문서의 조각을 지우고 색인 상태를 마지막 오류 코드로 `failed`로 쓴다. 문서 상태는 바꾸지 않는다. 전환 검사는 부르는 자리를 두고 14가 채운다.
- [x] 어느 갈래에도 들지 않는 예외는 `internal_error`로 받아 다시 예약하지 않고 재시도 소진과 같이 끝낸다.
- [x] 임베딩의 영구 실패(`embedding_rejected`, `embedding_dimension_mismatch`)는 그 (문서, 판)에 옛 조각을 지우고 `failed`를 쓰되 남은 대상 판의 계산을 이어 가고, 작업은 넷째 단계에서 `failed`다. 남은 판에서 일시 실패가 나면 그 시도는 일시 실패로 다룬다.
- [x] 시험: 일시 실패의 백오프(기다리지 않고 `run_after`의 차로 본다)와 최대 시도, 최대 시도 뒤 색인 상태 `failed`와 다시 넣을 때의 `requeued`(내용을 바꾼 문서는 옛 조각을 지우고 `failed`, 지운 문서는 색인 상태 행을 만들지 않음), 임베딩 끝점 `/info`의 모델 불일치가 작업의 `embedding_unavailable`을 냄(스토리 35). 재색인 중의 갈래는 14다.
- [x] 어댑터 시험: PostgreSQL과 파일 저장소의 오류 번역(메시지를 옮기지 않음), 다시 예약하려는 작업과 같은 문서에 다른 대기 작업이 있으면 다시 예약하지 않고 이번 오류 코드로 `failed`가 되며 문서 쪽을 쓰지 않음.
- [x] 교차 시험(메모리 안 가짜 포트는 09도 10도 만들지 않았다. 10의 `tests/support/interleaving.py` 끼어들기 훅과 실제 테스트 PostgreSQL로 한다): 한 판의 임베딩 영구 실패 뒤에도 남은 대상 판을 처리한다(대상 판 둘), 마지막 시도가 첫째 단계 전에 실패해 재시도를 다 써도 문서를 처음부터 맡을 다른 작업이 없으면 `pending`을 `failed`로 쓴다, 같은 문서의 옛 작업이 아직 실행 중이어도 늦게 시작한 작업이 재시도를 다 쓰면 `pending`을 `failed`로 쓴다, 세대가 다르고 다른 작업이 없으면 재시도 소진이 문서 쪽을 건드리지 않는다, 지운 뒤 같은 내용으로 되살린 사이에 옛 작업이 재시도를 다 써도 되살린 조각과 색인 상태를 건드리지 않는다(11이 넘긴 교차).
- [x] 검사 넷이 초록이다.

**13이 받을 것:** `process_job` 안의 작업 단위(다시 예약하기, 재시도 소진, 끝내기의 `finish`)와 `run_once`의 꺼내기(`claim`)에서 데이터베이스가 끊기면 `TransientFailure(database_unavailable)`가 `process_job`이나 `run_once`를 빠져나가 호출한 쪽까지 올라간다. 그 작업은 작업 행을 끝내지 못하므로 임대가 끝난 뒤 다른 작업자가 가져가 다시 돈다. 작업자 반복(13)이 그 예외를 받아 로그를 남기고 다음 반복으로 넘어가야 한다.
**14가 받을 것:** 파싱의 영구 실패, 임베딩의 영구 실패, 재시도 소진이 건설 중인 판을 `failed`로 쓰면 `app/index_failure.py`의 `mark_version_failed`가 `check_version_switch`를 부른다(잠금 상태의 차이는 티켓 14의 "07이 넘긴 것"에 적었다). 그 함수의 본문은 14가 채운다.
