---
status: accepted
date: 2026-11-12
---

# 브랜치 모델은 agent-os ADR 0043을 따르고, 이 저장소에서 다른 것만 적는다

지금 브랜치는 main 하나다. 티켓마다 브랜치를 따서 main으로 PR하고 squash로 합친다(`docs/constitution/operations.md`의 "브랜치와 병합"). 일하는 방식의 원천은 agent-os 저장소(`njh6803/agent-os`)이고, 공통 ADR 저장소나 공통 하네스 저장소는 두지 않는다(사용자가 2026-11-11에 정했다, agent-os 일지 `docs/journal/2026-11-11-1532-release-image-design-round3.md`). 그래서 **이 저장소의 브랜치 모델은 agent-os의 ADR 0043(`docs/adr/0043-dev-integrates-and-main-releases.md`)을 따른다.** 티켓 PR은 dev로 가서 squash로 합치고, 기능 하나가 끝나면 dev를 main에 merge 커밋으로 올리며(출시 PR), 핫픽스는 main에서 따서 main에 합친 뒤 main을 dev에 되돌려 합친다. 기준 브랜치 규칙(`hotfix/*`는 main, 그 밖은 이 클론에 `origin/dev`의 추적 ref가 있으면 dev, 없으면 main)과, agent-os가 전환을 나눈 티켓 다섯(그 저장소의 `.scratch/harness/issues/`에 있는 `dev-branch-transition`, `dev-review-bot-off`, `dev-base-tools`, `dev-base-skills-docs`, `dev-branch-create`)의 결과도 그대로 따른다. 결정 본문은 옮겨 적지 않고, 이 ADR은 이 저장소에서 다른 것과 전환의 차례만 적는다. 설계 인터뷰(일지 `docs/journal/2026-11-12-1419-dev-branch-model.md`)가 정했다.

## 이 저장소에서 다른 것

- **main PR에만 도는 잡이 지금 없다.** ADR 0043은 main PR에 LLM 테스트와 실제 이미지의 compose e2e를 더한다. 이 서버는 답을 만들지 않아 LLM을 부르는 테스트가 없고, compose e2e는 아직 없다. 그래서 dev PR과 main PR이 같은 잡(`.github/workflows/ci.yml`의 `python`, `image`, `ticket`과 필수 검사인 모음 잡 `verify`)을 돈다. 느린 검사(search-eval의 적중률 게이트, release-image의 단독 compose)를 main PR에만 둘지는 그 기능의 설계가 정한다(바뀜: ADR 0018). 그래서 지금 dev는 PR을 빠르게 하지 않는다. 그래도 옮기는 까닭은 두 저장소가 같은 방식으로 일하고, main이 출시된 기능만 든 머리가 되게 하기 위해서다(판을 어디서 내는지는 release-image가 정한다).
- **원격 설정.** 기본 브랜치를 dev로 옮기고, 각 클론에서 `git remote set-head origin dev`를 친다. dev는 `verify`를 필수로 두되 strict와 선형 이력 강제를 끄고, 강제 푸시와 삭제를 막는다(`tools/protection-dev.json`). main은 선형 이력 강제를 끈다(`tools/protection.json`). 출시 PR이 merge 커밋이기 때문이다. agent-os가 2026-11-12에 고른 값과 같고, 이 저장소에서는 사용자가 인터뷰에서 다시 골랐다. 실제 변경은 티켓 04가 사용자의 승인을 다시 받고 한다.
- **출시 PR을 여는 순서와 main의 strict는 아직 정하지 않는다.** agent-os가 harness 티켓 `dev-release-pr-step`에서 정하는 중이다. 그 결과가 agent-os의 `origin/dev`에 병합된 뒤 티켓 05가 옮기고 이 ADR에 이력을 더한다. 그때까지 출시 PR은 열지 않고 main의 strict는 지금대로 둔다. 그동안 main은 dev보다 뒤처진다. main을 받아 쓰는 곳(배포된 이미지)이 아직 없어 그 값이 작다.
- **전환 티켓은 하네스 기능의 티켓이다.** harness 티켓(`.scratch/harness/issues/`)이 아니라 하네스 기능 `.scratch/dev-branch/`의 티켓 `issues/01`~`05`다. 이 저장소의 커밋 검사는 `docs/` 브랜치에 실린 harness 티켓이 모두 done이기를 CI에서 요구해(`tools/check_ticket.py`), 설계 PR이 `ready-for-agent` harness 티켓을 실을 수 없기 때문이다. 번호 뒤의 이름은 agent-os의 티켓 이름을 따른다. 핫픽스의 티켓은 agent-os와 같이 `hotfix/<slug>` 브랜치와 `.scratch/harness/issues/<slug>.md`다.
- **도구는 agent-os의 전환 diff를 얹는다.** 이 저장소의 도구는 agent-os에서 복사한 뒤 이 저장소에 맞게 고친 줄이 있다. 예로 커밋 검사의 면제 모양은 용어집 파일 이름이 다르고, `sibling_overlap`은 카나리아 명세가 없는 저장소를 따로 판정하며, 훅 러너의 사례 표(`hook_payloads.toml`)에는 agent-os에만 있는 훅의 사례가 없다. 파일마다 얼마나 다른지는 일지의 "확인한 것"에 있다. 그래서 고친 판을 통째로 복사하지 않고, agent-os 전환 커밋의 diff를 이 저장소 파일에 얹어 이 저장소의 줄을 남긴다. 스킬과 규약 문서는 이 저장소에 맞게 고친 곳이 많아 손으로 맞춘다.
- **dev를 딴 순간 열린 PR은 base를 dev로 옮긴다.** ADR 0043은 "전환 때 열린 PR도 base를 dev로 바꾼다"를 거부하고, 그때 열린 PR(그 ADR을 싣는 PR 포함)을 main으로 끝냈다. 까닭은 base를 바꾸면 커밋 검사의 base가 움직인다는 것이었다(agent-os 일지 `docs/journal/2026-11-04-01-agent-os-direction-design.md`에 옮긴 사용자 답의 설명). 이 저장소에서는 따는 순간 dev와 main이 같은 커밋이라, base를 옮겨도 PR의 diff와 커밋 검사의 판정이 그대로다. 그래서 옮긴다. 다만 따고 나서 옮기기까지 main에 다른 병합이 들면 그 전제가 깨지므로, 옮기기 직전에 두 브랜치가 아직 같은 커밋인지 다시 본다. 핫픽스 PR(`hotfix/*`)은 옮기지 않는다(티켓 04).
- **용어는 `GLOSSARY.md`가 아니라 운영 문서에 둔다.** ADR 0043은 용어를 agent-os의 `CONTEXT.md`에 둔다. 이 저장소의 `GLOSSARY.md`는 제품의 말만 들고 티켓이나 기능 계획 같은 하네스의 말을 들지 않는다. 그래서 agent-os의 `CONTEXT.md`가 정의한 브랜치 모델의 용어(티켓 PR, 운영 브랜치, 개발 브랜치, 기준 브랜치, 루트 브랜치, 출시 PR, 핫픽스, 되돌려 합치기)는 `docs/constitution/operations.md`의 "브랜치와 병합"이 정의한다(티켓 03).

## 전환의 차례

1. `01-dev-base-tools`: 기준 브랜치 규칙(`tools/base_rule.py`), 커밋을 막는 훅과 푸시 훅, 커밋 검사, 나머지 도구, `ci.yml`의 push 트리거.
2. `02-dev-review-bot-off`: 리뷰 봇(`claude-code-review.yml`)이 dev→main PR을 건너뛴다. 그 파일을 바꾼 PR은 봇이 건너뛰고 기록 밖 파일을 함께 실으면 실패하므로 따로 PR이다.
3. `03-dev-base-skills-docs`: 스킬, `CLAUDE.md`, 헌법 운영 문서, `docs/agents/issue-tracker.md`, PR 서식, `next-session`의 되돌려 합치기 순서. 01과 02가 병합된 뒤에 병합한다. 문서가 가리키는 도구가 main에 있어야 하고, 02가 넘긴 것을 운영 문서에 적기 때문이다.
4. `04-dev-branch-create`: 앞의 셋(01을 쪼개 더한 티켓이 있으면 그것까지)이 병합된 뒤 원격 설정을 바꾸고 dev를 main에서 따며, 열린 PR의 base를 옮긴다.
5. `05-dev-release-pr-step`: agent-os의 `dev-release-pr-step`이 그 저장소의 `origin/dev`에 병합된 뒤, 출시 PR을 여는 순서와 main의 strict를 옮긴다.

01·02·03은 서로 겹치는 파일이 없어 나란히 돌 수 있다. 도구는 dev를 따는 순간부터 `origin/dev`를 기준으로 쓰므로, dev는 04가 마지막에 딴다. 그때까지는 지금 규약(main으로 PR)이 그대로다.

## Considered Options

- **agent-os처럼 harness 티켓으로 쓰고 첫 티켓의 PR이 나머지 티켓을 싣는다.** 이 PR에 티켓 파일이 없어 다음 세션이 옮기는 일이 하나 더 생기고, 그동안 다른 티켓을 나란히 시작할 수 없다. 거부했다.
- **티켓을 agent-os처럼 다섯으로 나누거나(도구를 규칙 몫과 나머지 몫으로), 셋으로 줄인다(도구와 스킬·문서를 한 장에).** 이 저장소의 도구는 diff를 얹는 일이라 한 장에 들고, 리뷰 봇은 따로 PR이어야 해서 셋보다 줄일 수 없다. 넷에 출시 순서 한 장을 더했다.
- **기본 브랜치를 main에 둔다.** base를 주지 않은 `gh pr create`와 base를 기본 브랜치로 감지하는 사용자 수준 스킬이 티켓 PR을 main으로 연다. 거부했다.
- **dev에 strict를 켜거나 dev를 보호하지 않는다.** strict이면 머리가 main인 되돌려 합치기 PR이 늘 뒤처짐으로 막혀 관리자 우회로만 병합되고, 보호하지 않으면 dev로의 강제 푸시와 빨간 PR의 병합이 막히지 않는다. 둘 다 거부했다.
- **main의 선형 이력 강제를 켜 두고 출시 PR만 관리자 우회로 병합한다.** 혼자일 때만 되는 길이고 출시마다 보호를 건너뛴다. 거부했다.
- **열린 PR을 main으로 끝내고 되돌려 합치거나, 열린 PR이 없을 때만 dev를 딴다.** 앞의 것은 출시되지 않은 티켓이 main에 먼저 들고 PR마다 되돌려 합치기가 하나씩 는다. 뒤의 것은 다른 세션이 PR을 여는 동안 기다림이 길어질 수 있다. 둘 다 거부했다.
- **dev를 따는 일도 agent-os의 출시 순서를 기다린다.** 그동안 앞의 셋이 병합된 채 도구가 main을 기준으로 돌고 전환이 미뤄진다. 거부했다.

## Consequences

- **헌법 개정.** `docs/constitution/operations.md`의 "브랜치와 병합", "가드레일", "리뷰 파이프라인"이 바뀌고 판이 오른다(티켓 03). 이 ADR이 그 개정의 근거다.
- **리뷰 봇 두 갈래.** `claude-code-review.yml`의 머리 주석대로라면 Claude Code Review 액션은 PR의 워크플로 파일을 기본 브랜치의 것과 견주므로, 기본 브랜치가 dev가 되면 dev의 것과 견줄 것이다(주석과 코드를 읽은 추론이고 재 보지 않았다). 그러면 dev에서 그 파일이 바뀌고 아직 출시되지 않은 동안에는 main을 머리로 둔 PR(main에서 딴 핫픽스 PR, 되돌려 합치기 PR)이 리뷰를 건너뛰고, 코멘트가 없다고 그 잡이 빨개질 수 있다(필수 검사는 아니다). 티켓 02가 이것을 다룬다. (바뀜: 이력 2026-11-12 "리뷰 봇 두 갈래의 추론과 확인할 것을 02의 결정과 CodeRabbit 문서 확인으로 맞춘다") CodeRabbit은 이 저장소의 별이 10개 미만이라 자동 리뷰가 어느 PR에도 돌지 않고 `@coderabbitai review`로 불러야 돈다(운영 문서 "리뷰 파이프라인"의 2026-11-09~10 실측). 부른 리뷰가 base가 기본 브랜치가 아닌 PR에서도 도는지는 확인하지 않았다(어림). 티켓 03이 확인한다. (바뀜: 이력 2026-11-12 "리뷰 봇 두 갈래의 추론과 확인할 것을 02의 결정과 CodeRabbit 문서 확인으로 맞춘다").
- **다른 세션.** 이 저장소의 워크트리는 주 체크아웃의 `.git`을 함께 써서, dev를 딴 뒤 한 체크아웃에서 친 `git fetch origin`과 `git remote set-head origin dev`가 모든 워크트리에 미친다. `EnterWorktree`는 `worktree.baseRef`가 기본값 `fresh`이면 새 워크트리를 `origin/<기본 브랜치>`에서 딴다(도구 설명. 2026-11-12에 사용자 설정과 프로젝트 설정에 그 키가 없었다). 그 전에 쓴 지시문을 따르는 세션을 위해 티켓 04가 보고와 지시문에 이 두 줄을 싣는다.
- **원칙 III.** 이 ADR이 agent-os를 드는 것은 하네스의 원천으로서이고, MCP 클라이언트로서가 아니다. 원칙 III은 서버가 클라이언트를 모른다는 제품 계약의 원칙이다. 대기열 `client-name-in-spec-body`가 처방한 낱말 검사가 `docs/adr/`의 산문에서 `agent-os`를 경고하게 되면 이 ADR이 걸린다.
- **치르는 값.** dev PR은 지금보다 빨라지지 않는다. 출시마다 출시 PR이, 핫픽스마다 되돌려 합치기 PR이 하나씩 는다. 티켓 05 전까지 main이 dev보다 뒤처진다. agent-os가 하네스를 바꾸면 이 저장소가 따라 옮겨야 하고, 두 저장소가 벌어진 곳을 알리는 점검 도구는 agent-os의 다음 하네스 일이다(그 저장소의 대기열 `rag-engine-harness-drift`).

## 이력

### 2026-11-12 리뷰 봇 두 갈래의 추론과 확인할 것을 02의 결정과 CodeRabbit 문서 확인으로 맞춘다

티켓 `.scratch/dev-branch/issues/03-dev-base-skills-docs.md`가 고쳤다. 본문 Consequences "리뷰 봇 두 갈래"는 그대로 두고 아래 둘을 바로잡는다. 하나는 티켓 `02-dev-review-bot-off`가 다룬 결과다. 기본 브랜치가 dev인 동안 main에서 딴 `hotfix/*`를 머리로, main을 base로 둔 핫픽스 PR이 액션의 워크플로 검증으로 건너뛰어지는 갈래는 알려진 빨강으로 둔다. 가드를 풀지 않고, 건너뛴 잡은 필수 검사가 아니라 병합을 막지 않으며, 그 PR의 리뷰는 PR 직전 리뷰와 셀프 리뷰가 대신한다. 이 갈래는 02 티켓이 액션 소스의 오류 코드와 안내 문구를 읽고 낸 추론이고 서버 쪽 비교는 보지 못했다(이 저장소에서 액션 소스를 다시 읽지 않았다). 되돌려 합치기 PR은 건너뛰지 않고 돈다. 다른 하나는 본문 끝의 "티켓 03이 확인한다"(CodeRabbit)가 닫힌 결과로, 공식 문서 `docs.coderabbit.ai/configuration/auto-review.md`를 `curl`로 내려받아 읽은 것으로 맞췄다. 문서는 자동 리뷰가 기본적으로 기본 브랜치를 base로 둔 PR만 보고(`base_branches`가 다른 base를 더하며 기본 브랜치는 늘 든다), 수동 호출은 자동 리뷰 설정과 상관없이 언제나 된다고 적는다. 이 저장소는 별이 0개(2026-11-12 `gh repo view`)라 자동 리뷰가 돌지 않고 수동 호출만 쓰므로, base가 기본 브랜치가 아닌 PR에서도 부르면 돈다고 본다. 문서가 base를 따로 가르지 않아 어림이고 그런 PR에서 불러 재 보지 않았으므로 첫 핫픽스 PR에서 본다. 자동 리뷰가 열리면 `.coderabbit.yaml`의 `auto_review.base_branches`에 `main`이 필요한지 그때 정한다. 이 판단은 운영 문서 "리뷰 파이프라인"에도 적었다.
