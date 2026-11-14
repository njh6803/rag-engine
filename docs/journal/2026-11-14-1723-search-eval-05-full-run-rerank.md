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
