# search-eval 06: 놓친 까닭과 나눠 본 숫자, `inspect`, `--config` · 2026-11-14

티켓 `.scratch/search-eval/issues/06-miss-causes-and-breakdowns.md`를 구현한 기록이다. 브랜치는 `feature/06-miss-causes-and-breakdowns`다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `tidy-checkouts`를 돈 뒤 `EnterWorktree`로 새 워크트리에 들어가 했다. 티켓 06, 07, 12를 나란히 여는 묶음의 하나라 세 티켓이 `tools/search_eval.py`, `app/eval_report.py`, `adapters/eval_run.py`를 함께 건드린다. 충돌은 나중에 병합하는 쪽이 푼다. 세션 도중 컨텍스트가 압축되었다. 이번 요청의 범위는 PR과 병합까지다.

## 준비

- 읽은 것: 지시문, `.claude/skills/implement/SKILL.md`, 티켓 06, 형제 티켓 07과 12, 명세 `.scratch/search-eval/spec.md`의 적중의 단위, 놓친 까닭, 지표, 보고서, 자리와 층, 평가 세트의 형식 절, 앞 일지 `2026-11-14-1723-search-eval-05-full-run-rerank.md`의 `## 다음`.
- 이 세션이 맡은 것은 티켓의 수용 기준 외에 둘이다. 05의 PR 봇 둘째 회차 Minor(`QueryOutcome.scored`의 기본값 `()`가 빠른 실행과 후보가 없는 전체 실행을 가르지 못한다)와, 04가 06에 넘긴 `## Comments` 셋(내용 해시의 구성 입력을 domain에 두기, `config_values`의 불리언 인자 쪼개기, `TeiEmbedderPool` 짓기의 되풀이 모으기)이다.
- 실제 TEI(Docker와 GPU)와 실제 HNSW가 모자라게 내는 경우는 이 티켓의 시험 범위 밖이다. 시험은 `TeiStub`의 결정적 값과 `INDEX`일 때만 후보를 줄이는 대역을 쓴다.

## 한 것

- `app/eval_stages.py`(새): `Stage`. `app/eval_misses.py`(새): `MissCause`(`no_matching_chunk`, `not_in_candidates`, `lost_in_fusion`, `lost_in_rerank`), `reaching_chunks`, `classify_miss`, `word_overlap`. `app/eval_breakdown.py`(새): 유형 표지별, 필터 질의별, 놓친 질의, 놓친 까닭의 수, 사람 판정의 수를 만드는 행들. `app/eval_inspect.py`(새): `inspect_query`와 표준 출력용 글 `inspection_text`.
- `app/eval_run.py`: `Evaluator`가 `rank`(단계마다의 순위)와 `outcome`(질의의 결과)로 나뉘고, `QueryOutcome`이 `miss`(`QueryMiss`)와 `filter_probe`(`FilterScanProbe`)를 싣는다. 쪽으로 적은 기대 근거가 닿는지는 `app/eval_metrics.py`의 `reaches`가 조각이 덮은 블록의 쪽 번호로 본다. 쪽 번호는 `read_evaluation_index`가 문서의 최신 파싱 결과에서 읽는다.
- `app/eval_report.py`: `by_tag`, `filtered`, `misses`, `miss_counts`, `human_causes` 칸과 `report.md` 표. 판은 `"1.0.0"` 그대로다(칸을 더하는 것은 판을 올리지 않는다).
- `domain/eval_set.py`: 유형 표지와 사람 판정의 까닭 목록, `MissReview`, 해시와 비교가 쓰는 `search_config_values`와 보고서가 쓰는 `config_values`(판정 칸을 더한다).
- `adapters/`: `eval_assembly.py`(새. `run`과 `inspect`가 함께 지나는 준비 `prepare_evaluation`, 데이터베이스 판정 `check_ready`, 조립 `evaluation_deps`), `eval_inspect.py`(새), `eval_environment.py`(`eval_embedder_pool`과 `eval_embedder_for`로 `TeiEmbedderPool` 짓기와 끝점 교체를 모았다), `eval_index.py`·`eval_set_reader.py`·`eval_bundle_hash.py`(구성 파일 `config_file` 길과 해시 입력 정리), `eval_run.py`.
- `tools/search_eval.py`: `inspect <묶음> <질의 목록> <기대 근거 id> [--through fused|rerank]`, `index`·`run`·`inspect`의 `--config <파일>`.
- 시험: `tests/app/test_eval_misses.py`, `test_eval_breakdown.py`, `test_eval_inspect.py`, `test_eval_report.py`(새), `tests/domain/test_eval_set.py`(새), `tests/tools/test_search_eval_misses.py`(새, 13), `tests/tools/test_search_eval_filter_probe.py`(새, 1), 지원 `tests/support/eval_run_support.py`(새)와 `tei_stub.py`의 `embed_with`, 기존 시험의 수정.
- 변이 표 `.scratch/search-eval/probes/eval_misses_mutations.toml`(12). 셀프 리뷰가 04와 05의 변이 표 두 개에서 원문이 사라진 여섯 항목을 잡아 새 위치로 고쳤다(아래).
- 문서: 티켓 06을 `done`으로 두고 `## Comments`를 더했다. `README.md`의 트리와 `compose.eval.yml`의 안내를 고쳤다.

## 정한 것

- 놓친 질의는 마지막 단계의 상위 10에 닿는 조각이 없는 질의다. 탈락 지점은 `classify_miss`가 `last_stage`를 받아 차례대로 처음 맞는 것을 붙인다. `lost_in_fusion`의 뜻이 빠른 실행과 전체 실행에서 다른 것은 명세 그대로이고 그 인자로 가른다.
- 필터 질의의 모자람은 `FilterScanProbe(expected_vectors=min(후보 수, 정확 스캔의 벡터 후보 수), index_vectors=INDEX 스캔의 벡터 후보 수)`의 `short`로 센다. 정확 스캔도 못 채우는 질의는 비율에 들지 않는다.
- `QueryOutcome.scored`는 `None`이면 빠른 실행, `()`이면 후보가 없던 전체 실행이다. 05 봇의 Minor가 짚은 구분이고 `build_score_distribution`은 `None`을 받으면 `ValueError`를 낸다.
- `inspect`는 질의의 글과 조각의 글을 표준 출력에만 싣고 파일을 쓰지 않는다. 데이터베이스에 붙으므로 `run`과 같은 준비와 판정(`prepare_evaluation`, `check_ready`)을 지난다(원칙 V).
- `--config`로 준 구성은 보고서의 `config`와 내용 해시 모두 그 구성으로 계산한다. 구성 파일은 묶음 밖의 경로여도 된다. `judge`에 더하는 것은 12가 맡는다(둘 가운데 나중에 병합하는 쪽이 더한다).
- 해시는 판정 칸을 뺀 `search_config_values`로, 보고서의 `config`는 판정 칸을 더한 `config_values`로 계산한다. 옛 `with_judge` 불리언 인자는 없앴다(`CODING_STANDARDS.md`).

## 셀프 리뷰

`code-review` 두 축. 표준 축은 Sonnet 5.5 / high다. 범위는 base `a495e80`, 수정 21개, 미추적 소스·시험·문서 18개, 커밋 0개다. Critical은 없었고 Major 둘을 두 축이 함께 잡았다.

- 고친 것(Major): `app/eval_report.py` 모듈 독스트링이 새 칸 다섯(`by_tag`, `filtered`, `misses`, `miss_counts`, `human_causes`)이 없다고 쓰고 그 칸을 "받는 티켓이 더한다"는 미래형을 남겼다. 이 변경이 거짓으로 만든 문장이라 칸 목록을 고치고 미래형은 LLM 숫자와 추론 기록(12, 07)에만 남겼다. 04와 05의 변이 표 두 개(`eval_run_mutations.toml` 11개 가운데 4개, `eval_full_run_mutations.toml` 9개 가운데 2개)가 가리키는 원문이 이번 변경의 코드 이동으로 사라져 `mutate.py --check`가 어긋났다. 여섯 항목을 새 위치(`eval_metrics.py`의 `reaches`, `eval_environment.py`의 끝점 교체, `eval_assembly.py`의 스키마 판정, `eval_bundle_hash.py`의 해시 입력, `eval_run.py`의 `rankings[Stage.RERANK]`와 `rerank_candidates` 호출)로 옮겨 `--check`를 다시 통과시켰다.
- 고친 것(Minor): `app/check_eval_database.py` 머리말이 `config.json`만 말하던 것(`--config`가 구성을 바꾼다), `app/eval_run.py` 모듈 독스트링이 `inspect`가 `Evaluator` 안에서 부르는 준비 함수를 직접 쓴다고 적던 것, `report_problems`의 "보고서를 쓰지 않았다" 문구(`inspect`도 쓰는 함수), `_snapshot`이 파일 크기만 견주던 것(내용 바이트를 견준다).
- 남긴 것(Minor, 동작을 바꾸지 않는다): 쪽으로 적은 기대 근거의 "두 쪽에 걸친 조각" 표면 시험이 짧은 PDF 두 쪽이 한 조각이 되는 것에 기댄다(첫 블록의 쪽과 덮은 블록의 쪽이 갈리는 것은 단위 시험 `test_eval_misses.py`가 본다). 글귀와 쪽을 섞은 기대 근거의 낱말 겹침은 글귀만으로 값을 낸다(명세는 쪽으로 적은 기대 근거만 `null`이라 적는다. 애매해서 그대로 두었다). `inspect`가 필터 질의에서 INDEX 스캔을 한 번 더 부른다(출력에 쓰이지 않는 호출이다). `Evaluator`의 `rank`와 `outcome`이 늘 짝으로 불리는 것, `_check_and_evaluate`와 `_check_and_inspect`의 같은 꼴, 전체 실행인지의 되판정(`through`, `reranker_url is None`, `reranker is None`), `QueryMiss.word_overlap` 필드와 같은 이름의 함수, 시험 도우미의 키워드 전용 불리언 `hit`, 05가 남긴 `rerank_candidates`와 `app/search.py`의 `_rerank` 되풀이는 모두 모양의 문제라 아래 "다음"에 적었다. 프로브 README에 `eval_misses_mutations.toml` 행을 더하지 않았다. 앞의 변이 표 셋(03, 04, 05)도 그 표에 없고, 그 표는 명세와 ADR의 근거로 든 프로브를 적는 곳이다.
- 이 반영이 새로 쓴 사실 문장(PR 직전 리뷰가 겨냥할 것): `app/eval_report.py` 모듈 독스트링의 칸 목록, `app/check_eval_database.py` 머리말의 "구성(묶음의 `config.json`이나 `--config`로 준 파일)", `app/eval_run.py` 모듈 독스트링에서 `inspect`가 `Evaluator`(`open_evaluator`)를 거쳐 같은 준비 함수를 쓴다고 적은 문단, 이 일지의 위 항목들.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format`(`tests/tools/test_search_eval_misses.py` 한 파일을 다시 접었다), `uv run pyright`(0 errors), 변이 표 세 개의 `--check`(원문이 한 번씩 있다). 전체 시험은 커밋의 pre-commit이 돈다.

## PR 직전 리뷰

CodeRabbit CLI(0.7.5)가 `coderabbit review --agent --include-untracked --base origin/dev`로 한 번 돌았고(`Seat: not assigned`, Free에서도 `review_completed`까지 돌았다) 지적은 2건이었다. 서브에이전트가 직접 읽어 4건을 더했다. Critical과 Major 가운데 유효한 것은 없었다.

- 오탐(CodeRabbit이 Critical로 낸 것): `adapters/eval_assembly.py`의 `guarded`가 예외 문자열을 표준 오류에 그대로 찍는다는 지적이다. 그 두 줄은 `origin/dev`의 `adapters/eval_run.py` 143행과 146행에 있던 것을 옮긴 것이고(본 세션이 `git show origin/dev:`로 확인했다), 닿는 예외 셋(`EvalRunError`, `EvalEnvironmentError`, `ConfigurationError`)의 문장은 고정 문구나 칸 이름, 질의 목록 이름, 기대 근거 id뿐이고 접속 문자열을 싣지 않는다. 접속 실패는 종류만 찍는 다른 갈래가 맡는다.
- 오탐(CodeRabbit이 Major로 낸 것): `read_evaluation_index`가 읽는 쪽(문서의 최신 파싱 블록)과 조각이 같은 판인지 확인하라는 지적이다. `check_ready`가 평가 전에 `check_documents_indexed`로 파싱 결과와 색인 상태가 지금 내용의 것인지 이미 본다. 남는 틈은 평가 도중 같은 평가 데이터베이스에 `index`를 동시에 돌리는 경우뿐이고 `is_current`가 판 전환은 막는다. 고치지 않았다.
- 유효(Minor): `inspect`가 조각 글을 표준 출력에 찍을 때 stdout 인코딩이 cp949(`PYTHONUTF8`이 없는 Windows에서 리디렉션이나 파이프)이면 `UnicodeEncodeError`로 끝난다. 콘솔에 바로 찍을 때는 괜찮다. 처음에는 남기려 했으나 PR의 CodeRabbit이 같은 지적을 내서 봇 회차에 고쳤다(아래 "봇 회차").
- 유효(Nit, 남김): `eval_environment.py`의 설정 오류 문장이 `--config`로 준 파일이 틀려도 `config.json`을 가리킨다. `inspect`가 조각 글의 제어 문자를 걸러내지 않는다(글은 평가 묶음에서 오므로 신뢰 경계 안이다). `reaching_chunks`가 조각마다 글귀를 다시 정규화한다(놓친 질의에서만 돌고 규모가 작다). 
- 서브에이전트가 직접 읽어 문제가 없다고 본 것: 질의와 조각의 글이 새는 길(`print`는 `inspect`의 표준 출력 한 곳과 오류 문장뿐이고 보고서 칸은 식별자와 숫자뿐이다), `--config` 경로 처리(묶음 밖 경로 허용, 디렉터리와 FIFO 거르기, 오류에 파일 내용이 안 실린다), 연결과 풀 닫기(`check_ready`와 `evaluation_deps`의 `finally`), 변이 표 다섯의 원문 정합. 변이를 실제로 돌려 빨강을 보는 일은 하지 않고 앵커만 봤다. 변이는 본 세션이 돌렸다.
- Nit(기존 모양): `evaluation_deps`가 엔진과 풀과 `httpx.AsyncClient`를 `try` 앞에서 만들어, `RAG_EVAL_RERANKER_URL`을 `httpx`가 거부하면 엔진과 풀이 닫히지 않는다. `origin/dev`의 옛 `_evaluate`와 같은 모양이고 프로세스가 곧 끝난다.
- 이 반영이 새로 쓴 사실 문장: 없다(코드와 독스트링을 고치지 않았다).

## 검증

- 손으로 친 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), `uv run lint-imports`(경계 계약 지킴), 전체 검사 러너 `tools/run_checks.py`(종료 코드 0, 셀프 리뷰 반영 전에 한 번). 새 표면 시험 16개와 기존 평가 시험 49개 초록. 변이 표 `eval_misses_mutations.toml` 열둘이 모두 기대대로 빨강이다. 셀프 리뷰가 고친 04와 05의 변이 표는 `eval_run_mutations.toml` 열하나, `eval_full_run_mutations.toml` 아홉 모두 다시 돌아 기대대로 빨강이고 `--check`도 통과한다(`eval_index_mutations.toml`, `eval_set_validate_mutations.toml` 포함 다섯 표).
- 시험 순서를 솔직히 적는다. 앱 시험은 시험을 먼저 쓰고 구현했지만, 표면 시험(`tests/tools/test_search_eval_misses.py`, `test_search_eval_filter_probe.py`)은 구현 뒤에 써서 처음부터 초록이었다(원칙 I). 빨강은 변이 표가 구현을 틀리게 했을 때 시험이 실패하는 것으로 확인했다. 04와 05에 이어 세 번째 사건이다.
- 실제 HNSW가 모자라게 내는 경우는 결정적으로 만들 수 없어 시험하지 않았다. INDEX일 때만 후보를 줄이는 대역(`_CutIndex`)이 그 질의가 비율에 드는 것을 본다.
- 변이 표를 처음 돌릴 때 `expect_output` 표지가 시험 파일에 이미 있는 글이라 거부되어, 표지 자리에 임시 글을 두고 실패 출력을 받아 실제 값으로 채웠다(`mutate-marker-discovery`의 사건). 그렇게 채운 표지 둘(`assert 50 == 1`, 호출 꼴이 든 `FilterScanProbe(…).short`)은 첫 커밋 시도에서 pre-commit의 `check-mutations`가 pytest의 단언 풀이 줄이라며 거부했고 커밋이 만들어지지 않았다. 단언 접두와 호출 이름을 뗀 `50 == 1`과 `index_vectors=2).short`로 바꿔 `--check`와 두 변이의 재실행을 통과시켰다. 회차는 회고가 센다.
- 이 세션의 셸은 `RAG_TEST_DATABASE_URL`이 없으면 DB 시험이 설정 단계에서 오류로 끝난다. 셀프 리뷰 반영 뒤 변이 표를 다시 돌릴 때 환경 변수 없이 돈 실행의 기준선이 오류였고, 그 실행은 멈춘 뒤 환경 변수를 명령 줄에 직접 붙여 다시 돌렸다. 왜 한 번은 환경 변수가 닿지 않았는지는 가리지 못했다. 이 Windows 셸에는 `pkill`이 없어 멈추려던 첫 실행이 계속 돌았고, 그 실행이 같은 변이 표를 이어 돌아 두 실행이 `src/rag_engine/app/eval_run.py`를 겹쳐 고쳤다. 첫 표가 "되돌리지 못했다"로 종료 코드 3을 냈고 `if not diagnosis.is_current:`가 `if False:`로 남아 있었다. 그 한 줄을 손으로 되돌린 뒤 다섯 표의 `--check`(변이 원문이 소스에 한 번씩 있다)와 `if False:` 검색으로 남은 변이가 없는 것을 확인하고, 두 표를 겹침 없이 처음부터 다시 돌렸다. 변이 도구를 백그라운드로 돌릴 때는 프로세스를 `Get-CimInstance Win32_Process`로 찾아 `Stop-Process`로 멈춰야 하고, 변이 도중에는 같은 소스를 고치지 않아야 한다(회고 후보).

## 봇 회차

PR #44, 첫 푸시 24ef179에서 두 봇이 처음 리뷰했다(`@coderabbitai review` 뒤에 CodeRabbit이 `Finished`였고 검사 여섯이 모두 초록이었다). 두 봇 모두 첫 회차다. CodeRabbit은 인라인 코멘트 하나(Minor)와 요약을, claude-review는 Minor 셋과 Nit 하나를 냈다. Critical과 Major는 없었다.

- 고친 것(CodeRabbit Minor, PR 직전 리뷰가 먼저 낸 것과 같은 지적): `inspect`의 출력이 cp949 stdout에서 `UnicodeEncodeError`로 끝나는 것. `adapters/eval_inspect.py`에 `emit(text, stream)`을 두어 스트림의 인코딩으로 표현할 수 없는 글자를 `?`로 바꿔 쓴다. 시험을 먼저 썼고(`tests/adapters/test_eval_inspect.py` 셋. 구현 전에 import 오류로 빨강), 변이 13번(`errors="replace"`를 `"strict"`로)이 기대대로 빨강이다. 기존 `inspect` 표면 시험 6개는 그대로 통과한다. 표면 시험이 `inspect_evaluation`에서 `emit`을 지나는지 가르지는 못한다(pytest의 `capsys`는 UTF-8이라 cp949 출력을 만들지 못한다).
- 보류(claude-review Minor 셋과 Nit 하나. 모두 동작을 바꾸지 않는 모양 문제): `inspect_query`가 `evaluator.index.pages`를 꺼내 `chunk_reach`에 넘기는 것(`Evaluator`가 닿았는지를 답하는 메서드를 가지는 편이 낫다), 공개 `Evaluator`가 비공개 `_DocumentChunks`를 칸의 타입으로 노출하는 것, `_check_and_evaluate`와 `_check_and_inspect`의 같은 꼴(07과 12가 보도록 이미 적었다), `inspect_query`의 한 식이 `Inspection`, `StageView`, `InspectedChunk`를 모두 짓는 것. 앞의 셋은 07과 12가 `Evaluator`와 `run` 조립을 건드릴 때 함께 보도록 아래 "다음"에 적었다. Nit은 두었다.
- 이 반영이 새로 쓴 사실 문장(다음 회차 봇이 겨냥할 것): `adapters/eval_inspect.py` 모듈 독스트링의 인코딩 문단(`PYTHONUTF8`이 없는 Windows에서 파이프나 리디렉션을 하면 cp949다)과 `emit`의 독스트링, 이 일지의 위 항목들.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`(0 errors), 새 시험 3개, `inspect` 표면 시험 6개, 변이 표 `--check`(13, 원문이 한 번씩 있다)와 13번 실행. 전체 시험은 커밋의 pre-commit이 돈다.

## 회고

낸 후보 열둘. 승인 6, 기각 6, 넘김 없음.

1. 변이 표의 표지가 시험 파일에 이미 있는 글이라 도구가 거부했고, 임시 글로 출력을 받아 채운 표지 둘(`assert 50 == 1`, `FilterScanProbe(…).short`)이 첫 커밋 시도에서 `check-mutations`에 단언 풀이 줄이라며 거부되어 표를 한 바퀴 더 돌았다. → 승인(회차로 세는 것). 열린 항목 `mutate-marker-discovery`가 이미 처방한 사건이고 승인 줄을 7회차로 고쳤다. 5회차 이상이라 이미 chore 배치 조건이다. 이 세션은 `tools/mutate.py`를 고치지 않는다.
2. 표면 시험(`tests/tools/test_search_eval_misses.py`, `test_search_eval_filter_probe.py`)을 구현 뒤에 써서 처음부터 초록이었다(원칙 I). 이 일지의 검증 절이 스스로 적었다. → 승인(회차로 세는 것). 열린 항목 `surface-tests-after-implementation`의 승인 줄을 3회차로 고쳤다. 다섯 번째 전이라 반영하지 않는다.
3. 스크립트로 쓴 시험 파일 넷이 CRLF가 되어 `sed -i 's/\r$//'`로 되돌렸다. → 승인(회차로 세는 것). 열린 항목 `crlf-from-script-edits`의 승인 줄을 6회차로 고쳤다. 5회차 이상이라 이미 chore 배치 조건이다.
4. 검사와 대기열 출력을 `../_g*.txt`, `../../../_q1.txt`, `../../../_nope.txt`로 리다이렉트해 주 체크아웃 루트에 파일을 세 번 만들었다. 셋째는 앞의 둘을 알고 한 것이다. 곧바로 지웠고 남은 것은 없다. → 승인(회차로 세는 것). 열린 항목 `redirect-outside-worktree`가 이미 처방한 사건이고 승인 줄을 2회차로 고쳤다. 한 세션의 세 번은 한 회차로 센다. 지침으로는 같은 세션 안에서 되풀이를 막지 못했으니 훅이 처방이라는 점이 더 분명하다. 파일이 남았다면 주 체크아웃이 깨끗하지 않아 `tidy-checkouts`가 당기지 못했을 것이라 손상의 문턱에 가깝지만, 이번에는 남은 것이 없어 문턱을 넘지 않았다고 본다. 다섯 번째 전이라 반영하지 않는다.
5. 변이 표를 백그라운드로 돌리다 `pkill`이 없는 Windows 셸에서 첫 실행을 멈추지 못해 두 실행이 `eval_run.py`를 겹쳐 고쳤고 `if False:`가 소스에 남았다. 손으로 되돌리고 `--check` 다섯과 검색으로 확인했다. → 승인(더하는 것). 대기열 폴더를 `--search mutate.py`, `겹쳐`, `동시`로 찾았다. 변이 도구가 pytest와 겹치는 `pytest-during-mutate`와 usage 출력이 긴 `mutate-usage-dump`가 맞았지만 변이 도구끼리 겹치는 사건은 아무도 다루지 않는다. 처방이 `tools/mutate.py`의 잠금이라 `pytest-during-mutate`(훅)와 길이 달라 새 항목 `mutate-concurrent-runs`를 쓰고 1회차로 적었다. `pytest-during-mutate`의 본문에서 새 항목을 가리킨다. 다섯 번째 전이라 반영하지 않는다.
6. 이 셸에서 `RAG_TEST_DATABASE_URL`이 없어 DB 시험이 설정 단계에서 오류로 끝났다. → 기각. 오류로 끝나 그 자리에서 알렸고(skip이 아니다), 변수의 값과 설정은 `CLAUDE.md` 검증 명령과 `compose.test.yml` 머리 주석에 이미 있다.
7. 이번 변경의 코드 이동으로 04와 05의 변이 표 두 개에서 원문 여섯이 사라졌다. → 기각. `mutate.py --check`가 어긋남을 잡았고(리뷰가 돌려 보았다) 고쳐서 다시 통과시켰다. 이미 있는 검사가 그 자리에서 알린 것이다.
8. 워크트리 가드가 `sed … && git …` 같은 복합 명령을 거부했다. → 기각. 이미 있는 가드가 그 자리에서 막았고 명령을 나누어 따랐다.
9. IDE가 편집 직후 낡은 pyright 진단을 보였다. → 기각. 색인이 늦은 소음이고 `uv run pyright`가 판정자다(05 회고 6과 같다).
10. 영어로 중간 문장을 한 줄 썼다. → 기각. 훅이 그 자리에서 알렸고 한국어로 이어 갔다.
11. 시험의 `TextIOWrapper`가 Windows에서 `\n`을 `\r\n`으로 바꿔 새 시험이 실패했고 ruff의 `unnecessary-encode-utf8`이 걸렸다. → 기각. 시험과 린트가 쓰는 중에 바로 알렸고 `newline=""`와 `.encode()`로 고쳤다.

12. 둘째 커밋(봇 회차 수정과 회고)의 pre-commit이 전체 pytest 1313초 끝에 `tests/test_serve_command.py`의 `serve` 시작 시험 하나가 "30초 안에 뜨지 않았다"로 실패해 커밋이 만들어지지 않았다. 이 변경은 `serve`를 건드리지 않았고 그 시험만 홀로 돌리면 14초에 통과한다. → 승인(고침). 대기열을 `--search test_serve_command`, `STARTUP_TIMEOUT`, `부하`로 찾아 맞은 `stale-branch-base-test-fix`(뒤처진 브랜치의 사건)와 닫힌 `token-expiry-test-load-margin`(다른 시험)을 열어 대 보았고 같은 시험을 다룬 항목이 없어 새 항목 `serve-startup-test-load-margin`을 1회차로 썼다. 고침이라 문턱 없이 반영할 수 있지만 기능 PR에 실을 수 없는 다른 파일이라 대기열에 둔다. 이 실패 하나를 지나가려고 시험을 고치지 않았고(원칙 I) 홀로 돌려 초록을 본 뒤 같은 커밋을 다시 돌린다. 같은 시험이 두 번 연속 실패하면 멈추고 `diagnosing-bugs`를 쓴다.

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev` 출력 모두 만료할 항목이 없다고 했다. 회차 5 이상은 `measured-claim-beyond-probe`(6회차), `mutate-marker-discovery`(7회차), `crlf-from-script-edits`(6회차)다.

## 다음

- 이 PR이 병합되면 티켓 06은 끝이다. 나란히 도는 07(추론 기록)과 12(관련성 판정자)가 이어서 같은 파일을 건드린다: `tools/search_eval.py`, `app/eval_report.py`, `adapters/eval_run.py`. 충돌은 나중에 병합하는 쪽이 푼다. 둘 다 티켓 06의 `## Comments`를 먼저 읽는다.
- 12가 맡은 것: `judge` 하위 명령에 `--config`를 더한다. 06은 `_add_config`를 `index`·`run`·`inspect`에만 달았으니, 12는 `judge`에 `_add_config(judge)`를 더하고 `config_file=args.config`를 넘긴다(둘 가운데 나중에 병합하는 쪽이 한다). 보고서의 LLM 숫자 칸은 12가, 추론 기록은 07이 더하며 `app/eval_report.py` 모듈 독스트링의 미래형은 그 둘에만 남아 있다.
- 07과 12가 `Evaluator`와 `run` 조립을 건드릴 때 함께 볼 Minor(06이 남겼다): `inspect_query`가 `evaluator.index.pages`를 꺼내 `chunk_reach`에 넘기는 것(`Evaluator`가 닿았는지를 답하는 메서드를 가지는 편이 낫다), 공개 `Evaluator`가 비공개 `_DocumentChunks`를 칸의 타입으로 노출하는 것, `Evaluator`의 `rank`와 `outcome`이 늘 짝으로 불리는 것, `_check_and_evaluate`와 `_check_and_inspect`의 같은 꼴, "전체 실행인가"의 되판정(`through`, `reranker_url is None`, `reranker is None`), `QueryMiss.word_overlap` 필드와 같은 이름의 함수, 05가 남긴 `rerank_candidates`와 `app/search.py`의 `_rerank` 되풀이, `stage_ranking`이 `Stage.RERANK`에 `ValueError`를 내는 것, TEI 설정 불일치를 "후보를 리랭크하지 못했다"로 뭉치는 것.
- 동작을 정할 일(06이 애매해서 그대로 둔 것): 글귀와 쪽을 섞은 기대 근거의 낱말 겹침은 글귀만으로 값을 낸다(명세는 쪽으로 적은 기대 근거만 `null`이라 적는다). `inspect`가 필터 질의에서 INDEX 스캔을 한 번 더 부른다(출력에 쓰이지 않는다). `eval_environment.py`의 설정 오류 문장이 `--config`로 준 파일이 틀려도 `config.json`을 가리킨다.
- 시험하지 못한 것: 실제 HNSW가 모자라게 내는 경우, 실제 TEI와 GPU, `inspect_evaluation`이 `emit`을 지나는지(`capsys`는 UTF-8이라 cp949 출력을 만들지 못한다).
- 회차 5 이상인 열린 항목이 셋이다(`measured-claim-beyond-probe` 6회차, `mutate-marker-discovery` 7회차, `crlf-from-script-edits` 6회차). search-eval의 마지막 티켓 뒤에 `next-session` 결정표가 chore 배치로 고른다.
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)이고 이 세션은 워크트리라 당기지 않았다. 병합 뒤 `tidy-checkouts`는 다음 새 세션이 주 체크아웃에서 돈다.
- 사람에게 넘긴 정리: 티켓 09(`feature/09-public-docs-documents`)는 사용자의 확정을 기다려 쉬는 세션이 맡고 있다. 워크트리 `14-reindex-version-switch`는 앞 일지에서 이어져 그대로 남아 있다. 원격 브랜치 `feature/04-fast-run-report`는 이번 확인에서 이미 없었다.
