# 05: 출시 PR을 여는 순서와 main의 strict를 agent-os에 맞춘다

**What to build:** 출시 PR(dev→main)을 누가 언제 어떤 순서로 여는지와, main이 strict라서 둘째 출시 PR부터 뒤처짐(BEHIND)이 날 것이라는 어림을 agent-os가 harness 티켓 `dev-release-pr-step`에서 정하는 중이다(설계 세션 때 병합 전). 그 결과가 agent-os의 `origin/dev`에 병합된 뒤 그 티켓 파일과 바뀐 스킬·문서(`next-session` `merge.md`, `docs/constitution/operations.md`, 보호 설정 파일)를 읽어 이 저장소에 옮긴다. main 보호의 strict는 그 결과를 보고 사용자에게 다시 묻고 정한다. 그때까지 출시 PR은 열지 않는다(ADR 0016).

- 옮긴 결정을 ADR 0016의 이력에 더하고, 이력이 본문 문장("출시 PR을 여는 순서와 main의 strict는 아직 정하지 않는다")을 거짓으로 만들면 그 문장 뒤에 포인터를 단다(`.claude/rules/adr.md`).
- main의 strict를 바꾸면 `tools/protection.json`을 고쳐 PUT하고, 사용자의 승인을 받은 뒤에 한다.
- 이 기능의 마지막 티켓이다. 끝 줄 시험은 `**슬라이스:**` 줄이 없는 기능 계획을 보지 않고, 하네스 기능은 티켓이 모두 done이면 끝난 것이다(`tests/test_plan_status.py` 머리 독스트링). 그래서 기능 계획에 `**끝:**` 줄을 적지 않는다. 닫는 커밋이 `.scratch/plan-head.md`의 "하네스 기능" 문단에서 dev-branch를 지우고 `uv run python tools/plan_table.py`를 돌아 결과를 같은 커밋에 싣는다.
- 첫 출시 PR을 이 티켓이 열지, 옮긴 순서를 따르는 다음 세션에 맡길지는 옮긴 순서대로 한다.

**Blocked by:** 04, 그리고 agent-os의 harness 티켓 `dev-release-pr-step`이 그 저장소의 `origin/dev`에 병합됨(`git -C <agent-os 클론> show origin/dev:.scratch/harness/issues/dev-release-pr-step.md`의 `Status:`가 done)

**Status:** ready-for-agent

- [ ] agent-os `dev-release-pr-step`의 결과(그 티켓 파일, 바뀐 스킬·문서·보호 설정 파일)를 읽었고, 옮긴 곳과 옮기지 않은 곳과 까닭의 표가 티켓 끝에 있다
- [ ] 출시 PR을 여는 순서가 `next-session`과 운영 문서에 적혀 있다
- [ ] main의 strict를 사용자에게 다시 물었고 답과 반영(바꿨으면 응답 값)을 티켓 끝에 적었다
- [ ] ADR 0016에 이력이 있고, `tools/check_adr_pointers.py`가 통과한다
- [ ] `.scratch/plan-head.md`의 "하네스 기능" 문단에서 dev-branch가 빠졌고 `uv run python tools/plan_table.py`의 결과가 같은 커밋에 실렸다
- [ ] 검사 넷이 초록이다
