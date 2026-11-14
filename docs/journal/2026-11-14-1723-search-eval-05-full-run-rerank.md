# search-eval 05: `run --through rerank`와 리랭크 점수 분포 · 2026-11-14

티켓 `.scratch/search-eval/issues/05-full-run-rerank.md`를 구현한 기록이다. 브랜치는 `feature/05-full-run-rerank`다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `tidy-checkouts`를 돈 뒤 `EnterWorktree`로 새 워크트리에 들어가 했다. 세션 도중 컨텍스트가 압축되었다. 이번 요청의 범위는 PR과 병합까지다.

## 준비

- 읽은 것: 지시문, `.claude/skills/implement/SKILL.md`, 티켓 05, 명세 `.scratch/search-eval/spec.md`의 진단용 검색과 단계·지표·전체 게이트·최소 점수 절, 앞 일지 `2026-11-14-1438-search-eval-04-fast-run-report.md`의 `## 다음`.
- 리랭커 TEI의 실제 서버(Docker와 GPU)는 이 티켓의 시험 범위가 아니다. 시험은 `TeiStub`의 결정적 점수를 쓴다.

## 한 것

- `app/eval_run.py`: `Stage.RERANK`, `FAST_STAGES`, `FULL_STAGES`, `ScoredCandidate`, `QueryOutcome.scored`를 더했다. `run_fast_evaluation`과 새 `run_full_evaluation`이 공통 `_evaluate`를 부르고, `reranker`가 있으면 합친 뒤 후보 전부를 `Reranker` 포트로 채점해 `rerank_ranking`(점수 순, 같은 점수는 합친 순위 순)으로 순위를 만든다. 리랭커에 보내는 글은 `compose_index_text`로 검색과 같이 절 경로를 붙인 글이다.
- `app/eval_score_distribution.py`(새 파일): 0.05 폭 20개 구간의 닿은 조각과 닿지 않은 조각 수, 문턱 0.05~0.95 열아홉 개마다의 적중률@5·10, 빈 질의 비율, 남는 조각 수의 평균.
- `app/eval_report.py`: 전체 실행의 보고서에만 `score_distribution`을 싣고 `report.md`에 같은 표를 싣는다.
- `adapters/eval_environment.py`: `require_reranker_url`. `adapters/eval_run.py`: `run_fast`를 `run_evaluation(..., through=Stage, ...)`로 바꾸고 전체 실행이면 `TeiReranker`를 `config.json`의 `reranker_model`로 지었다. `tools/search_eval.py`: `--through rerank`.
- 시험: `tests/app/test_eval_run.py`(4 추가), `tests/app/test_eval_score_distribution.py`(새 파일, 7), `tests/tools/test_search_eval_run.py`(표면 시험 추가·교체), 지원 `tests/support/eval_world.py`와 `tests/tools/conftest.py`의 리랭커 스텁 픽스처.
- 변이 표 `.scratch/search-eval/probes/eval_full_run_mutations.toml`(9).
- 문서: 티켓 05를 `done`으로 두고 `## Comments`를 더했다. 티켓 06의 `## Comments`, `README.md`의 트리, `compose.eval.yml`의 안내를 고쳤다.

## 정한 것

- 점수 구간은 나눗셈이 아니라 `number / 20`의 하한 목록과 `bisect_right`로 찾는다. `0.15 / 0.05`가 `2.9999999999999996`이라 나눗셈은 경계 점수를 앞 구간에 센다. 문턱은 그 값 이상을 남긴다. 분모는 평가한 모든 질의다.
- 불리언 플래그 인자를 만들지 않으려고 `through: Stage`를 넘긴다(`CODING_STANDARDS.md`).
- 리랭커 모델 이름은 지식베이스가 아니라 `config.json`의 `reranker_model`에서 읽는다.
- `QueryOutcome.scored`를 더해 06이 `lost_in_rerank`를 가를 수 있게 했다. 글과 식별자는 싣지 않는다(원칙 V).

## 셀프 리뷰

`code-review` 두 축. 표준 축은 Sonnet 5.5 / high다. 커밋 전에 돌았고 Critical은 없었다. 표준 축이 낸 Major 하나는 원칙 I(표면 시험을 구현 뒤에 썼다)이고, 티켓 `## Comments`와 아래 검증에 그대로 적었다.

- 고친 것: 시험 독스트링의 거짓 하나(문턱이 앞의 다섯을 걷어내면 순위가 오른다. 두 축이 함께 잡았다), 낡은 서술(`app/eval_run.py`와 시험의 모듈 독스트링, README의 tools 줄, 리랭커 끝점을 "없어도 된다"고 적은 `eval_environment.py`·`compose.eval.yml`·`search_eval.py`), `report.md` 표를 제목만 보던 시험(구간 표 두 줄과 문턱 표 세 줄의 값까지 본다).
- 남긴 것(Minor, 동작을 바꾸지 않는다): `_rerank`가 `app/search.py`의 `_rerank`와 글 만들기·예외 처리·문구를 되풀이한다. "전체 실행인가"가 네 곳에서 되판정된다. TEI 설정 불일치도 "후보를 리랭크하지 못했다"로 뭉친다(검색과 같은 처리). `EvalReport.score_distribution` 필드가 같은 이름의 함수를 가린다. `TeiEmbedderPool` 짓기의 되풀이(04가 05에 걸어 둔 약속)는 이 티켓의 수용 기준 밖이라 06이 `run` 조립을 다시 건드릴 때 모으도록 티켓 05와 06에 적었다.
- 다시 돌린 것: 커밋의 pre-commit이 `ruff`, `pyright`, `lint-imports`, 전체 `pytest`를 돌렸다.

## PR 직전 리뷰

CodeRabbit CLI(0.7.5)가 한 번 돌았다(`Seat: not assigned`, Free에서도 끝까지 돌았다). 지적은 0건이었다. 서브에이전트가 직접 읽어 확인한 것은 `_rerank`가 잡는 예외 둘과 TEI 어댑터가 올리는 예외의 대응, NaN·무한 점수가 어댑터에서 이미 거부되는 것, `finally`의 클라이언트 닫기, 오류 문장에 값이 실리지 않는 것(원칙 V)이다. Critical과 Major는 없었다.

- 이 반영이 새로 쓴 사실 문장(PR 봇이 겨냥할 것): `app/eval_run.py`의 모듈 독스트링(전체 실행 단락), `test_상위_5와_상위_10은_남은_조각의_순위로_센다`의 독스트링(문턱은 점수가 낮은 조각만 걷어낸다), `eval_environment.py` 모듈 독스트링과 `REQUIRED_ENV` 주석("전체 실행만 반드시 받는다"), `compose.eval.yml`과 `tools/search_eval.py`의 리랭커 끝점 서술, 티켓 05의 `## Comments`.

## 검증

- 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`(2 kept), 변이 표 아홉 개 모두 기대대로 빨강, 세 변이 표 `--check`로 원문이 한 번씩 있다.
- 시험 순서를 솔직히 적는다. 앱 시험(`tests/app/`)은 시험을 먼저 쓰고 구현했다. 표면 시험(`tests/tools/test_search_eval_run.py`)은 구현 뒤에 써서 처음부터 초록이었고, 빨강은 변이 표 아홉 개가 구현을 틀리게 했을 때 시험이 실패하는 것으로 확인했다.
- 변이 표의 표지 넷(3, 4, 7, 9번)이 처음에 실제 출력에 없어 `표지 없음`으로 어긋났다. 실패 출력을 파일로 받아 본 뒤 다시 골라 넷을 다시 돌았다(회고 후보).
- 실제 리랭커 TEI(Docker와 GPU)를 띄운 실행은 하지 않았다. 시험은 스텁으로 돈다.

## 봇 회차

PR #43, 첫 푸시 e0ff1ae에서 두 봇이 처음 리뷰했다(CodeRabbit은 `@coderabbitai review` 뒤에 `Finished`였고 검사 여섯은 모두 초록이었다). 두 봇 모두 첫 회차다. CodeRabbit은 "No actionable comments"였고 claude-review가 Minor 다섯과 Nit 하나를 냈다. Critical과 Major는 없었다.

- 고친 것(claude-review Minor): `EvalReport.score_distribution` 필드가 같은 모듈이 import한 함수 `score_distribution`과 이름이 같았다. 셀프 리뷰 표준 축도 Nit으로 낸 것이라 함수를 `build_score_distribution`으로 바꿨다(정의 하나, 호출 하나, 시험 셋, 변이 표 한 곳). 필드와 JSON 칸의 이름은 그대로다.
- 보류(claude-review Minor 넷과 Nit 하나): `stage_ranking`이 `Stage.RERANK`를 받으면 `ValueError`를 내는 것(인자를 `FAST_STAGES`의 좁은 타입으로 받으면 오류가 타입으로 바뀐다), `_rerank`가 `app/search.py`의 `_rerank`와 처리를 되풀이하는 것, "전체 실행인가"가 여러 곳에서 되판정되는 것은 모두 동작을 바꾸지 않는 모양 문제이고, `run` 조립을 06이 다시 건드릴 때 한꺼번에 보도록 아래 "다음"에 적었다. 표면 시험을 구현 뒤에 쓴 것은 이미 일지에 밝혔고 회고가 회차로 센다. Nit(질의가 0개인 전체 실행의 보고서에는 `score_distribution` 칸이 없다)은 질의 없는 묶음이 검증에서 걸러져 도달하지 않는 경로라 두었다.
- 이 반영이 새로 쓴 사실 문장(다음 회차 봇이 겨냥할 것): `build_score_distribution`의 독스트링과 `eval_report.py` 모듈 독스트링의 `score_distribution` 서술(이름만 바뀌었고 값은 같다), 이 일지의 위 항목들.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), 변이 표 `--check`(9, 원문이 한 번씩 있다), 앱 시험 16 passed. 전체 시험은 커밋의 pre-commit이 돈다.

## 회고

낸 후보 일곱. 승인 3, 기각 4, 넘김 없음.

1. 변이 표의 표지 넷(9개 가운데 3, 4, 7, 9번)이 처음 고른 문구와 달라 `표지 없음`으로 어긋났다. 어긋난 변이의 실패 출력을 보려고 스크래치 스크립트로 변이를 하나씩 적용해 시험을 돌린 뒤 표지를 고르고 넷을 다시 돌았다. → 승인(회차로 세는 것). 열린 항목 `mutate-marker-discovery`가 이미 처방한 사건이고 승인 줄을 6회차로 고쳤다. 5회차 이상이라 이미 chore 배치 조건이다. 이 세션은 `tools/mutate.py`를 고치지 않는다. 기능 PR에 실을 수 없는 처방이다.
2. 티켓 05의 문구를 고치는 `Path.write_text`가 파일을 CRLF로 바꿨다. 뒤이은 `git diff`의 `CRLF will be replaced by LF` 경고로야 알았고, 바이트 치환으로 LF로 되돌렸다. 커밋은 git이 정규화해 손상은 없었다. → 승인(회차로 세는 것). 열린 항목 `crlf-from-script-edits`가 이미 처방한 사건이고 승인 줄을 5회차로 고쳤다. 5회차에 이르러 chore 배치 조건이다. 이 세션은 반영하지 않는다(`tools/check_line_separators.py`나 `CLAUDE.md`를 고치는 일은 기능 PR에 실을 수 없다).
3. 표면 시험(`tests/tools/test_search_eval_run.py`)을 구현 뒤에 썼다(원칙 I). 04의 회고 5에서는 리뷰가 잡은 사건이 아니라 기각했지만, 이번에는 셀프 리뷰 표준 축이 Major로, 봇 claude-review가 Minor로 잡았다. 원칙 I은 구현 때 실리는 지침(`docs/constitution/principles.md`)이라 회차로 센다. → 승인(회차로 세는 것). 대기열 폴더와 일지를 `--search`로 찾았으나 같은 일을 다룬 항목이 없어 새 항목 `surface-tests-after-implementation`을 쓰고 2회차(04의 사건 포함)로 적었다. 한 커밋 안의 시험 작성 순서를 가를 검사가 없어 지침이 가장 높은 층이고, 처방은 `implement`의 시험 먼저 단계에 표면 시험도 구현 전에 빨강을 본다고 못 박는 것이다. 다섯 번째 전이라 반영하지 않는다.
4. 시험 독스트링의 거짓 하나(문턱이 앞의 다섯을 걷어내면 순위가 오른다)와 낡은 서술(`compose.eval.yml`, `eval_environment.py`, `app/eval_run.py` 모듈 독스트링 등)을 두 리뷰 축이 잡았다. → 기각. `code-review` 브리프의 주장 검증 목록이 겨눈 사건이고 리뷰가 제 몫을 한 것이다(회차로 세지 않는 것).
5. 워크트리 가드가 `git merge-base ... && ...` 같은 복합 명령을 거부했다. → 기각. 이미 있는 가드가 그 자리에서 막았고 명령을 하나씩 나눠 따랐다.
6. IDE가 편집 직후 낡은 pyright 진단(`reportUnknownMemberType` 열 개 남짓, `score_distribution is not defined`)을 보였다. → 기각. 색인이 늦은 소음이고 `uv run pyright`가 판정자다(03 회고 8과 04 회고 7과 같다).
7. 시험에서 `reranker_stub.bodies(...)`의 JSON 합집합 값을 순회하는 코드가 `uv run pyright`에서 여섯 오류를 냈다. → 기각. 손으로 친 pyright가 커밋 전에 잡았고 `isinstance`로 좁혀 고쳤다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev` 출력 모두 만료할 항목이 없다고 했다. 회차 5 이상은 `measured-claim-beyond-probe`(6회차), `mutate-marker-discovery`(6회차), `crlf-from-script-edits`(5회차)다.

## 다음

- 이 PR이 병합되면 티켓 05는 끝이다. 06이 놓친 까닭과 나눠 본 숫자, `inspect`, `--config`를 맡는다. 06이 읽을 것: 티켓 06의 `## Comments`(05가 남긴 문단 둘: `stages[-1]`이 마지막 단계다, `QueryOutcome.scored`와 `reach[Stage.RERANK]`를 06이 넓힌다).
- 06이 `run` 조립을 다시 건드릴 때 함께 볼 Minor(이번 PR이 남겼다): `TeiEmbedderPool` 짓기와 끝점 교체의 되풀이(04가 05에 걸어 둔 약속이고 05는 모으지 않았다), `app/eval_run.py`의 `_rerank`와 `app/search.py`의 `_rerank`의 되풀이, "전체 실행인가"의 되판정(`through`, `reranker_url is None`, `reranker is None`, `Stage.RERANK in stages`), `stage_ranking`의 `Stage.RERANK` 거부(좁은 인자 타입), TEI 설정 불일치를 "후보를 리랭크하지 못했다"로 뭉치는 것.
- 07이 읽을 것: 끝점 없이 리랭크 기록만으로 도는 길은 07이 더한다(티켓 05가 그렇게 정했다). 그때 `require_reranker_url`의 호출 자리가 바뀐다.
- 회차 5 이상인 열린 항목이 셋이다(`measured-claim-beyond-probe` 6회차, `mutate-marker-discovery` 6회차, `crlf-from-script-edits` 5회차). search-eval의 마지막 티켓 뒤에 `next-session` 결정표가 chore 배치로 고른다.
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)다. 병합 뒤 `tidy-checkouts`는 다음 새 세션이 돈다.
- 사람에게 넘긴 정리: 원격 브랜치 `feature/04-fast-run-report`는 병합된 PR 42의 것이고 앞 세션이 분류기에 거부되어 지우지 못했다. 사람이 `git push origin --delete feature/04-fast-run-report`를 치거나 허용 규칙을 더한 뒤 `tidy-checkouts`가 이어서 지운다. 티켓 09(`feature/09-public-docs-documents`)는 사용자의 확정을 기다려 쉬는 세션이 맡고 있고, 워크트리 `14-reindex-version-switch`는 앞 일지에서 이어져 그대로 남아 있다.
