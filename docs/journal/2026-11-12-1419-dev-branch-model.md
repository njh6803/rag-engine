# dev-branch 설계: 브랜치 모델을 agent-os ADR 0043으로 옮긴다 · 2026-11-12

agent-os의 `dev-branch-create`가 낸 지시문을 사용자가 붙여 넣어 연 세션의 기록이다(Opus 5.5 / high). 시작 프롬프트는 `/grill-with-docs rag-engine을 agent-os ADR 0043의 브랜치 모델(dev 전환)로 옮긴다`이고, 브랜치는 `docs/dev-branch-model`(설계·티켓을 쓰는 면제 PR), 작업은 워크트리 `dev-branch-model`에서 했다. 준비, 사용자가 넘긴 것, 확인한 것, 물은 것과 답, 반영한 것, 셀프 리뷰, 검증, 다음을 차례로 둔다.

## 준비

- 주 체크아웃(main)에서 시작해 `EnterWorktree`로 `dev-branch-model`에 들어갔고, 앱이 만든 브랜치를 `docs/dev-branch-model`로 바꾸고 세션 제목을 그 이름으로 바꿨다. 워크트리는 `origin/main`(11f91c9)에서 섰다.
- `grill-with-docs`가 `grilling`과 `domain-modeling`을 불렀다.
- agent-os는 읽기만 했다. `git -C C:/project/agent show origin/dev:<경로>`로 그 저장소의 `origin/dev`(4b02bbe29, 2026-11-12 13:35, PR #541)에서 ADR 0043, `.scratch/harness/issues/`의 `dev-branch-transition.md`·`dev-review-bot-off.md`·`dev-base-tools.md`·`dev-base-skills-docs.md`·`dev-branch-create.md`, `tools/base_rule.py`, `tools/protection.json`, `tools/protection-dev.json`, `docs/agents/issue-tracker.md`와 `docs/constitution/operations.md`의 해당 절, `.coderabbit.yaml`, `tools/check_ticket.py`의 hotfix 판정 줄을 읽었다. fetch는 하지 않았다.
- 이 저장소에서 읽은 것: `docs/adr/` 목록과 0015, ADR 색인, `domain-modeling`의 ADR-FORMAT, `.claude/rules/adr.md`, `docs/constitution/operations.md`의 "브랜치와 병합", 헌법 색인, `.github/workflows/ci.yml`, `.github/workflows/claude-code-review.yml`, `.coderabbit.yaml`, `tools/check_ticket.py`의 판정과 면제 모양, `tools/plan_table.py`의 하네스 기능 줄, `docs/agents/issue-tracker.md`의 harness 티켓과 기능 계획 줄, `GLOSSARY.md`의 머리와 항목 이름, `.scratch/plan.md`, `.scratch/core/plan.md`와 티켓 14(서식), `.scratch/harness/issues/`의 티켓 넷, 대기열 `client-name-in-spec-body`·`out-of-scope-receiver-unwritten`, 일지 `2026-11-11-1534-doc-permission-list-filter.md`(서식), `next-session` `SKILL.md` 28행.

## 사용자가 넘긴 것

- 붙여 넣은 지시문(agent-os `dev-branch-create` 결과 5의 글)이다. 이어받을 상태 (1)~(6)과 이번 요청 범위(얇은 ADR 초안과 harness 티켓까지, ADR은 셀프 리뷰를 반영한 뒤 보여 주고 승인을 받는다, dev를 따는 푸시와 GitHub 설정은 그 뒤의 티켓이 한다)를 따랐다. (4)대로 ADR 0043의 "잊으면 다음 dev→main에서 hotfix가 사라진다"는 옮기지 않았다.
- 세션 도중에 사용자가 보낸 글이다.

> 사용자: "(7) 출시 PR(dev→main)을 여는 순서와, main이 strict라서 둘째 출시 PR부터 BEHIND가 날 것이라는 어림(agent-os가 재 보지 않았다)은 agent-os가 정하는 중이다(harness 티켓 dev-release-pr-step, 아직 병합 전). 이 저장소의 ADR과 티켓은 그 결과가 agent-os의 origin/dev에 병합된 뒤 다시 읽어 맞추고, main 보호의 strict 여부는 그 전에 정하지 않는다"

## 확인한 것

- **도구는 agent-os 전환 직전 판과 거의 같다.** 커밋하지 않은 스크래치 스크립트(세션 스크래치패드의 `cmp_tools.py`, `diff_sizes.py`, `show_diff.py`)로 이 저장소의 `tools`·`tests/tools`·`.github`·`.claude`·`CLAUDE.md`·`docs/constitution/operations.md`·`docs/agents`의 추적 파일마다 blob 해시를 agent-os의 #534 첫 부모(`d7fdb250e`)와 `origin/dev`(`4b02bbe29`)의 같은 경로에 견주었다. 견준 범위에는 #539(base-agent 03)·#540(answer-markdown 문서)처럼 전환과 무관한 PR도 들어 있다.
  - 전환 직전 판과 같고 agent-os에서 바뀐 것은 열하나다. `tools/`의 `check_constitution_version`, `hook_git_main_commit`, `hook_push_behind_main`, `protection.json`, `queue_open_rows`, `tidy_checkouts`, `wait_ci`와, `tests/tools/`의 `test_check_constitution_version`, `test_hook_git_main_commit`, `test_hook_push_behind_main`, `test_tidy_checkouts`다.
  - 다르고 agent-os에서 바뀐 것 가운데 도구는 `check_ticket`(이 저장소와 직전 판의 차이 6줄, 직전→직후 121줄), `sibling_overlap`(11줄, 111줄), `hook_prompt_directive`(33줄, 9줄), `mutate`(17줄, 3줄), `run_hooks`(296줄, 37줄), `hook_payloads.toml`(514줄, 12줄)이고, 시험은 `test_check_ticket`(2줄, 110줄), `test_sibling_overlap`(15줄, 202줄), `test_run_hooks`(115줄, 7줄)다. `check_ticket`의 6줄은 면제 모양의 `CONTEXT.md`를 `GLOSSARY.md`로 바꾼 셋이고, `sibling_overlap`의 11줄은 카나리아 명세가 없는 저장소에서 바꾼 하네스 파일을 세지 않는 판정이다(`show_diff.py`로 읽었다).
  - 스킬과 문서는 이 저장소의 판이 많이 다르다. 예로 `ci.yml` 316줄, `CLAUDE.md` 108줄, `operations.md` 114줄, `issue-tracker.md` 58줄, `next-session/merge.md` 18줄이 직전 판과 다르다.
  - `tools/base_rule.py`와 `tests/tools/test_base_rule.py`는 이 저장소에 없다. agent-os의 `morning_*`, `rerun_*`, `canary`, `export_openapi`도 이 저장소에 없다.
- **CI**: 잡은 `python`, `image`, `ticket`과 모음 잡 `verify`이고 push 트리거는 `main`뿐이다. LLM을 부르는 테스트와 실제 이미지의 compose e2e가 없다(`ci.yml`을 읽었다). `pull_request:`에 `types`가 없어 기본 사건만 받는다.
- **리뷰 봇 워크플로**: 이 파일을 바꾼 PR은 액션이 리뷰를 건너뛰고, 기록(일지·대기열·티켓·하네스 탐침) 밖의 파일을 함께 실으면 가드 스텝이 실패한다. 액션은 이 파일을 기본 브랜치의 것과 견준다(머리 주석, agent-os PR #3·#6 실측). 그래서 기본 브랜치를 dev로 옮기면 dev에서 이 파일이 바뀐 동안 main에서 딴 PR이 건너뛰어질 수 있다(코드를 읽은 추론이고 재 보지 않았다).
- **CodeRabbit**: 두 저장소의 `.coderabbit.yaml` 모두 `auto_review.base_branches`를 두지 않는다(읽었다). 자동 리뷰가 기본 브랜치를 base로 둔 PR만 본다는 것은 어림이다(공식 문서 원문을 이 세션에서 읽지 않았다).
- **GitHub**(명령의 출력): `gh repo view`가 기본 브랜치 main, merge 커밋·squash·rebase 모두 허용. `gh api .../branches/main/protection`이 필수 검사 `verify`, strict true, `required_linear_history` true, 강제 푸시·삭제 금지, `enforce_admins` false. `tools/protection.json`이 그와 같은 값이다. `gh pr list --state open`이 빈 목록, `git ls-remote --symref origin HEAD`가 `refs/heads/main`, `git ls-remote origin refs/heads/dev`가 비었다.
- **도는 일**: `git worktree list`에 core 13·15(병합됨)와 core 14(`feature/14-reindex-version-switch`, 11f91c9)의 워크트리가 있다. core 14를 다른 세션이 진행하고 있다(지시문).
- **커밋 검사**: `docs/` 브랜치의 PR은 CI가 실린 harness 티켓의 `Status:`가 모두 done이기를 요구한다(`tools/check_ticket.py` 93~95행). 기능 폴더의 `.scratch/<slug>/issues/*.md`는 면제 모양이다(같은 파일 54~56행). 이 저장소의 harness 티켓 넷은 모두 그 일을 한 PR이 done으로 실었다(`git log --diff-filter=A`).
- **하네스 기능**: `**슬라이스:**` 줄이 없는 기능 계획은 전체 계획 표에 들지 않는다(`tools/plan_table.py` 20행).
- **용어집**: `GLOSSARY.md`는 문서와 원천, 색인과 검색, 수집, 플러그인과 통로의 말만 든다(항목 이름을 읽었다). 티켓이나 기능 계획 같은 하네스 말이 없다.
- **ADR 포인터**: `docs/adr/`를 `squash|스쿼시|브랜치와 병합|origin/main|main에|main으로|기본 브랜치`로 grep해 0건이라 포인터를 달 ADR이 없다.
- **ADR 번호**: `uv run python tools/sibling_overlap.py`가 "이 브랜치의 새 번호 없음", "번호 겹침 없음"으로 끝났다(쓰기 전). 형제의 가장 높은 헌법 판은 1.1.2다.
- **`EnterWorktree`**: 도구 설명이 새 워크트리를 `origin/<기본 브랜치>`에서 딴다고 적는다(읽었다).
- **`next-session`의 `Blocked by` 읽기**: "없음 …"으로 시작하면 막는 것이 없다고 읽고, 티켓 아닌 조건도 찬 것을 고른다(`SKILL.md` 28행).

## 물은 것과 답

추천안을 첫 자리에 두고 "(Recommended)"를 붙였다. 사용자는 모두 추천안을 골랐다.

라운드 1(네 질문).

- 질문(글 그대로): 전환 일을 harness 티켓 몇 장으로 나눌까요? 어느 안이든 dev를 따는 일은 마지막 티켓이고, 앞의 티켓이 모두 main에 병합된 뒤에 합니다. (선택지 3: 넷으로 나눈다, agent-os처럼 다섯, 셋으로 줄인다)

> 사용자: "넷으로 나눈다 (Recommended)" — 설명: 도구·훅·커밋 검사·CI 트리거를 한 장에 싣고(agent-os의 1번과 3번을 합칩니다. 이 저장소의 도구가 agent-os 전환 직전 판과 거의 같아 diff를 얹는 일이기 때문입니다), 리뷰 봇 한 장, 스킬·규약 문서·되돌려 합치기 순서 한 장, dev 따기와 GitHub 설정 한 장입니다. 앞의 셋은 서로 겹치는 파일이 없어 나란히 돌 수 있습니다.

- 질문(글 그대로): dev를 딴 뒤 GitHub의 기본 브랜치를 dev로 옮길까요? 실제 변경은 마지막 티켓이 승인을 다시 받고 합니다. (선택지 2: dev로 옮긴다, main에 둔다)

> 사용자: "dev로 옮긴다 (Recommended)" — 설명: base를 주지 않은 `gh pr create`와 사용자 수준 `/git-pr`이 dev로 PR을 열어, 다른 세션이 실수로 main에 티켓 PR을 여는 일이 없습니다. 대신 핫픽스 PR은 반드시 `--base main`으로 열고, 클론마다 `git remote set-head origin dev`를 한 번 칩니다. agent-os가 2026-11-12에 고른 것과 같습니다.

- 질문(글 그대로): dev 브랜치를 어떻게 보호할까요? 실제 설정은 마지막 티켓이 승인을 다시 받고 합니다. (선택지 3: verify 필수 strict 끔, strict도 켠다, 보호하지 않는다)

> 사용자: "verify 필수, strict 끔 (Recommended)" — 설명: `verify`가 초록이어야 병합되고 강제 푸시와 삭제를 막습니다. 최신 dev 위에서 다시 시험할 것(strict)과 선형 이력은 요구하지 않습니다. strict를 켜면 main→dev 되돌려 합치기 PR이 늘 뒤처짐(BEHIND)으로 막히기 때문입니다. 대신 나란히 돈 두 티켓 PR이 각자 초록으로 병합된 뒤 dev가 빨개질 수 있어, 늦게 병합하는 세션이 dev를 합쳐 시험을 직접 돌립니다. agent-os와 같습니다(`tools/protection-dev.json`).

- 질문(글 그대로): main의 선형 이력 강제를 끌까요? 지금 켜져 있어서 dev→main 출시 PR의 병합 커밋을 막습니다. main의 strict는 지시대로 지금 정하지 않습니다. (선택지 2: 끈다, 켜 두고 관리자 우회)

> 사용자: "끈다 (Recommended)" — 설명: 출시 PR(dev→main)을 병합 커밋으로 그대로 병합합니다. main 이력에 기능마다 병합 커밋이 하나씩 남고, 티켓 PR과 핫픽스는 계속 squash라서 그 밖의 이력 모양은 같습니다. agent-os가 고른 것과 같습니다.

라운드 2(두 질문). 라운드 1의 답(티켓 수, 기본 브랜치)이 연 것이다.

- 질문(글 그대로): dev를 따는 순간 main으로 열려 있는 티켓 PR은 어떻게 할까요? 지금 열린 PR은 없지만 다른 세션이 core 14를 진행하고 있습니다. (선택지 3: base를 dev로 바꾼다, main으로 끝내고 되돌려 합친다, 열린 PR이 없을 때만 딴다)

> 사용자: "base를 dev로 바꾼다 (Recommended)" — 설명: 마지막 티켓이 dev를 딴 직후 `gh pr edit <번호> --base dev`로 옮깁니다. 그 순간에는 dev와 main이 같은 커밋이라 PR의 diff와 커밋 검사의 판정이 그대로이고, main에는 출시된 것만 든다는 뜻이 지켜집니다. base를 바꿔도 CI는 다시 돌지 않고(`ci.yml`의 `pull_request`에 types가 없어 기본값만 받습니다), 머리 커밋의 지난 `verify`가 dev 보호에도 쓰일 것으로 봅니다(어림, 재 보지 않았습니다). agent-os는 ADR 0043에서 '전환 때 열린 PR도 base를 dev로 바꾼다'를 거부했는데, 그때는 dev를 따기 한참 전이라 열린 PR이 main으로 끝나는 것이 자연스러웠습니다.

- 질문(글 그대로): 출시 PR을 여는 순서는 agent-os의 dev-release-pr-step 결과를 기다립니다. dev를 따는 일도 그 결과를 기다릴까요? (선택지 2: 기다리지 않고 다섯째 티켓으로, agent-os를 기다린 뒤 딴다)

> 사용자: "기다리지 않고 다섯째 티켓으로 (Recommended)" — 설명: 마지막 티켓은 앞의 셋이 병합되면 바로 dev를 땁니다. 출시 PR을 여는 순서는 agent-os의 dev-release-pr-step이 origin/dev에 병합된 뒤 그 결과를 옮기는 다섯째 티켓이 하고, 그때까지 출시 PR은 열지 않습니다. 그동안 main은 dev보다 뒤처지고(core가 끝나도 main에는 오르지 않습니다), 핫픽스는 그대로 main에서 딸 수 있습니다. main을 받아 쓰는 곳(배포된 이미지)이 아직 없어 뒤처짐의 값이 작습니다.

라운드 3(한 질문). 티켓을 쓰는 자리를 정하다가 커밋 검사의 CI 판정(확인한 것)을 찾아 물었다.

- 질문(글 그대로): 전환 티켓 다섯을 어디에 쓸까요? `.scratch/harness/issues/`의 `ready-for-agent` 티켓을 이 docs PR에 실으면 CI의 커밋 검사가 done이 아니라고 막습니다. (선택지 2: 하네스 기능 폴더에 쓴다, harness 티켓으로 첫 티켓 PR에 싣는다)

> 사용자: "하네스 기능 폴더에 쓴다 (Recommended)" — 설명: `.scratch/dev-branch/plan.md`(슬라이스 줄 없음, 설계 줄은 ADR 0016)와 `.scratch/dev-branch/issues/01-dev-base-tools.md`~`05-dev-release-pr-step.md`를 이 PR에 ADR·일지와 함께 싣습니다. 면제 모양이라 CI가 지나고, 전체 계획 표에는 들지 않습니다. 브랜치는 `feature/01-dev-base-tools` 꼴이 되고, 번호 뒤에 agent-os의 티켓 이름을 그대로 두어 대응을 쉽게 찾습니다. 설계 인터뷰 스킬이 남기라고 하는 `**설계:**` 줄의 자리도 생깁니다.

합의 요약(결정 1~11, 갈래 12~14)을 올려 확인받았다.

> 사용자: "이대로 쓴다 (Recommended)" — 설명: 요약대로 파일을 쓰고 셀프 리뷰를 반영한 뒤 ADR 0016을 보여 드리며 승인을 요청합니다. 커밋과 PR은 승인 뒤에 합니다.

요약에서 이 세션이 정한 것(지시문이 이 판단을 이 세션에 맡겼거나 agent-os와 다를 까닭이 없는 것)은 넷이다. 도구는 agent-os 전환 diff를 3-way로 얹고 이 저장소의 줄을 남긴다. 핫픽스는 agent-os와 같이 `hotfix/<slug>`와 `.scratch/harness/issues/<slug>.md`다. main PR에만 도는 잡은 지금 없고 느린 검사를 더하는 기능이 정한다. 브랜치 용어는 `GLOSSARY.md`가 아니라 운영 문서에 둔다. 갈래 밟기(`grilling`)에서 찾은 셋은 리뷰 봇이 기본 브랜치와 견주는 갈래(02), CodeRabbit의 base 갈래(03), 낡은 지시문을 따르는 세션(04)이다.

## 반영한 것

- `docs/adr/0016-branch-model-follows-agent-os-adr-0043.md`(status proposed)와 색인 행.
- 하네스 기능 `.scratch/dev-branch/plan.md`(설계 줄 ADR 0016)와 티켓 `issues/01`~`05`(모두 `ready-for-agent`).
- 받는 기능의 본문: `.scratch/search-eval/plan.md`(적중률 게이트를 main PR에만 둘지)와 `.scratch/release-image/plan.md`(단독 compose 시험을 main PR에만 둘지, 판을 어디서 낼지).
- 대기열 `client-name-in-spec-body`: "두 자리의 산문에 그 낱말은 지금 0건"이 ADR 0016으로 거짓이 되어 그 뒤에 괄호로 적었다(`docs/adr/`의 `agent-os`는 ADR 0016과 색인 행뿐이다, Grep으로 셌다). 회차는 더하지 않았다. 같은 실수가 아니라 다른 쓰임이다.
- `GLOSSARY.md`는 고치지 않았다(결정 10).
- 셀프 리뷰를 반영하며 `.scratch/plan-head.md`에 "하네스 기능" 문단을 더하고 `uv run python tools/plan_table.py`로 `.scratch/plan.md`를 다시 만들었다(아래 셀프 리뷰의 명세 축 3).

## 셀프 리뷰

`code-review` 두 축. base `11f91c91986bdb8ea5ed3087436123073fc4b6e8`, 커밋 0, 바뀐 추적 파일 4, 미추적 8. 표준 축은 Sonnet 5.5 / high, 명세 축은 이 세션의 모델로 돌았다. 명세 축의 요구는 지시문 글 그대로, 사용자의 (7), 이 절 위의 "물은 것과 답"(라벨과 설명), 확인받은 합의 요약 전문이고, 이 세션이 요구 밖에서 더 한 것은 참고 절로 갈랐다. 두 브리프에 주장 검증 열 항목, 갈래 밟기 문단, `EnterWorktree` 도구 설명의 발췌를 실었다. 리뷰 도중 agent-os 클론의 `origin/dev`가 641165ff5로 나아갔다(그 저장소의 출시 PR #542와 되돌려 합치기 #543. 다른 세션의 fetch다). 표준 축은 트리가 4b02bbe29와 같다고 했고, 그 판에서도 `dev-release-pr-step.md`의 `Status:`는 `ready-for-agent`다(`git show`로 봤다).

### 표준 축 (Critical 0, Major 0, Minor 5, Nit 4)

- Minor 1. ADR 0016 초안의 닫힌 주장(이 저장소가 고친 줄은 용어집 파일 이름과 카나리아 판정 둘뿐이라는 문장)이 거짓이다. `run_hooks` 296줄, `hook_payloads.toml` 514줄 등이 그 둘 밖에서 다르다. → 고쳤다. 닫힌 목록을 일반 조항("이 저장소에 맞게 고친 줄이 있다")과 예로 바꿨다. `hook_payloads.toml`은 agent-os에만 있는 훅 열아홉의 사례가 없고 이 저장소에만 있는 사례는 없음을 `comm`으로 봤다. 그 가운데 아홉은 이 저장소의 `tools/`에 파일이 없음을 봤다. `run_hooks`가 다른 까닭은 재지 않아 문장에서 뺐다.
- Minor 2. ADR 0043이 열린 PR의 base 바꾸기를 거부한 까닭을 잘못 옮겼다. → 고쳤다. agent-os 일지 `docs/journal/2026-11-04-01-agent-os-direction-design.md`의 779~781행(사용자 답의 설명. base를 바꾸면 커밋 검사의 base가 움직인다는 문장이다)을 읽고, 그 까닭과 이 저장소에서 그 까닭이 서지 않는 이유(따는 순간 두 브랜치가 같은 커밋)를 적었다.
- Minor 3. 티켓 04의 갈래 셋: (다) 기본 브랜치 변경이 dev 따기보다 앞이다, 단계 4가 `hotfix/*` PR도 옮긴다, 단계 3과 4 사이의 main 병합과 끊긴 뒤의 재진입을 다루지 않는다. → 고쳤다. agent-os 티켓 5도 dev를 딴 뒤 `PATCH default_branch=dev`를 했다(결과 표 51행). 승인은 셋을 함께 받고 (나)·(다)는 딴 뒤 걸게 했다. 단계 3에 dev가 이미 있는지 먼저 보는 갈래, 3~4 사이 main 병합 금지, 옮기기 직전의 같은 커밋 재확인, `hotfix/*` 제외를 더했다.
- Minor 4. CodeRabbit 걱정이 운영 문서 "리뷰 파이프라인"의 실측(별 10개 미만이라 자동 리뷰가 돌지 않는다)을 빠뜨렸다. → 고쳤다. ADR Consequences와 티켓 03이 실측을 들고, 확인할 것을 "부른 리뷰가 base가 기본 브랜치가 아닌 PR에서도 도는지"로 바꿨다. 합의 요약 13의 어림(자동 리뷰가 기본 브랜치 PR만 본다)이 이 실측과 맞지 않아 승인 화면에서 바로잡는다.
- Minor 5. 티켓 05의 `**끝:**` 줄 요구가 저장소 규칙과 어긋난다. → 고쳤다. `tests/test_plan_status.py` 머리 독스트링 17~18행이 `**슬라이스:**` 줄이 없는 기능 계획을 끝 줄 시험에서 빼고 하네스 기능은 티켓이 모두 done이면 끝난 것이라 적는다. 05와 04에서 끝 줄을 빼고, 05가 `plan-head.md`의 하네스 기능 줄을 지우게 했다.
- Nit 1. `.claude/rules/adr.md` 둘째 항목의 "ADR 0016이 0010의 의존 방향을 바꿨다"는 agent-os의 번호인데 새 0016과 겹쳐 읽힌다. → 티켓 03에 넘겼다. 이 파일은 `tools/check_ticket.py` 독스트링의 면제 모양이 아니라 이 `docs/` 브랜치에서 고치면 커밋 검사가 막는다(판정 6·7).
- Nit 2. ADR이 proposed인데 accepted로 바꾸는 자리가 없다. → 남겼다. 승인 뒤 이 PR에서 status와 색인 행을 바꾼다(이 세션의 다음 단계).
- Nit 3. `EnterWorktree`가 `origin/<기본 브랜치>`에서 딴다는 것은 `worktree.baseRef`가 기본값 `fresh`일 때뿐이다. → 고쳤다(ADR, 티켓 04). 사용자 설정과 프로젝트 설정에 그 키가 없음을 봤다(사용자 설정은 키만 읽는 `uv run python -c`, 프로젝트는 Grep).
- Nit 4. 티켓 03의 "01 병합 뒤에 병합한다"가 산문뿐이다. → 고쳤다. 병합 직전에 01·02가 done이고 `origin/main`에 있는지 보는 수락 기준을 더했다(명세 축 5와 같다).

### 명세 축 (Major 3, Minor 11, Nit 1. 범위 넘침 없음)

- Major 1. 01을 쪼개면 04가 그 티켓을 기다리지 않는다. → 고쳤다. 01이 새 티켓을 쓰면 04의 `Blocked by`와 1단계에 번호를 더하게 했고, 04의 1단계는 폴더의 04·05 밖 티켓 전부를 본다. ADR 전환의 차례 4와 기능 계획도 맞췄다.
- Major 2. 02가 03에 넘기는 몫을 03이 02를 기다리지 않아 받지 못할 수 있다. → 고쳤다. 03은 01과 02가 병합된 뒤에 병합한다(티켓 03의 `Blocked by`와 수락 기준, ADR 전환의 차례 3, 기능 계획). 합의 요약 1의 "03은 01이 병합된 뒤"가 바뀌어 승인 화면에서 보인다.
- Major 3. 지시 (7)의 "병합된 뒤 다시 읽어 맞추고"를 할 05를 다시 집을 계기가 없다. 하네스 기능은 전체 계획의 표에 들지 않고 `next-session`은 같은 기능의 묶음만 고른다(`SKILL.md` 28행). → 고쳤다. `.scratch/plan-head.md`에 "하네스 기능" 문단을 두어 `.scratch/plan.md`를 읽는 세션(`next-session` 결정표의 원천, `SKILL.md` 47행)에 dev-branch와 05의 조건이 보이게 했고, 04가 닫을 때 조건이 차지 않았으면 일지 "다음"에 적고, 05를 닫는 커밋이 그 줄을 지운다.
- Minor 4. 지시 (5)가 든 `plan_table`이 01에 없다. → 고쳤다. `main`으로 grep해 `def main`과 `__main__`만 나왔고 agent-os 전환 diff(`d7fdb250e`..`4b02bbe29`의 `--stat`)도 그 파일을 고치지 않았다는 판단을 01의 "옮기지 않는 것"에 적었다.
- Minor 5. 03의 병합 순서에 관문이 없다. → 고쳤다(표준 축 Nit 4).
- Minor 6·7. 표준 축 Minor 1·2와 같다. → 고쳤다.
- Minor 8. ADR 머리의 글롭 `dev-*.md`가 `dev-release-pr-step`까지 여섯에 맞는다. → 고쳤다. 다섯 이름을 적었다.
- Minor 9. 01이 원천을 #534·#538로만 적었는데 #541도 `hook_push_behind_main.py`와 `ci.yml`을 고쳤고, 3-way의 직후 판이 정해지지 않았다. → 고쳤다. `git diff --stat`으로 #541(4b02bbe29)이 `ci.yml`, `hook_push_behind_main.py`, 보호 설정 둘을 고쳤음을 봤고, 세 판을 `d7fdb250e`와 `4b02bbe29`로 정했다.
- Minor 10. 03이 가리키는 "나란히 돈 마지막 티켓 둘" 문단이 이 저장소의 `issue-tracker.md`에 없고, 잔존 기준 "main에 PR한다"는 어디에도 맞지 않는다. → 고쳤다. 그 문장은 `tests/test_plan_status.py` 머리 독스트링 12행에 있다. 잔존 기준을 "기준 브랜치를 main으로 전제한 옛 표현"이라는 일반 조항으로 바꾸고, grep으로 찾은 예 셋과 찾는 말을 붙였다.
- Minor 11. CodeRabbit 갈래가 실측과 맞지 않는다. → 고쳤다(표준 축 Minor 4).
- Minor 12. "액션은 dev의 것과 견준다"가 재지 않은 추론인데 사실처럼 적혔다. → 고쳤다. ADR과 티켓 02에 머리 주석에서 끌어낸 추론이라고 적었다.
- Minor 13. 표준 축 Minor 3과 같다. → 고쳤다.
- Minor 14. 02의 경우 목록에 되돌려 합치기 PR(머리 main, base dev)이 없다. → 고쳤다. 02와 ADR Consequences에 그 PR을 더했다. agent-os의 조건식(`dev-review-bot-off.md` 22행)은 그 PR을 건너뛰지 않는다.
- Nit 15. `EnterWorktree`의 조건(표준 축 Nit 3)과, 03의 "운영 브랜치"가 정의할 용어 다섯에 없다. → 고쳤다. agent-os `CONTEXT.md`의 브랜치 모델 용어는 여덟이다(`git show`로 머리 줄을 봤다). ADR과 03이 그 여덟을 든다.

PR 직전 리뷰(`bug-perf-review`)에 밀 주장으로 넘길, 반영으로 새로 쓴 사실 문장(원문):

1. ADR: "까닭은 base를 바꾸면 커밋 검사의 base가 움직인다는 것이었다(agent-os 일지 `docs/journal/2026-11-04-01-agent-os-direction-design.md`에 옮긴 사용자 답의 설명). 이 저장소에서는 따는 순간 dev와 main이 같은 커밋이라, base를 옮겨도 PR의 diff와 커밋 검사의 판정이 그대로다."
2. ADR: "훅 러너의 사례 표(`hook_payloads.toml`)에는 agent-os에만 있는 훅의 사례가 없다."
3. ADR: "CodeRabbit은 이 저장소의 별이 10개 미만이라 자동 리뷰가 어느 PR에도 돌지 않고 `@coderabbitai review`로 불러야 돈다(운영 문서 "리뷰 파이프라인"의 2026-11-09~10 실측)."
4. ADR: "`EnterWorktree`는 `worktree.baseRef`가 기본값 `fresh`이면 새 워크트리를 `origin/<기본 브랜치>`에서 딴다(도구 설명. 2026-11-12에 사용자 설정과 프로젝트 설정에 그 키가 없었다)."
5. ADR과 티켓 03: "agent-os의 `CONTEXT.md`가 정의한 브랜치 모델의 용어(티켓 PR, 운영 브랜치, 개발 브랜치, 기준 브랜치, 루트 브랜치, 출시 PR, 핫픽스, 되돌려 합치기)"
6. 티켓 01: "#541은 티켓 5의 PR로 `hook_push_behind_main.py`에서 strict를 전제한 독스트링과 알림 문구를, 그리고 `ci.yml`을 고쳤다", "그 사이에는 agent-os에만 있는 파일(`morning_*`, `rerun_*` 등)의 변경도 섞여 있어", "`plan_table`은 main을 전제하지 않는다(설계 세션이 `main`으로 grep해 `def main`과 `__main__`만 나왔고, agent-os 전환 diff도 그 파일을 고치지 않았다)"
7. 티켓 02: "agent-os의 조건식은 그 PR을 건너뛰지 않는다"
8. 티켓 03: "설계 PR은 이 파일이 면제 모양이 아니라 고치지 못했다", "`tests/test_plan_status.py`의 머리 독스트링(나란히 돈 마지막 티켓 둘이 main의 strict로 막힌다는 문장"
9. 티켓 05: "끝 줄 시험은 `**슬라이스:**` 줄이 없는 기능 계획을 보지 않고, 하네스 기능은 티켓이 모두 done이면 끝난 것이다(`tests/test_plan_status.py` 머리 독스트링)."
10. `plan-head.md`: "하네스 기능의 기능 계획은 `**슬라이스:**` 줄이 없어 아래 표와 프론티어에 들지 않는다"

남긴 것: 표준 축 Nit 1(티켓 03, 면제 모양 밖), Nit 2(승인 뒤 이 PR에서). 다시 돌린 명령: `uv run python tools/plan_table.py`가 0으로 끝났다. 검증 명령 다섯은 커밋의 pre-commit으로 갈음하고 결과는 커밋 뒤 이 일지에 적는다.
