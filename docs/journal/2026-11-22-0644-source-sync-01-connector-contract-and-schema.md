# source-sync 01: 커넥터 인터페이스 1.0과 이 기능의 스키마 · 2026-11-22

source-sync 티켓을 나눈 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5 / high). 시작 프롬프트는 `/implement .scratch/source-sync/issues/01-connector-contract-and-schema.md`이고, 브랜치는 `feature/01-connector-contract-and-schema`, 작업은 워크트리 `01-connector-contract-and-schema`에서 했다. 요청 범위는 PR과 병합까지다.

## 준비

- 주 체크아웃 세션으로 열려 `tidy-checkouts`를 먼저 돌고, 그 뒤 `EnterWorktree`로 새 워크트리에 들어가 브랜치를 바꿨다. 사람에게 넘긴 것은 보고만 했고 답을 기다리지 않았다.
- 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 지은 것

**도메인.** `domain/connectors.py`에 커넥터 인터페이스 1.0을 두었다. `CONNECTOR_INTERFACE_VERSION`은 `1.0.0`이다. 사유 값 다섯(`invalid_config`, `unreadable`, `rejected`, `not_found`, `too_large`)을 든 `ConnectorFailureReason`, 사유만 받는 `ConnectorError`, 쓸 수 없는 커넥터를 알리는 `ConnectorUnavailableError`, 목록과 받기의 값(`ListedItem`, `FetchedItem`), `Connector` Protocol, 만드는 함수 꼴 `ConnectorFactory`가 든다. 모듈 머리 설명에 명세가 인터페이스의 설명에 적으라고 한 약속을 모두 적었다.

**포트.** `domain/ports.py`에 `ConnectorRegistry`, `ScheduleCalculator`, `SyncRecordStore`를 더하고 메서드의 모양은 처음 쓰는 티켓이 바꿀 수 있다고 독스트링에 적었다. 머리 설명의 `Connector`·`Transform` 문장도 고쳤다. `ScheduleCalculator`가 올리는 `InvalidScheduleError`를 `domain/errors.py`에 더했다.

**엔티티.** 티켓 본문에 없지만 `SyncRecordStore`가 값 형식으로 쓰는 `SyncRecord`와 그 열거(`SyncTrigger`, `SyncRecordStatus`)를 `domain/entities.py`에 더했다. 이미 있는 `Source`, `Job`, `Document` 엔티티는 이 티켓에서 바꾸지 않았다. 그 칸을 쓰는 티켓이 더한다.

**레지스트리.** `adapters/connectors/registry.py`의 `EntryPointConnectorRegistry`가 entry point 그룹 `rag_engine.connectors`에서 이름으로 커넥터를 찾아 만든다. 파서 레지스트리와 같은 모양이다. 만드는 함수가 올린 `ConnectorError`는 그대로 전하고, 그 밖의 예외와 읽기 실패와 major가 다른 인터페이스는 글 없는 `ConnectorUnavailableError`로 거부한다(`raise ... from None`이라 원인도 남기지 않는다). 로그에는 이름과 인터페이스 버전과 예외 종류의 이름만 남긴다(원칙 V).

**버전 줄.** `rag-engine --version`이 파서 인터페이스 다음에 `커넥터 인터페이스 1.0.0`을 찍는다. 시험 둘(`tests/test_version_command.py`, `tests/tools/test_release.py`)을 맞췄다.

**스키마.** 마이그레이션 `0004_pull_sources_and_sync_records.py` 하나에 모두 담았다.

- `sources`: 갈래 `pull`, 일곱 칸(커넥터, 설정, 그룹, 일정, 다음 실행 시각, 일시 중지, 제외 패턴)과 지운 시각, 만든 시각. 밀어 넣는 원천은 가져오기 전용 칸이 모두 비어 있어야 하고 가져오는 원천은 커넥터 이름, 설정, 그룹이 있어야 한다. 이미 있는 원천의 만든 시각은 올리는 순간의 시각으로 채운다.
- `documents`: 변경 확인값, 건너뜀 사유, 원천과 함께 지워졌다는 표시, 상태 `skipped`, 비어 있을 수 있는 `blob_path`.
- `jobs`: 종류 다섯, `source_id`와 `options`, 비어 있을 수 있는 `document_id`, 종류별 참조 제약, 부분 유일 색인 `uq_jobs_source_id_kind_active`(`NULLS NOT DISTINCT`), 색인 작업이 아닌 작업만 담은 꺼내기용 부분 색인.
- `sync_records` 표와 `(source_id, created_at)` 색인.
- 내리기(downgrade)도 썼다. 이 판이 더한 칸과 `sync_records` 표를 그 안의 값과 함께 지운다. 가져오는 원천, 건너뜀 문서, 원본 경로가 빈 문서, 색인이 아닌 작업이 남아 있으면 옛 제약이 받지 않아 내리는 중에 멈춘다. 머리 설명과 업그레이드 원고에 적었다(처음에는 "데이터를 지우지 않는다"고 적었다가 셀프 리뷰가 거짓이라고 잡았다. 아래 "셀프 리뷰").
- `SCHEMA_VERSION`은 올리지 않았다. 색인 판의 요소가 아닌 표를 고치므로 재색인이 필요 없다(0003과 같은 판단). 머리 설명에 까닭을 적었다.

`adapters/postgres/tables.py`를 마이그레이션과 맞췄고 `compare_metadata` 시험이 어긋남 없음을 확인한다. 업그레이드 원고는 `docs/release-notes/upgrade/source-sync-schema.md`다.

## 이 세션이 정한 것

- 티켓 본문과 명세가 정하지 않은 둘이다. 첫째, 가져오는 원천의 설정(`config`)도 비어 있으면 안 된다(명세는 커넥터 이름과 그룹만 요구한다). 설정을 읽지 못하면 커넥터를 만들 수 없어서다. 둘째, 건너뜀 사유 칸은 `skip_reason IS NULL OR (status = 'skipped' AND skip_reason IN ('encrypted', 'no_text'))`다. 명세의 사유 둘을 닫힌 값으로 두었다.
- 시험은 헤더의 차례대로 먼저 썼다(레지스트리, 도메인, 마이그레이션, 버전). 내리기 시험을 쓰다가 옛 판 스키마에는 `source_id` 칸이 없어 헬퍼 `_job_row`를 쓸 수 없다는 것을 알고 `_insert`로 직접 넣게 고쳤다.

## 겪은 것

- 테스트 코드에 `# type: ignore`를 썼다가(원칙 II) `inspect.signature`와 `setattr`로 바꿨다.
- 편집기의 pyright 진단은 새 모듈을 못 찾는다고 계속 띄웠지만 명령줄 `uv run pyright`는 0건이었다. 편집기 쪽이 옛 캐시였다.

## 검증

브랜치는 `feature/01-connector-contract-and-schema`였고 `tools/sibling_overlap.py`는 겹침 없음이었다. 손으로 친 검사는 모두 초록이다. `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`(계약 둘 KEPT), `tools/check_type_escapes.py`, `uv run pytest -n auto`(5051개 통과, 457초)다. 셀프 리뷰를 반영한 뒤에는 `ruff check`, `ruff format`, `pyright`(0 errors), `lint-imports`, `check_type_escapes`를 다시 돌려 모두 초록이었고, 고친 시험 다섯 파일(`test_migrations.py`, `test_connector_registry.py`, `test_connectors.py`, `test_version_command.py`, `test_release.py`)은 234개가 통과했다. PR 직전 리뷰를 반영한 뒤에도 `ruff check`, `ruff format --check`, `pyright`(0 errors), `lint-imports`, `check_type_escapes`를 다시 돌려 모두 0으로 끝났고, 시험 네 파일(`test_connectors.py`, `test_connector_registry.py`, `test_migrations.py`, `test_version_command.py`)은 120개가 통과했다. 전체 `pytest`는 pre-commit의 검사 러너가 돌고 그 결과는 커밋 뒤에 이 절에 적는다. 변이 도구(`tools/mutate.py`)는 돌리지 않았다. 이 티켓의 시험은 모두 구현 전에 빨갛게 써서 초록이 된 것이라 구현 전부터 초록이던 가드 시험이 없다.

## 셀프 리뷰

`/code-review`를 고정점 `origin/dev`(base `48cfc03`, HEAD와 같다)로 돌렸다. 본 범위는 고친 추적 파일 열, 미추적 파일 열(새 디렉터리와 마이그레이션, 시험, 일지, 원고), 커밋 0이다. 표준 축은 Sonnet(노력 high), 명세 축은 이 세션의 모델로 돌렸다. 두 축에 주장 검증 목록과 밀 주장(마이그레이션 내리기의 서술, 부분 유일 색인의 규칙, 독스트링과 명세의 일치)을 넘겼다.

### 보고

- **표준 축.** 하드 위반은 없었다. 주장 검증에서 Major 하나가 나왔다. 마이그레이션 머리 설명의 "내릴 때는 데이터를 지우지 않는다"는 거짓이다(서브에이전트가 임시 데이터베이스로 0003에서 올리고 지움 표시를 넣은 뒤 내려 보았다. 칸이 조용히 사라지고 `sync_records`도 함께 사라졌으며, 다시 올리면 지운 원천이 살아났다). 판단 항목은 레지스트리의 `_major`가 `try` 밖이라 정수 버전에서 `AttributeError`가 새는 것, `except` 위 주석 "서버는 기동한다"가 파서 레지스트리에서 옮긴 낡은 문장인 것, `ConnectorError`가 `copy`와 pickle에서 깨지는 것, `_major`가 세 벌인 것, README의 지도를 고치지 않은 것, 시그니처를 보는 시험의 구현 결합, 같은 이름 둘의 조용한 선택이다.
- **명세 축.** Major 둘, 틀린 것 셋, 빠진 것 하나였다. `sync_records.listed`가 `NOT NULL DEFAULT 0`이라 명세 176행의 "목록을 받지 못한 실패에서는 `listed`가 비어 있고, 받았는데 0건이었으면 0이다"를 가를 수 없다. `sync_records.job_id`가 `jobs.id`를 가리키는데 지울 때의 동작이 없어, 원천 삭제가 대기 중인 동기화 작업을 지우면(명세 269행) 외래 키 위반이 난다. 레지스트리 독스트링의 "`create` 호출이 드물어서다"는 거짓이다(작업자가 문서마다 만들 수 있다). `domain/__init__.py`의 머리 설명이 낡았고, 인터페이스의 확장자 규칙에 대소문자를 가리지 않는다는 말이 없었다(명세 165행). 가져오는 원천의 `config NOT NULL`은 명세가 요구하지 않은 엄격함이라 범위 넘침 여부를 물었고 해는 없다고 보았다.

### 판정과 반영

**고친 것.** 근거를 열고 판정한 뒤 모두 고쳤다.

- 마이그레이션 내리기의 서술(표준 축 Major): 머리 설명을 고쳐 이 판이 더한 칸과 표를 그 안의 값과 함께 지운다고 적었다. 지움 표시와 동기화 기록은 되돌릴 수 없고, 다시 올리면 기본값이 된다. 옛 제약이 받지 않는 행이 있으면 멈추고 아무것도 바꾸지 않는다고도 적었다. 업그레이드 원고와 이 일지의 같은 문장도 맞췄다. 같은 머리 설명의 "종류를 다섯으로 늘리고" 뒤에 이름이 넷만 있던 것도 `index_document`를 더해 맞췄다.
- `sync_records.listed`(명세 축 Major): 널을 허용하고 기본값을 없앴다. 표 정의도 맞췄고 시험을 고쳤다(기본 행은 `listed`가 비고, 0을 준 행은 0이다).
- `sync_records.job_id`(명세 축 Major): `ON DELETE SET NULL`로 정했다. 작업 행을 지우면 기록은 남고 작업 칸만 빈다. 명세 269행이 기록을 `failed`와 `source_deleted`로 닫는다고 했고 기록의 "작업" 칸은 없으면 비운다고 했다. 표 정의와 시험을 맞췄다.
- 레지스트리의 버전 판정(두 축 모두): `_major`를 `try` 안으로 옮겼다. 정수나 `None`인 버전이 `ConnectorUnavailableError`로 거부된다. 시험을 더했다. `except` 위 주석도 새로 썼다.
- 레지스트리 클래스 독스트링(명세 축): "드물어서다" 문장을 걷고 캐시하지 않는다는 사실만 적었다. 읽는 데 드는 시간은 재지 않았고, 호출이 잦아지면 부르는 티켓이 캐시를 더한다. 명세 축 서브에이전트가 이 환경에서 한 번에 15.6ms를 쟀다고 했지만 커밋한 프로브가 아니라서 이 글에는 옮기지 않았다.
- `ConnectorError`(표준 축): 부모에게 사유를 그대로 넘겨 `copy`와 pickle이 같은 인자로 다시 만든다. 글은 `StrEnum`이라 여전히 사유의 값이다. 시험을 더했다.
- `domain/__init__.py`, README 지도 세 줄, 인터페이스 독스트링의 대소문자(두 축).

**남긴 것.**

- `_major`가 세 벌(`adapters/connectors/registry.py`, `adapters/parsers/registry.py`, `eval_set_reader.py`의 `_major_of`)이고 파서 레지스트리에는 같은 구멍(정수 버전)이 있다. 이 티켓의 범위 밖이고 파서를 건드리면 다른 계약에 닿는다. 사건 하나(Duplicated Code, Minor)라 대기열에 올리지 않는다.
- 같은 `entry.name`이 둘이면 첫 것만 고른다(Nit). 설치처가 같은 이름을 둘 깐 것이라 거부할지 고르는 일은 04가 서버 경로 커넥터를 등록할 때 정한다.
- `inspect.signature`로 사유만 받는 것을 보는 시험(Nit): 글을 받는 길이 없다는 약속을 시그니처로 고정한 것이라 일부러 구현에 묶었다.
- 가져오는 원천의 `config NOT NULL`(범위 넘침 여부): 설정을 읽지 못하면 커넥터를 만들 수 없고 설정은 늘 객체라 해가 없다. 일지 "이 세션이 정한 것"에 적었다.
- 지운 원천의 `deleted_with_source`가 참이면 `deleted_at`이 있어야 한다는 CHECK(선택적 보강): 되살릴 때 두 칸을 한 문장에서 지우도록 07과 12가 맡는다. 지금 걸면 두 칸을 따로 쓰는 장면을 막아 시험을 못 쓴다.
- `JobQueue.claim`이 종류를 거르지 않고 `_job(row)`가 `document_id`를 UUID로 가정한다(명세 축 (d)). 아직 색인 작업이 아닌 작업을 넣는 코드가 없어 지금은 맞다. 첫 비색인 작업을 넣는 티켓(07)이 이것부터 고친다. "다음"에 적었다.

- 문서가 `skipped` 상태이면 `skip_reason`이 있어야 한다는 CHECK(선택적 보강): 건너뜀을 쓰는 02가 어떤 사유를 넣을지 정한 뒤에 건다. 지금 걸면 02의 시험이 사유 없는 `skipped` 행을 만들 수 없다.
- 레지스트리의 `entry_points` 캐시는 레지스트리 독스트링이 적은 대로, 커넥터를 문서마다 만들게 되는 티켓이 더한다.

**다시 돌린 명령.** 고친 뒤에 아래 "검증"의 명령을 모두 다시 돌렸고 결과는 거기에 적는다.

## PR 직전 리뷰

CodeRabbit CLI(`coderabbit-review` 서브에이전트가 부른다)는 권한 분류기가 명령을 막아 돌지 못했다. 우회하지 않았다. 같은 자리의 `bug-perf-review` 서브에이전트가 커밋 `4401df4`를 읽고 임시 데이터베이스로 내려 보는 것까지 했고, 그 보고를 받은 턴에 아래로 옮긴다. 보안 축은 이 세션의 내장 `/security-review`가 보는 몫이라 고친 뒤에 돌리고 결과를 이 절 끝에 적는다.

**보고.** Critical과 Major는 없었고 유효한 Minor 셋이었다.

1. `ConnectorUnavailableError`가 `ConnectorError`와 달리 `copy`와 pickle에서 깨진다. 생성자가 인자를 받지 않는데 부모에게 글을 넘겨 `args`가 비지 않았다.
2. 레지스트리가 만드는 함수가 올린 `ConnectorError`를 그대로 다시 올려, 설치처의 예외가 원인(`__cause__`)으로 묶여 있으면 그 글이 서버 쪽으로 따라온다. 로그와 응답에는 쓰지 않지만 원칙 V가 말하는 글이 예외 사슬에 남는다.
3. 내리기가 멈추는 두 경우(가져오는 원천이 남은 경우, 색인이 아닌 작업이 남은 경우)를 재는 시험이 없다. 서술은 있고 시험이 없었다.
4. `SyncRecord.listed`가 `int`인데 표에서는 비울 수 있다. 엔티티와 표가 어긋났다.

**판정과 반영.** 넷 모두 근거를 열어 맞다고 보고 이 PR에서 고쳤다.

- `ConnectorUnavailableError`에서 생성자를 걷고 `__str__`만 둔다. `args`가 비므로 복사와 pickle이 같은 예외를 다시 만든다. 시험을 더했다.
- 레지스트리가 `ConnectorError`를 받으면 사유만 들어 새로 올리고 원인은 끊는다(`from None`). 원인이 묶인 `ConnectorError`를 내는 가짜 함수(`create_chained`)와 시험을 더했다.
- 내리기가 멈추는 두 경우를 재는 시험 둘을 더했다. 모두 `IntegrityError`로 멈추고, 멈춘 뒤에도 판은 0004이고 `sync_records`가 남는다.
- `SyncRecord.listed`를 `int | None`으로 고쳤다.

## 회고

후보 일곱을 냈다. 승인 0, 기각 일곱, 넘김 0이다. 일곱째는 셀프 리뷰가 끝난 뒤에 더했다(아래 7). 대기열 항목에 회차를 더하거나 새로 쓴 것은 없다. `tools/queue_open_rows.py`의 만료할 항목은 "(없음)"이었다.

1. **테스트에 `# type: ignore`를 썼다가 고쳤다.** 기각. `tools/check_type_escapes.py`가 같은 자리에서 잡는 검사이고 커밋 전에 스스로 바꿨다. 이미 있는 검사가 그 자리에서 막은 일이다.
2. **맨 `python` heredoc 호출과 파이프(`| tail`)를 훅이 막거나 경고했다.** 기각. 이미 있는 훅이 그 자리에서 막거나 알렸고, `CLAUDE.md`의 환경 함정이 같은 사건을 적고 있다.
3. **한글 폭 때문에 줄 길이 경고(E501)가 일곱 줄 났다.** 기각. `hook_ruff_line_width`가 쓰는 순간 알렸고 `tools/rewrap_comments.py`로 고쳤다.
4. **스크래치 파일로 보내려던 리다이렉트 경로가 없는 폴더였다.** 기각. 한 번의 오타이고 명령이 바로 실패해 비용이 없었다.
5. **내리기 시험이 옛 판에 없는 `source_id` 칸을 쓰는 헬퍼를 불러 실패했다.** 기각. 시험이 그 자리에서 빨갛게 드러났고 시험을 고쳐 초록이 됐다.
6. **편집기의 pyright 진단이 새로 만든 모듈을 못 찾는다고 여러 번 띄웠다.** 기각. 명령줄 `uv run pyright`가 0건이라 판정이 갈렸고 처방이 될 만한 고칠 곳이 없다(편집기 쪽 캐시다).

7. **재 보지 않고 쓴 사실 문장 둘이 셀프 리뷰에서 거짓으로 나왔다.** 기각. 마이그레이션 머리 설명의 "내릴 때는 데이터를 지우지 않는다"와 레지스트리 독스트링의 "호출이 드물어서다"다. 둘 다 구현하며 처음 쓴 문장이고, 이 저장소가 셀프 리뷰의 주장 검증으로 잡도록 둔 자리에서 잡혔다. 리뷰가 제 몫을 한 사건이라 회차로 세지 않는다(4단계의 "리뷰가 잡도록 둔 기준을 어겨 리뷰가 잡은 사건").

## 다음

- **04와 06을 여는 세션이 겨냥할 것.** PR #98의 마지막 두 커밋(`ced726a`, `3412ee7`)은 CodeRabbit이 시간당 한도로 리뷰하지 않았고 claude-review만 지적 없이 지났다. 그 커밋이 더한 명세 144·148·149행의 문장(서버 경로 커넥터 키의 역슬래시 규칙, 폴더를 정하는 요청이 연결을 잡기 전에 서버 프로세스 안에서 세우는 차례)과 티켓 04·06의 수용 기준은 셀프 리뷰도 거치지 않았다. 01은 그 문장에 닿지 않았다. 04와 06을 여는 세션이 그 문장을 겨냥해 본다.
- **02, 03, 04, 05를 나란히 돌릴 수 있다.** 01이 병합되면 스키마와 인터페이스가 dev에 있다. 마이그레이션은 02(데이터만)가 더하고, 다른 티켓이 더해야 한다고 판단하면 형제 브랜치와 번호가 겹치는지 먼저 본다. 이 PR의 번호는 0004다.
- **엔티티는 쓰는 티켓이 더한다.** `Source`, `Job`, `Document` 엔티티는 새 칸을 아직 모른다. 그 칸을 읽고 쓰는 티켓(02 이후)이 엔티티와 어댑터를 함께 고친다. `SyncRecord`는 01이 더했다.
- **작업 단위 안에서 얻는 포트가 넷이라는 문장**은 07이 고친다.
- **작업이 지워질 때 동기화 기록을 닫는 일은 11이 맡는다.** `sync_records.job_id`는 `ON DELETE SET NULL`이라 원천 삭제가 대기 중인 동기화 작업을 지워도 기록은 남고 작업 칸만 빈다. 그 기록을 `failed`와 `source_deleted`로 닫는 코드는 아직 없고 명세 269행이 11의 일로 둔다.
- **`skipped` 문서의 `skip_reason`** 보강 CHECK는 02가 건너뜀 사유를 정할 때 같이 본다.
- **첫 비색인 작업을 넣는 티켓(07)이 먼저 고칠 것.** `JobQueue.claim`이 작업 종류를 거르지 않고, 작업 행을 엔티티로 바꾸는 함수가 `document_id`를 UUID로 가정한다. 문서를 가리키지 않는 작업이 처음 들어가면 작업자가 그 행을 색인 작업으로 꺼내 거기서 깨진다.
