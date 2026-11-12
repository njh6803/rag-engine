# core 14 재색인과 판 전환 일지 · 2026-11-12

티켓 `.scratch/core/issues/14-reindex-version-switch.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/14-reindex-version-switch`, 작업은 워크트리 `reindex-version-switch`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다. 구현 도중 컨텍스트가 압축되었다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 13 일지의 다음, 명세의 수집 파이프라인과 작업 절(잠금 규칙, 판 전환), ADR 0008과 ADR 0009.
- 테스트 PostgreSQL은 `compose.test.yml`의 컨테이너를 쓰고 명령마다 `RAG_TEST_DATABASE_URL`을 내보냈다.
- 티켓을 첫 변경에서 `in-progress`로 두었다.
- 이월 항목은 13 일지의 "다음" 가운데 이 티켓과 겹치는 것과 대기열 항목 `mutation-rerun-after-code-fix`(코드를 고친 뒤에는 그 코드를 겨냥한 변이를 실제로 다시 돈다)다.

## 정한 것

- **판 상태와 전환 검사**(`app/version_switch.py`). 판은 `building`, `current`, `retired` 순으로 간다. `check_version_switch`는 지식베이스 행을 `FOR UPDATE`로 잠근 뒤 판을 다시 읽고, 판이 `building`이 아니거나 `pending`이 하나라도 남았으면 아무것도 하지 않는다. 전환 조건에서 `failed`는 끝난 것으로 센다. 이 때문에 `pending` 행이 하나도 없는 건설 중인 판은 첫 전환 검사(색인, 삭제, 어느 쪽이든)에서 바로 전환된다. 시험에서 "재색인이 진행 중"인 판을 만들려면 `pending` 행을 일부러 남겨야 해서 `Pipeline.keep_pending`을 더했다.
- **잠금 순서**. 문서 행(`FOR NO KEY UPDATE`), 지식베이스 행(ID 순, `SHARE`나 `UPDATE`), 작업 행(`hold_attempt`) 순을 지킨다. 재색인 시작은 지식베이스 행을 `FOR UPDATE`로 잠그고 대기 중인 작업 행도 잠가(`lock_queued_documents`) 작업자의 `SKIP LOCKED` 꺼내기가 건너뛰게 한다. 문서 행은 잠그지 않는다. 문서 행을 잠그면 외래 키의 `FOR KEY SHARE`와 겹쳐 교착한다. 이 때문에 `ingest.py`의 `_index_failed` 독스트링에 "재색인 시작은 문서 행을 잠그지 않고 `pending`만 쓰는데 판정은 `failed`만 본다"는 문장을 더했다.
- **재색인 시작**(`app/reindex.py`). 물러난 판을 먼저 정리하고, 지식베이스 행을 잠근 뒤 `building` 판이 있으면 409 `reindex_in_progress`를 낸다. 없으면 새 판과 문서별 `pending`을 만들고, 대기 작업이 없는 문서에만 작업을 넣고, HNSW 부분 색인을 만든 뒤 전환 검사를 한 번 부른다. 문서가 없는 지식베이스는 이 전환 검사로 같은 작업 단위에서 바로 전환된다. 삭제된 문서에는 `pending`도 작업도 넣지 않는다.
- **물러난 판의 정리**(`app/retire_cleanup.py`, `adapters/postgres/index_maintenance.py`). 색인은 자동 커밋 연결에서 `DROP INDEX CONCURRENTLY IF EXISTS`로 먼저 지우고, 조각은 `FOR UPDATE SKIP LOCKED`로 고른 상수 크기 묶음마다 별도 트랜잭션에서 지운다. 정리를 겹쳐 돌려도 서로 기다리지 않는다. 앱 계층은 어댑터를 import할 수 없어서 정리 결과의 로그(`retired_version_cleaned`, `retired_cleanup_failed`)는 작업자 쪽(`worker/processing.py`)에서 남긴다. 명세 235행의 이벤트 목록에 이 둘을 더했다.
- **복사 경로**(`app/keyword_copy.py`). 건설 중인 판이 같은 지식베이스의 현재 판과 판 스키마, 임베딩 모델, 차원, 청킹 해시가 같으면(토크나이저 판만 다르면) 현재 판의 조각 가운데 `source_content_hash`가 첫째 단계가 기억한 내용 해시와 같은 것의 글과 위치와 임베딩을 그대로 쓰고 키워드만 다시 만든다. 키워드는 `index_text`로 만들므로 절 경로를 상한의 4분의 1 안으로 줄이는 규칙(`fit_section`)을 같은 토크나이저로 되풀이해 글을 되짓는다. 청킹도 같은 함수를 쓴다. 그런 조각이 없으면 다른 판처럼 청킹하고 임베딩한다.
- **판마다 청킹 설정**. 판은 자기 청킹 설정을 적어 두고, 청킹은 판의 설정으로 한다.
- **관리 API**(`server/admin_knowledge_base_api.py`). 목록과 상세에 `reindex_needed`와 건설 중인 판의 진행(색인 상태별 개수)을 싣고, `POST .../reindex`는 202에 새 판 ID와 넣은 작업 수를 낸다. `reindex_needed`는 03의 판 요소 함수로 계산한 요소와 현재 판의 요소를 견준 값이다. 건설 중인 판이 있으면 그 판이 현재 설정을 적은 판이므로 참이어도 곧 거짓이 된다.
- **영구 실패 기록의 잠금**(`app/index_document.py`의 `_record_permanent_failure`). 건설 중인 판에 `failed`를 쓰면 전환 검사가 지식베이스 행을 잠그므로 잠금 순서를 지키려고 작업 행 앞에서 잠가야 한다. 처음에는 그룹이 든 모든 지식베이스를 잠갔으나 리뷰가 불필요한 직렬화라고 짚어, 살아 있는 판 가운데 `building`인 판이 든 지식베이스만 ID 순으로 잠그도록 좁혔다. 잠그기 전에 읽은 판 목록을 쓰는 것이 안전한 까닭은, `mark_version_failed`가 읽어 둔 판 객체의 상태로 전환 검사 여부를 정하고 전환 검사는 잠근 채 판을 다시 읽기 때문이다. 읽은 뒤 재색인이 시작돼 새 `building` 판이 생겨도 재색인이 그 문서의 작업을 새로 넣으므로 그 판의 실패는 새 작업이 기록한다.
- **`lock_queued_documents`의 묶음**. psycopg는 한 문장에 바인드 파라미터를 65535개까지만 받는다. 살아 있는 문서가 그보다 많은 지식베이스에서 재색인 시작이 실패하므로 `IN` 목록을 1만 개씩 나눠 보낸다. 묶음 사이의 잠금 순서는 전체 ID 순이 아니지만, 재색인 시작은 지식베이스 행을 먼저 잠가 같은 지식베이스의 다른 재색인과 겹치지 않고 작업자는 잠긴 행을 건너뛰므로 서로 기다리는 일이 없다.

## 손으로 본 것

- 앱 시험과 어댑터 시험은 구현 앞에 썼고 빨강을 본 뒤 구현했다. 처음부터 초록이던 시험은 변이로 가렸다. 새 표는 `.scratch/core/probes/reindex_mutations.toml`이고 스물세 개다. 전환 조건, 잠그지 않는 경우, 재색인 시작의 409와 대기 작업 건너뛰기, 정리의 묶음과 색인 지우기, 복사 조건 일곱 가지, `fit_section` 호출, 색인 작업의 잠금과 전환 검사, `reindex_needed`, 대기 작업 잠금의 묶음을 가린다.
- 첫 실행은 표지(`expect_output`)가 시험 원문에 글자 그대로 있거나 단언을 풀어 쓴 줄이라는 검증에서 멈췄다. 표지를 f-string 메시지에 값을 실은 문구나 예외 메시지로 바꿨다. 이 도구는 시험 원문에 든 표지를 거부한다.
- **살아남은 변이 넷**(2, 3, 7, 12)을 시험을 강하게 해서 잡았다. 물러난 판이 틀리게 전환되는 것을 보려고 재색인을 두 번 해 보는 시험, 지식베이스 행을 다른 연결이 쥔 동안 전환 검사와 색인 작업이 기다리는지 보는 시험, 조각이 둘 이상 있어야 묶음을 되풀이해 지우는지 보이는 두 문서 정리 시험, 기다리는 동안 작업 행이 비어 있는지 보는 시험이다.
- **전환 의미 때문에 기존 시험이 빨개졌다**. 재시도 시험(`test_job_retry`), 삭제·되살림 시험, 검색 시험이 "건설 중인 판이 있는 채로" 무언가를 보는데, `pending`이 없는 건설 중인 판은 첫 전환 검사에서 전환된다. `Pipeline.keep_pending`으로 `pending` 행을 일부러 남기고, `Pipeline.states()`는 물러난 판까지 모든 판을 돌려주게 했다.
- 기존 표 세 개도 코드가 옮겨 가서 어긋났다. `chunker_mutations.toml`(`_SECTION_SHARE`가 `domain/index_text.py`로 옮겨 갔다), `delete_restore_mutations.toml`(앵커가 `lock_queued_documents(`로 끝난다), `first_round_trip_adapter_mutations.toml` 16번(표지를 `TransientFailure: 데이터베이스를 잠시 쓸 수 없다`로 약하게 했다)을 고쳐 다시 돌렸다. 코어 12가 `DBAPIError`를 `from None`으로 일시 실패로 바꿔 원래 SQL 오류 문구가 트레이스백에서 사라지기 때문에 표지는 번역된 문구만 쓸 수 있다.
- **초록으로 남은 변이**. `first_round_trip_mutations.toml` 11번은 기대와 달리 초록이다. `_finish`가 이미 `AttemptLostError`를 `None`으로 바꾸므로 변이가 같은 동작이 되는 동치 변이다. 이 티켓의 변경이 만든 것이 아니라 그대로 두었다.
- 리뷰 반영 뒤 새 표의 15번부터 23번까지를 돌렸다. 17번(원본이 현재 판이라는 검사)은 처음에 빨강이었으나 표지가 어긋났다. 그 검사를 지우면 건설 중인 판이 자기 자신을 복사 원본으로 골라, 먼저 터지는 시험이 다른 경우였다. 표지를 실제 출력으로 고쳐 다시 돌려 기대대로다. 23번(`IF EXISTS` 제거)은 빨강이지만 잡은 시험은 색인 지우기를 두 번 부르는 시험이고, 정리를 겹쳐 돌리는 새 시험은 `IF EXISTS`를 지워도 통과한다. 그 시험은 `SKIP LOCKED`로 같은 조각을 두 번 세지 않는 것을 보는 용도로 남긴다.

## 코드 리뷰

`/code-review`를 돌렸다. 범위는 base `origin/main`, 작업 트리의 커밋하지 않은 변경 전부와 추적하지 않는 새 파일이다. 표준 축(sonnet / high)과 명세 축이 따로 보았다. 근거는 코드에서 다시 열어 확인했다.

**고친 것**

- `lock_queued_documents`가 `IN` 목록 전체를 한 문장으로 보내 바인드 파라미터 한도(65535)를 넘으면 재색인 시작이 실패했다. 1만 개씩 묶었고 7만 개 ID 시험과 변이를 더했다.
- `_record_permanent_failure`가 그룹의 모든 지식베이스를 잠갔다. 건설 중인 판이 든 지식베이스만 ID 순으로 잠그도록 좁혔다. 그 판이 있을 때 작업 행을 쥐기 전에 기다리는지, 없을 때 지식베이스 행을 쥔 연결이 있어도 기다리지 않는지 보는 시험 둘을 잠금 시험에 더했다.
- `rebuild_keywords`의 `fit_section` 호출이 시험으로 고정되지 않았다. 가짜 임베더로 긴 절 경로가 줄어드는 것과 임베딩과 조각 글이 그대로인 것을 보는 시험과 변이를 더했다.
- `copy_source_of`의 조건별 시험이 없었다. 일곱 조건과 임베딩 끝점이 달라도 복사한다는 서술을 단위 시험(`tests/app/test_keyword_copy.py`)으로 고정하고 조건마다 변이를 더했다. 모듈 독스트링의 조건 목록에 빠진 판 스키마를 더했다.
- 영구 실패 시험 둘에 오류 코드(`PARSE_FAILED`) 단언을 붙이고, 시험이 하드코딩한 색인 이름을 `version_index_name`으로 바꿨다.
- 정리를 겹쳐 돌리는 시험을 더했다.
- 낡은 문장: `_index_failed`와 `index_document` 모듈 독스트링의 복사 경로와 전환 검사 서술, `processing.py` 모듈 독스트링의 정리 로그 이벤트, `index_maintenance.py`의 SQL 문자열 안전 서술, 명세 235행의 로그 이벤트 목록, `tests/test_migrate_command.py` 독스트링의 시험 위치를 고쳤다.

**남긴 것과 이유**

- API 프로세스가 전환하는 경로(삭제 등)는 물러난 판의 정리를 부르지 않는다. 명세가 허용한 범위이고 다음 재색인 시작이나 작업자의 전환이 정리한다.
- 잠금 시험은 재색인이 먼저 지식베이스 행을 쥔 순서만 본다. 반대 순서는 `held_knowledge_base_lock`으로 쥔 연결 쪽의 시험이 따로 본다.
- 관리 응답에 끝점 같은 설정 필드가 실린다. 관리 API 전용이고 명세 "설정" 절이 허용한다.
- 중복과 데이터 뭉치 냄새(`IndexVersion` 조립 세 곳, `compute_elements` 세 곳, `ChunkingResponse`, `_lock_knowledge_bases` 세 곳, 시험 상수)는 judgement call이다. 같이 바뀌어야 하는 일이 생기면 합친다.
- `check_version_switch`라는 이름은 검사만이 아니라 전환도 한다. 호출 지점이 많아 이름은 그대로 두었다.
- 어댑터 변이 16번의 표지는 번역된 문구뿐이라 약하다(위에서 설명한 `from None` 때문이다).

**다시 돌린 명령**

- 리뷰 반영 뒤 `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 오류), `uv run lint-imports`(계약 2개 유지)를 손으로 쳐서 모두 초록이었다.
- `uv run python tools/run_checks.py` 전체 실행이 초록이다(pytest 576초, run-hooks, pyright 둘, 타입 이스케이프, 지침 검사 포함).
- 변이: 새 표 `reindex_mutations.toml` 스물세 개가 모두 기대대로이고(17번은 표지를 고쳐 다시 돌렸다), 이 세션이 다시 고친 `index_document.py`와 `job_queue.py`를 겨누는 기존 변이 스물다섯 개(`retries`, `delete_restore`, `first_round_trip` 둘, `admin_queries`, `ingest`, `ingest_updates`, `lease_worker`, `parsers_isolation`, `reindex`의 12·13·15)를 다시 돌려 모두 기대대로다. 표 열네 개를 모두 `--check`했다.

## 회고

후보 여섯을 냈다. 승인 둘, 기각 넷, 넘김 0이다. 넘긴 것이 없어 사용자에게 묻지 않았다.

**승인**

- 변이 표가 코드 이동으로 어긋난 일: 이 브랜치가 코드를 옮기자 기존 표 셋(`chunker_mutations`의 상수 위치, `delete_restore_mutations`의 앵커, `first_round_trip_adapter_mutations` 16번의 표지)이 어긋났고, `--check`만으로는 `expect = "red"`가 거짓이 된 것을 가리지 못해 실제로 돌려서야 찾았다. 사건은 같은 실수의 반복이고 층은 이미 정해진 대기열 항목의 처방(스킬 문장)이다. 대기열 `mutation-rerun-after-code-fix`에 2회차를 더했다. 더하는 것이라 다섯 번째에 반영한다.
- `IN` 목록의 바인드 파라미터 한도: `lock_queued_documents`가 65,535개를 넘는 ID를 한 문장에 보내 재색인 시작이 실패할 수 있었고, 셀프 리뷰가 잡았다. 판정할 도구가 없고(목록 길이는 실행 때 정해진다) 판단 기준이라 `CODING_STANDARDS.md` 후보다. 병합 전이라 손상이 아니다. 새 항목 `in-list-bind-limit`로 1회차를 두었다.

**기각**

- 변이 표지가 시험 원문에 글자 그대로 있거나 단언 풀이 줄이라 도구가 멈춘 일: `tools/mutate.py`가 그 자리에서 막았다(이미 있는 검사).
- 도구 호출 사이의 중간 문장이 한국어가 아니라고 훅이 알린 일, 한글 폭 2 때문에 줄이 길어 E501이 난 일, 40줄 넘는 heredoc과 파이썬 heredoc을 훅이 막은 일: 각 훅이 그 자리에서 알리거나 막았다(이미 있는 훅).
- 건설 중인 판이 `pending` 없이 첫 전환 검사에서 전환되어 기존 시험이 빨개진 일: 설계 의미이고 실수가 아니다(사건 없음). `Pipeline.keep_pending`으로 시험 쪽을 맞췄다.
- 새 시험이 변이 23번(`IF EXISTS` 제거)을 잡는다고 적었으나 실제로는 기존 시험이 잡은 일: 이 세션의 서술 오류로 변이를 돌린 결과를 보고 바로 고쳤다. 반복이 아니고 검사가 잡았다.

## 다음

- 티켓 16(대상 사양에서 검색 지연 재기)이 남았다. 14와 15가 모두 병합되었으므로 막힌 것이 없다. 실제 TEI와 표본 문서가 필요하고 시험이 아니라 프로브다.
- 이 티켓에서 계획 파일의 `끝` 줄은 더하지 않았다. 기능의 마지막 티켓 16을 닫는 커밋이 더한다.
