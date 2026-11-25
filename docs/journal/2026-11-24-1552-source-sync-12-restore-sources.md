# source-sync 12: 원천 되살리기 · 2026-11-24

source-sync 티켓 11을 병합한 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5). 시작 프롬프트는 `/implement .scratch/source-sync/issues/12-restore-sources.md`이고, 브랜치는 `feature/12-restore-sources`, 작업은 워크트리 `12-restore-sources`에서 했다. 요청 범위는 PR과 병합까지다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 준비

- 읽은 것: 티켓 12와 13, 명세 `.scratch/source-sync/spec.md`의 "원천 삭제와 되살리기", "동기화의 차례", "Testing Decisions", 11 일지의 "다음".
- 지시문이 시킨 순서: `tidy-checkouts`를 먼저 돌았고, `EnterWorktree`로 새 워크트리에 들어가 브랜치를 바꿨다. 형제 워크트리를 열어 보는 일은 훅이 막아서 13번 티켓은 이 워크트리의 사본 파일로만 읽었다.
- 시험용 PostgreSQL은 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`로 붙여 돌렸다.

## 지은 것

- **도메인.** 오류 코드 `source_not_deleted`, `source_change_in_progress`, `source_retention_expired`를 더했다(HTTP 코드가 스물다섯이 되고, 새 셋은 모두 409다). 포트에 `Catalog.mark_source_restored`, `JobQueue.has_active_source_job`, `DocumentStore.list_held_keys_of_source`, `list_ids_deleted_with_source`, `list_stalled_ids_of_source`를 더하고 쓰는 곳이 없어진 `list_live_keys_of_source`를 뺐다. 마이그레이션은 없다.
- **되살리기 요청.** `POST /sources/{name}/restore`(202, `job_id`와 `connection_check`)가 한 작업 단위에서 원천 행을 잠그고 지움 표시를 걷는다. 일정이 있고 일시 중지가 아니면 다음 실행 시각을 다시 채우고, 원천 되살리기 작업을 넣는다. 거절은 순서대로 지운 원천이 아니면 `source_not_deleted`, 보관 기간(`RAG_DELETED_RETENTION_DAYS`)이 지났으면 `source_retention_expired`, 삭제나 되살리기 작업이 끝나지 않았으면 `source_change_in_progress`다. 원천을 지우는 요청도 같은 마지막 검사를 한다.
- **가져오는 원천.** `PullSources.restore`가 자기 폴더를 차례 앞에서 살피고(답하지 않거나 없어도 받는다), 자문 잠금과 프로세스 안의 차례 아래에서 다른 원천과의 겹침을 다시 본다. 겹치면 409 `source_folder_overlap`이고 되살리지 않는다. 되살린 뒤 연결 확인의 결과를 응답에 싣는다.
- **원천 되살리기 작업.** 작업자가 `deleted_with_source`가 선 문서를 50건씩 묶어 묶음마다 작업 단위 하나에서 되살린다. 맨 먼저 원천 행을 공유 잠금으로 잡고 지움 표시가 다시 섰으면 아무것도 하지 않고 성공으로 끝난다. 문서 하나를 되살리는 일은 ingest의 되살림과 같아야 해서 `restore_chunks`(`app/restore_chunks.py`)로 뽑아 둘이 함께 쓴다. 모든 문서를 되살린 뒤에는 색인이 멈춘 문서(대상 판에 `indexed`도 `failed`도 아닌 판이 있는데 색인 작업이 없다)에 색인 작업을 넣는다.
- **따로 지우는 요청.** 수집 API의 삭제와 동기화의 삭제 반영이 표시가 남은 문서를 만나면 `detach_from_source_deletion`이 표시를 걷고 지운 시각을 그 순간으로 고친다. 동기화는 그 문서를 `deleted`로 센다. 삭제 반영 대상을 고르는 질의가 표시가 남은 문서도 포함하도록 `list_held_keys_of_source`로 바꿨다.
- **시험.** 서버 왕복 9개(`test_restore_source_round_trip.py`), 앱 시험 5개(`test_restore_source.py`), 가져오는 원천의 HTTP 시험 6개(`test_restore_pull_source.py`), 어댑터 시험 5개(`test_restore_source_queries.py`)를 더하고 오류 코드 시험과 어댑터 시험 둘을 고쳤다. 변이는 `.scratch/source-sync/probes/restore_source_mutations.toml`에 열두 개를 넣었다(열한째는 셀프 리뷰가 낸 옛 내용 해시의 구멍을, 열두째는 PR 직전 리뷰가 낸 폴더 겹침의 설정 재확인을 지킨다). 내가 소스를 고쳐 원문이 어긋난 다른 표의 변이 일곱 개(`admin_queries`, `delete_restore`, `pull_sources`, `sync`)도 고쳐 다시 돌려 빨강을 확인했다.

## 이 세션이 정한 것

- **되살리기와 지우기를 서로 막는 검사는 작업 행으로 한다.** `jobs`의 활성 작업 유일 인덱스는 (원천, 종류) 단위라 삭제 작업과 되살리기 작업이 DB 수준에서는 함께 들어갈 수 있다. 그래서 요청이 원천 행을 잠근 뒤 두 종류의 활성 작업을 직접 보고 409로 막는다.
- **요청을 둘로 나눴다.** 가져오는 원천은 폴더 겹침을 되살리기 사이에 끼워야 해서 `lock_restorable_source`와 `apply_restoration`을 따로 부르게 했고, 밀어 넣는 원천은 둘을 한 함수(`request_source_restoration`)로 묶었다.
- **표시를 걷은 문서의 지운 시각은 그 순간으로 다시 쓴다.** 따로 지운 문서로 바뀌므로 보관 기간이 그 순간부터 다시 센다.

## 겪은 것

- 편집 도중 Pyright가 import를 못 찾는다는 진단을 여러 번 냈다. 편집 순서 때문의 일시 현상이었고 `uv run pyright`는 0 오류였다.
- 한글 줄이 ruff 100칸을 넘는 것을 훅이 알려 줬고 `tools/rewrap_comments.py`와 `ruff format`으로 감았다.
- 시험 둘이 내 쪽 잘못으로 처음에 빨갰다. 검색이 질의를 임베딩하므로 임베딩 호출 수는 검색 전에 재야 했다. 되살린 원천의 동기화가 읽은 문서(폴더에 남은 파일)는 코어의 되살림으로 표시가 걷히는데 이를 놓쳤다(티켓 12의 여섯째 완료 조건이 그렇게 정한다). 작업자의 시계(`NOW`)와 실제 시각이 달라 `run_after`를 실제 시각으로 쓰면 작업이 꺼내지지 않았다.
- `tests/adapters`의 헬퍼에 `# type: ignore`를 한 줄 쓰고 곧 `UUID` 타입으로 고쳤다. 원칙 II는 시험 코드도 대상이다.
- 변이 도구가 기준선이 빨강이면 변이를 넣지 않는다. 처음에는 `RAG_TEST_DATABASE_URL`을 붙이지 않아 기준선이 error였다. 변이 표지가 시험 원문에도 있으면 도구가 거절해 둘을 출력에만 나오는 문구로 바꿨다. `ruff format`이 감은 줄을 원문으로 쓴 변이는 원문이 0번이라 거절됐다.

## 셀프 리뷰

`/code-review`로 표준 축과 명세 축을 함께 돌렸다. 본 범위는 기준 커밋 `4d0b692`, 수정한 파일 26개, 추적하지 않는 새 파일 8개, 커밋 0개다. 두 축 모두 Critical과 Major는 없었다.

**고친 것**
- 명세 축 (d) 교차. `list_stalled_ids_of_source`가 `indexed`이지만 만든 내용 해시가 문서의 것과 다른 판을 정착한 것으로 봤다. 내용을 바꿔 넣은 문서는 옛 `indexed`를 둔 채 작업만 넣으므로, 그 작업이 지움 표시 때문에 아무것도 쓰지 않고 끝난 뒤 원천 삭제 작업이 실패로 끝난 원천을 되살리면, 문서가 옛 내용으로 검색에 남고 작업은 없다. 질의가 해시가 같은 `indexed`만 정착으로 본다(`job_failure._is_stale`과 같은 판정). 어댑터 시험에 경우 하나를 더하고 변이 하나를 더했다(둘 다 고치기 전에 빨강을 봤다).
- 명세 축 (c) 관리 API 머리 설명이 지운 원천이 받는 요청에서 되살리기를 빠뜨렸고, 삭제 응답 설명이 `source_change_in_progress`를 빠뜨렸다.
- 명세 축 (c) 두 독스트링(`restore_source`, `delete_source`)이 지움 표시가 걷히거나 다시 서는 길로 "다시 지웠다", "되살렸다"를 들었다. 두 요청이 서로의 작업이 끝나기 전에 거절되므로 작업을 대기열에 직접 넣은 길만 남는다.
- 명세 축 (c) 이 일지의 HTTP 코드 수 서술(새 셋이 모두 409이고 전체가 스물다섯)과, 있지도 않은 14번 항목을 가리킨 문장을 고쳤다.
- 표준 축 CQS. `detach_from_source_deletion`이 문서를 고치면서 참거짓도 돌려줬다. 질의 `holds_source_deletion_mark`와 명령으로 나눴고 두 부르는 곳(수집 API의 삭제, 동기화의 삭제 반영)이 질의를 먼저 부른다.
- 표준 축 잔존. ADR 0022 72행이 `ingest._restore_chunks` 독스트링을 전환 조건의 근거로 가리키는데, 이 변경이 그 문장을 `restore_chunks` 모듈로 옮겼다. ADR을 고치지 않고 `ingest._restore_chunks` 독스트링에 조건 문장을 다시 적었다.
- 리뷰 밖에서 찾은 것. 되살림 본체를 `restore_chunks.py`로 옮기자 `tests/app/test_delete_restore.py`의 한 시험이 가짜로 바꾼 `ingest.check_version_switch`가 닿지 않아 변이 16이 초록이 됐다. 가짜를 `restore_chunks` 모듈에 붙이고(그 모듈에는 그 이름이 없어 `raising=False`) 건설 중인 판을 `keep_pending`으로 붙들게 했다.

**남긴 것과 이유**
- 보관 기간 경계(`삭제 시각 + 보관 일수 == 지금`)는 이 변경이 `<=`로 거절한다. 명세가 경계를 정하지 않았고 정리 작업은 티켓 14가 넣는다. 정리가 `삭제 시각 + 보관 일수 <= 지금`인 원천을 지우도록 같은 경계를 쓰지 않으면, 되살릴 수도 없고 아직 지워지지도 않은 원천이 한 순간 남는다. 티켓 14가 같은 경계를 쓰게 다음에 적었다.
- 명세 274행, 282행, 287행의 그사이 다시 지웠다는 문장과 되살리는 요청도 `source_change_in_progress`라는 문장은 이 변경의 요청 검사로는 직접 넣은 작업 밖에서 닿지 않는다. 명세는 사용자 승인으로 고치므로 건드리지 않고 다음에 적었다.
- 되살리기 작업이 재시도를 다 쓰고 실패하면 원천은 살아 있고 문서는 표시가 남은 채 숨는다. 다시 되살리기는 `source_not_deleted`다. 풀 길은 티켓 14의 다섯째 단계(명세 307행)이고 그 단계가 이 작업을 다시 넣는다.
- 중복 냄새. `restore_source._lock_live`와 `_lock_knowledge_bases_of`가 `delete_source`의 것과 같은 모양이고 잠금 모드만 다르다. 합치려면 이미 병합된 삭제 쪽을 건드리고, 같은 파일을 고치는 티켓 13과 글자 충돌이 늘어난다. 같이 바뀌어야 하는 일이 생기면 합친다.
- Nit. 시험 픽스처(`_admin`, `_create_push`, `Gate`)가 앞 티켓 시험의 복사, `WRONG_SOURCE_KIND` 거절이 `pull_sources`에 둘, 요청 ID, 시각, 보관 일수가 함께 다니는 묶음, `_restore_batch`와 `_requeue_stalled`가 반복 제어로 참거짓을 돌려주는 것. 판단 항목이고 고치려면 쓰는 곳이 없는 장치를 더하게 된다.

## PR 직전 리뷰

CodeRabbit CLI 0.7.5가 끝까지 돌았다(`Seat: not assigned`, 계정 Plan은 Free, `review_completed`, 35개 파일, 지적 5건, 종료 코드 0). CLI가 도므로 `bug-perf-review`는 부르지 않았다. 내장 `/security-review`는 따로 돌았고 발견이 없었다(새 라우트는 `admin` 전용 라우터에 붙고, 새 질의는 모두 바인딩이며, 되살린 문서는 문서 행의 그룹과 그 그룹이 든 지식베이스의 살아 있는 판으로만 돌아간다). 보안 하위 작업에 넘긴 범위는 `git diff`가 아니라 기준 커밋 `4d0b692`부터의 변경이었다(스킬이 채우는 `origin/HEAD...` diff가 이 워크트리에서 비어 나왔다).

**고친 것**
- `PullSources.restore`가 잠그기 전에 읽은 설정으로 폴더 겹침을 봤다. 폴더를 살피는 호출은 한도(10초)까지 붙잡힐 수 있고, 그사이 같은 원천의 폴더가 바뀌고 원천이 지워지고 바뀐 폴더를 다른 원천이 쓰면 옛 폴더만 보고 받아들였다. 잠근 뒤 원천의 설정이 읽은 값과 다르면 그 설정으로 겹침을 보고 살핀 위치는 버린다(글자 견줌으로 떨어진다). 시험(폴더를 여는 호출을 붙잡은 채 폴더 변경, 지우기, 겹치는 원천 만들기를 끝낸 뒤 풀어 준다)은 고치기 전에 `202`로 빨갛고 고친 뒤 초록이다. 변이 하나를 더했다.

**남긴 것과 이유**
- `_requeue_stalled`가 실행 중인 색인 작업이 있는 문서를 건너뛴다. 그 작업이 이미 "지운 원천이라 아무것도 쓰지 않는다"고 정했으면 문서가 멈춘 채 남을 수 있다는 지적이다. 명세 283행이 멈춘 문서를 "색인 작업이 대기 중도 실행 중도 아닌 문서"로 정했고, 필요한 틈은 지움 표시가 선 동안 돈 작업이 끝을 기록하기 전에 삭제와 되살리기가 모두 지나가는 아주 짧은 사이다. 명세를 따랐다.
- `_lock_deleted_with_source`가 잠근 뒤 `purged_at`을 다시 보지 않는다는 지적. 티켓 14의 첫째 항목은 표시가 있는 문서를 지우지 않고, 둘째 항목은 지움 표시가 선 원천 전체를 지운다(되살린 원천은 지움 표시가 없어 지우지 않는다). 그래서 되살리기 작업이 후보를 읽은 뒤 그 문서가 비워지는 길이 없다.
- 오탐 둘. 동기화의 분기가 이미 표시를 걷는다는 것(`sync_source._delete_one`이 `detach_from_source_deletion`을 부른다). 건너뜀 문서가 상태 행 없이 반복 선택된다는 것(`index_document._record_skipped`와 `restore_locked_document`의 건너뜀 길이 대상 판마다 `indexed`를 쓴다).

**PR 직전 리뷰에 밀 주장.** CLI에는 주장을 넘기는 길이 없어 반영으로 새로 쓴 문장을 원문 그대로 남긴다.
- `pull_sources.py`: "폴더를 살피는 사이 같은 원천의 설정이 바뀌고 지워졌다. 살핀 위치는 옛 폴더의 것이다."
- `restore_source.py`와 `delete_source.py`: "지우는 요청과 되살리는 요청은 서로의 작업이 끝나기 전에는 거절되므로 그 밖의 길로는 서지 않지만 묶음마다 다시 본다"(`delete_source`는 "걷히지 않지만").
- `ports.py`(`list_stalled_ids_of_source`): "지금 내용으로 색인되지 않은 판은 색인 상태가 `pending`이거나 상태 행이 없거나, `indexed`인데 만든 내용 해시가 문서의 내용 해시와 다른 판이다. `failed`는 정착한 것으로 본다."
- `admin_source_api.py`: "지운 원천은 보기, 되살리기, 동기화 기록 보기만 받고".
- `ingest.py`(`_restore_chunks`): 건설 중인 판이 전환되는 조건은 모든 색인 상태가 `indexed`나 `failed`인 것이라는 문장(독스트링 485~486행).

## 검증

- 이 티켓의 시험 열넷 묶음(서버 왕복 9, 앱 5, 가져오는 원천 6, 어댑터 5)과 고친 시험 69개를 따로 돌려 모두 초록이었다.
- `restore_source_mutations.toml`의 변이 열둘이 모두 기대대로 빨강이다. pre-commit이 변이 표지에서 단언을 풀어 쓴 줄 네 개를 거절해, 시험 원문에 없고 실패 때만 찍히는 값(`At index 1 diff: 0 != 1`, `<Response [202 Accepted]>`, `assert None is not None`, `At index 0 diff: 202 != 409`)으로 바꾸고 변이 4, 8, 9, 12를 번호로 다시 돌려 빨강을 확인했다. 아홉째 변이의 시험은 `isinstance(…)` 단언을 `is not None`으로 바꿨다(문자열인지는 JSON이 정한다).
- 전체 시험에서 `test_답하지_않는_것으로_기억된_원천과는_기다리지_않고_글자로_견준다`가 두 번 1.0초 상한을 약간 넘겨(1.219초, 1.094초) 졌다. 홀로 돌리면 초록이고 서버 처리는 83ms였다. 이 변경이 닿지 않는 생성 경로의 시험이고 윈도에서 연결 재시도가 병렬 부하에 겹친 것으로 본다. 훅을 건너뛰지 않고 다시 커밋한다.
- 첫 커밋 시도(전체 24분)에서는 위 시험 파일의 네 시험(1.03초, 2.28초, 1.72초, 3.08초로 상한 1.0초 초과)과 이 티켓의 서버 왕복 시험 둘(`_seed`의 검색에서 클라이언트 `ReadTimeout`)이 졌다. 두 파일을 홀로 돌리면 22개가 모두 초록이었다(405초). 같은 실행에서 시간 시험이 함께 늘어진 것으로 보아 PC 부하 탓이다. 두 번째 시도에서 전체가 초록이어야 커밋한다.

## 다음

- 이어서 할 티켓은 14(하루 한 번 정리)다. 티켓 14 파일 끝에 이 세션이 넘긴 메모를 적었다. 보관 경계는 `삭제 시각 + 보관 일수 <= 지금`을 만료로 보고(되살리기가 같은 식으로 거절한다), 되살리기 작업이 재시도를 다 쓰고 실패한 원천을 푸는 길은 다섯째 단계뿐이다.
- 명세 고침은 사용자 승인이 있어야 한다. 아래 둘을 승인받아 고친다. 하나는 283행의 멈춘 문서 정의다. 구현은 만든 내용 해시가 문서의 것과 같은 `indexed`와 `failed`만 정착한 것으로 본다. 다른 하나는 274행, 282행, 287행이다. 지우는 요청과 되살리는 요청이 서로의 작업이 끝나기 전에 거절되므로 그 문장들은 작업을 대기열에 직접 넣은 길에서만 닿는다.
- 티켓 13(PR 113)이 이 PR보다 먼저 병합되어 `restore_chunks.py`가 양쪽에서 새로 생긴 파일이 되었다. 병합에서는 티켓 13의 본체(건너뜀 문서를 안에서 처리하고 잠근 지식베이스 행의 판만 대상으로 삼는다)를 취하고, 이 티켓의 `restore_locked_document`는 그 위의 얇은 겉껍질로 줄였다. 오류 코드는 스물여섯(HTTP)이 되었고 `test_delete_restore.py`의 같은 고침과 `delete_restore_mutations.toml`의 두 변이(15, 16번)를 합친 본체에 맞췄다. 합친 뒤 관련 시험 509개, 린트, 포맷, 타입, 경계가 초록이고 변이 15, 16번이 빨강이다.
- 전체 시험을 부하 아래에서 돌리면 `test_admin_pull_source_stuck_calls.py`의 시간 시험 넷이 1.0초 상한을 넘어 지는 일이 이번 세션에서 세 번 나왔다(홀로 돌리면 초록). 같은 실수의 반복 횟수를 retro 대기열에서 센다.
