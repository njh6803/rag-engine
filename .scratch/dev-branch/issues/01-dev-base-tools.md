# 01: 기준 브랜치 규칙을 도구·훅·커밋 검사·CI 트리거에 싣는다

**What to build:** ADR 0016의 "도구는 agent-os의 전환 diff를 얹는다"를 한다. agent-os가 전환 티켓 1(`dev-branch-transition`)과 3(`dev-base-tools`)에서 그 저장소의 `tools/`·`tests/tools/`·`.github/workflows/ci.yml`에 한 변경을 이 저장소에 옮긴다. 원천은 agent-os `origin/dev`의 두 티켓 파일(규칙, 결정표, 반박 결과 절)과, 전환 PR 가운데 도구와 `ci.yml`을 고친 셋(#534, #538, #541. #541은 티켓 5의 PR로 `hook_push_behind_main.py`에서 strict를 전제한 독스트링과 알림 문구를, 그리고 `ci.yml`을 고쳤다)의 병합 커밋이다. 얹는 diff는 전환 직전 판 `d7fdb250e`(#534의 첫 부모)에서 설계 세션이 읽은 `origin/dev` `4b02bbe29`(#541의 병합 커밋)까지다. 그 사이에는 agent-os에만 있는 파일(`morning_*`, `rerun_*` 등)의 변경도 섞여 있어 그것은 뺀다. agent-os는 읽기만 하고 고치지 않는다(`git -C <agent-os 클론> show origin/dev:<경로>`).

- **먼저 견준다.** 이 저장소의 `tools/`·`tests/tools/` 파일마다 agent-os 전환 직전 판(#534의 첫 부모)과 같은지 본다. 설계 세션이 blob 해시로 견준 결과(일지 `docs/journal/2026-11-12-1419-dev-branch-model.md`의 "확인한 것")를 출발점으로 삼되 다시 본다.
- **같은 파일은 diff를 그대로 얹는다.** 설계 세션의 셈으로는 `hook_git_main_commit`, `hook_push_behind_main`, `tidy_checkouts`, `check_constitution_version`, `queue_open_rows`, `wait_ci`와 그 시험이다. 얹은 판이 이 저장소에 없는 것(`CONTEXT.md`, `web/`, `morning_*`, `rerun_*`, `canary`)을 가리키면 이 저장소에 맞게 고친다.
- **다른 파일은 3-way로 얹고 이 저장소의 줄을 남긴다.** `check_ticket`(면제 모양의 `GLOSSARY.md`), `sibling_overlap`(카나리아 명세가 없는 저장소의 판정), `hook_prompt_directive`, `mutate`, `run_hooks`, `hook_payloads.toml`과 그 시험이다(`git merge-file`의 세 판은 이 저장소의 파일, 전환 직전 판 `d7fdb250e`, 직후 판 `4b02bbe29`).
- **새 파일을 들인다.** `tools/base_rule.py`와 `tests/tools/test_base_rule.py`다. 세 구현(`base_rule`, `check_ticket.base_ref`, `hook_push_behind_main.base_branch`)이 같은 입력에 같은 기준을 낸다는 시험이 따라온다.
- **CI 트리거.** `ci.yml`의 push 트리거를 `main`과 `dev`로 넓히고, 머리 주석에 dev PR과 main PR이 같은 잡을 돈다는 것(ADR 0016 "main PR에만 도는 잡이 지금 없다")을 적는다.
- **옮기지 않는 것.** agent-os에만 있는 도구(`morning_*`, `rerun_*`, `canary`, `export_openapi`)의 변경, `tools/protection.json`과 `tools/protection-dev.json`(04가 바꾸고 만든다), 리뷰 봇 워크플로(02). 지시문이 이름으로 든 `plan_table`은 main을 전제하지 않는다(설계 세션이 `main`으로 grep해 `def main`과 `__main__`만 나왔고, agent-os 전환 diff도 그 파일을 고치지 않았다). 이 판단을 다시 보고 표에 적는다.

크기가 한 세션에 안 들면 `sibling_overlap`·`tidy_checkouts`와 나머지로 나누고, 이 기능 폴더의 다음 번호로 새 티켓을 쓴다. 새 티켓을 쓰면 04의 `**Blocked by:**` 줄과 1단계에 그 번호를 더한다. 04가 그 티켓이 병합되기 전에 dev를 따지 않게 하기 위해서다.

**Blocked by:** 없음 (02·03과 나란히 돈다)

**Status:** ready-for-agent

- [ ] 티켓 끝에 파일마다 들인 길(그대로 얹음, 3-way, 손으로, 옮기지 않음)과 까닭의 표가 있다
- [ ] `origin/dev`가 없을 때 모든 도구가 지금과 같은 결과를 낸다는 시험이 있다
- [ ] `origin/dev`가 있을 때 `feature/*`·`chore/*`·`docs/*`는 dev, `hotfix/*`는 main을 기준으로 한다는 시험이 있고, `tests/tools/test_base_rule.py`가 세 구현을 묶는다
- [ ] `hook_git_main_commit`이 `dev` 위의 `git commit`을 막고 `main`을 그대로 막으며, `git merge`가 만든 병합 커밋은 막지 않는다는 시험이 있다
- [ ] `check_ticket`이 `hotfix/<slug>`를 `.scratch/harness/issues/<slug>.md`의 티켓으로 알아보고, 머리 브랜치가 `dev`나 `main`인 PR을 지나며, 이 저장소의 면제 모양(`GLOSSARY.md`)이 남아 있다
- [ ] `tidy_checkouts`와 `sibling_overlap`의 변경은 agent-os 티켓 3의 "반박 결과" 입력을 이 저장소의 임시 저장소에서 다시 쳐서 같은 판정을 봤고(`.claude/rules/tools.md`의 지우는 도구 반박 항목), 결과를 티켓 끝에 적었다
- [ ] `sibling_overlap`이 카나리아 명세가 없는 저장소에서 바꾼 하네스 파일을 세지 않는 판정이 남아 있다
- [ ] `ci.yml`이 dev 푸시에서도 돌고 필수 검사 `verify`의 `needs`는 그대로다
- [ ] `tools/run_hooks.py`가 통과하고, 변이 표가 있는 훅은 `tools/mutate.py`로 새 갈래를 깨어 빨강을 봤다
- [ ] 이 티켓은 `origin/dev`가 없는 채로 병합되고, 병합 뒤 모든 도구가 지금처럼 main을 기준으로 돈다
- [ ] 검사 넷이 초록이다
