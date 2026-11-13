# 병합까지 마친다

<!-- agent-os에서 옮긴 절차다(2026-11-09 킥오프 7단계). 괄호 속 대기열·일지·PR 번호는 agent-os의 기록이다. -->

next-session `SKILL.md` 순서 1의 본문이다. PR을 연 세션과 인계로 넘겨받은 세션이 이 파일을 Read로 열어 병합까지 마친다. 병합을 마치면 `SKILL.md`의 순서 2(다음 작업을 정한다)로 돌아간다.

## 병합 전

머리가 dev나 main인 PR(출시 PR, 되돌려 합치기 PR)은 이 절을 건너뛰고 아래 "출시 PR"과 "되돌려 합치기"의 절차를 따른다. 훅의 계기가 이 파일을 처음부터 읽게 해도 같다. 나머지 PR은 아래 넷을 차례로 거친다.

1. **PR 본문.** PR을 연 뒤 범위를 넓히는 커밋(PR 본문이 말하지 않은 결정, 대기열 항목, 영역을 더한 커밋. 이미 바꾼 파일 안의 새 결정도 든다)을 푸시하려면, 푸시하기 전에 `gh pr edit`으로 PR 제목과 본문("왜 이렇게 했나", "남긴 위험", "계약 영향", "변경된 영역")을 넓힌 범위로 먼저 고친다. claude-review는 푸시마다 돌며 처음에 제목과 본문을 읽고, 본문만 고친 것으로는 다시 돌지 않는다(`.github/workflows/claude-code-review.yml`의 `types`에 `edited`가 없다, 대기열 200).
2. **봇 회차.** 아래 넷을 차례로 거친다. 반영은 앞의 셋이 정한 대로 고치고 적은 것을 푸시한다.
   - **대기.** PR을 열었으면 마지막 푸시 뒤에 `@coderabbitai review` 코멘트를 남기고 상태를 **한 번** 읽는다. 초록이면 바로 아래 회차 세기로 가고(코멘트를 읽고 고치는 것은 반영에서 한다), pending이면 Bash 도구의 `run_in_background`로 `uv run python tools/wait_ci.py <번호>`를 띄우고 턴을 끝낸다. 검사와 CodeRabbit이 모두 끝나면 그 명령이 끝나며 이 세션을 다시 부르고, 출력의 마지막 줄이 결과와 다음 할 일이다(종료 코드와 못 보는 것은 그 독스트링). 통과 줄은 CodeRabbit이 리뷰했는지(`Review completed`) 한도에 걸렸는지(`Review rate limited`)를 함께 적는다. claude-review가 계정 한도로 빨갰으면 그 빨강을 실패로 세지 않고 CodeRabbit을 마저 기다리며, 통과 줄에 `claude-review: 계정 한도로 리뷰 없음(<한도 문구>)`을 덧붙인다. 그때 PR 코멘트에 마지막으로 리뷰를 받은 커밋(없으면 없다고)과 한도가 풀리는 시각을 남긴다. 잡 로그를 읽지 못하면 그 도구는 한도인지 모르는 빨강을 실패로 세고 끝 줄 앞에 `claude-review 이 한도인지 가르지 못했다`를 적는다. 그때는 `uv run python tools/gh_run_summary.py <run-id>`로 그 실행을 직접 읽어 가른다. 결과 블록이 `"is_error": true`이고 Claude의 말이 "You've hit your weekly limit"으로 시작하면 한도다(agent-os PR #172의 실행을 손으로 봤다. 이 규칙은 agent-os `docs/constitution/operations.md` 리뷰 파이프라인 3에서 옮겼다). 사람에게 끝나면 알려 달라고 하지 않는다. 앱의 감시가 깨우는 계기는 CI 실패, 충돌, 리뷰 코멘트이고(`set_monitor` 도구 설명) PR 구독도 연 지 몇 분 뒤에 생긴다(대기열 37의 4회차). 대기는 푸시마다 새로 띄우고, 앞 대기가 아직 돌면 TaskStop으로 멈춘 뒤 띄운다. 멈추지 않은 앞 대기는 헤드가 바뀐 것을 보고 끝나며 세션을 한 번 더 깨운다. 다른 이벤트로 깨어날 때마다 `gh pr checks`의 CodeRabbit 줄(`Review completed`)을 함께 보고, 끝났는데 코멘트가 없으면 요약 코멘트의 `Reviewing files … between` 범위가 현재 HEAD까지인지 본다.
   - **회차 세기.** PR 봇의 Minor·Nit은 푸시마다 새로 나와 병합이 미뤄진다(대기열 137). 그래서 둘째 회차부터는 Critical·Major만 고치고, 나머지는 지적마다 보류 이유를 PR 코멘트에 남긴 뒤 병합한다. 회차는 봇마다 센다. 그 봇이 이 PR에 낸 첫 리뷰가 첫 회차이고(한도에 걸려 리뷰가 없던 푸시는 세지 않는다), 첫 회차의 Minor·Nit은 고칠지를 지적마다 판단한다.
   - **뒤로 넘긴 일.** 어느 회차든 보류 이유가 그 일을 뒤의 작업으로 넘기는 것이면 그 일을 일지 "다음"에도 적는다. 병합 뒤의 지시문은 일지 "다음"으로 짓고 PR 코멘트를 다시 읽지 않는다(대기열 234). 그 일지 수정은 그 회차에 고친 것과 같은 커밋으로 병합 전에 푸시한다. 커밋하지 않은 수정은 4의 `headRefOid` 대조를 지나 병합에 실리지 않고, 일지만 따로 푸시하면 claude-review가 한 번 더 돈다(그 워크플로에 경로 거르기가 없다). 고친 것이 없는 회차라 일지만 푸시했으면 그 푸시로 돈 리뷰의 회차도 회차 세기대로 봇마다 세고, 그 리뷰에서 보류한 일은 다시 일지에 적어 푸시하지 않고 PR 코멘트와 다음 지시문의 "이어받을 상태"에 적는다. 일지만 푸시하기를 되풀이하면 봇이 푸시마다 새 지적을 내 끝나지 않는다. 병합한 뒤에야 일지에 빠진 일을 알았으면 그 일도 다음 지시문의 "이어받을 상태"에 적는다.
   - **반영.** `/git-pr-feedback`으로 검사와 코멘트를 반영한다. 반영 커밋의 푸시는 사용자에게 묻지 않는다. 그 사용자 수준 스킬의 6단계가 푸시를 먼저 확인하라고 하지만 이 절차에서는 건너뛴다(4의 병합과 같다. 묻고 턴을 끝내면 대기가 뜨지 않아 세션이 깨어나지 않는다).
3. **일지.** 셀프 리뷰가 고친 것이 실리도록 일지는 `/code-review` 뒤에 마무리한다(대기열 2). 리뷰의 보고와 반영은 마무리를 기다리지 않고 받은 턴에 옮긴다(`code-review` 6단계 끝, 대기열 244). 일지 파일 이름은 `docs/journal/<날짜>-<HHMM>-<슬러그>.md`이고, 앞부분은 그 파일을 만드는 지금의 로컬 날짜와 시분이다. Bash의 `date +%Y-%m-%d-%H%M`이나 PowerShell의 `Get-Date -Format yyyy-MM-dd-HHmm`으로 짓고 번호는 받지 않는다(agent-os ADR 0045 결정 7). 파일을 처음 만들 때 머리 한 줄만 든 일지 파일을 먼저 만든다(이 절차보다 앞서 만들어도 된다). 먼저 만들고 늦게 병합해도 이름을 옮기지 않는다. 같은 분에 만든 다른 일지가 main에 먼저 들어가 있으면 인용 `일지 <날짜>-<HHMM>`이 둘로 풀리므로, 늦게 병합되는 쪽의 세션이 분을 바꿔 이름과 이 브랜치가 들인 인용을 고친다. 그 겹침을 막는 일지 이름 시험은 agent-os의 `tests/test_journal_names.py`이고 이 저장소에는 아직 없어, 병합 전에 `docs/journal/`을 그 앞부분으로 Glob해 본다. 단계를 닫는 세션이면 일지의 "다음" 절이 이미 갱신되어 있다. 없으면 여기서 쓴다. 그 세션은 회고(`retro`)와 "다음"까지 마친 일지를 4(병합 길)의 `headRefOid` 대조 전에 푸시한다. 늦어도 마지막 봇 회차의 커밋에 싣고, 그 회차에 고친 것이 없으면 일지만 실은 커밋을 푸시한다(그 푸시로 도는 리뷰도 2의 회차 세기대로 센다, 대기열 341).
4. **병합 길.** 병합 직전에 `gh pr view --json headRefOid`와 `git rev-parse HEAD`가 같은지 본다. `gh pr checks`의 초록은 이전 커밋의 것일 수 있다(agent-os PR #44 실측. 푸시 직후 GitHub가 PR head를 갱신하기 전에 조회하면 이전 커밋의 결과가 보였다). 그 뒤 병합한다. 병합은 PR을 연 세션의 일이고, 인계로 넘겨받은 세션도 그 세션으로 센다. 병합할지는 사용자에게 묻지 않는다. PR이 문서가 사용자의 승인으로 정한 결정을 담으면(ADR 승인, 계약(검색 도구의 형식, 수집 API, 커넥터·변환·파서 인터페이스, 색인 형식)과 헌법의 변경이 그 예다. `CLAUDE.md` 작업 규약 5, 헌법 거버넌스) 그 승인은 병합 전에 받고, 받았으면 병합은 묻지 않는다(대기열 268). 주 체크아웃에서 열었으면 `/git-pr-merge`로 하고 그 뒤 Skill 도구로 `tidy-checkouts`를 돈다(병합된 워크트리와 로컬 브랜치를 지운다). `/git-pr-merge`는 실패한 체크가 있으면 멈추므로, 실패가 claude-review의 계정 한도뿐이면 아래 "워크트리에서 병합할 때" 1~3으로 병합한 뒤 `tidy-checkouts`를 돈다. **워크트리에서 열었으면** 아래 "워크트리에서 병합할 때"의 길로 한다. `/git-pr-merge`는 단일 체크아웃을 전제해 워크트리에서는 main을 가로채거나 실패한다. base가 dev인 PR과 머리가 dev인 출시 PR은 주 체크아웃에서도 `/git-pr-merge`를 쓰지 않고 "워크트리에서 병합할 때" 1~3(머리가 dev인 출시 PR은 3을 건너뛴다)으로 병합한 뒤 `tidy-checkouts`를 돈다. 사용자 수준 스킬이라 이 저장소가 dev를 가르치지 못하고(저장소 밖이라 고치지 않는다), 그 스킬은 squash와 `--delete-branch`로 병합해 출시 PR의 머리 dev를 지운다. 병합 방법은 PR 종류가 정한다(아래 "병합 방법"). 핫픽스(머리가 `hotfix/*`)였으면 병합 뒤 아래 "되돌려 합치기"까지 해야 끝이다.

## 병합 방법

기준 브랜치의 규칙은 `docs/constitution/operations.md` 브랜치와 병합이 원천이다. 이 파일이 직접 치는 병합 명령(워크트리에서 병합할 때의 2와 되돌려 합치기 4)에는 언제나 `--match-head-commit <머리 SHA>`를 붙인다. `/git-pr-merge`는 이 옵션을 받지 않으므로 그 길의 머리 대조는 위 4(병합 길)의 `headRefOid` 대조가 맡는다. 티켓 PR과 핫픽스의 머리 SHA는 이 브랜치의 `git rev-parse HEAD`이고, 출시 PR과 되돌려 합치기 PR의 머리는 dev와 main이라 `gh pr view <번호> --json headRefOid`의 값이다. 병합 방법과 base는 PR 종류가 정하므로 표에서 사용자에게 묻지 않는다(ADR 0016이 따르는 agent-os ADR 0043). 승인을 먼저 받아야 하는 PR(ADR 승인이나 헌법 변경을 담은 것)은 위 4(병합 길)가 정한 대로 병합 전에 받는다.

| PR | 머리 → base | 병합 | 병합 뒤 |
|---|---|---|---|
| 티켓 PR(`feature/*`, `chore/*`)과 티켓이 없는 면제 PR(`docs/*`) | 이 브랜치 → 기준 브랜치(`origin/dev`가 있으면 dev, 없으면 main) | `--squash` | 워크트리에서 열었으면 아래 "워크트리에서 병합할 때" 3~5, 주 체크아웃이면 `tidy-checkouts` |
| 핫픽스 | `hotfix/*` → main | `--squash` | 3과 4, 그 뒤 "되돌려 합치기", 그 뒤 5 |
| 출시 PR | dev → main | `--merge` | 머리 브랜치를 지우지 않는다(3을 건너뛴다). 아래 "출시 PR"의 병합 뒤대로 dev가 원격에 남았는지 보고 main을 dev에 되돌려 합친다 |
| 되돌려 합치기 PR | main → dev | `--merge` | 머리 브랜치를 지우지 않는다(3을 건너뛴다) |

기준 브랜치가 dev인 티켓 PR은 dev에 strict가 없어 뒤처진 채로도 병합된다. 나란히 도는 티켓 PR이 각자 초록으로 병합된 뒤 dev가 빨개질 수 있으므로, 병합 직전에 `git fetch origin`을 치고 `git merge-base --is-ancestor origin/dev HEAD`가 1이면 `origin/dev`를 이 브랜치에 합치고 `uv run pytest tests/test_plan_status.py`를 직접 돌린 뒤 푸시한다(`docs/constitution/operations.md` 브랜치와 병합). 푸시하면 머리 SHA가 바뀌므로 위 2(봇 회차)의 대기부터 다시 한다.

티켓 PR과 핫픽스는 squash로 티켓 하나가 커밋 하나인 이력을 지킨다. 출시 PR과 되돌려 합치기 PR을 squash하면 두 브랜치에 같은 변경이 서로 다른 커밋으로 남아, 다음 합치기가 같은 변경을 다시 싣고 충돌한다. 그래서 둘은 merge 커밋이다.

출시 PR과 되돌려 합치기 PR은 보호 설정에 걸리면 병합하지 않고 사용자에게 넘긴다. 보호 설정은 main이 `tools/protection.json`, dev가 `tools/protection-dev.json`이고(dev는 티켓 `04-dev-branch-create`가 2026-11-12에 따고 만들었다), 두 브랜치 모두 선형 이력을 강제하지 않아 merge 커밋을 받는다(ADR 0016). dev는 strict가 아니라 머리가 main인 되돌려 합치기 PR이 뒤처진 것으로 막히지 않는다. main은 strict를 그대로 둔다(사용자가 2026-11-13에 티켓 `05-dev-release-pr-step`에서 정했다). main이 strict라 출시 PR은 dev가 main의 머리를 품어야 병합되는데, 앞 출시 PR의 merge 커밋은 dev에 없으므로 되돌려 합치지 않으면 둘째 출시 PR부터 `BEHIND`가 날 것으로 본다(커밋 관계로 따진 어림이고 이 저장소에서는 출시 PR로 재 보지 않았다). 그래서 출시 PR을 병합한 세션이 바로 main을 dev에 되돌려 합친다(아래 "출시 PR"의 병합 뒤). 보호 설정을 바꾸는 두 길(출시 PR만 `gh pr merge --admin`으로 병합하기, main의 strict 끄기)은 사용자가 고르지 않았으므로 출시 PR에 `--admin`을 붙이지 않는다. 필수 검사 `verify`의 출처는 main이 `app_id` null이고 dev가 15368로 다르지만 그대로 둔다(두 JSON을 `checks`로 쓰면 맞출 수 있다. 같은 날 사용자가 맞추지 않기로 했다). 저장소의 자동 삭제(`delete_branch_on_merge`)는 2026-11-12에 `gh api`로 읽은 값이 꺼짐(false)이라 머리(dev, main)가 지워지지 않는다. 두 파일은 모두 삭제도 막는다(`allow_deletions: false`).

끝: PR이 병합됐고, 뒤로 넘긴 봇 지적의 일이 병합된 일지 "다음"이나 다음 지시문의 "이어받을 상태"에 있고, 뒷단계가 남아 있지 않다. 핫픽스였으면 "되돌려 합치기"의 끝 줄까지 찼다.

## 워크트리에서 병합할 때

워크트리 세션은 다른 체크아웃을 바꾸지 않는다. 앱의 워크트리 가드가 Bash 도구에서 주 체크아웃을 당기는 `git -C <루트> pull`을 거부한 것이(일지 `2026-10-02-06`·`2026-10-03-02`) 그 경계다. 주 체크아웃을 당기거나 다른 워크트리를 지우는 일은 주 체크아웃 세션의 `tidy-checkouts`에 넘긴다. 이 세션이 여는 새 세션이 보통 `EnterWorktree` 전의 첫 턴에 그 주 체크아웃 세션이다(4). 셸에서 `git -C <루트>`로 대신 당기는 길은 쓰지 않는다. 가드를 돌아가는 길이다. 워크트리의 기준은 `origin/<기준 브랜치>`다(`CLAUDE.md` 환경 함정, 5). 이 절의 1~3은 PR 종류마다 다른 병합 방법과 base를 위 "병합 방법"의 표에서 읽는다.

1. **확인.** `gh pr view --json mergeable,mergeStateStatus,baseRefName,headRefOid`가 병합할 수 있다고 하고(`UNKNOWN`이면 다시 본다), base가 표의 그 PR 종류의 base(티켓 PR은 `origin/<기준 브랜치>`의 이름, 핫픽스와 출시 PR은 main, 되돌려 합치기 PR은 dev)이고, `gh pr checks`에 실패가 없고(claude-review가 계정의 주간 사용량 한도로만 빨가면 실패로 세지 않고 기다리지 않는다. 그때 `mergeStateStatus`가 `UNSTABLE`이어도 병합할 수 있다는 값이다. 알아보는 법과 PR 코멘트에 남길 것은 위 2(봇 회차)의 대기), `headRefOid`가 위 "병합 방법"의 머리 SHA와 같다. pending이면 위 2(봇 회차)대로 `tools/wait_ci.py`를 백그라운드로 띄우고 턴을 끝낸다.
2. **병합.** `gh pr merge <번호> --squash --match-head-commit <HEAD>`(출시 PR과 되돌려 합치기 PR은 `--squash` 대신 `--merge`). `--delete-branch`는 쓰지 않는다. 그 플래그는 병합 뒤 작업 폴더에서 base 브랜치(main이나 dev)로 `git checkout`을 쳐서, 그 브랜치가 어디에도 체크아웃되어 있지 않으면 이 워크트리가 base 브랜치를 가져가 주 체크아웃이 그 브랜치로 돌아가지 못하고, 주 체크아웃이 그 브랜치면 실패해 원격 삭제를 건너뛴다(대기열 39). 사용자 수준 `/git-pr-merge`가 이 플래그를 쓰므로 워크트리에서는 그 스킬을 부르지 않는다.
3. **원격 정리.** `git fetch --prune origin` 뒤 `git ls-remote --exit-code --heads origin refs/heads/<브랜치>`의 종료 코드로 원격에 그 브랜치가 남았는지 본다. 패턴은 ref 이름의 꼬리와 맞대므로 `refs/heads/`까지 적어야 `old/<브랜치>` 같은 다른 브랜치를 잡지 않는다. 저장소가 병합한 PR의 브랜치를 스스로 지우게 켰으면(`delete_branch_on_merge`. agent-os는 2026-10-27에 켰다) 대개 이미 지워졌고, `--prune`은 원격에서 지워진 브랜치를 가리키던 `origin/<브랜치>`를 걷는다. 판정은 `ls-remote`의 종료 코드로만 한다. `fetch`가 실패하면 `origin/<브랜치>`가 남고 `origin/<base 브랜치>`도 병합 전에 머무므로, 5로 이어 가기 전에 `git fetch --prune origin`을 다시 치고, 그래도 실패하면 5로 잇지 않고 그 오류 문구를 보고에 남긴다.
   - 2(출력 없음)면 원격에 그 브랜치가 없다.
   - 0(그 브랜치의 줄이 나옴)이면 먼저 `gh pr view <번호> --json state`를 본다. `OPEN`이면 병합(2)이 끝나지 않은 것이라 1로 돌아간다. 열린 PR의 머리를 지우는 푸시를 막는 `tools/hook_push_delete_open_pr.py`는 PR을 읽지 못하면 막지 않는다. `MERGED`면 자동 삭제가 꺼졌거나 늦거나 돌지 않은 것이라 `git push origin --delete <브랜치>`로 지우고, 그 명령이 어떻게 끝나든 `git fetch --prune origin`과 같은 `ls-remote`로 다시 본다. 다시 봐도 0이면 `원격 브랜치 남음: <브랜치> (<까닭>)` 한 줄을 쓴다. 까닭은 지우는 명령이 막히거나 실패한 모양(분류기 거부, 훅 차단, 오류 문구)이다. 상태를 읽지 못했거나 그 밖의 값(`CLOSED`)이면 지우지 않고 `원격 브랜치 미확인: <브랜치> (<오류 문구나 상태>)` 한 줄을 쓴다.
   - 0과 2 밖의 종료 코드면 판정하지 못한 것이다. 원격에 닿지 못하면 128이고 출력이 비어 2와 같아 보인다. 한 번 다시 치고, 또 그러면 `원격 브랜치 미확인: <브랜치> (<오류 문구>)` 한 줄을 쓴다.

   남음·미확인 줄은 보고와 일지에 남기고 다음 지시문의 "이어받을 상태"에 옮긴다(대기열 497).
4. **주 체크아웃은 새 세션에 넘긴다.** 당기지 않고 병합된 워크트리도 지우지 않는다. `git worktree list`의 첫 줄로 루트의 브랜치를 보고, 보고와 일지에 `주 체크아웃 미갱신: 루트는 <브랜치>` 한 줄을 남긴다. 새 세션을 열면 `directive.md`대로 지시문의 "확인할 선행 조건"과 "어디서" 줄에 적고, 그 세션이 워크트리에 들어가기 전에 Skill 도구로 `tidy-checkouts`를 돈다(나란히 여는 묶음이면 첫 세션만). 무엇을 당기고 지우는지는 그 스킬이 정한다. 새 세션을 열지 않으면(결정표의 "이 세션") 미갱신은 다음에 새 세션을 열 때까지 남고, 그때 `directive.md`가 다시 적게 한다. 다만 훅 래퍼(`tools/launch_hook.py`)를 들이거나 옮긴 PR이면 병합 직후 당겨야 하므로(`.claude/rules/tools.md`) 기다리지 않고, 보고의 그 한 줄에 사람이 주 체크아웃 세션에서 `/tidy-checkouts`를 쳐 달라는 부탁을 붙인다. 당겨지기 전에는 새 세션과 훅이 주 체크아웃의 옛 하네스로 돈다(`.claude/rules/tools.md`의 `CLAUDE_PROJECT_DIR` 항목).
5. **이어 갈 때.** 다음 브랜치는 `git switch -c <다음 브랜치> origin/<다음 브랜치의 기준 브랜치>`로 딴다(`git fetch origin`을 먼저 친다. 다음 브랜치가 `hotfix/*`면 `origin/main`. 방금 병합한 PR이 핫픽스였으면 "되돌려 합치기"를 마친 뒤에 딴다). squash된 옛 브랜치 위에서 따면 병합된 커밋을 다시 싣는다. `/git-branch`의 `git checkout main`은 루트가 main이면 실패하고, main이 어디에도 없으면 이 워크트리가 main을 가져가며, 기준 브랜치가 dev면 틀린 브랜치에서 딴다.

머리 브랜치가 main이나 dev인 PR(출시 PR, 되돌려 합치기 PR)은 3을 건너뛴다. 그 브랜치는 지우지 않는다.

끝: PR이 병합됐고, (3을 건너뛴 PR이 아니면) 3의 `ls-remote`가 2로 끝났거나 `원격 브랜치 남음`·`원격 브랜치 미확인` 한 줄이 보고에 있고, 4를 거쳤으면 미갱신 한 줄이 보고에 있다.

## 출시 PR

dev의 머리를 main에 올린다. 병합 방법은 위 "병합 방법"의 표이고 사용자 승인은 받지 않는다(ADR 0016이 따르는 agent-os ADR 0043). 이 절의 순서는 agent-os가 그 저장소의 첫 출시 PR(#542)과 되돌려 합치기 PR(#543)로 거쳐 보고 정한 것을 옮겼다. 이 저장소에서는 아직 출시 PR을 열어 본 적이 없어, 아래의 명령과 판정(검사 줄, 건너뜀 상태, `BEHIND`)은 agent-os에서 본 것이고 여기서 다시 보지 않았다. 이 절의 끝 줄은 맨 뒤에 있다.

**이어받기.** 이 세션이나 앞 세션이 연 출시 PR이 열린 채 끊겼으면(압축 뒤, 인계 뒤, 검사 빨강, 머리 이동) 먼저 `git fetch origin`을 치고, 계기와 전제 확인과 열기를 건너뛰고 기다림부터 한다. `gh pr list --base main --head dev --state open`이 그 PR의 번호를 낸다. 출시 세션은 dev와 main에 커밋하지 못해 일지를 실을 PR이 없으므로 번호는 PR을 연 직후 보고에 적어 두고(일지를 쓰는 세션이면 일지에도), 이어받을 때는 번호와 `headRefOid`를 `gh pr list`와 `gh pr view <번호> --json headRefOid`로 다시 읽는다. 결정표의 출시 줄은 열린 출시 PR이 진행하다 끊긴 것이어도 고르고(조건은 그 줄), 그때는 새로 열지 않고 이 이어받기로 잇는다. 출시 세션은 일지를 못 남기므로 사용자에게 넘길 때는 PR 코멘트에 `사용자에게 넘김: <까닭>`을 남기고(`gh pr comment <번호> --body "<코멘트>"`), 그 코멘트가 있는 열린 PR은 결정표가 고르지 않는다.

**계기.** 기능 계획의 `**끝:**` 줄을 적은 커밋이 dev에 있고 main에 없으며, 열린 출시 PR이 없으면 출시할 때다. `git fetch origin` 뒤 `git log origin/main..origin/dev -G'^\*\*끝:\*\*' --format='%h %s' -- '.scratch/*/plan.md'`가 한 줄 이상이고 `gh pr list --base main --head dev --state open`이 비었다. 기능의 마지막 티켓을 병합한 세션이 보통 그 세션이다(그 PR의 커밋이 끝 줄을 적는다. `docs/agents/issue-tracker.md` "끝 줄을 적는 때"). 그 세션이 못 했거나 보류했으면 다음 병합 뒤에 결정표가 같은 상태를 보고 같은 줄을 고른다. 하네스 기능(`**슬라이스:**` 줄이 없어 끝 줄을 적지 않는 기능과 harness 티켓)은 계기가 아니다. 다음 기능의 출시 PR에 실려 오른다.

**전제 확인.** 둘 다 맞을 때만 연다. 어긋나면 열지 않고 `출시 보류: <까닭>` 한 줄을 보고에 쓴다. 그 세션에서는 출시 줄을 건너뛰고 결정표의 다음 줄에서 고른다(계기 조건은 그대로 참이라 표를 처음부터 다시 읽으면 이 줄이 또 선택된다).
1. main CI가 초록이다. `gh run list --branch main --workflow ci.yml --event push --limit 1 --json status,conclusion,headSha,url`의 `headSha`가 `git rev-parse origin/main`과 같고 `status`가 `completed`, `conclusion`이 `success`다. `--event push`가 없으면 머리가 main인 되돌려 합치기 PR의 실행이 첫 줄에 올 수 있어 push 실행이 진행 중이거나 빨강이어도 초록으로 읽힌다(agent-os에서 #543을 연 뒤 본 모양이다). 어긋나면 열지 않는다. `headSha`가 `origin/main`과 다르면(방금 병합돼 실행이 아직 없다) `출시 보류: main CI 아직 없음 <origin/main의 SHA>`, `status`가 `completed`가 아니면 `출시 보류: main CI 진행 중`, `conclusion`이 `success`가 아니면(`failure`, `cancelled`) `출시 보류: main CI <conclusion> <url>`이다. 빨간 main은 이 절차가 고치지 않는다.
2. dev가 main의 끝 커밋을 품었다. `git merge-base --is-ancestor origin/main origin/dev`가 0이다. 1이면 먼저 아래 "되돌려 합치기"를 마친다. main이 strict라 이것이 아니면 출시 PR이 `BEHIND`로 막힌다.

이 PR에는 위 "병합 전"의 봇 회차와 일지를 하지 않는다. 합치는 내용은 티켓 PR이 그 절차를 이미 거쳤다. 머리가 dev라 `git rev-parse HEAD`가 아니라 병합 직전 `gh pr view <번호> --json headRefOid`로 읽은 값이 머리 SHA다(위 "병합 방법").

**열기.** 제목은 `chore: <끝낸 기능 slug들>을 main에 출시한다`이고(slug는 계기 명령에 `--name-only`를 더해 읽은 `.scratch/<slug>/plan.md`의 `<slug>`다. 한 커밋이 여러 plan.md의 끝 줄을 한꺼번에 채운 일괄 편집이면 그 커밋의 slug는 쓰지 않고 마지막 티켓 PR의 제목을 읽는다), 본문은 `.github/PULL_REQUEST_TEMPLATE.md`가 아니라 아래 넷이다. 그 서식은 티켓 PR의 "왜"와 "남긴 위험"과 체크리스트를 묻는데, 출시 PR은 새 변경 없이 dev의 커밋을 그대로 올리고 리뷰 봇도 돌지 않는다(머리가 dev이면 claude-review는 건너뛰고 CodeRabbit은 요청하지 않는다. 티켓 `02-dev-review-bot-off`).
- `## 올리는 기능`: 끝 줄을 적은 기능의 slug와 그 마지막 티켓 PR 번호.
- `## 함께 오르는 진행 중 조각`: `.scratch/plan.md`에서 상태가 in-progress인 기능의 slug. 없으면 "없음". dev의 티켓 PR은 모두 dev의 CI를 지났고 출시 PR도 같은 검사(`ci.yml`의 `python`, `image`, `ticket`과 필수 검사 `verify`)를 다시 지나며, 끝나지 않은 기능의 조각이 올라도 머리는 그 검사를 지난 상태다. 그래서 막지 않고 알리기만 한다. 하네스 기능의 변경도 함께 오르며 여기에 적을 필요는 없다.
- `## 전제`: 전제 확인 1의 실행 주소와 `headSha`, 2의 `--is-ancestor`가 0이라는 것.
- `## 병합`: `merge 커밋, 사용자 승인 없음(ADR 0016), 병합 뒤 main을 dev에 되돌려 합친다`.

```
gh pr create --base main --head dev --title "<제목>" --body-file <본문 파일>
```

**기다리고 병합한다.** 봇 회차를 하지 않으므로 `uv run python tools/wait_ci.py <번호> --head <dev의 SHA> --expect verify`를 백그라운드로 띄우고 턴을 끝낸다(`<dev의 SHA>`는 PR을 연 직후면 `git rev-parse origin/dev`이고, 이어받을 때는 `gh pr view <번호> --json headRefOid`의 값이다. 로컬 `origin/dev`가 옛 값이면 헤드가 어긋난다. 되돌려 합치기 PR의 기다림과 같다). 종료 4와 `끝: CodeRabbit 리뷰가 요청되지 않았다`가 정상이고(`wait_ci`가 CodeRabbit의 건너뜀 상태를 요청 전으로 읽는다. CodeRabbit이 건너뜀 상태를 남기지 않으면 0일 수도 있다), 검사 줄에서 CodeRabbit과 `claude-review`(둘 다 SKIPPED)를 뺀 전부가 SUCCESS이면 "워크트리에서 병합할 때" 1~2대로 병합한다(`--merge`, `--admin` 없음. 머리가 dev라 3은 건너뛴다). PR을 연 직후 번호를 보고에 적어 둔다(이어받기가 읽는다).
- dev는 움직이는 머리다. 기다리는 동안 다른 티켓 PR이 dev에 병합되면 PR의 머리가 바뀌어 `wait_ci`가 "헤드가 바뀌었다"로 끝나거나(종료 4) 병합이 `--match-head-commit` 불일치로 거절된다. 둘 다 새 `headRefOid`와 `git rev-parse origin/dev`로 기다림부터 다시 한다. 새로 올라온 조각은 `## 함께 오르는 진행 중 조각`에 더한다. `wait_ci`가 종료 1(검사 실패)이면 병합하지 않고 실패한 검사를 보고에 쓴 뒤 PR 코멘트 `사용자에게 넘김: <까닭>`과 함께 사용자에게 넘긴다. 빨간 dev는 이 절차가 고치지 않는다.
- `mergeStateStatus`가 `BEHIND`면 병합하지 않는다. 전제 확인 2가 맞은 뒤에 main이 움직인 것(핫픽스)이다. "되돌려 합치기"를 마치고 새 `headRefOid`로 기다림부터 다시 한다.
- `CONFLICTING`이거나 보호 설정이 병합을 거절하면 병합하지 않고 PR 코멘트 `사용자에게 넘김: <까닭>`과 함께 사용자에게 넘긴다.

**병합 뒤.**
1. dev가 원격에 남았는지 본다. `git fetch --prune origin` 뒤 `git ls-remote --exit-code --heads origin refs/heads/dev`가 0이면 남았다. 저장소의 자동 삭제(`delete_branch_on_merge`)가 머리 dev를 지우지 않는다는 것은 agent-os의 첫 출시 PR 하나로 본 것이고 이 저장소에서는 보지 않았다(값은 꺼짐이고 dev는 삭제도 막혀 있다). 2면 지워진 것이다. 병합한 출시 PR의 `gh pr view <번호> --json headRefOid`가 낸 값(병합한 PR도 머리의 SHA를 계속 낸다)으로 `git push origin <headRefOid>:refs/heads/dev`로 되살리고 `gh repo view --json defaultBranchRef`로 기본 브랜치를 본 뒤, 되돌려 합치기(2)를 되살린 dev에 대고 마치고 나서 사용자에게 넘긴다. 이 갈래는 밟은 적이 없다. 이 세션이 이 확인 전에 끊기면 결정표의 두 줄이 모두 `origin/dev`를 요구해 이 갈래를 잇는 줄이 없으므로 병합한 직후 같은 턴에 한다. 이 확인은 "워크트리에서 병합할 때" 3을 대신한다(그 절은 머리가 dev인 PR에서 건너뛴다). 다른 곳에서 dev가 지워지고 `fetch --prune`이 `origin/dev`를 걷으면 기준 브랜치 규칙(`tools/base_rule.py`)이 조용히 main으로 돌아가므로 이 확인을 빼지 않는다.
2. main을 dev에 되돌려 합친다. 아래 "되돌려 합치기"의 1~5다. 병합한 출시 PR의 merge 커밋이 dev에 없으므로 1의 판정이 1로 나온다. 이 단계 전에 끊기면 결정표의 첫 줄(되돌려 합치기)이 같은 상태를 읽고 이어 간다. dev가 원격에서 지워진 채 끊겼으면 그 첫 줄의 조건(`origin/dev`가 있고)이 맞지 않으므로 이 1부터 다시 한다.
3. 보고에 `출시: PR <번호>, main <git rev-parse origin/main>`을 쓴다.

끝: 출시 PR이 병합됐고, 병합 뒤의 1~2가 끝났거나 사용자에게 넘긴 사유가 보고에 있다. 전제 확인이 어긋나 열지 않았으면 `출시 보류: <까닭>` 한 줄이 보고에 있다.

## 되돌려 합치기

핫픽스를 main에 병합한 세션이 바로 한다. 출시 PR을 병합한 세션도 같다(merge 커밋이 main에만 남는다). 결정표의 첫 줄이 가리킨 세션도 한다(병합하고 잊은 경우다). 끝낸 세션은 결정표로 돌아가 원래 줄을 고른다. 되돌려 합치지 않으면 핫픽스가 dev에 없다. 그 위에 쌓이는 dev의 변경은 핫픽스 없이 시험되고, 같은 곳을 고쳤으면 다음 출시 PR(dev→main)에서 충돌할 수 있다. 도중에 세션이 끊겨 열린 되돌려 합치기 PR만 남았으면 결정표의 첫 줄이 이 절로 오고, 아래 1이 그 PR을 찾아 3부터 잇는다.

**PR로 한다.** 머리가 `main`이고 base가 `dev`인 PR을 열어 merge 커밋으로 병합한다. 로컬에서 합치고 `dev`로 푸시하는 길은 쓰지 않는다. `dev` 위의 커밋을 막는 훅은 `git commit`만 보므로 병합 커밋을 지나가지만(`tools/hook_git_main_commit.py` 독스트링), CI가 합친 결과를 돌려 보지 못한 채 dev의 머리가 필수 검사 없이 바뀐다(관리자 우회에 기댄다). 머리가 main인 PR은 커밋 검사(`check_ticket`)가 티켓 없이 지난다.

이 PR에는 위 "병합 전"의 봇 회차와 일지를 하지 않는다. 합치는 내용은 핫픽스 PR이 그 절차를 이미 거쳤다. 리뷰 봇이 이 PR에서 어떻게 도는지는 `docs/constitution/operations.md` 리뷰 파이프라인이 적는다.

1. **필요한지 본다.** `git fetch origin` 뒤 `git ls-remote --exit-code --heads origin refs/heads/dev`가 2로 끝나면 dev가 없다. dev를 아직 따기 전이면 합칠 곳이 없으니 끝이다(핫픽스가 main에 오르는 것이 곧 기준 브랜치에 오르는 것이다). 출시 PR을 방금 병합했는데 2이면 dev가 지워진 것이므로 끝내지 않고 "출시 PR"의 병합 뒤 1(되살리기)로 간다. dev가 있고 `git merge-base --is-ancestor origin/main origin/dev`가 1이면 main에만 있는 커밋이 있다. 0이면 main의 모든 커밋이 dev에 있어 합칠 것이 없으니 끝이다. 변경 내용(`git diff`)이 아니라 커밋 포함으로 가른다. 출시 PR의 merge 커밋은 main에만 있고 내용은 dev와 같을 수 있는데, main의 strict는 머리가 main의 끝을 포함하라고 해서 그 커밋이 dev에 없으면 다음 출시 PR이 뒤처졌다고 막힌다(ADR 0016의 main 보호 설정). `gh pr list --base dev --head main --state open`에 PR이 이미 있으면 새로 열지 않고 그것으로 3으로 간다.
2. **연다.** `gh pr create --base dev --head main --title "chore: main을 dev에 되돌려 합친다" --body "<main에만 있는 변경의 PR 번호들과 한 줄>"`. 번호는 `git log origin/dev..origin/main --oneline`에서 읽는다. 핫픽스를 방금 병합한 세션이 아니어도 이 명령으로 알 수 있다.
3. **기다린다.** 위 "병합 전" 2의 대기대로 `tools/wait_ci.py`를 백그라운드로 띄우고 턴을 끝낸다. 이 PR은 봇 회차를 하지 않아 CodeRabbit을 요청하지 않는다. `uv run python tools/wait_ci.py <번호> --head <머리 SHA> --expect verify`로 띄우면 `verify`를 기다리지만, `--expect`가 CodeRabbit의 건너뜀 줄을 없애지는 못해 종료 4와 `끝: CodeRabbit 리뷰가 요청되지 않았다`로 끝나는 것이 정상이다(agent-os의 출시 PR #542와 되돌려 합치기 PR #543에서 본 모양이고 이 저장소에서는 다시 보지 않았다). `--head`를 빼면 이 세션의 로컬 HEAD를 기다릴 헤드로 읽어 어긋난다. `<머리 SHA>`는 띄우기 직전에 `gh pr view <번호> --json headRefOid`로 읽는다(열린 PR로 바로 이 단계에 왔거나 그새 main이 앞섰을 수 있어 `git rev-parse origin/main`을 믿지 않는다). 끝 알림의 보고에서 `verify`가 SUCCESS면 4로 간다. 종료 코드는 0이거나, CodeRabbit이 "Review skipped" 상태를 남겼을 때의 4(`tools/wait_ci.py`가 이 상태를 요청되지 않은 리뷰로 읽고 `--expect`와 무관하게 센다)일 수 있다. 이 PR은 CodeRabbit을 요청하지 않으므로 4의 "리뷰가 요청되지 않았다" 문구는 예상한 끝이다. 보고에 `verify` 줄이 없는 4(gh 조회 실패나 헤드 불일치)와 2(인자 오류)는 새 `headRefOid`로 이 단계를 다시 띄운다. 종료 1(충돌이나 실패)이나 3(시간 초과)이면 병합하지 않고 보고를 사용자에게 넘긴다. 실패한 검사가 `claude-review`뿐인 1도 넘긴다. 핫픽스가 `claude-code-review.yml`을 바꿨다면 이 PR에서 그 워크플로의 코멘트 0개 가드가 빨개질 수 있다(티켓 `02-dev-review-bot-off`의 결정). 필수 검사가 아니므로 병합할지는 사용자가 정한다.
4. **병합한다.** `gh pr view <번호> --json mergeable,mergeStateStatus,headRefOid`로 보고 `gh pr merge <번호> --merge --match-head-commit <headRefOid>`를 친다. 그새 main이 앞서 이 명령이 머리 SHA 불일치로 거절되면 새 `headRefOid`로 3부터 다시 한다. `--delete-branch`는 쓰지 않는다. 머리가 main이다. 아래 세 경우에는 병합하지 않고 사용자에게 넘긴다. 셋째는 위 "병합 방법"이 적은 보호 설정이다.
   - `mergeable`이 `CONFLICTING`이다. 핫픽스와 dev의 변경이 같은 곳을 고쳤으니 어느 쪽을 남길지 사람이 정한다.
   - `mergeStateStatus`가 `BEHIND`다. base(dev)에 "최신 브랜치만 병합"(strict) 보호가 걸렸을 때 나온다. dev는 strict가 아니므로(`tools/protection-dev.json`) 나오면 보호 설정이 바뀐 것이다. 머리가 main이라 dev에 늘 뒤처져 보인다. `gh pr update-branch`나 웹의 "Update branch"를 누르지 않는다. 그 동작은 dev를 main에 합친다. 관리자 우회로 병합할지는 사용자가 정한다.
   - `gh pr merge`가 보호 설정(필수 검사 미충족 등)에 거절된다. 거절 문구를 사용자에게 넘긴다.
5. **확인한다.** `git fetch origin` 뒤 `git merge-base --is-ancestor origin/main origin/dev`가 0이다.

끝: dev가 아직 없거나(1), 위 5의 판정이 0이거나, 사용자에게 넘긴 사유(`CONFLICTING`, `BEHIND`, 보호 설정의 거절 문구)를 보고와 일지에 적었다. 사용자에게 넘긴 채 끝났으면 열린 PR(`gh pr list --base dev --head main --state open`)이 남아 `--is-ancestor` 판정이 계속 1이다. 결정표 첫 줄은 사용자에게 넘긴 이 열린 PR을 고르지 않는다. 진행하다 끊긴 열린 PR(`CONFLICTING`·`BEHIND`가 아니고 넘긴다는 기록이 없다)은 고르고, 1이 그 PR을 찾아 3부터 잇는다.
