# search-eval 03: `index`와 `validate --indexed` · 2026-11-14

티켓 `.scratch/search-eval/issues/03-eval-index-command.md`를 구현한 기록이다. 브랜치는 `feature/03-eval-index-command`이고, `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 새 워크트리에 들어가 했다. 세션 도중 컨텍스트가 한 번 압축되었다. 이번 요청의 범위는 PR과 병합까지다.

## 준비

- 읽은 것: 지시문, `.claude/skills/implement/SKILL.md`, 티켓 03, 명세 `.scratch/search-eval/spec.md`의 "평가 전용 데이터베이스"와 "자리와 층"의 `index` 항목, 앞 일지 `2026-11-13-2350-search-eval-02-eval-set-format-validate.md`의 `## 다음`.
- 앞 티켓 02의 `read_eval_set`, `BundlePaths`, `check_bundle_files`를 그대로 불렀다. 03이 새로 연 모듈은 아래와 같다.

## 한 것

- `adapters/eval_environment.py`: `read_eval_environment`(평가 전용 환경 변수 넷만 읽는다), `check_database_name`(데이터베이스 이름이 `rag_eval`로 시작하는지, 주소 질의 칸이 허용 목록 `_SAFE_QUERY_KEYS`에 드는지, `#`가 없는지를 접속하기 전에 본다), `eval_settings`(제품 설정 객체를 읽는 곳을 지어 준 값 하나로 좁힌 서브클래스 `_IsolatedSettings`로 만든다. `.env`와 `RAG_*` 환경 변수를 읽지 않는다).
- `adapters/eval_database.py`: `read_schema_state`(비어 있음, 현재 판, 다른 판), `check_database`(스키마를 올리기 전의 판정), `check_indexed`.
- `adapters/eval_index.py`: `index_bundle`. 순서는 환경, 묶음 읽기, 문서 파일 판정, 해시를 대 본 바이트 읽기, 구성 판정, 데이터베이스 판정, `migrate_database`, 수집, 작업 처리다. 작업자는 `adapters` 위의 층이라 import-linter가 직접 부르기를 막으므로 한 번 돌기 입구를 `process_jobs` 인자로 받는다.
- `adapters/eval_validate.py`: `validate_bundle_indexed`. `adapters/postgres/migrate.py`에는 읽기 전용 `head_revision()`만 더했다.
- `app/check_eval_database.py`(소속과 현재 판의 요소 판정, 기본 지식베이스를 만들 수 있는 구성 판정), `app/check_indexed_documents.py`(색인 상태, 빌드 해시, 파싱 결과 해시를 본다), `app/eval_passages.py`(NFC 정규화와 공백 제거 뒤의 부분 문자열 비교, 절 제목 블록 제외).
- `tools/search_eval.py`: `index <묶음 폴더>`와 `validate <묶음 폴더> --indexed`. `compose.eval.yml`: 평가 전용 PostgreSQL과 TEI. `README.md`의 트리와 `.scratch/plan-head.md`에 새 모듈을 더했고 `.scratch/plan.md`는 `tools/plan_table.py`로 다시 만들었다.
- 시험: `tests/tools/test_search_eval_index.py`(약 50개. 실제 테스트 PostgreSQL과 TEI 스텁을 쓰고 skip하지 않는다), 지원 `tests/support/eval_bundle.py`, `tests/conftest.py`의 `empty_eval_database_url` 픽스처.
- 변이 표 `.scratch/search-eval/probes/eval_index_mutations.toml`(20). 구현과 함께 써서 빨강을 본 적 없는 가드(소속, 요소, 스키마를 올리기 전의 판정, 이름 규칙, 설정 격리, 글귀의 정규화와 제목 제외)를 겨눈다.

## 정한 것

- 환경은 `RAG_EVAL_*` 넷만 읽는다. 제품 설정은 환경 변수와 작업 폴더의 `.env`를 읽으므로, 읽는 곳을 좁힌 서브클래스로 평가용 값만 닿게 했다.
- 질의 칸은 거부 목록이 아니라 허용 목록(`sslmode`, `connect_timeout`, `application_name`)으로 걸렀다. 거부 목록은 libpq가 받는 칸이 늘 때마다 새 우회가 생긴다.
- 스키마를 올리기 전에 문서 파일, 데이터베이스의 소속, 스키마의 판, 현재 판의 요소, 기본 지식베이스를 만들 수 있는 구성을 차례로 본다. `migrate`와 같은 코드는 기본 지식베이스의 설정을 덮어쓰고 `judge`와 `index --records write`는 조각의 글과 벡터를 밖으로 내보내므로, 평가용이 아닌 데이터베이스에는 붙지 않아야 한다.
- 조각 상한의 4분의 1을 넘는 제목 블록은 청커가 문단으로 다루므로 본문에 둔다. 한 문서 안에서 두 번 이상 나오는 글귀는 오류가 아니라 경고다.
- `compose.eval.yml`의 TEI는 CPU 판(`cpu-1.9.4`)이다. 파일 이름 상수의 중복 정리는 07과 12로 미뤘다(티켓 03 `## Comments`).

## 셀프 리뷰

`code-review` 두 축. 표준 축은 Sonnet 5.5 / high다. 커밋 전에 돌았고 Critical은 없었다.

- 고친 것(표준 축 Minor 넷): 낡은 독스트링과 수치를 맞췄다.
- 고친 것(명세 축): 주소의 질의 칸이 목적지를 바꿀 수 있는 우회(`?dbname=`)를 거부 목록 대신 허용 목록으로 막았다. 스키마를 올린 뒤에야 거부하던 구성(차원 상한 초과, 모르는 청킹 전략)을 `check_default_records_input`으로 올리기 전에 거부하게 했다. 변이 8·9가 겨눈다.
- 남긴 것(Minor 셋, 판정을 바꾸지 않는다): (오류, 경고) 쌍이 하위 층에서는 이름 없는 튜플이다. `validate_bundle_indexed`가 묶음을 한 번 더 읽는다. `check_indexed_documents`가 읽기 트랜잭션을 연 채 문서마다 토큰 세기(HTTP)를 부른다. 티켓 03 `## Comments`와 PR 본문에 적었다. 04가 `check_indexed`의 반환을 넓힐 때 모은다.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, 변이 표 전체.

## PR 직전 리뷰

CodeRabbit CLI(0.7.5)가 한 번 돌았다. `Seat: not assigned`(Free)에서도 `review_completed`로 끝까지 돌았고 지적은 넷이었다.

- 고친 것(Major): 주소에 `#`가 들면 `urlsplit`은 `#` 뒤를 조각으로 잘라 질의 칸 허용 목록을 건너뛰지만 `make_url`은 `#?dbname=x`를 질의로 읽어 두 파서가 갈렸다. `#`가 든 주소를 거부하고 `#?dbname=`과 `#?host=` 주소를 시험에 더했다(변이 19).
- 고친 것(Minor): `index`가 스키마를 올리거나 수집하다 난 `SQLAlchemyError`·`OSError`는 호스트와 사용자 이름이 든 스택 대신 오류의 종류만 알리고 1로 끝낸다(원칙 V). 변이 20이 겨눈다.
- 남긴 것(Minor): 읽기 트랜잭션 안에서 TEI를 부르는 것. 셀프 리뷰가 남긴 셋째와 같다.
- 오탐 둘: 코드로 확인해 닫았다.
- 이 반영이 새로 쓴 사실 문장(PR 봇이 겨냥할 것): `eval_index.py`의 `except (OSError, SQLAlchemyError)` 주석("접속 실패의 메시지와 스택은 호스트와 사용자 이름을 싣는다(원칙 V). 오류의 종류만 알린다."), `eval_environment.py`의 `check_database_name`이 `#`를 거부하는 까닭의 주석, 커밋 2fc7e65 메시지의 `urlsplit`·`make_url` 서술, PR 본문의 "두 파서가 질의를 다르게 읽는 자리", 티켓 03 `## Comments`.
- 다시 돌린 것: 변이 표 20 모두 기대대로 빨강(6·7·19·20을 따로 다시 돌렸다), 전체 시험은 커밋의 pre-commit이 돌려 초록이었다.

## 검증

- 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, `uv run python tools/run_checks.py`(두 커밋 f2b1732와 2fc7e65 모두 종료 코드 0, 전체 pytest 포함, Skipped 없음), `tools/mutate.py`로 변이 20 모두 기대대로 빨강.
- 변이 표 실행은 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test PYTHONUTF8=1 uv run python tools/mutate.py <표>`다. 이름 규칙을 겨눈 변이는 닿지 않는 주소에 접속을 시도해 각각 130초 안팎이 걸린다.
- 실제 TEI(bge-m3)로 색인하는 실행은 이 PR에서 하지 않았다. 시험은 TEI 스텁(차원 16)으로 돈다. CI 러너에서 4096차원으로 뜨는지는 게이트 티켓(11)이 본다.

## 회고

낸 후보 여덟. 승인 2, 기각 6, 넘김 없음.

1. 변이 표의 표지로 처음 고른 글이 시험 파일에 글자 그대로 있어 도구가 거부했고, 실제 실패 출력에서 표지를 다시 골라 한 번 더 돌았다. → 승인(회차로 세는 것). 열린 항목 `mutate-marker-discovery`가 이미 처방한 사건이다. 승인 줄을 4회차로 고쳤다. 5회차 전이라 반영하지 않는다.
2. 변이 도구를 돌리는 동안 같은 체크아웃에서 pytest를 겹쳐 돌려, 도구가 소스를 잠깐 바꿔 둔 사이의 결과를 버리고 다시 돌았다. → 승인(더하는 것). 사건은 이 세션이고, 층은 훅이다(`hook_edit_during_mutate`가 편집만 알리고 pytest는 알리지 않는다. `tools/mutate.py`에도 겹침을 막는 장치가 없다). PR 하나로 되돌릴 수 있다. 대기열에서 `--search 동시 --search concurrent --search 겹쳐 --search overlap.*pytest`로 찾아 같은 일을 다룬 열린 항목이 없음을 보았고(맞은 하나는 `spec-review-transition-crossing`으로 다른 일이다), 새 항목 `pytest-during-mutate`를 1회차로 썼다. 손상이 아니고 5회차 전이라 반영하지 않는다. `mutate-marker-discovery`와 같은 도구를 다루지만 처방(표지를 고르는 길과 겹침을 알리는 훅)이 달라 서로 다른 일로 두었다.
3. 변이 표의 `old` 텍스트가 `ruff format`의 줄바꿈으로 깨져 도구가 "한 번만 맞아야 한다"고 알렸다. → 기각. 이미 있는 도구 검사가 그 자리에서 알렸고 표를 고쳤다.
4. TOML 리터럴 문자열의 `\\s+` 이스케이프 오류와 변이 번호 오기. → 기각. 도구 실행이 그 자리에서 드러냈고 같은 실수의 반복이 아니다.
5. 워크트리 가드가 리다이렉트와 복합 git 명령을 거부했다. → 기각. 이미 있는 가드가 그 자리에서 막았고, `git commit -F <파일>`로 따랐다.
6. 셀프 리뷰 두 축이 못 본 Major(`#`가 든 주소가 질의 칸 허용 목록을 건너뛴다)가 PR 직전 CodeRabbit CLI 단계에서 나왔다. → 기각. 리뷰 파이프라인의 PR 직전 층이 제 몫을 한 것이다. 02 회고가 "다시 나오면 회차로 센다"고 한 것은 경로를 다루는 코드의 윈도 특수 이름이고, 이번 것은 두 URL 파서가 같은 주소를 다르게 읽는 것이라 꼴이 다르다. 걸러야 할 입력 목록은 도구 하나로 닫을 수 없다.
7. 한국어 글자 폭 때문에 E501이 두 줄에 났고, `list[object]`가 `Sequence[UUID]`에 맞지 않는다고 pyright가 알렸다. → 기각. 린터와 타입체커가 그 자리에서 알렸다.
8. IDE가 낡은 pyright 진단을 보였다. → 기각. 사건이 아니라 소음이고 `uv run pyright`가 판정자다.

만료: 첫 `uv run python tools/queue_open_rows.py`가 만료할 항목이 없다고 했다(`--ref origin/dev` 출력과의 교집합도 비다). 회차 5 이상은 `measured-claim-beyond-probe`(6회차)뿐이고 이 브랜치와 닿지 않는다.

## 다음

- 이 PR이 병합되면 티켓 03은 끝이다. 04가 `check_indexed`의 반환을 넓힐 때 Minor 셋(이름 없는 튜플, 묶음 이중 읽기, 읽기 트랜잭션 안의 토큰 세기)을 모은다(티켓 03 `## Comments`).
- 07과 12는 `compose.eval.yml`의 TEI `cpu-1.9.4` 태그와 파일 이름 상수 결정을 티켓 03 `## Comments`에서 읽는다. 게이트 티켓(11)이 CI 러너에서 TEI가 4096차원으로 뜨는지 실제 실행으로 본다.
- 02에서 이어진 것: PR #40 봇 회차의 보류 둘(`_entries`의 출력 인자 변경, `_read_miss_reviews`의 이중 경로 검사)은 03이 그 파일을 넓히지 않아 건드리지 않았다. 변이 표 둘의 윈도 전용 표지는 리눅스에서 다시 골라야 한다.
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)이다. 병합 뒤 `tidy-checkouts`는 다음 새 세션이 돈다.
- 사람에게 넘긴 정리: 워크트리 `14-reindex-version-switch`(앞 일지에서 이어졌다).
