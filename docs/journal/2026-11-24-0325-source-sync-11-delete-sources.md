# source-sync 11: 원천 삭제 · 2026-11-24

source-sync 티켓 09를 병합한 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5). 시작 프롬프트는 `/implement .scratch/source-sync/issues/11-delete-sources.md`이고, 브랜치는 `feature/11-delete-sources`, 작업은 워크트리 `11-delete-sources`에서 했다. 요청 범위는 PR과 병합까지다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 준비

- 읽은 것: 티켓 11, 명세 `.scratch/source-sync/spec.md`의 "원천 삭제와 되살리기", "동기화의 차례", "관리 API", "Testing Decisions", ADR 0013과 0023, 09 일지의 "다음".
- 지시문이 시킨 순서: `tidy-checkouts`를 먼저 돌았고, `EnterWorktree`로 새 워크트리에 들어가 브랜치를 바꿨다. 형제 워크트리(`14-reindex-version-switch`, `glossary-release-number-names`)와의 겹침은 `tools/sibling_overlap.py`로 봤다.
- 시험용 PostgreSQL은 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`로 붙여 돌렸다.

## 지은 것

- **도메인.** 오류 코드 `source_deleted`와 `source_protected`를 더했다. 작업 코드는 스물하나(동기화 실패 코드에 `source_deleted`), HTTP 코드는 스물둘이다. 문서에 `deleted_with_source`(원천과 함께 지워졌다는 표시)를 더하고, 포트에 `lock_source_shared`, `mark_source_deleted`, `list_undeleted_ids_of_source`, `lock_queued_source_job`, `delete_queued_job`를 더했다. 마이그레이션은 없다(스키마는 0004에 이미 있었다).
- **원천 삭제 요청.** `DELETE /sources/{name}`(202, 작업 식별자)이 한 작업 단위에서 원천 행을 잠그고 지움 표시를 쓰며, 대기 중인 동기화 작업을 지워 그 기록을 `failed`와 `source_deleted`로 닫고, 원천 삭제 작업을 넣는다. `default`와 `upload`는 409 `source_protected`, 이미 지운 원천은 409 `source_deleted`다.
- **지운 원천의 문서가 지워진 것으로 읽힌다.** 검색 SQL이 지움 표시가 선 원천의 조각을 빼고, `get_document`는 `document_not_found`, 관리 API의 문서 조회와 목록은 `deleted`로 보인다. 목록의 상태 거르기도 그 원천의 문서를 `deleted`로 센다. 문서 수를 세는 자리는 그대로 문서 행의 지운 시각만 본다.
- **원천 삭제 작업.** 작업자가 문서를 50건씩 묶어 묶음마다 작업 단위 하나에서 원천 공유 잠금과 지움 표시를 다시 본 뒤 문서를 삭제 보관함으로 옮긴다. 지운 시각은 원천의 지운 시각이고 `deleted_with_source`가 선다. 원천을 지우기 전에 따로 지운 문서는 건드리지 않는다.
- **수집과 동기화.** 수집 API는 지운 원천에 409 `source_deleted`이고, 문서를 넣는 작업 단위가 맨 먼저 원천 행을 공유 잠금으로 잡는다. 동기화는 시작, 실행 표시, 문서 하나를 넣거나 지우는 작업 단위, 변경 확인값 갱신에서 지움 표시를 보고, 작업 담당 기록의 기한을 늘릴 때도 본다. 늘리는 쪽이 표시를 보면 처리를 취소하고 그 시도를 버리지 않은 채 기록을 `failed`와 `source_deleted`로 닫는다. 색인 작업은 첫째 단계에서 지운 원천의 문서를 보면 아무것도 쓰지 않고 성공으로 끝난다.
- **관리 API.** 지운 원천은 보기와 동기화 기록 보기만 받고 고치기, 지우기, 연결 확인, 지금 동기화, 일시 중지, 다시 시작은 409 `source_deleted`다. `GET /sources`는 `include_deleted=true`를 적어야 지운 원천도 낸다.
- **시험.** `tests/server/test_delete_source_round_trip.py`(실제 서버와 실제 작업자, 공식 MCP 클라이언트로 8개)와 `tests/app/test_delete_source.py`(동기화의 지움 표시 자리, 끝없는 목록, 읽는 중 삭제, 50건 묶음, 직접 넣은 작업, 잠금 순서 둘)를 더하고, 색인 작업 시험과 오류 코드 시험을 고쳤다. 변이는 `.scratch/source-sync/probes/delete_source_mutations.toml`에 일곱 개를 넣었다.

## 이 세션이 정한 것

- **잠금 순서를 색인 작업에도 지켰다.** 색인 작업의 첫째 단계는 문서 행을 먼저 잠그지만 문서가 속한 원천을 알아야 원천 공유 잠금을 먼저 잡을 수 있다. 문서를 잠그지 않고 읽어(`documents.get`) 원천을 알아낸 뒤 원천, 문서, 작업 행 순서로 잠근다. 문서의 원천은 바뀌지 않아서 안전하다.
- **상태 거르기는 EXISTS로 했다.** `list_documents`에서 지운 원천의 문서를 `deleted`로 세려고 원천 표를 이어 붙이는 대신 상관 부질의(`EXISTS`)를 썼다. 나머지 상태에서는 `NOT EXISTS`로 뺀다.
- **검색 SQL의 모양.** 바깥 `LEFT JOIN`은 조각이 하나도 남지 않아도 한 행이 나오게 하는 꼴이다. 안쪽 부질의가 지운 원천을 빼면 `is_current` 행을 살려 바깥 질의가 그대로 돈다.

## 겪은 것

- **원칙 I(테스트 먼저)를 지키지 못했다.** 이번에는 구현을 거의 다 쓴 뒤에 시험을 썼다. 변이로 시험이 빨개지는 것을 확인해 메웠다(아래 "검증").
- 관리 API 시험의 `GET`이 쿼리 매개변수를 JSON 본문으로 보내 거르기가 먹지 않았다. 처음에는 목록 SQL의 결함으로 의심했으나 시험 도우미(`_admin`)의 한계였고, 쿼리를 받는 `_documents`를 따로 뒀다. 이어서 `status=indexed`는 허용되는 상태가 아니라 422였다(`parsed`로 고쳤다).
- 편집 도중 Pyright가 import를 못 찾는다는 진단을 여러 번 냈다. 편집 순서 때문의 일시 현상이었고 `uv run pyright`는 0 오류였다.
- 한글 줄이 ruff 100칸을 넘는 것을 훅이 알려 줬고 `tools/rewrap_comments.py`로 감았다.
- 첫 커밋 시도가 변이 표 검사(`tools/mutate.py --staged`)에서 막혔다. 내가 고친 소스 줄을 원문으로 든 다른 표의 변이 다섯(`admin_queries` 1, `delete_restore` 2, `lease_worker` 2)이 원문이 한 번도 안 나오게 됐고, 내 표의 변이 하나(순서를 바꾼 `source_lookup.py`)도 같았다. 내 표의 표지 넷은 pytest가 단언을 풀어 쓴 줄이라 품질 검사가 거절했다. 원문을 새 소스에 맞게 고치고 표지를 pytest가 값을 견주어 찍는 차이 줄(`Extra items in the left set:` 같은 것)로 바꾼 뒤 손댄 변이를 하나씩 다시 돌려 모두 기대한 까닭으로 빨개지는 것을 봤다.

## 셀프 리뷰

`/code-review`를 base `ea3e404`(커밋 없이 작업 폴더의 변경만)로 돌렸다. 표준 축(sonnet·high)과 명세 축 보고에서 고친 것과 남긴 것은 다음과 같다.

- **고친 것.**
  - 시험 `test_수집이_먼저_잡은_원천에_삭제_요청이…`가 `RequestError`만 확인하던 것을 `code is SOURCE_DELETED`까지 단언하게 했다(표준: 실패를 기대하는 시험은 까닭까지 단언한다).
  - 항상 참인 `assert ErrorCode.SOURCE_DELETED.value == "source_deleted"`를 지웠다.
  - `ports.py`의 `lock_source_shared` 설명이 부르는 쪽을 "넣거나 지우거나 옮기는"으로 적었으나 수집 API의 삭제(`delete_document`)는 이 잠금을 잡지 않는다. "넣거나 옮기는"으로 고치고 색인 작업의 첫째 단계를 더했다.
  - `delete_source.py` 머리 설명이 지운 원천의 문서가 모든 자리에서 지워진 문서로 읽힌다는 보편 주장처럼 읽혀, 읽는 자리(검색, `get_document`, 관리 API의 문서 조회와 목록)로 한정하고 문서 수를 세는 자리는 문서 행만 본다고 적었다.
  - `sync_source.py` 머리 설명에 시작 때의 `source_deleted`와 기한을 늘리는 쪽의 길을 적었다.
  - 이 티켓이 12(원천 되살리기)의 일을 앞당긴 `ingest._restore`의 `deleted_with_source=False`를 되돌렸다(명세는 12에 둔다. 이 티켓에서는 닿을 길이 없다).
  - `_leased`가 취소를 알린 순간 처리가 이미 끝나 있었다면 끝난 결과를 버리지 않고 돌려주게 했다. 이전에는 기록은 `succeeded`인데 작업은 `failed`/`source_deleted`가 되는 틈이 있었다.
  - 시험을 더했다. 파일 하나를 읽다 멈춘 동기화가 기한을 늘릴 때 멈추는 길(티켓의 "읽는 중 삭제"의 기한 연장 쪽), 원천을 지우면 `next_run_at`이 비는 것.
- **되돌린 것.** 지운 원천에 대기 동기화가 남는 틈(`request_sync`가 원천 행을 잠그지 않아 삭제 요청과 겹친다)을 막으려고 `request_sync`에 공유 잠금을 더했더니 티켓 10의 시험 `test_일정_확인이_원천_행을_잡은_동안에도_지금_동기화_요청은_기다리지_않는다`가 빨개졌다. 그 시험이 지키는 결정(일정 확인이 원천 행을 잡아도 지금 동기화 요청은 기다리지 않는다)이 이 틈보다 앞서므로 잠금을 되돌렸다. 남는 대기 동기화는 시작에서 `source_deleted`로 닫히므로 문서는 새지 않는다.
- **남긴 것과 이유.**
  - 키워드 전용 불리언 `with_source`(`delete_locked_document`)와 `include_deleted`(`list_source_reports`). `CODING_STANDARDS.md`는 키워드 전용으로 옮겨 지나간 플래그를 쪼개라고 하지만, 앞의 것은 같은 일(잠근 문서를 삭제 보관함으로 옮기기)에 표시 한 칸만 다르고, 뒤의 것은 API의 쿼리 매개변수를 그대로 받은 값이다. 갈래를 고르는 플래그가 아니라 값으로 보아 남겼다. 반려가 나오면 쪼갠다.
  - "지운 원천의 문서는 지워진 문서"를 `await_documents`, `eval_run`, `check_indexed_documents`, `job_failure`가 보지 않는다(문서 행의 지운 시각만 본다). 작업자가 문서 행을 옮기고 나면 모두 같아지고, 지운 원천의 문서를 기다리는 호출이 그 사이에만 영향을 받는다. 이 티켓의 읽는 자리 목록(검색, `get_document`, 관리 API)에는 없다.
  - 기한 연장 쪽이 멈춘 동기화(`close_after_source_deleted`)는 그때까지 센 개수를 남기지 않는다. 취소한 처리 안의 개수를 가져올 길이 없어서이고, 문서를 쓰는 작업 단위에서 표시를 본 길은 개수를 남긴다. 명세 "동기화 기록"의 "실패로 끝난 동기화도 그때까지 센 개수를 남긴다"와 어긋난다. 아래 "다음"에 적는다.
  - `_delete_batch`가 묶음을 옮기는 명령이면서 계속할지(bool)를 돌려주는 것, 시험 도우미 `_push_source`와 `_create_push`가 계약 시험의 `_create_push_source`와 겹치는 것. 모두 판단 항목이고 이 크기에서 고치지 않았다.
  - 시험 이름이 구현(`deleted_with_source` 칸, 기한 연장)을 말하는 것. 장면을 서술하는 이름으로 바꾸는 것은 판단 항목이다.

## PR 직전 리뷰

- **보안 리뷰(`/security-review`).** 확신 8 이상인 취약점이 없었다. 새 `DELETE` 경로가 `admin` 토큰만 받는 라우터 안에 있고, 검색 SQL의 그룹 제한과 `is_current` 조건이 그대로이며, 새로 문자열에 끼는 사용자 입력이 없다는 것을 확인했다.
- **CodeRabbit CLI(`coderabbit review --agent --include-untracked --base origin/dev`).** 지적 셋이 나왔다.
  - 유효 하나(Minor): `require_push_source`와 `require_pull_source`가 종류 검사를 지움 검사보다 먼저 해서, 지운 원천에 어긋난 종류로 요청하면 `source_deleted` 대신 `wrong_source_kind`가 났다. 티켓이 지운 원천은 보기와 동기화 기록 보기를 빼고 모두 409 `source_deleted`로 거절하라고 적었으므로 지움 검사를 앞으로 옮기고 시험(`test_지운_밀어_넣는_원천에_가져오는_원천용_요청을_보내도_source_deleted다`)을 더했다.
  - 오탐 둘(Major로 났다): 작업자가 돌기 전의 검색(이미 `_final_select`의 `JOIN … s.deleted_at IS NULL`로 막혀 있다), 취소한 처리를 `gather`가 무기한 기다린다는 지적(스레드로 도는 커넥터 호출은 기다리는 쪽을 취소하면 future가 곧바로 취소되고 스레드는 따로 끝난다. `server_path._call_in_thread`가 그렇다).
  - 별도 관찰(Minor, 남김): 후보 상한이 `chunks` 표만 보고 먼저 적용되므로, 작업자가 문서를 옮기기 전에는 지운 원천의 조각이 후보 자리를 차지해 같은 지식베이스의 정상 결과가 요청 개수보다 적게 나올 수 있다. 티켓이 "후보를 뽑는 질의는 지금처럼 조각 표만 읽는다"고 정한 설계이고, 지운 조각은 결과에 나오지 않으며 작업자가 끝나면 사라진다.

## 검증

- 손으로 치는 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, `uv run python tools/check_type_escapes.py`가 모두 0으로 끝났다. 전체 `uv run pytest -n 4`는 반영 전 코드에서 5757개 통과(13분 10초)였고, 반영 뒤 바뀐 자리에 닿는 `tests/app`, `tests/server`, `tests/domain` 1077개가 통과했다.
- 변이(`.scratch/source-sync/probes/delete_source_mutations.toml`, 일곱 개)가 모두 기대한 시험에서 기대한 단언으로 빨개졌다. 표지는 각 변이가 낸 값 차이를 pytest가 찍은 줄이다. 변이 4(수집의 원천 공유 잠금을 뺀다)는 겹침 시험이 아니라 읽는 중 삭제 시험이 먼저 빨개졌다(`-x`로 첫 실패에서 멈춘다. 수집의 `_record_in`이 그 자리의 검사도 한다). 변이 2(수집 API가 지운 원천을 거절하지 않는다)는 수집의 거절이 `_record_in`의 잠금 확인과 두 군데에서 나서, 문서 삭제 요청의 거절에서 빨개졌다.
- 새 시험: 서버 왕복 8개, 앱 시험 10개, 색인 작업 시험 1개. 테스트 PostgreSQL은 `compose.test.yml`의 컨테이너로 돌렸다.

## 회고

후보 여섯, 승인 하나(회차를 더한 것), 기각 다섯, 넘김 없음.

- **승인(회차로 센다).** 시험을 구현 뒤에 썼다(서버 왕복 시험 8개와 앱 시험을 구현 코드가 거의 다 선 뒤에 써서 처음부터 초록이었다). 열린 항목 `surface-tests-after-implementation`의 처방이 막는 사건이라 그 항목의 승인 줄에 5회차를 더했다(4회차에서 5회차가 되었다). 층은 지침(스킬 `implement`)이고 이 항목이 5회차에 이르러 chore 배치 조건이 된다. 이 PR에서는 반영하지 않는다.
- **기각.**
  - 맨 `python`과 큰 heredoc을 훅이 막았다: 훅이 그 자리에서 막았다.
  - 변이 표의 `expect_output`을 시험 이름으로 적어 도구가 거절했다: 도구가 그 자리에서 알렸다.
  - 관리 API 시험의 `_admin` 도우미가 쿼리 매개변수를 JSON 본문으로 보내 필터가 먹지 않았다: 시험 도우미 하나의 결함이고 `_documents`를 따로 뒀다. 사건 하나이고 같은 꼴의 검사로 옮길 수 없다.
  - 편집 도중 Pyright가 import를 못 찾는다는 진단: 일시 현상이고 `uv run pyright`가 판정한다.
  - `request_sync`의 공유 잠금이 티켓 10의 시험을 깼다: 기존 시험이 그 자리에서 잡았다.

## 다음

- 11은 끝났다. 열린 것은 12(원천 되살리기), 13(문서 되살리기), 14(정리 작업), 15(단독 설치의 원천 폴더)다. 12는 원천 행 잠금과 원천 삭제 작업의 걷힌 지움 표시를 서로 맞춰야 한다. 되살리기도 같은 잠금 순서(원천 행, 문서 행, 지식베이스 행, 작업 행)를 쓴다.
- 12가 알아야 할 것: `deleted_with_source`가 선 문서만 되살리고 따로 지운 문서는 건드리지 않는다. 문서 행의 표시는 `ingest._restore`가 풀지 않는다(이 티켓은 되돌렸다). 되살린 원천에 지운 원천 시절 들어온 대기 동기화가 남을 수 있다(`request_sync`가 원천 행을 잠그지 않는다). 시작에서 닫히므로 문서는 새지 않는다.
- to-spec이나 명세 갱신으로 넘길 것: 기한 연장 쪽이 멈춘 동기화는 개수를 남기지 못한다. 처리를 취소하기 전에 개수를 가져오는 길(처리가 개수를 공유 객체에 두거나 취소가 개수를 낸다)을 정하거나, 명세 "동기화 기록"의 문장을 이 경우를 뺀 것으로 고친다.
- 하네스로 따로 할 일: 지운 원천의 문서를 기다리는 호출(`await_documents`), 색인 확인(`check_indexed_documents`), 평가(`eval_run`)가 원천 지움 표시를 보지 않는다. 필요하면 "지운 원천의 문서는 지워진 문서"를 읽는 자리를 한 곳으로 모으는 것을 14(정리 작업)와 함께 정한다.
