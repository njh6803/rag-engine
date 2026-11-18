# glossary-constitution-version-names: 헌법 판, 비워 둔 판, 판 번호를 "버전"으로 바꾼다 · 2026-11-19

앞 세션(일지 `2026-11-19-0025-glossary-ask-remaining-names.md`)이 PR 72를 병합하고 낸 지시문으로 연 세션의 기록이다(Sonnet 5.5, high). 티켓은 `.scratch/harness/issues/glossary-constitution-version-names.md`, 브랜치는 `chore/glossary-constitution-version-names`이고, 새 워크트리 `glossary-constitution-version-names`에서 `origin/dev`(29a315c)로 브랜치를 따서 했다. 용어집의 이름을 agent-os의 결정에 맞추는 일(받은 지시문의 원문 `.scratch/glossary-names-input.md`)의 여섯째 PR이고, 받은 지시문 5-2의 차례 5 가운데 첫 영역이다. 계기, 세션을 열며 한 정리, 조사한 것, 한 것, 바꾸지 않고 남긴 것, 옛 이름의 잔존, 검증, 셀프 리뷰, 다음을 차례로 둔다.

## 계기

사용자가 아래 지시문을 첫 메시지로 넣어 이 세션을 열었다. 지시문의 핵심 줄이다.

```
받은 지시문 5-2의 차례 5 첫 영역(헌법 판, 비워 둔 판, 판 번호를 도구, 시험, 스킬과 함께 "버전"으로 바꾸기)을 티켓 .scratch/harness/issues/glossary-constitution-version-names.md로 쓰고 한다

다음 작업: … 헌법 판, 비워 둔 판, 판 번호를 도구(tools/check_constitution_version.py, tools/sibling_overlap.py)와 그 시험, 그 출력을 읽으라고 적은 스킬과 CLAUDE.md까지 한 PR에서 함께 바꾼다
이어받을 상태: 색인 판 계열(색인 판, 현재 판, 건설 중인 판, 물러난 판, 살아 있는 판, 판 전환)은 … 이번 영역에서는 건드리지 않고 마지막 영역에서 바꾼다. 일지의 "다음"에 적은 헌법 README의 "판을 올린 까닭"과 "판 줄" 문장은 이번 영역 몫이다. … PR 봇이 낸 Minor 둘(AttemptLostError 독스트링, _EXTENSIONS_PER_LEASE 주석)은 이 PR에 섞지 않는다. 형제 워크트리 06-release-docs-and-merge-procedure가 헌법 README와 tech.md를 고치고 헌법 버전 1.4.0을 쓰고 있어, 헌법 문구를 바꿀 때 버전을 얼마로 올릴지는 시작할 때 origin/dev의 헌법 버전을 다시 보고 정한다
이번 요청 범위: PR과 병합까지
```

이 일은 retro가 승인한 대기열 항목이 아니라 사용자의 직접 지시다. 티켓의 대기열 줄에는 `glossary-plain-names-left`(이름을 바꾸는 일 전체)와 `rename-sweep-misses-forms`를 적었다.

## 세션을 열며 한 정리

지시문대로 이 세션의 제목을 브랜치 이름으로 바꾸고 `tidy-checkouts` 스킬을 먼저 돌렸다. 사람에게 넘기는 것은 보고만 하고 답을 기다리지 않았다. `empty-trash`는 `.pyd` 파일을 실행 중인 파이썬 프로세스가 쥐고 있어 종료 1(WinError 5)로 끝났고, 다음 정리가 다시 본다. 그 뒤 `EnterWorktree`(name `glossary-constitution-version-names`)로 새 워크트리에 들어가 브랜치 `chore/glossary-constitution-version-names`로 바꿨다.

시작할 때 `uv run python tools/sibling_overlap.py`를 먼저 쳤다. 형제 `06-release-docs-and-merge-procedure`는 아직 병합되지 않았고, `origin/dev`의 헌법 버전은 1.3.x대였다. 형제가 1.4.0을 쓰겠다고 헌법 README에 비워 둔 문장이 있어 이 브랜치는 그 위인 1.4.1을 골랐다(아래 "한 것").

## 조사한 것

옛 이름을 줄바꿈 꼴까지 훑으려고 Grep의 멀티라인(`헌법\s+판|비워\s+둔\s+판|판\s+번호|헌법의\s+판`)을 마크다운, 파이썬, YAML 등에 걸었다. 낱말 "판"이 두 뜻으로 쓰여, 모든 "판"을 바꾸면 안 된다는 것을 확인했다.

- 헌법에 붙이는 번호나 그 번호가 오른 일(헌법 판, 비워 둔 판, 판 번호): 이번 영역이 "버전"으로 바꾼다.
- 파일이나 도구의 사본·개정(예: "main 의 판에 글자 그대로 있는 줄", "옮긴 판", "읽은 판", "커밋에 들 판(색인)", "그 판에서"): 홀로 쓰인 "판" 영역 몫이라 남겼다.

"판"과 "버전"은 받침이 같아(ㄴ) 뒤에 붙는 조사가 달라지지 않는다. 그래서 낱말만 바꿔도 "버전는" 같은 어긋남이 생기지 않는다. 지시문이 어림으로 준 수(헌법 판 11개 파일 35곳, 비워 둔 판 5개 파일 20곳, 판 번호 3개 파일 3곳)와 실제로 바뀐 파일은 같지 않다. 바뀐 파일은 수정 20개, 새 파일 2개(티켓과 이 일지)다. 지시문이 센 것에는 기록 파일이 섞여 있었고, 거꾸로 도구의 시험 이름과 출력 문자열처럼 지시문이 세지 않은 곳도 있었다.

## 한 것

문자열 바꾸기는 스크래치패드의 스크립트 하나(`판(?!정)` → `버전`)로 하고, 두 뜻을 가르는 줄은 건너뛰는 줄 번호 목록을 주어 사람이 가렸다. 건너뛴 줄은 위 "조사한 것"의 사본·개정 뜻이다.

- **도구.** `tools/sibling_overlap.py`(63줄), `tools/check_constitution_version.py`(34줄), 한 줄씩 `tools/check_ticket.py`, `tools/hook_bash_gate_pipe.py`. 출력 문자열이 바뀌었다. 예: `헌법 버전: 이 가지가 고친 헌법 파일이 없다`, `!! 헌법 파일을 고쳤는데 버전을 올리지 않았다: …`, `형제가 쓴 가장 높은 헌법 버전: …(…). 버전을 올리면 이보다 높게 고른다`, `올린 버전으로 센 헌법 …: … 비워 둔 버전이고, …`.
- **시험.** `tests/tools/test_sibling_overlap.py`(52줄), `tests/tools/test_check_constitution_version.py`(40줄), 한 줄씩 `tests/tools/test_check_ticket.py`, `tests/conftest.py`. 단언하는 출력 문자열과 시험 함수 이름(예: `test_버전을_올렸는지는_…`)을 함께 바꿨다.
- **설정과 문서.** `.pre-commit-config.yaml`(훅 이름과 주석. 이름은 `constitution version (헌법 파일을 고친 가지가 버전을 올렸는지 — tools/check_constitution_version.py)`), `.claude/skills/next-session/directive.md`, `CLAUDE.md`, `.github/PULL_REQUEST_TEMPLATE.md`, `README.md`, `.scratch/release-image/spec.md`, `src/rag_engine/adapters/eval_judge.py`의 주석 한 곳("판 번호" → "버전 번호").
- **헌법 README.** 9행의 문단("버전을 올린 까닭은 …", "비워 둔 버전의 문장", "버전을 가져가면")과 버전 줄을 고쳤다. 버전은 `1.4.1`(`Last Amended` 2026-11-19)이다. 낱말만 바꾼 patch 개정이고, 형제 06이 쓰는 1.4.0보다 높게 골랐다. 비워 둔 문장의 정규식(`RESERVED`)에는 "판"이 없어 그 문장의 모양은 그대로다.
- **ADR 이력.** 본문은 두고 이력 항목만 더했다. ADR 0016("헌법에 붙이는 번호의 이름을 버전으로 바꿔 헌법 버전을 1.4.1로 올렸다". 형제의 1.4.0을 이름으로 든다), ADR 0020("용어집이 헌법 판의 이름을 헌법 버전으로 바꿨다"), ADR 0019(이력 절이 없어 `## 이력`을 새로 만들고 "용어집이 판 번호의 이름을 버전 번호로 바꿨다"를 달았다). ADR 0006은 "헌법 판"이 이력 항목 안에만 있어 기록이라 더하지 않았다.
- **대기열.** `.scratch/retro-queue/glossary-plain-names-left.md`에 차례 5의 첫 영역을 마쳤고 헌법 버전이 1.4.1이 된다는 것, 남은 영역이 릴리스 쪽 판, 용어집의 판 항목과 홀로 쓰인 판, 색인 판 계열이라는 것을 단락으로 이었다.
- **일지 인용 감싸기.** 바꾼 줄에 든 agent-os 일지 인용(`일지 2026-09-25-01` 등)은 `sibling_overlap`가 "어디에도 없는 일지를 가리킨 인용"으로 읽어 종료 1이 났다. 바꾼 줄의 인용을 코드 스팬으로 감싸 풀었다(이 저장소에 없는 agent-os의 일지라 정당한 인용이다).

## 바꾸지 않고 남긴 것

- 색인 판 계열(색인 판, 현재 판, 건설 중인 판, 물러난 판, 살아 있는 판, 판 전환)은 마지막 영역 몫이라 건드리지 않았다.
- 홀로 쓰인 "판"(파일의 사본·개정): `tools/sibling_overlap.py`의 15곳 안팎(바꾸기 전 줄 번호 41, 83, 136, 162, 217, 228, 232, 237, 428, 551, 615, 991, 1127, 1581, 1681), `tools/check_constitution_version.py`와 그 시험의 "커밋에 들 판", `src/rag_engine/adapters/eval_judge.py`의 "지시문 판"과 "판을 올렸으면", PR 템플릿의 "올린 판". 용어집의 "판" 항목과 `principles.md`, `tech.md`, `operations.md`, `GLOSSARY.md`의 홀로 쓰인 판도 다음 영역 몫이다.
- 기록: 일지, 끝난 기능의 명세·티켓·프로브(Dockerfile 프로브 포함), 닫힌 항목, `.scratch/glossary-names-input.md`.
- 형제 06이 편집 중인 `.scratch/release-image/issues/06-release-docs-and-merge-procedure.md`. 이 파일에도 "헌법 판"이 있을 수 있으나 형제와 충돌하지 않게 건드리지 않았고, 티켓에 그렇게 적었다.
- PR 봇의 Minor 둘(`AttemptLostError` 독스트링, `_EXTENSIONS_PER_LEASE` 주석)은 별도 작업이라 섞지 않았다.

## 옛 이름의 잔존

Grep 멀티라인 `헌법\s+판|비워\s+둔\s+판|판\s+번호|헌법의\s+판`을 마크다운, 파이썬, YAML, TOML에 걸었다. 남은 곳은 모두 기록이다: 일지, 끝난 기능의 파일, ADR 이력 항목(옛 이름을 인용한 것), `.scratch/glossary-names-input.md`, 옛 이름을 따옴표로 인용한 대기열 글, 형제 06의 티켓, 이 세션이 쓴 티켓과 ADR 이력. 양성 대조로 새 이름("헌법 버전", "비워 둔 버전", "버전 번호")이 바뀐 파일에서 찾아지는 것을 봤다. 조사 어긋남(`버전는`, `버전를` 등) 정규식은 판정 단계에서 한 번 더 친다.

## 검증

손으로 친 것은 다음과 같다.

- `uv run pytest tests/tools/test_check_constitution_version.py tests/tools/test_sibling_overlap.py tests/tools/test_check_ticket.py`: 271개 통과.
- `uv run ruff check .`: 통과. `uv run ruff format --check .`: 756개 파일 이미 맞음. `uv run pyright`: 오류 0개. `uv run lint-imports`: 2개 지킴, 0개 깨짐.
- `tools/check_instructions.py`, `tools/check_adr_pointers.py`, `tools/plan_table.py --check`: 출력 없이 통과.
- `uv run python tools/sibling_overlap.py`: 종료 0(일지 인용을 감싼 뒤). 남은 알림은 형제 06도 `CLAUDE.md`와 헌법 README를 바꾼다는 것인데 다른 줄이다. 헌법 README의 버전 줄은 둘째로 병합되는 쪽에서 글자 그대로 충돌한다.
- 전체 `uv run pytest`는 커밋이 부르는 pre-commit의 검사 러너가 돈다. 첫 커밋 시도에서 러너의 검사 열(ruff, 포맷, test-db, check-ticket, zizmor, lint-imports, check-instructions, check-type-escapes, pyright 둘, run-hooks, pytest 434초)과 변이 표, 헌법 버전, 표 검사가 모두 통과했다. 그 시도는 커밋 메시지 제목이 79자라 72자를 넘어 commit-msg 훅이 막았다. 제목을 줄이고 인용 대조 경고(막지 않는다. 티켓과 일지의 따옴표 인용 셋을 따옴표 없는 서술로 풀었다)를 고쳐 다시 커밋한다.

pyright가 시험 파일의 안 쓰는 인자와 스크래치 스크립트 타입에 힌트 진단을 내지만 이 변경 이전부터 있던 것이다.

## 셀프 리뷰

`code-review` 스킬로 기준 `29a315c`(`origin/dev` 끝)에서 파일 20개(수정)와 미추적 1개(티켓), 커밋 0개를 두 축으로 봤다. 표준 축은 sonnet·high, 명세 축은 본 세션의 모델로 돌렸다. Critical은 없었고 Major에 해당하는 것도 없었다.

**고친 것.**
- 티켓이 ADR 0006에도 이력 항목을 달겠다고 적었으나 diff에는 없었다(표준·명세 두 축 모두 지적). 0006의 옛 이름은 지난 이력 항목 안에만 있어 `.claude/rules/adr.md`가 기록으로 두므로 항목을 더하지 않는 쪽이 맞다고 보고, 티켓의 "고치는 곳"과 수용 기준에서 0006을 뺐다.
- 티켓 수용 기준의 `uv run python tools/check_constitution_version.py`는 `ModuleNotFoundError: No module named 'tools'`로 죽는다(이 변경 이전부터다. 훅과 시험은 `-m tools.check_constitution_version`으로 부른다). 기준의 명령을 `-m` 꼴로 고쳤다.
- ADR 0020 이력이 올린 까닭을 ADR 0016의 같은 날 이력이라고만 가리킨 것은 0016에 2026-11-19 항목이 둘(1.3.9, 1.4.1)이라 어느 쪽인지 모호했다. 이력 제목을 글자 그대로 적어 가리키게 했다.
- 살아 있는 글에 "판을 patch로 올리고"가 남아 있었다: `.scratch/release-image/issues/08-ci-releases-from-main.md` 25줄(상태 `ready-for-agent`). 앞서 쓴 잔존 훑기는 "헌법 판" 같은 구절 꼴을 중심으로 했고 홀로 쓰인 "판"을 이 티켓에서 놓쳤다. "헌법 버전을 patch로 올리고"로 고쳤다(형제 06이 편집 중인 파일이 아니다).
- 루트 `README.md`의 고침과 08 티켓을 티켓의 "고치는 곳"에 적어 넣었다.

**남긴 것과 이유.**
- 같은 글 안에서 서버·계약 번호의 "판"과 헌법 "버전"이 나란히 있는 곳(루트 `README.md` 9행, PR 서식 27행, `eval_judge.py`의 "지시문 판 … 버전 번호"). 서버·릴리스·홀로 쓰인 "판"은 뒤 영역 몫이라 이번에는 두고, 티켓의 "바꾸지 않는 것"에 알고 둔다고 적었다.
- `GLOSSARY.md` 220~221행의 판 항목(`_Avoid_: 버전 …`)과 `principles.md` 거버넌스의 "판은 semver다"는 이번 PR의 "헌법 버전"과 잠시 어긋난다. 용어집의 판 항목과 헌법 원칙은 뒤 영역이 한 번에 맞춘다(티켓이 밝혔다).
- `.scratch/retro-queue/constitution-edit-beyond-approval.md`의 "판을 1.1.2로 올렸다"는 지난 사건의 서술이라 기록처럼 두었다.
- 두 도구와 시험에서 일지 인용을 코드 스팬으로 감싼 것은 이름 바꾸기가 아니라 `sibling_overlap`의 "어디에도 없는 일지를 가리킨 인용" 알림(줄바꿈이 줄 번호를 바꿔 새로 걸린 것)을 피하려는 것이다. 위 "한 것"에 적었다.

**다시 돌린 명령.** 고친 뒤 `check_adr_pointers.py`, `check_instructions.py`는 출력 없이 통과했고, `sibling_overlap.py`는 종료 0(형제 최고 1.4.0, 이 브랜치 1.4.1, "번호 겹침 없음")이다. 형제 06은 PR 73으로 열렸고 아직 병합되지 않았다. 린트, 포맷, 타입체크, import 경계와 전체 pytest는 커밋이 부르는 pre-commit의 결과로 갈음한다(커밋 뒤에 적는다).

지시문 어림과 실제 수: 지시문은 헌법 판 11개 파일 35곳, 비워 둔 판 5개 파일 20곳, 판 번호 3개 파일 3곳으로 어림했다. 실제로 바뀐 것은 수정 21개 파일(리뷰 반영의 08 티켓 포함)과 새 파일 2개(티켓, 일지)다. 지시문의 수는 기록 파일을 섞어 센 어림이고, 우리는 도구·시험의 출력 문자열과 홀로 쓰인 헌법 번호의 "판"까지 바꿔 더 많은 곳이 바뀌었다.

## 커밋

첫 시도는 pre-commit의 검사 열이 모두 통과했으나 커밋 메시지 제목이 79자라 commit-msg 훅이 72자 초과로 막았다. 제목을 줄여 다시 커밋했고 통과했다. 커밋은 `3cbc776`(`chore: 헌법 판을 버전으로 바꾼다 (harness glossary-constitution-version-names)`) 하나이고, 이후 리뷰 반영 한 건(ADR 0016 이력의 한 문장과 이 일지)이 한 커밋으로 더해진다. 둘 다 파일 안의 뜻은 바꾸지 않는 문구 고침이다.

## PR 직전 리뷰

- **CodeRabbit CLI.** `Seat: not assigned`, `Plan: Free`인 계정이라 `coderabbit review`를 권한 판정기가 "Unsanctioned Communication"으로 거절해 돌지 못했다. 거절한 명령을 우회해 다시 치지 않았다. 지침의 대체(`bug-perf-review` 서브에이전트와 내장 `/security-review`)로 갔다.
- **`/security-review`.** 발견 없음. 추가된 파이썬 줄이 모두 한글이 든 줄(주석, 독스트링, 문자열, 시험 이름)이라 실행 논리 변경이 없고, `.pre-commit-config.yaml`은 훅 이름과 주석만 바뀌었다(명령, 훅 id, `files`는 그대로).
- **`bug-perf-review`.** 유효한 지적 없음, Minor 하나. 겨냥한 주장 여섯(실행 논리 불변, 출력과 단언 일치, ADR 0020이 든 0016 제목, ADR 0006 이력 안에만 옛 이름, 08 티켓 25줄이 다른 워크트리와 겹치지 않음, 코드 스팬이 뜻을 안 바꿈)이 모두 맞았다. 도구 둘을 직접 돌려 새 문구를 확인했다.
- **Minor (고침).** ADR 0016 이력이 "문구 수정(patch)으로 올렸다"고만 적었으나 번호는 1.3.9에서 1.4.1이라 minor 자리가 바뀐다. "크기는 patch이지만 번호는 minor 자리가 바뀐 것이고 이 PR이 먼저 병합되면 1.4.0은 형제 몫으로 비는 번호"라는 문장을 더했다. 도구는 크기를 보지 않아 동작은 같다.

## 다음

(PR 병합 뒤 회고가 채운다.)
