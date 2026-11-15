# search-eval 19: 공개 데이터셋의 참고 측정 · 2026-11-15

티켓 `.scratch/search-eval/issues/19-public-dataset-reference.md`를 구현한 기록이다. 브랜치는 `feature/19-public-dataset-reference`다. `next-session` 지시문이 연 새 세션(Sonnet 5.5 / high)이 `EnterWorktree`로 워크트리 `19-public-dataset-reference`에 들어와 이어 갔다. 티켓이 멈추라고 한 지점이 둘 있어 사용자에게 물었다(이용 조건은 멈추지 않았고, 문서 용량 규칙에서 멈췄다).

## 한 것

- 이용 조건. 데이터셋 카드와 API 응답을 `curl`로 받아 읽고 해시와 읽은 줄을 프로브 README에 적었다. 라이선스는 `mit`이고 라이선스 파일이 따로 없다. 질문과 정답은 커밋하지 않고 숫자와 식별자만 커밋하므로 멈추지 않았다. PDF는 데이터셋이 싣지 않고 출처 기관의 주소만 있어 그 조건은 확인하지 않았고 저장소 밖에만 뒀다.
- 용량 규칙에서 멈췄다. 직접 주소로 받은 PDF 21개의 합이 41.5MB(십진)라 문서 합 30MiB 상한에 걸렸다. 사용자가 "참고 묶음에는 걸지 않는다"를 골랐다. 묶음 머리 `eval-set.json`에 선택 칸 `local_only`를 더했다. 참이면 `check_bundle_files`가 합 상한만 보지 않고 해시, 경로, 목록 판정은 그대로다. 도메인에는 열거형 `BundleScope`(`COMMITTED`, `LOCAL_ONLY`)로 두고 읽는 쪽이 JSON 불리언을 옮긴다. 판은 올리지 않았다(칸을 더한 것).
- PDF는 사용자가 "너가 받아줘"라고 해서 이 세션이 받았다. 직접 주소 21개는 `allganize_bundle.py fetch`로, 게시판 페이지 21개는 `fetch_landing.py`로 받아 64개 가운데 42개를 얻었다. 받지 못한 22개와 까닭은 프로브 README에 있다.
- `verify_documents.py`로 받은 문서가 그 문서인지 정답 낱말로 대 봤다. 5번(6쪽)은 쪽 수만 같고 2026-11-13자 주택시장 보도자료라 다른 문서였다. `convert --exclude 5`로 빼고 묶음을 다시 만들었다.
- 티켓 14 세션이 띄운 GPU TEI 임베딩 끝점(18083)을 사용자가 정한 대로 읽기 전용으로 같이 썼다. 이 세션은 PostgreSQL 컨테이너(`rag-eval-19-postgres`, 55439)만 따로 띄웠다. 리랭커 끝점은 부르지 않아 전체 실행(`--through rerank`)은 돌리지 않았다.
- 결과. 문서 41개, 질문 174개(300개의 58%). `index --records off` 2,074초(약 35분), `run --through fused --records off` 62초. fused @5 0.770, @10 0.822, MRR 0.679. 놓친 질의 31개 가운데 금융 16개가 모두 `figure`이고 3번과 4번 문서에서 났다. 숫자는 쪽 단위 적중이라 공공 문서 묶음의 글귀 단위 숫자와 견줄 수 없다.
- 시험은 `tests/tools/test_search_eval.py`에 다섯을 더했다. `local_only`의 합 상한 면제, `local_only`여도 해시와 목록 판정이 남는 것(둘), 불리언이 아닌 값의 거부, 커밋하는 공공 문서 묶음이 이 칸을 켜지 않는 것이다. 변이 표(`eval_set_validate_mutations.toml`)에 변이 둘을 더하고 옛 변이 둘의 원문을 새 조건으로 고쳤다(변이 3~6이 기대대로 빨강).

## 정한 것

- 첫 실행(문서 42개, 질문 177개, fused @5 0.757)은 다른 문서(5번)가 든 묶음이었다. 낡은 데이터베이스에 더하거나 빼는 길은 쓰지 않았다. `index`가 묶음에 없는 문서가 든 데이터베이스를 거부해, 새 데이터베이스(`rag_eval_b`)와 새 데이터 폴더로 처음부터 다시 색인했다.
- 쪽 수 일치를 "그 문서"의 증거로 쓰지 않는다. 판정은 정답 낱말의 겹침으로 후보를 가르고(0.15 미만), 후보는 사람이 첫 쪽의 글과 질문을 읽고 정한다. 22번(이미지 위주 책자)과 28번(pdfFactory 체험판이 글자를 겹쳐 찍음)은 후보였으나 맞는 문서로 판정했다.
- `local_only` 묶음이 문서 바이트를 모두 메모리에 올리는 길(`_read_verified`)은 고치지 않고 명세에 적었다. 이번 묶음은 합 약 124MB로 돌았다.

## 검증

- `validate <묶음>`과 `validate <묶음> --indexed`가 `문제 없음`이다. `tests/tools/test_search_eval.py`가 60개 통과한다.
- 첫 전체 검사 러너(`tools/run_checks.py`)는 pytest 1078초에 4417개 가운데 `test_serve가_뜨면_JSON_Lines만_남기고_접근_로그에_쿼리_문자열을_싣지_않는다` 하나가 "serve가 30초 안에 뜨지 않았다"로 빨갰다. 이 변경은 `serve`를 건드리지 않았고, `RAG_TEST_DATABASE_URL`을 주고 그 파일만 홀로 돌리면 두 시험이 78초에 통과했다(부하는 재지 않았다). 커밋이 부른 pre-commit의 전체 검사는 526초와 745.5초에 모두 통과했다. 일지와 대기열만 스테이징한 셋째 커밋의 pre-commit은 전체 pytest 1091초에 4417개 가운데 `test_job_lease`의 `test_임대를_잃은_것이_드러나면_처리를_멈추고_문서에도_작업_행에도_쓰지_않는다`가 `time.monotonic() - started < 5`를 6.1초로 넘겨 빨갰다(`381034.312 - 381028.171`). 이 변경은 임대 경로를 건드리지 않았고, 시간 단언이 부하에서 빨간 종류라 항목에 잇지 않고 여기에만 적는다. 같은 커밋을 다시 시도했다.
- 후속 수정 뒤 새 폴더로 `convert --exclude 5`를 다시 돌린 묶음이 `bundle2`와 `documents.json`, `evidence.jsonl`, `queries-human.jsonl`, `eval-set.json`, `convert_report.json`이 모두 같다. `verify_documents.py`의 출력은 커밋한 `verify_report.tsv`와 같다. 비지 않은 `--bundle`과 범위 밖 `--exclude`는 종료 코드 1로 거부한다.

## 셀프 리뷰

`code-review` 두 축(표준 축 Sonnet 5.5 / high, 명세 축은 세션 모델). 기준은 `origin/dev`(63fb219)이고 수정 7개와 미추적 경로 하나(`probes/allganize/`)를 봤다.

- 명세 축 Critical: 변이 표 `eval_set_validate_mutations.toml`의 변이 둘이 `if total > MAX_DOCUMENT_BYTES:`라는 옛 원문을 찾아 커밋 전 `check-mutations`가 막을 상태였다. 새 조건으로 고치고 변이를 둘 더했다.
- 명세 축 Major: 게시판에서 받은 문서 21개의 질문 111개 중 30개가 빗나갔다. 잘못된 판일 수 있다는 지적이라 정답 낱말 겹침을 재 5번이 다른 문서임을 찾았고 빼서 다시 돌렸다.
- 표준 축: `EvalSet.local_only: bool`이 분기를 고르는 불리언 칸이라 열거형으로 바꾸라는 지적을 받아들여 `BundleScope`로 바꿨다. 중복 시험(거짓이면 상한이 걸린다)을 빼고 해시와 목록이 남는 시험, 공공 문서 묶음 가드 시험을 더했다. 프로브 독스트링과 README의 사실(쪽 수 칸, 받은 날, 키 자르는 순서, 로그인 주장, 웹 아카이브 주장, 드라이버 값의 출처, MB와 MiB)을 바로잡았다.
- 남긴 것: 같은 `probes/README.md`를 티켓 14 워크트리도 고쳐 병합 때 글자 충돌 후보다(`sibling_overlap.py`의 알림).
- 이 반영이 새로 쓴 사실 문장(PR 직전 리뷰가 겨냥할 것): 프로브 README의 "받은 문서가 그 문서인지" 표, "금융이 낮은 까닭" 문단, 실행 표의 수치와 시간, 명세의 `local_only` 항목과 `validate` 절의 괄호, 티켓 Comments 여섯 항목.

## PR 직전 리뷰

- `coderabbit-review` 에이전트. `coderabbit review --agent --include-untracked --base origin/dev`가 권한 판정기에 막혔다(사유 `Unsanctioned Communication`). 우회하지 않았고 CLI findings는 0건이다. 에이전트가 diff와 파일을 읽고 `documents.csv`와 질문 CSV로 README의 숫자를 다시 계산했다. 5·22·28번 판정, 도메인별 놓친 수와 합, 탈락 지점, 문서와 질문 수가 모두 맞았다. 틀린 곳은 "글층이 없는 그림 질문"이다. 3번은 글층이 있고(58쪽에 226,769자) 글층이 없는 것은 4번뿐이다. 22번의 `paragraph` 질문 둘은 기대 쪽 글이 0자라 닿을 수 없다. 둘 다 고쳤다.
- 같은 에이전트의 Minor를 고쳤다. `convert`가 비지 않은 `--bundle`과 범위 밖 `--exclude`를 거부하고, 이름 `strip`을 맞추고, `extract_text`를 한 번만 부르게 했다. 명세에 `local_only` 묶음의 메모리 비례를 적고 "지키는 장치가 없다" 문장을 시험이 지킨다는 문장으로 고쳤다.
- 내장 `/security-review`. 보고할 취약점이 없다. `curl`은 인자 목록으로 불러 셸을 거치지 않고, 후보 주소의 `file://`는 `%PDF-`로 시작할 때만 남아 어디에도 나가지 않아 제외했다.
- `bug-perf-review`(CLI 대체). 8건 모두 Minor이고 프로브를 다른 입력으로 다시 돌릴 때만 닿는다. 실제 데이터(64문서, 300문항)에서는 일어나지 않는다. `src`와 시험의 변경에는 지적이 없고, `local_only`가 해시·경로·목록 판정을 풀지 않는다는 것과 불리언 아닌 값(`"true"`, `1`, `null`)의 거부를 재현으로 확인했다.
- 남겼다(프로브의 한계로, 이 PR에서 고치지 않는다). 같은 파일 이름이 `documents.csv`에 두 번 나오면 앞 문서가 사라진다. 깨진 PDF 하나가 `verify_report.tsv` 전체를 막는다. 쪽 번호 칸의 `isdigit()`이 `²`를 통과시켜 `int()`가 죽는다. 쪽수 칸이 숫자가 아닌 문서는 `fetch_landing`에서 늘 MISS다. 같은 출처 주소의 문서들이 같은 쪽수이면 첫 후보 파일 하나를 모두에게 둔다. 후보 상한 14개가 법원 `download()` 후보를 잘라 낸다. 기대 쪽이 없는 질문이 `median_at`에 0.0으로 든다. 원시 한글 `filename`이 latin-1로 깨져 파일 이름 우선순위가 무력하다(보류, 응답이 필요하다).
- 고친 코드와 파일의 새 사실 문장은 위 "셀프 리뷰"의 목록과 이 절의 남긴 것뿐이다.

## 회고

후보 일곱을 내고 승인 2, 기각 5, 넘김 0이다. 새로 쓴 대기열 항목은 없고 회차를 더한 항목이 둘이다. 만료할 항목은 없었다(`queue_open_rows.py`가 만료 없음).

- 승인. `serve` 시작 시험이 전체 검사 러너에서만 30초 기한을 넘겨 빨갰다(사건: 1078초 pytest의 4417개 가운데 이 하나, 홀로 돌리면 78초에 통과). 열린 항목 `serve-startup-test-load-margin`이 이미 처방한 사건이라 3회차를 더했다(`.scratch/retro-queue/serve-startup-test-load-margin.md`). 이 PR은 `serve`를 건드리지 않은 기능 PR이라 시험을 고쳐 싣지 않았다. 이 시험은 `load-readtimeout-flake`(3회차)와 같은 부하 종류의 사례다. 그 항목이 3회차부터 사례 대신 종류 전체를 없애거나 받아들이라고 적었으므로 그 항목을 반영할 chore가 함께 다룬다.
- 승인. `.scratch/search-eval` 아래 파일만 스테이징한 후속 커밋의 pre-commit이 전체 pytest를 745.5초 돌았다. 열린 항목 `docs-only-commit-full-pytest`의 2회차로 더했다. 그 항목은 게이트를 좁히는 일이라 사용자가 2026-11-13에 대기열에 두기로 했고 다섯 번째에 반영한다.
- 기각. 게시판 첨부를 쪽 수만 맞춰 받아 다른 문서(5번)를 묶음에 넣은 것. 이 PR이 `verify_documents.py`(자동 검사)와 README로 그 자리에서 고쳤고, 같은 실수가 이 환경에서 되풀이될 근거가 없다.
- 기각. CodeRabbit CLI가 권한 판정기에 막힌 것. `operations.md`가 CLI가 못 돌면 `bug-perf-review`가 같은 축을 본다고 이미 적었고 그 대체가 돌았다. 앞선 PR에서는 CLI가 돌았으므로 한 번의 거부는 회차로 세지 않았다.
- 기각. 앱 가드가 괄호와 `;`가 든 명령을 "워크트리 안에 머무는지 확인할 수 없다"며 거부했다. 앱 가드가 그 자리에서 막았고 명령을 쪼개 바로 풀렸다. 이 저장소가 고칠 수 있는 훅이나 지침이 아니다.
- 기각. 편집 직후 `ruff` 줄 길이 훅이 한글 폭 때문에 넘친 줄을 알렸다. 이미 있는 훅이 그 자리에서 알린 것이고 `rewrap_comments.py`로 풀렸다.
- 기각. 스크래치 스크립트의 pyright 진단이 대화에 새 진단으로 올라왔다. 저장소 밖 파일이라 게이트에 걸리지 않고 판단을 바꾼 것도 없는 소음이다.

## 다음

- 이 PR이 병합되면 티켓 19는 끝이다. `.scratch/search-eval/plan.md`의 `끝` 줄은 아직 없다(열린 티켓이 여럿이다). 열린 티켓은 11, 13, 14, 15, 16, 17, 18이다. 11(빠른 게이트의 CI, PR #51)과 14(GPU 리랭크 기록)는 다른 세션이 맡아 돌고 있다. 나머지는 11이나 14를 기다린다(13은 11과 12, 15는 11과 14, 16은 11, 17과 18은 14).
- 이 측정을 다시 돌릴 때: PDF와 데이터베이스는 저장소 밖(`C:\project\eval-data-allganize\`, 컨테이너 `rag-eval-19-postgres`의 `rag_eval_b`, 데이터 폴더 `run-data-b`)에 있다. 병합 뒤 이 세션이 컨테이너를 멈춰 두었으므로 `docker start rag-eval-19-postgres`로 다시 띄운다. `convert --exclude 5`로 묶음을 새(빈) 폴더에 만들고, `index`는 묶음에 없는 문서가 든 데이터베이스를 거부하므로 묶음이 바뀌면 데이터베이스와 데이터 폴더를 새로 만든다(약 35분). 이 PC의 GPU는 티켓 14 세션과 나눠 쓴다.
- 리랭커 단계(`--through rerank`)의 참고 숫자는 없다. 티켓 14가 리랭커 끝점으로 전체 실행을 돌 때 같은 묶음에 `--through rerank`를 붙여 돌리면 된다(위 데이터베이스에 이미 색인되어 있다).
- 쪽 번호가 밀렸을 수 있는 문서(22번의 `paragraph` 질문 둘)와 글층이 없는 스캔본(24, 40번)은 이 묶음의 한계로 남았다. 결과를 더 쓰려면 먼저 그 질문만 따로 보는 것이 좋다.
