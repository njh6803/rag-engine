# ui-design-skill-port: 화면 그림 스킬과 그 계기를 agent-os에서 옮긴다

**What to build:** 화면이 있는 기능은 명세를 쓰기 전에 화면을 그려 사용자에게 확인받고, 고른 그림을 `.scratch/<기능>/design/`에 둔다(ADR 0026 "화면 그림을 명세 앞에 둔다"). 그 절차를 돌리는 스킬과 계기가 이 저장소에 없어서, `next-session` 결정표가 화면이 있는 기능(지금은 admin)을 곧바로 명세 쓰기로 보낸다. agent-os의 화면 그림 스킬 `ui-design`과 그 계기 셋을 옮겨 이 길을 연다. 옮길 원본은 agent-os 저장소(`C:\project\agent`)의 같은 이름 파일이다.

**옮기는 것 넷.**
- `.claude/skills/ui-design/SKILL.md`. 순서는 설치, 계정과 디자인 시스템, 참고 디자인과 시작 프롬프트, `frontend-design` 부르기, 그리기, 고르기, 옮기기, 그리고 웹 편집 확인이다. ADR 0026이 정한 대로 디자인 시스템 아티팩트(agent-os가 관리한다)는 읽기만 하고, 코드와 맞추는 도구는 옮기지 않으므로 그 도구를 부르는 자리(`sync-design-system`, 토큰 코드로 들이기)와 디자인 시스템의 방향을 새로 탐색하는 갈래(`design-system`)를 뺀다. 이 저장소에 없는 `.claude/rules/web-design.md`와 `kickoff/prompting.md`를 가리키던 자리는 이 저장소의 사실로 바꾼다.
- `tools/hook_ui_design.py`와 그 시험, 훅 표의 사례, `.claude/settings.json`의 등록. 기능의 디자인 폴더(`.scratch/<기능>/design/`) 아래 파일을 쓰거나 고치면 `/ui-design <기능>`을 부르라고 세션마다 한 번 알린다. 스킬 설명이 목록에서 밀려도 계기가 남게 하려는 훅이다.
- `.claude/skills/next-session/SKILL.md` 결정표의 "화면 디자인" 줄. 그 줄은 "명세" 줄보다 위에 둔다(아래 지킬 것 첫째).
- `docs/agents/issue-tracker.md`의 "화면 디자인" 절. 시작 프롬프트가 담을 것, 그릴 화면을 가르는 규칙, 폴더와 `README.md` 표의 칸이다.

**지킬 것 둘**(`.scratch/admin/plan.md`의 "차례"가 적은 것).
1. 결정표의 "화면 디자인" 줄을 "명세" 줄보다 위에 둔다. 아래에 두면 설계 줄이 있고 명세가 없는 admin이 "명세" 줄에 먼저 걸려 그림 없이 명세로 간다.
2. 그 줄이 화면이 있는 기능을 가리는 표지는 agent-os와 같게 기능 계획 본문의 "명세 전에 화면을 그린다"는 문장이다. admin, group-kb, eval-screen의 계획이 그 문장을 이미 적는다.

**이 저장소에 맞추는 것.** agent-os의 스킬은 저장소 안의 도구와 규칙에 기댄다. 옮기며 이 저장소에 있는지 하나씩 본다.
- 없어서 뺀 것: 디자인 시스템과 코드를 맞추는 스킬과 도구(`sync-design-system`, `web/tools/sync-design-system`), 화면 코드를 고치면 알리는 훅(`hook_web_edit_check`), 디자인 시스템의 방향 탐색(`.scratch/design-system/`).
- 이 저장소의 이름으로 바꾼 것: `CONTEXT.md`는 `GLOSSARY.md`, 훅의 표지 폴더 이름, 충돌 목록의 자리(기능마다 `design/frontend-design-conflicts.md`).
- `.claude/rules/web-design.md`는 web 뼈대 티켓이 `web/`을 세울 때 생긴다. 스킬은 그 파일이 있으면 읽고 없으면 디자인 시스템 아티팩트의 README와 `tokens.json`, `guidelines/web-design.md`의 "쓰는 법"을 규칙으로 쓴다.

**이번에 바꾸지 않는 것.**
- admin의 화면 그림(`.scratch/admin/design/`)과 명세. 이 티켓이 병합된 뒤 결정표가 보내는 다음 세션이 그린다.
- `to-spec`, `to-tickets`, `implement`. 명세가 `design/`의 그림을 가리키게 하는 문장은 admin의 명세 세션이 필요할 때 더한다.
- `.claude/rules/tools.md`. 훅 목록이 이 훅의 이름을 이미 들고 있다.

**대기열:** 없음

**Status:** done

- [x] `.claude/skills/ui-design/SKILL.md`가 있고, 단계 일곱과 웹 편집 확인을 담고, 이 저장소에 없는 스킬·도구·규칙 파일(`sync-design-system`, `web-design.md`가 없을 때의 길, `kickoff/prompting.md`, `design-system` 갈래)을 가리키는 곳이 없다(grep으로 본다)
- [x] 스킬 머리 주석이 agent-os에서 옮겼다는 것과 옮기지 않은 것을 적고, `프로젝트 사본` 낱말을 쓰지 않는다(`tools/check_instructions.py`의 덧댄 스킬 판정에 걸린다)
- [x] `tools/hook_ui_design.py`가 기능의 디자인 폴더 아래 Write·Edit에만 `/ui-design <기능>`을 알리고, 세션·에이전트마다 한 번이며, 표지를 쓰지 못하면 호출마다 알린다. 독스트링이 못 보는 것을 적고 시험이 그 항목마다 하나씩 고정한다
- [x] `.claude/settings.json`에 래퍼 모양으로 등록되고(`PostToolUse`, 매처 `Write|Edit`), `tools/hook_payloads.toml`에 발동 하나와 침묵 둘이 있으며, `uv run python tools/run_hooks.py`가 초록이다
- [x] `next-session` 결정표의 "화면 디자인" 줄이 "명세" 줄보다 위에 있고, 표지가 기능 계획 본문의 "명세 전에 화면을 그린다"는 문장이다. 스킬 머리 주석의 "화면 디자인 단계도 복사하지 않아 결정표에서 뺐다"는 문장과 `/ui-design`을 모델이 부를 수 있다는 줄이 맞게 고쳐졌다
- [x] 결정표의 새 줄을 admin의 지금 상태(설계 줄이 있고 명세가 없고 `design/`이 없고 계획 본문에 그 문장이 있다)에 손으로 대 보아 "화면 디자인"이 고르는 줄이라는 것을 확인했다. 같은 상태에서 그 문장이 없는 기능은 "명세" 줄로 간다
- [x] `docs/agents/issue-tracker.md`에 "화면 디자인" 절이 있고, 스킬이 가리키는 규약(시작 프롬프트가 담을 것, 그릴 화면을 가르는 규칙, 폴더와 표의 칸, 계정)을 이 저장소에 맞게 적는다. 디자인 시스템 아티팩트의 주소가 그 절에 있고, 읽은 날짜와 방법(손으로 읽었다)이 적혀 있다
- [x] `.scratch/plan-head.md`의 "하네스 기능" 절에서 이 일의 줄이 지워지고(`열린 하네스 기능이 없다`), `uv run python tools/plan_table.py`로 `.scratch/plan.md`를 다시 만들었다
- [x] `.scratch/admin/plan.md`의 "차례"가 이 티켓이 끝난 뒤의 사실로 읽힌다(스킬을 옮기기 전이라는 문장이 남지 않는다)
- [x] 옛 말(`그림 스킬을 옮기기`, `복사하지 않아 결정표에서 뺐다`)이 일지와 대기열 밖에서 0이다(`CLAUDE.md` 작업 규약 4의 명령)
- [x] `uv run pytest`, `uv run ruff check .`, `uv run ruff format --check .`, `uv run pyright`, `uv run lint-imports`가 초록이다
- [x] 일지가 있고 이 PR의 셀프 리뷰 결과를 담는다

## Comments

- 2026-11-26 결정표 손 대기. admin의 지금 상태(`**설계:**` 줄이 있고, `spec.md`가 없고, `design/`이 없고, 계획 본문에 "명세 전에 화면을 그린다"가 있다)는 "화면 디자인" 줄로 간다. 같은 상태에서 그 문장이 없으면 "명세" 줄로 간다(가정 사례다. 지금 저장소에서 설계 줄이 있는 기능은 admin뿐이고, 다른 기능은 설계 줄이 없어 설계 인터뷰 줄로 간다).
- "화면 디자인" 줄의 "어디서"가 Docker가 켜진 로컬 세션인 것은 셀프 리뷰 명세 축이 짚었다. 옮긴 화면 파일 `.dc.html`은 `run_checks.is_doc_path`가 문서로 보지 않아 그 커밋에 테스트 PostgreSQL이 든다.
- 이 저장소에서 처음 돌리는 일(플러그인 설치, 계정 판정, 아티팩트 만들기)은 재지 못했다. 처음 돌리는 세션(admin의 화면 그리기)이 막힌 자리를 스킬 끝 절에 적는다.
