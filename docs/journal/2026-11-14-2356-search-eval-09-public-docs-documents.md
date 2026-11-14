# search-eval 09: 공공 문서 묶음의 문서와 문서 목록 · 2026-11-14

티켓 `.scratch/search-eval/issues/09-public-docs-documents.md`를 구현한 기록이다. 브랜치는 `feature/09-public-docs-documents`다. 티켓 09는 코드가 아니라 데이터(`evals/public-docs/`)를 커밋하는 티켓이라 후보 목록을 사용자가 두 번 확정하는 자리에서 멈추며 진행했다. 세션 도중 컨텍스트가 압축되었다. 이번 요청의 범위는 PR과 병합까지이고, 후보 목록의 사용자 확정에서 멈추는 조건이 붙었다.

## 준비

- 읽은 것: `.claude/skills/implement/SKILL.md`, 티켓 09, 명세 `.scratch/search-eval/spec.md`의 공공 문서 묶음 절과 평가 세트의 형식 절, `docs/agents/issue-tracker.md`의 프로브와 근거 절, 앞 일지 `2026-11-14-1128-search-eval-03-eval-index-command.md`.
- 후보를 고르기 전에 파싱 확인 프로브 `.scratch/search-eval/probes/public-docs/parse_check.py`를 먼저 커밋했다(커밋 `10f8860`). 제품 파서로 후보를 읽어 블록, 글자, 표, 제목, 쪽 수를 재는 읽기 전용 스크립트다.
- 순서는 사용자가 정했다. 법령 외(공공누리 제1유형 보고서)를 먼저 하고 법령은 21시 뒤에 받는다(`AskUserQuestion`의 답 "법령 외 먼저, 법령은 21시 뒤").
## 한 것

- 1차(커밋 `05d9d9b`): 공공누리 제1유형 보고서 열네 개(PDF 일곱, HWPX 넷, DOCX 셋)와 `documents.json`의 해당 항목. 사용자가 "확정"했다.
- 2차(커밋 `a122fe9`): 법령 스물아홉과 행정규칙 셋, 모두 서른둘. PDF 열여섯과 HWPX 열여섯이다. 사용자가 "32개 그대로 확정"했다. 국가법령정보센터의 저장 단추를 Playwright로 눌러 받았다.
- 묶음 전체: 문서 46개, 17,042,352바이트. 형식은 PDF 23, HWPX 20, DOCX 3이다. 법령과 시행령이 짝을 이루는 것이 11쌍이고, 표가 있는 문서는 보고서 11개다(법령은 `tables=0`). `index`(기본 구성, GPU TEI `turing-1.9.4`)로 센 조각 수는 2,193개로 상한 3,000개 이하다.
- `evals/public-docs/documents.json`(열 칸: key, title, publisher, source_url, license, license_evidence, downloaded_at, sha256, bytes, updated_at), `eval-set.json`, `config.json`, 비어 있는 `evidence.jsonl`·`queries-human.jsonl`·`queries-keyword.jsonl`, `.gitattributes`의 `evals/public-docs/documents/** binary`.
- 문서: 티켓 09를 `done`으로 두고 수용 기준 일곱을 모두 체크했다. 프로브 README에 `public-docs/parse_check.py` 행을 더했다. `README.md` 트리와 `.scratch/plan-head.md` 목표 배치에 `evals/public-docs/` 줄을 더했다.
- 병합: 브랜치를 `origin/dev`와 합쳤다. `README.md`와 `.scratch/plan-head.md`의 충돌은 이 브랜치의 `evals/` 줄과 dev의 `tools/` 줄을 둘 다 남기는 것으로 풀었고, `.scratch/plan.md`는 `tools/plan_table.py`로 다시 만들었다.

## 정한 것

- 이용 조건 근거: 법령은 국가법령정보센터 「법적효력 및 저작권」 안내(정책 1항)와 저작권법 제7조 1호·2호(`laws/저작권법.pdf` 4쪽에서 원문을 확인했다). 보고서는 data.go.kr JSON-LD의 `공공저작물 : 출처표시 (제 1유형)`이다.
- 법령 파일은 내려받을 때마다 생성되어 바이트와 `sha256`이 달라지지만 파싱한 글은 같다(두 파일로 확인했다). 그래서 `sha256`은 이 묶음이 가진 파일의 것이고 원천의 안정된 값이 아니다.
- `updated_at`은 법령이 공포일이고, 보고서는 열넷 가운데 열은 포털의 자료 기준일(JSON-LD `alternateName`의 끝 `_YYYYMMDD`)이다. 네 개는 파일 안에서 확인했다. 열 개의 값이 문서가 실제로 고쳐진 날은 아니라는 점은 티켓 10과 명세에 넘겼다.
- 규모는 명세의 "법령 서른쯤 + 보고서 열쯤"에서 보고서가 열넷으로 넘쳤다. 명세의 상한(문서 30 이하, 조각 3,000 이하, 30MB 이하)은 지켰고 이탈은 티켓 Comments에 적었다.
- CPU TEI는 `index`에서 시간 제한 60초(제품 기본 `tei_timeout_seconds`)에 걸려 `embedding_unavailable`로 끝났다. 평가 도구는 이 시간 제한을 바꾸지 못하므로 GPU TEI로 색인했고, 이 점은 티켓 10과 명세에 넘겼다.

## 셀프 리뷰

`code-review` 두 축(표준 축 Sonnet 5.5 / high). 범위는 base `origin/dev`, 커밋 둘(`10f8860`, `05d9d9b`)과 아직 커밋하지 않은 법령 서른둘, `documents.json`, 티켓 09, 프로브 README다. Critical과 Major는 없었다.

- 고친 것(Minor): 티켓 Comments의 근거 문장을 손으로 본 것과 어림한 것으로 나눠 적었다. `parse_check.py`의 출력 칸을 머리 줄과 맞췄다(`pages`를 `max_page`로, 오류 줄의 칸 수). 프로브 README에 `parse_check.py` 행을 더하고 GPU TEI(`--gpus all`)로 돈 사실과 `ldcache` 오류를 적었다. `updated_at`과 CPU 시간 제한은 위 "정한 것"대로 티켓 10과 명세에 넘겼다.
- 남긴 것: 없다.
- 다시 돌린 것: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, `uv run python tools/search_eval.py validate evals/public-docs`와 `validate --indexed`. 전체 시험은 커밋의 pre-commit이 돌았다.

## PR 직전 리뷰

- 보안(`/security-review`): 이 브랜치 자체의 변경은 데이터 파일과 읽기 전용 프로브뿐이다. 프로브에는 하위 프로세스, 네트워크, 쓰기 호출이 없다(`subprocess`, `os.system`, `eval`, `exec`, `pickle`, `open(`, `requests`, `httpx`, `urllib`를 찾았으나 맞는 줄이 없었다). `evals/public-docs/*.json`의 비밀 패턴 한 건은 `config.json`의 청킹 설정 이름(`max_tokens`, `overlap_tokens`)이다. `documents.json`의 `source_url`은 `www.law.go.kr` 32건과 `www.data.go.kr` 14건뿐이다. 확신도 높은 취약점은 없었다.
- CodeRabbit CLI(`coderabbit review --agent --include-untracked --base origin/dev`, `review_completed`, `Seat: not assigned`): 지적 네 건, 유효 0. CodeRabbit이 잡은 merge-base가 이 브랜치의 기준보다 앞서 search-eval 04부터 06까지(origin/dev에 이미 병합된 #42~#44)의 `src`·`tests`까지 검토해 네 건 가운데 셋이 이 PR의 몫이 아니다. `git diff --cached origin/dev -- src tests tools`는 비어 있다.
  - 보류(이미 dev에 있는 코드, Major): `adapters/eval_run.py`의 `check_ready`가 승인한 판과 `open_evaluator`가 고른 평가 판의 구성이 같다는 보장이 없다는 지적이다. 04~06의 몫이라 이 PR에서 고치지 않고 아래 "다음"에 적었다.
  - 보류(같은 이유, Minor): `app/eval_run.py`의 `_probe_filter`가 마지막 질의에 필터가 없으면 평가 중 판 변경을 못 볼 수 있다는 지적이다.
  - 오탐: `parse_check.py`의 `read_bytes()`에 크기 상한이 없다는 지적. 입력은 사용자가 확정한 46개(합 17MB, 가장 큰 파일 약 3MB)이고 30MB 상한은 묶음 합계 기준이다. `check_indexed_documents.py`가 파싱 본문을 메모리에 쌓는다는 지적. 이 PR의 변경이 아니고 이 묶음 규모(글자 수 수십만 자)에서 문제가 아니다.
  - 서브에이전트가 따로 확인한 것: `documents.json` 46개의 바이트와 `sha256`이 실제 파일과 모두 같다. 키와 파일 집합이 일치하고 `sha256`과 `source_url`에 중복이 없다. 형식 합계 PDF 23, HWPX 20, DOCX 3과 17,042,352바이트, 보고서 14개 10,970,917바이트가 티켓의 수치와 맞는다. 개인정보 보호법 시행령과 저작권법 시행령이 둘 다 제36804호(2026-11-10), 주택임대차·상가임대차 시행령이 둘 다 제36423호(2026-06-23)로 번호가 겹치는데, HWPX 본문에 같은 번호와 날짜가 실제로 적혀 있어 모순이 아니다. 티켓 `## Comments`의 수(14+32=46, 29와 3, 11쌍, 2,193개)가 서로 맞는다. 이메일, 키, 토큰, 로컬 경로는 `evals/`와 `.scratch/search-eval/`에서 나오지 않았다. `parse_check.py`는 `OSError`를 잡지 않아 한 파일이 막히면 전체가 멈추지만 프로브라 Minor 이하다.
  - 이 반영이 새로 쓴 사실 문장: 없다(코드와 데이터를 고치지 않았다).

## 검증

- 손으로 친 것: 위 셀프 리뷰의 다섯 명령, `uv run python tools/search_eval.py validate evals/public-docs`(통과), `validate --indexed`(통과, 조각 2,193개).
- 커밋의 pre-commit이 전체 pytest를 돌렸다. 법령 커밋의 첫 시도(25분 41초)는 3,983개 통과, 2개 실패였다. `tests/contract/test_search_complete.py::test_리랭커가_순서를_바꾸고_점수는_리랭크_점수다`는 MCP 호출의 `httpx2.ReadTimeout`으로, `tests/app/test_job_lease.py::test_임대를_잃은_것이_드러나면_처리를_멈추고_문서에도_작업_행에도_쓰지_않는다`는 `time.monotonic() - started < 5`가 7.8초로 실패했다. 이 변경은 코드를 바꾸지 않았고 두 시험을 따로 돌리면 3분 6초 안에 통과했다. 같은 PC에서 GPU 색인과 다른 세션의 검사가 돌고 있었다(부하는 재지 않았다). 같은 커밋을 다시 돌려 927초에 초록이 되었다. 이 일은 회고가 `load-sensitive-time-tests`로 센다.
- 시험 순서: 이 변경은 코드가 아니라 데이터라 새 시험이 없다. 데이터의 판정자는 `validate`와 `validate --indexed`다(원칙 I의 표면에 해당하는 검사).
- 시도한 것 가운데 되돌린 것: 첫 커밋 시도는 출력을 `/dev/null`로 버리고 `; echo started`를 이었더니 pre-commit 실패가 종료 코드 0으로 보고되고 까닭이 남지 않았다. `git log`로 HEAD가 그대로인 것을 보고서야 알아 `git commit -F <파일>`로 출력을 남기며 다시 돌렸다.
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)이고 이 세션은 워크트리라 당기지 않았다.

## 봇 회차

(PR을 연 뒤에 적는다)

## 회고

낸 후보 여섯. 승인 3, 기각 3, 넘김 없음.

1. Playwright 플러그인이 작업 폴더에 `.playwright-mcp/`를 만들었고 `.gitignore`에 그 이름이 없어 `git add -A`가 실을 수 있었다. 이 세션은 커밋 전에 폴더를 지웠고 스테이징을 경로로 좁혀 실리지 않았다. → 승인(더하는 것). 대기열을 `--search playwright`로 찾아 맞은 항목이 없어 새 항목 `playwright-output-folder-ignore`를 1회차로 썼다. 지워서 커밋에 실리지 않았으므로 손상이 아니고 다섯 번째 전이라 반영하지 않는다.
2. 게이트 명령 뒤에 `; echo started`를 이어 백그라운드에 띄웠더니 pre-commit 실패가 종료 코드 0으로 보고되고 출력도 버려 까닭이 없었다. 실패한 pytest의 출력을 보려고 커밋을 처음부터 다시 돌렸다(약 26분). → 승인(회차로 세는 것). `CLAUDE.md` 환경 함정의 "파이프와 `&&`·`;` 체인 뒤의 `$?`는 마지막 명령의 종료 코드다"가 낳은 닫힌 항목 `gate-pipe-read-status`의 같은 원리라 새 항목 `gate-masked-by-echo-chain`을 `gate-pipe-read-status`의 6회차로 이어 썼다. 이번 꼴은 `$?`를 읽지 않아 기존 훅이 경고하지 않는다. 커밋이 만들어지지 않았을 뿐 잃은 작업이 없어 손상이 아니다. 훅이 처방이라는 점이 분명하다.
3. 전체 pytest에서 시간 단언 시험 둘이 부하에 빨개져 pre-commit이 두 번 돌았다(25분 41초와 15분 27초). → 승인(더하는 것, 끝이 열린 결함 종류). 사례는 닫힌 `token-expiry-test-load-margin`, 열린 `serve-startup-test-load-margin`, 이 세션의 둘로 넷이다. 사례를 하나 더 고치지 않고 종류를 다루는 새 항목 `load-sensitive-time-tests`를 1회차로 썼다. 길은 둘(시간 단언을 신호 기다리기로 바꾸거나 상한을 배수로 두기, 이 값을 받아들이고 닫기)이고 게이트를 느슨하게 하는 길은 사용자에게 넘긴다.
4. 법령 커밋 메시지 초안이 형식 수를 "PDF 열넷과 HWPX 열여덟"로 잘못 셌다. → 기각. 커밋을 만들기 전에 알아채 열여섯과 열여섯으로 고쳤고 틀린 메시지는 기록에 남지 않았다.
5. `ruff` E501이 프로브 독스트링에서 걸렸다. → 기각. 린트가 쓰는 중에 바로 알렸고 줄을 다시 접었다.
6. 대기열 항목의 승인일을 2026-11-15로 잘못 적었다. → 기각. 커밋 전에 알아채 2026-11-14로 고쳤다(일회성 오타이고 같은 사건이 되풀이된 기록이 없다).

만료: `uv run python tools/queue_open_rows.py`와 `--ref origin/dev` 출력 모두 만료할 항목이 없다고 했다.

## 다음

- 이 PR이 병합되면 티켓 09는 끝이다. 이어서 티켓 10(공공 문서 묶음의 질의와 기대 근거)이 이 묶음에 질의를 채운다. 티켓 10의 `## Comments`에 이번에 넘긴 둘이 있다: `updated_at`이 보고서 열 개에서 포털의 자료 기준일이라는 점, CPU TEI에서는 `index`가 시간 제한 60초에 걸려 GPU TEI로 색인했다는 점.
- CodeRabbit이 이 PR 밖(이미 dev에 있는 04~06의 코드)에서 낸 보류 둘은 후속 확인 대상이다: `adapters/eval_run.py`의 `check_ready`가 승인한 판과 `open_evaluator`가 고른 평가 판의 구성이 같다는 보장(Major), `app/eval_run.py`의 `_probe_filter`가 마지막 질의에 필터가 없을 때 평가 중 판 변경을 못 보는 것(Minor). 이 묶음으로 전체 실행을 처음 돌리는 티켓 10이나 11이 `run` 조립을 건드릴 때 함께 본다.
- 이 묶음의 조각 수는 GPU TEI 기본 구성 기준 2,193개다. 임베딩 모델이나 청킹 구성을 바꾸면 다시 센다.
- 회차 5 이상인 열린 항목은 직전 일지(06)가 적은 셋(`measured-claim-beyond-probe`, `mutate-marker-discovery`, `crlf-from-script-edits`)과 같다. search-eval의 마지막 티켓 뒤에 `next-session` 결정표가 chore 배치로 고른다.
- 주 체크아웃 미갱신: 루트는 `dev`(97f9914)이고 이 세션은 워크트리라 당기지 않았다. 병합 뒤 `tidy-checkouts`는 다음 새 세션이 주 체크아웃에서 돈다.
