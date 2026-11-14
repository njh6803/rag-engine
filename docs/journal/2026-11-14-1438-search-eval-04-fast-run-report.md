# search-eval 04: `run --through fused`와 단계별 지표 보고서 · 2026-11-14

티켓 `.scratch/search-eval/issues/04-fast-run-report.md`를 구현한 기록이다. 브랜치는 `feature/04-fast-run-report`이고 PR은 #42다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `tidy-checkouts`를 돈 뒤 `EnterWorktree`로 새 워크트리에 들어가 했다. 세션 도중 컨텍스트가 압축되었다. 이번 요청의 범위는 PR과 병합까지다.

## 준비

- 읽은 것: 지시문, `.claude/skills/implement/SKILL.md`, 티켓 04, 명세 `.scratch/search-eval/spec.md`, 앞 일지 `2026-11-14-1128-search-eval-03-eval-index-command.md`의 `## 다음`, 티켓 03의 `## Comments`.
- 티켓 03의 `## Comments`가 보류한 지적 둘은 `run`이 03의 판정(`check_database`)과 같은 길을 쓰므로 한 번 읽었다. 04는 `check_indexed`의 반환을 넓히지 않아 그 둘을 손대지 않았고 티켓 06의 `## Comments`로 넘겼다.

## 한 것

- `app/eval_metrics.py`: 순수 함수다. `score_query`가 질의 하나의 결과를 순위별로 닿은 기대 근거의 집합으로 들고, `aggregate`가 적중률@1·3·5·10, MRR, 재현율, nDCG@10, nDCG 잘린 수를 낸다.
- `app/eval_run.py`: `run_fast_evaluation`과 `stage_ranking`이다. 질의마다 진단용 검색(`diagnose_candidates`, 정확 스캔)을 한 번 불러 벡터만, 키워드만, 합친 뒤 세 단계의 순위를 만든다. 합친 뒤 단계만 `fused_rank <= 후보 수`로 자른다.
- `app/eval_report.py`: `report.json`과 `report.md`의 내용. 보고서의 `format_version`은 `1.0.0`이다.
- `adapters/eval_run.py`: `run_fast`. 환경을 읽고, 03의 `check_database`와 스키마가 비어 있지 않은지를 확인하고, 평가 도중 판이 바뀌었는지 보고, 보고서를 쓴다. `adapters/eval_bundle_hash.py`는 묶음의 내용 해시를 계산한다.
- `tools/search_eval.py`: `run` 하위 명령. `--through`는 값 하나만 받고, 다르면 종료 코드 2다. `--through rerank`는 05가 더한다는 안내와 함께 1로 끝난다.
- 시험: `tests/app/test_eval_metrics.py`(13), `tests/app/test_eval_run.py`(5), `tests/adapters/test_eval_bundle_hash.py`(12), `tests/adapters/test_eval_run_commit.py`(3), `tests/tools/test_search_eval_run.py`(표면, 약 25). 지원으로 `tests/support/eval_world.py`와 `tests/tools/conftest.py`를 두었고, 03의 `test_search_eval_index.py`가 같은 세계와 픽스처를 쓰게 옮겼다. `tests/support/tei_stub.py`에는 응답 순번을 거는 `on_embeddings`를 더했다.
- 변이 표 `.scratch/search-eval/probes/eval_run_mutations.toml`(11). 표면 시험의 가드를 겨눈다.
- 문서: 티켓 04를 `done`으로 두고 `## Comments`를 더했다. 티켓 06의 `## Comments`, `README.md`의 트리, `.scratch/plan-head.md`를 고치고 `.scratch/plan.md`는 `tools/plan_table.py`로 다시 만들었다.

## 정한 것

- 검색 유스케이스를 부르지 않는다. 그 유스케이스는 `top_k`로 자른 결과만 돌려줘 단계마다의 순위를 주지 못하고, 시간 제한은 평가가 재는 것이 아니다. 같은 준비(현재 판 읽기, 질의 임베딩)는 평가 유스케이스에서 따로 한다.
- 질의의 임베딩 끝점은 판에 적힌 것이 아니라 `RAG_EVAL_EMBEDDING_URL`이다. `run`은 `RAG_EVAL_*` 환경 변수만 읽고 제품 `RAG_*`와 `.env`는 읽지 않는다.
- nDCG는 기대 근거 하나가 처음 닿은 순위에서 한 번만 이득 1을 준다. 이상적인 순위는 min(기대 근거 수, 10)개이고 값은 1에서 자르며, 잘린 질의 수를 센다.
- 평가 도중 색인 판이 바뀌면 보고서를 쓰지 않고 1로 끝낸다. 시험은 TEI 스텁의 응답 순번으로 판을 바꾼다.
- 내용 해시는 머리, 구성(`judge_*`를 뺀 정렬된 JSON), 문서 목록, 기대 근거, 질의 목록 파일을 `이름\0길이\0바이트`로 이어 sha256으로 계산한다. 심판 모델이 바뀌어도 같은 묶음으로 본다.
- 쪽으로 적은 기대 근거는 닿지 않는 것으로 센다. 티켓 06이 더한다.

## 셀프 리뷰

`code-review` 두 축. 표준 축은 Sonnet 5.5 / high다. 커밋 전에 돌았고 Critical과 Major는 없었다.

- 고친 것: 합친 뒤 단계의 후보 수 걸러내기, 내용 해시, `--through` 오류 까닭을 겨누는 시험을 더했다. 변이 표의 `sort_keys` 변이는 보고서에 차이가 없는 동등 변이라 구성의 바이트를 넣는 변이로 바꿨다.
- 고친 것(명세 축과 표준 축이 함께 잡은 틀린 문장): 티켓 `## Comments`가 "후보 수는 SQL이 이미 자른다"고 적었다. 진단용 검색은 합집합을 자르지 않으므로 합친 뒤 단계를 후보 수에서 자르는 곳은 `stage_ranking` 하나다. 문장과 모듈 독스트링을 코드에 맞게 고쳤다.
- 남긴 것(Minor, 동작을 바꾸지 않는다): 아래 PR 직전 리뷰의 유효 다섯과 같다. PR 본문 "남긴 위험"에 적었다.
- 다시 돌린 것: 커밋의 pre-commit이 `ruff`, `pyright`, `lint-imports`, 전체 `pytest`를 돌렸다.

## PR 직전 리뷰

CodeRabbit CLI(0.7.5)가 한 번 돌았다. `Seat: not assigned`(Free)에서도 끝까지 돌았고 지적은 여덟이었다. 유효 다섯은 모두 Minor였고, 오탐 셋은 코드로 확인해 닫았다. Critical과 Major는 없었다.

- 남긴 것(Minor 다섯): 내용 해시가 머리와 목록을 `read_eval_set`과 따로 한 번 더 읽는다(두 읽기 사이에 파일이 바뀌면 보고서의 해시가 평가한 묶음과 어긋난다). 세트 이름과 질의 목록 이름이 `report.md`에 이스케이프 없이 들어간다. `report.json`을 쓴 뒤 `report.md`를 쓰기 전에 실패하면 새 json과 옛 md가 섞인다. `meta.commit`이 작업 트리가 더러운지는 싣지 않는다. `TeiEmbedderPool` 짓기와 끝점 교체가 `check_indexed`와 되풀이된다(평가 끝점을 쓰는 셋째 자리인 05가 생길 때 모은다).
- 이 반영이 새로 쓴 사실 문장(PR 봇이 겨냥할 것): `app/eval_run.py`의 모듈 독스트링(준비를 검색과 따로 한다는 서술)과 `stage_ranking` 독스트링(진단용 검색이 합집합을 자르지 않아 이곳이 자른다), 티켓 04와 06의 `## Comments`, PR 본문의 "리뷰어 참고".

## 검증

- 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`, 변이 표 열한 개 모두 기대대로 빨강.
- 첫 커밋 시도의 pre-commit은 전체 `pytest`에서 4044개 가운데 `tests/test_serve_command.py`의 `test_serve가_뜨면…` 하나(serve가 30초 안에 뜨지 않았다)로 막혔다. 그 회차의 검사 러너가 989초 걸렸고 앞 회차는 329초였다. 그 시험은 단독으로 8.85초에 통과했고, 같은 커밋을 다시 돌린 훅이 통과해 커밋이 만들어졌다(9c0a53d).
- 시험 순서를 솔직히 적는다. 표면 시험(`tests/tools/test_search_eval_run.py`)은 구현 뒤에 썼다. 빨강은 그 시험이 아니라 변이 표 열한 개가 구현을 틀리게 했을 때 시험이 실패하는 것으로 확인했다.
- 실제 TEI(bge-m3)로 `run`을 돌리는 실행은 이 PR에서 하지 않았다. 시험은 TEI 스텁으로 돈다.

## 봇 회차

PR #42, 첫 푸시 9c0a53d에서 두 봇이 처음 리뷰했다(CodeRabbit은 `@coderabbitai review` 뒤에 리뷰했고 검사 여섯은 모두 초록이었다). 두 봇 모두 첫 회차다. CodeRabbit이 Major 하나와 Minor 셋, claude-review가 Minor 셋과 Nit 하나를 냈다.

- 고친 것(CodeRabbit Major): `run`의 시작 판정(`check_database`)이 문서의 소속과 내용 해시만 보고 색인 상태는 보지 않았다. 문서의 내용 해시는 올릴 때 저장되므로 색인이 대기 중이거나 실패한 문서도 묶음과 같아, 그 문서의 조각이 0개로 세어져 보고서가 종료 코드 0으로 끝나고 그 문서의 질의가 모두 놓친 것이 된다. 수용 기준에는 없던 요구지만 틀린 숫자를 조용히 내는 결함이라 고쳤다. 시험을 먼저 써서(색인 대기, 색인 실패, 옛 내용으로 지은 상태 셋) 고치기 전에 세 경우가 모두 실패함을 보았다. `app/check_indexed_documents.py`에서 문서마다의 색인 판정을 `_indexed_content`로 빼 `validate --indexed`와 `run`이 같은 기준을 쓰게 했고, 토큰을 세는 끝점이 필요 없는 `check_documents_indexed`를 더해 `_check_ready`가 질의를 임베딩하기 전에 부른다.
- 고친 것(CodeRabbit Minor): `current_commit`이 `git -C`를 주고도 `GIT_DIR`이 다른 저장소를 가리키면 그 저장소의 커밋을 읽었다. 시험을 먼저 써서 고치기 전 실패를 보았고(다른 저장소의 커밋이 나왔다), 저장소 위치 환경 변수(`tools/run_hooks.py`의 `REPO_LOCATION_VARS`와 같은 일곱)를 자식 환경에서 벗겼다.
- 보류(CodeRabbit Minor 둘): 내용 해시가 평가한 입력과 같은 스냅샷에서 나오지 않는 것과 `report.json`·`report.md`를 차례로 쓰는 것은 셀프 리뷰와 PR 직전 리뷰가 이미 남긴 Minor와 같다. 앞의 것은 `read_eval_set`이 바이트가 아니라 읽은 값을 돌려주어, 같은 스냅샷으로 만들려면 02와 03이 쓰는 읽기 모듈의 반환을 넓혀야 한다. 뒤의 것은 두 파일을 한 쌍으로 바꿔 놓을 길이 없고, 쓰기가 실패하면 종료 코드 1과 오류의 종류를 알린다. 둘 다 PR 본문 "남긴 위험"에 이미 적혀 있다.
- 보류(claude-review Minor 셋과 Nit 하나): Minor 둘(해시 모듈이 머리의 두 칸을 따로 선언한다, `run_fast`가 실패 분기마다 출력과 종료 코드를 되풀이하고 `TeiEmbedderPool` 짓기가 `check_indexed`와 되풀이된다)은 셀프 리뷰가 남긴 것과 같고 평가 끝점을 쓰는 셋째 자리(05)가 생길 때 모은다. 새로 나온 Minor 하나(해시의 구성 입력이 보고서 모듈의 `config_values`에 기대어, 보고서에 구성 칸을 더하면 내용 해시가 바뀐다)는 06의 `--config`가 구성이 보고서와 해시에 들어가는 길을 건드릴 때 정하도록 티켓 06의 `## Comments`에 적었다. Nit(`QueryOutcome`이 `frozen=True`인데 `reach`가 가변 dict이다, `stage_ranking`의 `or 0`)는 동작을 바꾸지 않는다.
- 이 반영이 새로 쓴 사실 문장(다음 회차 봇이 겨냥할 것): `check_documents_indexed`와 `_check_ready`의 독스트링("문서의 내용 해시는 올릴 때 저장되므로 색인이 대기 중이거나 실패한 문서도 묶음과 같다"), `adapters/eval_run.py` 모듈 독스트링의 4번 항목, `current_commit` 독스트링("`git -C`를 줘도 `GIT_DIR`이 있으면 git이 그 저장소를 읽는다")과 `_GIT_LOCATION_VARIABLES` 주석("`tools/run_hooks.py`의 `REPO_LOCATION_VARS`와 같은 목록이다"), 티켓 04와 06의 `## Comments`의 새 항목.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`, 새 시험과 `tests/tools/test_search_eval_run.py`·`test_search_eval_index.py`·`tests/adapters/test_eval_run_commit.py` 92 passed. 전체 시험은 커밋의 pre-commit이 돈다. 첫 커밋 시도는 전체 시험(`pytest` 427초)을 모두 통과한 뒤 03의 변이 표 한 항목(10번, 색인 상태와 파싱 결과 판정을 지운다)이 옮겨 간 원문을 찾지 못해 막혔다(회고 9). 원문의 들여쓰기를 고친 뒤 두 표(`eval_index_mutations.toml` 23, `eval_run_mutations.toml` 11)가 `--check`로 원문이 한 번씩 있고, 10번 변이를 실제로 돌려 기대대로 빨강이다(`1 failed`).

## 회고

낸 후보 열. 승인 3, 기각 7, 넘김 없음.

1. 변이 표의 표지로 처음 고른 글이 시험 파일에 글자 그대로 있어 도구가 거부했고, 다음에 고른 표지는 실제 실패 출력에 없어(`표지 없음`) 둘 다 출력을 본 뒤 다시 골라 표를 한 번 더 돌았다. → 승인(회차로 세는 것). 열린 항목 `mutate-marker-discovery`가 이미 처방한 사건이고 승인 줄을 5회차로 고쳤다. 다섯 번째라 반영 문턱에 닿았지만 이 세션은 반영하지 않는다. 처방이 `tools/mutate.py`를 고치는 일이라 기능 PR에 실을 수 없고, 회차 5 이상인 열린 항목이 `next-session` 결정표의 chore 배치 조건이기 때문이다. 같은 도구를 다루는 `pytest-during-mutate`(1회차)는 처방이 달라 따로 둔다.
2. `test_serve가_뜨면…`이 전체 러너 한 회차의 부하에서 30초 기동 시간을 넘겨 빨갰고 단독으로는 초록이었다. → 기각, 일지에만. 부하에서만 빨간 시간 시험은 닫힌 항목 `token-expiry-test-load-margin`이 받아들여 닫은 종류이고, 세 일지(`2026-11-12-1419-dev-branch-model`, `2026-11-13-0124-session-model-fable-5-2`, `2026-11-13-0144-dev-release-pr-step`)가 같은 시험의 새 사례를 항목으로 잇지 않았다(retro 5단계). 든 비용은 pre-commit 한 바퀴(989초)다. 다시 열지는 사용자가 정한다.
3. 변이 표의 `sort_keys` 변이가 보고서에 차이를 내지 않는 동등 변이였다. → 기각. 도구가 기대한 빨강이 나오지 않는다고 그 자리에서 알렸고 표를 고쳤다.
4. 티켓 `## Comments`에 "후보 수는 SQL이 이미 자른다"는 틀린 문장을 썼다. → 기각. 두 축이 모두 잡아 리뷰가 제 몫을 했다(retro 4단계의 회차로 세지 않는 것).
5. 표면 시험을 구현 뒤에 썼다(헌법 I). → 기각, 일지에만. 리뷰가 잡은 사건이 아니고, 한 커밋 안에서 시험과 구현의 작성 순서를 판정할 검사가 없다. 시험이 구현을 겨누는지는 변이 표가 따로 판정한다.
6. 워크트리 가드가 큰 heredoc과 복합 명령을 거부했다. → 기각. 이미 있는 가드가 그 자리에서 막았고 `Edit`와 명령 분리로 따랐다.
7. IDE가 낡은 pyright 진단("could not be resolved")을 보였다. → 기각. 색인이 늦은 소음이고 `uv run pyright`가 판정자다(03 회고 8과 같다).
8. `run`이 색인이 끝나지 않은 문서를 막지 않는다는 Major를 PR 봇(CodeRabbit)이 첫 회차에서 냈다. → 기각. 티켓과 명세에 없던 요구라 어긴 지침이 없고, 리뷰 파이프라인의 봇 층이 제 몫을 한 것이다(retro 4단계의 회차로 세지 않는 것). 셀프 리뷰 두 축과 PR 직전 CodeRabbit CLI는 이것을 내지 않았다. 같은 꼴(수용 기준 밖의 결함을 봇만 잡는다)이 다시 나면 회차로 센다.

9. 봇 회차 반영 커밋의 첫 시도가 전체 `pytest`(427초)를 모두 통과한 뒤에야 `check-mutations`에 막혔다. `check_indexed_documents.py`를 함수로 빼며 조건문의 들여쓰기가 줄어, 03의 변이 표(`eval_index_mutations.toml`)의 한 항목이 원문을 찾지 못했다. → 승인(회차로 세는 것). 열린 항목 `precommit-mutations-after-tests`가 이미 처방한 사건(`pytest` 같은 긴 검사 뒤에야 1초 안 걸리는 변이 표 검사가 실패를 알린다)이고 승인 줄을 4회차로 고쳤다. 5회차 전이라 반영하지 않는다. 코드를 고친 뒤 그 파일을 가리키는 다른 표를 `uv run python tools/mutate.py --check <표>`로 먼저 보는 길은 도구 독스트링에 이미 있었다. 이번에는 이 길을 거치지 않았고, 표를 다시 쓴 뒤에는 `--check`로 원문을 보고 그 변이 하나를 실제로 돌려 빨강을 확인했다.
10. 같은 커밋의 둘째 시도가 전체 검사(`pytest` 468초)를 통과한 뒤 `commit-msg` 훅에서 제목 80자 > 72자로 막혔다. → 승인(회차로 세는 것). 열린 항목 `commit-msg-after-slow-checks`가 이미 처방한 사건(메시지 형식 검사가 긴 검사 러너 뒤에 돌아 늦게 막힌다)이고 승인 줄을 3회차로 고쳤다. 5회차 전이라 반영하지 않는다. 명령은 `git commit -F <메시지 파일>`이었고 `hook_bash_commit_msg`가 그 꼴을 막도록 있는데 지나갔다. 명령이 `cd <워크트리> &&`로 시작했고 세션의 작업 폴더가 연결된 워크트리였다는 것만 확인했고, 훅이 왜 지나갔는지는 진단하지 않았다. 항목의 처방이 이미 있는 훅으로 충분한지는 다음 회고가 그 훅을 이 입력으로 불러 보고 가른다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev` 출력 모두 만료할 항목이 없다고 했다. 회차 5 이상은 `measured-claim-beyond-probe`(6회차)와 이번에 5회차가 된 `mutate-marker-discovery`다.

## 다음

- 이 PR이 병합되면 티켓 04는 끝이다. 05가 `--through rerank`를 더한다(지금은 05가 더한다는 안내와 함께 종료 코드 1이다). 05는 평가 끝점을 쓰는 셋째 자리라, `TeiEmbedderPool` 짓기와 끝점 교체의 되풀이를 그때 모은다.
- 06이 읽을 것: 티켓 06의 `## Comments`. 03의 Minor 셋(이름 없는 `(오류, 경고)` 튜플, 읽기 트랜잭션 안의 토큰 세기 등)과, `--config`로 바꾼 후보 수가 `stage_ranking`의 걸러내기에 이어지는지 보는 시험이다.
- 이번 PR이 남긴 Minor 다섯(위 PR 직전 리뷰)은 어느 티켓도 맡지 않았다. 해시의 이중 읽기와 `report.md` 이스케이프는 06이나 07이 보고서를 건드릴 때 같이 본다.
- 02에서 이어진 것: PR #40 봇 회차의 보류 둘(`_entries`의 출력 인자 변경, `_read_miss_reviews`의 이중 경로 검사)은 04가 그 파일을 넓히지 않아 건드리지 않았다. 변이 표 둘의 윈도 전용 표지는 리눅스에서 다시 골라야 한다.
- 03에서 이어진 것: `index_bundle`의 `except` 갈래 되풀이와 `_ingest_and_process`의 한 함수 안 추상화 수준은 `index`의 단계가 늘 때 나눈다(티켓 03 `## Comments`).
- 대기열 `commit-msg-after-slow-checks`(3회차): `hook_bash_commit_msg`가 `cd <워크트리> && git commit -F <파일>`의 80자 제목을 지나친 까닭을 이 입력으로 훅을 불러 진단한다. 커밋 전에는 `uv run python tools/check_commit_msg.py <메시지 파일>`로 제목을 먼저 본다.
- 회차 5 이상인 열린 항목이 둘이다(`measured-claim-beyond-probe` 6회차, `mutate-marker-discovery` 5회차). 다음 chore는 `next-session` 결정표가 고른다.
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)다. 병합 뒤 `tidy-checkouts`는 다음 새 세션이 돈다.
- 사람에게 넘긴 정리: 워크트리 `14-reindex-version-switch`는 앞 일지에서 이어져 `git worktree list`에 그대로 남아 있다.
