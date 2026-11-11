# core 10 수집의 갱신 갈래 일지 · 2026-11-11

티켓 `.scratch/core/issues/10-ingest-updates-group-requeue.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/10-ingest-updates-group-requeue`, 작업은 워크트리 `ingest-updates-group-requeue`에서 했다. 지시문의 이번 요청 범위는 PR과 병합까지다. 준비, 정한 것, 손으로 본 것, 코드 리뷰, 다음을 차례로 둔다. 구현 도중 컨텍스트가 한 번 압축되었다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 08 일지의 "다음", 09 일지의 "다음", 명세의 "수집 API"와 "수집 파이프라인과 작업" 절.
- 지시문대로 `tidy-checkouts`를 먼저 돌고 워크트리에 들어가 브랜치를 땄다.
- 테스트 PostgreSQL은 `compose.test.yml`의 컨테이너를 쓰고 명령마다 `RAG_TEST_DATABASE_URL`과 `PYTHONUTF8=1`을 내보냈다.

## 정한 것

- **같은 내용의 수집은 세 갈래다**(`app/ingest.py`의 `_amend`). 그룹이 다르면 `_update_group`(`updated`), 그룹이 같고 앞선 색인이 실패했으면 `_requeue`(`requeued`), 아니면 `unchanged`(200)다. 내용이 다른 갱신(`_update_content`)도 이제 요청의 그룹을 문서 행에 쓰고, 그룹이 바뀌었으면 같은 `_schedule`로 빠지는 지식베이스를 정리한다.
- **하나의 일정 함수**(`_schedule`): 지식베이스 행을 잠그고, 빠지는 지식베이스에서 문서를 걷고, 복사 칸을 고치고, 작업을 넣는 순서를 한 곳에 모았다. 잠금 순서는 문서 행, 지식베이스 행(ID 순), 작업 행이다. 문서가 드는 지식베이스는 `FOR SHARE`, 빠지는 지식베이스는 `FOR UPDATE`이고, 둘을 합쳐 ID 순으로 하나씩 잠가 다른 수집과 서로를 기다리는 길을 없앴다. 새 문서(`_create`)도 같은 함수를 지난다.
- **빠지는 지식베이스의 정리**: 살아 있는 판(현재와 건설 중)마다 그 문서의 조각과 색인 상태를 지운다. 이를 위해 포트에 `VectorIndex.delete_state`를 더했다. 건설 중인 판이면 전환 검사를 부른다. 그 검사는 새 모듈 `app/version_switch.py`의 `check_version_switch`가 맡고, 본문은 비어 있다(14가 채운다). 08이 비공개 `_check_version_switch`로 두었던 자리를 `index_document.py`와 `ingest.py`가 함께 쓰도록 공개로 옮겼다. 살아 있는 판을 찾는 `live_index_versions`도 `app/live_versions.py`로 옮겼다.
- **`requeued`의 판정**(`_index_failed`): 문서 상태가 `failed`이거나, 문서의 현재 그룹이 드는 지식베이스의 살아 있는 판 가운데 색인 상태가 `failed`인 판이 있다. 물러난 판의 `failed`는 세지 않는다. 세대를 올리고 작업을 넣으며 문서 상태는 작업이 정한다.
- **원본 정리**: 원본 경로를 바꾸지 않는 수집(`requeued`, 그룹만 바뀐 `updated`)은 새 원본(`upload.blob_key`)을 커밋 뒤에 지우고 문서 행은 옛 원본을 가리킨다. 내용이 바뀐 갱신은 옛 원본(`existing.blob_path`)을 지운다.
- **메타데이터 갱신 범위가 명세보다 한 갈래 넓다.** 명세는 메타데이터·갱신일만 달라진 수집을 `unchanged`인 채로 고친다고 적었다. `requeued`와 그룹만 바뀐 `updated`도 같은 `_refresh_metadata`로 제목, 메타데이터, 갱신일을 문서 행과 조각의 복사 칸에 반영한다. 같은 요청이 다른 값을 들고 올 때 한 갈래만 옛 값을 남기면 다음 수집이 또 달라 보이기 때문이다. 명세 문장은 틀리지 않아 고치지 않았다.
- **교차 시험의 이음매**: 티켓이 말한 메모리 안 가짜 포트(`DocumentStore`, `JobQueue`, `BlobStore`)는 만들지 않았다. 09는 그런 포트를 만든 적이 없고(검색 시험은 실제 PostgreSQL 위에서 돈다), 교차 시험이 보려는 것이 잠금과 격리 수준이라 가짜 포트가 재현하지 못하는 쪽이다. 대신 실제 테스트 PostgreSQL에 한 번만 끼어드는 훅을 달았다(`tests/support/interleaving.py`의 `InterruptingEmbedder`, `FailingRunner`, `InterruptingBlobStore`). 티켓의 해당 체크박스는 취소선과 이유로 닫았다.
- **시험 도우미**: `Pipeline.add_group`, `Pipeline.add_knowledge_base`, `RoundTrip.add_group_with_knowledge_base`는 `Catalog` 어댑터로 둘째 그룹과 지식베이스(첫 판 포함)를 만든다.

## 손으로 본 것

- 새 시험 일부는 구현 앞에 썼다. `tests/app/test_ingest_group_requeue.py`는 `NotImplementedError`(그룹을 바꾸는 수집은 티켓 10이 처리한다)로 빨강인 것을 먼저 보고 초록으로 만들었다. 교차 시험과 계약 시험은 쓰는 시점에 이미 구현이 있어 처음부터 초록이었다.
- 처음부터 초록이던 시험은 `tools/mutate.py`의 표(`.scratch/core/probes/ingest_updates_mutations.toml`)로 변이 열다섯을 돌렸다. 빠지는 지식베이스의 조각과 색인 상태를 걷지 않는다(둘), 건설 중인 판의 전환 검사를 부르지 않는다, 복사 칸을 고치지 않는다, `FOR SHARE`로 잠근다, `requeued`가 세대를 올리지 않는다, 새 원본을 지우지 않는다(둘), `failed` 판정 둘, 내용이 바뀐 갱신이 그룹을 쓰지 않는다, 갱신일 변경이 복사 칸에 닿지 않는다, 원본 키가 고정된다, 셋째 단계와 늦은 영구 실패가 세대를 대조하지 않는다(교차 시험 둘)가 그것이다. 모두 기대한 표지와 함께 빨강이다. 코드 리뷰 반영(`copies_changed` 인자를 `_schedule` 안의 판정으로 옮김) 뒤에 원문이 옮겨진 변이 둘(복사 칸, 세대)은 새 원문으로 다시 돌려 빨강을 확인했다.
- 첫 커밋 시도에서 pre-commit의 `check-mutations`가 변이 표 둘이 이 변경에 깨졌다고 알렸다. `first_round_trip_mutations.toml`의 "살아 있는 판 하나에만 쓴다"는 원문이 `live_index_versions`와 함께 `app/live_versions.py`로 옮겨졌고, `ingest_mutations.toml`의 "같은 내용을 건너뛰지 않는다"는 원문의 조건이 `==`에서 `!=`로 뒤집혀(내용이 다른 갱신을 먼저 가르는 순서가 되었다) 새 원문(`if True:`로 바꾸어 같은 내용도 갱신으로 보낸다)으로 고쳤다. 둘 다 다시 돌려 기대한 표지로 빨강임을 보았다.
- 08 변이 표(`parsers_isolation_mutations.toml`)의 원문이 이 변경으로 옮겨졌다. 전환 검사 호출의 이름이 `_check_version_switch`에서 `check_version_switch`로 바뀌어서 3번 변이의 원문을 새 이름으로 고쳤다.
- 한 번 틀린 것: 교차 시험의 첫 초안에서 끼어들 함수 형을 맞추려 `# type: ignore`를 썼다. 원칙 II 위반이라 `Interloper` 형을 두고 `_interrupting` 도우미로 다시 썼다. 갱신·삭제 문에 `fetchall`을 쓰던 계약 시험 도우미는 `_execute`를 따로 두어 고쳤다.

## 코드 리뷰

`/code-review`를 돌렸다. 범위는 base `68aa7e0`, 수정한 파일 10개, 추적하지 않는 새 파일 8개(임시 로그 `.tmp_pytest.log`는 뺐다), 커밋 0개다. 표준 축(sonnet / high)과 명세 축(세션 모델)이 따로 보았고 근거는 내가 코드에서 다시 열어 확인했다. 명세 축은 Critical·Major 없이 Minor 다섯, 표준 축은 Major 하나와 Minor 몇이다.

**고친 것**

- Major(표준 축): 티켓 14가 옛 이름 `index_document._check_version_switch`와 `_live_versions`를 가리켜, 14를 구현할 세션이 없는 심볼을 찾게 된다. 새 이름과 자리(`app/version_switch.py`의 `check_version_switch`, `app/live_versions.py`의 `live_index_versions`)로 고치고, 수집 쪽도 빠지는 지식베이스에서 그 자리를 부른다는 것과 그때 지식베이스 행이 `FOR UPDATE`로 잠겨 있다는 것을 적었다.
- 티켓 11~14가 "가짜 포트 시험"이라고 적은 항목을, 가짜 포트가 만들어지지 않았다는 사실과 10의 끼어들기 훅(`tests/support/interleaving.py`)으로 하라는 안내로 바꾸고, 12의 `Blocked by` 줄에 있던 "09의 메모리 안 가짜 포트" 문구도 고쳤다(받는 쪽에 적는다).
- 모듈 독스트링이 지우는 원본을 "옛 원본, 또는 `unchanged`가 쓴 새 원본"이라고만 적어 `requeued`와 그룹만 바뀐 `updated`를 빠뜨렸다. 네 갈래를 모두 적었다.
- `_lock_knowledge_bases` 독스트링의 "다른 수집과 서로를 기다리지 않는다"는 거짓이다(ID 순은 교착만 막고, 같은 변경의 시험이 기다림을 본다). "교착하지 않는다. 잠금이 풀리길 기다리는 일은 있다"로 고쳤다.
- `_index_failed` 독스트링의 색인 상태가 이 사이에 바뀌지 않는다는 문장은 닫힌 주장이다. 재색인 시작은 문서 행을 잠그지 않고 새 판의 `pending`을 쓴다. "작업 단위가 문서 행을 잠그고 쓰는 색인 상태(작업의 결과)"로 좁혔다.
- `tests/support/interleaving.py` 독스트링의 "끼어들 일은 한 번만"은 `FailingRunner`에 맞지 않아 고쳤다.
- 불리언 플래그 인자(CODING_STANDARDS): `_schedule(..., copies_changed=…)`의 호출 셋이 각자 계산해 넘기던 것을 `_schedule` 안에서 `previous`와 대 보고 정하게 했다(그룹이 바뀌었거나 갱신일이 바뀌었으면 복사 칸을 고친다). 한 줄짜리 `_moved`는 없앴다. 동작이 한 곳 달라진다. 내용이 바뀐 갱신에서 갱신일만 달라져도 옛 조각의 복사 칸이 새 갱신일로 따라간다(옛 조각은 작업이 바꿀 때까지 검색에 보이므로 문서 행과 어긋나지 않는 쪽이 맞다). 전체 시험이 초록이다.
- 명세 축이 짚은 시험 공백 하나: 교차 시험 셋이 변이 표에 없었다. 셋째 단계와 늦은 영구 실패의 세대 대조를 지우는 변이 둘을 표에 더해 빨강을 확인했다.

**PR 직전 리뷰에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `app/ingest.py` `_lock_knowledge_bases`: 지식베이스 행을 ID 순으로 하나씩 잠그므로 다른 수집과 교착하지 않는다. 잠금이 풀리길 기다리는 일은 있다.
- `app/ingest.py` `_index_failed`: 문서 행을 잠근 채라 작업 단위가 문서 행을 잠그고 쓰는 색인 상태(작업의 결과)는 이 사이에 바뀌지 않는다.
- `app/ingest.py` `_schedule`: 그룹이나 갱신일이 바뀌었으면 조각의 복사 칸을 고친다.
- 티켓 14: `ingest`가 빠지는 지식베이스의 건설 중인 판에서 문서의 색인 상태를 지운 직후 `check_version_switch`를 부르고, 그때 그 지식베이스 행은 `FOR UPDATE`로 잠겨 있다.

**남긴 것과 이유**

- Minor: ID 순 잠금(`sorted`)과 양쪽 그룹에 든 지식베이스가 `FOR SHARE`로 남는다는 것은 시험이 직접 재지 못한다. 교착이 없음은 시험으로 보이기 어렵고(교착은 타이밍), 순서를 지우는 변이는 시험이 서도 교착이 드물게만 난다. 설계 문서의 잠금 순서(문서 행, 지식베이스 행, 작업 행)와 코드가 같다는 것을 읽어서 확인했고, 14가 지식베이스 행 잠금을 올릴 때 이 순서가 시험으로 서는지 다시 본다(열린 일).
- Minor: 같은 문서의 작업 둘이 엇갈리는 교차 가운데 먼저 시작한 작업이 성공으로 늦게 끝나는 갈래는 셋째 단계 시험이 간접으로만 덮는다.
- 판단 항목(냄새): `_update_group`과 `_requeue`의 앞 두 줄과 `_schedule` 호출 모양이 같다. `(transaction, document, existing, request_id, now)`가 네 함수에 되풀이된다. `_leave_knowledge_bases`가 `document.id` 말고는 catalog와 index만 만진다. `_lock_knowledge_bases`가 잠그면서 `departing`을 돌려준다(CQS). 시험 도우미 둘이 첫 현재 판이 있는 지식베이스를 만드는 순서를 따로 갖는다. 회고가 다섯 번째 반복인지 센다.
- Nit: `_schedule`과 `_leave_knowledge_bases` 주석의 "걷다"와 "지우다"가 같은 일에 섞인다.

**다시 돌린 명령**

- 반영 뒤 `ruff format`, `ruff check .`, `pyright`가 통과다. 변이 표 둘의 원문 확인(`--check`)이 통과다.
- 반영을 마친 트리에서 `uv run python tools/run_checks.py`가 `test-db`, `zizmor`, `check-ticket`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`, `pytest` 모두 통과다(pytest 373초). 같은 검사를 커밋이 부르는 pre-commit이 한 번 더 돌았다. 첫 시도는 `parallel-checks`가 361초 통과한 뒤 `check-mutations`가 변이 표 둘이 깨졌다고 막았고(위 손으로 본 것), 고친 둘째 시도(283초)는 모든 훅이 통과해 커밋 `edbb6f3`이 섰다.

### PR 직전 리뷰(CodeRabbit CLI는 돌리지 않고 대체 둘)

CodeRabbit CLI는 08에서 앱의 분류기가 코드 diff의 외부 전송이라며 거절했고 그 판단을 사용자가 풀지 않았으므로 이번에는 시도하지 않고 PR 템플릿이 정한 대체 둘을 돌렸다. `origin/main`이 base와 같아(`sibling_overlap.py` 출력) 합칠 것이 없었다. 커밋 `edbb6f3` 위에서 돌았다.

- 보안(`/security-review`, 식별 하위 작업 하나): 발견 없음이라 오탐 거르기 하위 작업은 띄우지 않았다. 따라간 길은 그룹 변경 때의 접근 격리(복사 칸 갱신, 빠지는 지식베이스의 정리, 검색 SQL의 `group_id IN` 조건이 둘째 방어선), 바인딩된 SQL(`delete_state`), 원본 키(UUID 둘만 조합, 사용자 입력 없음)와 지우는 대상(요청이 방금 쓴 새 원본이나 그 문서 자신의 옛 원본뿐), 로그(새 호출 없음), 인증(수집 API는 `admin` 몫)이다.
- 버그·성능(`bug-perf-review`): Critical·Major 없음, Minor 둘. 밀 주장 다섯 모두 근거와 맞았다(코드를 읽어 판정했고 새 시험이 든 다섯 파일 50개를 돌려 통과했다). 교착(지식베이스 `FOR SHARE`에서 `FOR UPDATE`로 올리다 생기는 순환)과 그룹 변경 중 진행 작업의 경합 등 오탐 여섯은 근거와 함께 닫혔다.

**고친 것**

- Minor(티켓 14 11번째 줄): 같은 문단이 "수집 쪽은 지식베이스 행을 `FOR UPDATE`로 잠근 채 부른다"에 이어 "호출 때 문서 행과 작업 행이 잠겨 있고 지식베이스 행은 아직 잠기지 않았다"를 이었다. 뒤 문장은 `index_document`가 부를 때만 맞다. 두 호출처의 잠금 상태를 따로 적고, 재색인 시작이 문서 행을 잠그지 않고 `pending`을 쓰면 `_index_failed` 독스트링이 어긋나는지 14가 같이 보라는 말을 더했다(둘째 밀 주장의 전제가 14에서 깨질 수 있다는 리뷰의 지적을 받는 쪽 티켓에 적었다).

**PR 직전 리뷰에 밀 주장**(이번 반영이 새로 쓴 사실 문장)

- `.scratch/core/issues/14-reindex-version-switch.md`: 수집이 `check_version_switch`를 부를 때는 문서 행과 그 지식베이스 행(`FOR UPDATE`)이 잠겨 있고 작업 행은 아직 잠기지 않았다(`jobs.enqueue`가 뒤에 온다).

**남긴 것과 이유**

- Minor(성능): 그룹이 든 지식베이스 K개와 판 V개에 비례해 `requeued` 판정과 `_schedule`이 DB 왕복을 늘리고(`_index_failed`가 `live_index_versions`로, `_lock_knowledge_bases`가 목록을 되읽고 한 행씩 잠근다), 모두 문서 행 잠금 아래에서 일어난다. 지금 규모(K와 V가 한 자리 수)에서는 틀린 값을 내지 않고, 두 모드를 ID 순으로 섞어 잠가야 하는 지금 구조는 한 행씩일 때만 성립해 묶으려면 순서 논거를 다시 세워야 한다. 그대로 둔다.

## 회고

후보 여덟, 승인 하나(새 항목), 기각 일곱, 넘김 없음이다. 이 세션에서 반영한 것은 없다. 만료할 항목은 `tools/queue_open_rows.py`가 없다고 냈다.

**승인**

- pre-commit이 6분짜리 `parallel-checks`를 돈 뒤에야 1초 안 걸리는 `check-mutations`가 실패를 알린다. 사건: 첫 커밋 시도에서 `parallel-checks`가 361초 통과한 뒤 변이 표 둘이 깨졌다고 막았고 고친 뒤 283초를 다시 돌았다. 08 일지도 같은 사건이다(07의 변이 표 둘). 층: 훅 순서(`.pre-commit-config.yaml`)가 지침보다 높다. 되돌림: PR 하나. 대기열 `precommit-mutations-after-tests`를 2회차로 새로 썼다(더하는 것이라 다섯 번째에 반영한다).

**기각**

- 변이 표 둘이 이 변경으로 깨진 일 자체: `check-mutations`가 커밋에서 알렸다(앞의 승인은 그 알림이 늦게 온 비용이다).
- 40줄을 넘는 heredoc을 훅이 막은 일(변이 표와 일지 작성에서 두 번): 훅이 그 자리에서 막았고 `Write`·`Edit`로 바꿨다.
- 도구 호출 사이의 영어 문장을 훅이 알린 일(두 번): 훅이 그 자리에서 알렸다.
- 줄 길이(E501)를 넘긴 독스트링: 편집 훅이 그 자리에서 알렸다(세 번).
- 티켓 14가 옛 이름을, 티켓 11~14가 만들어지지 않은 가짜 포트를 가리킨 일과 닫힌 주장 둘: `code-review`의 주장 검증 목록이 잡도록 둔 기준이라 리뷰가 제 몫을 했다.
- 편집기 진단이 새 모듈을 못 찾는다며 오래된 오류를 보인 일(여러 번): `ruff check`와 `pyright`가 통과한 것이 판정이었다. 사건이 아니라 편집기의 지연이다.
- 변이 표 첫 초안의 표지 자리표시자(`@@`)로 한 번 돌려 실제 출력을 본 일: 도구가 표지 없음을 알려 주어 의도한 흐름이었다.

## 다음

- core의 프론티어는 11(삭제와 되살림, 묘비)이다. 12(재시도와 오류 번역), 13(임대와 작업자), 14(재색인과 판 전환), 15(조회와 `ingest` 명령), 16(검색 지연 프로브)이 차례로 이어지고, 열린 티켓이 남아 있어 이 PR은 기능 계획의 `**끝:**` 줄을 더하지 않았다.
- 10이 각 티켓에 넘긴 것:
  - 11: 지운 문서를 되살리는 수집은 `_amend`에서 `NotImplementedError("지운 문서를 되살리는 수집은 티켓 11이 처리한다")`로 멈춘다. 되살림의 `restored`와 묘비 행 다시 쓰기는 11이 `_amend` 첫머리에서 갈래를 낸다. 교차 시험은 10의 끼어들기 훅(`tests/support/interleaving.py`)과 실제 테스트 PostgreSQL로 한다.
  - 12·13: 시험은 같은 끼어들기 훅을 쓴다(티켓의 "가짜 포트" 항목을 "교차 시험"으로 고쳐 두었다).
  - 14: `check_version_switch`(`app/version_switch.py`)는 `index_document`(영구 실패와 셋째 단계)와 `ingest`(`_leave_knowledge_bases`, 빠지는 지식베이스의 건설 중인 판)가 부르는 빈 자리다. 수집이 부를 때는 문서 행과 그 지식베이스 행(`FOR UPDATE`)이 잠겨 있고 작업 행은 잠겨 있지 않다. 재색인 시작이 문서 행을 잠그지 않고 `pending`을 쓰면 `_index_failed`의 독스트링(문서 행을 잠그고 쓰는 색인 상태는 판정 사이에 바뀌지 않는다)이 어긋나는지 본다.
- 열린 일:
  - ID 순 잠금과 양쪽 그룹에 든 지식베이스가 `FOR SHARE`로 남는다는 것은 시험이 직접 재지 못한다(교착은 타이밍이라 시험으로 세우기 어렵다). 14가 지식베이스 행 잠금을 올릴 때 이 순서를 다시 본다.
  - 판 수에 비례하는 왕복(`_index_failed`, `_lock_knowledge_bases`, 위 Minor)은 K와 V가 한 자리 수인 지금은 두고, 규모가 커지면 목록을 한 번 읽어 넘기는 쪽으로 고친다.
  - 05와 08에서 넘어온 것(확장자와 내용 불일치 판정, 키 길이 상한, `.env.example`, `request_failed` 이벤트, 토큰 목록의 회수 칸, 파서 자식의 환경 변수, 작업자 메모리 예산)은 여전히 사용자가 정할 것이다.

