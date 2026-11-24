# source-sync 14: 하루에 한 번 도는 정리 작업 · 2026-11-24

source-sync 티켓 12와 13을 병합한 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5). 시작 프롬프트는 `/implement .scratch/source-sync/issues/14-daily-cleanup.md`이고, 브랜치는 `feature/14-daily-cleanup`, 작업은 워크트리 `14-daily-cleanup`에서 했다. 요청 범위는 PR과 병합까지다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 준비

- 읽은 것: 티켓 14, 명세 `.scratch/source-sync/spec.md`의 "정리 작업"과 "원천 삭제와 되살리기"의 잠금 순서, ADR 0022, 12와 13의 일지의 "다음".
- 지시문이 시킨 순서: 주 체크아웃이 낡아(루트는 dev) `tidy-checkouts`를 먼저 돌고 `EnterWorktree`로 새 워크트리에 들어가 브랜치를 바꿨다.
- 시험용 PostgreSQL은 `docker compose -f compose.test.yml up -d --wait`로 띄우고 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`로 붙여 돌렸다.

## 지은 것

- **유스케이스 `app/cleanup.py`.** 정리 작업 하나(`cleanup`)가 다섯 단계를 차례로 마친다.
  1. 보관 기간이 지난 임시 삭제 문서를 50건씩 작업 단위 하나에서 완전히 지운다. 문서 행을 잠그고 지웠는지, 기간이 지났는지, 원천과 함께 지워졌다는 표시가 없는지 다시 본 뒤 삭제 보관함의 조각과 파싱 결과를 지우고 원본 경로를 비우고 완전히 지운 시각을 적는다. 원본 파일은 커밋한 뒤에 지운다.
  2. 보관 기간이 지난 지운 원천을 지운다. 원천 행을 잠그고 문서를 50건씩 지우며, 마지막 묶음과 같은 작업 단위에서 그 원천의 작업, 동기화 기록, 원천 행을 지운다. 지워지지 않은 문서가 남은 원천이면 색인 상태가 사라져 건설 중인 판이 전환될 수 있어 지식베이스 행을 잠그고 전환 검사를 부른다.
  3. 어느 문서도 가리키지 않고 쓴 지 24시간이 지난 원본을 치운다. 데이터 폴더의 `blobs/` 아래만 훑어 서버 폴더(`RAG_SOURCES_DIR`)와 그 밖의 파일은 건드리지 않는다.
  4. 끝난 지 `RAG_SYNC_RECORD_RETENTION_DAYS`(새 설정, 기본 90)가 지난 동기화 기록을 지운다. 끝나지 않은 기록과 원천마다 가장 최근 기록 하나는 남긴다.
  5. 재시도를 다 쓰고 멈춘 원천 삭제 작업과 원천 되살리기 작업을 다시 넣는다.
- **일정 확인이 정리 작업을 넣는다.** `check_cleanup`은 일정 시간대로 가장 최근의 새벽 3시 뒤에 넣은 정리 작업이 없고 대기 중이거나 실행 중인 것도 없을 때 하나 넣는다. 있는지 보는 일과 넣는 일은 한 문장(`enqueue_cleanup`)이다. 정리 작업을 넣은 적이 없는 설치에서는 첫 확인이 넣는다. 로그 `schedule_cleanup_enqueued`와 정리 작업의 끝 로그 `cleanup_finished`(개수 다섯만 싣는다)를 더했다.
- **포트와 어댑터.** `BlobStore.list_written_before`, `Catalog.list_purgeable_source_ids`와 `delete_source`, `DocumentStore`의 `list_purgeable_ids`, `purge`, `list_ids_of_source`, `delete_documents`, `has_undeleted_documents`, `has_documents_deleted_with_source`, `referenced_blob_paths`, `JobQueue`의 `enqueue_cleanup`, `latest_source_job`, `delete_jobs_of_documents`, `delete_jobs_of_source`, `SyncRecordStore`의 `delete_of_source`와 `delete_finished_before`.
- **`restore_document`의 경쟁.** 되살리는 요청이 문서를 읽은 뒤 원천 행을 잠글 때 그 원천이 정리 작업에 지워져 있으면 500이 아니라 404 `document_not_found`다. 13이 넘긴 것이다.
- **설정.** `RAG_SYNC_RECORD_RETENTION_DAYS`(기본 90, 0 이하는 거부). `.env.example`의 예시 줄은 명세가 티켓 15에 두었으므로 더하지 않았다.
- **시험.** 앱 시험(`test_cleanup.py`, `test_cleanup_resume.py`, `test_schedule_check_cleanup.py`), 어댑터 시험(`test_job_queue_cleanup.py`, `test_blob_store.py`), 서버 왕복 4개(`tests/server/test_cleanup_round_trip.py`). 변이는 `.scratch/source-sync/probes/cleanup_mutations.toml`에 넣었다.

## 이 세션이 정한 것

- **원천의 마지막 문서 묶음과 원천 행을 같은 작업 단위에서 지운다.** 문서 행이 커밋 전까지 보이는 동안 끼어든 되살리기는 원천 행 잠금에서 기다리다 사라진 원천을 본다. 묶음이 모자라야(50건 미만) 마지막으로 본다.
- **다섯째 단계의 조건은 티켓 그대로다.** 지움 표시가 선 원천은 지워지지 않은 문서가 남았을 때, 지우지 않은 원천은 표시가 남은 문서가 있거나 가장 나중 되살리기 작업이 실패했을 때 넣는다. 대기 중이거나 실행 중인 작업이 있으면 `enqueue_source_job`이 넣지 않고 `None`을 낸다.
- **원본을 지우지 못하면 이어 간다.** 문서 행은 이미 경로를 비웠으므로 남은 파일은 셋째 단계가 치운다.

## 겪은 것

- **PostgreSQL에는 `max(uuid)`가 없다.** 원천마다 가장 최근 동기화 기록을 남기는 판정을 `max(id)`로 쓰려다 `function max(uuid) does not exist`가 났다. 같은 원천에 더 나중 기록이 없는 행(`NOT EXISTS`)으로 바꿨다.
- **정리 작업이 기존 시험 셋을 깼다.** 작업자가 처음 일정을 확인할 때 정리 작업을 하나 넣으므로, 작업 행의 개수와 `job_finished` 로그를 세던 시험(`test_worker_command.py` 둘, `test_worker_schedule_loop.py`의 `_events`)이 정리 작업까지 셌다. 시험이 보려던 `index_document`와 원천 일정 로그만 고르게 고쳤다. 정리 작업의 로그는 `test_schedule_check_cleanup.py`가 따로 본다.
- **원본 지우기 변이가 초록이었다.** 문서나 원천을 지울 때 원본 파일을 지우는 줄을 빼도(변이 3, 4) 시험이 모두 통과했다. 까닭은 시험의 가짜 시계(`NOW`에 30일을 더한 2026-12-11)가 실제 파일을 만든 때보다 늦어서, 셋째 단계(주인 없는 원본 치우기)가 같은 파일을 치웠기 때문이다. 지울 문서의 원본 시각을 정리 작업이 도는 시각의 한 시간 전으로 맞추는 `make_recent`를 더해 두 시험이 앞 단계의 지우기만 보게 했다. 변이 3, 4가 빨개진다.
- **변이 표의 표지가 시험 이름이면 거부된다.** `tools/mutate.py`는 표지가 시험 원문에 글자 그대로 있으면 표를 읽지 않는다. 표지를 `파일 경로::시험 이름`으로 적었다. pytest 요약 줄(`FAILED …::이름`)에만 나온다. 변이 2, 9, 13은 시험 파일 전체를 걸면 `-x` 때문에 엉뚱한 시험이 먼저 빨개져 표지가 어긋났으므로 `::`로 의도한 시험 하나만 걸었다.
- **변이 표는 시험용 DB 접속값이 있어야 돈다.** `RAG_TEST_DATABASE_URL` 없이 돌리면 기준선이 `errors`로 빨갛다. 표 머리 주석에 적지는 않았고 `compose.test.yml` 머리 주석이 원천이다.

## 검증

- **변이 표.** `.scratch/source-sync/probes/cleanup_mutations.toml`의 19개가 모두 기대한 시험에서 기대한 이유로 빨갛다(`RAG_TEST_DATABASE_URL`을 준 실행. 처음 돌릴 때 접속값이 없어 기준선이 `errors`였다). 변이 2, 9, 13은 시험 하나만 걸었다. 변이 3, 4는 `make_recent`를 더하기 전에는 초록이었다(위 "겪은 것").
- **검사 러너 전체(`tools/run_checks.py`).** 5843개 통과, 3개 실패였다. 실패는 서버를 띄우는 시험과 시간 제한을 재는 시험(`test_admin_pull_source_stuck_calls.py` 둘, `test_serve_command.py` 하나)이고, 같은 때 리뷰 서브에이전트와 변이 실행이 이 PC에서 겹쳐 돌았다. 그 셋만 홀로 돌리면 16개 모두 통과했다(202초).
- **커밋 시도 네 번이 모두 pytest 훅에서 막혔다(한 번에 20~27분).** 실패한 시험은 매번 달랐다. 1번째 2개(`test_admin_pull_source_stuck_calls.py`의 1.0초 한도에 1.55초, `test_ingest_source.py`의 MCP 읽기 시간 초과), 2번째 3개(같은 파일의 1.08초와 `test_restore_source_round_trip.py` 둘의 검색 오류와 읽기 시간 초과), 3번째 1개(`test_restore_source_round_trip.py`의 `_seed` 검색), 4번째 2개(같은 파일의 1.08초와 1.30초). 셋째 시도의 실패는 `_seed`의 검색 호출에서 나 이 변경의 코드에 닿기 전이다. `POST /sources` 경로는 이 변경이 건드리지 않았다(`catalog.py`에는 메서드 둘을 더했다). 이 PC에는 2026-11-21에 시험이 남긴 `git-receive-pack` 찌꺼기 `sh`(pid 27972)가 한 코어를 계속 쓰고 있었다(손대지 않았다). 실패한 시험을 홀로 돌리면 모두 통과했다(16개, 22개, 22개). 이 종류는 닫힌 항목 `token-expiry-test-load-margin`이 받아들인 것이라 일지에만 적는다. 네 번째 뒤에 사용자에게 물었고 사용자가 `SKIP=pytest`로 pytest 훅만 건너뛰고 커밋하기를 골랐다. 나머지 훅은 모두 통과한 채로 돈다. 전체 시험의 판정은 CI의 `verify`가 한다. 첫 시도에서는 변이 표 검사(`check-mutations`)도 막았다. 다른 표 둘의 원문이 이 커밋이 바꾼 줄을 가리켰기 때문이다: `.scratch/core/probes/delete_restore_mutations.toml`의 `_check_building_versions`(이 티켓이 공개 이름 `check_building_versions`로 바꿨다)와 `.scratch/source-sync/probes/restore_document_mutations.toml`의 `lock_live_source` 둘(`restore_document`가 `lock_source_shared`와 `ensure_not_deleted`를 쓰게 바뀌었다). 원문을 새 코드에 맞추고 그 변이를 다시 돌렸다.
- **리뷰 반영 뒤.** `test_cleanup`·`test_cleanup_resume`·`test_worker_schedule_loop`·`test_delete_restore`·`test_schedule_check_cleanup`·`test_cleanup_round_trip` 49개와 `test_restore_source`·`test_restore_source_round_trip`·`test_restore_pull_source` 20개가 통과했다. ruff(포맷·린트)와 pyright strict, import-linter, `check_type_escapes`는 반영 뒤에 다시 돈다(아래 커밋 직전 단계).

## 셀프 리뷰(`/code-review`, base `c0f26d9`, 수정 20·미추적 8·커밋 0)

표준 축은 Critical·Major 없이 Minor 12개와 Nit 3개를, 명세 축은 (a) 둘 (c) 넷 (d) 셋을 냈다. Critical·Major는 없다.

**고친 것**
- 원천 되살리기의 경쟁(명세 축 (d)1). `lock_restorable_source`가 이름으로 읽은 원천을 잠그기 전에 정리 작업이 지우면 `RuntimeError`(500)였다. 404 `source_not_found`로 고쳤고, 문서 쪽과 같은 틀의 시험(`test_원천을_지우는_도중에_끼어든_원천_되살리기는_500이_아니라_404로_끝난다`)과 변이 19를 더했다. 시험은 고치기 전에 `RuntimeError`로 빨갰다.
- `cleanup.py` 머리 독스트링의 다섯째 단계가 코드와 달랐다(지운 원천에서 "가장 나중 삭제 작업이 실패했을 때"라고 적었으나 코드는 지워지지 않은 문서가 남았는지만 본다. 지우지 않은 원천의 "표시가 남은 문서" 갈래도 빠졌다). 코드에 맞췄다.
- `tests/app/test_delete_restore.py` 머리의 "정리 작업은 core에 없어"가 이 변경으로 거짓이 됐다. 고쳤다.
- 왕복 시험 머리의 "31일 앞으로 옮겨"를 "31일 전으로 옮겨"로 고쳤다.
- 일정 확인 실패 로그(`schedule_check_failed`)에 어느 확인인지 `check`(`sources`, `cleanup`)를 더했다.

**남긴 것과 이유**
- 정리 작업이 단계마다 예외를 격리하지 않는다(명세 축 (d)3). 첫째나 둘째 단계가 일시 실패가 아닌 예외를 내면 작업이 `internal_error`로 끝나 뒤 단계가 그 날은 돌지 않는다. 명세는 다섯 단계를 차례로 마친다고만 적었고 격리를 요구하지 않는다. 같은 예외가 다음 날에도 나면 로그로 보이므로 숨기지 않는 쪽을 골랐다.
- 보관 일수를 올리면 둘째 단계가 절반 지운 원천이 다시 되살릴 수 있게 된다((d)2). 명세 288행이 보관 기간으로 이 틈을 막는다는 전제를 두었고, 운영자가 설정을 올리는 일은 그 전제 밖이다.
- 고른 50건이 모두 그사이 되살아나면 첫째 단계가 0건으로 끝나 하루 미뤄진다((c)3). 50건이 동시에 되살아나야 하는 드문 경우이고, 다음 정리 작업이 이어 지운다.
- `jobs`에서 끝난 정리 작업을 찾는 질의에 쓸 색인이 없다((c)4). 일정 확인이 5초마다 부르므로 작업 표가 수백만 건이 되면 읽는 양이 는다. 마이그레이션이 필요한 스키마 변경이라 이 티켓 범위 밖으로 두었다. 작업 표의 크기가 문제가 되면 `created_at`에 `kind = 'cleanup'` 부분 색인을 더한다(후속 후보).
- `blobs_removed`는 셋째 단계가 치운 원본만 센다((a)1). 명세의 "치운 원본"이 셋째 단계의 이름이라 그 뜻으로 읽었다. 첫째와 둘째 단계가 지운 원본은 `documents_purged`와 `sources_purged`에 딸린 것으로 센다.
- 지우는 도중 끼어든 문서 되살리기가 마지막 묶음이 아닌 앞 묶음 뒤에 오면 404가 아니라 409 `source_deleted`다((c)2). 500은 아니고, 원천 행이 남아 있어 지움 표시가 서 있기 때문이다.
- 표준 축 Minor: `_remove_blob`의 명령·질의 섞임, `_lock_documents`·`_lock_knowledge_bases_of`가 `delete_source.py`·`restore_source.py`와 같은 모양으로 세 벌, 보관 기간 경계가 `restore_source.py`와 `cleanup.py`에 따로 적힘, `restore_document`가 `lock_live_source`를 풀어 씀, 블롭 키 첫 토막 `blobs`가 두 곳, `(deps, job)`이 다섯 단계 함수에 붙어 다님, `IndexDocumentDeps`에 정리 설정이 들어옴, "완전히 지움"의 동사가 셋(`delete_source`, `delete_documents`, `purge`), `test_cleanup_resume.py`가 `test_cleanup.py`의 도우미를 가져옴, `list_purgeable_source_ids`의 `limit`이 늘 1. 모두 동작이 맞고 이 PR의 범위를 넓히지 않으려고 뒤로 둔다. 같은 모양이 다섯 번째로 나오면 retro가 센다.

**PR 직전 리뷰에 밀 주장(이 반영으로 새로 쓴 문장)**
- `lock_restorable_source` 독스트링: "이름으로 읽은 뒤 잠그기 전에 정리 작업이 그 원천을 지웠으면 404 `source_not_found`다."
- `cleanup.py` 머리 독스트링 5: "지운 원천은 지워지지 않은 문서가 남았을 때, 지우지 않은 원천은 원천과 함께 지워졌다는 표시가 남은 문서가 있거나 가장 나중 원천 되살리기 작업이 실패로 끝났을 때다. 대기 중이거나 실행 중인 작업이 있으면 넣지 않는다."
- 일지의 "`jobs`에서 끝난 정리 작업을 찾는 질의에 쓸 색인이 없다": 끝난 작업이 담기는 색인은 없다(`tables.py`의 `jobs` 색인 넷은 모두 `queued`·`running` 작업만 담는 부분 색인이다). EXPLAIN으로 재지는 않았고 정의를 읽은 것이다.

## 회고

후보 6개, 승인 0, 기각 6, 넘김 0. 대기열에서 같은 사건을 다룬 항목을 `tools/queue_open_rows.py --search`로 찾았다(`mutate`, `expect_output`, `RAG_TEST_DATABASE_URL`, `utime`, `시계`). 맞은 항목은 변이 도구나 시간 시험에 관한 것이고 이 세션의 사건과 처방이 달라 회차를 더하지 않았다. 만료할 항목은 없었다.

- **변이 표의 표지를 시험 이름으로 적어 도구가 표를 거부했다.** 기각. 이미 있는 검사가 아무 파일도 쓰기 전에 그 자리에서 알렸고(`mutate-marker-discovery`가 닫힌 처방이 이 검사다), 고치는 데 한 바퀴가 들었을 뿐이다.
- **`RAG_TEST_DATABASE_URL` 없이 변이 표를 돌려 기준선이 `errors`로 빨갰다.** 기각. 도구가 기준선 빨강을 알렸고 변이는 하나도 돌지 않아 잃은 것이 없다. 접속값은 `CLAUDE.md`의 검증 명령 절과 `compose.test.yml` 머리 주석에 이미 적혀 있다.
- **원본을 지우는 줄을 뺀 변이 둘이 초록이었다(가짜 시계가 실제 파일 시각보다 늦어 셋째 단계가 같은 파일을 치웠다).** 기각. 변이 표가 바로 그런 시험의 구멍을 잡으려는 검사이고 이번에도 그 자리에서 잡았다. 시계를 옮기는 시험이 파일 시각도 맞춰야 한다는 판단은 이 사건 하나뿐이고 자동 검사로 옮길 수 없다. 같은 꼴이 다섯 번 나오면 `CODING_STANDARDS.md`의 줄 후보가 된다. 지금은 회차를 셀 항목을 따로 만들지 않고 이 일지에만 남긴다.
- **작업자가 첫 일정 확인에서 정리 작업을 넣어, 작업 행의 개수와 `job_finished` 로그를 세던 기존 시험 셋이 빨개졌다.** 기각. 전체 시험이 그 자리에서 잡았고 시험이 보려던 작업 종류만 고르게 고쳤다.
- **서버를 띄우는 시험과 시간 제한을 재는 시험 셋이 전체 실행에서 빨갰다(리뷰 서브에이전트와 변이 실행이 같이 돌던 때).** 기각. 부하에서 빨개지는 시간 시험은 사용자가 2026-11-15에 닫힌 채 두기로 한 종류라 새 사례를 일지에만 적는다(위 검증 절). 그 셋을 홀로 돌리면 모두 통과했다.
- **셀프 리뷰가 독스트링의 틀린 서술과 원천 되살리기의 경쟁을 잡았다.** 기각. 리뷰가 제 몫을 한 것이라 회차로 세지 않는다. 경쟁은 이 세션에서 시험과 함께 고쳤다.

## 다음

- 후속 후보 하나. 작업 표가 수백만 건이 되면 일정 확인이 5초마다 부르는 `enqueue_cleanup`의 "끝난 정리 작업이 있나" 질의가 표를 훑는다. `kind = 'cleanup'`에 `created_at`을 키로 하는 부분 색인을 더하는 마이그레이션이 필요하다(위 셀프 리뷰의 남긴 것). 지금 요청한 일이 아니라 만들지 않았다.
- 15(단독 설치의 원천 폴더)가 남았다. `deploy/standalone/.env.example`에 `RAG_SYNC_RECORD_RETENTION_DAYS`와 `RAG_DELETED_RETENTION_DAYS`의 예시 줄을 15가 더한다(명세 391행).
