# core 09 검색의 완성 일지 · 2026-11-11

티켓 `.scratch/core/issues/09-search-complete-tools.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/09-search-complete-tools`, 작업은 워크트리 `search-complete-tools`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다. 구현 도중 컨텍스트가 한 번 압축되었다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 명세(`.scratch/core/spec.md`)의 검색 흐름·MCP 도구·임베딩 서버와 리랭커 어댑터 절, 직전 일지(`2026-11-11-0615-core-07-first-search-round-trip.md`)의 "코드 리뷰"와 "다음", 티켓 08.
- 묶음의 첫 세션이 아니라 `tidy-checkouts`는 돌지 않았다.
- 중간에 다른 세션이 PR 12(문서만 바꾼 PR)로 사용자가 고른 `get_document` 전문 창 규칙을 명세에 쓰고, 이 티켓이 그 모양으로 구현하도록 부탁했다. PR 12가 사용자의 선택을 기록한 것을 `gh pr view`와 `gh pr diff`로 확인한 뒤 따랐다. 이 작업 트리의 `spec.md`는 아직 그 규칙을 모르는 판이고(PR 12가 먼저 병합되어야 명세와 맞는다), 코드와 독스트링의 "명세 'MCP 도구'"는 그 병합 뒤의 명세를 가리킨다. 내용 해시 출력 칸은 사용자가 정하지 않아 만들지 않았다.
- 테스트 PostgreSQL은 `docker compose -f compose.test.yml up -d --wait`로 올렸고 명령마다 `RAG_TEST_DATABASE_URL`을 내보냈다.

## 정한 것

- **리랭크는 후보 전부를 한 번에, 점수 순으로 바꾼다.** 리랭커가 실패하거나 설정이 맞지 않으면 RRF로 대신하지 않고 `search_unavailable`이다(`app/search.py`). 점수가 같으면 RRF 순서를 지킨다(안정 정렬). 리랭크 글은 `compose_index_text(location.section, text)`다. 06이 넘긴 어긋남(절 경로가 상한의 4분의 1을 넘어 줄어든 조각은 색인 때의 글과 다를 수 있다)은 닫지 않았다. 리랭크 요청이 `truncate: true`라 입력 상한을 넘는 글은 서버가 자른다. 순위에 얼마나 영향을 주는지는 재지 않았다(티켓에 적었다).
- **TEI 리랭커 어댑터**(`adapters/tei.py`): 끝점마다 첫 호출 전에 `/info`로 모델과 `max_input_length`(조각 상한 이상)를 확인하고 `auto_truncate`를 로그에 남기며, 묶음은 `RAG_TEI_BATCH_SIZE`와 `max_client_batch_size` 가운데 작은 값이고 점수는 응답의 `index`로 입력 순서에 되돌린다. 모델이나 최대 입력 길이가 어긋나면 "설정 불일치"라 일시 실패이고 검색이 `search_unavailable`로 옮긴다. 리랭커 풀의 키는 (끝점, 모델, 조각 상한)이다.
- **필터**: 그룹과 갱신일은 벡터와 키워드 두 CTE의 `WHERE`에 같이 들고, 필터가 있으면 `SET LOCAL hnsw.iterative_scan = relaxed_order`를 더한다. `relaxed_order`는 결과 순서가 엄밀하지 않을 수 있는 설정이라, 후보 안의 순서는 RRF와 리랭크가 다시 정한다. 없는 그룹 이름은 오류가 아니라 아무 문서에도 맞지 않는다. 오프셋이 없는 날짜(`2026-06-01`)는 `invalid_argument`다.
- **전체 시간 제한**은 `asyncio.timeout`이고 지식베이스 조회부터 건다(명세 100행은 "질의 임베딩부터 리랭크까지", 185행은 "전체"다. 조회 한 번만큼 더 엄격한 쪽을 골랐다). 설정은 정수 1 이상이다. 제한을 넘으면 `search_unavailable`이다. `search` 로그 이벤트는 끝난 검색에만 남고 단계별 지연(임베딩·SQL·리랭크)과 전체 지연만 싣는다. 결과가 없는 검색(없는 지식베이스, 리랭커 실패)은 `search` 이벤트를 남기지 않는다.
- **도구 오류**는 07의 방식을 그대로 쓴다(`CallToolResult(is_error=True)` 하나, 키 `type, title, status, code, request_id`). 코드는 다섯이고 상태는 404/404/422/503/500이다. `internal_error`는 시험이 `chunks` 테이블 이름을 바꿔 일으킨다.
- **토큰 범위**: 범위가 빈 토큰은 전부다. 범위 밖 지식베이스는 없는 것과 같게 보인다(`search`의 `knowledge_base_not_found`, 목록과 `chunk_counts`에서 빠짐). 문서는 지워졌거나 그 그룹이 든 지식베이스가 범위 안에 하나도 없으면 `document_not_found`다.
- **`get_document`의 전문 창**(사용자가 고른 안, PR 12): 입력 `include_text`, `offset`, `max_chars`(기본과 상한 `RAG_DOCUMENT_TEXT_MAX_CHARS`, 20000). 전문은 블록 글을 빈 줄로 이은 글이고 제목 블록은 수준만큼 `#`을 붙인다. 창은 `offset`보다 크고 `offset + max_chars` 이하인 마지막 블록 경계에서 자르고 경계가 없으면 `offset + max_chars`에서 자른다(`app/document_text.py`의 순수 함수). `text_length`는 `include_text`와 상관없이 낸다. 파싱 결과가 없거나 내용 해시가 다르면 `text_length`, `text`, `next_offset`이 모두 null이다. `max_chars`와 음수 `offset`은 문서를 찾기 전에, 길이를 넘는 `offset`은 문서를 찾고 범위를 확인한 뒤에 `invalid_argument`다. 판은 1.0.0 그대로다.
- **공백뿐인 질의도 `invalid_argument`로 본다**(명세는 "비어 있으면"). 질의 임베딩이 공백만으로 무의미한 요청이 되기 때문이다. 명세에 한 줄 더하는 것은 사용자 판단으로 남겼다.
- **문서의 제목은 파일 이름의 이름 부분**이다(수집이 정한다). 본문의 첫 제목이 아니다(`get_document` 시험이 "규정"으로 고정한다).
- **메모리 안 가짜 포트 열셋(티켓 22행)은 만들지 않았다.** 쓰는 곳이 없어, 동시성 교차를 처음 시험하는 12~14가 필요한 만큼 짓는 쪽이 낫다고 판단했다. 판 전환 재시도는 07이 실제 PostgreSQL 위에서 이미 시험했고, 리랭커·임베딩 실패와 시간 제한은 시험마다 짠 대본 가짜가 같은 파일에서 시험한다. 티켓 본문에 이유를 적었다.

## 손으로 본 것

- 같은 키를 재수집한 `unchanged` 시험이 202를 받았다. DOCX 바이트에는 만든 시각이 들어 부를 때마다 달라서다. 시험 도우미에 `ingest_bytes`를 두어 같은 바이트를 다시 넣게 했다. 응답의 칸은 `status`가 아니라 `action`이다.
- 07의 왕복 시험이 리랭크가 켜진 기본 지식베이스에서 `score > 0`을 단언하다 실패했다. 스텁의 단어 겹침 점수가 0이라서다. 그 시험만 `round_trip.drop_reranker()`로 RRF 점수를 쓰게 했다.
- 시간 제한 시험이 xdist에서 흔들렸다. 처음 몇 번의 검색은 형태소 모델을 올리느라 1초를 넘긴다. 제한 안에 끝난 검색이 나올 때까지 되풀이한 뒤에 리랭커 답을 늦춘다.
- `run_server`가 동기 함수라 비동기 시험 안에서 부를 수 없었다. 서버를 띄우는 일은 동기 픽스처(`one_second_limit`, `small_window`)가 한다.
- **로그 시험이 아무것도 단언하지 않고 10초를 기다렸다.** 명세 축 리뷰가 지적했다. `events("search", count=2)`는 모자라도 시간 제한 뒤에 그냥 돌려주고 반환값을 쓰지 않았다. 끝난 검색이 하나뿐이라 `count=1`과 길이 1의 단언으로 고쳤다.
- **변이.** 구현과 함께 쓴 시험이라 `tools/mutate.py`로 `.scratch/core/probes/search_complete_mutations.toml`의 서른셋을 돌렸다(1~17은 검색·어댑터·읽기 도구, 18~32는 `get_document`의 창과 검증, 33은 리랭커의 최대 입력 길이). 표지(`expect_output`)는 처음에 예상으로 적어 네 건이 어긋났고, 각각 변이를 손으로 한 번 적용해 실제 실패 문구를 보고 고쳤다. 모두 기대한 이유로 빨강이다. 07의 표(`first_round_trip_mutations.toml`)의 8, 9번은 `search.py`의 새 글에 맞춰 고쳤다. 경계가 창의 끝과 정확히 같은 갈래는 그 경계에서 자르든 `offset + max_chars`에서 자르든 결과가 같아 변이로 가를 수 없는 시험이라 지웠다.
- 변이가 소스를 바꾸는 동안에는 `src/`와 시험을 건드리지 않았다.

## 코드 리뷰

`/code-review`를 돌렸다. 범위는 base `1ab024d`, 수정한 파일 22개, 추적하지 않는 새 파일 13개, 커밋 0개다. 표준 축(sonnet / high)과 명세 축(세션 모델)이 따로 보았고 지적마다 근거를 코드와 명세에서 다시 열어 판정했다. 두 보고 모두 Critical·Major는 없었다. 두 축이 각자 `text_window`를 무작위 2만 건으로 기준 구현과 견줘 어긋남 0을 확인했다.

**고친 것**

- 명세 "임베딩 서버와 리랭커 어댑터"(170행)가 끝점마다 `max_input_length` 확인과 `auto_truncate` 로그를 요구하는데 리랭커 어댑터에는 둘 다 없었다. 시험을 먼저 쓰고(`test_tei_reranker.py`) 더했다. 변이 33이 그 확인의 빨강을 보인다.
- 로그 시험이 `count=2`를 기다리며 단언하지 않던 결함(위).
- 명세 248행의 시험 항목: 창 사이에 재수집하고 파싱한 뒤의 다음 창이 새 전문의 창임(`text_length`가 새 전문의 것), 글이 없는 문서의 `text_length` 0과 빈 `text`.
- `DocumentOutput.next_offset` 설명이 불완전했다(`text`가 null이거나 `include_text`가 거짓일 때도 null이고, 창 사이에 문서가 바뀌지 않았을 때만 창들이 한 전문을 이룬다). 도구 설명에 길이를 넘는 `offset`의 오류를 더했고, `read_documents.py` 독스트링에 그룹이 든 지식베이스가 아예 없는 문서의 `document_not_found`를 적었다.
- 티켓 10의 기대 문장이 "null `text`"였다. `text_length`·`text`·`next_offset` 모두 null로 고쳤다.
- 표준 축의 중복: `get_group`과 `get_group_by_id`가 `Group` 만들기를 되풀이해 `_group_where`로 합쳤고, `tei.py`의 `_parse`·`_malformed_response` 기본값 리터럴 "임베딩 서버"를 `_EMBEDDING_SERVER`로 바꿨다.

**남긴 것과 이유**

- 판단 항목이라 손대지 않았다. 회고가 다섯 번째 반복인지 센다.
  - Data Clumps(Minor): `include_text`, `offset`, `max_chars`, `max_text_chars`가 도구에서 유스케이스로 함께 간다. 도구 입력 모양이 계약이고 07의 `search`도 같은 꼴이라, 값 객체로 묶는 일은 `get_document`의 입력이 더 늘 때 다시 본다.
  - Duplicated Code: 세 도구가 `request_scope`·`run_guarded`·`authenticated_token(scope)`의 뼈대를 되풀이하고 `_result`와 `search_tool._output`이 같은 짝을 되풀이한다. `TeiEmbedderPool`과 `TeiRerankerPool`이 닮았다.
  - `_instant`의 이름(`_parse_offset_datetime` 쪽이 더 낫다), `_chunk_counts`가 지식베이스마다 쿼리하는 점(지식베이스가 몇 개 안 된다), `get_document`가 검증·가시성·조립을 한 함수에서 하는 점.
- HWPX 제목 `## `와 PDF 전문에 `#` 줄이 없음의 시험은 그 파서를 만드는 08의 몫이다(이 티켓에는 DOCX 파서뿐이다). 08 티켓이 그 시험을 수용 기준에 넣어야 한다.
- 시간 제한의 시작점(조회부터)과 공백뿐인 질의의 `invalid_argument`는 명세와 글자가 다르게 구현한 판단이라 위 "정한 것"에 적었다.
- 명세 `spec.md`는 PR 12가 병합되어야 전문 창과 `RAG_DOCUMENT_TEXT_MAX_CHARS`를 담는다. 이 세션이 끝나기 전에 PR 12가 병합되어(`a879fa4`) origin/main을 합쳤고, 합친 명세가 코드와 맞다.

**PR 직전 리뷰에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `adapters/tei.py`(`TeiReranker` 독스트링): "첫 호출 전에 `/info`로 모델과 최대 입력 길이(조각 상한 이상이어야 한다)를 확인하고(다르면 "설정 불일치"라 일시 실패) `auto_truncate`를 로그에 남기며".
- `app/read_documents.py` 모듈 독스트링: "문서는 지워졌거나 그 그룹이 든 지식베이스가 토큰 범위 안에 하나도 없으면(그룹이 든 지식베이스가 아예 없는 경우도 같다) `document_not_found`다."
- `server/tool_models.py`(`next_offset`): "전문이 `text`에서 끝나거나 `text`가 null이면 null이다. … 창 사이에 문서가 바뀌지 않았을 때만 창들이 한 전문을 이룬다".
- `tests/contract/test_tool_errors.py`의 주석: "지연을 남기는 `search` 이벤트는 끝난 검색에만 있다. 없는 지식베이스와 리랭커 실패의 검색은 결과가 없어 남기지 않는다."
- 티켓 09 머리말: "리랭크 요청이 `truncate: true`로 보내 입력 상한을 넘는 글은 서버가 오른쪽을 자르므로".

**다시 돌린 명령**

- 새 시험은 구현 전에 아직 없는 모듈과 설정 칸 때문에 빨강이었다(`document_text`, `document_text_max_chars`, `TeiReranker(max_chunk_tokens=)`). 구현 뒤 `ruff format`, `ruff check .`, `pyright` 0 오류, `lint-imports` 통과다.
- 리뷰 반영 전 트리에서 전체 `pytest` 3386개 통과(7분 51초)다. 리뷰를 반영한 트리에서 3390개 통과(7분 31초)다. 그 뒤 회고가 로그 도우미를 고쳐 `tests/server` 122개와 `tests/contract` 50개를 다시 돌렸고 모두 초록이다.
- 같은 트리에서 `ruff format --check .`, `ruff check .`, `pyright`(0 오류), `lint-imports`(계약 2 유지), `tools/check_type_escapes.py`가 통과다. 같은 검사를 커밋이 부르는 pre-commit이 한 번 더 돌렸고(테스트 3390 통과, 변이 표 검사 포함), 첫 시도는 변이 표의 표지 아홉 개가 pytest 단언 풀이 줄이라 막혀 `At index 0 diff`와 `-` 줄과 단언 위치 줄로 고친 뒤 변이 아홉을 다시 돌려 기대대로를 보았다. 둘째 시도는 커밋 메시지 제목이 72자를 넘어 막혀 줄였고, 셋째 시도가 통과했다(`ac14244`). 그 뒤 origin/main(PR 12의 명세, 하네스 chore 두 건)을 합쳐 티켓 둘의 충돌을 풀었다.
- 변이 표 서른셋은 마지막 수정(리랭커 확인 변이 33과 표지 고침) 뒤에 12~14, 28, 30~33번을 다시 돌려 기대한 빨강임을 보았다. 나머지는 해당 소스가 바뀐 뒤 처음 돌린 결과가 그대로다.

## PR 직전 리뷰

`coderabbit-review` 서브에이전트가 CodeRabbit CLI(0.7.5)로 끝까지 돌았다(`review_completed`, 종료 코드 0, 파일 39개, CLI 지적 2건). 좌석은 `Seat: not assigned`(Plan: Free)였고 리뷰는 좌석 없이도 정상 완료됐다. 에이전트가 코드를 직접 읽어 Minor 다섯을 더했다. Critical·Major는 없고 보안 축 지적은 없다. 밀어 둔 주장 다섯(리랭커 `/info` 확인, `get_document`의 `document_not_found` 조건, `next_offset` 설명, 로그 시험의 주석, 원칙 IV·V)은 모두 코드와 맞았다. 지적마다 코드에서 다시 열어 판정했다.

**고친 것**

- `search_default_top_k`가 `search_max_top_k`를 넘는 설정이 기동 때 걸러지지 않아, `top_k`를 주지 않은 모든 검색이 요청 때마다 `invalid_argument`가 되었다. 시험을 먼저 쓰고(`DID NOT RAISE`로 빨강) `Settings`에 `model_validator`를 더했다(`adapters/settings.py`, `tests/adapters/test_settings.py`).
- 시간 제한 시험의 리랭커 지연 3초, 단언 `elapsed < 3.0`이 병렬 부하에서 흔들릴 수 있었다. 지연 20초, 상한 10초로 바꿨다(`tests/contract/test_search_complete.py`). 시험이 실제로 기다리는 시간은 제한(1초)까지뿐이다.
- `filter.groups`의 설명에 빈 배열은 그룹으로 거르지 않는다는 말을 더했다(`server/tool_models.py`). 코드의 동작은 그대로다.

**남긴 것과 이유**(모두 Minor)

- 리랭커가 NaN·inf 점수를 돌려주면 `SearchResult.score` 검증에서 `internal_error`가 된다. TEI가 그런 값을 낼 가능성이 낮아 처음에는 손대지 않았다. PR의 CodeRabbit 첫 회차가 같은 지적을 내서 고쳤다(아래 "PR 봇 첫 회차").
- `filter.groups`는 이름마다 `get_group`을 순차로 부르고 이름 수의 상한이 없다. 20초 제한이 끝을 막는다. 그룹 이름이 많은 설치가 생기면 이름 목록으로 한 번에 조회하거나 상한을 둔다.
- `get_document`는 창 하나마다 블록 전체를 읽고 전문을 새로 이어 붙인다(`text_length` 때문에 `include_text` 없이도 읽는다). 큰 문서를 창으로 끝까지 읽으면 호출 수만큼 되풀이해 읽는다. 병목으로 보이면 블록 경계를 누적 합으로 찾거나 `text_length`를 저장한다.
- 리랭크 묶음마다 질의가 되풀이해 실리고 `search`에 질의 길이 상한이 없다. 매우 긴 질의는 요청 본문 상한을 넘을 수 있다. 상한을 어디에 둘지는 명세가 정할 일이다.
- 리랭커·임베딩 실패와 시간 초과로 끝난 검색은 로그가 남지 않는다(명세와 티켓은 끝난 검색의 지연만 남기라고 했다). 운영 가시성의 빈칸이라, 실패한 검색에 질의 없이 코드와 지연만 남길지는 사용자 판단이다.

**다시 돌린 명령**

- `tests/adapters/test_settings.py`와 `tests/contract/test_search_complete.py`의 관련 시험 50개 통과, `pyright` 0 오류, `ruff check`·`ruff format --check` 통과. 이 반영은 커밋의 pre-commit이 전체를 한 번 더 돌린다.

## PR 봇 첫 회차

PR 14(헤드 `909a5e4`). 검사 여섯(`CodeRabbit`, `claude-review`, `image`, `python`, `ticket`, `verify`)이 모두 통과했다. CodeRabbit은 리뷰를 달았고(`Finished`, 인라인 1건) claude-review도 코멘트를 달았다. 둘 다 이 PR의 첫 리뷰라 첫 회차이고, 첫 회차의 Minor·Nit은 지적마다 판단한다.

**고친 것**

- CodeRabbit(Minor): 리랭커가 NaN·inf 점수를 돌려주면 정렬이 순서를 보장하지 못하고 `SearchResult.score` 검증이 실패해 `search_unavailable`이 아니라 `internal_error`가 된다. 위 PR 직전 리뷰가 낸 것과 같은 건이다. 시험을 먼저 썼다(`NaN`, `Infinity`, `-Infinity` 셋이 `DID NOT RAISE`로 빨강). `_scores`가 유한하지 않은 점수를 `_malformed_response`(일시 실패)로 올리게 했다(`adapters/tei.py`, `tests/adapters/test_tei_reranker.py`).

**보류한 것과 이유**

- claude-review(Major): `get_document`의 `text`가 전문에서 창으로 뜻이 바뀌었는데 판이 `1.0.0`이다. 사실과 달라 판을 올리지 않았다. main(`origin/main`)에는 출력 모델 `DocumentOutput`만 있고 `get_document` 도구는 어디에도 등록되지 않았으므로(`git grep get_document origin/main -- src`로 확인했다) 옛 `text`의 뜻이 클라이언트에 나간 적이 없다. 이 PR이 처음 도구를 열며 이 모양이 첫 판이다. 이는 사용자가 PR 12에서 고른 결정이고 명세 "MCP 도구" 절과 PR 12의 일지가 그렇게 적는다("`get_document`가 아직 나가지 않았으므로 판은 1.0.0 그대로"). 같은 명세는 이 PR이 옛 모양으로 먼저 나가면 판을 올린다고 적었는데 이 PR은 새 모양으로 나간다. 다만 리뷰가 짚은 대로 PR 본문의 "칸을 더하기만 했고 뜻을 바꾼 것이 없습니다"는 이 사정을 말하지 않아 오해를 부르므로, 본문 "계약 영향"을 고쳤다.
- claude-review(Minor): `TeiReranker._endpoint_batch_size`와 `TeiEmbedder._endpoint_limits`·`_verify`가 `/info` 검증의 모양을 되풀이한다. 한쪽만 고치면 어긋날 수 있는 것은 맞다. 서버 이름과 오류 메시지만 다른 공통 함수로 뽑는 일은 14에서 두 풀을 함께 만질 때 하는 편이 낫다고 보아 넘긴다(코드 리뷰 절의 Duplicated Code와 같은 건이다).
- claude-review(Minor): `text_window`가 창마다 전문 전체를 새로 짓는다. 위 PR 직전 리뷰의 남긴 것과 같은 건이다.
- claude-review(Nit): `get_document`의 `include_text and blocks is not None and length is not None`에서 `length is not None`이 중복이라고 했다. `length`의 형이 `int | None`이라 이 조건이 pyright의 좁히기를 맡는다. 빼면 `offset > length`가 형 오류가 되어 둔다.

## 회고

후보 여섯, 승인 하나(이 세션에서 반영), 기각 다섯, 넘김 없음이다. 대기열 항목에 회차를 더한 것은 없고 새 항목도 없다. 만료할 항목은 `tools/queue_open_rows.py`가 로컬과 `origin/main` 양쪽에서 없다고 냈고, 같은 일을 다룬 항목은 `--search`(`LogCapture`, `tests/harness.py`, `events`)로 찾아도 없었다.

**승인**

- 시험의 로그 도우미 `LogCapture.events`가 기대한 개수에 못 미쳐도 시간이 지나면 모자란 목록을 조용히 돌려줬다. 사건: `tests/contract/test_tool_errors.py`의 `events("search", count=2)`는 끝난 검색이 하나뿐인데도 10초를 기다린 뒤 반환값을 쓰지 않고 지나갔고, 명세 축 리뷰가 잡기 전까지 초록이었다. 층: 도우미 코드가 가장 높다(타입으로 나타낼 수 없고 린터도 못 본다). 모자라면 `AssertionError`로 실패하게 했다(`lines_containing`도 같다). 되돌림: PR 하나. 고침(도구 버그)이라 사건 하나로 이 세션에서 반영했다. 시험 `tests/server/test_log_capture.py`는 구현 전에 `DID NOT RAISE`로 빨강이었다. `tests/server` 122개가 초록이다. 티켓 09에 `회고 반영` 줄을 더했다.

**기각**

- 변이 표의 표지를 예상으로 적어 네 건이 어긋난 일: `tools/mutate.py`가 어긋남을 알려 주었고 변이를 손으로 한 번 적용해 고쳤다. 도구가 제 몫을 했다.
- 경계가 창의 끝과 정확히 같은 갈래의 시험이 어떤 변경으로도 빨개질 수 없던 일: 변이를 설계하며 이 세션이 스스로 찾아 지웠고, 사건 하나이며 검사로 옮길 수 있는 꼴이 아니다(변이 표가 가르는 것은 이미 `tools/mutate.py`가 한다).
- 큰 heredoc, 파이프 뒤 `$?` 판정, 주 체크아웃 경로로 Edit한 것: 이미 있는 훅과 가드가 그 자리에서 막았다.
- 시험에 `# type: ignore[arg-type]`을 쓴 것: 검사(`tools/check_type_escapes.py`)가 막는 자리이고 검사 전에 스스로 걷었다.
- 티켓 13행이 명세 170행의 일부(`max_input_length`, `auto_truncate`)를 줄여 적어 구현에서 빠진 일: `code-review`의 명세 축이 잡도록 둔 기준이고 그 축이 잡았다. 리뷰가 제 몫을 한 것이라 회차로 세지 않는다.
- 열린 항목 `review-report-journal-lag`와 겹치는지도 보았다. 두 리뷰의 보고를 받은 같은 턴에 지적별 판정을 일지로 옮겼고 컨텍스트 압축이 끼지 않아 회차를 더하지 않았다.

## 다음

- core의 프론티어는 08(PDF·HWPX 파서와 격리·자원 한도)과 10(수집 갱신과 그룹 변경·재큐), 이 PR 뒤에 열리는 것은 11~15다.
- 08이 받는 것: PDF 파서는 제목 블록을 내지 않아 전문에 `#` 줄이 없고 HWPX 제목은 `## ` 같은 표시가 붙는다. 그 시험을 08의 수용 기준에 넣는다.
- 10이 받는 것: 내용과 그룹을 바꾼 직후 파싱 전의 `get_document`는 `text_length`·`text`·`next_offset`이 모두 null이다(티켓 문장을 고쳤다).
- 11이 받는 것: 지운 문서의 `get_document`와 `list_knowledge_bases`의 `document_count`(09가 지은 갈래).
- 열린 일:
  - 리랭크 글과 색인 때 글의 절 경로 어긋남. 순위에 미치는 영향을 재고 필요하면 `index_text`를 저장하는 것은 14와 함께 판단한다.
  - 명세의 보강 한 줄(공백뿐인 질의, 시간 제한의 시작점)은 사용자 판단이다.
  - `get_document`의 내용 해시 출력 칸은 사용자가 아직 정하지 않았다.
  - PR 직전 리뷰가 남긴 Minor 넷(위 "PR 직전 리뷰"의 남긴 것. NaN 점수는 PR 봇 첫 회차에서 고쳤다). 실패한 검색의 로그(질의 없이 코드와 지연)와 질의 길이 상한은 명세에 닿아 사용자 판단이고, 나머지(그룹 이름 일괄 조회, 창 읽기의 반복 비용)는 쓰임이 늘 때 다시 본다.
  - 리랭커와 임베더의 `/info` 검증 중복(claude-review Minor)은 14가 두 풀을 함께 만질 때 공통 함수로 뽑는다.
  - 병합 뒤 `parsers-isolation` 워크트리(08)가 `tests/support/pipeline.py`를 고치고 있어, 08이 origin/main을 합칠 때 이 PR의 같은 파일 변경과 글자 충돌이 날 수 있다.
  - 05에서 넘어온 것(확장자와 내용 불일치 판정, 키 길이 상한, `.env.example`, `request_failed` 이벤트, 토큰 목록의 회수 칸)은 여전히 사용자가 정할 것이다.
