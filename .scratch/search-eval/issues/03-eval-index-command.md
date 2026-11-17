# 03: `index`와 `validate --indexed`: 평가 전용 데이터베이스에 묶음을 색인한다

**What to build:** 개발자가 `compose.eval.yml`로 PostgreSQL과 임베딩 TEI를 띄우고 `index <묶음 폴더>`를 치면, 도구가 제품과 같은 길(`migrate`와 같은 코드, 수집 유스케이스, 작업자의 한 번 돌기 입구)로 묶음의 문서를 평가 전용 데이터베이스에 색인한다(스토리 1). `validate --indexed`는 묶음의 모든 문서가 색인되었고 글귀가 그 본문에 있는지 본다. 평가용이 아닌 데이터베이스와 다른 묶음의 문서가 든 데이터베이스에는 아무것도 쓰지 않는다(명세 "자리와 층"의 `index` 항목과 평가 전용 데이터베이스 항목).

**Blocked by:** 02 (묶음 형식과 `validate`)

**Status:** done

- [x] 환경은 평가 전용 이름 넷(`RAG_EVAL_DATABASE_URL`, `RAG_EVAL_DATA_DIR`, `RAG_EVAL_EMBEDDING_URL`, 없어도 되는 `RAG_EVAL_RERANKER_URL`)만 받는다. 앞의 셋 가운데 빠진 것이 있으면 빠진 이름을 알리고 값은 찍지 않는다. 제품의 설정 객체는 환경 변수와 작업 폴더의 `.env`를 읽지 않게 지어, `config.json`과 그 넷에서 오지 않은 칸은 코드의 기본값이 된다.
- [x] 데이터베이스의 이름이 `rag_eval`로 시작하지 않거나 주소에서 이름을 읽을 수 없으면 접속하지 않고 종료 코드 1과 이름의 규칙을 낸다(주소는 찍지 않는다).
- [x] 스키마를 올리기 전에 차례로 본다. 문서 파일의 판정 셋(경로, 목록의 모든 파일이 있고 해시가 맞는지, 목록에 없는 파일이 없는지), 데이터베이스가 이 묶음의 것인지(든 문서의 키가 문서 목록에 있고 내용 해시가 그 키의 `sha256`과 글자 그대로 같은지), 스키마의 판(스키마가 없는 빈 데이터베이스는 지나가고 이 체크아웃이 올릴 판과 다르면 거부), 기본 지식베이스가 이미 있으면 그 현재 판의 요소가 `config.json`과 같은지다. 하나라도 어긋나면 아무것도 쓰지 않고 1이다.
- [x] 수집에는 해시를 대 본 그 바이트를 넘긴다. 문서의 키는 `documents/` 기준 POSIX 상대 경로이고(`ingest` 명령의 규칙과 같다), 갱신일은 02의 함수로 바꾼 `updated_at`이다. 색인에 실패한 문서가 하나라도 있으면 1이다.
- [x] `validate --indexed`: 묶음의 모든 문서가 그 데이터베이스에 색인되어 있지 않으면 실패한다. 글귀마다 그 문서의 본문(최신 파싱 결과에서 조각 글에 드는 블록의 글을 이은 것. 절을 가르는 제목 블록은 빼고, 조각 상한의 4분의 1을 넘는 제목 블록은 문단으로 다뤄 넣는다)에 NFC 정규화와 공백류 제거 뒤 들어 있는지 본다. 본문에 없는 글귀는 세트의 오류이고, 한 문서 안에서 두 번 이상 나오는 글귀는 경고다(명세 "평가 세트의 형식", "적중의 단위").
- [x] 루트에 `compose.eval.yml`을 둔다. 데이터베이스 이름이 `rag_eval`인 PostgreSQL과 `--max-batch-tokens 4096`으로 띄우는 임베딩 TEI다. 머리 주석에 평가 전용 이름의 값과, TEI의 판을 올리는 PR은 추론 기록을 다시 만든다는 것을 적는다. `README.md`의 트리와 `.scratch/plan-head.md`의 목표 배치를 같이 고친다.
- [x] 시험(명세 Testing Decisions의 표면 시험 가운데 이 티켓의 것): 평가 전용 이름이 없으면 제품의 `RAG_DATABASE_URL`과 작업 폴더의 `.env`가 있어도 돌지 않고 빠진 이름을 알린다, 작업 폴더의 `.env`에 `RAG_PARSE_MAX_PAGES=1`이 있어도 색인 결과가 같다, 이름이 `rag_eval`로 시작하지 않는 주소는 닿지 않는 주소여도 연결 오류가 아니라 이름의 규칙이 나온다, 묶음 밖의 문서가 든 데이터베이스와 키는 같고 내용 해시가 다른 문서가 든 데이터베이스에서 스키마도 올리지 않고 1이다, 현재 판의 요소가 구성과 다르면 아무것도 쓰지 않고 1이다, 목록과 해시가 다른 문서 파일이 있으면 스키마를 올리지 않고 1이다, `validate --indexed`가 본문에 없는 글귀와 색인되지 않은 문서를 거부한다.
- [x] "아무것도 쓰지 않는다"와 "스키마도 올리지 않는다"는 바깥에서 본다. 스키마의 판 표가 없는지, 기존 관리 유스케이스로 읽은 문서와 지식베이스 설정이 그대로인지다(명세 Testing Decisions). 시험이 만드는 데이터베이스는 `rag_eval` 머리로 이름을 짓고, 뒤는 실제 테스트 PostgreSQL과 TEI 스텁(`tests/support/tei_stub.py`, `tei_server.py`)이다. 시험 문서는 `tests/support/docx_files.py` 같은 생성기로 짓는다.
- [x] 검사 넷이 초록이다.

## Comments

- 04 이후가 평가 전용 환경을 읽을 때는 `adapters/eval_environment.py`의 `read_eval_environment(os.environ)`를 부르고, 제품의 설정 객체가 필요하면 `eval_settings(environment, config)`로 짓는다. 이 객체는 환경 변수와 작업 폴더의 `.env`를 읽지 않으므로 `config.json`과 평가 전용 이름 넷에서 오지 않은 칸은 코드의 기본값이다.
- `index`의 시작 판정은 `adapters/eval_database.py`의 `check_database`다. 스키마를 올리기 전에 부르고, 04 이후의 `run`·`judge`도 같은 함수를 시작에서 부른다. 스키마가 올라 있지 않은 데이터베이스는 `SchemaState`로 가른다.
- 글귀의 본문 판정에 쓰는 `app/eval_passages.py`의 `normalize_text`와 `document_body`는 조각과 글귀를 견주는 04 이후의 적중 판정이 같은 정규화로 다시 쓴다. 제목 블록의 토큰 수는 현재 판의 모델로 세고, 센 끝점은 `validate --indexed`가 환경의 끝점으로 갈아 끼운다.
- `index_bundle`은 작업자의 한 번 돌기 입구(`worker.assembly.run_once_with_settings`)를 인자 `process_jobs`로 받는다. adapters는 worker를 import하지 못하므로(import-linter) `tools/search_eval.py`가 건넨다. 04 이후가 같은 입구를 쓸 일이 있으면 같은 방식으로 건넨다.
- 묶음의 파일 이름 상수(`config.json`, `miss-review.jsonl`, `documents.json`, `evidence.jsonl`)는 이 티켓에서 옮기지 않았다. 이 티켓이 읽는 묶음 파일은 `read_eval_set`이 이미 읽는 것뿐이라 더 읽을 파일이 없었다. 07과 12가 묶음에 쓸 때 정한다.
- `compose.eval.yml`의 TEI 이미지 태그는 `cpu-1.9.4`다. 07이 이 태그에서 장치 머리를 뗀 판(`1.9.4`)을 `config.json`의 `tei_version`과 견준다.
- PR #40 두 번째 봇 회차에서 미룬 둘(`eval_bundle_files.py`의 `_entries`가 출력 인자 `unreadable`을 바꾸는 것, `eval_set_reader.py`의 `_read_miss_reviews`가 경로를 두 번 판정하는 것)은 이 티켓이 두 파일을 넓히지 않아 손대지 않았다.
- 변이 표 `.scratch/search-eval/probes/eval_index_mutations.toml`의 스물세 변이가 모두 기대대로 빨갛다. 변이를 돌릴 때는 테스트 PostgreSQL 주소를 `RAG_TEST_DATABASE_URL`로 준다. 이름의 규칙 변이 둘은 닿지 않는 주소(`127.0.0.1:1`)에 접속을 시도해 변이 도구의 출력이 각각 131초와 133초를 냈다.
- 셀프 리뷰에서 남긴 Minor: (오류, 경고) 쌍이 `check_passages`·`check_indexed_documents`·`check_indexed`에서는 이름 없는 튜플이고 `eval_validate.ValidationReport`에서만 타입이라는 것, `check_indexed_documents`가 읽기 트랜잭션을 연 채 토큰 세기(HTTP)를 부르는 것이다. 둘 다 판정을 바꾸지 않아 이 티켓에서는 고치지 않았다. 04가 `check_indexed`의 반환을 넓힐 때 쌍을 타입으로 모은다. (`validate_bundle_indexed`가 묶음을 한 번 더 읽던 것은 PR 봇 첫 회차 뒤에 고쳤다. 두 함수가 묶음을 한 번만 읽는다.)
- PR 봇 첫 회차(CodeRabbit Major 하나, Minor 둘)의 반영: `read_schema_state`는 표 목록을 검색 경로 전체(`current_schemas(false)`)에서 읽는다. 데이터베이스에 `search_path = 빈_스키마, public`이 걸려 있으면 비한정 표 이름은 `public`으로 풀리는데 첫 스키마만 보면 빈 데이터베이스로 읽었다. `_IsolatedSettings`는 `model_config`의 `env_file`도 끈다. `settings_customise_sources`만으로는 pydantic-settings가 그 함수를 부르기 전에 `.env`를 열어, UTF-8이 아닌 `.env`가 작업 폴더에 있으면 도구가 멈췄다. 04 이후가 평가 설정 객체를 지을 때도 이 클래스를 쓴다.
- PR 봇 첫 회차에서 보류한 claude-review의 Minor 둘: `index_bundle`의 `except` 갈래가 같은 출력과 종료 코드를 되풀이하는 것, `_ingest_and_process`가 수집 루프와 처리, 대기, 실패 보고를 한 함수에 두는 것이다. 동작을 바꾸지 않는 모양 문제이고 `index`의 단계가 늘 때 함께 나눈다.
