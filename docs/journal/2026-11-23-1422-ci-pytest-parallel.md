# ci-pytest-parallel: CI의 pytest를 나눠 돌린다 · 2026-11-23

source-sync 티켓 08을 병합한 세션이 이어서 한 harness 일의 기록이다(Sonnet 5.5). 브랜치는 `chore/ci-pytest-parallel`이고 티켓은 `.scratch/harness/issues/ci-pytest-parallel.md`다. 사용자가 "CI 시간 제한 문제를 이 세션에서 바로 풀까요?"에 "여기서 풀기"를 골라 시작했다. 이 세션은 PR을 열어 CI 시간을 보는 데까지다. 병합은 아직 정하지 않았다.

## 준비

- `git fetch origin` 뒤 `origin/dev`(`6601a7c`)에서 `chore/ci-pytest-parallel`을 땄다. `tools/sibling_overlap.py`는 번호와 헌법 버전 겹침이 없다고 답했다.
- 읽은 것: `ci.yml`(python 잡의 제한 15분, pytest 스텝), `pyproject.toml`의 `pytest-xdist`, `tests/conftest.py`의 템플릿 데이터베이스(작업자마다 한 번, 시험마다 `uuid4` 이름의 복제본), `tools/run_checks.py`의 `pytest_workers`와 독스트링, 대기열 `load-readtimeout-flake`·`load-sensitive-time-tests`·`manual-full-pytest-sequential`.
- 사용자에게 고르게 한 것 둘. 첫째는 "병렬로 돌리기 / 제한만 올리기 / 잡 나누기"에서 병렬로 돌리기였다. 둘째는 셀프 리뷰가 "CI는 한 프로세스"라는 옛 결정을 뒤집는다는 것과 부하 위험을 알린 뒤의 "절반으로 병렬 / 전부 써서 병렬 / 옛 결정 유지"에서 전부 써서 병렬(`-n auto`)이었다.

## 지은 것

- `ci.yml`의 pytest 스텝을 `uv run pytest -q -n auto`로 바꾸고, 까닭을 적은 주석을 달았다. 제한 15분은 그대로다.
- 시험 `test_CI_의_python_잡은_pytest_를_작업자_여럿으로_나눠_돌린다`(`tests/tools/test_run_checks_database.py`). 고치기 전에 `uv run pytest -q`에서 빨갰고 고친 뒤 초록이다. 명령을 `shlex`로 읽는 `_나눠_돌린다`가 작업자를 둘 이상 띄우는지 가르고, 입력 열두 개(나눠 돈다 다섯, 나눠 돌지 않는다 일곱)를 시험이 고정한다.
- 옛 결정을 적은 문장 셋을 고쳤다: `pyproject.toml`의 `pytest-xdist` 주석, `tools/run_checks.py` 독스트링, `tests/tools/test_run_checks.py`의 독스트링.
- 티켓에 `dev` 푸시의 취소 둘을 포함한 실행 기록 표와 뒤집는 결정, 알고 고른 위험을 적었다.

## 이 세션이 정한 것

- ADR은 쓰지 않았다. `domain-modeling`의 세 조건 가운데 "되돌리기 어렵다"가 빠진다(`-n auto`를 지우면 끝난다). 결정은 티켓과 문장 셋이 기록한다.
- `-n auto`는 사용자의 선택이다. 이 세션의 추천은 러너처럼 CPU의 절반이었다.

## 셀프 리뷰 (`/code-review`, 기준 `6601a7c`, 파일 2개 수정과 미추적 1개, 커밋 0개)

**고친 것**
- 명세 축 Major와 표준 축 하드 위반 1: 옛 결정("CI는 한 프로세스")을 적은 문장 셋이 거짓이 되었다(`pyproject.toml:68`, `tools/run_checks.py` 독스트링, `tests/tools/test_run_checks.py` 독스트링). 셋을 고쳤고 `한 프로세스`·`손으로 치는 pytest`로 grep한 나머지는 손으로 치는 pytest만 말한다(`.claude/skills/implement/SKILL.md` 21행 포함).
- 표준 축 하드 위반 2와 명세 축 Minor: 시험의 정규식이 `-n 0`, `-n 1`, 줄 끝 주석 속 `-n auto`, `-n auto -p no:xdist`를 통과시켰고 `-nauto`·`--numprocesses=auto`는 막았다. 명령을 `shlex.split(comments=True)`로 읽고 값을 가르는 함수로 바꿨다.
- 티켓·주석의 사실 오류: "같은 머리의 14분 43초"(그 값은 `149e5eb`의 것), "세 번째 재시도"(세 번째 시도), "13분을 넘겨 17초 차이"(17초는 잡 시간 기준이고 pytest 스텝은 13분 반 안팎), "러너도 같은 방식으로 돈다"(러너는 CPU의 절반, CI는 전부), "`tests.md`가 이미 그렇게 적는다"(그 줄은 pre-commit 러너만 말한다). `dev` 푸시 취소 둘이 빠진 것도 채웠다.
- 티켓 문구를 쉬운 말로 고쳤다("프로브는 없다"를 "측정 스크립트는 없다"로).

**남긴 것**
- ci.yml 주석과 시험 독스트링이 같은 근거 문장을 되풀이하는 냄새(Duplicated Code, 판단 항목): 주석은 `ci.yml`에서 읽는 사람의 몫이고 독스트링은 시험이 지키는 것을 적는 몫이라 둘 다 둔다.
- 병렬 시험이 DB 준비 시험 파일에 있는 냄새(Divergent Change, 약함): 헬퍼 `_CI_python_잡`이 그 파일에 있어서다. 옮기려면 헬퍼도 옮겨야 해 이 일 밖이다.
- 부하 위험은 이 PR의 CI가 보여 줄 때까지 재지 못한다. 티켓 Comments에 적었다.

**다시 돌린 명령(손으로 치는 것, 모두 초록)**: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`, `uv run pytest tests/tools/test_run_checks_database.py tests/tools/test_run_checks.py`(71개 통과), `uv run python tools/check_instructions.py`, `uv run zizmor --offline --strict-collection --config .github/zizmor.yml .`. 전체 테스트는 커밋의 pre-commit이 갈음한다.

**PR 직전 리뷰가 겨눌 문장(셀프 리뷰 반영으로 새로 쓴 것)**
- ci.yml 주석: "한 프로세스로 돌린 pytest 스텝이 13분 반 안팎이라 잡의 제한 15분을 넘긴 실행이 나왔다", "러너(`tools/run_checks.py`)는 논리 CPU 의 절반으로 나누고, 이 스텝은 러너의 CPU 전부(auto)를 쓴다".
- `tools/run_checks.py` 독스트링: "CI 도 나누게 된 것은 2026-11-23이다. 그전에는 CI 가 한 프로세스라 테스트끼리 부딪혀서 나는 실패가 이 러너에서만 났는데, 지금은 CI 에서도 난다".
- 티켓의 실행 기록 표(여섯 줄)와 "통과한 실행에도 제한까지 17초가량밖에 남지 않았다".

## PR 직전 리뷰

- **`/security-review`**: 보고할 취약점이 없다. 워크플로는 상수 인자 `-n auto` 하나만 바뀌었고 새 `env`, 식 펼침, 권한, 비밀 사용이 없다. 시험의 `shlex.split`은 저장소의 `ci.yml` 글을 읽기만 한다. diff가 작아 서브에이전트로 나누지 않고 직접 읽었다.
- **CodeRabbit CLI**(`coderabbit-review` 서브에이전트, 0.7.5, 좌석은 배정되지 않았지만 리뷰는 끝까지 돌았다): 지적 0건, 파일 10개를 다 봤다. 서브에이전트가 따로 대 본 셋의 결과는 다음과 같다.
  - `-n auto`와 부딪힐 길은 못 찾았다. 서버 시험은 `bind(("127.0.0.1", 0))`의 빈 포트를 쓰고, 데이터베이스 이름은 모두 `uuid4` 토막이 붙으며, 호스트 443을 쓰는 `tests/standalone`은 `norecursedirs`라 python 잡에 들지 않는다.
  - 시험의 `_나눠_돌린다`가 잘못 읽는 꼴 가운데 둘을 고쳤다. 붙여 쓴 `-pno:xdist`가 "나눠 돈다"로 읽히던 것(거짓 양성)은 `"no:xdist"`가 든 낱말이 있으면 나눠 돌지 않는다고 읽게 했고, `value.isdigit()`가 `"²"`에서 `ValueError`를 내던 것은 `isascii()`를 더해 막았다. 두 입력을 시험에 더했다. 나머지는 시끄럽게 실패하는 쪽이라 남겼다. 묶음 단축 옵션(`-qn auto`)은 "안 나눈다"로 읽고, `run: |` 여러 줄 꼴은 스텝이 하나라는 단언에서 빨갛다. 둘 다 거짓 음성이 아니라 실패로 드러난다.
  - 티켓의 실행 기록 표 수치가 `gh run view`의 `startedAt`·`completedAt`과 맞았다(`cc807a1`은 실행 전체 15분 13초이고 python 잡은 15분 3초에 취소됐다는 것까지 표의 서술과 같다).

## 둘째 커밋의 pre-commit

- 첫 시도의 검사 러너가 pytest 5655개 가운데 `tests/test_serve_command.py`의 `test_serve가_뜨면_JSON_Lines만_남기고_접근_로그에_쿼리_문자열을_싣지_않는다` 하나에서 "serve가 30초 안에 뜨지 않았다"로 빨갰다(pytest 스텝 999초, 직전 커밋의 705초보다 길다). 이 변경은 `serve` 경로를 건드리지 않았다.
- `RAG_TEST_DATABASE_URL`을 주고 그 파일만 홀로 돌리니 세 시험이 90초에 통과했다. 대기열 `serve-startup-test-load-margin`이 적은 사례와 같은 꼴이다(부하에서만 빨갛고 홀로 돌리면 초록). 이 PC가 이때 느렸다는 것은 같은 파일을 홀로 돌린 시간이 그 항목의 기록(14초, 78초)보다 길었다는 것으로만 안다. 부하의 원인은 재지 않았다.
- 부하 시간 시험 종류는 사용자가 닫은 채 두기로 했으므로(2026-11-15) 이 사례는 일지에만 적고 대기열의 회차를 더하지 않는다. 시험도 고치지 않는다.
- 같은 커밋의 둘째 시도(pytest 스텝 844초)에서는 다른 시험이 빨갰다. `tests/server/test_admin_pull_source_stuck_calls.py`의 `test_권한_오류도_끊긴_폴더와_같은_응답이다`가 `assert elapsed < PROMPT_SECONDS`에서 `1.547 < 1.0`으로 졌다. 그 파일 열세 시험을 홀로 돌리면 171초에 모두 통과했다. 이것도 시간을 재는 단언이 부하에서 넘친 같은 종류라 일지에만 적는다. 두 시도에서 진 시험이 달라, 한 시험의 기한만 고쳐서는 이 커밋의 pre-commit을 통과시킬 수 없다.
- CI와의 관계: CI가 `-n auto`로 돌면 같은 시험이 같은 모양으로 질 수 있다. 이 PR의 CI에서 지면 티켓 Comments의 대로 어느 작업자 수에서 졌는지 적고 작업자 수를 줄일지 사용자에게 묻는다.

## 회고

후보 여섯, 승인 셋(회차 둘, 새 항목 하나), 기각 셋, 넘김 없음. 읽은 것: 이 일지, 대기열 항목 여덟(`tools/queue_open_rows.py --search`로 찾아 같은 일로 보이는 둘을 열었다).

**승인**
- **선택 화면의 전제를 대 보지 않았다 → `grilling-premise-check` 7회차.** 병렬로 돌릴지 묻는 질문의 설명이 "시험은 이미 병렬을 전제로 짜여 있다"고 적었는데, 그 호출 앞에 읽지 않은 `tools/run_checks.py` 독스트링이 "CI는 한 프로세스로 둔다는 결정"을 적고 있었다. 사용자가 고른 뒤 셀프 리뷰가 짚어 같은 질문을 한 번 더 했다. 사건은 위 "셀프 리뷰"의 하드 위반 1이다. 조건: 사건(있음), 층(지침. 자동 검사로 옮길 수 없다. 설명의 사실을 어디에 대 볼지는 판단이다), 되돌림(PR 하나). 더하는 것이라 반영은 다섯 번째이고 이 항목은 이미 그 수를 넘어 chore 계기에 들어 있다.
- **저장소 상태 시험을 위반을 잡는 짝 없이 썼다 → `repo-state-test-without-mutation-partner` 2회차.** `.claude/rules/tests.md`의 규칙을 어겨 셀프 리뷰가 그 정규식의 구멍 넷을 짚었다. 짚은 것이 짝의 부재 자체가 아니라 부재가 낳은 결함이어서 회차로 세는 데 거친 판정이다. 조건: 사건(있음), 층(검사. 항목의 처방이 이미 `tools/check_instructions.py`다), 되돌림(PR 하나).
- **병합한 뒤 기준 브랜치의 푸시 CI를 보지 않았다 → 새 항목 `post-merge-base-push-ci-unchecked` 1회차.** `dev`의 푸시 실행 둘(`cc807a1`, `6601a7c`)이 15분 제한에서 취소되고 `verify`가 빨갰는데 병합 절차에 그것을 보는 단계가 없어 병합한 세션이 모르고 끝났다. 손상(병합 뒤 `dev`의 검사가 빨갛다)이라 한 번으로 반영한다. 이 PR은 CI 시간을 고치는 일이어서 싣지 않고 대기열에 두었다. 처방은 `merge.md`의 한 줄(층은 지침이다. 이 판정에는 사람이 보는 훅이나 검사가 아직 없다)이고, 새 지침 문장이라 다음 chore를 기다린다. 사용자가 순서를 올리면 바로 간다.

**기각**
- 08의 일지가 취소된 두 시도를 적지 않았다: 이 티켓의 실행 기록 표가 그 기록을 채운다(이미 고쳤다).
- 워크트리 가드가 복합 git 명령을 거절했고 Grep 훅이 `.env`에 닿는 glob을 거절했다: 가드가 그 자리에서 막고 알렸다. 사건 비용이 한 호출씩이다.
- 복사한 주석이 이 저장소에 없는 agent-os의 ADR 0035를 가리킨다: 이 저장소의 `retro` 스킬 머리 주석이 이미 "괄호 속 번호는 agent-os의 기록"이라 적고, 이 세션에서 든 비용이 한 번의 확인이다.

## 다음

- 이 브랜치로 PR을 열어 CI의 `python` 잡 시간과 pytest 스텝 시간을 본다. 15분 안에서 줄지 않았거나 시험이 작업자 수 때문에 깨지면 티켓 Comments의 대로 작업자 수를 줄일지 사용자에게 묻는다.
- 병합은 사용자의 뜻을 받고 한다.
- 이 PR이 병합되기 전까지 `dev`의 푸시 CI는 15분에 끊긴다. 급하면 병합을 서두를 까닭이다.
