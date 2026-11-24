# source-sync 13: 문서 되살리기 · 2026-11-24

source-sync 티켓 11을 병합한 세션이 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5). 시작 프롬프트는 `/implement .scratch/source-sync/issues/13-restore-documents.md`이고, 브랜치는 `feature/13-restore-documents`, 작업은 워크트리 `13-restore-documents`에서 했다. 요청 범위는 PR과 병합까지다. 나란히 여는 티켓 12(원천 되살리기)는 다른 세션이 맡았다. 이 세션의 대화는 구현 도중 한 번 요약으로 줄었다.

## 준비

- 읽은 것: 티켓 13, 명세 `.scratch/source-sync/spec.md`의 "문서 되살리기"와 "원천 삭제와 되살리기"의 잠금 순서, "관리 API", "Testing Decisions", ADR 0021, 11 일지의 "다음".
- 지시문이 시킨 순서: 묶음의 둘째 세션이라 `tidy-checkouts`는 돌지 않았다. `EnterWorktree`로 새 워크트리에 들어가 브랜치를 바꿨다.
- 시험용 PostgreSQL은 `RAG_TEST_DATABASE_URL=postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`로 붙여 돌렸다.

## 지은 것

- **공용 단계 `app/restore_chunks.py`.** 수집 API의 같은 키 되살림이 쓰던 `ingest._restore_chunks`의 조각 되돌리기를 뽑아 관리 API의 되살리기와 수집 API가 같은 길을 쓰게 했다. 문서가 든 지식베이스의 살아 있는 판(현재 판과 건설 중인 판)마다, 삭제 보관함에서 내용 해시가 문서 해시와 같은 조각을 검색 표로 되돌린다. 되돌린 판에는 `indexed`를 쓰고, 되돌리지 못한 판이 있으면 색인 작업을 넣는다. 그 판이 건설 중이 아니면 `pending`도 쓴다. 건너뜀 문서는 조각이 없어서 작업을 넣지 않고 대상 판마다 조각 0개인 `indexed`만 다시 쓴다.
- **유스케이스 `app/restore_document.py`.** 문서를 읽어 없거나 정리된 문서면 404 `document_not_found`, 원천 행을 공유 잠금으로 잡아 지운 원천이면 409 `source_deleted`, 밀어 넣는 원천이 아니면 409 `wrong_source_kind`, 문서 행을 잠근 뒤 지워지지 않은 문서면 409 `document_not_deleted`다. 통과하면 지운 시각과 `deleted_with_source`를 풀고 세대를 하나 올린 뒤 `restore_chunks`를 부른다.
- **관리 API `POST /api/v1/admin/documents/{id}/restore`.** 새 라우터 `server/admin_document_api.py`에 두었다. 200이고 응답은 `document`(문서 보고)와 `job_id`(작업을 넣었으면 식별자, 아니면 `null`)다. reader 토큰은 403이다.
- **오류 코드 `document_not_deleted`.** Problem Details에만 쓰는 코드이고 409다. 코드 집합은 스물둘에서 스물셋이 되었다. 마이그레이션은 없고 새 경로와 새 응답 칸이라 계약 버전은 `v1` 그대로다.
- **수집 API의 되살림.** `ingest._restore_chunks`가 `restore_chunks`를 부르도록 줄었다. 건너뜀 문서의 같은 키 되살림은 이제 작업 없이 색인 상태만 다시 쓴다(02 일지의 "13이 건너뜀 문서를 만난다" 항목이 정한 길이다).
- **시험.** 앱 시험 14개(`tests/app/test_restore_document.py`)와 서버 왕복 7개(`tests/server/test_restore_document_round_trip.py`, 실제 서버와 실제 작업자, 공식 MCP 클라이언트의 `search`)를 더했다. 오류 코드 시험은 스물셋으로 고쳤다. 변이는 `.scratch/source-sync/probes/restore_document_mutations.toml`에 아홉 개를 넣었다.

## 이 세션이 정한 것

- **건너뜀 갈래를 공용 단계에 두었다.** 명세가 12의 "원천 되살리기 작업"과 13이 같은 일을 하는 자리로 적은 것이어서 한 함수에 두면 12가 같은 함수를 부른다. 12가 병합되기 전에는 둘의 글자가 겹칠 수 있고, 나중에 병합하는 쪽이 푼다.
- **건설 중인 판에는 `pending`을 쓰지 않는다.** 건설 중인 판에 `pending`을 쓰면 그 문서의 작업이 끝날 때까지 판이 전환되지 않을 수 있다(명세 "재색인 시작" 항목). 되돌릴 조각이 없는 건설 중인 판에는 작업만 넣는다. 건설 중인 판에 `indexed`를 쓸 때도 전환 검사는 부르지 않는다. 그 판에 색인 상태가 없던 문서의 `indexed` 한 행은 전환 조건을 새로 채우지 못하고, 검사가 지식베이스 행을 `FOR UPDATE`로 올려 잠가야 해서 같은 지식베이스의 되살림끼리 서로 기다릴 수 있기 때문이다.
- **작업은 판마다가 아니라 한 번에 하나만 넣는다.** 되돌리지 못한 판이 둘 이상이어도 `jobs.enqueue`는 한 번 부르고, 낸 값은 그 작업의 식별자다.
- **정리 작업과의 겹침은 문서 행 잠금으로 푼다.** 정리 작업(티켓 14)은 아직 코드가 없다. 명세대로 문서 하나를 문서 행을 잠근 작업 단위 하나에서 지우도록 14가 짓는다는 전제로 독스트링에 적었다.

## 겪은 것

- **원칙 I(테스트 먼저)를 지키지 못했다.** 11과 같은 모양이다. 유스케이스와 라우터를 거의 다 쓴 뒤에 왕복 시험을 썼다. 변이 아홉 개로 시험이 빨개지는 자리를 하나씩 확인해 메웠다(아래 "검증").
- 시험 첫 실행에서 넷이 빨갰다. `index_document`를 직접 부르면 작업 행이 `running`으로 남는데 `queued`가 없다는 단언으로 썼기 때문이다. 단언을 `["running", "queued"]`로 고쳤다.
- 건너뜀 문서의 수집 시험에 쓸데없는 해시 조작을 넣었다가 지웠다. 시험 본문이 고정 바이트라 해시가 이미 같았다.
- 한글 줄이 100칸을 넘어 `tools/rewrap_comments.py`와 `ruff format`으로 감았다.
- 변이 표의 `expect_output` 표지가 어긋났다(4번, 8번). 시험을 튜플 비교로 바꾸고 표지를 pytest가 값을 견주어 찍는 차이 줄로 바꿨다.
- 워크트리 가드가 `$(...)`나 `;`로 묶은 git 호출을 거부해서 git은 단독 명령으로 나눴다.
- 파이썬 `write_text`로 `ingest.py`를 쓰자 줄 끝이 CRLF로 바뀌었다. `sed -i 's/\r$//'`로 되돌리고 `tools/check_line_separators.py`가 0으로 끝나는 것을 봤다.
- **첫 커밋 시도가 변이 표 검사(`tools/mutate.py --staged`)에서 막혔다.** 조각 되돌리기를 `ingest.py`에서 `restore_chunks.py`로 옮기자 다른 표(`.scratch/core/probes/delete_restore_mutations.toml`)의 변이 셋(보관 조각 지우기, 건설 중인 판의 `pending`, 건설 중인 판의 전환 검사)이 `ingest.py`에서 찾던 원문이 사라졌다. 세 변이의 대상 파일과 원문을 `restore_chunks.py`의 모양에 맞추고(셋째는 `check_version_switch`의 import를 같이 더했다) 하나씩 다시 돌렸다.
- **고친 변이 하나(16번)가 처음에는 초록이었다.** 시험 `test_건설_중인_판에_보관_조각이_돌아오면_indexed를_쓰고_전환_검사는_부르지_않는다`가 `ingest` 모듈의 `check_version_switch`만 가로채고 있었다. 호출이 `restore_chunks`로 옮겨 갔으니 그 모듈도 가로채게 했다(`raising=False`. 이 모듈에는 평소 그 이름이 없다). 그래도 초록이어서 `restore_chunks` 안에서 `versions`와 `restored`를 찍어 보니 되살릴 때 살아 있는 판이 현재 판 하나뿐이었다. 시험 도우미 `keep_pending`의 설명대로 `pending` 문서가 없는 건설 중인 판은 색인과 삭제를 만나면 곧바로 현재 판이 되어, 시험이 이름이 말하는 장면(건설 중인 판에 돌아온다)을 한 번도 만들지 못했다. 이 변경 전의 소스에서는 돌려 보지 않았으나, 되살리기 앞의 흐름은 이 변경이 닿지 않은 자리라 앞서부터 그랬을 것이다. 시험에 `await pipeline.keep_pending(building)`을 더하자 변이 16이 기대한 `Left contains one more item: IndexVersion(`으로 빨개졌다.
- 첫 커밋 시도의 pytest(20분)도 두 개가 빨갰다. `test_admin_pull_source_stuck_calls.py`의 시간 상한 단언 하나(앞선 전체 검사와 같은 파일)와 `tests/contract/test_search_tool.py::test_현재_판이_없는_지식베이스는_빈_결과를_낸다`(MCP 클라이언트 연결의 `httpcore` 읽기 도중 예외)다. 계약 시험 파일은 단독으로 5개 모두 통과했다.

## 셀프 리뷰

`/code-review`를 base `4d0b692`(커밋 없이 작업 폴더의 변경만, 추적 파일 8개와 미추적 7개)로 돌렸다. 표준 축(sonnet·high)은 하드 위반 없이 판단 항목 여섯과 냄새 둘을, 명세 축은 빠진 것 없이 닫힌 문장 하나와 거절 순서와 교차 몇을 냈다.

- **고친 것.**
  - `restore_document.py` 머리 설명이 "정리 작업은 문서 하나를 … 지우므로 끼어들 틈이 없고"를 현재형 사실로 적었으나 정리 작업(티켓 14)은 아직 코드가 없다. "명세는 정리 작업이 … 지우도록 정한다"로 고치고, 이 문서 행 잠금과 `deleted_at`·`purged_at` 재확인이 그 약속의 이쪽 절반이라고 적었다.
  - `ingest.py` 머리 설명의 되살림 문단이 "되돌릴 조각이 없는 대상 판이 있을 때만 작업을 넣는다"로만 적혀, 건너뜀 문서가 조각이 없어도 작업 없이 색인 상태만 다시 쓰는 갈래를 놓쳤다. 한 줄을 더했다.
  - `server/ingest_models.py`의 `IngestResponse` 설명이 "작업이 없는 경우는 `unchanged`와 보관 조각이 대상 판을 모두 채운 `restored`다"로 닫혀 있어, 이 변경으로 건너뜀 문서의 `restored`도 작업이 없게 되면서 거짓이 되었다. 셋째 경우를 더했다(명세 축이 계약 변경이 거짓으로 만든 문장으로 찾았다).
  - `restore_chunks.py`의 "건너뜀은 같은 내용을 다시 파싱해도 같은 결과이므로"는 반례가 있다. 명세 "건너뜀"(262행)은 글자 없음 문서를 파서 버전이 지금과 다르면 재색인이 다시 파싱한다고 적는다. 이유 문장을 지우고 명세 "문서 되살리기"가 정한 길이라고만 적고, 그 결과(재색인 도중에 되살린 건너뜀 문서는 그 재색인의 다시 보기를 받지 않고 다음 재색인이 본다)를 적었다.
  - 거절 순서를 명세가 정하지 않았다. 코드는 없는 문서, 지운 원천, 가져오는 원천, 지워지지 않은 문서 순으로 찾아 먼저 걸린 것을 낸다(지운 원천의 지워지지 않은 문서는 `source_deleted`다). `restore_document.py` 머리 설명에 이 순서와 "명세는 순서를 정하지 않았다"를 적었다.
  - 변이 표 머리 설명이 "공유 잠금과 지움 표시 확인을 하나씩 깨뜨린다"로 적었으나 변이는 둘을 함께 뺐다. 지움 표시는 보되 잠금만 빼는 변이(4번)를 더하고 설명을 고쳤다. 새 변이는 `test_원천을_지우는_요청이_먼저_잡은_원천이면…` 하나에서 `DID NOT RAISE`로 빨개졌다.
  - 문서 행을 잠근 뒤 `purged_at`을 다시 보는 길(`restore_document.py`)을 밟는 시험도, 그것을 깨뜨리는 변이도 없었다. 시험 `test_문서_행을_잡은_작업이_문서를_정리하면_기다린_되살리기는_404로_끝난다`(다른 작업 단위가 문서 행을 잡고 `purged_at`을 쓰는 동안 온 되살리기가 기다렸다가 404)와 변이 5번을 더했다. 변이는 그 시험 하나에서 빨개졌다.
  - `admin_document_api.py`에 되살린 작업 단위가 끝난 뒤 문서를 읽는다는 주석을 달았다(처음 쓴 문장은 아래 "PR 직전 리뷰"가 바로잡았다).
  - 저장소 루트의 빈 파일 `sep13.out`을 지웠다.
- **넘긴 것(받는 쪽에 적었다).** 되살리는 요청이 문서를 읽은 뒤 원천 행과 문서 행을 차례로 잠그는 사이에 완전히 지우는 묶음이 그 행을 지우면 `lock_live_source`와 `documents.lock`이 `RuntimeError`를 내 500이 된다. 행을 물리 삭제하는 쪽이 티켓 14이므로 그 티켓(`14-daily-cleanup.md`)의 수용 기준에 "500이 아니라 404 `document_not_found`로 끝나게 고치고 실제 정리 작업과 겹치는 시험을 둔다"를 더했다. 14는 13을 막는 선행 조건(Blocked by)으로 걸어 둔 티켓이라 받는 쪽이 이 일지를 읽는다.
- **남긴 것과 이유.**
  - 수집 API의 같은 키 되살림(`ingest._restore`)이 `deleted_with_source`를 풀지 않는 것(표준 축이 Duplicated Code로 냈다). 명세 "원천 삭제와 되살리기"의 원천 되살리기 쪽 결정(표시가 남은 문서와 같은 키가 들어오면 되살리고 표시를 지운다)이고 티켓 12의 14번째 줄이 맡는다. 11 일지가 12로 넘긴 것과 같다. 13은 관리 API의 되살리기만 고쳤다.
  - `ingest._restore_chunks`가 `replace` 뒤 `restore_chunks`를 부르는 얇은 감싸개이고 이름이 모듈 함수와 같다(Middle Man, Mysterious Name). 이름을 바꾸면 이 PR에서 `ingest.py`의 호출부가 더 늘어 12와 글자가 겹칠 수 있고, 판단 항목이라 남겼다.
  - 되살리기 둘이 동시에 오는 시험이 없다(순차 시험만). 코드는 문서 행 잠금 뒤 `deleted_at`을 다시 보고, 그 재확인은 순차 시험(변이 2번이 빨개진다)이 판정한다.
  - 색인 작업의 세대 대조와 되살리기가 겹치는 시험이 없다. 되살릴 때 세대를 하나 올리는 것은 변이 6번이 지키고, 옛 세대의 작업이 쓰지 못하는 것은 색인 작업의 시험이 맡는다.
  - 건설 중인 판에서 건너뜀 문서를 되살리면 재색인의 다시 보기를 받지 않는 것. 명세 "문서 되살리기" 295행이 정한 동작이라 고치지 않는다.
- **다시 돌린 명령.** `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, `uv run python tools/check_type_escapes.py`를 모두 단독으로 돌려 0으로 끝났다. 앱 시험은 15개가 모두 초록이다. 결과의 나머지는 아래 "검증".

## PR 직전 리뷰

- **보안 리뷰(`/security-review`).** 확신 8 이상인 취약점이 없었다. 새 `POST` 경로가 인증 미들웨어 안에 있고(역할은 `admin`과 `reader` 둘이며 `reader`는 `/mcp` 밖에서 403이다), 입력은 `UUID`로 검증되는 경로 값 하나이며, 새로 문자열에 끼는 사용자 입력과 파일·서브프로세스 접근이 없고, 검색의 그룹 제한은 그대로임을 확인했다. 미커밋 변경이라 `git diff` 입력이 비어 있어 새 코드를 직접 읽고 판정했다(하위 작업은 나누지 않았다).
- **CodeRabbit CLI(`coderabbit review --agent --include-untracked --base origin/dev`, 0.7.5).** 지적 하나가 나왔고 오탐이다. "해시가 다른 보관 조각이 복원되어 판이 `indexed`로 기록될 수 있다"는 지적인데, 어댑터 `restore_archived_chunks`가 `archived.c.source_content_hash == document.content_hash`로 이미 거른다(`vector_index.py` 369줄). 다른 해시의 조각은 복원되지 않아 그 판은 되돌리지 못한 판이 되고 작업이 들어간다.
- **밀어 본 새 문장(에이전트가 직접 대 봤다).** 맞은 것: 거절 순서 문장, 건너뜀 문단(재색인은 지운 문서에 작업을 넣지 않으므로 도중에 되살린 건너뜀 문서는 그 재색인의 다시 보기를 받지 않는다), `ingest.py`와 `IngestResponse` 설명.
  - **고친 것(Major).** `admin_document_api.py`의 주석 "다시 지우면 이 읽기가 404일 수 있다"는 틀렸다. `get_document_report`는 `documents.get`으로 읽고 `deleted_at`을 거르지 않아, 되살린 뒤 다시 지워져도 응답은 404가 아니라 `deleted_at`이 찬 문서로 온다. 404는 행이 없을 때만 난다. 주석을 "응답의 문서가 이미 다시 지워진 모양일 수 있다"로 고쳤다. 내가 근거를 열지 않고 쓴 문장이다(`code-review` 6단계 1의 "고치며 새로 쓰는 사실 문장" 사건).
  - **고친 것(Minor, Nit).** `restore_document.py`의 "정리 작업은 문서 하나를 … 작업 단위 하나에서 지운다"는 티켓 14가 50건씩 묶어 한 작업 단위에서 문서 행을 잠근다는 것과 달랐다. "문서 행을 잠근 작업 단위에서 지운다(50건씩 묶는다)"로 고치고, 행이 이미 사라진 뒤에 만나는 경우는 티켓 14가 맡는다고 한 줄을 더했다. 명세 296줄에도 같은 느슨한 문장("문서 하나는 … 작업 단위 하나에서 지우므로")이 있다. 명세는 이 PR이 고치지 않고, 티켓 14의 수용 기준이 정확한 모양을 적는다.

## PR 봇 회차

- **CodeRabbit 첫 회차(커밋 `fc0eb34`).** Minor 하나. `restore_chunks`가 그룹의 지식베이스를 나열해 잠근 뒤 `live_index_versions`로 그룹의 지식베이스를 다시 읽어, 그 사이에 그룹에 붙은 지식베이스의 판(잠기지 않았다)이 대상에 들 수 있다는 지적이다. 맞다. 같은 모양이 `dev`의 옛 `ingest._restore_chunks`에도 있었다(회귀는 아니다). `job_failure._lock_knowledge_bases`는 잠근 행에서 판을 읽는다. 고쳤다: `lock_knowledge_bases`가 낸 행마다 `list_live_index_versions`로 판을 읽고, 더 쓰지 않는 `live_index_versions` import를 지웠다.
  - 시험을 먼저 썼다(`test_잠근_뒤에_그룹에_붙은_지식베이스의_판에는_상태도_작업도_쓰지_않는다`). `PostgresCatalog.lock_knowledge_bases`를 바꿔 치는 시험으로, 진짜 잠금이 끝난 바로 뒤에 새 지식베이스를 그룹에 붙인다. 고치기 전에는 작업이 들어가(`job_id`가 `None`이 아니다) 빨갰고, 고친 뒤 초록이다.
  - 변이 12번을 더했다(잠근 행이 아니라 그룹 연결에서 읽는다). 빨강이다. 변이 16번은 import 줄이 사라져 원문의 기준 줄을 `from rag_engine.domain.ports import LockMode, Transaction`으로 옮겼고 다시 돌려 기대대로 빨갰다.
  - `claude-review`는 지적이 없었다.

## 검증

- 손으로 치는 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, `uv run python tools/check_type_escapes.py`가 모두 0으로 끝났다(셀프 리뷰 반영 뒤 다시 돌렸다).
- 검사 러너(`uv run python tools/run_checks.py`): `test-db`, `check-notes`, `lint-imports`, `check-ticket`, `zizmor`, `check-instructions`, `check-type-escapes`, `pyright-linux`, `pyright`, `run-hooks`가 통과했다. `pytest`는 5778개 통과, 5개 실패(15분 23초)였다. 실패는 모두 `tests/server/test_admin_pull_source_stuck_calls.py`의 시간 상한 단언이다(`assert again_elapsed < PROMPT_SECONDS`, 1.64초가 1.0초 상한을 넘었다). 이 변경이 닿지 않는 가져오는 원천 시험이고, 그 파일만 단독으로 다시 돌리면 13개가 모두 통과했다(47초). 부하에서만 빨간 시간 시험이라 사용자가 2026-11-15에 다시 열지 않기로 한 종류의 새 사례로 일지에만 적고 새 항목은 쓰지 않는다.
- 첫 커밋 시도의 pre-commit 러너: pytest가 5781개 통과, 2개 실패(19분 51초)였다. 실패는 앞선 전체 검사에서 본 시간 상한 단언(`test_admin_pull_source_stuck_calls.py`, 앞 실행과 다른 시험 하나)과 계약 시험의 연결 예외 하나다. 둘 다 부하에서만 빨간 종류로 보인다. 시간 시험 파일은 앞 실행 뒤 단독으로 13개가, 계약 시험 파일은 단독으로 5개가 통과했다. 커밋은 이 실패가 아니라 변이 표 검사에서 막혔다. 고친 변이 표의 번호 13, 15, 16을 단독으로 돌려 모두 기대한 시험에서 기대한 까닭으로 빨개졌다.
- 둘째 커밋 시도는 pytest가 5782개 통과, 1개 실패(14분 1초)였다. 같은 파일 `test_admin_pull_source_stuck_calls.py`의 시간 상한 단언이다(`assert 1.42 < 1.0`). 같은 시험의 단독 실행은 요청 하나가 42ms였다. 셋째 시도에서 pre-commit이 모두 통과해 커밋 `3c4705f`이 만들어졌다(pytest 947초). 전체 pytest를 돌린 네 번(러너 한 번, 커밋 시도 셋) 가운데 셋이 빨갰고, 빨간 시험은 이 변경이 닿지 않은 것이며 병렬로 도는 다른 세션의 시험과 부하가 겹친 것으로 보인다(재 보지는 않았다).
- 변이(`.scratch/source-sync/probes/restore_document_mutations.toml`, 열한 개)가 모두 기대한 시험에서 기대한 까닭으로 빨개졌다. 처음 아홉은 구현 직후에, 4번(잠금만 뺀다)과 5번(정리됐는지 다시 보지 않는다)은 셀프 리뷰 반영 뒤에 각각 단독으로 돌려 확인했다. 아홉은 반영 전의 소스에서 돌렸고, 반영이 닿은 것은 독스트링과 주석, 시험 하나, 변이 표뿐이다.
- 봇 회차 반영 뒤: 변이 열두 개(12번 추가)와 다른 표의 16번이 기대대로 빨갰고, 앱 시험 `test_restore_document.py`와 `test_delete_restore.py` 28개가 초록이며, `ruff check`와 `pyright`가 0이다. 봇 회차 커밋의 첫 pre-commit 시도는 pytest가 5778개 통과, 6개 실패(18분 27초)였다. 실패는 모두 이 변경이 닿지 않는 시험이다: `test_admin_pull_source_stuck_calls.py` 넷, `test_admin_pull_source_locking.py` 하나(시간 상한), `test_serve_command.py` 하나(`serve가 30초 안에 뜨지 않았다`). 셋 파일을 단독으로 돌리면 19개가 모두 통과했다(74초). 앞 시도들과 같은 부하 종류로 보여 사례로만 적고 다시 커밋했다. 둘째 시도는 pytest가 5777개 통과, 7개 실패(26분 34초)였다. `test_admin_pull_source_stuck_calls.py` 다섯(시간 상한, 1.17~2.48초가 1.0초 상한을 넘었다)과 `tests/contract/test_search_complete.py` 둘(`httpx2.ReadTimeout`)이고, 두 파일을 단독으로 돌리면 32개가 모두 통과했다(218초). 다시 커밋한다.
- 새 시험: 앱 시험 16개(봇 회차에서 하나 더했다), 서버 왕복 7개. 테스트 PostgreSQL은 `compose.test.yml`의 컨테이너로 돌렸다.

## 회고

후보 일곱, 승인 하나(회차를 더한 것), 기각 여섯, 넘김 없음.

- **승인(회차로 센다).** 시험을 구현 뒤에 썼다(서버 왕복 시험 7개와 앱 시험을 구현 코드가 거의 다 선 뒤에 써서 처음부터 초록이었고, 변이 아홉 개로 빨강을 확인했다고 위 "겪은 것"이 스스로 적었다). 열린 항목 `surface-tests-after-implementation`의 처방이 막는 사건이라 그 항목의 승인 줄에 6회차를 더했다(5회차에서 6회차가 되었다). 층은 지침(스킬 `implement`)이고 이 항목은 이미 회차 5 이상이라 chore 배치 조건이다. 이 PR에서는 반영하지 않는다.
- **기각.**
  - 워크트리 가드가 `$(...)`와 `;`로 묶은 git 호출을 거부했다: 가드가 그 자리에서 알렸고 git을 단독 명령으로 나누어 지나갔다.
  - 파이썬 `write_text`가 `ingest.py`의 줄 끝을 CRLF로 바꿨다: `tools/check_line_separators.py`가 그 자리에서 잡았다.
  - 한글 줄이 100칸을 넘었다: 편집 훅이 줄 길이(E501)를 알렸고 `tools/rewrap_comments.py`로 감았다.
  - 변이 표의 `expect_output` 표지가 pytest 단언 풀이와 달라 도구가 거절했다: 도구가 그 자리에서 알렸다.
  - 코드를 옮기자 다른 표의 변이 셋이 원문을 잃어 pre-commit이 막았고, 그 가운데 하나(16번)는 시험이 건설 중인 판을 한 번도 만들지 못해 초록이었다: 첫째는 훅(`tools/mutate.py --staged`)이 그 자리에서 막았고, 둘째는 변이 도구가 "어긋남"으로 알렸다. 사건은 하나이고 둘 다 도구가 잡았다.
  - 독스트링이 아직 코드가 없는 정리 작업을 현재형 사실로 적고, 계약 변경이 거짓으로 만든 문장(`IngestResponse` 설명)을 놓쳤다: 셀프 리뷰 두 축이 잡았다. 이 기준은 `code-review`의 두 브리프가 가진 주장 검증 목록(미래형과 계약 변경이 거짓으로 만드는 문장의 grep)이 이미 다루므로 리뷰가 제 몫을 한 것이다. `/code-review`의 회차 셈에서 뺀다.

## 다음

- 13은 끝났다. 열린 것은 12(원천 되살리기, 다른 세션이 워크트리 `12-restore-sources`에서 하는 중), 14(정리 작업, 12와 13이 끝나야 한다), 15(단독 설치의 원천 폴더)다.
- **12와 13이 겹친다. 나중에 병합하는 쪽이 푼다.** `tools/sibling_overlap.py`가 12 워크트리와 함께 고친 파일로 `ingest.py`, `restore_chunks.py`, `domain/errors.py`, `server/app.py`, `server/problems.py`, `tests/domain/test_errors.py`를 냈다. 가장 큰 것은 `app/restore_chunks.py`다. 양쪽이 같은 이름의 파일을 새로 만들어 추가와 추가가 부딪친다. 핵심(보관 조각 되돌리기, 판마다 `indexed`, 되돌리지 못한 판에 작업과 `pending`, 건설 중인 판에는 `pending`을 쓰지 않는 것)은 거의 같고 시그니처도 `restore_chunks(transaction, document, request_id, now) -> UUID | None`로 같다. 다른 곳은 둘이다. 13은 `restore_chunks` 안에서 지식베이스 행을 `FOR SHARE`로 잠그고 건너뜀 문서를 같은 함수의 첫 갈래로 처리한다. 12는 지식베이스 잠금을 `_lock_knowledge_bases_of`로 따로 두고 건너뜀 처리를 `restore_locked_document`로 나눈다. 오류 코드는 13이 `document_not_deleted`를 더해 `PROBLEM_ERROR_CODES`가 스물셋이 되었고, 12도 코드를 더하면 머리 설명의 수와 시험(`SPEC_PROBLEM_CODES`)이 부딪친다.
- 14가 알아야 할 것: `restore_document`가 문서 행을 잠근 뒤 `purged_at`을 다시 보므로 정리 작업이 먼저 지웠으면 404다(시험과 변이 5번이 지킨다). 정리 작업이 문서 행이나 원천 행을 물리 삭제한 뒤에 오는 되살리기는 `lock_live_source`와 `documents.lock`의 `RuntimeError`로 500이 된다. 티켓 14의 수용 기준에 "404로 끝나게 고치고 실제 정리 작업과 겹치는 시험을 둔다"를 더해 두었다.
- 하네스로 따로 할 일: 열린 항목 `surface-tests-after-implementation`이 6회차가 되어 chore 배치 조건에 이미 든다(지침, 스킬 `implement`). 이 PR에서는 반영하지 않았다.
