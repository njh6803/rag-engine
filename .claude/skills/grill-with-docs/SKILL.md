---
name: grill-with-docs
description: "설계 인터뷰. 사용자가 이를 요청할 때('grill', '인터뷰 진행하자'), 또는 기능에 명세(`.scratch/<slug>/spec.md`)도 기능 계획의 `**설계:**` 줄도 없는 단계일 때만 부른다. 구현과 리뷰 중에는 하던 일을 이어 간다."
---

<!-- 프로젝트 사본, model-invoked. 원본(mattpocock/skills)은 disable-model-invocation: true. agent-os가 덧댄 판을 2026-11-09 킥오프에서 옮겼고, 괄호 속 일지·ADR 번호는 agent-os의 기록이다. agent-os에서 사용자가 다른 세션에서 설계 인터뷰를 `grilling`만 불러 진행했고, 그 결과 `domain-modeling`이 하는 용어집(이 저장소는 GLOSSARY.md) 기록과 ADR 초안이 빠졌다. 이 스킬이 둘을 차례로 부르는 라우터라서, 모델이 이 스킬을 부를 수 있어야 한 번에 둘 다 돈다(agent-os 일지 2026-10-15-10). 모델이 부르면 설명이 모든 세션에 실리므로 설명은 짧게, 트리거는 좁게 썼고, 부르기 직전 `tools/hook_grill_design_check.py`가 설계 인터뷰가 맞는지 확인하라는 계기를 넣는다(agent-os ADR 0028 이력 2026-10-15). `to-spec`·`to-tickets`·`implement`는 단계를 넘어갈지 사람이 정하는 관문이라 사용자 전용으로 둔다. 설계 인터뷰의 계기는 명세도 설계 줄도 없는 기능이라는 하나의 조건이고(설명, `docs/agents/issue-tracker.md` 전체 계획 절의 설계 줄 항목, 훅, `next-session` 결정표가 같은 말을 쓴다), 인터뷰를 마친 표지는 산출물 단계가 기능 계획에 적는 `**설계:**` 줄이다(agent-os ADR 0045 결정 4와 이력 2026-11-06). 이 주석이 `tools/check_instructions.py`의 센티널이라 지우면 검사가 빨강이 된다. -->

Call the Skill tool twice, for "grilling" and "domain-modeling".

산출물 단계. 두 스킬이 끝나고 사용자가 설계를 승인하면 기능 계획 `.scratch/<slug>/plan.md`에 `**설계:** ADR NNNN` 줄을 적는다. ADR을 내지 않은 설계면 설계 일지의 이름을 적는다. 줄은 `**Blocked by:**` 줄 뒤, `**끝:**` 줄이 있다면 그 앞에 둔다. 기능 계획이 아직 없는 새 기능이면 이 세션이 첫 줄 `# <slug>: <한 줄 요약>`, `**슬라이스:** N`, `**Blocked by:**` 줄로 기능 계획을 만든다(모양의 원천은 `docs/agents/issue-tracker.md`의 전체 계획 절. 하네스 기능은 `**슬라이스:**` 줄을 두지 않는다). 기능 계획을 만들거나 고쳤으면 `uv run python tools/plan_table.py`를 돌려 `.scratch/plan.md`까지 같은 커밋에 싣는다. 끝: 설계 줄이 기능 계획에 있고 도구가 0으로 끝났다.
