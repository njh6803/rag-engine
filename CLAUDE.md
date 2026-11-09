# rag-engine

MCP를 쓰는 어떤 클라이언트에서도 쓸 수 있는 설치형 문서 검색 서버(지식베이스)다. 원칙만 아래에서 임포트하고 나머지는 경로로 읽는다.

@docs/constitution/principles.md

## 레이어
위가 아래를 import한다. 경계는 `pyproject.toml`의 import-linter 계약이 판정한다. 층은 core 설계 인터뷰가 더 정한다.
- `rag_engine.main`: 관리 명령(argparse). `serve`가 서버를 띄운다.
- `rag_engine.server`: FastAPI 앱 조립. REST 경로와 MCP 하위 앱(`/mcp`)을 한 앱이 연다(ADR 0005).

## 지도
| 문서 | 읽는 때 | 쓰는 때 |
|---|---|---|
| docs/constitution/principles.md | 항상(임포트) | 개정은 ADR과 승인 |
| docs/constitution/tech.md | 의존성을 더하거나 스택을 바꿀 때 | ADR 뒤 |
| docs/constitution/operations.md | 커밋·병합·리뷰·트래커·가드레일을 만질 때 | ADR 뒤 |
| docs/PRD.md | 범위를 정하거나 스펙이 충돌할 때 | 사용자 승인으로 |
| GLOSSARY.md, docs/adr/ | 용어를 쓰거나 결정을 바꾸기 전 | domain-modeling, 승인 뒤 |
| CODING_STANDARDS.md | 리뷰 때 | retro가 다섯 번째 반복에서 더할 때 |
| .scratch/plan.md(생성 파일), .scratch/<slug>/(기능 계획 plan.md, 명세, 티켓) | 이어서 할 때, 티켓 시작 전 | 전체 계획은 `uv run python tools/plan_table.py`가 기능 계획과 티켓에서 만든다(손으로 고치지 않는다). 기능 계획은 설계 인터뷰를 마친 세션(`설계` 줄)과 기능의 마지막 티켓을 닫는 커밋(`끝` 줄)이, 명세와 티켓은 to-spec, to-tickets가 |
| .scratch/retro-queue/(폴더, 항목마다 파일 하나. 모양과 인용을 푸는 규칙은 그 README.md) | 회고 뒤, chore 브랜치를 딸 때 | 후보가 승인될 때와 반영을 닫을 때 |
| docs/journal/ | 이어서 할 때 끝의 "다음" | 단계를 마칠 때 |
| docs/agents/ | 트래커·도메인 문서 규약이 헷갈릴 때 | setup 스킬이 |
| .claude/rules/*.md | 해당 경로의 파일을 Read 도구로 열 때 자동. Bash(cat·sed)로 읽으면 안 실린다 | 아래 로드 시점 표에 따라 |
| README.md | 사람이 처음 볼 때 | 구조가 바뀔 때 |

## 검증 명령
- 테스트: `uv run pytest` / 린트: `uv run ruff check .`과 `uv run ruff format --check .` / 타입체크: `uv run pyright` / 경계: `uv run lint-imports`
- 훅·CI만 도는 게이트: pre-commit의 검사 러너(`tools/run_checks.py`의 `CHECKS`)와 그 밖의 pre-commit 훅, CI의 `image`·`ticket` 잡과 필수 검사 `verify`.
- 손으로 치는 것과 훅·CI만 도는 게이트를 가른다. 티켓의 "검사 N이 초록"은 손으로 치는 것을 말한다.

## 작업 규약
1. 작업 전 명세·티켓·해당 ADR을 읽는다. 결정을 바꾸기 전에는 반드시.
2. 고칠 파일과 영향을 세 줄로 적고 시작한다.
3. 끝나면 검증 명령을 돌린다. 하네스를 바꿨으면 실제 실행으로 확인한다.
4. 결정이 바뀌면 그것을 참조하는 스킬·훅·rules·워크플로·명세를 같이 고치고, 옛 표현을 grep해 잔존이 0인지 본 뒤 3을 다시 돈다.
5. 아키텍처 결정은 ADR 초안을 보여주고 승인받는다.
6. 같은 테스트가 두 번 연속 실패하면 추측 수정을 멈추고 diagnosing-bugs 스킬을 쓴다.
7. 커밋 전에 /code-review로 셀프 리뷰하고 Critical·Major를 고친다.

## 교정 루프
- 내가 네 결과를 고치거나 되돌리면, 먼저 그 실수를 테스트·린트·훅 같은 자동 검사로 잡을 수 있는지 판단하고 검사를 제안한다.
- 자동 검사로 잡을 수 없는 판단 기준만 CODING_STANDARDS.md에 한 줄 후보로 올린다. 더할지는 retro가 판정한다(아래 회고 줄).
- 새 검사·훅·지침 문장과 규칙(CODING_STANDARDS.md의 줄)은 같은 실수의 다섯 번째이거나 손상(작업·데이터를 잃음, 비밀이 밖으로 나감, main이 깨짐, 다른 세션이나 체크아웃의 상태를 망가뜨림)이 한 번 났을 때 더한다. 그 전에는 대기열에서 회차를 센다. 고침(버그, 틀린 사실, 깨진 경로)은 사건 하나로 한다(retro 4단계). 지침으로 적은 뒤에도 어겨지면 막는 훅 후보다. 계기만 넣는 훅은 단계를 닫는 순간의 지침에 처음부터 붙인다(retro, next-session).
- 규칙은 강제력이 가장 높은 층에 둔다. 타입 → 린터·훅 → 아키텍처 테스트 → 지침 → 리뷰. 린터가 잡는 것을 지침에 적지 않고, 거짓 양성이 많은 규칙을 하드 게이트로 만들지 않는다.
- 회고는 retro 스킬이 정해진 계기에 스스로 돈다. 계기는 그 스킬의 설명이 원천이다. 후보의 승인도 retro가 스스로 판정하고, 나에게는 그 스킬이 넘긴 것만 묻는다. 승인됐는데 아직 반영하지 않은 것은 .scratch/retro-queue/의 항목 파일이 든다.

지침을 추가할 때는 내용보다 로드 시점을 먼저 정한다. `paths` 없는 rules와 `@` 임포트로 쪼개도 컨텍스트는 줄지 않는다.

| 성격 | 어디에 |
|---|---|
| 린터·타입체커·훅이 판정할 수 있는 것 | 도구 설정. 문서에는 실행 명령만 |
| 특정 디렉터리·파일 패턴에만 해당 | .claude/rules/*.md + paths 필수 |
| 순서 있는 다단계 절차 | .claude/skills/ |
| 반드시 실행되어야 하는 것 | 문서가 아니라 훅. 문서는 강제력이 없다 |
| 가끔 참조하는 자료 | docs/ + 마크다운 링크. @를 쓰지 않는다 |
| 매 세션 필요 | 이 파일. 넣기 전에 "이 줄을 지우면 실수하게 되나"를 묻고, 코드에서 유추 가능한 것은 넣지 않는다 |

## 환경 함정
- 파이썬은 맨 `python`이 아니라 `uv run python <파일>`로 친다. 개발 기계(Windows)의 맨 `python`은 pyenv-win shim이고, stdin(heredoc)으로 넘긴 스크립트를 출력 없이 끝냈다(2026-11-09 킥오프에서 봤다).
- 파이프와 `&&`·`;` 체인 뒤의 `$?`는 마지막 명령의 종료 코드다. 판정 명령은 파이프·체인 없이 돌린다. 훅이 경고한다.
- 커밋 전에 `git branch --show-current`로 브랜치를 본다. 같은 체크아웃을 다른 세션이 옮길 수 있다. main 위의 커밋은 훅이 막는다. 그리고 `uv run python tools/sibling_overlap.py`를 쳐 ADR 번호와 헌법 판을 형제(origin/main, 열린 PR, 형제 워크트리)와 대 본다(무엇을 보는지는 그 독스트링). 1로 끝나면 출력대로 고친다. 번호는 "옮길 번호"대로 비켜 가고, 이 브랜치의 변경에서 옛 번호를 가리킨 인용도 고친다.

## 원칙
- 답변과 문서는 한국어로 쓴다.

## Agent skills
### Issue tracker
이슈와 명세는 `.scratch/<feature-slug>/` 아래 로컬 마크다운이고, 명세·ADR·코드 주석이 근거로 드는 프로브는 그 아래 `probes/`에 커밋한다. `docs/agents/issue-tracker.md` 참조. 근거 문장(쟀다·실측·수치)을 쓸 때는 그 문서의 프로브와 근거 절을 따른다.
### Domain docs
단일 컨텍스트. 루트 `GLOSSARY.md`와 `docs/adr/`. `docs/agents/domain.md` 참조.
