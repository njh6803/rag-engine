# dev-branch: 브랜치 모델을 agent-os ADR 0043으로 옮긴다. 티켓 PR은 dev로, 출시는 dev→main merge 커밋, 핫픽스는 main에서
**Blocked by:** 없음
**설계:** ADR 0016. 일지 `docs/journal/2026-11-12-1419-dev-branch-model.md`

하네스 기능이다(`**슬라이스:**` 줄이 없어 전체 계획 표에 들지 않는다). 이 저장소의 브랜치 모델을 agent-os ADR 0043으로 옮긴다. 무엇을 따르고 무엇이 다른지는 ADR 0016이 원천이고, 이 계획은 티켓의 차례만 적는다.

티켓은 다섯이다(`issues/`). 01(도구·훅·커밋 검사·CI 트리거), 02(리뷰 봇), 03(스킬·규약 문서·되돌려 합치기 순서)은 서로 겹치는 파일이 없어 나란히 돌 수 있고, 03은 01과 02가 병합된 뒤에 병합한다. 04(원격 설정과 dev 따기)는 앞의 셋(01을 쪼개 더한 티켓이 있으면 그것까지)이 병합된 뒤에 한다. 도구가 dev를 따는 순간부터 `origin/dev`를 기준으로 쓰기 때문이다. 05(출시 PR을 여는 순서와 main의 strict)는 04가 병합되고, agent-os의 harness 티켓 `dev-release-pr-step`이 그 저장소의 `origin/dev`에 병합된 뒤에 한다. 그때까지 출시 PR은 열지 않는다. 이 기능은 전체 계획의 표에 들지 않으므로, 05를 다시 집게 하는 자리는 `.scratch/plan-head.md`의 "하네스 기능" 문단과 04가 일지의 "다음"에 적는 줄이다.

이 기능이 다른 기능에 넘긴 것: 느린 검사를 main PR에만 둘지는 그 검사를 더하는 기능이 정한다(search-eval의 적중률 게이트, release-image의 단독 compose. 두 계획의 본문에 적었다).

agent-os 쪽의 원천은 그 저장소의 `origin/dev`에 있는 ADR 0043, `.scratch/harness/issues/`의 `dev-branch-transition.md`·`dev-review-bot-off.md`·`dev-base-tools.md`·`dev-base-skills-docs.md`·`dev-branch-create.md`(각 티켓의 결과 절), `tools/base_rule.py`, `tools/protection.json`, `tools/protection-dev.json`이다. agent-os는 읽기만 하고 고치지 않는다.
