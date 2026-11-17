# search-eval 01: 진단용 검색 `diagnose_candidates`와 판정기 `RelevanceJudge` 포트 · 2026-11-13

티켓 `.scratch/search-eval/issues/01-diagnose-and-judge-ports.md`를 구현한 기록이다. 브랜치는 `feature/01-diagnose-and-judge-ports`이고, `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `tidy-checkouts`를 먼저 돌고 `EnterWorktree`로 새 워크트리에 들어가 했다. 세션 도중 컨텍스트가 한 번 압축되었다. 이번 요청의 범위는 PR과 병합까지다.

## 준비

- 읽은 것: 지시문, `.claude/skills/implement/SKILL.md`, 티켓 01, 명세 `.scratch/search-eval/spec.md`의 "진단용 검색과 단계", 앞 일지 `2026-11-13-1716-search-eval-tickets.md`의 `## 다음`, ADR 0007·0018·0019.
- `tidy-checkouts` 결과(보고만 하고 답을 기다리지 않았다): 루트는 `dev`였고 커밋하지 않은 로그 파일 둘(`.scratch_li.log`, `.scratch_pyr.log`)이 있어 당기지 않았다. 병합된 워크트리 정리 가운데 `14-reindex-version-switch`는 사람에게 넘겼고, `.claude/worktrees/.tidy-trash/`에 `.venv` 둘이 남았다.
- 이어받은 결정: 진단용 검색의 불리언 인자 `exact`가 `CODING_STANDARDS.md`의 첫 판단 기준(불리언 플래그 인자 금지)에 걸리므로 열거로 둘지 메서드 둘로 쪼갤지를 포트를 세울 때 정한다.

## 한 것

- `domain/entities.py`에 `CandidateScan`(`INDEX`, `EXACT`), `DiagnosedHit`(`hit`, `ordinal`, `vector_rank`, `keyword_rank`, `fused_rank`), `SearchDiagnosis`(`is_current`, `hits`)를 더했다.
- `domain/ports.py`에 `VectorIndex.diagnose_candidates(query, *, scan)`과 `RelevanceJudge.judge(query, text) -> bool`을 더했다. 판정기의 독스트링은 다시 해 볼 만한 실패는 `TransientFailure`, 그 밖은 `PermanentFailure`로 올리고 제3자 메시지를 싣지 않는다고 적는다.
- `adapters/postgres/vector_index.py`: 벡터·키워드 CTE, 필터와 그룹 집합의 조건, RRF 점수의 식을 `_candidate_parts`로 하나로 모아 `search_sql`과 `diagnosis_sql`이 함께 쓴다. `search_sql`이 낸 SQL 글은 질의 여덟 종류에서 고치기 전과 같았다. `SET LOCAL hnsw.ef_search`와 `hnsw.iterative_scan`은 `_apply_search_settings`로 모아 두 메서드가 같은 규칙으로 건다. `EXACT`는 `_scan_plan`이 호출 동안만 `enable_indexscan`을 끄고 끝에 끄기 전 값으로 되돌린다. 시험용으로 계획을 글로 내는 `explain_diagnosis`를 두었다.
- 시험: `tests/adapters/test_vector_index_chunks.py`에 대조 시험(키워드 유무 × 필터 유무), 합집합과 순위, 키워드가 빈 질의, `ef_search`·`iterative_scan` 감시, `scan` 설정 감시, EXPLAIN(정확 스캔에는 판의 HNSW 부분 색인이 없고 색인 스캔에는 있다. `EXACT` 호출 뒤에도 같은 트랜잭션의 `INDEX` 계획과 `search_candidates` 계획에 색인이 있다), `EXACT`의 `vector_rank`가 거리 순, `is_current`, 같은 연결에서 두 계획을 번갈아 부르는 시험을 더했다. `tests/domain/test_relevance_judge.py`와 `tests/support/fake_judge.py`(가짜 판정기)를 새로 두었다.
- 명세와 티켓 04·06의 `exact` 참·거짓 서술을 `CandidateScan.INDEX/EXACT`로 고쳤다. 티켓 12에는 판정기 실패의 오류 코드가 정해지지 않았다는 주석을 더했다. 변이 표 `first_round_trip_adapter_mutations.toml`에서 `ef_search` 변이의 원문을 새 코드에 맞췄고 항목 하나(`진단용 문장 글이 계획마다 같다`)를 더했다.

## 정한 것

- 열거로 갔다. 메서드를 둘로 쪼개지 않은 것은 두 계획이 같은 SQL 글을 돌고 다른 것은 계획 설정뿐이라서다. 명세의 `[사용자 선택]`(정확 스캔으로 후보를 뽑는다)은 그대로다.
- `DiagnosedHit`은 `SearchHit`을 상속하지 않고 `hit` 칸으로 든다. 평가가 `dataclasses.replace`로 리랭크 점수를 붙이려면 `SearchHit`이 그대로 필요하고, 어댑터가 칸 열세 개를 되풀이해 적지 않아도 된다.
- `EXACT`의 계획 설정은 세이브포인트 없이 되돌린다. `SET LOCAL`은 `RELEASE SAVEPOINT` 뒤에도 남기 때문이다. 몸통에서 데이터베이스 오류가 나면 트랜잭션이 되돌려지므로 되돌리기를 건너뛴다.
- 판정기 실패의 오류 코드는 정하지 않았다. 시험은 `ErrorCode.EMBEDDING_UNAVAILABLE`·`EMBEDDING_REJECTED`를 빌려 썼고, 티켓 12가 정한다(티켓 12 `## Comments`).

## 셀프 리뷰

`code-review` 두 축, base `97f9914`. 표준 축은 Sonnet 5.5 / high다.

- 명세 축 Major 하나: `explain_diagnosis`만 보는 계획 시험으로는 실제 `diagnose_candidates`가 `scan`을 따르는지 알 수 없다. → 고쳤다. 호출이 거는 `set_config('enable_indexscan', ...)`을 감시하는 시험을 더했고(`INDEX`는 설정하지 않고 `EXACT`는 off 뒤 on), `_scan_plan(CandidateScan.INDEX)`로 바꾸는 변이에서 빨강을 봤다.
- 남긴 것(Minor·Nit): `is_current`와 `hits`를 짜는 곳이 두 군데에 비슷하게 있다. `ef_search` 감시 코드가 시험 셋에 되풀이된다. 둘 다 동작에 영향이 없어 이 PR에서 정리하지 않았다.
- ADR 0007 이력의 한 줄(`search_candidates`와 같은 질의를 받아)은 인자가 열거로 바뀌어도 거짓이 되지 않아 건드리지 않았다. ADR 고침은 승인이 필요하다.

## PR 직전 리뷰

CodeRabbit CLI가 한 번 돌았고 리뷰는 끝까지 돌았다(`Seat: not assigned`). 지적 1건(Major, 유효): psycopg는 같은 문장을 다섯 번 돌리면 서버에 준비시키고 서버는 그 뒤 일반 계획을 쓰는데, 일반 계획은 `enable_indexscan`이 바뀌어도 다시 짜지지 않는다. 그래서 같은 연결에서 `INDEX`와 `EXACT`를 번갈아 부르면 `EXACT`도 색인을 탄다.

- 시험으로 재현했다. 여덟 번씩 번갈아 부른 뒤 `pg_stat_user_indexes`의 `idx_scan` 증가가 8이어야 하는데 11이었다.
- 고침: `diagnosis_sql`이 글 앞에 `/* scan=<값> */` 주석을 붙여 두 계획이 다른 문장으로 준비되게 했다. 같은 시험이 초록이 되었고, 주석을 지우는 변이에서 `색인 스캔 11회, 기대 8회`로 빨강이다(변이 표 항목 16).
- 그 고침이 새로 쓴 사실 문장(PR 봇이 겨냥할 것): `diagnosis_sql`의 독스트링(`enable_indexscan`은 `SET LOCAL`이라 문장 글에 나타나지 않는다, psycopg가 다섯 번 넘게 돌리면 준비시킨다, 일반 계획은 설정이 바뀌어도 다시 짜지지 않는다, 주석이 다르면 서버가 다른 문장으로 준비시킨다), 티켓 01 `## Comments` 여섯째 항목.

## 검증

- 손으로 친 것: `uv run ruff check`, `uv run ruff format`, `uv run pyright`(변경 파일, 0 errors), `uv run pytest tests/adapters/test_vector_index_chunks.py`(37 passed), `tools/mutate.py --staged`와 변이 항목 16 실행(기대대로 빨강), `tools/sibling_overlap.py`(0, 번호·파일 겹침 없음).
- 첫 커밋 `1e093df`의 pre-commit은 전체 pytest가 부하로 두 번 빨갰다(`test_job_lease`의 시간 시험들, `test_tool_errors`의 `ReadTimeout`). 모두 따로 돌리면 초록이었고 이 변경이 닿지 않는 시험이며, 셋째 시도에서 통과했다.
- 둘째 커밋 `ed9f544`의 첫 시도는 `parallel-checks`가 465초를 돈 뒤 `check-mutations`가 새 변이 항목의 표지를 거절해 커밋이 만들어지지 않았다(먼저 pytest가 풀어 쓴 단언 줄, 그다음 시험 원문에 그대로 있는 문구). 단언 메시지에 받은 값을 싣고 그 문구를 표지로 고른 뒤 둘째 시도에서 통과했다.
- 이 일지와 회고의 대기열 갱신을 싣는 커밋은 pre-commit으로 갈음하고 결과는 PR 본문에 적는다.

## 회고

낸 후보 여섯. 승인 2(둘 다 열린 항목의 3회차), 기각 4, 넘김 없음.

1. 같은 연결에서 준비된 일반 계획이 설정을 무시하는 결함을 어댑터 시험이 밟지 못하고 PR 직전 CodeRabbit CLI가 잡았다. → 승인(회차로 세는 것). 열린 항목 `adapter-tests-generic-plan`이 이미 처방한 사건이다. 승인 줄을 3회차로 고쳤다. 5회차 전이라 반영하지 않는다.
2. pre-commit의 `parallel-checks`가 465초를 돈 뒤에야 변이 표 검사가 실패를 알렸다. → 승인(회차로 세는 것). 열린 항목 `precommit-mutations-after-tests`가 처방한 사건이다. 승인 줄을 3회차로 고쳤다. 5회차 전이라 반영하지 않는다. 표지 규칙(`mutate-marker-discovery`가 다루는 종류)에 걸린 것은 같은 사건의 일부라 따로 세지 않았다.
3. 전체 pytest가 부하에서 시간 경쟁 시험으로 두 번 빨개져 커밋이 막혔다. → 기각. 닫은 항목 `token-expiry-test-load-margin`이 받아들여 닫은 종류(부하에서만 빨간 시간 시험)라 새 항목으로 잇지 않고 일지에만 적는다(`retro` 4단계).
4. 긴 heredoc, `python3`, 한국어가 아닌 중간 문장, 한글 폭으로 넘친 주석 줄이 각각 PreToolUse 훅과 `ruff`와 `tools/rewrap_comments.py`에 그 자리에서 막히거나 고쳐졌다. → 기각. 이미 있는 훅과 검사가 그 자리에서 막았다.

만료: `uv run python tools/queue_open_rows.py`는 만료할 항목이 없다고 했다(`--ref origin/dev`로 다시 돌리지는 않았다. 승인 줄의 가장 늦은 날짜가 모두 14일 안이다). 회차 5 이상은 `measured-claim-beyond-probe`(6회차)뿐이고 이 브랜치와 닿지 않는다.

## 다음

- 이 PR이 병합되면 티켓 01은 끝이고 02가 열린다(`Blocked by`가 01뿐인 티켓). 02는 `.scratch/search-eval/issues/02-*.md`를 읽고 `/implement`로 연다.
- 티켓 12가 판정기 실패의 오류 코드를 정한다(티켓 12 `## Comments`). 01은 `ErrorCode.EMBEDDING_*`를 시험의 대역으로만 빌려 썼다.
- ADR 0007 이력의 한 줄(`search_candidates`와 같은 질의를 받아)은 인자의 모양이 바뀌어도 그대로 읽히지만, 이력을 더할 일이 생기면 `CandidateScan`을 함께 적는다. 승인이 필요한 일이라 이 PR에서 하지 않았다.
- Minor로 남긴 둘(`is_current`·`hits` 조립의 중복, `ef_search` 감시 코드의 되풀이)은 같은 시험 파일을 더 넓힐 때 정리한다.
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)이고 커밋하지 않은 로그 둘이 있어 당기지 못했다. 병합 뒤 `tidy-checkouts`는 다음 새 세션이 돈다.
- 사람에게 넘긴 정리: 워크트리 `14-reindex-version-switch`와 `.claude/worktrees/.tidy-trash/`의 `.venv` 둘(다음 정리가 다시 본다).
