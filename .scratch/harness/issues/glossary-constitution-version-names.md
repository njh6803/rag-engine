# glossary-constitution-version-names: 헌법 판, 비워 둔 판, 판 번호를 도구, 시험, 스킬과 함께 버전으로 바꾼다

**What to build:** 사용자가 2026-11-18에 용어집의 이름을 agent-os에서 고른 이름과 맞추라는 지시문을 냈다(원문 `.scratch/glossary-names-input.md`). 그 일은 PR 여럿으로 차례로 하고, 이 티켓은 지시문 5-2의 차례 5 가운데 첫 영역이다. 앞의 다섯 PR이 병합되어 지시문 1절의 이름 가운데 "판"을 뺀 나머지와 3절의 답(색인 판 계열은 "버전으로 바꾼다"를 골랐다)이 끝났다. 이 PR은 헌법에 붙이는 번호를 가리키는 세 이름을 바꾼다. 헌법 판은 헌법 버전으로, 비워 둔 판은 비워 둔 버전으로, 판 번호는 버전 번호로 바꾼다. 새 이름은 사용자가 agent-os에서 이미 골랐고 지시문 1절이 이 이름들은 다시 묻지 않고 한다고 적었다. 이 이름의 글자를 찍거나 맞대는 도구가 둘(`tools/check_constitution_version.py`, `tools/sibling_overlap.py`)이라, 지시문 1-2가 적은 대로 도구, 그 시험, 그 출력을 읽으라고 적은 스킬과 `CLAUDE.md`의 문장을 한 PR에서 함께 고친다.

**고치는 곳.**
- 두 도구의 독스트링, 주석, 출력 문구, 에러 문구, 시험 이름과 시험이 맞대는 글자. 두 도구는 한 덩어리로 읽히므로 "헌법 판"이라는 구절뿐 아니라 같은 도구 안에서 헌법 버전을 가리키며 홀로 쓰인 "판"(판을 올린다, 판 줄, 같은 판, 가장 높은 판)도 함께 바꾼다. 그 도구가 읽는 헌법 README의 문장 꼴(`<버전>은 함께 돌던 형제 브랜치(…)가 먼저 매겨 비워 두었다`)은 "판"이 들지 않아 그대로다.
- 같은 판정을 쓰는 자리: `tools/check_ticket.py`의 독스트링과 그 시험 이름, `tools/hook_bash_gate_pipe.py`의 독스트링 한 줄, `tests/conftest.py`의 주석, `.pre-commit-config.yaml`의 훅 이름과 주석.
- 그 출력을 읽으라고 적거나 이름을 부르는 글: `CLAUDE.md`(작업 환경 함정의 브랜치 줄), `.github/PULL_REQUEST_TEMPLATE.md`, 진행 중인 기능 `release-image`의 명세와 티켓 08(`ready-for-agent`라 살아 있는 글이다. "판을 patch로 올리고"), `.claude/skills/next-session/directive.md`의 "판 번호", 루트 `README.md`의 "헌법의 판".
- "판 번호"를 쓴 `src/rag_engine/adapters/eval_judge.py`의 독스트링 한 곳.
- 헌법 `docs/constitution/README.md`의 문단 하나("판을 올린 까닭", "판 줄", "비워 둔 판"). 헌법 문구라 아래 "헌법 버전"을 따른다.
- 옛 이름이 본문에 든 ADR은 본문을 두고 이력에 한 항목을 단다(`0016`, `0019`, `0020`). `0006`은 옛 이름이 지난 이력 항목 안에만 있어 기록이라 항목을 더하지 않는다(`.claude/rules/adr.md`는 지난 이력 항목을 기록으로 둔다).
- 대기열 항목 `glossary-plain-names-left`는 이 영역이 끝났음을 맞춘다.

**헌법 버전.** 바꾸는 헌법 문장은 `docs/constitution/README.md`의 한 문단뿐이고 규칙은 그대로이며 낱말만 바뀐다. 문구 수정이라 patch로 올린다. 시작할 때 `origin/dev`의 버전은 1.3.9이고, 형제 워크트리 `06-release-docs-and-merge-procedure`가 1.4.0을 쓰고 있다(`uv run python tools/sibling_overlap.py`가 알렸다). 도구가 "올리면 이보다 높게 고른다"고 하므로 1.4.1로 올리고, 병합 전에 다시 대 본다. 올린 까닭은 ADR 0016의 이력에 적는다. 사용자가 이 영역을 지시문으로 넘기면서 README의 "판을 올린 까닭"과 "판 줄" 문장을 이번 영역의 몫으로 정했다(아래 `## Comments`). `principles.md`, `tech.md`, `operations.md`는 고치지 않는다.

**이번에 바꾸지 않는 것.** 다음 영역이 맡는다.
- 파일이나 도구의 한 시점 사본·고침본을 뜻하는 "판"(예: `sibling_overlap.py`의 "main 의 판에 글자 그대로 있는 줄", "읽은 판으로 덮어써", "옮긴 판"). 번호가 아니라서 버전으로 바꿀 수 없고, 홀로 쓰인 판을 뜻에 따라 바꾸는 영역이 가른다.
- 계약에 붙이는 번호 "판"(`principles.md` 원칙 VII과 거버넌스의 "판은 semver다", `GLOSSARY.md`의 판 항목, `tool_models.py` 같은 코드 설명), 릴리스를 가리키는 판, 색인 판 계열.
- 형제 `06-release-docs-and-merge-procedure`가 고치고 있는 `.scratch/release-image/issues/06-release-docs-and-merge-procedure.md`. 그 티켓의 "헌법 판"은 그 세션이 마칠 때 맞추거나 다음 영역이 맞춘다.
- 기록: 일지, 받은 지시문의 원문, 끝난 기능(`core`, `search-eval`, `dev-branch`)의 명세·티켓·프로브, 닫힌 항목. 열린 대기열 항목 `constitution-edit-beyond-approval`의 "판을 1.1.2로 올렸다"는 지난 사건을 쓴 글이라 기록처럼 두고, 홀로 쓰인 판 영역이 본다.
- 같은 글 안에서 계약 번호나 서버 번호를 뜻하는 "판"과 헌법 "버전"이 나란히 남는 곳: 루트 `README.md`의 "서버의 판 … 헌법의 버전", PR 서식의 "올린 판 … 헌법 버전", `eval_judge.py`의 "지시문 판 … 버전 번호". 뒤 영역(릴리스를 가리키는 판, 홀로 쓰인 판)이 한 번에 맞춘다. 그 사이에 한 문장에서 두 낱말이 섞여 읽히는 것을 알고 둔다.
- 코드의 식별자, 설정 키, 파일 이름(`check_constitution_version.py` 같은 도구 이름은 그대로다).

**대기열:** glossary-plain-names-left, rename-sweep-misses-forms

**Status:** done

- [x] 두 도구와 그 시험이 같은 새 글자를 찍고 맞댄다. 바뀐 시험 이름을 이름으로 골라 돌리는 설정(변이 표, `pyproject.toml`)이 옛 이름을 가리키지 않는지 `.scratch`까지 훑었고 결과를 일지에 적는다
- [x] 두 도구의 출력(`uv run python -m tools.check_constitution_version`, `uv run python tools/sibling_overlap.py`)이 새 글자로 나온다. 헌법 README의 비워 둔 문장 꼴을 읽는 정규식은 그대로이고 그것을 쓰는 시험이 초록이다
- [x] 이 도구들의 출력을 읽으라고 적은 스킬과 `CLAUDE.md`, PR 서식, 진행 중인 기능의 명세가 새 글자를 쓴다. 스킬과 규칙을 고쳤으면 그 파일을 원천으로 든 확인 절차(`tools/check_instructions.py`)를 다시 돌린다
- [x] 헌법 `docs/constitution/README.md`의 문단 하나만 바뀌고 버전이 1.4.1(형제가 쓴 가장 높은 버전보다 높다)이며 `Last Amended`가 오늘이다. 올린 까닭이 ADR 0016의 이력에 있다
- [x] 옛 이름이 본문에 든 ADR(0016, 0019, 0020)의 이력에 이름을 바꿨다는 항목이 있고 본문은 그대로다. `tools/check_adr_pointers.py`가 초록이다
- [x] 세 이름이 살아 있는 글에 남지 않았다. 찾은 명령과 결과는 일지에 있고, 줄바꿈으로 갈라진 꼴(Grep 도구의 여러 줄 정규식)과 줄여 부른 꼴, 낱말 하나("비워 둔", "판 번호")로도 훑었으며, 출력이 빈 검색은 일치 없음으로 읽지 않고 양성 대조를 함께 쳤다(대기열 `rename-sweep-misses-forms`). 기록, ADR 본문, 옛 이름을 일부러 적은 곳, 바꾸지 않는 것에 든 자리는 뺀다
- [x] 조사를 확인했다. "버전"과 "판"은 받침이 같아 조사가 그대로인지 정규식으로 한 번 훑었다
- [x] 시험 이름이 길어져 줄 폭(한글 두 칸, 100칸)을 넘는 줄이 없고 `ruff format --check`가 초록이다
- [x] 사용자에게 보인 바뀌는 파일 수와 실제로 바뀐 파일 수는 지시문의 어림(헌법 판 11개 파일 35곳, 비워 둔 판 5개 파일 20곳, 판 번호 3개 파일 3곳)이다. 달라지면 일지와 마무리 보고가 알린다
- [x] 손으로 치는 검사 넷(린트, 포맷 검사, 타입체크, import 경계), 지침 검사 `tools/check_instructions.py`, 형제 겹침 `tools/sibling_overlap.py`, 전체 계획 `tools/plan_table.py --check`가 초록이고, 전체 pytest는 커밋의 검사 러너가 돌아 초록이다(결과는 일지)

## Comments

- 2026-11-19, 헌법 문구를 고치는 근거. 이 세션의 첫 메시지(사용자의 글)는 이 영역을 "받은 지시문 5-2의 차례 5 첫 영역(헌법 판, 비워 둔 판, 판 번호를 도구, 시험, 스킬과 함께 "버전"으로 바꾸기)"이라 적었고, 이어받을 상태에서 일지의 다음 절에 적은 헌법 README의 판을 올린 까닭과 판 줄 문장을 이번 영역 몫으로 정했다. 그래서 `docs/constitution/README.md`의 그 문단을 고친다. 고치는 범위는 그 문단의 낱말이고 규칙은 그대로이며, 다른 헌법 파일은 고치지 않는다.
