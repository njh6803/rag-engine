# 05: 전체 실행: `run --through rerank`가 리랭크 뒤 줄과 점수 분포를 낸다

**What to build:** 개발자가 리랭커 TEI를 띄우고 `run --through rerank`를 치면, 평가가 합친 뒤의 후보 전부를 실제 검색과 같은 `Reranker` 포트로 채점해 리랭크 뒤 단계의 줄을 더하고, 최소 점수를 정할 근거인 `score_distribution`을 보고서에 싣는다(스토리 3, 27). 리랭커의 모델 이름은 지식베이스가 아니라 `config.json`의 `reranker_model`에서 읽는다.

**Blocked by:** 04 (빠른 실행)

**Status:** done

- [x] 리랭크 뒤 단계는 합친 뒤의 후보 전부(`fused_rank`가 후보 수 이하인 줄)를 리랭크한 점수 순이고, 점수가 같으면 합친 순위 순이다(명세 "진단용 검색과 단계"). 리랭커에 보내는 글은 검색과 같다(온전한 절 경로를 붙인 글).
- [x] 리랭커의 끝점은 `RAG_EVAL_RERANKER_URL`이다. 이 티켓에서 끝점이 없는 전체 실행은 종료 코드 1과 빠진 이름을 낸다. 끝점 없이 리랭크 기록만으로 도는 길은 07이 더한다.
- [x] 보고서의 마지막 단계는 리랭크 뒤다. 유형 표지와 필터 질의의 줄을 마지막 단계에 대해 내는 규칙(06)이 이 단계를 쓰게 한다.
- [x] `score_distribution`(명세 "최소 점수"): 합친 뒤의 후보 전부의 리랭크 점수를 기대 근거에 닿은 조각과 그렇지 않은 조각으로 갈라 0.05 폭 구간마다 세고, 문턱 0.05부터 0.95까지 0.05 간격마다 상위 5 적중률, 상위 10 적중률, 결과가 비는 질의의 비율, 질의마다 남는 조각 수의 평균을 낸다. 빠른 실행의 보고서에는 이 칸이 없다. `report.md`에 같은 표를 싣는다.
- [x] 표면 시험: `--through rerank`의 보고서에 리랭크 뒤 줄이 있다, 리랭크에서 순위가 바뀐 질의의 적중률이 리랭크 뒤 줄에 반영된다(TEI 스텁의 결정적 점수로 순위를 정한다), `score_distribution`의 구간 수와 문턱별 값이 손으로 계산한 값과 같다(스토리 27).
- [x] 검사 넷이 초록이다.

## Comments

- 시험 순서를 솔직히 적는다. 앱 시험(`tests/app/test_eval_run.py`, `test_eval_score_distribution.py`)은 시험을 먼저 쓰고 빨강을 본 뒤 구현했다. 표면 시험(`tests/tools/test_search_eval_run.py`)은 구현 뒤에 써서 처음부터 초록이었다. 그 빨강은 변이 표 `probes/eval_full_run_mutations.toml`로 확인했다.
- 실제 리랭커 TEI(Docker와 GPU)를 띄운 실행은 하지 않았다. 표면 시험은 `TeiStub`의 결정적 점수를 쓴다. 실제 서버와 모델 이름 확인(`/info`)의 길은 스텁이 `model_id`로 흉내 낸다.
- 점수 구간은 나눗셈이 아니라 `number / 20`의 하한 목록과 `bisect_right`로 찾는다. `0.15 / 0.05`가 `2.9999999999999996`이라 나눗셈은 경계 점수를 앞 구간에 센다. 문턱은 그 값 이상을 남긴다.
- `QueryOutcome.scored`(합친 뒤 후보 전부의 리랭크 점수와 닿았는지)를 더했다. 06이 `lost_in_rerank`를 가를 때 쓰고, 합친 뒤 후보 밖의 조각을 보려면 06이 `QueryOutcome`을 더 넓혀야 한다(06 `## Comments`).
- 보류: 임베더 풀과 리랭커를 짓는 조립의 되풀이(`adapters/eval_run.py`의 `_evaluate`)는 모으지 않았다. 06이 조립을 다시 건드릴 때 모은다.
- 셀프 리뷰(표준·명세 두 축)에서 고친 것: 시험 독스트링의 거짓 하나(문턱이 앞의 다섯을 걷어내면 순위가 오른다), 낡은 서술(`app/eval_run.py`와 시험의 모듈 독스트링, README의 tools 줄, 리랭커 끝점을 "없어도 된다"고 적은 `eval_environment.py`·`compose.eval.yml`·`search_eval.py`), `report.md` 표를 제목만 보던 시험(구간 표 두 줄과 문턱 표 세 줄의 값까지 본다).
- 셀프 리뷰에서 남긴 것(Minor): `app/eval_run.py`의 `_rerank`가 `app/search.py`의 `_rerank`와 글 만들기·예외 처리·문구를 되풀이한다("검색과 같다"를 한쪽 변경이 깨뜨릴 수 있다). "전체 실행인가"가 `through`, `reranker_url is None`, `reranker is None`, `Stage.RERANK in stages`로 되판정된다. TEI 설정 불일치(`/info`의 모델 불일치)도 "후보를 리랭크하지 못했다"로 뭉친다(검색과 같은 처리). `EvalReport.score_distribution` 필드가 같은 이름의 함수를 가린다. 모두 동작을 바꾸지 않는 모양 문제라 06이 `run` 조립을 다시 건드릴 때 함께 본다.
