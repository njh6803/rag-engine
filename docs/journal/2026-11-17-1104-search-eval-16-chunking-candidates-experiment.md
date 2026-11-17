# search-eval 16: 조각 크기·겹침과 후보 수 설정 실험 · 2026-11-17

티켓 `.scratch/search-eval/issues/16-chunking-candidates-experiment.md`를 진행한 기록이다. 브랜치는 `feature/16-chunking-candidates-experiment`, base는 dev다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 워크트리 `16-chunking-candidates-experiment`에 들어와 진행했다. 나란히 도는 형제 티켓은 13, 17이고 20은 이미 병합됐다. 이 티켓은 구현이 아니라 실험이라 제품 코드(`src/`)와 계약은 건드리지 않았다.

## 한 것

- 조각 상한·겹침 256·32, 512·64(기본), 512·128, 1024·128을 각각 새 데이터베이스(`rag_eval_c...`)에 색인하고, 기본 청킹에서 후보 수 20, 50(기본), 100을 같은 색인으로 빠른 실행(`run --through fused --records off --config`)했다. 묶음의 `config.json`과 추론 기록은 건드리지 않았다.
- 보고서, 구성 파일 여섯, 실행 스크립트, 요약 표(`summary.md`, `summarize.py`가 만든다), 걸린 시간(`timings.tsv`)을 `.scratch/search-eval/probes/experiments/chunking-candidates/`에 두고 프로브 README 표에 행을 더했다.
- 합친 뒤 줄의 상위 5 적중률(사람 질의 / 키워드형 질의, %): 256·32는 69.7 / 77.4, 512·64(기본)는 83.2 / 80.6, 512·128은 82.6 / 77.4, 1024·128은 83.2 / 80.0, 후보 20은 81.3 / 84.5, 후보 100은 82.6 / 81.9다. 질의 한 개가 0.65%p라 1~2개 차이는 우열을 말하지 않는다.
- 판단용 숫자: 기본 구성의 키워드만 줄 상위 5 적중률은 사람 질의 49.7%, 키워드형 질의 58.7%다. 필터 질의는 사람 질의 목록에만 20개 있고, HNSW 계획의 벡터 후보 부족은 여섯 구성 모두 0건이다.
- 숫자 표를 사용자에게 보이고 멈췄다. 사용자의 답은 "유지"였고, 설정 기본값, 명세, `config.json`, 추론 기록, 기준 보고서는 고치지 않았다.

## 정한 것

- 폴더를 `experiments/` 바로 아래가 아니라 `experiments/chunking-candidates/`에 둔다. 티켓 17이 같은 `experiments/` 아래를 쓰므로 충돌을 피하려는 것이다.
- 후보 수 20·100은 조각 크기가 같아 새 데이터베이스를 만들지 않고 `c512-64`의 색인을 썼다(`compose.eval.yml` 머리 주석의 길). 티켓의 "구성마다 새 데이터베이스"에서 벗어난 것이라 티켓 Comments에 적었다.
- 같은 시각 티켓 17 세션이 띄운 임베딩 TEI(포트 18093)를 읽기 전용으로 함께 썼다. PostgreSQL은 이 실험 전용으로 따로 띄웠다(`compose-postgres.yml`, 포트 55463). 그래서 걸린 시간은 GPU 단독 값이 아니다.
- 1024·128 색인은 도구의 코드 기본값(TEI 배치 32, 시간 제한 60초)에서 끝나지 않았다. 그 구성만 커밋하지 않은 임시 변경(`settings.py`의 배치 8, 시간 제한 120초)으로 다시 돌린 뒤 되돌렸다. 보고서의 `meta.commit`에는 이 변경이 보이지 않아 README와 티켓 Comments에 적었다. 원인(요청 크기인지, 그 시각의 GPU 공유인지)은 가르지 않았다.

## 검증

- `uv run python tools/run_checks.py`가 전부 통과했다(pytest 707초). 커밋마다 pre-commit이 같은 검사를 다시 돌려 통과했다.
- `summarize.py`는 ruff와 pyright strict가 통과하고, 출력이 커밋한 `summary.md`와 바이트 단위로 같다.
- 기본 구성(`c512-64`)의 합친 뒤 줄은 `baseline-fast.json`과 상위 1·3·5·10 적중률, MRR, 재현율, 놓친 질의의 수가 같다. nDCG@10은 최대 0.0002 다르다. 단계별 줄(벡터만·키워드만)은 질의 1~2개씩 달랐다. GPU에서 임베딩을 새로 계산한 탓으로 보지만(어림) 가르지 않았다.

## 셀프 리뷰

`/code-review`(표준 축과 명세 축, 서브에이전트)를 돌렸다. Critical과 Major는 없었고, 표준 축 Minor 넷과 명세 축 Minor 둘을 고쳤다. 냄새 Nit 둘(구성 이름 목록의 반복, `main`의 평행 리스트)은 일회성 프로브 스크립트라 보류했다.

고치기 전에 제가 숫자를 다시 대 보다가 바로잡은 서술이 하나 더 있다. README가 합친 뒤 줄이 기준과 "nDCG까지 같고 MRR만 다르다"고 적었는데, 다시 재니 nDCG@10이 최대 0.0002 달랐고 단계별 줄(벡터만·키워드만)은 @1·@3·@10과 재현율까지 질의 1~2개씩 움직였다. README, 프로브 README 행, 티켓 Comments를 고쳤다. 이 고침으로 새로 쓴 문장 가운데 PR 직전 리뷰에 밀 주장은 다음과 같다.

- "합친 뒤 줄의 nDCG@10만 최대 0.0002 달랐다."
- "키워드형 목록의 키워드만 줄과 태그별 nDCG@10(최대 0.001)도 조금 움직였다."
- "사람 질의의 벡터만 줄은 @1이 0.587에서 0.581, MRR이 0.719에서 0.716으로, 키워드만 줄은 @3이 0.413에서 0.419, @10이 0.613에서 0.626(질의 2개), 재현율이 0.590에서 0.603으로 움직였다."

## PR 직전 리뷰

- `coderabbit-review` 에이전트: CodeRabbit CLI 0.7.5가 `Seat: not assigned`(Free)에서 `review_completed`까지 돌았고 지적 2건이었다. 읽기·실행 대조를 더했고 Critical과 Major는 없었다. Minor 셋을 모두 고쳤다. 스크립트가 한 구성이 실패해도 종료 코드 0으로 끝나던 것(실패한 구성을 모아 종료 코드 1로 끝내고, `c512-64`가 실패하면 그 색인을 쓰는 후보 수 구성을 건너뛴다), 데이터베이스가 이미 있을 때의 안내가 없는 코드를 약속하던 것(손으로 `DROP DATABASE`를 친다는 말로 고쳤다), 후보 수 구성이 새 데이터베이스를 만들지 않은 사유가 티켓 Comments에 없던 것이다. 오탐 1건(보고서 여섯의 `content_hash`가 서로 다르다는 지적)은 반영하지 않았다. 해시에 구성이 들어가도록 설계돼 있고 `c512-64`의 해시는 기준 보고서와 같다.
- `/security-review`(서브에이전트): 확신 8 이상의 취약점이 없었다.

## PR 봇 회차

헤드 `085e6a3`에서 검사 여덟(`CodeRabbit`, `claude-review`, `eval-fast`, `eval-full`, `image`, `python`, `ticket`, `verify`)이 모두 통과했다.

- `claude-review`: 지적 없음. 첫 회차다.
- CodeRabbit: Minor 1건이고 첫 회차라 지적마다 판단했다. `run_experiments.sh` 66행에서 `c1024-128`에만 `RAG_TEI_BATCH_SIZE=8`과 `RAG_TEI_TIMEOUT_SECONDS=120`을 환경 변수로 넘기자는 제안이다. 보류한다. 평가 도구의 설정 객체(`_IsolatedSettings`)가 환경 변수를 읽지 않아 값이 닿지 않는다(`eval_environment.py` 모듈 독스트링). 같은 우려를 README의 "알아 둘 것"과 티켓 Comments가 이미 적고 있어, 사유를 PR 코멘트에 남겼다. 뒤로 넘기는 일이 아니라 근거로 닫은 보류라 "다음"에 따로 옮기지 않는다.

## 회고

후보 여섯을 내고 승인 1, 기각 5, 넘김 0이다. 만료할 항목은 없었다(`queue_open_rows.py`가 만료할 항목 없음. 워크트리 출력과 `--ref origin/dev` 출력이 같다).

- 승인. README와 프로브 README 행, 티켓 Comments가 측정한 것보다 넓은 서술(기준과 "nDCG까지 같다", "MRR만 다르다")을 적었다. 사건: 커밋 전에 제가 숫자를 다시 대 보다가 잡았다(리뷰 보고의 지적이 아니고, 대화 기록에서 리뷰가 이 서술을 지적한 흔적을 찾지 못했다). 열린 항목 `measured-claim-beyond-probe`가 같은 꼴을 처방한다. 10회차를 더했다(9회차에서 10회차). 이미 chore 계기(회차 5 이상)라 이 세션에서 반영하지 않는다. 이번 사건은 프로브 README와 티켓 Comments에서 났고 항목의 처방 자리(`to-spec`)가 닿지 않는다는 8회차의 관찰이 이어진다.
- 기각. Bash 가드가 `cd <하위 폴더> && …`와 heredoc 파이썬을 "너무 복잡하다"며 거부한 것. 이미 있는 훅이 그 자리에서 막고 알렸고, 단순한 명령과 Write 도구로 풀어 한두 번의 호출 비용으로 끝났다.
- 기각. `summarize.py`가 ruff E501과 pyright strict에서 빨갰던 것. 린터와 타입 검사가 그 자리에서 잡았다.
- 기각. 실행 스크립트가 한 구성이 실패해도 종료 코드 0으로 끝나던 것. PR 직전 리뷰가 제 몫으로 잡았고, 일회성 프로브 스크립트라 새 판단 기준으로 올릴 사건이 아니다.
- 기각. 영어로 쓴 중간 설명에 훅이 한국어 경고를 붙인 것. 훅이 알렸고 이후 한국어로 썼다.
- 일지에만. 일지·대기열만 바꾼 커밋의 pre-commit 전체 pytest(808초)에서 `tests/test_serve_command.py`의 `serve` 시작 시험이 30초 기한에 걸려 한 건 빨갰고 나머지 4562건은 통과했다. 부하에서 빨개지는 시간 시험 종류(대기열 `serve-startup-test-load-margin`, `load-time-assertion-margins`)의 새 사례다. 이 종류는 사용자가 닫은 채 두기로 해서 항목을 만들거나 회차를 더하지 않는다. 그 시각의 부하 원인(형제 세션의 작업 등)은 가르지 않았다. 같은 시험이 두 번 연속 실패한 것이 아니라 첫 실패라 커밋을 다시 시도한다.
- 기각. 1024·128 색인이 TEI 시간 제한에 걸린 것. 환경 개선이 아니라 제품 쪽 결과다(조각 상한을 올릴 때 점검할 설정). 아래 "다음"에 적는다.

## 다음

- `search-eval` 기능은 이 PR이 병합돼도 끝나지 않는다. 티켓 13, 17이 열려 있다. 남은 티켓과 프론티어는 `uv run python tools/plan_table.py`가 만드는 `.scratch/plan.md`로 본다.
- 후보 수의 효과는 리랭커 없이는 방향이 일관되지 않았다(20이 키워드형 질의에서, 100이 사람 질의에서 낫다). 티켓 17이 리랭커를 넣은 상태로 다시 본다.
- 조각 상한을 올리는 쪽을 고르면 제품의 `RAG_TEI_BATCH_SIZE`와 `RAG_TEI_TIMEOUT_SECONDS`를 함께 봐야 할 수 있다. 1024 조각 색인이 막힌 원인(요청 크기인지 GPU 공유인지)은 가르지 않았고, 배치 8로 낸 임베딩이 배치 32와 비트까지 같은지도 보지 않았다.
- 프로브 README 표에 행을 더해, 티켓 13·17의 PR과 같은 파일에서 글자 충돌이 날 수 있다(`tools/sibling_overlap.py`가 알렸다). 나중에 병합하는 쪽이 푼다.
- 이 실험이 띄운 PostgreSQL(프로젝트 `rag-engine-eval-exp16`)과 저장소 밖 작업 폴더가 남아 있다. 보고서는 모두 커밋했으므로 병합 뒤에 `docker compose -f .scratch/search-eval/probes/experiments/chunking-candidates/compose-postgres.yml down -v`로 내린다.
- 대기열의 `measured-claim-beyond-probe`(10회차), `mutate-marker-discovery`(11회차) 같은 회차 5 이상 항목이 `next-session` 결정표의 chore 배치 조건이다. 이 기능의 마지막 티켓이 병합되면 결정표가 고를 수 있다.
