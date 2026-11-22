# source-sync 03: 밀어 넣는 원천을 만들고 보는 관리 API와 수집 API의 원천 이름 · 2026-11-22

source-sync 티켓을 나눈 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/source-sync/issues/03-push-sources-and-ingest-source-name.md`이고, 브랜치는 `feature/03-push-sources-and-ingest-source-name`, 작업은 워크트리 `03-push-sources-and-ingest-source-name`에서 했다. 요청 범위는 PR과 병합까지다. 나란히 여는 네 티켓(02, 03, 04, 05) 가운데 둘째다.

## 준비

- 주 체크아웃이 아니라 `EnterWorktree`로 새 워크트리에 들어가 브랜치를 바꿨다. `tidy-checkouts`는 묶음의 첫 세션이 돌아서 이 세션은 돌리지 않았다.
- 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 지은 것

**원천 이름의 규칙.** `domain/source_names.py`에 1~63자, 영문 소문자·숫자·`-`·`_`, 영문 소문자나 숫자로 시작하는 규칙을 두었다. 정규식은 최대 길이(63)에서 파생한다. 입구 둘(관리 API, 수집 API)은 이 값을 pydantic `pattern`으로 쓰고(`server/source_name.py`의 `SourceName`), 기본 원천 `default`와 `upload`가 규칙에 맞는지는 시험이 본다.

**기본 레코드.** `app/default_records.py`가 `default`와 함께 `upload`를 밀어 넣는 원천으로 만든다. `Catalog.add_source`가 멱등이라 `migrate`를 다시 돌려도 둘째가 생기지 않는다.

**도메인과 포트.** `Source`에 만든 시각(필수)과 지운 시각을 더했다. `DocumentCounts`(전체, 실패, 건너뜀)와 `DocumentQuery.source_id`를 더했다. `Catalog.create_source`(이름이 겹치면 `SourceAlreadyExistsError`), `Catalog.list_sources`, `DocumentStore.count_documents_of_source`를 더했다. 오류 코드 `source_not_found`(404)와 `source_already_exists`(409)를 Problem Details 코드에 더하고 코드 수를 적은 머리 설명을 열여섯으로 고쳤다.

**어댑터.** `adapters/postgres/catalog.py`는 `create_source`가 이름의 유일 제약 위반만 `SourceAlreadyExistsError`로 바꾸고, `list_sources`가 만든 시각 순(같으면 ID 순)으로 낸다. `document_store.py`는 문서 목록을 원천으로 거르고, 원천의 문서를 지워지지 않은 것만 상태별로 센다.

**유스케이스.** `app/source_lookup.py`의 `require_source`가 이름(없으면 `default`)으로 원천을 찾고 없으면 `source_not_found`를 올린다. 넣기(`ingest.py`)와 지우기(`delete_document.py`)가 이것을 쓴다. `app/admin_sources.py`가 원천을 만들고(`create_push_source`) 목록과 하나 보기(`SourceReport`)를 낸다. `admin_queries.list_document_reports`는 `source` 필터를 받고, 모르는 원천 이름이면 빈 목록을 낸다.

**서버.** 관리 API에 `POST /sources`(201), `GET /sources`, `GET /sources/{name}`을 더했다(`server/admin_source_api.py`, `admin_source_models.py`). 만들기 본문은 `name`과 `kind: "push"` 둘만 받고 그 밖의 칸은 422다. 응답은 가져오는 원천만 쓰는 칸을 모두 null로 내고 `documents`는 `{total, failed, skipped}`, `last_sync`는 늘 null이다. 수집 API의 넣기 폼과 지우기 쿼리에 `source`를 더했고, 관리 API의 문서 목록에 `source` 필터를 더했다.

**시험.** `tests/domain/test_source_names.py`, `tests/adapters/test_catalog_sources.py`, `tests/server/test_admin_sources.py`, `tests/server/test_ingest_sources.py`가 새로 생겼고 `test_errors.py`, `test_migrate_command.py`, 시험 보조(`records.py`, `support/`)와 `test_admin_queries.py`, `test_unit_of_work.py`를 맞췄다. 티켓의 주 이음매 시험(같은 키가 원천 둘에서 다른 문서로 남음, `source` 없음·`upload`·없는 이름의 차례, 작업자 한 번 뒤 검색에 나옴, 규칙에 어긋나는 이름 셋이 만들기와 수집 모두 422, 지우기가 그 원천 문서만 지움)는 실제 서버와 실제 작업자로 돈다.

## 이 세션이 정한 것

- **`create_source`를 따로 두었다.** `add_source`에 반환값을 주어 "이미 있었다"를 알리면 명령과 조회가 섞인다(`CODING_STANDARDS.md`의 CQS 줄). 문서를 만드는 길이 `DocumentAlreadyExistsError`를 올리는 선례도 있어서, `migrate`가 쓰는 `add_source`는 멱등으로 두고 관리 API가 쓰는 `create_source`는 예외를 올리게 나눴다.
- **넣기 폼의 빈 `source=`는 적지 않은 것으로 읽힌다.** FastAPI가 폼의 빈 문자열을 없는 값으로 읽어 `default`로 간다(`group`과 같은 동작이다). 처음에는 빈 값이 422라고 쓴 시험이 있었으나 202가 나와 그 사례를 지웠다. 반면 지우기의 쿼리 `source=`는 빈 값이 패턴에 걸려 422다(셀프 리뷰가 물어서 시험으로 재 확인했다).
- **`Source` 엔티티에는 가져오는 원천만 쓰는 칸을 아직 두지 않는다.** 응답이 그 칸을 모두 null로 박아 낸다. 그 칸을 읽고 쓰는 06이 엔티티와 응답을 함께 고친다. `last_sync`도 타입이 `None`으로 굳어 있다.
- **모르는 원천 이름으로 문서 목록을 거르면 404가 아니라 빈 목록이다.** 명세가 `group`과 같은 거르개로 적었고, 목록은 거르개일 뿐 원천을 찾는 요청이 아니다.
- **입구가 이름 규칙을 판정하고 유스케이스는 다시 보지 않는다.** 규칙은 도메인에 두되 거절은 HTTP 입구의 `pattern`이 422로 낸다.
- **`require_source`는 지운 원천과 가져오는 원천을 걸러 내지 않는다.** 그 거절(`source_deleted`, `wrong_source_kind`)은 티켓이 11과 06으로 넘겼다.

## 겪은 것

- 맨 `python3` 호출과 `source`가 든 heredoc·`sed` 명령을 훅이 막았다. `uv run python`과 Read·Grep 도구로 바꿨다.
- 한글 폭 때문에 줄 길이 경고(E501)가 여러 번 났다. `tools/rewrap_comments.py`와 `ruff format`으로 감았다.
- 호출하는 쪽 서명을 바꿨더니 `tests/support/pipeline.py`와 `tests/app/test_admin_queries.py`가 pyright에 걸렸다. 두 곳에 새 인자를 넘겼다.
- 편집기의 pyright 진단이 새 모듈을 못 찾는다고 여러 번 띄웠지만 명령줄 `uv run pyright`는 0건이었다(편집기 캐시다).
- 처음 돌린 시험이 `RAG_TEST_DATABASE_URL`이 없다고 실패해, 이미 떠 있는 공용 테스트 PostgreSQL(55432 포트)을 가리키게 했다.

## 셀프 리뷰

`/code-review`를 고정점 `origin/dev`(base `3c30d47`, HEAD와 같다)로 돌렸다. 본 범위는 고친 추적 파일 스물둘, 미추적 파일 열, 커밋 0이다. 표준 축은 Sonnet(노력 high), 명세 축은 이 세션의 모델로 돌렸다. 두 축에 주장 검증 목록과 밀 주장(오류 코드 수, 정규식 주석, 포트 독스트링)을 넘겼다.

### 보고

- **표준 축.** 하드 위반은 Minor 둘이다. `test_add_source는_같은_이름이_있으면_아무것도_하지_않는다`는 이름에 함수명이 든다(테스트 이름은 행동 명세). `test_reader_토큰은...`은 상태 코드만 보고 `code`를 보지 않는다(실패의 까닭까지 단언한다). 주장 검증에서 거짓 둘이 나왔다. `source_names.py`의 주석(앞뒤를 고정한 꼴이라 정규식 엔진이 부분 일치로 받지 않는다는 말)은 `re.match`와 `re.search`에서 틀리고(`$`가 끝의 개행을 받는다), `re.fullmatch`와 pydantic만 `"abc\n"`을 거절한다. 같은 파일 머리 설명의 기본 원천을 만드는 쪽도 이 규칙 하나를 쓴다는 말도 거짓이다(`default_records.py`는 이 모듈을 import하지 않고 시험만 쓴다). `ports.py`의 `create_source` 독스트링 "늦은 쪽의 커밋을 기다린 뒤"는 기다리는 쪽과 대상이 거꾸로 읽히고 겹친 두 요청을 시험하는 곳도 없다. `CreateSourceRequest`의 "이름만 받으므로"는 `kind`를 빠뜨렸다. `test_catalog_sources.py`의 첫 시험 이름은 "지운 시각이 실린다"인데 `None`만 본다. 판단 항목은 문자열 리터럴 `"failed"`, `"skipped"`(Primitive Obsession), `{0,62}`와 63의 같은 지식 둘, `DocumentCounts`와 `DocumentCountsResponse`의 같은 세 칸, `source`·`source_name`·`source_id` 이름 갈림, `add_source`와 `create_source`의 이름 차이, 기본값 `= None`이다. 오류 코드 수 "열여섯"과 `list_sources`의 정렬 서술은 맞았다.
- **명세 축.** 빠졌거나 부분인 요구는 없었다. 티켓의 시험 체크박스 장면(같은 키가 원천 둘에서 다른 문서로 남는다, `source` 없음·`upload`·없는 이름이 차례로 default·upload·404다, 넣은 문서는 작업자 한 번 돈 뒤 검색에 나온다, 대문자·64자·`-` 시작이 원천 만들기와 수집 API 모두 422다, 지우기 요청이 `source`로 그 원천 문서만 지운다)이 모두 시험에 있었다. 범위를 넘은 동작도 없었다. 오류 코드 수는 맞고(`열넷`, `열여섯`이 남은 자리가 없다), 정규식은 경계 입력(63자와 64자, `a\n`, 전각 `ａ`, 빈 문자열 등)으로 대 보니 규칙과 같았다. 주의점 셋이다. 첫째, 지우기 쿼리의 빈 `source=`는 패턴에 걸려 422일 가능성이 큰데 시험이 없다(넣기 폼의 빈 값은 적지 않은 것으로 읽혀 `group`과 같다). 둘째, `create_source` 독스트링이 겹친 두 요청을 말하는데 그것을 도는 시험이 없다(표준 축도 같은 지적). 셋째, `last_sync`의 타입이 `None`으로 굳어 있어 동기화 기록을 채우는 티켓이 모델을 고쳐야 한다.

### 판정과 반영

**고친 것.** 근거를 열어 맞다고 보고 모두 고쳤다.

- 정규식 주석(표준 축 거짓): 전체 일치로 쓰는 값이라고 밝히고, `re.match`와 `re.search`는 `$`가 끝의 개행도 받으므로 통과시키며 `re.fullmatch`와 pydantic의 `pattern`은 거절한다고 다시 썼다. 두 서브에이전트가 임시 스크립트로 `"abc\n"`과 63자·64자 경계를 직접 대 본 결과다.
- `source_names.py` 머리 설명: 쓰는 쪽을 "입구 둘"로 줄이고 기본 원천 둘은 시험이 본다고 적었다. 시험 `test_source_names.py`가 실제로 그 둘을 대 본다.
- 정규식의 `{0,62}`는 최대 길이 상수에서 파생한다. 같은 지식이 두 곳에 있던 것을 하나로 만들었다.
- `create_source` 독스트링: 나중에 넣는 쪽이 먼저 넣은 쪽의 커밋을 기다린 뒤 판정한다(이름의 유일 제약이 판정한다)고 바로잡았고, 그것을 도는 시험(`이름이_겹친_두_요청이_동시에_오면_하나만_만들어지고_나머지는_오류다`)을 더했다. 첫 요청이 넣고 0.3초 쥐고 있는 동안 둘째가 같은 이름을 넣어 기다린 뒤 `SourceAlreadyExistsError`를 받는다.
- `CreateSourceRequest` 독스트링: "받는 칸은 `name`과 `kind` 둘이므로 그 밖의 칸은 모두 422다"로 고쳤다.
- 시험 이름 둘: 함수명이 든 이름을 행동 명세(`기본_원천을_더하는_길은_같은_이름이_있으면_아무것도_하지_않는다`)로, "지운 시각이 실린다"는 이름을 실제로 보는 것(만든 시각이 실리고 지운 시각은 비어 있다)에 맞췄다. 지운 시각이 있는 원천이 목록에 들고 그 시각이 실리는 시험을 따로 더했다.
- reader 토큰 시험: 403 셋의 `code`가 `forbidden`이고 토큰 없는 요청은 401 `unauthenticated`임을 단언한다.
- 지우기 쿼리의 빈 `source=`: 시험에 `""`를 더해 422임을 확인했다.
- `count_documents_of_source`가 `failed`를 `DocumentState.FAILED.value`로 쓴다. `skipped`는 열거에 없어 글로 두고 그 까닭을 주석으로 적었다.

**남긴 것.**

- `DocumentCounts`(도메인)와 `DocumentCountsResponse`(서버)의 같은 세 칸: 서버의 응답 모델은 도메인 값과 따로 둔다(`IngestResponse`도 그렇다). 층 사이의 복사는 의도한 것이라 접었다(Data Clumps, 판단 항목).
- `skipped`의 문자열: 문서 상태 열거에 그 상태가 아직 없다. 건너뜀을 쓰는 02가 열거를 다룰 때 같이 옮기는 것이 자연스럽다(Primitive Obsession, 판단 항목).
- `source`·`source_name`·`source_id`로 갈린 이름: 입구와 유스케이스의 인자는 이름(글)이고 `source_id`는 UUID라 값이 다르다. 인자 이름을 하나로 맞추는 것은 Nit이라 남긴다.
- `add_source`(멱등)와 `create_source`(겹치면 예외)의 이름 차이: `add_source`는 앞 티켓부터 있는 이름이고 `migrate`가 부른다. 독스트링이 차이를 적는다.
- `IngestRequest.source`와 `DocumentQuery.source_id`의 `= None` 기본값: 명세가 "적지 않으면 `default`"라고 했고 `source_id`가 없으면 모든 원천이다. 의도한 기본값이다.

**다시 돌린 명령.** 반영 뒤에 `ruff format .`(872개 파일 변경 없음), `ruff check .`(통과), `pyright`(0 errors), `lint-imports`(계약 둘 KEPT), `tools/check_type_escapes.py`(출력 없음), 고친 시험 세 파일(`test_source_names.py`, `test_admin_sources.py`, `test_catalog_sources.py`) 55개 통과, 지우기 쿼리 시험 5개 통과. 전체 `pytest`는 pre-commit의 검사 러너가 돌고 결과는 커밋 뒤에 이 절에 적는다.

## 검증

브랜치는 `feature/03-push-sources-and-ingest-source-name`이었고 `tools/sibling_overlap.py`는 종료 코드 0, 번호 겹침 없음이었다. 같은 파일을 고치는 형제는 `02-skipped-documents` 워크트리(`document_store.py`, `ingest.py`, `entities.py`)와 `glossary-release-number-names` 워크트리(이 PR이 고친 파일 열셋)라 나중에 병합하는 쪽에 글자 충돌이 날 수 있다. 셀프 리뷰 전에 `uv run python tools/run_checks.py`를 돌려 모든 검사가 초록이었다(전체 `pytest`가 약 845초). 리뷰를 반영한 뒤의 명령은 위 "다시 돌린 명령"에 있다. 변이 도구(`tools/mutate.py`)는 돌리지 않았다.

## 회고

후보 일곱을 냈다. 승인 하나(기존 항목의 2회차), 기각 여섯, 넘김 0이다. 일곱째는 첫 커밋 시도가 실패한 뒤에 더했다(아래 7). 후보의 낱말(`RAG_TEST_DATABASE_URL`, `compose.test.yml`)로 대기열을 찾았으나 아래 4번과 같은 일을 다룬 항목은 없었다. `tools/queue_open_rows.py`의 만료할 항목은 "(없음)"이었다. 이 세션은 `review-report-journal-lag`(열린 항목)가 처방한 대로 리뷰 보고 둘을 받은 턴에 일지로 옮겼으므로 그 항목에 더할 회차가 없다.

1. **맨 `python3` 호출과 `source`가 든 heredoc·`sed` 명령을 훅이 막았다.** 기각. 이미 있는 훅이 그 자리에서 막았고 `uv run python`과 Read·Grep으로 바꿔 한 번에 지나갔다.
2. **한글 폭 때문에 줄 길이 경고(E501)가 여러 번 났다.** 기각. `hook_ruff_line_width`가 쓰는 순간 알렸고 `tools/rewrap_comments.py`와 `ruff format`으로 고쳤다.
3. **편집기의 pyright 진단이 새 모듈을 못 찾는다고 여러 번 띄웠다.** 기각. 명령줄 `uv run pyright`가 0건이라 판정이 갈렸고 고칠 자리가 없다(편집기 쪽 캐시다). 앞 티켓 일지의 같은 후보도 같은 이유로 기각했다.
4. **처음 돌린 시험이 `RAG_TEST_DATABASE_URL`이 없어 실패했다.** 기각. `CLAUDE.md`의 검증 명령 절이 이 변수를 준비하라고 적고 있고, 환경이 없으면 skip이 아니라 실패로 곧바로 알리는 가드(`.claude/rules/tests.md`)가 그 자리에서 알렸다. 이미 떠 있는 공용 테스트 데이터베이스를 가리켜 한 번에 지나갔다.
5. **새로 쓴 사실 문장 셋이 셀프 리뷰에서 거짓으로 나왔다.** 기각. 정규식 주석("부분 일치로 받지 않는다"), 규칙 모듈 머리 설명("기본 원천을 만드는 쪽이 쓴다"), `create_source` 독스트링("늦은 쪽의 커밋을 기다린 뒤")이다. 셋 다 구현하며 처음 쓴 문장이고, 이 저장소가 셀프 리뷰의 주장 검증으로 잡도록 둔 자리에서 잡혔다. 리뷰가 제 몫을 한 사건이라 회차로 세지 않는다(4단계의 "리뷰가 잡도록 둔 기준을 어겨 리뷰가 잡은 사건"). 이 사건을 검사로 옮길 수 있는지도 보았으나 문장의 참거짓을 가리는 기계적 검사는 없다.
6. **시험에 쓴 기대 둘을 확인하지 않고 적었다.** 기각. 넣기 폼의 빈 `source=`가 422라고 쓴 시험은 돌리자 202가 나와 그 자리에서 빨갛게 드러났고, 401의 코드 이름을 `unauthorized`로 적은 단언은 쓴 직후 기존 시험을 grep해 시험을 돌리기 전에 `unauthenticated`로 바로잡았다. 시험과 확인이 사건을 그 자리에서 잡았다.
7. **첫 커밋 시도에서 pre-commit의 검사가 메모리 부족으로 빨갛게 끝났다.** 승인. 기존 항목 `concurrent-checks-exhaust-memory`의 2회차다. 사건: `pyright`와 `pyright-linux`가 노드의 `Zone Allocation failed - process out of memory`로, `pytest`가 작업자의 `MemoryError`(`tests/conftest.py`를 읽다가 났고 xdist가 작업자를 다시 띄우지 못해 `EOFError`로 끝났다)로 모두 이 변경과 상관없이 빨갰다. 그 시각 이 PC는 물리 메모리 32GB 가운데 5GB가 남아 있었고 다른 세션의 파이썬 프로세스 61개가 9GB를 쓰고 있었다. 같은 변경에서 명령줄 `pyright`는 0 errors였다. 층: 그 항목이 이미 처방한 대로 `tools/run_checks.py`가 검사를 띄우기 전에 부하를 알리는 한 줄이다. 더하는 것이라 다섯 번째에 반영하고, 커밋이 만들어지지 않았을 뿐 잃은 작업이 없어 손상이 아니다. 그 항목의 승인 줄을 2회차로 고치고 이 일지를 더했다.

## 다음

- **06이 가져오는 원천을 열 때.** `CreateSourceRequest.kind`를 `pull`까지 열고 `SourceResponse`의 가져오는 원천 칸(`connector`, `config`, `group`, `schedule`, `next_run_at`, `paused`, `exclude_patterns`)을 엔티티에서 읽게 바꾼다. 지금은 모두 null로 박혀 있다. `require_source`는 가져오는 원천의 이름을 받아도 걸러 내지 않으므로 수집 API가 `wrong_source_kind`(409)를 내는 것도 06이 맡는다.
- **11이 원천을 지울 때.** `require_source`는 `deleted_at`을 보지 않는다. 지운 원천의 이름이면 `source_deleted`(409)를 내는 것과 관리 API의 `include_deleted`는 11이 연다. `GET /sources`와 `list_sources`는 지금도 지운 원천을 모두 낸다(지운 원천이 아직 생기지 않아 보이지 않을 뿐이다).
- **07이 동기화 기록을 채울 때.** `SourceResponse.last_sync`가 타입 `None`으로 굳어 있다. 기록 칸을 읽으며 타입을 바꾼다.
- **02가 건너뜀을 쓸 때.** 원천의 `documents.skipped`는 문서 상태 `skipped`를 세지만 이 PR의 시험은 0만 본다(건너뜀 문서를 세는 시험은 07이 동기화로 본다는 티켓의 말대로다). `skipped`가 문서 상태 열거에 들어가면 `count_documents_of_source`의 글을 열거로 바꾼다.
- **글자 충돌.** 02와 `glossary-release-number-names` 워크트리가 같은 파일을 고친다. 나중에 병합하는 쪽이 충돌을 풀 때 `Source`와 `DocumentQuery`, `IngestRequest`에 이 PR이 더한 칸을 지우지 않는다.
