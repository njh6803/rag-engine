# core 07 첫 왕복 일지 · 2026-11-11

티켓 `.scratch/core/issues/07-first-search-round-trip.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/07-first-search-round-trip`, 작업은 워크트리 `first-search-round-trip`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다. 구현 도중 컨텍스트가 한 번 압축되었다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 명세(`.scratch/core/spec.md`)의 수집 파이프라인과 작업·검색 흐름·MCP 도구·데이터 모델 절, 직전 일지(`2026-11-11-0314-core-05-ingest-api.md`)의 "다음".
- 지시문대로 `tidy-checkouts`를 먼저 돌고 워크트리에 들어가 브랜치를 땄다. 05가 남긴 원격 브랜치 `feature/05-ingest-api`는 건드리지 않았다. 확장자와 내용이 어긋날 때의 판정은 사용자 판단이라 07에서 고치지 않았다.
- 의존성을 하나 더했다(`python-docx>=1.2,<2`). `docs/constitution/tech.md`의 스택 표와 맞는지 확인했다.
- 테스트 PostgreSQL은 `docker compose -f compose.test.yml up -d --wait`로 올렸고 명령마다 `RAG_TEST_DATABASE_URL`을 내보냈다.

## 정한 것

- **파서는 자식 프로세스가 돌고, 원본은 경로가 아니라 바이트로 넘긴다.** 부모가 `BlobStore.read`로 읽은 바이트를 자식 프로세스의 spawn 인자(피클)로 주므로 자식은 파일 시스템을 열 일이 없다(`adapters/parsers/runner.py`). 티켓 문구는 "파서 이름, 원본 경로, 한도를 넘긴다"이나, 명세 "파서 인터페이스"가 파서는 바이트를 받는다고 해서 경로 대신 바이트를 넘겼고 파서는 이름 대신 대상(`모듈:클래스`)으로 부른다. 큰 원본(100MB까지)을 피클로 복사하는 비용은 재지 않았다. 파서는 entry point 그룹 `rag_engine.parsers`에서 찾고(`registry.py`), DOCX 파서가 첫 사용자다. 파서의 판은 새 값 객체 `ParserVersion`과 `ParseRunner.current_version(mime)`으로 노출해, 저장된 파싱 결과의 재사용 여부(`_is_reusable`)를 내용 해시와 파서 판 둘이 가른다.
- **`index_document`는 명세의 네 단계를 그대로 따른다**(`app/index_document.py`). 첫째 단계가 문서 행을 잠그고 세대를 올리고, 둘째가 파싱 결과를 저장하며, 셋째가 판마다 청킹·임베딩·키워드를 만든 뒤 문서 행을 다시 잠가 세대를 대조하고 옛 조각을 새 조각으로 바꾼다. 세대가 달라졌으면 문서에 아무것도 쓰지 않고 성공으로 끝낸다. 작업의 상태는 그 작업이 끝난 모양이지 문서의 색인 결과가 아니기 때문이다.
- **작업 행 조건은 `JobQueue.hold_attempt`가 판정한다.** 작업 행을 잠그고 작업자 ID와 시도 횟수가 꺼낼 때 값과 같은지 보며, 아니면 `AttemptLostError`(오류 코드 없는 시도 중단 신호)를 올려 작업 단위를 롤백한다. 세 쓰기 단위가 모두 부른다. `process_job`은 그 예외를 받으면 작업 행을 끝내지 않고 로그에 `result: lost`만 남긴다.
- **잠금 순서를 07은 지키지 못한다.** 명세의 순서는 문서 행, 지식베이스 행, 작업 행인데 07의 셋째 단계는 지식베이스 행을 아예 잠그지 않는다. 판 전환 검사(14)가 `_check_version_switch`에서 지식베이스 행을 잠그면 문서, 작업, 지식베이스 순이 되어 순서가 어긋난다. 그래서 14 티켓에 지식베이스 행 잠금을 `_hold` 앞으로 올리라고 적었다.
- **`index_text`는 `chunks`에 저장하지 않는다**(칼럼이 없다). 임베딩과 키워드는 색인 때 청커가 지은 글을 그대로 쓴다. 14의 키워드 재생성과 09의 리랭크는 `compose_index_text(location.section, text)`로 되짓되, 절 경로가 상한의 4분의 1을 넘어 줄어든 조각은 다를 수 있다. 두 티켓에 적었다.
- **검색 SQL은 판의 UUID와 차원을 문장에 리터럴로 적는다**(`search_sql`). 판마다 부분 HNSW 색인(`embedding::vector(D)`)이 있어, 판 ID를 매개변수로 보내면 일반 계획이 부분 색인을 쓰지 못한다. UUID와 정수는 서버가 만든 값이라 주입 위험이 없다. 질의 벡터와 후보 수, 키워드는 매개변수로 남긴다. `explain_search_generic`으로 일반 계획에서도 색인 스캔을 고르는 것을 어댑터 시험으로 고정했다. 명세 "검색 흐름"에 이 결정을 적었다.
- **`search`는 같은 SQL에서 판이 아직 현재인지 읽고, 아니면 둘째 단계부터 한 번 다시 한다**(`app/search.py`). 다시 해도 아니면 `search_unavailable`이다. 임베딩 서버 실패도 `search_unavailable`로 번역하고 서버의 메시지는 옮기지 않는다. 빈 질의와 `top_k` 범위 검증, 필터, 리랭크, 전체 시간 제한은 09의 몫이다.
- **도구 오류는 예외가 아니라 `CallToolResult(is_error=True, content=[Problem Details JSON])`로 직접 낸다**(`server/search_tool.py`). MCP SDK가 도구 예외의 메시지에 `Error executing tool …` 접두를 붙여 JSON이 깨지기 때문이다. 반환 타입은 `Annotated[CallToolResult, SearchOutput]`이라 outputSchema는 그대로 공개되고, 직접 만든 `CallToolResult`는 SDK가 그대로 통과시킨다. `detail`에는 아무것도 싣지 않는다(원칙 V).
- **Kiwi는 작업자 조립 때 `tokenize_keywords("준비")`로 예열하고, 서버는 lifespan의 백그라운드 스레드로 예열한다**(기동을 막지 않는다. 예열이 실패하면 `kiwi_warmup_failed`를 ERROR로 남기고 서버는 뜬다. 적재 실패는 `@cache`가 저장하지 않으므로 첫 검색이 적재를 다시 시도한다). `kiwipiepy`의 스레드 안전성을 확인하지 못해 어댑터가 호출을 잠금 하나로 직렬화한다(`adapters/kiwi.py`의 `_LOCK`). 예열 스레드와 첫 검색이 같은 인스턴스를 동시에 쓰지 않게 하려는 것이다. 검색은 질의 토큰화를 스레드로 넘겨 임베딩과 함께 진행하고(명세의 "둘은 병렬"), 색인 때의 청킹과 키워드 호출은 스레드로 넘기지 않고 이벤트 루프 안에서 그대로 부른다. 큰 문서가 임대 연장을 막을 수 있는 문제는 13이 본다(13 티켓에 적었다).
- **실패 처리는 단순하게 했다.** `RagEngineError`가 올라오면 그 코드로, 그 밖의 예외는 `job_crashed` 로그와 `internal_error`로 작업을 `failed`로 끝낸다. 파싱의 영구 실패 종결은 08, 재시도·소진·오류 번역은 12, 임대 연장·인수는 13, 판 전환 검사는 14가 채운다. 각 티켓에 07이 넘기는 것을 적었다.
- **로그.** `job_started`와 `job_finished`가 작업 ID, 종류, 문서 ID, 시도 횟수, 결과, 오류 코드, 파싱·임베딩·쓰기 지연을 싣는다. 요청 ID는 수집 요청의 것이 작업 행을 거쳐 이어진다. 문서의 키와 제목은 싣지 않는다. `search` 이벤트는 임베딩·SQL·전체 지연만 싣는다.

## 손으로 본 것

- **일반 계획 시험이 바인드 이름을 못 찾았다.** `explain_search`가 `:name` 바인드를 `$n`으로 바꾸는 정규식 끝에 백스페이스 문자(`\x08`)가 저장되어 있었다(`\b`가 이스케이프로 해석되어 들어갔다). 디버그 출력으로 치환 뒤 `$` 개수가 0인 것을 보고 찾았고 `rf` 문자열로 바꿔 `\b`가 정규식의 낱말 경계가 되게 고쳤다.
- **전체 시험 3254개 통과**(10분 48초). 그 뒤에 `process_job`, `search_documents` 시험을 더했다.
- **변이.** 구현과 함께 쓴 시험이라 `tools/mutate.py`의 표 둘로 변이 스물일곱을 돌렸다. 앱과 서버 층 열둘은 `.scratch/core/probes/first_round_trip_mutations.toml`, 어댑터 열다섯(작업 꺼내기와 작업 행 조건, DOCX 파서, 파싱 실행기, 조각 쓰기와 검색 SQL)은 `first_round_trip_adapter_mutations.toml`이다. 첫 실행에서 앱 층 둘과 어댑터 층 넷, 모두 여섯이 초록으로 살아남아 시험을 보강했고 스물일곱 모두 기대한 표지와 함께 빨강이다.
  - 어댑터 층의 생존 넷: 작업 행 조건(`hold_attempt`)이 작업자와 시도 횟수를 보는지 어댑터 시험이 없었고(앱 시험이 간접으로만 잡았다), `delete_chunks`의 판 지정과 `ef_search` 값을 보는 시험이 없었으며, 신호로 죽은 자식을 메모리 초과로 보는 갈래도 비어 있었다. 앞의 셋은 시험을 더해 잡았다. 마지막은 `CrashingParser` 시험을 더했으나 리눅스에서만 빨개지는 갈래(윈도의 종료 코드는 양수라 `parse_failed`로 보인다)라 이 PC에서는 변이로 재지 못했다. 변이는 표에서 뺐고 CI의 리눅스 실행이 시험이 초록임을 보인다. 시험이 이 PC에서 빨개지는지는 확인하지 못했다.
  - 7번(조각의 갱신일을 문서에서 복사하지 않는다): 시험의 수집이 갱신일을 주지 않아 문서의 갱신일과 지금 시각이 같았다. `Pipeline.ingest`에 `updated_at`을 받게 하고 30일 전 값으로 단언했다.
  - 11번(임대를 잃은 시도를 실패로 끝낸다): 끝내기가 작업 행 조건에 막혀 DB에는 차이가 없고 로그의 `result`만 달라서 시험이 보지 못했다. 로그의 `lost`를 단언했다. 이 시험은 먼저 `LogCapture`(stdout)를 썼다가 앱 시험에는 로그 핸들러가 없어 실패했고, 05의 시험처럼 `caplog`와 `JsonLinesFormatter`로 바꿨다.
- 표지 고르기에서 두 번 돌아갔다. 단언에 메시지를 달아 표지로 삼으니 도구가 시험 원문에 글자 그대로 든 표지라며 거절했다(표지의 메아리). 그래서 값 하나를 비교하던 단언을 목록 비교로 바꿔 실패하면 `At index 0 diff` 줄이 찍히게 하고 그 줄을 표지로 삼았다.
- 줄 끝. `vector_index.py`, `search_tool.py`, 시험 도우미 몇 개가 작업 트리에서 CRLF였다(색인과 `.gitattributes`는 LF). 여러 줄 원문의 변이 표가 그 파일을 못 읽어 `--check`가 알려 주었고, 모두 LF로 되돌린 뒤 `git ls-files --eol`로 CRLF 0개를 확인했다. 어느 도구가 CRLF로 썼는지는 가리지 못했다.
- 시험이 잡은 실수. (1) 앱 시험에서 로그를 `capsys`로 읽으려다 빈 출력을 받았다(위). (2) `RoundTrip.add_knowledge_base`를 쓰고도 정의하지 않았다.

## 코드 리뷰

`/code-review`를 돌렸다. 범위는 base `e9b4259`, 수정한 파일 19개, 추적하지 않는 새 파일 27개, 커밋 0개다. 표준 축(sonnet / high)과 명세 축(세션 모델)이 따로 보았다. 두 서브에이전트는 아직 커밋이 없는 작업 트리를 읽었고 근거는 내가 코드에서 다시 열어 확인했다.

**고친 것**

- 표준 Major: 서버 lifespan의 `finally`가 `await warmup`을 먼저 해서 Kiwi 적재가 실패하면 `embedders.aclose()`와 `engine.dispose()`를 건너뛰었다. `_warm_up_kiwi`가 실패를 `kiwi_warmup_failed` 로그로만 남기게 했다(`tests/server/test_warmup.py`).
- 표준 Major(검증 못 함으로 보고됨): `RAG_SEARCH_CANDIDATES`가 `hnsw.ef_search`에 그대로 들어가는데 상한이 없었다. 테스트 PostgreSQL(pgvector 0.8.7)에서 재니 `hnsw.ef_search`는 1부터 1000까지만 받는다. 확장을 로드하기 전에는 `hnsw.` 변수가 자리표시자라 1001도 받으므로, 벡터 연산 뒤에 쟀다. 근거는 커밋한 프로브 `.scratch/core/probes/vector-store/probe_ef_search_range.py`와 그 출력이다(README 표에 한 줄). 설정에 `le=1000`을 걸었다(`tests/adapters/test_settings.py`).
- 명세 3번과 표준: 서버 예열 스레드와 첫 검색이 같은 Kiwi 인스턴스를 동시에 쓸 수 있었다. 어댑터가 호출을 잠금으로 직렬화한다(`tests/adapters/test_kiwi.py`).
- 명세 6번: 명세 "검색 흐름"의 셋째 단계가 "둘은 병렬"인데 순차였다. 질의 토큰화를 스레드로 넘겨 임베딩과 `asyncio.gather`로 함께 진행한다. 서로 기다리는 두 이벤트로 순차이면 시간 초과로 빨개지게 시험했다(`tests/app/test_search_documents.py`).
- 명세 5번: 작업자 조립이 `configure_logging`을 부르지 않아 작업자 단독 실행에서 `job_started`와 `job_finished`가 JSON으로 나오지 않았다. 계약 시험은 같은 프로세스의 `create_app`이 로깅을 설정해 주어 이 빈틈을 가렸다. 조립이 설정한다(`tests/app/test_worker_assembly.py`).
- 표준 Minor: `explain_search(query, *, generic_plan=False)`가 CODING_STANDARDS의 불리언 플래그 항목에 걸려 `explain_search`와 `explain_search_generic` 둘로 쪼갰다. 같은 지적에서 시험 이름이 준비된 문장의 계획을 본다고 하면서 새 `EXPLAIN`만 보던 것을 하는 일 그대로의 이름과 본문으로 줄였다.
- 문서의 거짓 주장: 일지와 08 티켓의 "표준 입력"(실제는 spawn 인자), 08 티켓의 "major 거부를 레지스트리에 더한다"(이미 `_register`와 `test_parse_runner.py`가 한다), `vector_index.py` 독스트링의 "`delete_chunks`는 아직 없다", 일지의 "`chr()`로 고쳤다", `docx_parser.py` 독스트링의 "합쳐진 칸은 한 번만"(가로만 맞고 세로는 행마다 되풀이), `search_tool.py` 독스트링의 "예외를 올리지 않고", `processing.py` 독스트링의 이벤트 수(`job_crashed`가 있다), `job_queue._attempt_of`의 "완성은 13"(지식베이스 행 잠금은 14), 티켓 07 "03이 넘긴 것"의 `delete_chunks`, 티켓 09의 "둘째 항목", `runner.py` 독스트링의 "파서 이름", 명세의 `explain_search(generic_plan=True)`. 모두 코드에서 확인해 고쳤다.

**PR 직전 리뷰에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `adapters/settings.py`: "pgvector의 `hnsw.ef_search`는 1부터 1000까지만 받고, 검색이 이 값을 그대로 그 설정에 넣는다."
- `adapters/kiwi.py`: "kiwipiepy의 스레드 안전성을 확인하지 못했다. … 호출을 한 번에 하나로 직렬화한다. `_kiwi()`의 지연 적재가 두 번 일어나는 일도 막는다."
- `adapters/parsers/docx_parser.py`: "가로로 합쳐진 칸은 한 번만 적고, 세로로 합쳐진 칸은 행마다 같은 글을 적는다." `세로합침 | a`, `세로합침 | b`로 되풀이되는 출력을 재현했다.
- `app/search.py`: "임베딩은 서버를 기다리고 토큰화는 CPU를 쓰므로 함께 진행한다. 토큰화는 스레드로 넘긴다."
- 13 티켓: "`finish`는 작업 행 조건에 막혀 0행이 갱신되어도 알리지 않아서 … `process_job`이 `job_finished`의 `result`를 `succeeded`로 남긴다."

**남긴 것과 이유**

- 판단 항목이고 티켓의 수용 기준 밖이라 손대지 않았다. 회고가 다섯 번째 반복인지 센다.
  - Data Clumps: `parser_name`·`interface_version`·`library_version`이 `ParsedDocument`·`ParserVersion`·`DocumentContent`에 있고 `runner`가 같은 조립을 두 번 한다. `_Prepared`의 병렬 리스트 `drafts`·`embeddings`·`keyword_texts`.
  - Duplicated Code: `_MS_PER_SECOND` 네 곳, `TeiEmbedderPool`의 httpx 람다(`server/app.py`와 `worker/assembly.py`), Block 필드 열거 세 곳, 시험 도우미 `docx_bytes`와 `serve_stub`의 중복.
  - CQS와 출력 인자: `hold_attempt`가 행을 잠그며 bool을 돌려준다(잠그고 확인하는 일이 한 문장이라 쪼개면 틈이 생긴다). `_ensure_parsed`가 `_Timer`를 바꾼다.
  - Middle Man `runner._fail`, 추상화 수준이 섞인 `_replace_chunks`, 시험 전용 `explain_search`와 `_sql_literal`이 어댑터에 있다.
  - Speculative Generality(Nit): 빈 `_check_version_switch`와 항상 `SUCCEEDED`인 `IndexResult.outcome`은 14 티켓이 채울 자리다.
- 시험이 약한 곳. 직접 시험이 없는 `TeiEmbedderPool`(06의 것), 도구의 `search_failed`에서 `internal_error`로 가는 갈래(09가 "도구 오류 코드마다 한 사례"를 시험한다), DOCX 세로 병합(독스트링을 사실대로 고쳤다). `test_메모리_한도…`가 구현의 분기를 복제하고, `ef_search` 시험이 `repr(parameters)` 문자열에 묶여 있다.
- 티켓 문구와 다르게 구현한 것: 자식에게 경로가 아니라 바이트를 넘긴다(위 "정한 것"). 명세 "파서 인터페이스"가 바이트를 받는다고 해서 그 쪽을 따랐다.
- `finish`의 0행 로그는 13 티켓에 넘겼다(위).

**다시 돌린 명령**

- 새 시험 다섯은 구현 전에 기대한 이유로 빨강이었다(`2 == 1`, `DID NOT RAISE`, `assert False`, 빈 로그, 빈 핸들러). 구현 뒤 변경한 시험 묶음 136개(어댑터 Kiwi·설정·조각, 앱, 계약, 서버 예열)가 초록이다.
- 반영을 마친 트리에서 전체 `pytest` 3272개 통과(10분 17초), `ruff check .` 통과, `pyright` 0 오류, `lint-imports` 통과, `tools/check_type_escapes.py` 통과다. 같은 검사를 커밋이 부르는 pre-commit이 한 번 더 돌린다(결과는 커밋 뒤에 적는다).

### PR 직전 리뷰(CodeRabbit CLI)

`coderabbit-review` 에이전트가 CodeRabbit CLI로 작업 트리를 보았고, 지적마다 코드에서 근거를 다시 열어 판정했다.

**고친 것**

- 보안(Major): 부모가 자식의 `Connection.recv()` 결과를 받았는데 `recv()`는 pickle을 푼다. 침해된 자식(파서가 신뢰할 수 없는 문서를 읽는 프로세스다)이 객체를 `__reduce__`로 심으면 부모에서 코드가 돈다. 자식이 pydantic 모델(`ChildMessage`)을 JSON 바이트로 보내고 부모는 `recv_bytes()`와 스키마 검증만 한다. 검증에 실패하면 `parse_failed`다. 시간 초과 뒤에는 `terminate()`에 이어 `kill()`까지 한다. `HijackingParser` 시험이 옛 코드에서 실제로 부모의 코드 실행을 재현해 빨강이었고, 윈도의 `PipeConnection`이 `Connection`의 하위 클래스가 아니라는 점 때문에 처음 시험은 0개를 검사해 헛초록이었다(모듈 이름으로 판정하도록 고쳤다).
- 버그(Major): `replace_chunks`가 문서의 조각을 한 `INSERT`로 넣어 큰 문서에서 바인드 인자 한도(문장당 65535)를 넘는다. 조각당 열이 14개라 4680조각 언저리에서 터진다. 1000조각 묶음으로 나눈다(`test_조각이_한_문장_한도를_넘어도…`, 5000조각).
- 표준: 서버 lifespan에서 종료가 취소로 올 때 `await warmup`이 끊기면 `aclose`와 `dispose`를 건너뛰었다. 정리를 안쪽 `finally`에 둔다.
- 표준: `asyncio.gather`의 한쪽이 실패해도 다른 쪽이 끝까지 돈다는 점을 주석에 적었다.
- 시험: DOCX 세로 병합 시험이 없었다. 더했다(`test_docx_parser.py`).
- 근거 문장: `ef_search` 범위의 "쟀다"가 커밋한 프로브를 가리키지 않았다. `probe_ef_search_range.py`와 출력을 커밋하고 README 표에 한 줄 더했다. 프로브는 확장 로드 전에 1001을 받고, 로드 뒤에 0과 1001을 거부하는 것을 보였다.

**PR 직전 리뷰에 밀 주장**

- `adapters/parsers/runner.py`: 자식은 JSON 바이트만 보내고 부모는 `recv_bytes()`와 `ChildMessage.model_validate_json`만 쓴다. pickle을 풀지 않는다. 시간 초과 뒤에는 `terminate()`, 그래도 살아 있으면 `kill()`이다.
- `adapters/postgres/vector_index.py`: 조각당 바인드 인자가 14개라 1000조각 묶음이 14000개이고 문장당 한도 65535 안이다.
- `server/app.py`: 예열 실패는 로그만 남기고, 종료 때 `aclose`와 `dispose`는 예열이 취소되거나 실패해도 돈다. 적재가 실패하면 결과를 캐시하지 않아 첫 검색이 다시 시도한다.

**푸시 뒤 보안 검토**(security-guidance 플러그인, 커밋 `62812c6` 푸시 뒤)

- `adapters/parsers/runner.py` MEDIUM 하나, 세 갈래였다. 코드에서 모두 사실임을 확인했다.
  - 알 수 없는 `error`·`kind` 값이 오면 `ErrorCode(...)`·`BlockKind(...)`가 `ValueError`를 올려 작업자까지 번진다. **고쳤다.** `ChildMessage`의 필드를 enum 타입으로 바꿔 스키마 검증이 `parse_failed`로 거르게 했고(`decode_child_message`를 공개해 시험이 직접 부른다), 시험(`test_자식이_모르는_오류_코드나_블록_종류를_보내면_parse_failed다`)은 구현 전에 `'not_a_code' is <ErrorCode.PARSE_FAILED>`로 빨강이었다. 변이 18을 표에 더했다.
  - 받는 바이트 수에 상한이 없다. 앞서 남긴 08의 몫과 같은 갈래다. 08 티켓에 `recv_bytes(maxlength=)`로 적었다.
  - `receiver.poll(타임아웃)`이 첫 바이트까지만 기다려, 보내다 멈춘 자식이 `recv_bytes()`를 무기한 막는다. 이 갈래는 새로 알았다. 시간 제한이 수신 전체를 덮게 하는 일(감시 타이머와 절반만 보내는 파서 시험)은 08의 실행기 한도 작업이라 08 티켓에 적었다. 07은 자식이 신뢰할 수 없는 문서를 읽는 길을 처음 열지만 PDF·HWPX 파서가 없어 DOCX 파서를 침해해야만 닿는다.

**남긴 것과 이유**

- 압축 폭탄 한도(`parse_max_unzipped_mb` 등) 설정이 아직 파서에서 쓰이지 않는다. 08이 파서 격리와 함께 채운다.
- 자식 메시지의 받는 크기 상한이 없다. 윈도에는 자식의 메모리 한도가 없어 큰 메시지를 막을 수단이 마땅치 않다. 08이 격리와 함께 정한다(08 티켓에 적었다).
- 검색 SQL이 삭제된 문서의 조각을 거르지 않는다. `src/`에 문서를 지우는 유스케이스가 아직 없어(`deleted_at`을 쓰는 곳은 수집 갱신뿐이다) 지금은 걸릴 일이 없다. 11 티켓이 삭제 커밋에서 조각을 `archived_chunks`로 옮기므로(수용 기준 "삭제의 작업 단위"), 검색 SQL이 따로 거르지 않아도 지운 문서는 검색에서 빠진다. 그 티켓의 시험이 이를 지킨다. PR 본문에 알린다.
- `top_k` 검증은 09, `finish`의 0행 로그는 13이다.

**다시 돌린 명령**

- 새 시험 둘(pickle 가로채기, 5000조각 묶음)은 구현 전에 빨강이었다. 변이 표(`first_round_trip_adapter_mutations.toml`)에 둘을 더해(묶음을 나누지 않는다: `number of parameters must be between 0 and 65535`, 스키마 검증 실패를 `parse_failed`로 보지 않는다: `Invalid JSON: expected value`) 기대한 이유로 빨강임을 보았다. 시간 초과 뒤 `kill()` 갈래는 SIGTERM을 무시하는 자식을 만드는 시험이 없어 변이로 재지 못했다. 구현 뒤 `ruff format`, `ruff check .`, `pyright`, `lint-imports`, `check_type_escapes.py`가 통과이고, 고친 시험 파일 네 개의 33개가 초록이다. 전체 `pytest`는 3275개 통과(10분 14초)다. 같은 검사를 커밋이 부르는 pre-commit이 한 번 더 돌렸고(커밋 `ae024ab`) 통과했다. 인용 대조는 이 일지가 고친 거짓 주장의 옛 원문을 따옴표로 옮긴 두 줄(50행)에 경고를 냈고, 막는 검사가 아니라 그대로 두었다.

## 회고

후보 여덟, 승인 둘(둘 다 기존 항목의 회차만 더한다), 기각 여섯, 넘김 없음이다. 새 항목도, 이 세션에서 반영한 것도 없다. 만료할 항목은 `tools/queue_open_rows.py`가 없다고 냈다.

**승인(회차 더하기)**

- 스크립트가 쓴 저장소 파일의 CRLF. 사건: 작업 트리의 `vector_index.py`, `search_tool.py`, `tei.py`와 시험 도우미 몇이 CRLF였고, 손으로 치는 줄 끝 검사가 아니라 변이 표의 `--check`가 못 읽는다고 알려 주어서야 알았다(위 "손으로 본 것"의 줄 끝). 어느 도구가 썼는지는 가리지 못했다. 층: 검사가 가장 높은 층이고 열린 항목 `crlf-from-script-edits`가 이미 그 처방을 든다. 되돌림: PR 하나. `crlf-from-script-edits`에 2회차를 더했다(더하는 것이라 다섯 번째에 반영한다).
- 어댑터 시험이 준비된 문장의 일반 계획을 밟지 못하는 공백. 사건: 07이 쓴 시험 `test_벡터_질의는_준비된_문장이_된_뒤에도…`가 같은 질의를 여덟 번 돌린 뒤 새 `EXPLAIN`을 보았을 뿐이라 준비된 문장의 계획을 보지 못했고, 표준 축 리뷰가 잡았다. 어댑터 시험의 연결이 기본 `plan_cache_mode`로 열리는 같은 뿌리다. `adapter-tests-generic-plan`에 2회차를 더했다. 07은 일반 계획을 강제하는 시험(`explain_search_generic`)을 따로 두어 이 질의만 막았고, 시험 연결 전체를 일반 계획으로 여는 처방은 그 항목의 몫으로 남는다.

**기각**

- 변이 표가 잡은 약한 시험 여섯(작업 행 조건, `delete_chunks`, `ef_search` 등): `tools/mutate.py`가 제 몫을 했다.
- 문서의 거짓 주장(표준 입력, `chr()`, `delete_chunks` 독스트링, 08 티켓의 major 거부): `code-review`의 주장 검증 목록이 잡았다. 리뷰가 잡도록 둔 기준이라 회차에서 뺀다.
- 명세의 "둘은 병렬"과 불리언 플래그 인자: 명세 축과 `CODING_STANDARDS.md`가 잡도록 둔 기준을 리뷰가 잡았다.
- 작업자 조립이 `configure_logging`을 부르지 않은 것: 계약 시험이 서버 프로세스 안에서 돌아 가려졌으나 시험과 코드로 이 세션에서 고쳤고, 같은 꼴이 다시 난 적이 없다.
- heredoc 40줄 상한과 한글 `-k` 인자 거부: 훅과 가드가 그 자리에서 막았다.
- 전체 `pytest` 10분 실행을 반영마다 되풀이한 비용: 이미 알려진 비용이고 처방이 될 새 사건이 없다.

## 다음

- core의 프론티어는 08(PDF·HWPX 파서와 격리·자원 한도), 09(검색의 완성), 10(수집 갱신과 그룹 변경·재큐)이다. 08·09·10은 07이 병합되면 열린다.
- 07이 각 티켓에 넘긴 것은 해당 티켓 본문의 "07이 넘긴 것" 단락에 있다(08, 09, 12, 13, 14).
- 열린 일:
  - 잠금 순서: 07의 셋째 단계가 지식베이스 행을 잠그지 않아 14가 순서를 맞춰야 한다.
  - 청킹과 키워드는 이벤트 루프 안에서 도는 동기 호출이다. 큰 문서에서 얼마나 막는지 재지 않았다(13이 동시 처리를 넣을 때 잰다).
  - `finish`가 작업 행 조건에 막혀 0행이 갱신되어도 알리지 않아 `job_finished`가 `succeeded`로 남을 수 있다(13).
  - 파서에 원본을 바이트로 넘기는 피클 복사 비용을 재지 않았다(08이 자원 한도를 볼 때).
  - `index_text`를 저장하지 않으므로 키워드 재생성과 리랭크 글이 색인 때의 글과 다를 수 있다(14, 09).
  - 05에서 넘어온 것: 확장자와 내용 불일치 판정, 키 길이 상한, `.env.example`, `request_failed` 이벤트, 토큰 목록의 회수 칸은 여전히 사용자가 정할 것이다.
