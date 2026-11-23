# docs-only-commit-narrow-pytest: 문서만 바꾼 커밋은 pre-commit이 전체 pytest 대신 문서를 읽는 시험만 돈다

**What to build:** 문서만 바꾼 커밋도 pre-commit의 검사 러너(`tools/run_checks.py`)가 전체 pytest를 돌아, 커밋을 시도할 때마다 약 7분에서 21분(434초에서 1292초)을 기다렸다(대기열 항목 `docs-only-commit-full-pytest` 12회차까지). 이 티켓은 스테이징한 파일이 전부 문서일 때만 pytest를 문서를 읽는 시험 넷으로 좁힌다. 사용자가 2026-11-23에 이 목록과 범위를 승인했고, 이 변경에는 ADR을 새로 쓰지 않는다(아래 "ADR을 쓰지 않는 까닭").

**문서의 범위.** 스테이징한 경로가 전부 아래 가운데 하나일 때만 "문서만 바꾼 커밋"이다. 하나라도 벗어나면 지금처럼 전체 pytest를 돈다.
- `.scratch/`나 `docs/` 아래의 `.md`
- `.scratch/` 아래의 프로브 출력 `.txt`, `.json`, `.tsv`, `.csv`
- 저장소 루트의 `CLAUDE.md`, `GLOSSARY.md`, `CODING_STANDARDS.md`, `README.md`

프로브의 `.py`와 `.toml`(변이 표), 셸 스크립트, `.github/`, `.claude/`, `evals/`, `deploy/`는 코드나 설정을 읽는 시험이 있어 문서로 보지 않는다. 이 범위의 파일을 읽는 시험은 넷만이 아니다. 처음에 `tests/`를 grep으로 훑어 넷을 골랐고, 파일을 열 때마다 기록하는 감사 훅을 붙여 전체 pytest를 한 번 돌려 보니 둘이 더 나왔다(아래 "감사에서 나온 것"). 목록 밖에 남는 시험은 CI의 전체 pytest가 PR에서 잡는다.

**남기는 시험.** `uv run pytest -q <아래 넷>`으로 손으로 돌려 105건이 통과했다(다섯 번 쟀고 24, 32, 49, 148, 165초다. 다른 세션이 함께 돌수록 느렸다). 전체는 약 7분에서 21분이다.
- `tests/test_plan_status.py`: 전체 계획 표가 기능 계획과 티켓에서 만든 것과 같은지, 끝 줄이 빠지지 않았는지
- `tests/tools/test_check_adr_pointers.py`: ADR을 가리킨 인용이 ADR 이력 제목과 맞는지
- `tests/tools/test_queue_open_rows.py`: 회고 대기열 항목 파일이 깨지지 않았는지
- `tests/tools/test_check_quotes.py::test_이_저장소_전체를_돌려도_끝난다`

나머지 문서 검사(지침 검사, 커밋 검사, 노트 검사, 표, 줄 구분 문자, 인용)는 검사 러너와 pre-commit이 이미 따로 돌아서 남기지 않는다.

**감사에서 나온 것.** 2026-11-24에 파일을 열 때마다 시험 이름과 경로를 적는 훅(`sitecustomize`와 pytest 플러그인)을 붙여 전체 pytest를 `-n 6`으로 한 번 돌렸다(1시간 16분). 테스트 데이터베이스가 없어 오류 480건이 났으므로 데이터베이스를 쓰는 시험은 보지 못했다. 문서 범위의 파일을 연 시험은 다음과 같다.
- 승인한 넷: `test_plan_status.py`, `test_check_adr_pointers.py`, `test_queue_open_rows.py`, `test_check_quotes.py`의 전체 시험.
- 따로 도는 검사가 같은 일을 하는 것: 줄 구분 문자, 마크다운 표, 인용의 명령줄 시험 둘, 지침 검사의 이 저장소 시험.
- 목록에도 없고 따로 도는 검사도 없는 것 둘: `test_hook_prompt_directive.py::test_알림의_규약_낱말은_원천_문서에_있다`(`docs/agents/issue-tracker.md`를 연다), `test_hook_grill_design_check.py::test_알림이_드는_용어집은_이_저장소의_용어집이다`(`docs/agents/domain.md`를 연다).

사용자가 승인한 목록은 넷이므로 이 티켓은 넷으로 둔다. 위 둘은 문서 커밋의 pre-commit에서 돌지 않고 CI에서 잡힌다. 독스트링의 "못 보는 것"에 적었고, 목록에 더할지는 사용자의 결정으로 남겼다.

**고치는 곳.**
- `tools/run_checks.py`: 스테이징한 경로를 읽는 함수와 문서 판정 함수를 더하고, 문서만 바꾼 커밋이면 pytest 검사를 위 시험 넷으로 바꾼다. 이때 `-n`(나눠 돌리기)을 쓰지 않고, 시험 데이터베이스 준비(`prepare_test_database`)도 건너뛴다. 스테이징 목록을 읽지 못하거나(스테이징 목록을 읽는 git 명령이 시간 제한을 넘기는 경우도 읽지 못한 것으로 센다), 목록이 비었으면 전체 pytest를 돈다. 좁힌 pytest가 제 시간 제한(900초)을 넘기면 전체로 넘어가지 않고 그 검사가 실패로 끝난다. `SKIP=pytest`는 그대로 통한다. 독스트링의 "문서만 바뀐 커밋에서도 pytest 를 건너뛰지 않는다(core 01 결정)" 항목은 이 변경의 결정으로 바꾼다.
- `tests/tools/test_run_checks.py`: 문서 판정과 검사 고르기의 시험.
- `.pre-commit-config.yaml` 머리 주석: "문서만 고친 커밋도 마찬가지다"를 새 동작에 맞게 고친다.
- `.claude/skills/next-session/SKILL.md`의 Docker 갈래: 문서만 바꾼 커밋은 Docker가 필요 없다는 것을 반영한다. 이 스킬 파일이 `PATCHED_SKILLS`의 덧댄 사본이면 센티널 규칙을 지킨다(`tools/check_instructions.py`).
- 옛 표현("문서만 바뀐 커밋에서도 pytest를 건너뛰지 않는다", 문서 커밋도 Docker가 필요하다는 문장)을 grep으로 찾아 잔존이 0인지 본다(`CLAUDE.md` 작업 규약 4).

**ADR을 쓰지 않는 까닭.** 문서만 바뀐 커밋에서도 pytest를 건너뛰지 않는다는 결정은 ADR이 아니라 `tools/run_checks.py` 독스트링(core 01 결정)과 `.pre-commit-config.yaml` 주석에만 적혀 있다. 헌법 `docs/constitution/operations.md`의 가드레일 절은 훅과 검사의 목록을 코드와 설정이 원천이라고 가리킬 뿐 이 결정을 적지 않는다. 그래서 그 독스트링을 고치면 결정이 바뀐다. 헌법과 계약은 건드리지 않는다.

**이번에 바꾸지 않는 것.**
- CI의 `python` 잡. 그대로 전체 pytest를 돈다. 문서 커밋에서 빠진 몫은 PR에서 잡힌다.
- 같은 파일 `tools/run_checks.py`를 대상으로 든 열린 항목 `concurrent-checks-exhaust-memory`, `scratch-compose-syntax-check`. 더하는 항목이고 다섯 번째 전이라 묶지 않는다(retro 4단계).
- 코드를 바꾼 커밋의 pytest 범위(변경한 파일에 맞춰 좁히는 일).

**대기열:** docs-only-commit-full-pytest

**Status:** in-progress

- [ ] 문서만 바꾼 커밋의 판정 함수가 위 범위대로 가르고, 하나라도 벗어난 경로, 빈 목록, 읽기 실패, 시간 제한 초과는 전체 pytest로 간다(시험이 각 경우를 본다)
- [ ] 문서만 바꾼 커밋에서 pytest 검사는 위 시험 넷만 돌고 `-n`이 없으며 시험 데이터베이스 준비를 건너뛴다. 그 밖의 커밋은 지금과 같다(시험이 본다)
- [ ] 남길 시험 넷의 경로가 실제로 있는지 시험이 본다(이름을 바꾸면 빨개진다)
- [ ] 실제 커밋으로 확인한다: 문서 하나만 스테이징한 커밋의 pre-commit에서 pytest 검사가 몇 초에 끝나고, 코드 한 줄을 섞은 커밋에서는 전체 pytest가 돈다(걸린 시간과 명령을 `## Comments`에 손으로 봤다고 적는다)
- [ ] `tools/run_checks.py` 독스트링, `.pre-commit-config.yaml` 주석, `next-session` Docker 갈래가 새 동작과 어긋나지 않고, 옛 표현의 잔존이 0이다
- [ ] 검증 명령이 초록이다: `uv run pytest`(전체, 이 티켓의 시험 포함), `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`
- [ ] 대기열 항목 `docs-only-commit-full-pytest`의 상태가 닫힘으로 바뀐다
- [ ] 일지가 있고 이 PR의 셀프 리뷰 결과를 담는다
