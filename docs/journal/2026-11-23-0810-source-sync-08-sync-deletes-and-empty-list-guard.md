# source-sync 08: 지움 반영과 빈 목록 보호 · 2026-11-23

source-sync 티켓 07을 닫은 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5). 시작 프롬프트는 `/implement .scratch/source-sync/issues/08-sync-deletes-and-empty-list-guard.md`이고, 브랜치는 `feature/08-sync-deletes-and-empty-list-guard`, 작업은 워크트리 `08-sync-deletes-and-empty-list-guard`에서 했다. 요청 범위는 PR과 병합까지다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 준비

- 읽은 것: 티켓 08, 명세 `.scratch/source-sync/spec.md`의 "동기화의 차례", "수집 정책", "오류 코드", "원천 삭제와 되살리기", "Testing Decisions", 07 일지의 "다음"과 "봇 회차".
- 시험용 PostgreSQL은 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`로 붙여 돌렸다.
- 지시문이 이어받으라 한 일 둘: `SyncLogLine.warning` 불리언 칸을 닫힌 열거로 바꾸는 것(시험과 변이를 먼저), 동기화가 `NOT_FOUND`를 세는 법은 명세가 침묵하므로 임의로 정하지 않고 to-spec 물음으로 두는 것.

## 지은 것

- **삭제 반영.** `sync_source`가 넣기를 끝낸 뒤, 그 원천의 지워지지 않은 문서 가운데 후보에 키가 없는 것을 문서마다 작업 단위 하나에서 임시 삭제하고 `deleted`로 센다. 읽다가 `too_large`가 난 파일은 후보에서 빠진 키(`_Counts.withdrawn`)로 따로 적어 그 키의 문서도 지운다. 잠그고 보니 이미 지워진 문서는 다시 지우지도 세지도 않는다. 작업 행 확인(`hold_attempt`)은 작업 단위의 맨 끝이다.
- **문서 삭제 규칙을 함수로 뗐다.** `app/delete_document.py`의 `delete_locked_document(transaction, document, now)`를 공개 함수로 떼어 수집 API의 삭제와 동기화의 삭제 반영이 같이 쓴다. 동작은 그대로이고 들여쓰기만 한 단계 줄었다.
- **빈 목록 판정.** `_guard_empty_list`. 삭제 반영 직전에 후보(읽다가 빠진 것을 뺀 것)가 0건이고 "빈 목록도 반영"(`apply_empty`)이 꺼져 있고 그 원천에 있는 문서가 하나라도 있으면 아무것도 지우지 않고 실패로 끝낸다. 커넥터가 낸 항목이 0건이면 `source_unreadable`, 항목은 있는데 모두 걸렸으면 `nothing_accepted`다. "있는 문서"는 지워지지 않은 문서와, 원천과 함께 지워졌다는 표시(`deleted_with_source`)가 남은 문서다. 포트에 `has_documents_held_by_source`와 `list_live_keys_of_source`를 더했다.
- **오류 코드.** `nothing_accepted`를 `ErrorCode`와 `SYNC_FAILURE_CODES`에 더했다. 작업 코드는 스물이다.
- **로그 수준 열거.** `SyncLogLine.warning`(불리언)을 `SyncLogLine.level`(`SyncLogLevel.INFO`·`WARNING`)로 바꿨다. 작업자(`worker/processing.py`)가 열거를 로그 수준으로 옮긴다.
- **시험.** 새 파일 셋: `tests/app/test_sync_deletes.py`(21개), `tests/app/test_sync_log_lines.py`(3개), `tests/server/test_sync_deletes_round_trip.py`(실제 서버와 실제 `server_path` 커넥터와 MCP `search`로 5개). 어댑터 시험 둘(`test_catalog_sources.py`)과 오류 코드 목록 시험을 고쳤다. 시험 도우미 `run_sync`에 `max_upload_bytes`, `apply_empty`, `unit_of_work` 인자를 더했다. 변이는 `.scratch/source-sync/probes/sync_mutations.toml`에 열한 개를 더해 33개가 됐다.

## 이 세션이 정한 것

- **빈 목록 판정은 한 자리만 둔다.** 티켓과 명세는 후보 직후와 삭제 반영 직전의 두 자리를 적었다. 후보가 0건이면 앞의 자리와 뒤의 자리 사이에 읽을 파일이 없어 결과가 같고, 후보가 있으면 앞의 자리는 늘 지나간다. 앞의 자리를 지워도 실패 사유, 기록의 개수, 로그, 문서 상태 어느 것도 달라지지 않는다(명세 축이 직접 따졌다). 앞의 자리를 지워 보는 변이는 살아남을 수밖에 없는 동등 변이라 표에 넣지 못한다. 그래서 뒤의 한 자리만 두고 코드와 티켓 문구를 맞췄다. 명세 문구("두 자리", "한 번 더")는 사용자 선택이 담긴 글이라 고치지 않았다. 아래 "다음"에 물음으로 남긴다.
- **`NOT_FOUND`는 정하지 않았다.** 동기화가 파일을 읽을 때의 `NOT_FOUND`는 07의 `_fetch`가 다른 이유와 같이 `source_unreadable` 실패로 세고 문서는 그대로 둔다. 이 티켓은 그 자리를 바꾸지 않았다.

## 겪은 것

- 변이 표 일회용 스크립트의 `write_text`가 Windows에서 줄 끝을 CRLF로 바꿔 파일 전체(439줄)가 `check_line_separators` 시험에서 빨개졌다. 줄 끝의 CR만 지워 되돌렸다. 스크립트로 파일을 쓸 때는 바이트로 쓰거나 줄 끝을 지정해야 한다.
- 새 변이 열 개를 처음 돌렸을 때 아홉 개는 기대한 빨강이었고 "잠그고 보니 이미 지워진 문서를 다시 지우고 센다"는 초록으로 살아남았다. 시험이 목록을 읽은 뒤 잠그기 전의 틈을 만들지 못해서였다. 목록을 읽은 직후에 다른 작업 단위가 끼어들어 문서를 지우게 하는 시험을 더하고 나서야 빨강이 됐다. 이 시험은 작업 단위를 바꿔 끼우는 `_InterruptedUnitOfWork`를 쓴다(`tests/app/test_ingest.py`의 같은 꼴을 따랐다).
- 문서 삭제 규칙을 떼면서 `.scratch/core/probes/delete_restore_mutations.toml`의 변이 넷의 `old`(들여쓰기)가 틀어졌고, 07의 변이 둘(`reject` 호출 줄)도 틀어졌다. `--check`가 잡아 새 코드에 맞췄다.
- 빈 목록 판정이 처음에는 `deleted_at IS NULL`인 문서만 셌다. 명세 축 리뷰가 티켓의 "원천과 함께 지워졌다는 표시가 남은 문서도 있는 문서로 센다"를 빠뜨렸다고 짚었다(아래).

## 셀프 리뷰

`/code-review`를 고정점 `origin/dev`(base `f6eb956`)로 돌렸다. 본 범위는 고친 추적 파일 12개, 미추적 파일 3개, 커밋 0이다. 표준 축은 Sonnet(노력 high), 명세 축은 이 세션의 모델로 돌렸다. 명세 축에는 문서 삭제 전이가 얽혀 전이 교차 (d)를 붙였다.

### 보고(요약)

- **표준 축.** Critical, Major 없음.
  - **Minor.** `GLOSSARY.md`의 "삭제 반영" 풀이가 "목록이 통째로 비면"으로 좁다(이제 모두 걸려도 지우지 않는다).
  - **냄새(판단).** 오류 코드 수 "열아홉→스물"을 네 곳에서 손으로 고친 것(Shotgun Surgery), `_LOG_LEVELS`가 `SyncLogLevel`과 평행한 표인 것(Repeated Switches), `_InterruptedUnitOfWork`가 `begin`을 복사하고 `self._engine`을 한 번 더 대입한 것, 빈 목록 경로에서 `_live_keys`를 연달아 두 번 부르는 것(Nit), `kept`와 `withdrawn`의 이름.
  - **주장 검증.** 옛 값(`열아홉`의 오류 코드 뜻, `.warning`, `warning=`)의 잔존은 없고, 코드의 동작을 서술한 문장은 모두 맞았다.
- **명세 축.**
  - **(a) 빈 목록 판정이 원천과 함께 지워졌다는 표시가 남은 문서를 세지 않는다.** 티켓 08의 두 번째 체크박스와 명세 176행이 요구한다. `list_live_keys_of_source`가 `deleted_at IS NULL`만 보았다. 지금은 그 표시가 선 문서를 만드는 티켓(11, 12)이 아직 없어 드러나지 않지만, 12가 되살린 원천에서 폴더가 안 붙은 채 동기화하면 실패해야 할 것이 성공한다.
  - **(a) `NOT_FOUND` 물음이 이 변경의 어느 파일에도 남지 않았다.** 코드에서 새로 정한 것은 없다.
  - **"두 자리"와 한 자리.** 관찰되는 차이는 없고 글만 어긋난다(위 "정한 것").
  - **(b) 범위 넘침, (c) 틀린 구현 없음.** 티켓 10과 겹치는 파일은 `domain/ports.py` 하나뿐이고 고친 자리가 다르다.
  - **(d) 교차.** 수집 API 삭제와의 겹침은 가져오는 원천에서는 `wrong_source_kind`로 막히고 틈은 `_is_live` 재확인으로 덮는다. 작업 담당 기록을 잃으면 그 문서의 삭제는 롤백된다. 도중에 작업자가 죽으면 다시 도는 시도가 남은 문서부터 지운다(명세 212가 받아들인 동작). 티켓 11이 지움 표시를 보는 자리를 `_delete_one`에 더해야 하고, 12가 표시가 선 문서를 지우려면 `_live_keys`도 바뀌어야 한다.

### 판정과 반영

고친 것(코드가 바뀌는 것은 먼저 실패하는 시험을 쓰고 고쳤다).

- 명세 (a) 첫째. `has_documents_held_by_source`를 포트와 어댑터에 더해 빈 목록 판정이 "지워지지 않은 문서와, 원천과 함께 지워졌다는 표시가 남은 문서"를 센다(완전히 지워져 삭제 기록 행만 남은 문서는 세지 않는다). 시험은 `test_원천과_함께_지워졌다는_표시가_남은_문서도_있는_문서로_세어_빈_폴더를_실패로_닫는다`(동기화)와 `test_빈_목록_판정이_셀_문서는_…`(어댑터, 다섯 상태를 원천마다 비교)이다. 변이 33번이 이 규칙을 깬다. 그 사이 변이 27번의 `old`를 새 가드 코드에 맞췄다. 이 판정에 표시를 서게 하는 시험 데이터는 `UPDATE`로 직접 만들었다. 표시를 서게 하는 코드는 11이, 표시를 지우는 코드는 12가 더한다.
- 표준 Minor. `GLOSSARY.md`의 "삭제 반영" 풀이를 "남는 파일이 하나도 없으면(목록이 통째로 비었거나, 파일이 모두 수집 정책에 걸렸다)"로 넓혔다.
- 표준 냄새. `_InterruptedUnitOfWork`의 `self._engine` 중복 대입을 지웠다. `_live_keys`를 연달아 두 번 부르던 것은 가드가 새 조회로 바뀌며 없어졌다.
- 명세 (a) 둘째. `NOT_FOUND` 물음을 아래 "다음"에 적었다.

남긴 것과 이유.

- `_LOG_LEVELS`가 `SyncLogLevel`과 같은 분기를 적은 평행 표인 것: 열거가 늘면 `KeyError`가 나므로 빨강으로 바로 드러난다. 값이 둘뿐이라 이대로 둔다.
- 오류 코드 수를 네 곳에 적은 것: 07이 정한 방식(머리 설명, 주석, 시험)을 그대로 따랐다. 수를 한곳에서 끌어오는 일은 이 티켓의 범위 밖이다.
- `_InterruptedUnitOfWork`가 `PostgresUnitOfWork.begin`을 복사하고 오류 번역을 빠뜨린 것: `tests/app/test_ingest.py`가 이미 같은 꼴이고, 이 시험은 데이터베이스 오류를 내지 않는다.
- 명세의 "두 자리": 위 "정한 것"과 아래 "다음".
- 변이 `delete_restore_mutations.toml`의 16번("돌아온 건설 중인 판에 전환 검사를 부른다")이 초록으로 살아남는다. 변이가 겨누는 `src/rag_engine/app/ingest.py`와 그 시험 `tests/app/test_delete_restore.py`는 이 변경이 건드리지 않았다. 변이의 편집을 직접 적용해 시험을 돌려도 초록이었다. 이 변경 이전에도 살아남았는지 `origin/dev`의 나무에서 돌려 확인하지는 않았다. 이 PR에서는 고치지 않고 아래 "다음"에 적는다.

밀 주장(PR 직전 리뷰가 겨냥할 새 사실 문장).

- `DocumentStore.has_documents_held_by_source`(`domain/ports.py`): "지워지지 않은 문서와, 원천과 함께 지워졌다는 표시가 남은 문서를 센다. 완전히 지워져 삭제 기록 행만 남은 문서는 세지 않는다."
- `sync_source._guard_empty_list`: "받는 도중의 실패는 이 자리에 닿기 전에 끝난다", "커넥터가 낸 항목이 0건이면 `source_unreadable`이고 항목은 있는데 모두 걸렸으면 `nothing_accepted`다."
- `sync_source._apply_deletions`: "읽지 못해 실패로 센 파일은 후보에 있으므로 지우지 않고, 읽다가 `too_large`가 난 파일은 후보에서 빠졌으므로 그 키의 문서를 지운다."
- `delete_locked_document`: "작업 행은 이 함수 뒤에 잠근다(잠금 순서)."
- `GLOSSARY.md`의 "삭제 반영" 풀이.

다시 돌린 명령(반영 뒤): `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`가 통과했다. 새 시험 둘과 어댑터 시험을 돌려 통과했고, 변이 27번과 33번을 따로 돌려 기대한 빨강을 확인했다. 커밋 직전 pre-commit의 검사 러너가 전체 시험을 다시 돌린다.

## 검증

- 변이 표 33개 가운데 열한 개(23~33)가 이 티켓의 것이다. 23~32번을 한 번에 돌려 아홉 개는 기대한 빨강이었고 30번만 초록이어서 시험을 더했고, 30번이 빨강이 된 것을 확인했다. 07의 기존 변이 1~22번도 새 코드에 맞춰 한 번에 돌려 기대대로였다. 반영 뒤 27번과 33번은 따로 돌려 빨강이었고, 표 전체를 한 번에 다시 돌리지는 않았다.
- `delete_restore_mutations.toml` 20개를 돌려 열아홉 개는 기대대로이고 16번만 어긋났다(위 "남긴 것").
- 전체 검사 러너(`tools/run_checks.py`)는 `pytest` 단계만 781초가 걸렸다. 반영 전의 값이고 이 PC에서 xdist로 돈 시간이다. CI의 `python` 잡 제한은 15분이고 07 일지에 적힌 앞 성공 실행은 13분 7초였다. 시험을 스물 남짓 더했으므로 CI에서 본 시간을 PR 뒤에 적는다.

## 회고

- 일회용 스크립트가 Windows에서 줄 끝을 바꾼 것은 이 저장소에서 처음 본 사건이 아니다(`check_line_separators`가 이미 잡는 검사다). 새 규칙은 더하지 않았다.
- 변이 도구가 "빨강이어야 한다"를 확인하자 시험이 못 만든 장면(목록을 읽은 뒤 잠그기 전의 경쟁)이 드러났다. 변이를 시험 뒤에 쓰는 순서가 맞았다.
- 명세 축이 코드와 티켓을 대 보고 빠진 요구를 잡았다. 표시 칸이 코드에 아직 읽히지 않는다는 이유로 내가 뺀 것이 틀렸다. 칸이 표에는 이미 있었다.

## 다음

- 08은 끝났다. 09(`reread` 뜻과 실패한 문서 다시 넣기)와 10(일정)이 열려 있다.
- 11이 알아야 할 것: `_delete_one`에 지움 표시를 보는 자리가 필요하다(명세 187행). 표시가 선 원천의 동기화는 `source_deleted`로 끝난다. `_guard_empty_list`의 `has_documents_held_by_source`가 이미 표시 문서를 센다.
- 12가 알아야 할 것: 동기화의 삭제 반영이 "이미 지워져 있으면서 표시가 남은 문서"를 만나면 표시를 지우고 지운 시각을 그 순간으로 고쳐야 한다(명세 188, 286행. 티켓 12의 세 번째 항목). 이 티켓의 `_apply_deletions`는 `list_live_keys_of_source`만 읽으므로 그런 문서를 보지 못한다. 12가 이 자리를 넓혀야 하고, 이 티켓이 둔 "표시 문서도 있는 문서로 센다"의 시험은 12의 "되살린 원천에서 폴더가 안 붙은 채 동기화한다" 장면에서 이어서 본다.
- to-spec으로 넘길 것:
  - 동기화가 파일을 읽을 때 `NOT_FOUND`를 어떻게 셀지(07 일지의 같은 항목과 같다). 지금은 `source_unreadable` 실패로 세고 문서는 그대로 두며, 다음 동기화의 삭제 반영이 목록에서 사라진 그 문서를 지운다.
  - 빈 목록 판정이 후보 직후와 삭제 반영 직전의 두 자리라는 명세 문구(176, 178, 188행)와 티켓 08 문구. 구현은 뒤의 한 자리만 둔다(위 "정한 것"). 문구를 한 자리로 고칠지, 앞의 자리를 되살릴지 정한다.
- 하네스로 따로 할 일: `.scratch/core/probes/delete_restore_mutations.toml`의 16번이 초록으로 살아남는다(위 "남긴 것"). 이 PR 이전부터인지, 시험이나 `add_building_version`의 변화 때문인지 `origin/dev`에서 가려야 한다. CI `python` 잡의 15분 제한은 07 일지의 같은 항목이 이어진다.
