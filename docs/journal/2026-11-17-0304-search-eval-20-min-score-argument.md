# search-eval 20: 검색의 min_score 인자와 지식베이스 기본값 · 2026-11-17

티켓 `.scratch/search-eval/issues/20-min-score-argument.md`를 구현한 기록이다. 브랜치는 `feature/20-min-score-argument`, base는 dev다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `tidy-checkouts`를 돈 뒤 `EnterWorktree`로 워크트리 `20-min-score-argument`에 들어와 진행했다. 나란히 도는 형제 티켓은 13, 16, 17이다.

## 시작할 때

`tidy-checkouts`가 남긴 것을 사람에게 넘긴다. 답을 기다리지 않았다.

- 주 체크아웃이 미갱신이다. 루트가 dev이고 깨끗하지 않아(추적하지 않는 `.scratch_li.log`, `.scratch_pyr.log`) 당기지 않았다.
- 휴지통(`.claude/worktrees/.tidy-trash/`)에 `.venv` 둘이 남았다. python.exe pid 13996이 쥐고 있어 비우지 못했다. 그 프로세스가 끝난 뒤의 정리가 다시 비운다.
- 워크트리 `14-reindex-version-switch`는 판정이 넘겼다. 폴더 `17-reranker-on-off-experiment`는 `.git` 파일이 있어 등록 없는 폴더로 지울 수 없어 넘겼다.

## 한 것

- 검색: `app/search.py`가 리랭크 뒤, `top_k`로 자르기 앞에서 `min_score`보다 낮은 조각을 뺀다. 같은 점수는 남는다. 요청 인자가 지식베이스 기본값을 이기고 `0`은 기본값을 덮는다. 범위 밖과 `nan`, 무한대는 임베딩을 부르기 전에 `invalid_argument`다. 리랭커가 없으면 요청 인자는 `invalid_argument`, 기본값만 있으면 `search_unavailable`이다.
- 저장: 지식베이스에 `min_score` 칸(널 허용 실수)과 CHECK 제약을 더했다(마이그레이션 0003, `SCHEMA_VERSION`은 그대로).
- 설정: `RAG_DEFAULT_MIN_SCORE`(비움이 기본)를 `migrate`가 기본 지식베이스에 쓰고 매번 덮어쓴다. 리랭커 URL이 비면 `migrate`가 변수 이름만 싣고 거부한다.
- 도구: `search`에 `min_score` 인자와 설명을 더했고 `FORMAT_VERSION`을 `1.1.0`으로 올렸다. 이 상수는 세 도구가 함께 쓴다.
- 시험: 새 시험 파일 둘(`tests/app/test_search_min_score.py` 19개, `tests/contract/test_search_min_score.py` 8개)과 기존 시험 파일 여덟의 고침(`tests/records.py`의 도우미 포함). 변이 11개를 표(`.scratch/search-eval/probes/min_score_mutations.toml`)로 묶었다.
- 문서: ADR 0017에 구현 이력 2026-11-17과 본문 포인터 셋을 더했다. `.scratch/core/spec.md`(기본 설정 나열, 시험 서술)와 `.scratch/search-eval/spec.md`(기본값 거부의 범위)를 맞췄다. 코어 변이 표 둘(`contract_mutations.toml`의 옛 판 `1.0.0`, `first_round_trip_mutations.toml`의 `hits[: request.top_k]`)이 깨져 맞췄다.

## 정한 것

- 티켓 17(리랭커 켬·끔)은 아직 결정 전이라 ADR 0017 이력의 전제(리랭커가 있는 지식베이스)로 진행했다.
- 거르는 자리와 `top_k`의 앞뒤는 결과가 점수 순이라 관찰로 가를 수 없다. 그래서 "리랭크 뒤"는 RRF 점수로 거르면 빨개지는 시험이 덮는다.
- `min_score`의 유효성은 색인 상태에 달리지 않는다. 판이 없는 지식베이스에서도 리랭커가 없으면 요청 인자는 `invalid_argument`다. `_effective_min_score`를 판 없음 반환 앞에 둔 까닭이다. 이 조합만 따로 덮는 시험은 없다.
- 설정의 범위 검사(`Field(ge=0, le=1)`)는 티켓이 요구하지 않았지만 `migrate` 앞에서 잘못된 값을 막는다. ADR 이력에 적었다.
- 관리 API의 거부(기본값이 있는 지식베이스에서 리랭커를 빼는 변경)는 이 티켓의 범위 밖이다. 관리 API에는 설정을 바꾸는 길이 없다(조회와 재색인뿐).

## 검증

- `uv run python tools/run_checks.py`가 전부 통과했다(pytest 393.5초). 커밋의 pre-commit도 같은 검사를 돌려 통과했다(pytest 625초).
- 변이 11개가 모두 기대한 빨강이다. 표지를 세 번 고쳐 다시 돌렸다(아래 회고).
- 새로 고친 두 코어 변이도 다시 돌려 빨강을 봤다.
- `tools/check_adr_pointers.py`와 `tools/plan_table.py --check`가 통과했다.

## 셀프 리뷰

`/code-review`(표준 축과 명세 축, 둘 다 서브에이전트)를 돌렸다. Critical과 Major는 없었다. 고친 것:

- 변이 표 `.scratch/core/probes/contract_mutations.toml`이 옛 판 `1.0.0`을 찾고 있었다(계약 변경이 거짓으로 만든 문장을 바뀐 값으로 grep해 찾았다). `1.1.0`과 `1.1.1`로 고쳐 다시 돌렸다.
- `.scratch/search-eval/spec.md` 197행이 "기본값을 설정하는 것도 거부한다"고만 적었다. 구현은 `migrate`에서만 거부한다는 범위와 ADR 이력을 가리키게 했다.
- `.scratch/core/spec.md` 97행의 `RAG_DEFAULT_*` 나열에 `RAG_DEFAULT_MIN_SCORE`가 없었다.
- 계약 시험이 도구 설명에 `min_score`라는 글자만 봤다. 거부 문구도 보게 했다.
- ADR 이력에 설정의 기동 검사(범위 밖, `nan`, 무한대)가 빠져 있어 더했다.
- 시험이 기대값을 분기로 계산하던 것(`[0.5, 0.2] if min_score == 0.0 else []`)을 값으로 나눴다.

남긴 것:

- 같은 범위 "0 이상 1 이하"가 유스케이스, 설정, 제약 둘에 따로 있다는 지적(Primitive Obsession)은 보류한다. 층마다 다른 방어이고 값 타입 하나가 이 네 곳을 한 번에 지키지 못한다.
- `_validate`와 `_effective_min_score`가 규칙을 나눠 담는다는 지적(Divergent Change)은 보류한다. 둘의 바뀌는 이유가 다르다(입력 범위, 리랭커 유무).
- 티켓의 `Status`가 `done`인데 마지막 칸이 비었다는 지적은 검사가 끝나 칸을 닫았다.

## PR 직전 리뷰

- `coderabbit-review` 에이전트: CLI 0.7.5(`Seat: not assigned`, Plan Free)가 `--base dev`로 26개 파일을 끝까지 리뷰했고 지적은 0건이었다. 밀어 본 주장 다섯(ADR 이력의 관리 API 서술, 설정 검증의 경계 입력, `_effective_min_score`의 네 조합, 명세 서술, 도구 설명)은 모두 코드·시험과 맞았다. 설정 검증은 `0`, `1`, 빈 문자열, `-0.01`, `1.01`, `nan`, `inf`, `abc`로 직접 불러 대 보았다.
- `/security-review`(서브에이전트): 확신 8 이상의 취약점 없음. `min_score`는 SQL에 들어가지 않고 메모리에서 비교만 하며, 인가(`_pick_knowledge_base`)가 새 흐름에서도 가장 먼저 돌고, 새 오류 메시지는 고정 문자열이다.
- Minor 셋(첫 회차이므로 지적마다 판단했다):
  - 도구 설명에 범위 밖 값의 거부가 없다는 지적: 보류한다. 범위 `0 이상 1 이하`는 설명에 있고, 위반이 `invalid_argument`인 것은 이 서버의 인자 오류가 모두 같은 코드라 설명이 되풀이할 정보가 아니다. 리랭커가 빈 채 기본값이 있는 행의 `search_unavailable`은 클라이언트가 고칠 수 없는 운영자 몫이라 설명에 싣지 않는다.
  - 판이 없는 지식베이스에서 요청 `min_score`가 `invalid_argument`가 되는 순서를 덮는 시험이 없다는 지적: 동작은 유지한다(위 "정한 것"). 시험은 아래 "다음"에 적는다.
  - 관리 API의 `KnowledgeBaseSettingsResponse`에 `min_score`가 없다는 지적: admin 기능의 몫으로 넘긴다. 아래 "다음"에 적는다.

## 회고

후보 여섯을 내고 승인 4, 기각 2, 넘김 0이다. 만료할 항목은 없었다(`queue_open_rows.py`가 만료할 항목 없음. 워크트리에서 낸 출력이고 병합 직전에 `--ref origin/dev`로 한 번 더 본다).

- 승인. 변이 표의 표지를 실제 출력을 본 뒤에야 고를 수 있어 새 표 11개에서 세 바퀴를 돌았다(시험 함수 이름이라 거부, 짐작한 표지가 어긋남, 단언 풀이 줄이라 `--staged`가 거부). 사건: 표지를 고치고 어긋난 항목만 다시 돌았다. 층: 열린 항목 `mutate-marker-discovery`가 이미 같은 사건을 처방한다. 되돌림: PR 하나다. 항목에 11회차를 더했다(10회차에서 11회차). 이미 chore 배치 조건(회차 5 이상)이라 이 세션에서 반영하지 않는다. `--check <파일>`에 이름을 주지 않으면 표 품질 검사를 건너뛴다는 사실도 항목에 적었다.
- 승인. 단언 풀이 줄을 표지로 쓴 항목이 `--staged`의 `check-mutations`에 거부된 것을 `parallel-checks`를 약 10분 돈 뒤에야 알았다. 층: 열린 항목 `precommit-mutations-after-tests`(훅 순서)가 처방한다. 5회차를 더했다(4회차에서 5회차). `.pre-commit-config.yaml`을 바꾸는 하네스 변경이라 이 기능의 PR에 싣지 않고 chore 배치로 둔다.
- 승인. 커밋 제목이 75자로 72자 제한을 넘어 `commit-msg`가 약 10분 뒤에 막았고, 50자로 줄여 약 10분을 더 돌았다. 층: 열린 항목 `commit-msg-after-slow-checks`가 처방한다. 4회차를 더했다(3회차에서 4회차). 막지 못한 까닭을 `tools/hook_bash_commit_msg.py`를 읽어 확인했다. 그 훅은 `-F <파일>`만 판정하고 `-m`의 메시지와 `cd`가 앞선 복합 명령은 독스트링의 "못 보는 것"에 이미 적혀 있다. 훅의 버그가 아니라 설계된 사각이라 고침 한 건으로 세지 않고 회차만 더한다.
- 승인. 백그라운드로 돌리던 `tools/run_checks.py`가 도는 동안 시험 파일을 고쳐 그 실행을 멈추고 다시 돌렸다. 층: 열린 항목 `edit-during-precommit`이 처방한다. 3회차를 더했다(2회차에서 3회차).
- 기각. 워크트리 가드가 `git -C .`, `&&` 체인, `; echo`를 거부한 것. 이미 있는 훅이 그 자리에서 막고 알렸고, 단순한 명령으로 풀어 호출 비용 한두 번이었다.
- 기각. 셀프 리뷰와 서브에이전트 리뷰가 잡은 것: 코어 변이 표 둘이 이 변경으로 깨진 것, ADR에 쓴 "관리 API가 아직 없다"가 틀렸던 것, 영어 중간 문장에 붙은 훅 경고. `code-review` 6단계의 주장 검증 목록(계약 변경이 거짓으로 만드는 문장을 바뀐 값으로 grep한다)이 이미 처방하는 사건을 리뷰가 제 몫으로 잡았다. 훅 경고는 훅이 알린 것이다.

## 다음

- 이 PR이 병합돼도 `search-eval` 기능은 끝나지 않는다. 티켓 13, 16, 17이 열려 있고, 남은 티켓과 프론티어는 `uv run python tools/plan_table.py`가 만드는 `.scratch/plan.md`로 본다.
- 티켓 17(리랭커 켬·끔 실험)의 결정이 `min_score`의 쓰임을 바꾼다. 17이 리랭커를 기본으로 끄면 이 인자를 거부하는 지식베이스가 늘어나고, ADR 0017 이력의 전제(리랭커가 있는 지식베이스)가 흔들린다. 17의 결정 뒤에 이 인자의 거부 규칙을 다시 본다.
- 보류한 Minor 셋을 받을 자리가 있다.
  - 색인 판이 없고 리랭커도 없는 지식베이스에서 요청 `min_score`가 `invalid_argument`가 되는 순서를 덮는 시험이 없다. 이 기능에서 검색 유스케이스를 다시 만지는 티켓이 있으면 그 티켓이 시험을 더한다.
  - 관리 API의 `KnowledgeBaseSettingsResponse`에 `min_score`가 없어 운영자가 설정된 기본값을 REST로 볼 수 없다. 설정을 바꾸는 길을 여는 admin 기능이 받는다. 그때 기본값이 있는 지식베이스에서 리랭커를 빼는 변경을 422로 거부하는 규칙도 함께 받는다.
  - 도구 설명에 범위 밖 값의 거부 문장이 없다. 이 서버의 인자 오류가 모두 `invalid_argument`라 되풀이하지 않기로 했다. 클라이언트가 헷갈린 사례가 나오면 다시 본다.
- 대기열의 `mutate-marker-discovery`(11회차)와 `precommit-mutations-after-tests`(5회차)가 chore 배치 조건(회차 5 이상)이다. `next-session` 결정표의 chore 배치가 고를 수 있다. 같은 대상 파일의 항목(`tools/mutate.py`의 셋)이 함께 묶일 수 있다.
- 주 체크아웃은 이 세션이 시작될 때 깨끗하지 않아(추적하지 않는 `.scratch_li.log`, `.scratch_pyr.log`) 당기지 않았다. 병합 뒤에도 당기지 않는다. 사람이 주 체크아웃 세션에서 `/tidy-checkouts`를 치거나 새 세션이 첫 턴에 부른다.
