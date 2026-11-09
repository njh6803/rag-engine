# 킥오프 진행

킥오프의 진행 파일이다. 런북 clone의 진행 규율(`kickoff/runner.md`)이 준비의 첫 일로 `kickoff/progress-template.md`를 이 자리에 복사해 만들고 채운다. `/kickoff`를 다시 부르면 아래 단계 표의 첫 미완 단계부터 잇는다. 이 파일은 8단계의 첫 커밋으로 원격에 올라가므로 다른 저장소의 이름과 금액은 적지 않는다. 표의 칸에 파이프 문자를 넣지 않는다.

## 머리

| 항목 | 값 |
|---|---|
| 런북 clone의 경로 | C:/project/agent |
| 런북 커밋 | 24fdbe9a2e13ac3a7ab131497b4fba13b087b5bb |
| 런북 브랜치 | main |
| 시작 확인에서 clone 상태에 답한 것 | 브랜치 main, 뒤처짐 0, 앞섬 0, 고치다 만 파일 0개. 물을 조건이 아니어서 묻지 않았다 |
| 새 프로젝트의 경로 | C:/project/rag-engine |
| 시작한 날 | 2026-11-09 |

## 준비에서 정한 것

| 항목 | 값 |
|---|---|
| 무엇을 만드나 | MCP를 쓰는 어떤 클라이언트에서도 쓸 수 있는 설치형 문서 검색 서버(지식베이스). 여러 원천에서 문서를 수집하고 색인해서, 근거 위치와 갱신일이 붙은 검색 결과를 MCP 읽기 도구로 돌려준다 |
| 저장소의 주인 | njh6803 |
| 저장소 이름 | rag-engine |
| 공개 여부 | 공개 |
| 플랜 | free |
| 비공개 저장소의 Actions 분(`sku`마다 합계) | 2026-11(UTC) 모든 `sku` 0분 |
| CodeRabbit의 `Seat` 값 | not assigned |

## 단계

상태는 빈 칸(아직), `진행 중`, `대기`, `막힘`, `끝남`, `건너뜀` 가운데 하나다. 건너뜀과 막힘의 이유는 메모 칸에 적는다. 첫 미완 단계는 상태가 `끝남`도 `건너뜀`도 아닌 첫 행이다.

| 단계 | 상태 | 메모 |
|---|---|---|
| 준비 | 끝남 | 도구, gh 로그인과 user 범위, CodeRabbit 로그인 모두 되어 있어 사람만 줄은 조건이 맞지 않았다 |
| 0단계 | 끝남 | 이 기계는 이미 했다. superpowers는 꺼져 있고(7.0.0, disabled), 전역 스킬 넷은 없으며, 전역 CLAUDE.md는 0바이트다. 허락 줄은 모두 조건이 맞지 않았다. kickoff 스킬: 시작 행 끝남(이미 이 clone을 가리켰다) |
| 1단계 | 끝남 | `git init -b main` 했다. 워크트리를 쓴다 |
| 2단계 | 끝남 | 런북 목록 13개에 codebase-design을 더해 14개를 `--copy`로 설치했다. `npx skills ls`와 `skills-lock.json`에 14개가 있다 |
| 3단계 | 끝남 | `/init`을 Skill로 불렀고, 런북 어긋남(묻는다)은 런북으로 답하고 템플릿 모양으로 바로 썼다. `@` 줄은 주석, 검증 명령 칸은 비움, 레이어는 7단계 뒤 |
| 4단계 | 끝남 | docs/agents 둘과 CLAUDE.md의 Agent skills 블록을 썼다. 첨부 문서 6절의 행 12개로 기능 계획 `.scratch/<slug>/plan.md`와 `.scratch/plan-head.md`를 쓰고, 첨부 문서를 `.scratch/kickoff-input.md`로 옮겼다. `.scratch/plan.md`는 7단계가 도구를 복사한 뒤 만든다 |
| 5단계 | 끝남 | docs/PRD.md, 헌법 세 파일과 README(1.0.0), ADR 0001~0005와 색인을 썼고 CLAUDE.md의 `@` 줄을 살렸다 |
| 6단계 | 끝남 | CODING_STANDARDS.md를 런북 뼈대로 쓰고 agent-os 판단 기준 아홉 줄을 이 스택에 맞춰 씨앗으로 옮겼다. 7단계의 Claude Code Review 워크플로가 읽는 리뷰 관점 넷도 agent-os에서 옮겼다 |
| 7단계 | 끝남 | 골격(main·server, /health와 MCP 계약 시험, Dockerfile, ci.yml의 python·image·ticket·verify)과 복사 목록을 들였다. 검증 명령은 색인에 올린 뒤 모두 통과했다(pytest 2701+2, pyright, ruff 둘, lint-imports, run_hooks, check_type_escapes, check_instructions, zizmor). pre-commit과 commit-msg 훅을 깔았다. `.scratch/plan.md`를 생성했다 |
| 8단계 | 진행 중 | |

## 사람 몫

멈춘 사람 몫 줄마다 한 행이다. 갈래는 결정, 허락, 사람만 가운데 하나이고, 상태는 `대기`, `끝남`, `건너뜀` 가운데 하나다. 확인 결과 칸에는 확인 명령의 결과, 고른 답, 건너뛴 이유를 적는다. 단계 `시작`의 행은 진행 규율의 시작 확인이 받은 허락이다.

| 단계 | 갈래 | 할 일 | 상태 | 확인 결과 |
|---|---|---|---|---|
| 시작 | 허락 | 사용자 레벨 스킬 `~/.claude/skills/kickoff/SKILL.md`가 이 clone을 가리키게 한다 | 끝남 | 이미 이 clone(C:/project/agent/kickoff/runner.md)을 가리켰다. 첫 시작은 붙여 넣은 한 줄이었고, 같은 세션에서 `/kickoff`로 다시 불렀다 |
| 준비 | 결정 | 무엇을 만드나 | 끝남 | 사용자가 첨부 문서 rag-engine-plan.md의 "준비의 답" 절로 답했다. 값은 위 "준비에서 정한 것" 표 |
| 준비 | 결정 | 저장소의 주인과 이름 | 끝남 | 사용자가 첨부 문서의 "준비의 답" 절로 답했다. njh6803, rag-engine. gh 로그인과 같고 같은 이름의 저장소는 없다 |
| 준비 | 결정 | 공개 여부 | 끝남 | 사용자가 첨부 문서의 "준비의 답" 절로 답했다. 공개. 플랜 free의 추천과 같다 |
| 1단계 | 결정 | 이 프로젝트에서 워크트리를 쓸지 | 끝남 | 워크트리를 쓴다 (추천). `.gitignore`에 `/.claude/worktrees/`를 넣었다 |
| 2단계 | 결정 | `codebase-design`을 함께 설치할지, `tdd` 사본에서 그 문장을 지우고 센티널을 붙일지 | 끝남 | codebase-design도 설치 (추천) |
| 4단계 | 결정 | 이슈 트래커와 도메인 문서의 모양 | 끝남 | 이슈 트래커는 사용자가 첨부 문서의 "킥오프에서 이 문서를 쓰는 법" 표(4단계: agent-os와 같은 로컬 마크다운)로 답했다. 도메인 문서는 모노레포 신호가 없어 단일 컨텍스트이고, 용어집 이름은 런북 어긋남의 결정으로 GLOSSARY.md (추천). triage 스킬이 없어 라벨 절은 건너뛰었다 |
| 4단계 | 결정 | 산출물 초안(docs/agents/issue-tracker.md, docs/agents/domain.md, CLAUDE.md의 Agent skills 블록)의 승인 | 끝남 | 승인한다 (추천) |
| 5단계 | 결정 | PRD의 내용, 헌법 인터뷰의 결정들, 인터뷰에서 나온 ADR 초안의 승인 | 끝남 | PRD 그대로 확정 (추천). 원칙은 테스트 먼저를 올려 일곱(추천은 다섯). Python 3.12와 agent-os 도구 (추천). 벡터 저장소·작업 대기열은 core, 화면 스택은 admin 설계 인터뷰로 (추천). mcp 2.x로 묶는다 (추천). 운영 규약 그대로 (추천). 거버넌스는 철수 조건 없이 (추천). 헌법 확정 (추천). ADR 다섯 모두 승인 (추천) |
| 6단계 | 결정 | 선행 프로젝트(agent-os)의 판단 기준을 첫날 씨앗으로 넣을지와 어느 항목을 넣을지 | 끝남 | 넣는다 (추천). 묶음 넷 모두(코드 구조 넷, 린터 짝 둘, 테스트 둘, 동사 어휘 통일) |
| 7단계 | 결정 | 복사 목록의 조건부 항목(답변 언어가 한국어인가, claude.ai 클라우드 세션을 쓰는가) | 끝남 | 한국어다 (추천). 클라우드 세션은 쓰지 않는다(추천 없음). 같은 화면에서 화면 디자인(ui-design, frontend-design)을 물었고 admin 인터뷰까지 미룬다 (추천) |
| 7단계 | 허락 | 파이썬 LSP 플러그인(pyright-lsp)을 프로젝트 범위로 설치한다 | 끝남 | 프로젝트 범위로 설치 (추천). `claude plugin install pyright-lsp@claude-plugins-official --scope project`가 성공했고 `.claude/settings.json`의 `enabledPlugins`에 true로 들었다. 사용자 범위로는 이미 켜져 있었다 |
| 7단계 | 사람만 | 그 플러그인이 부르는 언어 서버 바이너리(pyright-langserver)를 이 기계에 설치한다 | 끝남 | 사용자가 설치했다(npm 전역). `command -v pyright-langserver`가 npm 전역 경로를 냈고, 같은 패키지의 `pyright --version`과 `package.json`이 1.1.414다. `pyright-langserver --version`은 연결 인자가 없다는 오류로 끝나 확인 명령으로 쓰지 못했다(런북 어긋남) |
| 7단계 | 결정 | 안 쓰는 플러그인과 MCP 서버를 끌지와 어떻게 끌지(런북은 사람만 줄 둘, /plugin과 /mcp) | 끝남 | settings.json에 적어 끈다 (추천). agent-os와 같은 다섯(document-skills, example-skills, skill-creator, code-review 플러그인, slack)을 `enabledPlugins`에 false로 적었다. MCP 서버는 묻지 않았다. 끄기 전후의 /context는 재지 않았다(런북 어긋남) |
| 7단계 | 사람만 | 끄기 전에 이 세션의 입력창에 /context를 친다 | 건너뜀 | jira-* 다섯의 skillOverrides를 settings.json을 처음 만들 때 함께 적어, 끄기 전을 잴 때를 지나쳤다. 에이전트의 차례 실수다 |
| 7단계 | 사람만 | 안 쓰는 플러그인과 MCP 서버를 /plugin·/mcp 화면에서 끈다 | 건너뜀 | 결정 행에서 사용자가 settings.json에 적어 끄기를 골랐다. MCP 서버는 끄지 않았다 |
| 7단계 | 사람만 | 끈 뒤에 다시 /context를 친다 | 끝남 | 사용자가 쳤다. 끈 다섯의 스킬이 목록에 없어 세션 안에서 반영된 것을 봤다. 스킬 7.4k, MCP 도구 14.4k(지연 75.6k), 메시지 257.7k, 합 321.1k/400k. 값은 일지 |
| 8단계 | 허락 | GitHub에 저장소를 만들고 첫 커밋을 푸시한다 | 끝남 | 만들고 푸시한다 (추천). `gh repo create njh6803/rag-engine --public --source=. --push`가 첫 커밋 9f1ee79를 main으로 올렸고, 그 푸시의 CI가 초록이었다 |
| 8단계 | 결정 | 혼자인지 팀인지 | 끝남 | 혼자 (추천). 리뷰 승인 필수와 CODEOWNERS를 두지 않고 관리자 우회를 허용한다 |
| 8단계 | 허락 | `tools/protection.json`으로 main을 보호한다 | 끝남 | 보호를 건다 (추천). PUT이 0으로 끝났고, 읽어 보니 필수 검사 verify(strict), 선형 이력, 강제 푸시·삭제 금지, 관리자 우회 허용, 리뷰 필수 없음이다 |
| 8단계 | 사람만 | `claude setup-token`의 토큰을 시크릿 `CLAUDE_CODE_OAUTH_TOKEN`으로 넣는다 | 끝남 | 넣었다 (추천). `gh secret list`에 그 이름과 넣은 시각(2026-11-09T06:13:09Z)이 있다 |
| 8단계 | 사람만 | CodeRabbit에 로그인하고 이 저장소에 CodeRabbit GitHub App을 설치한다 | 대기 | 설치했다 (추천). 설치 여부는 첫 PR의 coderabbitai[bot] 코멘트로 대 본다 |

## 런북 어긋남

진행 중에 런북이 실제와 어긋난 자리(명령이 없다, 경로가 다르다, 출력이 런북의 설명과 다르다)를 한 줄에 하나씩 적는다. 단계, 어긋난 것, 이번에 어떻게 지나갔는지다. 끝에서 사람에게 보이고 런북 저장소에서 고칠 거리로 넘긴다.

- 3단계: 런북은 "`/init`으로 만든 뒤 템플릿 모양으로 줄인다"이고 사람 몫이 없다고 적었지만, 지금의 `/init`은 파일을 쓰기 전에 선택 화면으로 여러 번 묻는다(어느 CLAUDE.md를 만들지, 스킬과 훅도 만들지, 빈 칸 인터뷰, 제안 승인). 이번에는 결정으로 "런북으로 답하고 바로 쓴다 (추천)"를 골라, 질문을 띄우지 않고 프로젝트 CLAUDE.md 하나만 템플릿 모양으로 바로 썼다(스킬은 2단계, 훅과 린트는 7단계)
- 4단계: 런북(4단계의 도메인 문서, "어디에 무엇이 사는가" 표, CLAUDE.md 템플릿의 지도)은 용어집을 루트 `CONTEXT.md`로 적지만, 2단계가 설치한 상류 스킬(setup-matt-pocock-skills, domain-modeling, diagnosing-bugs, tdd)은 `GLOSSARY.md`(멀티 컨텍스트는 `GLOSSARY-MAP.md`)를 쓰고 `CONTEXT.md`를 옛 이름으로 본다. 7단계가 agent-os에서 복사하는 파일(to-tickets와 grill-with-docs 사본, spec-reviewer, PR 템플릿, claude-code-review 워크플로, ui-design)은 아직 `CONTEXT.md`다. 이번에는 결정으로 "GLOSSARY.md (추천)"를 골라 docs/agents/domain.md와 CLAUDE.md를 GLOSSARY.md로 썼고, 7단계 복사 파일의 CONTEXT.md는 그 단계에서 고친다
- 7단계: 복사 목록의 `tests/conftest.py`(목록은 직접 들지 않지만 복사한 테스트가 기대는 파일)가 복사하지 않는 `tools/llm_tokens.py`를 import해 수집이 죽었다. 이번에는 LLM 마커와 토큰 합계 부분을 빼고 `agent_os`를 `rag_engine`으로, 원칙 번호를 rag-engine 것으로 고쳤다
- 7단계: 복사 목록의 `tidy-checkouts` 스킬은 `tools/tidy_checkouts.py`를 부르지만 목록에 그 도구가 없다. 이번에는 도구와 그 시험을 함께 복사했다
- 7단계: `ci.yml`과 검사 러너가 zizmor(워크플로 감사)를 돌리고 `.github/zizmor.yml`을 읽지만 목록에 그 설정과 개발 의존성이 없고, 설정은 복사하지 않는 `tests/tools/test_zizmor_gate.py`를 가리킨다. 이번에는 설정을 복사해 그 문장을 빼고 zizmor를 개발 의존성에 넣었다
- 7단계: 런북은 타입 우회 검사를 "원칙 III의 판정자"로 적고 바꿀 곳에 원칙 번호를 들지 않지만, 원칙 번호는 프로젝트마다 다르다(rag-engine은 테스트 먼저가 I, 타입 우회 금지가 II). 이번에는 복사본의 원칙 번호 인용을 rag-engine 것으로 옮겼다
- 7단계: 런북은 안 쓰는 플러그인을 사람이 /plugin 화면에서 끄라고 적었지만, 같은 결과를 `.claude/settings.json`의 `enabledPlugins` false로 낼 수 있다(agent-os의 모양). 이번에는 사용자가 결정으로 "settings.json에 적어 끈다 (추천)"를 골랐다
- 7단계: LSP 플러그인의 언어 서버(pyright-langserver)는 개발 의존성 pyright가 `.venv`에 두지만 전역 PATH에는 없다. 런북은 바이너리를 따로 설치하라고만 적었다. 이번에는 사람만 줄로 사용자가 설치한다
- 7단계: 런북은 언어 서버 바이너리의 확인을 "그 바이너리의 `--version`"으로 적지만, `pyright-langserver --version`은 `--stdio` 같은 연결 인자가 없다는 오류로 끝난다. 이번에는 경로(`command -v`)와 같은 npm 패키지의 `pyright --version`으로 확인했다
- 7단계: 런북은 `.claude/rules/tools.md`와 `.claude/rules/adr.md`를 바꿀 곳 0으로 적지만, 두 파일은 복사하지 않는 훅·도구·프로브(`.scratch/harness/`)와 agent-os의 ADR·대기열 번호를 근거로 들고, adr.md는 용어집을 `CONTEXT.md`로 적는다. agent-os ADR 0005 같은 번호는 rag-engine의 다른 ADR로 풀린다. 이번에는 adr.md의 용어집 이름만 GLOSSARY.md로 고치고(4단계 결정) 나머지는 두었다
- 7단계: 복사한 스킬 사본(next-session 넷, open-session, tidy-checkouts, implement)이 agent-os `operations.md`의 절(환경 규약 상세, 리뷰 파이프라인 3, 병렬·워크트리 규칙)과 agent-os `CLAUDE.md`의 절을 가리키지만, 런북 5단계가 만드는 새 프로젝트의 헌법과 CLAUDE.md에는 그 절이 없다. 본문의 agent-os ADR 번호도 새 프로젝트의 번호와 겹친다. 이번에는 서브에이전트가 포인터를 rag-engine에 있는 자리로 옮기거나 내용을 사본에 풀어 넣고, ADR 인용에 agent-os 접두를 달았다
- 7단계: 복사 목록에 `.gitattributes`가 없다. agent-os는 `* text=auto eol=lf`를 두고, 이 PC는 `core.autocrlf=true`라 없으면 워크트리와 클론의 작업 파일이 CRLF가 될 수 있다(서브에이전트의 복사 저장소에서 `git add`가 거의 모든 파일에 CRLF 경고를 냈다). 이번에는 agent-os와 같은 한 줄을 첫 커밋 전에 두었다
- 7단계: 런북이 바꿀 곳을 적지 않은 시험의 문턱이 agent-os의 저장소 크기에 맞춰져 있다(`test_rewrap_comments`의 파일 수 100, `test_check_instructions`의 도구·불리언 소스 수, `test_queue_open_rows`가 찾는 agent-os 항목, `test_mutate`의 변이 표 하나 이상). 이번에는 rag-engine의 실제 수에 맞추고 "첫 X를 커밋할 때 되살린다"는 주석을 달았다. 런북은 `test_hook_report`의 문턱만 바꿀 곳으로 적었다
- 7단계: `tools/sibling_overlap.py`는 카나리아 명세가 없는 저장소에서도 하네스를 바꾼 브랜치에 없는 `tools/canary.py`를 돌리라고 알린다. 이번에는 명세가 하나도 없으면 세지 않게 고쳤다
- 8단계: 런북의 첫 커밋 명령 `SKIP=check-constitution-version git commit`의 `SKIP`이 pre-commit, 검사 러너, pytest를 거쳐 시험이 임시 저장소에서 띄우는 pre-commit까지 이어져, `test_check_constitution_version`의 지운 파일 시험이 `(no files to check)Skipped` 대신 `Skipped`를 보고 실패했다(첫 커밋이 막혔다). 이번에는 결정으로 "conftest가 SKIP을 벗긴다 (추천)"를 골라, `tests/conftest.py`가 `GIT_*`처럼 `SKIP`도 시험 프로세스 환경에서 벗기게 고치고 그 시험(`tests/test_conftest.py`)을 먼저 써서 빨강을 봤다. agent-os의 conftest도 `SKIP`을 벗기지 않는다
- 8단계: 런북은 첫 커밋 뒤의 진행 파일과 일지를 `chore/kickoff` 브랜치에 커밋하라고만 적었지만, 7단계가 복사한 커밋 검사(`check-ticket`)가 그 브랜치에 티켓 `.scratch/harness/issues/kickoff.md`가 없다며 커밋을 막았다(일지는 면제 모양이고 진행 파일은 아니다). 이번에는 검사가 안내하는 대로 harness 티켓을 써서 같은 커밋에 실었다
