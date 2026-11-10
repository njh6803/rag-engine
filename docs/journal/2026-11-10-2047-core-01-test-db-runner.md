# core 01 테스트 데이터베이스 러너 일지 · 2026-11-10

티켓 `.scratch/core/issues/01-test-db-runner.md`를 구현한 기록이다. next-session 지시문이 연 새 세션(Sonnet 5.5 / high)이고 브랜치는 `feature/01-test-db-runner`다. 지시문의 이번 요청 범위는 PR과 병합까지다. 읽은 것, 정한 것, 실제 실행에서 나온 버그, 사용자가 승인한 것, 리뷰, 검증, 남긴 것, 다음을 차례로 둔다.

## 준비

- 읽은 것: 구현 스킬, 티켓, 명세 "테스트 데이터베이스와 이미지 판" 절과 Testing Decisions, `docs/constitution/tech.md`·`operations.md`, `tools/run_checks.py`와 `tests/tools/test_run_checks.py`, `tests/conftest.py`, `.github/workflows/ci.yml`, `.pre-commit-config.yaml`, 설계 일지(`2026-11-09-2125-core-design.md`)의 테스트 DB 갈래, 티켓 일지의 `## 다음`, `next-session` SKILL.md와 directive.md, 프로브 `pg-ddl/ddl_locks.py`의 컨테이너 설정.
- 작업 폴더는 `C:\project\rag-engine`이었고 주 체크아웃이 main이며 깨끗해서 워크트리에 들지 않고 이 체크아웃에서 `feature/01-test-db-runner`를 땄다. 티켓은 첫 편집으로 `in-progress`로 바꿨다.

## 정한 것

- **컨테이너는 내리지 않고 남긴다.** 설계 인터뷰의 선택("컨테이너는 커밋 뒤에도 내리지 않고 남습니다")과 같다. 프로젝트 이름을 `rag-engine-test`로 고정해 워크트리와 세션이 서버 하나를 함께 쓴다. 데이터는 tmpfs다. 내린 뒤 `prepare_test_database`가 다시 올리는 데 5.6~6.8초가 들었다(세 번, 커밋하지 않은 스크래치 스크립트, 손으로 봤다). 서버를 여럿이 쓰므로 03의 템플릿 데이터베이스 이름은 세션마다 달라야 한다. 03 티켓에 메모로 넘겼다.
- **문서만 바뀐 커밋에서도 pytest를 건너뛰지 않는다.** 까닭 둘. pytest에 문서를 읽는 저장소 상태 시험이 있어(`tests/test_plan_status.py` 등) 문서만 고친 커밋이 그 시험을 깰 수 있다. 건너뛰는 판정은 부분 커밋의 색인(`GIT_INDEX_FILE`)과 파일 분류를 새로 따져야 한다. CI는 어차피 전부 돌아 로컬에서 건너뛰면 빨강이 PR로 늦게 올 뿐이다. 대가는 Docker도 닿는 PostgreSQL도 없는 세션이 커밋을 못 한다는 것이고 next-session 결정표 아래에 Docker 갈래로 적었다. `SKIP=pytest` 우회는 막지 않는다. 이 우회로 난 사고를 일지와 대기열에서 grep으로 찾지 못했고, 판정은 CI의 `verify`가 한다. 근거와 못 보는 것은 `tools/run_checks.py` 독스트링이 원천이다.
- **서버가 답하는지는 SSL 요청으로 본다.** TCP 연결만 되는지는 답이 아니다. Docker의 포트 전달은 안쪽 서버가 없어도 연결을 받고 끊는다(가짜 서버 시험이 고정한다).
- **주소와 역할.** `postgresql://rag_test:rag_test@127.0.0.1:55432/rag_test`. `POSTGRES_USER`는 이미지가 슈퍼유저로 만들어 02~03의 템플릿 데이터베이스를 만들 권한이 있고, `tests/test_test_database.py`가 서버에 붙어 `vector` 확장과 이 권한을 본다. 스킴은 `postgresql://`(psycopg 직접 접속용)이라 SQLAlchemy 엔진은 `postgresql+psycopg://`로 바꿔 쓴다(03 메모).
- **psycopg를 dev 의존성으로 들였다.** `psycopg[binary]>=3.3,<3.4`, 설치된 판 3.3.8이고 ADR 0011이 근거로 든 프로브의 판과 같다(major 같음. 프로브 README `sqlalchemy-async/probe.py` 줄). 런타임 의존성으로 올리는 것은 SQLAlchemy와 함께 02가 하고 greenlet 휠 확인도 02의 몫이다.

## 승인받은 것

헌법 patch를 사용자에게 제안했다(`docs/constitution/tech.md` 테스트 칸의 마지막 문장이 이 티켓으로 거짓이 된다). 선택 화면의 질문과 답:

> 사용자: "tech.md 테스트 칸의 마지막 문장이 이 티켓으로 거짓이 됩니다. 아래 문구로 고치고 헌법 판을 1.1.1에서 1.1.2(patch)로 올려도 됩니까?" → "제안대로 고친다 (Recommended)" — 설명: "마지막 문장을 '검사 러너가 pytest 전에 서버가 안 보이면 compose.test.yml을 띄우고 컨테이너는 남긴다. 손으로 친 pytest는 띄우지 않는다'로 바꾸고, 판을 1.1.2로 올려 README에 까닭을 적는다."

고친 문장: "검사 러너(`tools/run_checks.py`)는 pytest를 돌리기 전에 서버가 안 보이면 `compose.test.yml`을 띄우고 준비를 기다리며, 띄운 컨테이너는 내리지 않고 남긴다. 손으로 치는 `uv run pytest`는 띄우지 않는다". 판은 1.1.1에서 1.1.2(문구 수정, patch)다. 까닭은 이 일지가 원천이다(`docs/constitution/README.md`가 판을 올린 까닭을 ADR 이력이나 일지에 적게 한다). ADR은 새로 쓰지 않았다. 스택이나 의존성의 결정이 아니라 이미 정한 결정(ADR 0006, 설계 일지 라운드 16)을 문장에 맞춘 것이다. `tools/sibling_overlap.py`는 번호 겹침 없음, 형제가 쓴 가장 높은 판 1.1.1로 보고했다.

## 실제 실행에서 나온 것

러너를 처음 진짜로 돌리자 `test-db` 준비가 "띄웠는데도 답하지 않는다"로 실패했다. 컨테이너는 healthy였고 몇 초 뒤 직접 부른 프로브는 답했다. 원인은 `pg_isready`의 기본이 유닉스 소켓이라, 이미지가 처음 초기화하는 동안 TCP 없이 소켓으로만 듣는 임시 서버가 답해 `up --wait`가 일찍 돌아온 것이다. `-h 127.0.0.1`을 붙여 고쳤고(compose와 CI 서비스 컨테이너 둘 다), 내렸다 올리기를 세 번 되풀이해 통과했다(5.6~6.8초). 이 옵션을 빼면 빨개지는 시험을 더했고 compose 파일에서 옵션을 뺀 변이로 빨강을 본 뒤 되돌렸다(손으로 `sed`).

같은 실행에서 pytest는 데이터베이스 시험 하나만 빼고 2,729건이 통과했다.

## 코드 리뷰

`/code-review`로 두 축(표준 Sonnet 5.5 high, 명세)을 돌렸다. 범위는 기준 SHA c4aac94 이후 변경 13개, 미추적 3개, 커밋 0개였다.

고친 것:
- 출력 인자와 CQS(표준 Major급): `prepare_test_database`가 `environ`을 바꾸지 않고 주소를 돌려주며 실패는 예외 `DatabaseNotReady`로 낸다. `compose_up`도 같다. `main`이 환경에 넣는다.
- 비교가 글자 그대로였다(명세 축 Major급): 끝 슬래시, `localhost`, 다른 데이터베이스 이름이 compose가 여는 서버를 가리켜도 막았다. 호스트(`127.0.0.1`, `localhost`)와 포트 55432로 비교한다.
- 포트 0이 5432로 읽히던 것, 모양이 틀린 주소의 메시지가 실제 검사보다 엄하던 것, 띄우기 실패 메시지가 포트 충돌에도 "Docker를 켠다"로 시작하던 것.
- 독스트링의 틀린 서술: 164MB를 설계 일지의 어림이라 적었으나 출처가 없어 뺐다, "알리고 멈춘다"는 실제와 달라 고쳤다, "매번 몇 초"는 측정을 달았고, 사고 기록이 없다는 말은 grep을 밝혔다. 모든 커밋이 Docker를 요구한다는 두 문장(결정표 갈래, pre-commit 머리 주석)은 `RAG_TEST_DATABASE_URL`이 닿는 서버를 가리키는 반례를 달았다.
- 못 보는 것 다섯을 러너 독스트링에 적었다(역할까지 맞는지, `getaddrinfo`, Ctrl-C, 동시 러너, IPv6).
- 시험: 표준 지침대로 실패의 까닭까지 단언(러너 CLI 시험이 `uv`를 못 찾아서 빨갛다는 것을 본다), 시간 제한 600초 고정, 세션 픽스처의 실패 경로를 pytest 안에서 돌려 종료 코드와 한 줄 안내를 본다(주소 없음, 닫힌 포트), 헬퍼 이름을 한국어로.
- 문서: README의 PowerShell 갈래, `.scratch/plan-head.md`의 "core 01이 함께 한다" 문장을 지난 일로, 명세 271행의 "띄우고 내리는"을 "띄우는"으로.

남긴 것과 이유:
- `host, port`를 묶는 타입과 `Speculative Generality`류 냄새는 판단 항목이고 이 크기에서 값이 작아 두었다. 시험 코드의 반복 읽기는 `_글`·`_CI_python_잡` 헬퍼로 줄였다.
- 55432를 다른 PostgreSQL이 쓰는 경우의 안내, `getaddrinfo`의 시간 제한은 못 보는 것에 적었을 뿐 코드로 막지 않았다.
- tech.md 개정에 ADR이 필요한지: 위 "승인받은 것"의 까닭으로 일지에 적었다. 사용자가 다르게 보면 알려 주면 된다.

## PR 직전 리뷰

- CodeRabbit CLI(`coderabbit-review`)는 돌지 못했다. 자동 모드 분류기가 코드를 밖으로 보내는 호출이라며 거부해서, 우회하지 않고 재시도하지 않았다. 그 서브에이전트가 diff와 코드를 직접 읽어 낸 수동 검토(Minor 여섯)만 남았다. 운영 규약대로 `bug-perf-review`로 대신했다. 보안 축의 내장 `/security-review`는 처음에 `git diff origin/HEAD...`에서 로컬 `origin/HEAD` 참조가 없어 시작하지 못했다. `git symbolic-ref refs/remotes/origin/HEAD refs/remotes/origin/main`으로 그 참조를 만든 뒤(로컬 참조만 바꿨고 원격에는 닿지 않았다. 지우려면 `git symbolic-ref --delete refs/remotes/origin/HEAD`) 다시 돌려 식별 서브에이전트 하나가 확신 8 이상의 취약점 없음으로 돌려보냈다(셸 없는 고정 인자 `subprocess`, 사용자 주소가 메시지에 실리지 않는 것, `127.0.0.1`에만 여는 포트, `${{ }}` 보간이 없는 CI 변경을 살폈다). 보고된 취약점이 없어 거짓 양성 거르기 서브태스크는 돌리지 않았다.
- Critical, Major는 없었다. 고친 것:
  - `server_answers`가 IDNA 인코딩에 걸리는 호스트 이름(`a..b`, 64자 넘는 레이블)에서 `UnicodeError`를 흘려 러너가 트레이스백으로 끝나고 나머지 검사가 하나도 돌지 않던 것(`bug-perf-review`가 `uv run python -c`로 재현). `(OSError, UnicodeError)`로 잡고 시험 둘을 더했다.
  - 준비한 주소를 `os.environ`에 넣는 한 줄을 어느 시험도 단언하지 않던 것. `main`을 직접 불러 검사들이 물려받을 환경을 보는 시험을 더했다. 두 고침은 되돌린 변이로 빨강을 확인하고 복원했다(세 시험 빨강).
  - 독스트링 "못 보는 것": Windows에서 Ctrl-C가 docker를 끝내는지의 단정을 POSIX만 코드로 안다고 고쳤고, 쿼리의 `host`·`port`·`hostaddr`와 다중 호스트와 유닉스 소켓 주소(6), 워크트리마다 `compose.test.yml`이 다를 때 컨테이너가 다시 만들어지는 것(7)을 더했다. 고정하지 못한 항목은 까닭과 함께 적었다.
- 남긴 것: `postgresql+psycopg://` 스킴 거부는 03 메모가 이미 다룬다. `test-db` 준비가 다른 검사를 직렬로 막는 것은 5~8초라 값이 작다(이미지를 처음 받을 때만 길다). `.cmd`를 ASCII로 쓰는 시험은 이 PC(`C:\Users\User`)와 CI에서 걸리지 않아 두었다.

## 검증

- 러너 `uv run python tools/run_checks.py`를 세 번 돌렸다. 첫 번째는 healthcheck 버그를 만나 `test-db`가 빨갰고, 두 번째는 모든 검사 초록(pytest 226초)이었다. 리뷰 반영 뒤의 판은 커밋 때 훅으로 다시 본다(리뷰 반영 뒤 `ruff check`·`ruff format --check`·`pyright`는 초록이었고, 손댄 시험 57건은 통과했으며 데이터베이스 시험 하나는 주소 없이 돌려 오류 1건이 났다. 러너 밖에서 주소 없이 돌리면 나야 하는 오류다).
- 실제 커밋 훅 실행: 첫 커밋(15d35c2)에서 `test-db`와 pytest(248.8초)를 포함한 모든 검사가 초록이었다. 리뷰 반영 뒤 커밋(476b1c6)도 `test-db`와 pytest(154.9초)를 포함해 모두 초록이었다. CI의 `python` 잡 결과는 PR의 검사 목록이 원천이라 이 일지에 옮기지 않는다.

## 회고

후보 여섯을 냈다. 승인 둘(둘 다 대기열 회차 더하기, 이 세션에서 반영하는 것은 없다), 기각 넷, 넘김 없음이다. 사용자에게 묻는 것은 없다. 만료할 항목은 없었고(`queue_open_rows.py`, 열린 항목 19개), 회차 5 이상은 `spec-review-transition-crossing`(8회차) 하나로 이 세션의 일이 아니다.

승인:
- **출처 없는 수치와 재지 않은 시간을 독스트링에 적었다.** 사건: 러너 독스트링의 용량 어림(164MB)과 "매번 몇 초"를 표준 축 리뷰가 잡았다. 이미 있는 지침(`docs/agents/issue-tracker.md` 프로브와 근거 절)을 어긴 사건이라 회차로 센다. 간 자리: 대기열 `measured-claim-beyond-probe`에 3회차를 더했다. 앞 둘은 명세 문장이었고 이번은 코드 독스트링이라 처방(`to-spec`)이 닿지 않는다는 것을 항목 본문에 적었다. 층과 되돌림은 항목의 처방이 정한다. 더하는 것이라 문턱(다섯 번째)을 지나지 않아 반영하지 않는다.
- **게이트 뒤의 `$?` 경고가 게이트가 아닌 명령의 `$?`에도 떴다.** 사건: `sibling_overlap.py --journal; echo exit=$?; …; queue_open_rows.py > 파일; echo q_exit=$?`에서 첫 `$?`를 바로 읽은 뒤인데 둘째 `$?`에 경고가 떴다. 훅의 거짓 양성이라 고침이다. 간 자리: 대기열 `gate-pipe-read-status`에 4회차를 더했다(이미 사용자가 승인한 항목이다). 이 세션에서 훅을 고치지 않는 까닭은 이 티켓의 범위 밖이기 때문이다.

기각:
- `pg_isready`가 유닉스 소켓을 보던 healthcheck 결함: 이미 시험이 고정한다(`test_준비_신호는_TCP_로_본다`, 변이로 빨강 확인). 사건 하나로 고쳤다.
- 40줄 넘는 heredoc을 훅이 막은 것: 훅이 그 자리에서 막았고 Write로 돌아갔다.
- 한글이 든 `tmp_path`에 `.cmd`를 쓰다 난 `UnicodeEncodeError`: 시험이 그 자리에서 빨개졌고 이 시험 하나에 한정된다. 같은 사건이 되풀이되면 그때 센다.
- 리뷰가 잡은 표준 위반(출력 인자, CQS, 글자 그대로 비교), 닫힌 주장("모든 커밋이 Docker를 요구한다"), 계약 변경이 거짓으로 만든 옛 문장(`plan-head.md`, 명세 271행): 모두 리뷰가 제 몫을 한 것이다(`CODING_STANDARDS.md`와 `code-review`의 주장 검증 목록이 판정한다). 회차에서 뺀다.

## 다음

- core의 프론티어는 02(계약)다. 02는 이 티켓이 병합되면 풀리고 01을 뺀 모든 core 티켓을 막는다. ADR 0007 Consequences 두 문장의 이력·포인터를 사용자에게 제안하는 수용 기준을 들고 있다.
- 03 티켓 머리의 "01이 넘긴 것"(템플릿 데이터베이스 이름, xdist 작업자, 스킴)을 03이 읽는다.
- 이 티켓 뒤 모든 커밋은 Docker가 켜진 기계가 필요하다. 클라우드 세션에서는 열지 않는다.
