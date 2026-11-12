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

**Status:** done

- [x] 티켓 끝에 파일마다 들인 길(그대로 얹음, 3-way, 손으로, 옮기지 않음)과 까닭의 표가 있다
- [x] `origin/dev`가 없을 때 모든 도구가 지금과 같은 결과를 낸다는 시험이 있다
- [x] `origin/dev`가 있을 때 `feature/*`·`chore/*`·`docs/*`는 dev, `hotfix/*`는 main을 기준으로 한다는 시험이 있고, `tests/tools/test_base_rule.py`가 세 구현을 묶는다
- [x] `hook_git_main_commit`이 `dev` 위의 `git commit`을 막고 `main`을 그대로 막으며, `git merge`가 만든 병합 커밋은 막지 않는다는 시험이 있다
- [x] `check_ticket`이 `hotfix/<slug>`를 `.scratch/harness/issues/<slug>.md`의 티켓으로 알아보고, 머리 브랜치가 `dev`나 `main`인 PR을 지나며, 이 저장소의 면제 모양(`GLOSSARY.md`)이 남아 있다
- [x] `tidy_checkouts`와 `sibling_overlap`의 변경은 agent-os 티켓 3의 "반박 결과" 입력을 이 저장소의 임시 저장소에서 다시 쳐서 같은 판정을 봤고(`.claude/rules/tools.md`의 지우는 도구 반박 항목), 결과를 티켓 끝에 적었다
- [x] `sibling_overlap`이 카나리아 명세가 없는 저장소에서 바꾼 하네스 파일을 세지 않는 판정이 남아 있다
- [x] `ci.yml`이 dev 푸시에서도 돌고 필수 검사 `verify`의 `needs`는 그대로다
- [x] `tools/run_hooks.py`가 통과하고, 변이 표가 있는 훅은 `tools/mutate.py`로 새 갈래를 깨어 빨강을 봤다
- [x] 이 티켓은 `origin/dev`가 없는 채로 병합되고, 병합 뒤 모든 도구가 지금처럼 main을 기준으로 돈다
- [x] 검사 넷이 초록이다

## 얹은 길

원천은 agent-os `origin/dev`의 전환 직전 판 `d7fdb250e`와 직후 판 `4b02bbe29`다. 구간의 도구·시험·`ci.yml` 변경은 PR #534·#538·#541 셋의 것이고(`git log --first-parent`로 PR마다 파일을 나눠 봤다), 구간의 나머지 PR(#536, #537, #539, #540)은 `tools/`와 `tests/tools/`와 `ci.yml`을 건드리지 않았다(같은 경로 제한으로 `git log --no-merges`를 쳐 확인했다). 블롭 해시 견줌은 이 저장소 `HEAD`를 직전 판과 직후 판에 맞댄 것이고 설계 세션의 셈과 같게 나왔다. "그대로 얹음"은 `git diff d7fdb250e 4b02bbe29`를 `git apply`로, "3-way"는 `git merge-file`(이 저장소의 파일, 직전 판, 직후 판)로 얹었다. 3-way 열 파일은 모두 충돌 0이었다.

| 파일 | 길 | 까닭 |
|---|---|---|
| `tools/base_rule.py`, `tests/tools/test_base_rule.py` | 새 파일(직후 판) + 손으로 | 이 저장소에 없던 파일이다. 독스트링이 원천으로 든 agent-os의 티켓 경로(`.scratch/harness/issues/dev-branch-transition.md`)는 이 저장소에 없어 ADR 0016으로 고쳤다 |
| `tools/check_constitution_version.py`, `tests/tools/test_check_constitution_version.py` | 그대로 얹음 | 직전 판과 같았다 |
| `tools/hook_git_main_commit.py`, `tests/tools/test_hook_git_main_commit.py` | 그대로 얹음 | 직전 판과 같았다. `dev` 위의 커밋을 막고 `git merge`가 만든 병합 커밋은 막지 않는다 |
| `tools/hook_push_behind_main.py`, `tests/tools/test_hook_push_behind_main.py` | 그대로 얹음 + 손으로 | 직전 판과 같았다. 독스트링이 이 저장소에 없는 티켓 경로, 프로브(`ci_wait/runs_per_pr.py`), 보호 설정(`tools/protection-dev.json`, 04가 만든다)을 가리켜 ADR 0016과 04로 고치거나 뺐다 |
| `tools/queue_open_rows.py`, `tools/wait_ci.py` | 그대로 얹음 | 직전 판과 같았고 안내 글만 바뀐다. 시험은 이 구간에서 바뀌지 않았다 |
| `tools/tidy_checkouts.py`, `tests/tools/test_tidy_checkouts.py` | 그대로 얹음 + 손으로 | 직전 판과 같았다. 반박이 찾은 공백 하나를 시험으로 메웠다(아래) |
| `tools/check_ticket.py`, `tests/tools/test_check_ticket.py` | 3-way + 손으로 | 이 저장소의 줄(면제 모양의 `GLOSSARY.md`)이 남았다. `hotfix/<slug>`를 `.scratch/harness/issues/<slug>.md`의 티켓으로 알아본다. 독스트링이 핫픽스 티켓의 자리를 `docs/agents/issue-tracker.md`로 근거 삼았는데 그 문서의 "기능 밖에서 제품 코드를 고치는 일" 항목은 기능 디렉터리의 티켓을 말해 서로 어긋나서, 근거를 ADR 0016으로 고치고 어긋남을 적었다. 그 문서에 핫픽스를 적는 일은 이 티켓의 범위 밖이다 |
| `tools/sibling_overlap.py`, `tests/tools/test_sibling_overlap.py` | 3-way + 손으로 | 카나리아 명세가 하나도 없는 저장소에서 바꾼 하네스 파일을 세지 않는 판정이 남았다(`test_카나리아_명세가_하나도_없는_저장소에서는_바꾼_스킬을_알리지_않는다`). 기준이 아닌 오래 사는 브랜치의 끝이 이 브랜치의 조상이 아니어도 `HEAD`와의 merge-base 시점의 ADR을 물려받은 것으로 센다(PR 봇 첫 회차의 Major, 아래 "반박 결과"). agent-os `origin/dev`의 같은 분기에는 이 줄이 없다 |
| `tools/hook_prompt_directive.py`, `tools/mutate.py`, `tools/run_hooks.py`, `tests/tools/test_run_hooks.py`, `tools/hook_payloads.toml` | 3-way | 이 저장소에만 있는 줄(헤드리스 가름의 옮긴 판, agent-os에만 있는 훅 열아홉의 사례 빠짐)이 남았다. 훅 러너는 124건 어긋남 0건이다 |
| `.github/workflows/ci.yml` | 3-way + 손으로 | push 트리거를 `main`과 `dev`로 넓혔다. 직후 판의 머리 주석이 agent-os의 잡 수(일곱), `ci-llm-job`, ADR 0056을 말해 이 저장소의 잡(`python`, `image`, `ticket`, 모음 잡 `verify`)과 ADR 0016 "main PR에만 도는 잡이 지금 없다"로 다시 썼다. 잡과 `verify`의 `needs`는 그대로다 |
| `tools/plan_table.py` | 옮기지 않음 | `main`으로 grep하면 `def main`과 `__main__`뿐이다(이 세션이 다시 봤다). agent-os 전환 diff도 이 파일을 고치지 않았다 |
| `tools/hook_bash_msys_pathconv.py`, `tools/hook_pr_head_sync.py` | 그대로 둠 | `origin/main`은 명령 예시 글이다 |
| `tools/morning_*.py`, `tools/rerun_select.py`, `tests/tools/test_morning_*.py` | 옮기지 않음 | 이 저장소에 없는 도구다 |
| `tools/canary.py`, `tools/export_openapi.py` | 옮기지 않음 | 이 저장소에 없는 도구다 |
| `tools/protection.json`, `tools/protection-dev.json` | 옮기지 않음 | 04가 바꾸고 만든다 |
| `.github/workflows/claude-code-review.yml` | 옮기지 않음 | 02의 몫이다 |

`tools/`에서 `origin/main`·`refs/remotes/origin/main`·`"main"`을 센 12개 파일(55곳)은 위 표의 파일로 모두 닿는다. 얹은 판이 이 저장소에 없는 것(`CONTEXT.md`, `web/`, `morning_*`, `rerun_*`, `canary`)을 가리키는지는 더해진 줄만 `git diff -U0`로 골라 같은 낱말로 grep해 0건임을 봤다. 얹기 전부터 있던 그런 가리킴(`tidy_checkouts.py`의 `web/` 경로 등)은 이 티켓이 바꾸지 않았다. 독스트링의 `ADR 0043`은 agent-os의 번호라 "agent-os ADR 0043"으로 출처를 밝혔다.

## 시험과 확인

- 변경한 시험 일곱 파일(`test_check_ticket`, `test_hook_git_main_commit`, `test_hook_push_behind_main`, `test_tidy_checkouts`, `test_sibling_overlap`, `test_run_hooks`, `test_check_constitution_version`)과 `test_base_rule.py`를 합친 여덟 파일이 715개 통과했다(`uv run pytest <여덟 파일> -n 4`. 이 가운데 `test_base_rule.py`는 35개이고, `tidy_checkouts`의 대소문자 시험 둘과 `sibling_overlap`의 물려받은 ADR 시험 하나가 이 수에 든다).
- `origin/dev`가 없을 때의 결과는 `test_dev가_없으면_모두_main을_기준으로_한다`(`test_base_rule.py`)와 `check_ticket`·`hook_push_behind_main`·`sibling_overlap`의 "dev가 없으면 main" 전용 시험이 고정한다. `tidy_checkouts`에는 그런 전용 시험이 없고, 기존 시험이 `origin/dev`가 없는 임시 저장소에서 돌아 간접으로만 덮는다(dev가 없을 때 판정은 같고 이유 줄의 글만 `origin/main 이나 origin/dev`로 바뀐다고 agent-os 티켓이 적었다). `origin/dev`가 있을 때 `feature/*`·`chore/*`·`docs/*`는 dev, `hotfix/*`는 main이라는 갈래는 `test_세_구현은_같은_저장소와_브랜치에서_같은_기준을_낸다`가 `BRANCHES` 아홉 이름과 `with_dev` 둘로 `base_rule`, `hook_push_behind_main.base_branch`, `check_ticket.base_ref`를 묶는다.
- 변이: `.scratch/harness/probes/dev_base_tools_mutations.toml`의 변이 10개가 모두 기대대로 빨강이다(`PYTHONUTF8=1 uv run python tools/mutate.py .scratch/harness/probes/dev_base_tools_mutations.toml`). 이 저장소에는 이 도구들을 겨눈 변이 표가 없어 새로 지었고, 기대 표지는 변이가 만든 받은 값의 문구다. 9번(`tidy_checkouts`의 워크트리 판정에서 `casefold`를 뺀다)은 첫 실행에서 초록이었다(아래).
- 훅 러너: `uv run python tools/run_hooks.py`가 훅 페이로드 124건, 어긋남 0건, 래퍼 알림 4건, 어긋남 0건, 표의 빈자리 0건으로 끝났다. `hook_git_main_commit`의 사례에 `dev` 위의 커밋(막는다)과 `dev` 위의 `git merge`(막지 않는다)가 든다.

## 반박 결과

agent-os 티켓 `dev-base-tools`의 "반박 결과" 입력은 `tidy_checkouts`와 `sibling_overlap`의 시험으로 얹혀 왔다. 이 저장소의 임시 저장소(`tmp_path`에 만든 저장소)에서 그 시험이 같은 판정을 내는지 봤다. 손으로 따로 입력을 친 것은 아니다.

- `tidy_checkouts`: 분리 HEAD·브랜치가 `origin/dev`에만 있을 때 지울 후보, 어디에도 없으면 넘김(`test_judge_는_분리_HEAD_가_origin_dev_…` 둘, `test_judge_는_PR_없이_origin_dev_에만_든_브랜치를_…`). `dev` 이름의 로컬 브랜치와 원격 추적 ref 없이 이름만 `origin/dev`인 브랜치는 오래 사는 브랜치가 아니다(`test_반박_로컬_dev_브랜치에만_…`, `test_반박_원격_추적_ref_없이_…`). `origin/dev`를 지우면 dev에만 있던 커밋이 다시 남는다(`test_반박_origin_dev_를_지우면_…`). 다른 원격 ref나 태그에만 있는 커밋은 오래 사는 브랜치에 든 것이 아니다(`test_반박_다른_원격_ref_나_태그에만_…`). 머리가 `dev`인 병합된 PR이 있어도 `dev`를 체크아웃한 워크트리를 지우지 않는다(`test_반박_dev_를_체크아웃한_워크트리는_…`). 모두 통과했다.
- `sibling_overlap`: dev가 main보다 뒤처졌을 때, 이력이 갈라진 dev를 받았을 때, dev 브랜치 자체에서, dev의 추적 ref가 없을 때, main에서 딴 열린 PR, hotfix 브랜치와 열린 PR이 dev가 쥔 번호에 다른 파일을 더할 때, 기준이 아닌 브랜치에서 물려받은 ADR을 옮길 번호에 넣지 않을 때(`test_반박_…` 여섯과 `test_dev가_…`·`test_hotfix_브랜치는_…`·`test_origin_dev가_…` 시험들). 모두 통과했다.
- **PR 봇 첫 회차의 Major.** CodeRabbit이 `tools/sibling_overlap.py`의 `inherited` 분기를 짚었다. 기준이 아닌 오래 사는 브랜치(dev가 기준일 때의 main)의 끝이 이 브랜치의 조상일 때만 물려받은 ADR을 `ours`에서 뺐고, 이 브랜치를 딴 뒤 그쪽이 더 나아가면 물려받은 ADR도 이 브랜치의 새 번호로 셌다. `test_반박_딴_뒤_기준이_아닌_브랜치가_더_나아가도_물려받은_ADR은_옮길_번호에_들지_않는다`가 그 입력을 재현했고 수정 전에는 빨갰다(`이 브랜치의 새 번호: ADR 0002, ADR 0003`, `옮길 번호: ADR 0002 → 0004, ADR 0003 → 0005`로 `--move`가 main에서 물려받은 0002까지 옮기려 했다). 조상이 아닌 분기에서도 `HEAD`와의 merge-base 시점의 ADR을 `inherited`에 더하자 초록이다. agent-os `origin/dev`의 같은 분기(`git -C C:/project/agent show origin/dev:tools/sibling_overlap.py`로 읽었다)에도 이 줄이 없어, 같은 결함이 상류에 있다. agent-os에 알릴지는 사람이 정한다.
- **이 저장소에서 찾은 공백.** 변이 9번이 초록이었다. 보호 브랜치 이름의 대소문자 시험(`test_보호_브랜치는_이름의_대소문자와_상관없이_지우지_않는다`)은 체크아웃되지 않은 브랜치(`judge_branch`)만 거치고, 워크트리의 브랜치 견줌(`wt.branch.casefold() in PROTECTED_BRANCHES`)은 `casefold`를 빼도 아무 시험이 빨개지지 않았다. `Dev`·`DEV` 브랜치를 체크아웃한 워크트리가 병합된 PR 머리와 같으면 `지운다`로 나올 입력이다(`.claude/rules/tools.md`의 지우는 도구 반박 항목이 같은 값을 견주는 다른 자리에도 반박 입력을 넣어 보라고 한다). 그 입력의 시험 `test_반박_대소문자가_다른_보호_브랜치를_체크아웃한_워크트리도_지우지_않는다`를 더했고, 변이 9번이 그 시험에서 빨강이다. 이 시험은 agent-os에는 없다. agent-os에 알릴지는 사람이 정한다.
