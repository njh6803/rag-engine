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
- 반영을 마친 트리에서 `uv run python tools/run_checks.py`가 `test-db`, `zizmor`, `check-ticket`, `lint-imports`, `check-instructions`, `check-type-escapes`, `pyright`, `pyright-linux`, `run-hooks`, `pytest` 모두 통과다(pytest 373초). 같은 검사를 커밋이 부르는 pre-commit이 한 번 더 돌린다(결과는 커밋 뒤에 적는다).

