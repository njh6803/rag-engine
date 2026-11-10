# core 03 migrate와 기본 레코드 일지 · 2026-11-11

티켓 `.scratch/core/issues/03-migrate-default-records.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/03-migrate-default-records`다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, PR 직전 리뷰, 남긴 것을 차례로 둔다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 명세(`.scratch/core/spec.md`)의 설정·관리 명령·데이터 모델과 스키마·색인 판 절, ADR 0006·0011·0015, 직전 일지(`2026-11-10-2250-core-02-contract-layers.md`)의 "다음".
- 의존성을 둘 더했다: `pydantic-settings`(ADR 0015)와 `kiwipiepy`(ADR 0006, 토크나이저 판을 읽으려는 용도이고 import하지 않는다). 설치된 판은 pydantic-settings 2.16.2, kiwipiepy 0.24.1, kiwipiepy_model 0.24.0이다.

## 정한 것

- **판 요소 계산은 어댑터에 둔다.** `adapters/index_elements.py`의 `compute_index_elements`가 스키마 판, 임베딩 모델·차원, 청킹 설정 해시, 토크나이저 판을 낸다. app은 이 함수를 `ComputeIndexElements` 포트 별칭으로 받아 쓰므로 kiwipiepy를 import하지 않는다. 청킹 해시에는 전략 구현 판(`STRUCTURE_FIRST_VERSION`)과 kiwipiepy·kiwipiepy_model의 설치 판이 든다. 토크나이저 판 문자열은 `kiwipiepy X; kiwipiepy_model Y; keyword-rules Z` 꼴이다.
- **`ensure_default_records`는 한 트랜잭션에서 돈다.** `add_*` 셋으로 기본 원천·그룹·지식베이스를 멱등으로 만든 뒤 지식베이스 행을 `FOR UPDATE`로 잠그고 읽어 설정을 반영한다. 모델·차원이 같고 끝점만 다른 살아 있는 판(건설 중 포함)은 끝점만 고친다. 현재 판이 없으면 BUILDING 판을 만들어 현재로 전환하고, 마지막에 그 판의 HNSW 부분 색인(`ix_chunks_hnsw_<hex>`)을 만든다.
- **차원 상한 2,000은 도메인 상수다**(`MAX_EMBEDDING_DIMENSIONS`). 넘으면 `ConfigurationError`이고 지식베이스를 만들지도 고치지도 않는다. 오류 메시지에는 설정 값이 실리지 않는다.
- **임베딩 끝점의 기본값은 두지 않았다.** 명세가 기본 호스트를 정하지 않았다. `RAG_DEFAULT_EMBEDDING_URL`이 없으면 `migrate`가 스키마를 올리기 전에 설정 오류로 끝난다(리뷰 지적으로 처음의 지어낸 기본값 `http://embedding:80`을 걷었다).
- **`Catalog` 포트에 쓰기 여섯을 더했다.** 멱등인 `add_source`, `add_group`, `add_knowledge_base`, `add_group_to_knowledge_base`와 덮어쓰는 `update_knowledge_base`, `update_index_version_endpoint`다.
- **PostgreSQL 작업 단위.** `begin()`이 비동기 컨텍스트이고 예외 없이 나가면 커밋, 예외면 롤백이다. 엔진은 `hide_parameters=True`이고, 비동기 실행은 Windows 때문에 Selector 루프에서 돈다(`run_in_selector_loop`, ADR 0011).
- **설정 객체의 pyright 우회.** `pydantic-settings`의 합성 `__init__`이 `_env_file`을 모르는 문제를 `if TYPE_CHECKING: def __init__(self, **values: object)`로 풀었다. 원칙 II가 막는 넷은 쓰지 않았다.
- **테스트 템플릿 데이터베이스.** 세션(xdist 작업자마다)당 한 번 `migrate_database`로 만들고, 시험마다 `CREATE DATABASE … TEMPLATE …`로 복제해 쓰고 끝나면 `DROP DATABASE … WITH (FORCE)`로 지운다. 복제본 이름에는 `uuid4().hex`를 붙인다. `build_test_settings`는 개발자 셸의 `RAG_*`를 읽지 않도록 `_env_prefix="RAG_TEST_UNUSED_"`와 `_env_file=None`으로 만든다.
- **아직 없는 어댑터 자리.** `PostgresTransaction.documents`·`jobs`와 `PostgresVectorIndex`의 다섯 메서드(`replace_chunks`, `delete_chunks`, `archive_chunks`, `get_state`, `save_state`)는 `NotImplementedError`다. 소유 티켓은 05, 07, 10, 11이고 각 티켓 머리의 "03이 넘긴 것"에 적었다.

## 손으로 본 것

- **변이.** 구현 뒤에 쓴 시험이라 빨강을 본 적이 없어 변이 일곱을 손으로 확인했다(`tools/mutate.py` 대신 스크래치패드의 손 스크립트로 했다. 원문이 한 번만 나오는지 보고 바이트 그대로 복원한다). 끝점 따라가기 끔, 차원 한도 경계(`>=`), HNSW 생략, 커밋 안 함, 롤백 안 함, 문장 분리기 판을 해시에서 제외, 설정 갱신 생략이다. 일곱 모두 빨개졌고 살아남은 변이는 없었다. `lock_knowledge_bases`의 `read=` 값은 반환 행만 보는 시험이라 잡히지 않는다(남긴 것).

## 코드 리뷰

`/code-review`로 두 축을 돌렸다(범위: `origin/main` 이후 스테이지된 변경과 미추적 파일). Critical은 없었다.

고친 것:
- `build_test_settings` 독스트링이 "환경 변수를 읽지 않는다"고 적었는데 실제로는 읽었다. `_env_prefix="RAG_TEST_UNUSED_"`로 코드를 고쳤다.
- 로그 형식 거부 시험이 까닭을 단언하지 않았다. `loc`과 `type`(`literal_error`)을 단언한다.
- `migrate` 성공 시험이 데이터베이스 상태를 보지 않았다. 지식베이스와 현재 판 행을 읽어 단언한다.
- 격리 시험이 실행 순서에 기댔고 `("0001",)`를 하드코딩했다. 복제 공장 `make_seeded_database`로 두 복제본을 한 시험에서 비교하고 버전 행 수만 본다.
- 05 티켓 메모의 "모두 멱등" 문장이 틀렸다. 멱등은 `add_*` 넷뿐이라고 고쳤다. 같은 메모의 "그 둘"이 가리키는 대상이 없어 소유 티켓을 나열했다.
- 명세 축: 지어낸 임베딩 끝점 기본값 제거와 시험 둘 추가, `_ensure_default_records`를 `_run_default_records_use_case`로 이름 바꾸기(`app.ensure_default_records`와 헷갈렸다).

남긴 것과 이유:
- alembic 단계의 동시 실행 방어: alembic 자체의 몫이다.
- `is_default` 부분 유일 색인 충돌: 이름 `default`가 유일이라 드문 경우다.
- DB 접속 실패 때의 트레이스백: 비밀번호는 실리지 않는다(`hide_parameters`와 메시지 검증).
- `Settings` 불변식 부재와 Data Clumps·Duplicated Code 판단: 02 일지가 03 이후로 미룬 자리다.
- `SCHEMA_VERSION`과 alembic 판을 잇는 시험 없음: 이 티켓의 수용 기준에 없어 두지 않았다. 받는 티켓은 정하지 않았다.
- 명세에 없는 `gt=0` 검증: 가벼운 초과로 유지한다.

다시 돌린 명령: `ruff check .`, `ruff format --check .`, `pyright`(0 오류), `lint-imports`(2 kept), 검사 러너 전체(`tools/run_checks.py`의 아홉 검사와 pytest 162.2초). 커밋(`ecc3382`)의 pre-commit도 같은 검사를 다시 돌려 초록이었다(pytest 187.7초).

## PR 직전 리뷰

CodeRabbit CLI(`coderabbit-review` 에이전트)는 돌지 못했다. `coderabbit review --agent --include-untracked --base origin/main` 실행을 권한 분류기가 거부했고(사유: 데이터 반출), 우회하지 않았다. 설치(0.7.5)와 로그인, `Seat: not assigned`(Free)는 확인했다. 운영 문서의 대체 경로로 `bug-perf-review`와 내장 `/security-review`를 돌렸다.

- 코드를 읽은 표준 에이전트(CodeRabbit 에이전트가 CLI 없이 Read, Grep으로 본 결과): Minor 셋, Critical·Major 없음.
  - 고친 것: 05 티켓의 "같은 이름이 이미 있으면"이 `add_group_to_knowledge_base`(키가 이름이 아니라 지식베이스와 그룹의 쌍)에 맞지 않았다. "같은 키(이름, 또는 지식베이스와 그룹의 쌍)가 이미 있으면 아무것도 하지 않는"으로 고쳤다. `bootstrap.py`의 주석이 "설정이 모자라면 스키마를 올리기 전에 멈춘다"고 했는데 차원 상한과 청킹 전략은 스키마가 오른 뒤에 걸린다. 주석을 사실대로 고쳤다.
  - 남긴 것: `retired_at`은 DB 시계(`sa.func.now()`)이고 `created_at`은 앱이 넘긴 `now`라 시계가 둘이다. 판 전환 한 곳의 표시 칸이고 정합성을 깨지 않아 둔다.
- `bug-perf-review`: 유효 Minor 하나, Critical·Major 없음. 유스케이스를 여섯 동시 실행(별도 엔진)으로 두 번 돌려 예외 0건, 원천·그룹·지식베이스·판 각 1개, HNSW 색인 1개를 직접 확인했다.
  - 남긴 것: `tests/conftest.py`의 `make_seeded_database`와 `empty_database_url` 정리 루프가 DROP 한 번이 실패하면 나머지 복제본을 지우지 못한다. 서버 연결이 끊기는 때뿐이라 드물어 선택 사항으로 둔다.
  - 보류: `upgrade_to_head`(alembic)를 두 프로세스가 동시에 도는 첫 설치는 확인하지 못했다(스레드 시험은 120초 안에 끝나지 않았다). alembic 구간에 어드바이저리 락이 없다(`migrate.py`). 이 티켓의 수용 기준에 없고 02에서 온 `upgrade_to_head`의 몫이라 고치지 않았다.
- `/security-review`: 보고할 취약점 없음. 동적 SQL은 HNSW DDL 하나뿐이고 들어가는 값이 UUID와 검증된 정수 차원이다.
